#!/usr/bin/env python3
"""Score sessions against the magic-era workflow patterns.

Scores each session 0-100 based on how closely it follows the delegation
pattern observed in the Mar 29-31 "magic era" sessions.

Usage:
    python3 pattern-score.py SESSION_FILE.jsonl
    python3 pattern-score.py SESSIONS_DIR/ [--top N] [--trend]
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

MAGIC_BENCHMARKS = {
    "delegation_rate": 0.55,    # agents per edit (not per turn) — magic era: 200 agents / 360 edits
    "skills_per_session": 3.5,
    "task_tracking_pct": 11.1,
    "specialization_pct": 82.0,
}

SPECIALIZED_PREFIXES = ("drupal-workflow:", "ork:", "superpowers:")
# Fix 3: Also match bare agent basenames (JSONL may omit prefix)
SPECIALIZED_AGENTS = {
    "drupal-builder", "drupal-reviewer", "drupal-verifier", "semantic-architect",
}
PLAN_SKILLS = {
    # In-house (drupal-workflow)
    "drupal-workflow:drupal-brainstorming", "drupal-brainstorming",
    "drupal-workflow:writing-plans", "writing-plans",
    "drupal-workflow:drupal-delegation", "drupal-delegation",
    # External (superpowers — optional, recognized if installed)
    "superpowers:brainstorming", "superpowers:writing-plans",
    "brainstorm",
}


def warn(msg):
    print(f"WARN: {msg}", file=sys.stderr)


def dt(obj):
    ts = obj.get("timestamp", "")
    if not ts and obj.get("type") == "file-history-snapshot":
        ts = (obj.get("snapshot") or {}).get("timestamp", "")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def jsonl_files(path):
    if os.path.isfile(path) and path.endswith(".jsonl"):
        return [path]
    if os.path.isdir(path):
        return sorted(os.path.join(path, f) for f in os.listdir(path) if f.endswith(".jsonl"))
    return []


def analyze_session(fpath):
    sid = os.path.basename(fpath).replace(".jsonl", "")[:8]
    info = {"sid": sid, "date": None, "branch": None,
            "user_turns": 0, "agent_dispatches": 0, "skill_invocations": 0,
            "task_tracking": 0, "total_tools": 0, "edits": 0, "specialized_agents": 0,
            "total_agents": 0, "plan_first": False,
            "first_plan_turn": None, "first_heavy_turn": None,
            "has_verification": False}
    turn_idx = 0
    with open(fpath) as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not info["date"]:
                d = dt(obj)
                if d:
                    info["date"] = d.strftime("%Y-%m-%d")
            if not info["branch"]:
                info["branch"] = obj.get("gitBranch", "")
            if obj.get("type") == "user":
                info["user_turns"] += 1
                turn_idx += 1
            if obj.get("type") != "assistant":
                continue
            msg = obj.get("message") or {}
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "tool_use":
                    continue
                name = part.get("name", "")
                inp = part.get("input") or {}
                info["total_tools"] += 1
                if name == "Agent":
                    info["agent_dispatches"] += 1
                    info["total_agents"] += 1
                    at = inp.get("subagent_type", "general")
                    # Fix 3: Match prefixed names OR bare specialized agent names
                    if any(at.startswith(p) for p in SPECIALIZED_PREFIXES) or at in SPECIALIZED_AGENTS:
                        info["specialized_agents"] += 1
                    # Fix 4: Detect verification via agent dispatch
                    if at in ("drupal-workflow:drupal-verifier", "drupal-verifier"):
                        info["has_verification"] = True
                    if info["first_heavy_turn"] is None:
                        info["first_heavy_turn"] = turn_idx
                elif name == "Skill":
                    info["skill_invocations"] += 1
                    sk = inp.get("skill", "")
                    if sk in PLAN_SKILLS and info["first_plan_turn"] is None:
                        info["first_plan_turn"] = turn_idx
                    # Fix 4: Detect verification via skill invocation
                    if sk in ("drupal-workflow:drupal-verify", "drupal-verify"):
                        info["has_verification"] = True
                elif name in ("TaskCreate", "TaskUpdate"):
                    info["task_tracking"] += 1
                elif name in ("Edit", "Write"):
                    info["edits"] += 1
                    if info["first_heavy_turn"] is None:
                        info["first_heavy_turn"] = turn_idx
                elif name == "Bash":
                    if info["first_heavy_turn"] is None:
                        info["first_heavy_turn"] = turn_idx
    if info["first_plan_turn"] is not None:
        if info["first_heavy_turn"] is None or info["first_plan_turn"] <= info["first_heavy_turn"]:
            info["plan_first"] = True
    return info


def score_session(info):
    scores = {}
    edits = max(info["edits"], 1)
    tt = max(info["total_tools"], 1)
    ta = max(info["total_agents"], 1)
    # Delegation: agents per edit (not per turn) — burst sessions score fairly
    rate = info["agent_dispatches"] / edits
    scores["delegation"] = min(20, int(20 * rate / MAGIC_BENCHMARKS["delegation_rate"]))
    sk = info["skill_invocations"]
    scores["skills"] = min(25, int(25 * sk / MAGIC_BENCHMARKS["skills_per_session"]))
    pct = info["task_tracking"] / tt * 100
    scores["tracking"] = min(20, int(20 * pct / MAGIC_BENCHMARKS["task_tracking_pct"]))
    if info["total_agents"] > 0:
        spec_pct = info["specialized_agents"] / ta * 100
        scores["specialization"] = min(15, int(15 * spec_pct / MAGIC_BENCHMARKS["specialization_pct"]))
    else:
        scores["specialization"] = 0
    scores["plan_first"] = 10 if info["plan_first"] else 0
    # Fix 4: New verification dimension
    scores["verification"] = 10 if info.get("has_verification") else 0
    return sum(scores.values()), scores


def label(score):
    if score >= 80: return "Magic"
    if score >= 60: return "Good"
    if score >= 40: return "Ad-hoc"
    return "Chaotic"


def main():
    parser = argparse.ArgumentParser(description="Score sessions against magic-era patterns")
    parser.add_argument("path", help="Session file or directory")
    parser.add_argument("--top", type=int, default=10, help="Show top N sessions (default: 10)")
    parser.add_argument("--trend", action="store_true", help="Show daily trend")
    args = parser.parse_args()

    files = jsonl_files(args.path)
    if not files:
        print(f"No .jsonl files found at {args.path}", file=sys.stderr)
        sys.exit(1)

    results = []
    for fpath in files:
        try:
            info = analyze_session(fpath)
            if info["user_turns"] < 3:
                continue
            total, scores = score_session(info)
            results.append({**info, "score": total, "scores": scores, "label": label(total)})
        except Exception as e:
            warn(f"{os.path.basename(fpath)}: {e}")

    if not results:
        print("No sessions with 3+ turns found.")
        return

    results.sort(key=lambda r: r["date"] or "0")
    scores_list = [r["score"] for r in results]
    avg_score = sum(scores_list) / len(scores_list)
    dist = Counter(r["label"] for r in results)

    print(f"Sessions: {len(results)}  Avg score: {avg_score:.0f}/100")
    print(f"  Magic(80+): {dist.get('Magic',0)}  Good(60-79): {dist.get('Good',0)}  "
          f"Ad-hoc(40-59): {dist.get('Ad-hoc',0)}  Chaotic(<40): {dist.get('Chaotic',0)}")
    print()

    if args.trend:
        by_date = defaultdict(list)
        for r in results:
            by_date[r["date"] or "?"].append(r["score"])
        print(f"{'Date':<12} {'Sess':>4} {'Avg':>6}  Bar")
        print("-" * 55)
        for d in sorted(by_date.keys()):
            vals = by_date[d]
            a = sum(vals) / len(vals)
            bar = "#" * int(a / 2)
            print(f"{d:<12} {len(vals):>4} {a:>6.0f}  {bar}")
        print()

    if len(files) == 1 and results:
        r = results[0]
        s = r["scores"]
        print(f"Session: {r['sid']}  Date: {r['date']}  Branch: {r['branch']}")
        print(f"  Delegation:     {s['delegation']:>2}/20  ({r['agent_dispatches']} agents / {r['edits']} edits)")
        print(f"  Skills:         {s['skills']:>2}/25  ({r['skill_invocations']} invocations)")
        print(f"  Task tracking:  {s['tracking']:>2}/20  ({r['task_tracking']} creates+updates / {r['total_tools']} tools)")
        print(f"  Specialization: {s['specialization']:>2}/15  ({r['specialized_agents']}/{r['total_agents']} specialized)")
        print(f"  Plan-first:     {s['plan_first']:>2}/10  ({'yes' if r['plan_first'] else 'no'})")
        print(f"  Verification:   {s['verification']:>2}/10  ({'yes' if r['has_verification'] else 'no'})")
    else:
        ranked = sorted(results, key=lambda r: -r["score"])[:args.top]
        print(f"{'SID':<10} {'Date':<12} {'Score':>5} {'Label':<8} {'Turns':>5} {'Agents':>6} {'Skills':>6} {'Branch'}")
        print("-" * 85)
        for r in ranked:
            print(f"{r['sid']:<10} {r['date'] or '?':<12} {r['score']:>5} {r['label']:<8} "
                  f"{r['user_turns']:>5} {r['agent_dispatches']:>6} {r['skill_invocations']:>6} {r['branch']}")


if __name__ == "__main__":
    main()
