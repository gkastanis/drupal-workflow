#!/usr/bin/env python3
"""Extract user prompts from Claude Code session JSONL files that triggered
the "magic pattern" — structured delegation via skills, agents, and tasks.

Usage:
    python3 extract-prompts.py SESSIONS_DIR/ --date-range 2026-03-29:2026-03-31 --min-agents 3 --output eval-cases.json
"""
import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

INJECTED_MARKERS = [
    "Base directory for this skill:", "<command-name>", "<command-message>",
    "<command-args>", "<local-command-caveat>", "<skill-format>",
    "# /drupal-", "## Purpose\n",
]


def warn(msg):
    print(f"warning: {msg}", file=sys.stderr)


def dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def parts(content):
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [p for p in content if isinstance(p, dict)]
    return []


def is_injected(text):
    s = text.strip()
    return any(s.startswith(m) or m in s[:200] for m in INJECTED_MARKERS)


def clean_prompt(text):
    """Remove system-reminder blocks but keep everything else including XML/HTML."""
    return re.sub(r'<system-reminder>.*?</system-reminder>', '', text, flags=re.DOTALL).strip()


def extract_user_text(msg):
    content = msg.get("content", "")
    if isinstance(content, str):
        text = content.strip()
        if is_injected(text):
            return ""
        # Fix 5: Strip system-reminder blocks instead of dropping all <-prefixed text
        text = clean_prompt(text)
        return text
    if isinstance(content, list):
        texts = []
        for p in content:
            if not isinstance(p, dict) or p.get("type") == "tool_result":
                continue
            t = (p.get("text") or "").strip()
            if not t or is_injected(t):
                continue
            # Fix 5: Strip system-reminder blocks instead of dropping all <-prefixed text
            t = clean_prompt(t)
            if t:
                texts.append(t)
        return " ".join(texts)
    return ""


def extract_response_signals(assistant_events):
    skills, agents = [], []
    tools = Counter()
    has_tasks = False
    for evt in assistant_events:
        for p in parts(evt.get("message", {}).get("content", [])):
            if p.get("type") != "tool_use":
                continue
            name = p.get("name", "")
            inp = p.get("input", {})
            tools[name] += 1
            if name == "Skill":
                s = inp.get("skill", "")
                if s:
                    skills.append(s)
            elif name == "Agent":
                agents.append(inp.get("subagent_type", "unknown"))
            elif name in ("TaskCreate", "TaskUpdate"):
                has_tasks = True
    return {
        "skills_invoked": skills,
        "agents_dispatched": agents,
        "agent_types": dict(Counter(agents)),
        "tools_used": dict(tools),
        "task_tracking": has_tasks,
    }


def scan_session(path, date_start, date_end, min_agents):
    events, session_id, session_date = [], path.stem, None
    for raw in path.open("r", encoding="utf-8", errors="replace"):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        events.append(obj)
        if not session_date:
            ts = dt(obj.get("timestamp"))
            if ts:
                session_date = ts.date()

    if not session_date:
        return []
    if date_start and session_date < date_start:
        return []
    if date_end and session_date > date_end:
        return []

    # Split into user turns and following assistant responses
    turns = []
    cur_user, cur_asst = None, []
    for evt in events:
        etype = evt.get("type")
        if etype == "user":
            if cur_user is not None:
                turns.append((cur_user, cur_asst))
            cur_user, cur_asst = evt, []
        elif etype == "assistant" and cur_user is not None:
            cur_asst.append(evt)
    if cur_user is not None:
        turns.append((cur_user, cur_asst))

    # Count total agents for session-level filter
    total_agents = sum(
        1 for _, assts in turns for evt in assts
        for p in parts(evt.get("message", {}).get("content", []))
        if p.get("type") == "tool_use" and p.get("name") == "Agent"
    )
    if total_agents < min_agents:
        return []

    # Extract cases from meaningful turns
    cases = []
    for idx, (user_evt, asst_evts) in enumerate(turns):
        text = extract_user_text(user_evt.get("message", {}))
        if not text or len(text) < 15:
            continue
        resp = extract_response_signals(asst_evts)
        has_work = (resp["skills_invoked"] or resp["agents_dispatched"]
                    or sum(resp["tools_used"].values()) > 2)
        if not has_work:
            continue
        cases.append({
            "session_id": session_id, "date": session_date.isoformat(),
            # Fix 5: Increase truncation from 500 to 1000 chars
            "prompt": text[:1000], "prompt_index": idx,
            "observed_response": resp,
        })
    return cases


def main():
    ap = argparse.ArgumentParser(
        description="Extract user prompts that triggered the magic delegation pattern."
    )
    ap.add_argument("path", help="Session JSONL file or directory")
    ap.add_argument("--date-range", default=None,
                    help="Date range as YYYY-MM-DD:YYYY-MM-DD (inclusive)")
    ap.add_argument("--min-agents", type=int, default=3,
                    help="Minimum Agent dispatches per session (default: 3)")
    ap.add_argument("--output", default=None, help="Output JSON file (default: stdout)")
    args = ap.parse_args()

    p = Path(args.path)
    if p.is_file():
        files = [p]
    elif p.is_dir():
        files = sorted(x for x in p.iterdir() if x.is_file() and x.suffix == ".jsonl")
    else:
        print(f"error: {args.path} not found", file=sys.stderr)
        sys.exit(1)

    date_start = date_end = None
    if args.date_range:
        dr = args.date_range.split(":")
        if len(dr) == 2:
            date_start, date_end = date.fromisoformat(dr[0]), date.fromisoformat(dr[1])

    all_cases = []
    for fp in files:
        try:
            all_cases.extend(scan_session(fp, date_start, date_end, args.min_agents))
        except Exception as exc:
            warn(f"{fp.name}: {exc}")

    all_cases.sort(key=lambda c: (c["date"], c["session_id"], c["prompt_index"]))
    output = json.dumps(all_cases, indent=2)
    if args.output:
        Path(args.output).write_text(output + "\n")
        print(f"Wrote {len(all_cases)} eval cases to {args.output}", file=sys.stderr)
    else:
        print(output)

    sessions = set(c["session_id"] for c in all_cases)
    print(f"\nSummary: {len(all_cases)} cases from {len(sessions)} sessions "
          f"({len(files)} files scanned)", file=sys.stderr)


if __name__ == "__main__":
    main()
