#!/usr/bin/env python3
"""Autopilot diagnostic script — analyzes session data and generates tuning proposals.

Reads intervention logs, outcome archives, and current policies to produce
a structured report with specific, data-backed improvement proposals.

Usage:
    python3 diagnose.py              # human-readable report
    python3 diagnose.py --json       # machine-readable JSON
    python3 diagnose.py --dir PATH   # override state directory
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def dt(s):
    """Parse ISO timestamp string to datetime."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def find_state_dirs(base):
    """Find all active-* dirs under the state base directory."""
    base = Path(base)
    if not base.is_dir():
        return []
    return sorted(d for d in base.iterdir() if d.is_dir() and d.name.startswith("active-"))


def parse_jsonl(path):
    """Parse a JSONL file, skipping bad lines."""
    entries = []
    if not path.exists():
        return entries
    for line in path.open("r", encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def load_json(path):
    """Load a JSON file, return None on failure."""
    try:
        with path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return None


# ─── Acceptance Analysis ───────────────────────────────────────────

ACCEPTANCE_FIELDS = {
    "plan_missing": "plan_exists",
    "delegate_suggest": "delegations",
    "skill_suggest": "skills_used",
    "verify_remind": "verification_done",
}


def analyze_acceptance(interventions, state):
    """Compute per-type acceptance rates from intervention log + final state."""
    by_type = defaultdict(lambda: {"fires": 0, "levels": [], "timestamps": []})

    for entry in interventions:
        itype = entry.get("type", "")
        stats = by_type[itype]
        stats["fires"] += 1
        if entry.get("level"):
            stats["levels"].append(entry["level"])
        if entry.get("timestamp"):
            stats["timestamps"].append(entry["timestamp"])

    results = {}
    for itype, stats in by_type.items():
        accepted = False
        if state:
            field = ACCEPTANCE_FIELDS.get(itype)
            if field:
                val = state.get(field)
                if isinstance(val, bool):
                    accepted = val
                elif isinstance(val, (int, float)):
                    accepted = val > 0
                elif isinstance(val, list):
                    accepted = len(val) > 0

        levels = stats["levels"]
        results[itype] = {
            "fires": stats["fires"],
            "accepted": 1 if accepted else 0,
            "rate": (1.0 / stats["fires"]) if accepted and stats["fires"] > 0 else 0.0,
            "avg_level": round(sum(levels) / len(levels), 2) if levels else None,
            "suppressed": sum(1 for l in levels if l >= 3),
        }

    return results


# ─── Outcome Analysis ──────────────────────────────────────────────

def analyze_outcomes(outcomes):
    """Summarize session outcomes from the archived outcomes.jsonl."""
    if not outcomes:
        return {"count": 0}

    drifts = [o.get("drift_score", 0) for o in outcomes]
    verified = sum(1 for o in outcomes if o.get("verification_done"))
    planned = sum(1 for o in outcomes if o.get("plan_exists"))
    edits = [o.get("edits", 0) for o in outcomes]
    interventions = [o.get("intervention_count", 0) for o in outcomes]

    by_type = defaultdict(list)
    for o in outcomes:
        by_type[o.get("policy_task_type", "unknown")].append(o)

    type_summary = {}
    for task_type, group in by_type.items():
        type_summary[task_type] = {
            "count": len(group),
            "avg_edits": round(sum(o.get("edits", 0) for o in group) / len(group), 1),
            "avg_drift": round(sum(o.get("drift_score", 0) for o in group) / len(group), 2),
            "pct_verified": round(sum(1 for o in group if o.get("verification_done")) / len(group), 2),
            "pct_planned": round(sum(1 for o in group if o.get("plan_exists")) / len(group), 2),
            "avg_skills": round(sum(len(o.get("skills_used", [])) for o in group) / len(group), 1),
        }

    n = len(outcomes)
    return {
        "count": n,
        "avg_drift": round(sum(drifts) / n, 3),
        "pct_verified": round(verified / n, 2),
        "pct_planned": round(planned / n, 2),
        "avg_edits": round(sum(edits) / n, 1),
        "avg_interventions": round(sum(interventions) / n, 1),
        "by_task_type": type_summary,
    }


# ─── Classification Analysis ──────────────────────────────────────

def analyze_classification(outcomes):
    """Detect possible misclassifications based on session behavior vs task type."""
    issues = []
    for o in outcomes:
        task_type = o.get("policy_task_type", "")
        edits = o.get("edits", 0)
        delegations = o.get("delegations", 0)

        # Maintenance sessions that look like implementation
        if task_type == "maintenance" and (edits > 10 or delegations > 1):
            issues.append({
                "type": "possible_misclass",
                "classified_as": "maintenance",
                "likely_was": "implementation",
                "evidence": f"{edits} edits, {delegations} delegations",
                "archived_at": o.get("archived_at", ""),
            })

        # Implementation sessions that were trivial
        if task_type == "implementation" and edits <= 3 and delegations == 0:
            issues.append({
                "type": "possible_misclass",
                "classified_as": "implementation",
                "likely_was": "maintenance",
                "evidence": f"only {edits} edits, 0 delegations",
                "archived_at": o.get("archived_at", ""),
            })

    return issues


# ─── Threshold Sensitivity ────────────────────────────────────────

def analyze_thresholds(interventions):
    """Check at what edit count interventions fire vs when agents comply."""
    by_type = defaultdict(list)
    for entry in interventions:
        itype = entry.get("type", "")
        by_type[itype].append(entry)

    results = {}
    for itype, entries in by_type.items():
        # Drift components tell us the state at each fire
        fire_edits = []
        for e in entries:
            dc = e.get("drift_components", {})
            # The turn number is a proxy for activity level
            fire_edits.append(e.get("turn", 0))

        results[itype] = {
            "fire_count": len(entries),
            "first_fire_turn": min(fire_edits) if fire_edits else None,
            "avg_fire_turn": round(sum(fire_edits) / len(fire_edits), 1) if fire_edits else None,
        }

    return results


# ─── Proposal Generation ──────────────────────────────────────────

def generate_proposals(acceptance, outcomes_summary, classification_issues, thresholds, policies):
    """Generate specific, data-backed tuning proposals."""
    proposals = []
    pid = 0

    # P1: Skill suggestion has very low acceptance
    skill_stats = acceptance.get("skill_suggest", {})
    if skill_stats.get("fires", 0) >= 3 and skill_stats.get("rate", 0) < 0.15:
        pid += 1
        impl_policy = policies.get("implementation", {})
        current_min = impl_policy.get("min_skills", 2)
        proposals.append({
            "id": f"P{pid}",
            "category": "threshold",
            "target": "scripts/policies/implementation.json",
            "field": "min_skills",
            "old_value": current_min,
            "new_value": max(1, current_min - 1),
            "reason": (
                f"skill_suggest has {skill_stats.get('rate', 0)*100:.0f}% acceptance "
                f"across {skill_stats['fires']} fires — agents consistently ignore this. "
                f"Reducing min_skills means fewer wasted interventions."
            ),
            "confidence": "high" if skill_stats["fires"] >= 5 else "medium",
            "risk": "Agents may consult fewer skills, slightly reducing discovery of relevant patterns.",
        })

    # P2: Plan missing acceptance improves with escalation
    plan_stats = acceptance.get("plan_missing", {})
    if plan_stats.get("fires", 0) >= 2 and plan_stats.get("avg_level") and plan_stats["avg_level"] > 1.3:
        pid += 1
        proposals.append({
            "id": f"P{pid}",
            "category": "escalation",
            "target": "scripts/autopilot-monitor.sh",
            "field": "plan_missing hint text",
            "old_value": "(current gentle hint)",
            "new_value": "(make level 1 hint firmer, closer to current level 2)",
            "reason": (
                f"plan_missing avg acceptance level is {plan_stats['avg_level']:.1f} — "
                f"agents mostly comply at level 2 (command), not level 1 (hint). "
                f"Making the hint firmer could get compliance earlier."
            ),
            "confidence": "medium",
            "risk": "Firmer hints everywhere may feel aggressive on tasks that don't need plans.",
        })

    # P3: Classification mismatches detected
    maint_as_impl = [i for i in classification_issues if i.get("likely_was") == "maintenance"]
    impl_as_maint = [i for i in classification_issues if i.get("likely_was") == "implementation"]

    if len(maint_as_impl) >= 2:
        pid += 1
        proposals.append({
            "id": f"P{pid}",
            "category": "classifier",
            "target": "scripts/task-classifier.sh",
            "field": "maintenance keywords",
            "old_value": "(current pattern)",
            "new_value": "(narrow maintenance keywords to avoid catching implementation tasks)",
            "reason": (
                f"{len(maint_as_impl)} sessions classified as maintenance turned out to be "
                f"implementation-scale work (10+ edits or delegation needed)."
            ),
            "confidence": "medium",
            "risk": "Narrowing maintenance may push small tasks back into implementation, requiring plans.",
        })

    if len(impl_as_maint) >= 2:
        pid += 1
        proposals.append({
            "id": f"P{pid}",
            "category": "classifier",
            "target": "scripts/task-classifier.sh",
            "field": "implementation keywords",
            "old_value": "(current pattern)",
            "new_value": "(widen maintenance or add quick-fix heuristic based on edit count)",
            "reason": (
                f"{len(impl_as_maint)} sessions classified as implementation finished in "
                f"≤3 edits with no delegation — these were maintenance-scale tasks."
            ),
            "confidence": "medium",
            "risk": "May cause some small implementation tasks to skip planning.",
        })

    # P4: Threshold too eager — fires before agents are ready
    plan_threshold = thresholds.get("plan_missing", {})
    if plan_threshold.get("first_fire_turn") and plan_threshold["first_fire_turn"] <= 4:
        outcome_data = outcomes_summary.get("by_task_type", {}).get("implementation", {})
        avg_edits = outcome_data.get("avg_edits", 0)
        if avg_edits > 8:
            pid += 1
            proposals.append({
                "id": f"P{pid}",
                "category": "threshold",
                "target": "scripts/autopilot-monitor.sh",
                "field": "plan_missing edit threshold",
                "old_value": 3,
                "new_value": 5,
                "reason": (
                    f"plan_missing fires at edit 3 but implementation sessions average "
                    f"{avg_edits:.0f} edits. Agents may need a few exploratory edits before "
                    f"planning. Raising threshold to 5 reduces noise in the early phase."
                ),
                "confidence": "medium",
                "risk": "Agents get 2 more edits before being nudged, which may deepen commitment to a bad approach.",
            })

    # P5: Verification never done despite reminders
    verify_stats = acceptance.get("verify_remind", {})
    if verify_stats.get("fires", 0) >= 2 and verify_stats.get("rate", 0) == 0:
        pid += 1
        proposals.append({
            "id": f"P{pid}",
            "category": "escalation",
            "target": "scripts/autopilot-monitor.sh",
            "field": "verify_remind conditions",
            "old_value": "fires when edits >= 5 AND delegations >= 1",
            "new_value": "fire when edits >= 5 (regardless of delegations)",
            "reason": (
                f"verify_remind has 0% acceptance across {verify_stats['fires']} fires. "
                f"The delegations >= 1 condition may be too restrictive — sessions without "
                f"delegation still need verification."
            ),
            "confidence": "medium",
            "risk": "May fire in sessions where verification isn't applicable.",
        })

    # P6: Delegate suggestion never fires
    if "delegate_suggest" not in acceptance:
        pid += 1
        proposals.append({
            "id": f"P{pid}",
            "category": "policy",
            "target": "scripts/policies/implementation.json",
            "field": "min_delegations",
            "old_value": 1,
            "new_value": 0,
            "reason": (
                "delegate_suggest never fired — the conditions may be too hard to reach "
                "(requires edits > 5 AND min_delegations > 0 AND zero delegations). "
                "Consider whether delegation is actually required, or lower the threshold."
            ),
            "confidence": "low",
            "risk": "Agents may never delegate, doing all work inline.",
        })

    return proposals


# ─── Main ──────────────────────────────────────────────────────────

def collect_data(base_dir):
    """Collect all session data from state directories."""
    state_dirs = find_state_dirs(base_dir)

    all_interventions = []
    all_outcomes = []
    latest_state = None
    policies = {}

    for d in state_dirs:
        interventions = parse_jsonl(d / "interventions.log")
        all_interventions.extend(interventions)

        outcomes = parse_jsonl(d / "outcomes.jsonl")
        all_outcomes.extend(outcomes)

        state = load_json(d / "state.json")
        if state and state.get("turn", 0) > 0:
            latest_state = state

    # Load current policies
    plugin_root = Path(__file__).resolve().parent.parent.parent
    policies_dir = plugin_root / "scripts" / "policies"
    if policies_dir.is_dir():
        for p in policies_dir.glob("*.json"):
            data = load_json(p)
            if data:
                policies[p.stem] = data

    return all_interventions, all_outcomes, latest_state, policies


def format_text_report(report):
    """Format the report as human-readable text."""
    lines = []
    s = report["summary"]
    lines.append("Autopilot Diagnostic Report")
    lines.append("=" * 30)
    lines.append(f"Sessions with outcomes: {s['outcomes_count']}")
    lines.append(f"Total interventions: {s['total_interventions']}")
    if s.get("date_range"):
        lines.append(f"Date range: {s['date_range'][0]} -- {s['date_range'][1]}")
    lines.append("")

    # Acceptance
    lines.append("Intervention Acceptance:")
    for itype, stats in sorted(report["acceptance"].items()):
        rate_str = f"{stats['rate']*100:.0f}%"
        level_str = f"avg level {stats['avg_level']}" if stats["avg_level"] else "n/a"
        supp = f", {stats['suppressed']} suppressed" if stats["suppressed"] else ""
        lines.append(f"  {itype}: {stats['fires']} fires, {rate_str} accepted ({level_str}{supp})")
    lines.append("")

    # Outcomes
    o = report["outcomes"]
    if o["count"] > 0:
        lines.append("Session Outcomes:")
        lines.append(f"  Avg drift: {o['avg_drift']:.2f}")
        lines.append(f"  Verified: {o['pct_verified']*100:.0f}%")
        lines.append(f"  Planned: {o['pct_planned']*100:.0f}%")
        lines.append(f"  Avg edits: {o['avg_edits']:.0f}")
        if o.get("by_task_type"):
            lines.append("  By task type:")
            for tt, ts in sorted(o["by_task_type"].items()):
                lines.append(f"    {tt}: {ts['count']} sessions, avg {ts['avg_edits']} edits, "
                             f"{ts['avg_drift']:.2f} drift, {ts['pct_verified']*100:.0f}% verified")
        lines.append("")

    # Classification issues
    if report["classification_issues"]:
        lines.append("Classification Issues:")
        for issue in report["classification_issues"]:
            lines.append(f"  {issue['classified_as']} -> likely {issue['likely_was']}: {issue['evidence']}")
        lines.append("")

    # Proposals
    if report["proposals"]:
        lines.append("Proposals:")
        for p in report["proposals"]:
            lines.append(f"  [{p['id']}] ({p['confidence']}) {p['category']}: {p['target']}")
            lines.append(f"      {p['field']}: {p['old_value']} -> {p['new_value']}")
            lines.append(f"      Reason: {p['reason']}")
            lines.append(f"      Risk: {p['risk']}")
            lines.append("")
    else:
        lines.append("No proposals — everything looks healthy or not enough data.")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Autopilot diagnostic: analyze effectiveness and propose tuning.")
    ap.add_argument("--dir", default="/tmp/drupal-workflow-states/", help="State directory")
    ap.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    args = ap.parse_args()

    interventions, outcomes, latest_state, policies = collect_data(args.dir)

    if not interventions and not outcomes:
        msg = "No session data found. Run a few sessions first."
        if args.json_output:
            print(json.dumps({"error": msg}))
        else:
            print(msg, file=sys.stderr)
        sys.exit(1)

    # Analyze
    acceptance = analyze_acceptance(interventions, latest_state)
    outcomes_summary = analyze_outcomes(outcomes)
    classification_issues = analyze_classification(outcomes)
    thresholds = analyze_thresholds(interventions)
    proposals = generate_proposals(acceptance, outcomes_summary, classification_issues, thresholds, policies)

    # Date range
    timestamps = [e.get("timestamp") for e in interventions if e.get("timestamp")]
    dates = [dt(t) for t in timestamps if dt(t)]
    date_range = None
    if dates:
        date_range = [min(dates).strftime("%Y-%m-%d"), max(dates).strftime("%Y-%m-%d")]

    report = {
        "summary": {
            "outcomes_count": len(outcomes),
            "total_interventions": len(interventions),
            "date_range": date_range,
        },
        "acceptance": acceptance,
        "outcomes": outcomes_summary,
        "classification_issues": classification_issues,
        "thresholds": thresholds,
        "proposals": proposals,
    }

    if args.json_output:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(format_text_report(report))


if __name__ == "__main__":
    main()
