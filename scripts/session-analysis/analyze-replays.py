#!/usr/bin/env python3
"""Analyze autopilot intervention logs to compute acceptance rates and suggest policy tweaks."""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from _common import warn, dt


# Maps intervention type -> state field(s) that indicate acceptance.
# Each entry is (field, check_fn) where check_fn(before, after) -> bool.
ACCEPTANCE_SIGNALS = {
    "plan_missing": [("plan_exists", lambda b, a: not b and a)],
    "delegate_suggest": [("delegations", lambda b, a: a > b)],
    "skill_suggest": [("skills_used", lambda b, a: len(a) > len(b) if isinstance(a, list) and isinstance(b, list) else False)],
    "verify_remind": [("verification_done", lambda b, a: not b and a)],
}


def find_session_dirs(base_dir):
    """Find all directories under base_dir that contain an interventions.log."""
    base = Path(base_dir)
    if not base.is_dir():
        warn(f"directory not found: {base_dir}")
        return []
    return sorted(
        d for d in base.iterdir()
        if d.is_dir() and (d / "interventions.log").exists()
    )


def parse_interventions(log_path):
    """Parse a JSONL intervention log into a list of dicts."""
    entries = []
    for lineno, raw in enumerate(log_path.open("r", encoding="utf-8", errors="replace"), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            warn(f"{log_path}:{lineno}: {exc}")
            continue
        entries.append(obj)
    return entries


def load_state(session_dir):
    """Load state.json from a session directory. Returns None on failure."""
    state_path = session_dir / "state.json"
    if not state_path.exists():
        return None
    try:
        with state_path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        warn(f"cannot read {state_path}: {exc}")
        return None


def group_by_session(entries):
    """Group intervention entries into sessions by detecting turn resets.

    The autopilot appends all interventions for all sessions to a single file.
    A new session starts when the turn number drops below the previous entry's turn.
    """
    sessions = []
    current = []
    prev_turn = -1
    for entry in entries:
        turn = entry.get("turn", 0)
        if turn < prev_turn and current:
            sessions.append(current)
            current = []
        current.append(entry)
        prev_turn = turn
    if current:
        sessions.append(current)
    return sessions


def check_acceptance(intervention, state):
    """Check if an intervention was accepted based on final state.

    Since we only have the final state snapshot (not per-turn snapshots), we use
    a heuristic: if the state field the intervention targets is now in the
    "accepted" state, and the intervention fired, we count it as accepted.

    For more accurate tracking, per-turn state snapshots would be needed.
    Returns: True (accepted), False (rejected), None (unknown)
    """
    if state is None:
        return None
    itype = intervention.get("type", "")
    signals = ACCEPTANCE_SIGNALS.get(itype)
    if not signals:
        return None
    for field, check_fn in signals:
        # Build a "before" value from what we know the state was when the
        # intervention fired. For boolean fields the intervention only fires
        # when the field is False/empty, so we can reconstruct "before".
        current = state.get(field)
        if current is None:
            continue
        if isinstance(current, bool):
            before = False
        elif isinstance(current, (int, float)):
            before = 0
        elif isinstance(current, list):
            before = []
        else:
            continue
        if check_fn(before, current):
            return True
    return False


def analyze_session_dir(session_dir):
    """Analyze a single session directory.

    Returns a dict with per-type stats for this session.
    """
    log_path = session_dir / "interventions.log"
    entries = parse_interventions(log_path)
    if not entries:
        return None

    state = load_state(session_dir)

    # Group entries into logical sessions (turn resets = new session)
    sessions = group_by_session(entries)

    results = []
    for session_entries in sessions:
        type_stats = defaultdict(lambda: {
            "fires": 0,
            "accepted": 0,
            "unknown": 0,
            "levels": [],
            "suppressed": 0,
            "timestamps": [],
        })

        # Track consecutive fires of the same type to detect suppression
        consecutive = defaultdict(int)

        for entry in session_entries:
            itype = entry.get("type", "unknown")
            level = entry.get("level")
            ts = entry.get("timestamp")

            stats = type_stats[itype]
            stats["fires"] += 1
            if ts:
                stats["timestamps"].append(ts)
            if level is not None:
                stats["levels"].append(level)

            # Count consecutive fires (same type without acceptance between)
            consecutive[itype] += 1

            # Level 3 = max escalation = suppression
            if level is not None and level >= 3:
                stats["suppressed"] += 1

        # Check acceptance against final state (heuristic)
        for itype, stats in type_stats.items():
            result = check_acceptance({"type": itype}, state)
            if result is True:
                stats["accepted"] = 1
            elif result is None:
                stats["unknown"] = stats["fires"]

            # If no level data (Phase 1 logs), estimate suppression from
            # consecutive fire count. 3+ fires of same type without the
            # state changing = likely suppressed.
            if not stats["levels"] and consecutive.get(itype, 0) >= 3:
                stats["suppressed"] = 1

        results.append(dict(type_stats))

    return {
        "dir": str(session_dir),
        "session_count": len(sessions),
        "per_session": results,
        "timestamps": [e.get("timestamp") for e in entries if e.get("timestamp")],
    }


def aggregate(all_results):
    """Aggregate per-session stats into global stats."""
    totals = defaultdict(lambda: {
        "fires": 0,
        "accepted": 0,
        "unknown": 0,
        "levels": [],
        "suppressed": 0,
    })

    for result in all_results:
        for session_stats in result["per_session"]:
            for itype, stats in session_stats.items():
                t = totals[itype]
                t["fires"] += stats["fires"]
                t["accepted"] += stats["accepted"]
                t["unknown"] += stats["unknown"]
                t["levels"].extend(stats["levels"])
                t["suppressed"] += stats["suppressed"]

    return dict(totals)


def compute_date_range(all_results):
    """Compute the earliest and latest timestamps across all results."""
    all_ts = []
    for result in all_results:
        for ts_str in result.get("timestamps", []):
            parsed = dt(ts_str)
            if parsed:
                all_ts.append(parsed)
    if not all_ts:
        return None, None
    return min(all_ts), max(all_ts)


def format_table(totals):
    """Format totals as an ASCII table."""
    if not totals:
        return "No interventions found.\n"

    # Sort by fires descending
    rows = sorted(totals.items(), key=lambda x: x[1]["fires"], reverse=True)

    # Column headers and widths
    headers = ["Type", "Fires", "Accepted", "Rate", "Avg Level", "Suppressed"]
    data = []
    for itype, stats in rows:
        fires = stats["fires"]
        accepted = stats["accepted"]
        rate = (accepted / fires * 100) if fires > 0 else 0.0
        levels = stats["levels"]
        avg_level = sum(levels) / len(levels) if levels else 0.0
        suppressed = stats["suppressed"]

        rate_str = f"{rate:.1f}%" if stats["unknown"] < fires else "unknown"
        level_str = f"{avg_level:.1f}" if levels else "n/a"

        data.append([itype, str(fires), str(accepted), rate_str, level_str, str(suppressed)])

    # Compute column widths
    widths = [max(len(h), max((len(r[i]) for r in data), default=0)) for i, h in enumerate(headers)]

    # Build box-drawing table
    def sep(left, mid, right, fill):
        return left + mid.join(fill * (w + 2) for w in widths) + right

    def row_str(cells):
        return "|" + "|".join(f" {c.ljust(w)} " if i == 0 else f" {c.rjust(w)} " for i, (c, w) in enumerate(zip(cells, widths))) + "|"

    lines = [
        sep("+", "+", "+", "-"),
        row_str(headers),
        sep("+", "+", "+", "-"),
    ]
    for r in data:
        lines.append(row_str(r))
    lines.append(sep("+", "+", "+", "-"))

    return "\n".join(lines) + "\n"


def suggest_tweaks(totals):
    """Generate policy tweak suggestions based on the data."""
    suggestions = []
    for itype, stats in sorted(totals.items()):
        fires = stats["fires"]
        accepted = stats["accepted"]
        suppressed = stats["suppressed"]
        unknown = stats["unknown"]

        if fires == 0:
            continue

        # Skip unknowns for rate-based suggestions
        if unknown >= fires:
            suggestions.append(
                f"  ? {itype}: {fires} fires but acceptance unknown (no readable state.json)"
            )
            continue

        rate = accepted / fires * 100 if fires > 0 else 0.0

        if rate > 80:
            suggestions.append(
                f"  OK {itype}: {rate:.0f}% acceptance -- hint level sufficient, no escalation needed"
            )
        elif rate < 30:
            detail = f"{rate:.0f}% acceptance"
            if suppressed > 0:
                detail += f", {suppressed} suppression(s)"
            suggestions.append(
                f"  !! {itype}: {detail} -- consider relaxing this rule or switching to a softer nudge"
            )
        else:
            suggestions.append(
                f"  OK {itype}: working well at {rate:.0f}%"
            )

        if suppressed > 0 and rate >= 30:
            suggestions.append(
                f"     ^ {itype}: {suppressed} suppression(s) -- agent repeatedly ignored this type"
            )

    # Check for types that are defined but never fired
    known_types = set(ACCEPTANCE_SIGNALS.keys())
    fired_types = set(totals.keys())
    never_fired = known_types - fired_types
    for itype in sorted(never_fired):
        suggestions.append(
            f"  -- {itype}: never fired -- threshold may be too high or policy not enabled"
        )

    return suggestions


def split_by_timestamp(all_results, cutoff_dt):
    """Split session results into before/after groups based on cutoff timestamp.

    Each result's group is determined by its earliest timestamp.
    """
    before, after = [], []
    for result in all_results:
        timestamps = [dt(ts) for ts in result.get("timestamps", [])]
        timestamps = [t for t in timestamps if t is not None]
        if not timestamps:
            before.append(result)
            continue
        earliest = min(timestamps)
        if earliest < cutoff_dt:
            before.append(result)
        else:
            after.append(result)
    return before, after


def format_comparison(before_totals, after_totals, cutoff_str):
    """Render a side-by-side before/after comparison table."""
    all_types = sorted(set(list(before_totals.keys()) + list(after_totals.keys())))

    if not all_types:
        return "No intervention data to compare.\n"

    # Column widths
    label_w = 21
    col_w = 10
    delta_w = 8

    def hline():
        return "+" + "-" * label_w + "+" + "-" * col_w + "+" + "-" * col_w + "+" + "-" * delta_w + "+"

    def header():
        lbl = "".ljust(label_w)
        bef = "Before".center(col_w)
        aft = "After".center(col_w)
        dlt = "Delta".center(delta_w)
        return "|" + lbl + "|" + bef + "|" + aft + "|" + dlt + "|"

    def data_row(label, bval, aval, delta_str):
        lbl = ("  " + label).ljust(label_w)
        b = bval.rjust(col_w - 2) + "  "
        a = aval.rjust(col_w - 2) + "  "
        d = delta_str.rjust(delta_w - 2) + "  "
        return "|" + lbl + "|" + b + "|" + a + "|" + d + "|"

    def type_row(itype):
        lbl = itype.ljust(label_w)
        return "|" + lbl + "|" + " " * col_w + "|" + " " * col_w + "|" + " " * delta_w + "|"

    def delta_int(b, a):
        diff = a - b
        if diff == 0:
            return "0"
        return f"{diff:+d}"

    def delta_float(b, a):
        diff = a - b
        if diff == 0.0:
            return "0.0"
        return f"{diff:+.1f}"

    lines = [
        f"Phase Comparison (cutoff: {cutoff_str})",
        "=" * (label_w + col_w + col_w + delta_w + 5),
        hline(),
        header(),
        hline(),
    ]

    for itype in all_types:
        b = before_totals.get(itype, {"fires": 0, "accepted": 0, "levels": [], "suppressed": 0, "unknown": 0})
        a = after_totals.get(itype, {"fires": 0, "accepted": 0, "levels": [], "suppressed": 0, "unknown": 0})

        b_fires = b["fires"]
        a_fires = a["fires"]
        b_rate = (b["accepted"] / b_fires * 100) if b_fires > 0 else 0.0
        a_rate = (a["accepted"] / a_fires * 100) if a_fires > 0 else 0.0
        b_rate_str = f"{b_rate:.1f}%" if b["unknown"] < b_fires and b_fires > 0 else "unknown" if b_fires > 0 else ""
        a_rate_str = f"{a_rate:.1f}%" if a["unknown"] < a_fires and a_fires > 0 else "unknown" if a_fires > 0 else ""
        b_levels = b["levels"]
        a_levels = a["levels"]
        b_avg = sum(b_levels) / len(b_levels) if b_levels else None
        a_avg = sum(a_levels) / len(a_levels) if a_levels else None
        b_avg_str = f"{b_avg:.1f}" if b_avg is not None else "n/a"
        a_avg_str = f"{a_avg:.1f}" if a_avg is not None else "n/a"
        avg_delta = ""
        if b_avg is not None and a_avg is not None:
            avg_delta = delta_float(b_avg, a_avg)

        rate_delta = ""
        if b_fires > 0 and a_fires > 0 and b["unknown"] < b_fires and a["unknown"] < a_fires:
            rate_delta = delta_float(b_rate, a_rate)

        lines.append(type_row(itype))
        lines.append(data_row("Fires", str(b_fires), str(a_fires), delta_int(b_fires, a_fires)))
        lines.append(data_row("Acceptance", b_rate_str, a_rate_str, rate_delta))
        lines.append(data_row("Avg Level", b_avg_str, a_avg_str, avg_delta))
        lines.append(data_row("Suppressed", str(b["suppressed"]), str(a["suppressed"]), delta_int(b["suppressed"], a["suppressed"])))
        lines.append(hline())

    return "\n".join(lines) + "\n"


def format_output(all_results, totals, verbose=False):
    """Format the full text report."""
    total_sessions = sum(r["session_count"] for r in all_results)
    start_dt, end_dt = compute_date_range(all_results)

    lines = [
        "Autopilot Replay Analysis",
        "=" * 25,
        f"Sessions analyzed: {total_sessions}",
    ]
    if start_dt and end_dt:
        lines.append(f"Date range: {start_dt.strftime('%Y-%m-%d')} -- {end_dt.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("Intervention Statistics:")
    lines.append(format_table(totals))

    suggestions = suggest_tweaks(totals)
    if suggestions:
        lines.append("Suggested Policy Tweaks:")
        lines.extend(suggestions)
        lines.append("")

    if verbose:
        lines.append("Per-Session Breakdown:")
        lines.append("-" * 40)
        for result in all_results:
            lines.append(f"  Dir: {result['dir']}")
            for i, session_stats in enumerate(result["per_session"]):
                lines.append(f"    Session {i + 1}:")
                for itype, stats in sorted(session_stats.items()):
                    rate = (stats["accepted"] / stats["fires"] * 100) if stats["fires"] > 0 else 0
                    status = "unknown" if stats["unknown"] >= stats["fires"] else f"{rate:.0f}%"
                    lines.append(f"      {itype}: {stats['fires']} fires, {status} accepted")
            lines.append("")

    return "\n".join(lines)


def to_json(all_results, totals):
    """Format output as JSON."""
    total_sessions = sum(r["session_count"] for r in all_results)
    start_dt, end_dt = compute_date_range(all_results)

    output = {
        "sessions_analyzed": total_sessions,
        "date_range": {
            "start": start_dt.isoformat() if start_dt else None,
            "end": end_dt.isoformat() if end_dt else None,
        },
        "intervention_stats": {},
        "suggested_tweaks": [],
    }

    for itype, stats in totals.items():
        fires = stats["fires"]
        accepted = stats["accepted"]
        levels = stats["levels"]
        output["intervention_stats"][itype] = {
            "fires": fires,
            "accepted": accepted,
            "acceptance_rate": round(accepted / fires * 100, 1) if fires > 0 else 0.0,
            "avg_level": round(sum(levels) / len(levels), 2) if levels else None,
            "suppressed": stats["suppressed"],
            "unknown": stats["unknown"],
        }

    output["suggested_tweaks"] = suggest_tweaks(totals)

    return json.dumps(output, indent=2)


def main():
    ap = argparse.ArgumentParser(
        description="Analyze autopilot intervention logs: acceptance rates, suppression, and policy suggestions."
    )
    ap.add_argument(
        "--dir",
        default="/tmp/drupal-workflow-states/",
        help="State directory to scan (default: /tmp/drupal-workflow-states/)",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON instead of table",
    )
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="Show per-session breakdown",
    )
    ap.add_argument(
        "--compare",
        nargs="?",
        const="2026-04-14T06:42:00+00:00",
        default=None,
        metavar="TIMESTAMP",
        help="Compare before/after a timestamp (default: Phase 2 deployment date)",
    )
    args = ap.parse_args()

    session_dirs = find_session_dirs(args.dir)
    if not session_dirs:
        print(f"No intervention logs found in {args.dir}", file=sys.stderr)
        sys.exit(1)

    all_results = []
    for d in session_dirs:
        result = analyze_session_dir(d)
        if result:
            all_results.append(result)

    if not all_results:
        print("No intervention data found.", file=sys.stderr)
        sys.exit(1)

    if args.compare:
        cutoff = dt(args.compare)
        if cutoff is None:
            print(f"Invalid timestamp: {args.compare}", file=sys.stderr)
            sys.exit(1)
        before, after = split_by_timestamp(all_results, cutoff)
        before_totals = aggregate(before)
        after_totals = aggregate(after)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        if args.json_output:
            output = {
                "comparison": {
                    "cutoff": args.compare,
                    "before": {
                        "sessions": sum(r["session_count"] for r in before),
                        "stats": {},
                    },
                    "after": {
                        "sessions": sum(r["session_count"] for r in after),
                        "stats": {},
                    },
                },
            }
            for label, totals in [("before", before_totals), ("after", after_totals)]:
                for itype, stats in totals.items():
                    fires = stats["fires"]
                    levels = stats["levels"]
                    output["comparison"][label]["stats"][itype] = {
                        "fires": fires,
                        "accepted": stats["accepted"],
                        "acceptance_rate": round(stats["accepted"] / fires * 100, 1) if fires > 0 else 0.0,
                        "avg_level": round(sum(levels) / len(levels), 2) if levels else None,
                        "suppressed": stats["suppressed"],
                        "unknown": stats["unknown"],
                    }
            print(json.dumps(output, indent=2))
        else:
            print(format_comparison(before_totals, after_totals, cutoff_str))
        return

    totals = aggregate(all_results)

    if args.json_output:
        print(to_json(all_results, totals))
    else:
        print(format_output(all_results, totals, verbose=args.verbose))


if __name__ == "__main__":
    main()
