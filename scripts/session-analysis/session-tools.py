#!/usr/bin/env python3
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PATH_RE = re.compile(r"(?:/[\w./:@+-]+|(?:\./|\.\./)?[\w.-]+(?:/[\w.-]+)+)")
READ_HINTS = ("read", "view", "search", "glob", "ls", "find", "cat")
EDIT_HINTS = ("edit", "write", "replace", "multi", "create", "delete")


def warn(msg):
    print(f"warning: {msg}", file=sys.stderr)


def jsonl_files(path):
    p = Path(path)
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(x for x in p.iterdir() if x.is_file() and x.suffix == ".jsonl")
    raise FileNotFoundError(path)


def walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from walk_strings(v)
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)


def extract_paths(value):
    hits = Counter()
    for text in walk_strings(value):
        for match in PATH_RE.findall(text):
            hits[match] += 1
    return hits


def main():
    ap = argparse.ArgumentParser(description="Tool usage analysis for Claude Code session JSONL logs.")
    ap.add_argument("path", help="Directory or single JSONL file")
    ap.add_argument("--by-session", action="store_true", help="Show per-session tool breakdown")
    ap.add_argument("--patterns", action="store_true", help="Show common tool sequences")
    args = ap.parse_args()
    tool_counts, reads, edits, seq2 = Counter(), Counter(), Counter(), Counter()
    by_session = defaultdict(Counter)
    for path in jsonl_files(args.path):
        session_tools = []
        for lineno, raw in enumerate(path.open("r", encoding="utf-8", errors="replace"), 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                warn(f"{path}:{lineno}: {exc}")
                continue
            if obj.get("type") != "assistant":
                continue
            for part in obj.get("message", {}).get("content", []):
                if not isinstance(part, dict) or part.get("type") != "tool_use":
                    continue
                name = part.get("name", "unknown")
                tool_counts[name] += 1
                by_session[path.stem][name] += 1
                session_tools.append(name)
                found = extract_paths(part.get("input", {}))
                lname = name.lower()
                if any(h in lname for h in READ_HINTS):
                    reads.update(found)
                if any(h in lname for h in EDIT_HINTS):
                    edits.update(found)
        if args.patterns:
            for a, b in zip(session_tools, session_tools[1:]):
                seq2[(a, b)] += 1
    print("Tool Frequency")
    print("--------------")
    for name, count in tool_counts.most_common(25):
        print(f"{name:28} {count}")
    print()
    print("Most Read Paths")
    print("---------------")
    for path, count in reads.most_common(15):
        print(f"{count:4} {path}")
    print()
    print("Most Edited Paths")
    print("-----------------")
    for path, count in edits.most_common(15):
        print(f"{count:4} {path}")
    if args.patterns:
        print()
        print("Common Tool Sequences")
        print("---------------------")
        for (a, b), count in seq2.most_common(20):
            print(f"{count:4} {a} -> {b}")
    if args.by_session:
        print()
        print("By Session")
        print("----------")
        for session, counts in sorted(by_session.items()):
            top = ", ".join(f"{name}:{count}" for name, count in counts.most_common(8))
            print(f"{session[:8]} {top}")


if __name__ == "__main__":
    main()
