#!/usr/bin/env python3
"""
Drupal-Workflow Session Dashboard
Comprehensive single-page analysis of session cost, quality, skills, and workflow patterns.
"""

import json
import sys
import argparse
import glob
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Any

# Model pricing per million tokens
MODEL_PRICING = {
    "claude-opus-4-6": (15.0, 75.0, 1.50, 0.30),
    "claude-sonnet-4-6": (3.0, 15.0, 0.75, 0.06),
    "claude-haiku-4-5": (0.80, 4.0, 0.20, 0.02),
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Drupal-Workflow session dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 session-dashboard.py ~/.claude/projects/-home-pointblank-projects-openbrain-drupal/
  python3 session-dashboard.py /path/to/session.jsonl
  python3 session-dashboard.py /path/to/sessions/ --days 7
  python3 session-dashboard.py /path/to/sessions/ --json > dashboard.json
        """,
    )
    parser.add_argument(
        "path",
        help="Directory with .jsonl files or single .jsonl file",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Limit to last N days (default: all)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON instead of dashboard",
    )
    return parser.parse_args()


def calculate_cost(usage: Dict[str, Any], model: str) -> float:
    """Calculate session cost from token usage."""
    input_rate, output_rate, cache_create_rate, cache_read_rate = MODEL_PRICING.get(
        model, MODEL_PRICING["claude-opus-4-6"]
    )

    inp = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
    out = usage.get("output_tokens", 0)
    cache_create = usage.get("cache_creation_input_tokens", 0)

    cost = (inp / 1_000_000) * input_rate
    cost += (out / 1_000_000) * output_rate
    cost += (cache_create / 1_000_000) * cache_create_rate
    return cost


def extract_tools(content: List[Dict]) -> Dict[str, int]:
    """Extract tool names and counts from assistant message content."""
    tools = defaultdict(int)
    for item in content:
        if item.get("type") == "tool_use":
            name = item.get("name", "unknown")
            tools[name] += 1
    return tools


def process_session_file(filepath: str) -> Dict[str, Any]:
    """Process a single JSONL session file."""
    cost = 0.0
    turns = 0
    tool_calls = defaultdict(int)
    skills = set()
    agents = set()
    branch = None
    start_time = None
    end_time = None
    turntable = []

    try:
        with open(filepath) as f:
            for line in f:
                try:
                    data = json.loads(line)

                    # Capture metadata
                    if "gitBranch" in data and not branch:
                        branch = data["gitBranch"]
                    if "timestamp" in data:
                        if not start_time:
                            start_time = data["timestamp"]
                        end_time = data["timestamp"]

                    # Process assistant messages
                    if data.get("type") == "assistant":
                        turns += 1
                        usage = data.get("message", {}).get("usage", {})
                        model = data.get("message", {}).get("model", "claude-opus-4-6")

                        if usage:
                            cost += calculate_cost(usage, model)

                        # Extract tools
                        content = data.get("message", {}).get("content", [])
                        tools = extract_tools(content)
                        for tool_name, count in tools.items():
                            tool_calls[tool_name] += count

                            # Categorize
                            if tool_name == "Skill":
                                for item in content:
                                    if item.get("type") == "tool_use" and item.get("name") == "Skill":
                                        skill_name = item.get("input", {}).get("skill", "")
                                        if skill_name:
                                            skills.add(skill_name)
                            elif tool_name == "Agent":
                                for item in content:
                                    if item.get("type") == "tool_use" and item.get("name") == "Agent":
                                        agent = item.get("input", {}).get("subagent_type", "")
                                        if agent:
                                            agents.add(agent)
                            else:
                                agents.add(tool_name)

                        # Record for activity tracking
                        turntable.append(
                            {
                                "turn": turns,
                                "timestamp": data.get("timestamp"),
                                "tools": dict(tools),
                                "model": model,
                            }
                        )

                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return None

    if turns == 0:
        return None

    return {
        "session_id": Path(filepath).stem,
        "branch": branch or "unknown",
        "start_time": start_time,
        "end_time": end_time,
        "turns": turns,
        "cost": cost,
        "skills": len(skills),
        "agents": len(agents),
        "tool_calls": dict(tool_calls),
        "skill_list": sorted(skills),
        "agent_list": sorted(agents),
        "turntable": turntable,
    }


def get_date_from_timestamp(ts: str) -> str:
    """Extract date from ISO timestamp."""
    try:
        return ts.split("T")[0]
    except:
        return "unknown"


def should_include_session(session: Dict[str, Any], days_back: int) -> bool:
    """Check if session should be included based on date filter."""
    if days_back is None:
        return True
    if not session.get("start_time"):
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    try:
        session_time = datetime.fromisoformat(session["start_time"].replace("Z", "+00:00"))
        return session_time >= cutoff
    except:
        return False


def calculate_magic_score(session: Dict[str, Any]) -> int:
    """Calculate workflow quality score (0-100)."""
    score = 0
    metrics = {}

    # Delegation rate: target >= 0.5 agents per turn
    delegation_rate = session.get("agents", 0) / max(session.get("turns", 1), 1)
    delegation_score = min(100, int((delegation_rate / 0.5) * 100))
    metrics["delegation"] = delegation_score
    score += delegation_score * 0.2

    # Skill discipline: target >= 3 skills per session
    skill_count = session.get("skills", 0)
    skill_score = min(100, int((skill_count / 3) * 100))
    metrics["skill_discipline"] = skill_score
    score += skill_score * 0.2

    # Task tracking: target >= 11% of tool calls
    total_tools = sum(session.get("tool_calls", {}).values())
    task_tools = (
        session.get("tool_calls", {}).get("TaskCreate", 0)
        + session.get("tool_calls", {}).get("TaskUpdate", 0)
    )
    task_pct = (task_tools / max(total_tools, 1)) * 100
    task_score = min(100, int((task_pct / 11) * 100))
    metrics["task_tracking"] = task_score
    score += task_score * 0.2

    # Specialization: target >= 70% of agents are specialized (not Agent generic)
    total_agents = session.get("agents", 0)
    generic_agents = session.get("tool_calls", {}).get("Agent", 0)
    spec_pct = ((total_agents - generic_agents) / max(total_agents, 1)) * 100 if total_agents > 0 else 0
    spec_score = min(100, int((spec_pct / 70) * 100))
    metrics["specialization"] = spec_score
    score += spec_score * 0.2

    # Plan-first: check if brainstorming/planning tools used early
    plan_tools = session.get("tool_calls", {}).get("Skill", 0)
    plan_score = 80 if plan_tools > 0 else 20
    metrics["plan_first"] = plan_score
    score += plan_score * 0.2

    return int(score)


def build_daily_summary(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build daily activity summary."""
    daily = defaultdict(lambda: {"sessions": [], "turns": 0, "cost": 0.0, "skills": 0, "agents": 0, "scores": []})

    for session in sessions:
        date = get_date_from_timestamp(session.get("start_time", ""))
        if date != "unknown":
            daily[date]["sessions"].append(session)
            daily[date]["turns"] += session.get("turns", 0)
            daily[date]["cost"] += session.get("cost", 0)
            daily[date]["skills"] += session.get("skills", 0)
            daily[date]["agents"] += session.get("agents", 0)
            daily[date]["scores"].append(calculate_magic_score(session))

    # Calculate magic score per day
    for date in daily:
        scores = daily[date]["scores"]
        daily[date]["magic_score"] = int(sum(scores) / len(scores)) if scores else 0

    return daily


def format_currency(value: float) -> str:
    """Format value as currency."""
    return f"${value:.2f}"


def format_bar(value: float, max_value: float, width: int = 20) -> str:
    """Create a simple bar chart."""
    if max_value == 0:
        return "▁" * width
    filled = int((value / max_value) * width)
    return "█" * filled + "▁" * (width - filled)


def print_dashboard(sessions: List[Dict[str, Any]], daily: Dict[str, Any]):
    """Print formatted text dashboard."""
    if not sessions:
        print("No sessions found.")
        return

    total_cost = sum(s["cost"] for s in sessions)
    total_turns = sum(s["turns"] for s in sessions)
    total_sessions = len(sessions)
    avg_cost_per_turn = total_cost / total_turns if total_turns > 0 else 0

    # Get date range
    dates = sorted([get_date_from_timestamp(s["start_time"]) for s in sessions if s.get("start_time")])
    date_range = f"{dates[0]} - {dates[-1]}" if dates else "Unknown"

    # Collect all cache hit stats
    cache_hits = 0
    cache_reads = 0
    for session in sessions:
        for turn in session.get("turntable", []):
            for item in (turn.get("tools") or {}).items():
                if item[0] in ["cache_read_input_tokens", "cache_creation_input_tokens"]:
                    cache_reads += item[1]

    # Summary Box
    print("╔" + "═" * 58 + "╗")
    print("║  DRUPAL-WORKFLOW SESSION DASHBOARD" + " " * 24 + "║")
    print(f"║  Period: {date_range}" + " " * (34 - len(date_range)) + "║")
    print(f"║  Sessions: {total_sessions} | Turns: {total_turns:,} | Cost: {format_currency(total_cost)}" + " " * (20 - len(format_currency(total_cost))) + "║")
    print(f"║  Avg cost/turn: {format_currency(avg_cost_per_turn)}" + " " * (31 - len(format_currency(avg_cost_per_turn))) + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    # Daily Activity (last 7 days)
    print("Daily Activity (last 7 days)")
    print("Date        Sess  Turns  Cost     Skills  Agents  Score")
    print("─" * 60)
    for date in sorted(daily.keys())[-7:]:
        d = daily[date]
        print(
            f"{date}   {len(d['sessions']):3d}   {d['turns']:4d}  {format_currency(d['cost']):8s}  "
            f"{d['skills']:3d}     {d['agents']:3d}    {d['magic_score']:3d}/100"
        )
    print()

    # Skill Heatmap
    skill_counts = defaultdict(int)
    for session in sessions:
        for skill in session.get("skill_list", []):
            skill_counts[skill] += 1

    if skill_counts:
        print("Skill Usage (top 10)")
        for skill, count in sorted(skill_counts.items(), key=lambda x: -x[1])[:10]:
            bar = format_bar(count, max(skill_counts.values()), 18)
            print(f"  {skill:40s} {bar}  {count:2d}")
        print()

    # Agent Delegation
    agent_counts = defaultdict(int)
    for session in sessions:
        for agent in session.get("agent_list", []):
            agent_counts[agent] += 1

    total_agent_calls = sum(agent_counts.values())
    if agent_counts:
        print(f"Agent Dispatches: {total_agent_calls} total")
        for agent, count in sorted(agent_counts.items(), key=lambda x: -x[1])[:5]:
            pct = (count / total_agent_calls) * 100
            bar = format_bar(count, max(agent_counts.values()), 18)
            print(f"  {agent:30s}  {count:3d} ({pct:5.1f}%)  {bar}")
        print()

    # Workflow Health
    scores = [calculate_magic_score(s) for s in sessions]
    avg_score = int(sum(scores) / len(scores)) if scores else 0
    print(f"Workflow Health Score: {avg_score}/100")
    print(f"  Average delegation rate: {sum(s.get('agents', 0) for s in sessions) / max(total_turns, 1):.2f} agents/turn (target: 0.5)")
    print(f"  Average skills/session: {sum(s.get('skills', 0) for s in sessions) / max(total_sessions, 1):.1f} (target: 3.0)")
    print()

    # Cost Breakdown by Branch
    branch_costs = defaultdict(lambda: {"cost": 0.0, "sessions": 0})
    for session in sessions:
        branch = session.get("branch", "unknown")
        branch_costs[branch]["cost"] += session.get("cost", 0)
        branch_costs[branch]["sessions"] += 1

    print("Cost by Branch:")
    for branch, stats in sorted(branch_costs.items(), key=lambda x: -x[1]["cost"])[:3]:
        pct = (stats["cost"] / total_cost * 100) if total_cost > 0 else 0
        bar = format_bar(stats["cost"], max(s["cost"] for s in branch_costs.values()), 15)
        print(
            f"  {branch:30s} {format_currency(stats['cost']):8s} ({pct:5.1f}%)  {bar}  "
            f"{stats['sessions']} sessions"
        )
    print()

    # Top Sessions
    print("Top 5 Sessions by Cost:")
    for session in sorted(sessions, key=lambda x: -x["cost"])[:5]:
        print(
            f"  {session['session_id'][:8]}  {get_date_from_timestamp(session['start_time'])}  "
            f"{format_currency(session['cost']):8s}  {session['turns']:3d} turns  {session['branch']}"
        )


def print_json_output(sessions: List[Dict[str, Any]], daily: Dict[str, Any]):
    """Print machine-readable JSON output."""
    total_cost = sum(s["cost"] for s in sessions)
    total_turns = sum(s["turns"] for s in sessions)

    output = {
        "summary": {
            "total_sessions": len(sessions),
            "total_turns": total_turns,
            "total_cost": round(total_cost, 2),
            "avg_cost_per_turn": round(total_cost / total_turns, 2) if total_turns > 0 else 0,
        },
        "daily": {date: {
            "sessions": len(d["sessions"]),
            "turns": d["turns"],
            "cost": round(d["cost"], 2),
            "magic_score": d["magic_score"],
        } for date, d in sorted(daily.items())},
        "sessions": [
            {
                "session_id": s["session_id"],
                "branch": s["branch"],
                "start_time": s["start_time"],
                "turns": s["turns"],
                "cost": round(s["cost"], 2),
                "skills": s["skills"],
                "agents": s["agents"],
                "score": calculate_magic_score(s),
            }
            for s in sessions
        ],
    }
    print(json.dumps(output, indent=2))


def main():
    args = parse_args()
    path = Path(args.path)

    # Determine if file or directory
    if path.is_file() and path.suffix == ".jsonl":
        files = [str(path)]
    elif path.is_dir():
        files = sorted(glob.glob(str(path / "*.jsonl")))
    else:
        print(f"Error: {args.path} is not a valid file or directory", file=sys.stderr)
        sys.exit(1)

    if not files:
        print(f"No .jsonl files found in {args.path}", file=sys.stderr)
        sys.exit(1)

    # Process sessions
    sessions = []
    for filepath in files:
        session = process_session_file(filepath)
        if session and should_include_session(session, args.days):
            sessions.append(session)

    if not sessions:
        print("No sessions matched the filters.", file=sys.stderr)
        sys.exit(1)

    # Build summaries
    daily = build_daily_summary(sessions)

    # Output
    if args.json:
        print_json_output(sessions, daily)
    else:
        print_dashboard(sessions, daily)


if __name__ == "__main__":
    main()
