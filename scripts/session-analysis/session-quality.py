#!/usr/bin/env python3
"""Session quality scoring — success/failure heuristics for Claude Code JSONL logs."""
import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ERROR_PATTERNS = re.compile(r"\b(error|Error|ERROR|FAIL|denied|permission|Exit code [1-9])\b")


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
    """Analyze a single session file and return quality metrics."""
    info = {
        "id": path.stem,
        "tool_uses": 0,
        "tool_results": 0,
        "tool_errors": 0,
        "hook_errors": 0,
        "system_api_errors": 0,
        "stop_reasons": Counter(),
        "has_last_prompt": False,
        "last_event_type": None,
        "error_messages": [],
        "date": "-",
        "branch": "-",
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

        etype = obj.get("type")
        info["last_event_type"] = etype

        ts = dt(obj.get("timestamp"))
        if ts and not first_ts:
            first_ts = ts
            info["date"] = ts.date().isoformat()

        info["branch"] = obj.get("gitBranch") or info["branch"]

        if etype == "assistant":
            msg = obj.get("message", {})
            sr = msg.get("stop_reason")
            if sr:
                info["stop_reasons"][sr] += 1
            for p in parts(msg.get("content", [])):
                if p.get("type") == "tool_use":
                    info["tool_uses"] += 1

        elif etype == "user":
            for p in parts(obj.get("message", {}).get("content", [])):
                if p.get("type") == "tool_result":
                    info["tool_results"] += 1
                    is_error = p.get("is_error", False)
                    content_str = str(p.get("content", ""))
                    if is_error:
                        info["tool_errors"] += 1
                        info["error_messages"].append(content_str[:200])
                    elif ERROR_PATTERNS.search(content_str[:500]):
                        # Soft error: not flagged is_error but content has error text
                        info["tool_errors"] += 1
                        info["error_messages"].append(content_str[:200])

        elif etype == "system":
            hook_errors = obj.get("hookErrors", [])
            if hook_errors:
                info["hook_errors"] += len(hook_errors)
                for he in hook_errors:
                    info["error_messages"].append(str(he)[:200])
            if obj.get("subtype") == "api_error":
                info["system_api_errors"] += 1
                status = obj.get("error", {}).get("status", "?")
                info["error_messages"].append(f"API error HTTP {status}")

        elif etype == "last-prompt":
            info["has_last_prompt"] = True

    return info


def score(info):
    """Compute a 0-100 quality score from session metrics."""
    s = 100.0

    # Tool success rate (up to -30 points)
    if info["tool_results"] > 0:
        error_rate = info["tool_errors"] / info["tool_results"]
        s -= min(30, error_rate * 60)

    # Hook errors (-10 per hook error, max -20)
    s -= min(20, info["hook_errors"] * 10)

    # API errors (-8 per error, max -24)
    s -= min(24, info["system_api_errors"] * 8)

    # max_tokens stop reasons indicate truncation (-5 each, max -15)
    max_tokens_count = info["stop_reasons"].get("max_tokens", 0)
    s -= min(15, max_tokens_count * 5)

    # Abrupt ending: no last-prompt event (-5)
    if not info["has_last_prompt"]:
        s -= 5

    # Last event is a system error (-5)
    if info["last_event_type"] == "system":
        s -= 5

    # Empty session (no tool use at all) — cap at 50
    if info["tool_uses"] == 0 and info["tool_results"] == 0:
        s = min(s, 50)

    return max(0, min(100, round(s)))


def main():
    ap = argparse.ArgumentParser(
        description="Session quality scoring for Claude Code JSONL logs."
    )
    ap.add_argument("path", help="Directory or single JSONL file")
    ap.add_argument(
        "--failures-only",
        action="store_true",
        help="Only show sessions scoring below 70",
    )
    ap.add_argument(
        "--verbose", action="store_true", help="Show specific error messages"
    )
    args = ap.parse_args()

    sessions = []
    for p in jsonl_files(args.path):
        info = scan(p)
        info["score"] = score(info)
        sessions.append(info)

    sessions.sort(key=lambda x: x["score"])

    if args.failures_only:
        sessions = [s for s in sessions if s["score"] < 70]

    # Summary
    scores = [s["score"] for s in sessions]
    if not scores:
        print("No sessions to analyze.")
        return

    avg = sum(scores) / len(scores)
    print(f"Sessions analyzed: {len(scores)}")
    print(f"Average quality:   {avg:.1f}/100")
    print(
        f"Distribution:      "
        f"excellent(90+)={sum(1 for s in scores if s >= 90)} "
        f"good(70-89)={sum(1 for s in scores if 70 <= s < 90)} "
        f"poor(<70)={sum(1 for s in scores if s < 70)}"
    )

    # Stop reason summary
    all_sr = Counter()
    for s in sessions:
        all_sr.update(s["stop_reasons"])
    print(f"Stop reasons:      {dict(all_sr)}")

    # Failure patterns
    all_errors = Counter()
    for s in sessions:
        for msg in s["error_messages"]:
            # Normalize to pattern
            key = msg[:80].strip()
            all_errors[key] += 1
    if all_errors:
        print()
        print("Most Common Failure Patterns")
        print("----------------------------")
        for pattern, count in all_errors.most_common(10):
            print(f"  {count:4}x  {pattern}")

    # Per-session table
    print()
    if args.failures_only:
        print(f"Sessions Below 70 ({len(sessions)})")
    else:
        print("Worst 20 Sessions" if len(sessions) > 20 else "All Sessions")
    print("-" * 90)
    shown = sessions[:20] if not args.failures_only else sessions
    for s in shown:
        tool_ok = s["tool_results"] - s["tool_errors"]
        tool_total = s["tool_results"]
        tool_pct = f"{tool_ok}/{tool_total}" if tool_total else "-/-"
        flags = []
        if s["hook_errors"]:
            flags.append(f"hooks:{s['hook_errors']}")
        if s["system_api_errors"]:
            flags.append(f"api_err:{s['system_api_errors']}")
        if not s["has_last_prompt"]:
            flags.append("no_last_prompt")
        if s["stop_reasons"].get("max_tokens", 0):
            flags.append(f"max_tokens:{s['stop_reasons']['max_tokens']}")
        flag_str = " ".join(flags) if flags else "ok"
        print(
            f"  {s['id'][:8]}  score={s['score']:3}  "
            f"tools={tool_pct:>8}  "
            f"{s['date']}  {s['branch'][:28]:28}  {flag_str}"
        )
        if args.verbose and s["error_messages"]:
            for msg in s["error_messages"][:3]:
                print(f"           -> {msg[:100]}")


if __name__ == "__main__":
    main()
