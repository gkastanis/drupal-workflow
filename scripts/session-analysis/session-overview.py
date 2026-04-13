#!/usr/bin/env python3
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from _common import warn, dt, jsonl_files, parts, model_cost


def summarize(path):
    s = {
        "file": str(path),
        "session_id": path.stem,
        "branch": "",
        "start": None,
        "end": None,
        "counts": Counter(),
        "tools": Counter(),
        "user_turns": 0,
        "tokens": Counter(),
        "cost": 0.0,
    }
    for lineno, raw in enumerate(path.open("r", encoding="utf-8", errors="replace"), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            warn(f"{path}:{lineno}: {exc}")
            continue
        kind = obj.get("type", "unknown")
        s["counts"][kind] += 1
        ts = dt(obj.get("timestamp") or obj.get("snapshot", {}).get("timestamp"))
        if ts:
            s["start"] = min(filter(None, [s["start"], ts]), default=ts)
            s["end"] = max(filter(None, [s["end"], ts]), default=ts)
        s["session_id"] = obj.get("sessionId") or s["session_id"]
        s["branch"] = obj.get("gitBranch") or s["branch"]
        if kind == "user":
            items = parts(obj.get("message", {}).get("content"))
            has_text = False
            for part in items:
                if part.get("type") == "tool_result":
                    s["counts"]["tool_result"] += 1
                text = part.get("text") or part.get("content")
                if isinstance(text, str) and text.strip():
                    has_text = True
            if isinstance(obj.get("message", {}).get("content"), str):
                has_text = bool(obj["message"]["content"].strip())
            if has_text:
                s["user_turns"] += 1
        elif kind == "assistant":
            usage = obj.get("message", {}).get("usage", {})
            in_tok = usage.get("input_tokens", 0)
            out_tok = usage.get("output_tokens", 0)
            cache = usage.get("cache_creation", {})
            cc_tok = cache.get(
                "ephemeral_1h_input_tokens", usage.get("cache_creation_input_tokens", 0)
            )
            cr_tok = usage.get("cache_read_input_tokens", 0)
            s["tokens"]["input"] += in_tok
            s["tokens"]["output"] += out_tok
            s["tokens"]["cache_create"] += cc_tok
            s["tokens"]["cache_read"] += cr_tok
            model = obj.get("message", {}).get("model", "")
            s["cost"] += model_cost(model, in_tok, out_tok, cc_tok, cr_tok)
            for part in parts(obj.get("message", {}).get("content")):
                if part.get("type") == "tool_use":
                    s["tools"][part.get("name", "unknown")] += 1
    return s


def fmt_num(n):
    return f"{n:,}"


def row(s):
    duration = (s["end"] - s["start"]).total_seconds() if s["start"] and s["end"] else 0
    tools = ", ".join(f"{k}:{v}" for k, v in s["tools"].most_common(5)) or "-"
    return [
        s["session_id"][:8],
        s["start"].strftime("%Y-%m-%d %H:%M") if s["start"] else "-",
        f"{duration/60:.1f}m",
        s["branch"] or "-",
        str(s["user_turns"]),
        str(s["counts"]["assistant"]),
        fmt_num(sum(s["tokens"].values())),
        f"${s['cost']:.2f}",
        tools,
    ]


def print_table(rows, headers):
    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)] if rows else [len(h) for h in headers]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(str(v).ljust(w) for v, w in zip(r, widths)))


def main():
    ap = argparse.ArgumentParser(description="Quick stats for Claude Code session JSONL logs.")
    ap.add_argument("path", help="Session JSONL file or directory of JSONL files")
    args = ap.parse_args()
    sessions = [summarize(p) for p in jsonl_files(args.path)]
    # Bug 1 fix: use timezone-aware datetime.min as fallback sort key
    sessions.sort(key=lambda s: s["start"] or datetime.min.replace(tzinfo=timezone.utc))
    if len(sessions) == 1 and Path(args.path).is_file():
        s = sessions[0]
        duration = (s["end"] - s["start"]).total_seconds() if s["start"] and s["end"] else 0
        print(f"Session: {s['session_id']}")
        print(f"Date:    {s['start'].isoformat() if s['start'] else '-'}")
        print(f"Branch:  {s['branch'] or '-'}")
        print(f"Duration:{duration/60:.1f} minutes")
        print(f"Counts:  " + ", ".join(f"{k}={v}" for k, v in sorted(s["counts"].items())))
        print(f"Turns:   {s['user_turns']}")
        print(
            "Tokens:  input={input:,} output={output:,} cache_create={cache_create:,} cache_read={cache_read:,}".format(
                **s["tokens"]
            )
        )
        print(f"Cost:    ${s['cost']:.2f}")
        print("Tools:   " + (", ".join(f"{k}:{v}" for k, v in s["tools"].most_common()) or "-"))
        return
    rows = [row(s) for s in sessions]
    print_table(rows, ["ID", "Date", "Duration", "Branch", "Turns", "Asst", "Tokens", "Cost", "Top tools"])
    total_tokens = Counter()
    total_cost = 0.0
    total_turns = 0
    total_tools = Counter()
    for s in sessions:
        total_tokens.update(s["tokens"])
        total_cost += s["cost"]
        total_turns += s["user_turns"]
        total_tools.update(s["tools"])
    print()
    print(f"Sessions: {len(sessions)}")
    print(f"Turns:    {total_turns:,}")
    print(
        "Tokens:   input={input:,} output={output:,} cache_create={cache_create:,} cache_read={cache_read:,}".format(
            **total_tokens
        )
    )
    print(f"Cost:     ${total_cost:.2f}")
    print("Tools:    " + ", ".join(f"{k}:{v}" for k, v in total_tools.most_common(10)))


if __name__ == "__main__":
    main()
