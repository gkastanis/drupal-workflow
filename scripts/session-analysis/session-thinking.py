#!/usr/bin/env python3
"""Thinking token analysis for Claude Code JSONL logs."""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Per-MTok pricing
PRICES = {"input": 15.0, "output": 75.0, "cache_create": 18.75, "cache_read": 1.50}


def warn(msg):
    print(f"warning: {msg}", file=sys.stderr)


def dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def jsonl_files(path):
    p = Path(path)
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(x for x in p.iterdir() if x.is_file() and x.suffix == ".jsonl")
    raise FileNotFoundError(path)


def parts(content):
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [p for p in content if isinstance(p, dict)]
    return []


def scan(path):
    """Extract thinking metrics from a single session."""
    info = {
        "id": path.stem,
        "date": "-",
        "branch": "-",
        "turns": [],  # list of (thinking_chars, text_chars, cost)
        "total_input": 0,
        "total_output": 0,
        "total_cache_create": 0,
        "total_cache_read": 0,
    }
    first_ts = None
    for lineno, raw in enumerate(path.open("r", encoding="utf-8", errors="replace"), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            warn(f"{path.name}:{lineno}: {exc}")
            continue

        ts = dt(obj.get("timestamp"))
        if ts and not first_ts:
            first_ts = ts
            info["date"] = ts.date().isoformat()

        info["branch"] = obj.get("gitBranch") or info["branch"]

        if obj.get("type") != "assistant":
            continue

        msg = obj.get("message", {})
        usage = msg.get("usage", {})
        info["total_input"] += usage.get("input_tokens", 0)
        info["total_output"] += usage.get("output_tokens", 0)
        info["total_cache_read"] += usage.get("cache_read_input_tokens", 0)
        info["total_cache_create"] += usage.get("cache_creation", {}).get(
            "ephemeral_1h_input_tokens",
            usage.get("cache_creation_input_tokens", 0),
        )

        thinking_chars = 0
        text_chars = 0
        for p in parts(msg.get("content", [])):
            ptype = p.get("type")
            if ptype == "thinking":
                thinking_chars += len(p.get("thinking", ""))
            elif ptype == "text":
                text_chars += len(p.get("text", ""))

        turn_cost = (
            usage.get("input_tokens", 0) * PRICES["input"]
            + usage.get("output_tokens", 0) * PRICES["output"]
            + usage.get("cache_read_input_tokens", 0) * PRICES["cache_read"]
            + usage.get("cache_creation", {}).get(
                "ephemeral_1h_input_tokens",
                usage.get("cache_creation_input_tokens", 0),
            )
            * PRICES["cache_create"]
        ) / 1_000_000.0

        info["turns"].append((thinking_chars, text_chars, turn_cost))

    return info


def percentile(values, pct):
    if not values:
        return 0
    values = sorted(values)
    k = (len(values) - 1) * pct / 100.0
    f = int(k)
    c = f + 1 if f + 1 < len(values) else f
    d = k - f
    return values[f] + d * (values[c] - values[f])


def main():
    ap = argparse.ArgumentParser(
        description="Thinking token analysis for Claude Code JSONL logs."
    )
    ap.add_argument("path", help="Directory or single JSONL file")
    ap.add_argument(
        "--top", type=int, default=10, help="Show top N sessions by thinking volume"
    )
    ap.add_argument(
        "--by-session",
        action="store_true",
        help="Show per-session thinking breakdown",
    )
    args = ap.parse_args()

    sessions = [scan(p) for p in jsonl_files(args.path)]

    # Global aggregates
    total_thinking_chars = 0
    total_text_chars = 0
    all_thinking_per_turn = []
    total_cost = 0.0

    per_session = []
    for s in sessions:
        s_thinking = sum(t[0] for t in s["turns"])
        s_text = sum(t[1] for t in s["turns"])
        s_cost = (
            s["total_input"] * PRICES["input"]
            + s["total_output"] * PRICES["output"]
            + s["total_cache_create"] * PRICES["cache_create"]
            + s["total_cache_read"] * PRICES["cache_read"]
        ) / 1_000_000.0
        thinking_turns = [t[0] for t in s["turns"] if t[0] > 0]

        total_thinking_chars += s_thinking
        total_text_chars += s_text
        total_cost += s_cost

        all_thinking_per_turn.extend(thinking_turns)

        ratio = s_thinking / s_text if s_text > 0 else 0.0
        per_session.append(
            {
                "id": s["id"],
                "date": s["date"],
                "branch": s["branch"],
                "thinking_chars": s_thinking,
                "text_chars": s_text,
                "ratio": ratio,
                "thinking_turns": len(thinking_turns),
                "total_turns": len(s["turns"]),
                "cost": s_cost,
            }
        )

    # Summary
    ratio = total_thinking_chars / total_text_chars if total_text_chars > 0 else 0.0
    sessions_with_thinking = sum(1 for ps in per_session if ps["thinking_chars"] > 0)

    print(f"Sessions analyzed:        {len(sessions)}")
    print(f"Sessions with thinking:   {sessions_with_thinking}")
    print(f"Total thinking chars:     {total_thinking_chars:,}")
    print(f"Total visible text chars: {total_text_chars:,}")
    print(f"Thinking/text ratio:      {ratio:.2f}x")
    print(f"Total cost:               ${total_cost:.2f}")
    print()

    # Thinking length distribution per turn
    if all_thinking_per_turn:
        print("Thinking Length per Turn (chars)")
        print("-------------------------------")
        print(f"  Count:  {len(all_thinking_per_turn)}")
        print(f"  Median: {percentile(all_thinking_per_turn, 50):,.0f}")
        print(f"  p75:    {percentile(all_thinking_per_turn, 75):,.0f}")
        print(f"  p95:    {percentile(all_thinking_per_turn, 95):,.0f}")
        print(f"  Max:    {max(all_thinking_per_turn):,}")
        print()

    # Cost correlation: high-thinking vs low-thinking sessions
    with_t = [ps for ps in per_session if ps["thinking_chars"] > 0]
    without_t = [ps for ps in per_session if ps["thinking_chars"] == 0]
    if with_t and without_t:
        avg_c_w = sum(ps["cost"] for ps in with_t) / len(with_t)
        avg_c_wo = sum(ps["cost"] for ps in without_t) / len(without_t)
        avg_t_w = sum(ps["total_turns"] for ps in with_t) / len(with_t)
        avg_t_wo = sum(ps["total_turns"] for ps in without_t) / len(without_t)
        print("Cost Correlation")
        print("----------------")
        print(f"  With thinking:    avg cost=${avg_c_w:.2f}  avg turns={avg_t_w:.1f}  (n={len(with_t)})")
        print(f"  Without thinking: avg cost=${avg_c_wo:.2f}  avg turns={avg_t_wo:.1f}  (n={len(without_t)})")
        if avg_c_wo > 0:
            print(f"  Thinking sessions cost {avg_c_w / avg_c_wo:.1f}x more on average")
        print()

    # Top N by thinking volume
    per_session.sort(key=lambda x: x["thinking_chars"], reverse=True)
    top = per_session[: args.top]
    print(f"Top {args.top} Sessions by Thinking Volume")
    print("-" * 85)
    for ps in top:
        print(
            f"  {ps['id'][:8]}  {ps['date']}  "
            f"thinking={ps['thinking_chars']:>8,}  text={ps['text_chars']:>8,}  "
            f"ratio={ps['ratio']:.2f}x  cost=${ps['cost']:.2f}  "
            f"{ps['branch'][:24]}"
        )

    # Per-session breakdown
    if args.by_session:
        print()
        print("Per-Session Thinking Breakdown")
        print("-" * 85)
        per_session.sort(key=lambda x: x["date"])
        for ps in per_session:
            if ps["thinking_chars"] == 0:
                continue
            print(
                f"  {ps['id'][:8]}  {ps['date']}  "
                f"thinking={ps['thinking_chars']:>8,}  text={ps['text_chars']:>8,}  "
                f"ratio={ps['ratio']:.2f}x  turns={ps['thinking_turns']}/{ps['total_turns']}  "
                f"cost=${ps['cost']:.2f}"
            )


if __name__ == "__main__":
    main()
