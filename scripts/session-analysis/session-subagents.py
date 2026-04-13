#!/usr/bin/env python3
"""Agent/subagent usage analysis for Claude Code JSONL logs."""
import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


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
    if isinstance(content, list):
        return [p for p in content if isinstance(p, dict)]
    return []


def scan(path):
    """Extract Agent tool usage from a single session."""
    info = {
        "id": path.stem,
        "date": "-",
        "branch": "-",
        "agents": [],  # list of dicts: {type, background, description}
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

        for p in parts(obj.get("message", {}).get("content", [])):
            if p.get("type") == "tool_use" and p.get("name") == "Agent":
                inp = p.get("input", {})
                info["agents"].append(
                    {
                        "type": inp.get("subagent_type", "unknown"),
                        "background": bool(inp.get("run_in_background")),
                        "description": (inp.get("description") or "")[:120],
                    }
                )

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
        description="Agent/subagent usage analysis for Claude Code JSONL logs."
    )
    ap.add_argument("path", help="Directory or single JSONL file")
    ap.add_argument(
        "--by-type", action="store_true", help="Show breakdown by subagent_type"
    )
    ap.add_argument(
        "--by-session",
        action="store_true",
        help="Show per-session agent counts",
    )
    args = ap.parse_args()

    sessions = [scan(p) for p in jsonl_files(args.path)]

    # Global counts
    total_agents = 0
    total_bg = 0
    type_counter = Counter()
    bg_by_type = Counter()
    per_session_counts = []

    for s in sessions:
        count = len(s["agents"])
        total_agents += count
        per_session_counts.append(count)
        for a in s["agents"]:
            type_counter[a["type"]] += 1
            if a["background"]:
                total_bg += 1
                bg_by_type[a["type"]] += 1

    sessions_with_agents = sum(1 for c in per_session_counts if c > 0)
    agent_counts_nonzero = [c for c in per_session_counts if c > 0]

    print(f"Sessions analyzed:       {len(sessions)}")
    print(f"Sessions using agents:   {sessions_with_agents}")
    print(f"Total Agent calls:       {total_agents}")
    print(f"  Foreground:            {total_agents - total_bg}")
    print(f"  Background:            {total_bg}")
    print(f"Unique agent types:      {len(type_counter)}")
    print()

    # Distribution
    if agent_counts_nonzero:
        print("Agents per Session (sessions with agents)")
        print("-" * 42)
        print(f"  Median: {percentile(agent_counts_nonzero, 50):.0f}")
        print(f"  p75:    {percentile(agent_counts_nonzero, 75):.0f}")
        print(f"  p95:    {percentile(agent_counts_nonzero, 95):.0f}")
        print(f"  Max:    {max(agent_counts_nonzero)}")
        print()

    # By type
    if args.by_type or not args.by_session:
        print("Agent Types")
        print("-" * 60)
        for atype, count in type_counter.most_common():
            bg = bg_by_type.get(atype, 0)
            bg_str = f"  (bg:{bg})" if bg else ""
            print(f"  {count:4}  {atype}{bg_str}")
        print()

    # Top sessions by agent count
    ranked = sorted(
        [(s, len(s["agents"])) for s in sessions if s["agents"]],
        key=lambda x: x[1],
        reverse=True,
    )
    print("Top 15 Sessions by Agent Usage")
    print("-" * 80)
    for s, count in ranked[:15]:
        types_in_session = Counter(a["type"] for a in s["agents"])
        top_types = ", ".join(
            f"{t}:{c}" for t, c in types_in_session.most_common(4)
        )
        print(
            f"  {s['id'][:8]}  {s['date']}  agents={count:3}  "
            f"{s['branch'][:24]:24}  {top_types}"
        )

    # Per-session breakdown
    if args.by_session:
        print()
        print("Per-Session Agent Breakdown")
        print("-" * 80)
        for s in sorted(sessions, key=lambda x: x["date"]):
            if not s["agents"]:
                continue
            types_in_session = Counter(a["type"] for a in s["agents"])
            bg_in_session = sum(1 for a in s["agents"] if a["background"])
            top_types = ", ".join(
                f"{t}:{c}" for t, c in types_in_session.most_common(5)
            )
            print(
                f"  {s['id'][:8]}  {s['date']}  total={len(s['agents']):3}  "
                f"bg={bg_in_session}  {s['branch'][:20]:20}  {top_types}"
            )


if __name__ == "__main__":
    main()
