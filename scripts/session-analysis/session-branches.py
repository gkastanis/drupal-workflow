#!/usr/bin/env python3
"""Git branch lifecycle analysis for Claude Code JSONL logs."""
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


def scan(path):
    """Extract branch, timing, and cost info from a single session."""
    info = {
        "id": path.stem,
        "branch": None,
        "first_ts": None,
        "last_ts": None,
        "dates": set(),
        "input": 0,
        "output": 0,
        "cache_create": 0,
        "cache_read": 0,
    }
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
        if ts:
            if info["first_ts"] is None or ts < info["first_ts"]:
                info["first_ts"] = ts
            if info["last_ts"] is None or ts > info["last_ts"]:
                info["last_ts"] = ts
            info["dates"].add(ts.date().isoformat())

        branch = obj.get("gitBranch")
        if branch:
            info["branch"] = branch

        if obj.get("type") == "assistant":
            usage = obj.get("message", {}).get("usage", {})
            info["input"] += usage.get("input_tokens", 0)
            info["output"] += usage.get("output_tokens", 0)
            info["cache_read"] += usage.get("cache_read_input_tokens", 0)
            info["cache_create"] += usage.get("cache_creation", {}).get(
                "ephemeral_1h_input_tokens",
                usage.get("cache_creation_input_tokens", 0),
            )

    return info


def cost(s):
    return (
        s["input"] * PRICES["input"]
        + s["output"] * PRICES["output"]
        + s["cache_create"] * PRICES["cache_create"]
        + s["cache_read"] * PRICES["cache_read"]
    ) / 1_000_000.0


def duration_minutes(s):
    if s["first_ts"] and s["last_ts"]:
        return (s["last_ts"] - s["first_ts"]).total_seconds() / 60.0
    return 0.0


def main():
    ap = argparse.ArgumentParser(
        description="Git branch lifecycle analysis for Claude Code JSONL logs."
    )
    ap.add_argument("path", help="Directory or single JSONL file")
    ap.add_argument(
        "--cost", action="store_true", help="Include cost breakdown per branch"
    )
    ap.add_argument(
        "--timeline",
        action="store_true",
        help="Show branch activity over time (one line per day)",
    )
    args = ap.parse_args()

    sessions = [scan(p) for p in jsonl_files(args.path)]

    # Group by branch
    branches = defaultdict(
        lambda: {
            "sessions": [],
            "first_ts": None,
            "last_ts": None,
            "dates": set(),
            "input": 0,
            "output": 0,
            "cache_create": 0,
            "cache_read": 0,
        }
    )

    for s in sessions:
        bname = s["branch"] or "(unknown)"
        b = branches[bname]
        b["sessions"].append(s)
        if s["first_ts"]:
            if b["first_ts"] is None or s["first_ts"] < b["first_ts"]:
                b["first_ts"] = s["first_ts"]
        if s["last_ts"]:
            if b["last_ts"] is None or s["last_ts"] > b["last_ts"]:
                b["last_ts"] = s["last_ts"]
        b["dates"].update(s["dates"])
        b["input"] += s["input"]
        b["output"] += s["output"]
        b["cache_create"] += s["cache_create"]
        b["cache_read"] += s["cache_read"]

    # Sort branches by session count descending
    ranked = sorted(branches.items(), key=lambda kv: len(kv[1]["sessions"]), reverse=True)

    print(f"Branches: {len(ranked)}")
    print(f"Sessions: {len(sessions)}")
    print()

    # Main table
    print("Branch Activity")
    print("-" * 95)
    header = (
        f"  {'Branch':<36} {'Sessions':>8} {'Days':>5} "
        f"{'First':>10} {'Last':>10} {'Avg min':>8}"
    )
    if args.cost:
        header += f" {'Cost':>9}"
    print(header)
    print("-" * 95)

    for bname, b in ranked:
        nsess = len(b["sessions"])
        ndays = len(b["dates"])
        first = b["first_ts"].date().isoformat() if b["first_ts"] else "-"
        last = b["last_ts"].date().isoformat() if b["last_ts"] else "-"
        durations = [duration_minutes(s) for s in b["sessions"]]
        avg_dur = sum(durations) / len(durations) if durations else 0.0
        line = (
            f"  {bname:<36} {nsess:>8} {ndays:>5} "
            f"{first:>10} {last:>10} {avg_dur:>7.1f}"
        )
        if args.cost:
            bcost = cost(b)
            line += f" ${bcost:>8.2f}"
        print(line)

    # Cost breakdown
    if args.cost:
        print()
        total = sum(cost(b) for _, b in ranked)
        print(f"Total cost across all branches: ${total:.2f}")
        print()
        print("Top 10 Most Expensive Branches")
        print("-" * 70)
        cost_ranked = sorted(ranked, key=lambda kv: cost(kv[1]), reverse=True)
        for bname, b in cost_ranked[:10]:
            bcost = cost(b)
            pct = bcost / total * 100 if total > 0 else 0
            in_tok = b["input"]
            out_tok = b["output"]
            print(
                f"  {bname:<36} ${bcost:>8.2f}  ({pct:>5.1f}%)  "
                f"in={in_tok:>10,}  out={out_tok:>10,}"
            )

    # Timeline
    if args.timeline:
        # Collect all dates across all branches
        all_dates = set()
        for _, b in ranked:
            all_dates.update(b["dates"])
        if not all_dates:
            return
        all_dates = sorted(all_dates)

        # Only show branches active on 2+ days for readability
        active_branches = [
            (bname, b) for bname, b in ranked if len(b["dates"]) >= 2
        ]
        if not active_branches:
            active_branches = ranked[:10]

        print()
        print("Branch Timeline (sessions per day)")
        print("-" * 80)

        # Build per-branch-per-day counts
        day_counts = {}
        for bname, b in active_branches:
            day_counts[bname] = defaultdict(int)
            for s in b["sessions"]:
                for d in s["dates"]:
                    day_counts[bname][d] += 1

        # Print header with branch names
        name_width = 28
        for bname, _ in active_branches:
            short = bname[:name_width]
            print(f"  {short}")

        print()
        for date in all_dates:
            row = f"  {date} "
            for bname, _ in active_branches:
                count = day_counts[bname].get(date, 0)
                if count == 0:
                    row += " . "
                else:
                    row += f" {count} "
            print(row)


if __name__ == "__main__":
    main()
