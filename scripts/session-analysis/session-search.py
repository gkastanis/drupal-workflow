#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from _common import warn, dt, jsonl_files, parts


def shorten(text, size=140):
    text = " ".join((text or "").split())
    return text if len(text) <= size else text[: size - 3] + "..."


def emit(session, ts, role, text):
    stamp = ts.isoformat() if ts else "-"
    print(f"{session[:8]} {stamp} {role:10} {shorten(text)}")


def main():
    ap = argparse.ArgumentParser(description="Full-text search across Claude Code session JSONL logs.")
    ap.add_argument("path", help="Directory or single JSONL file")
    ap.add_argument("query", help="Case-insensitive text to search")
    ap.add_argument("--user", action="store_true", help="Search user messages")
    ap.add_argument("--assistant", action="store_true", help="Search assistant text")
    ap.add_argument("--tools", action="store_true", help="Search tool input and tool results")
    args = ap.parse_args()
    if not (args.user or args.assistant or args.tools):
        args.user = args.assistant = True
    needle = args.query.lower()
    matches = 0
    for path in jsonl_files(args.path):
        for lineno, raw in enumerate(path.open("r", encoding="utf-8", errors="replace"), 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                warn(f"{path}:{lineno}: {exc}")
                continue
            ts = dt(obj.get("timestamp"))
            session = obj.get("sessionId") or path.stem
            if args.user and obj.get("type") == "user":
                content = obj.get("message", {}).get("content")
                # Bug 4 fix: normalize to list of dicts once via parts(), avoiding double-count
                # of string content (previously searched as raw string AND via parts())
                for part in parts(content):
                    text = part.get("text") or ""
                    if isinstance(text, str) and needle in text.lower():
                        emit(session, ts, "user", text)
                        matches += 1
            if args.assistant and obj.get("type") == "assistant":
                for part in parts(obj.get("message", {}).get("content")):
                    text = part.get("text") or part.get("thinking") or ""
                    if isinstance(text, str) and needle in text.lower():
                        emit(session, ts, f"assistant/{part.get('type','text')}", text)
                        matches += 1
            if args.tools:
                if obj.get("type") == "assistant":
                    for part in parts(obj.get("message", {}).get("content")):
                        if part.get("type") == "tool_use":
                            blob = json.dumps(part.get("input", {}), ensure_ascii=False, sort_keys=True)
                            if needle in blob.lower() or needle in part.get("name", "").lower():
                                emit(session, ts, "tool_use", f"{part.get('name')} {blob}")
                                matches += 1
                elif obj.get("type") == "user":
                    for part in parts(obj.get("message", {}).get("content")):
                        if part.get("type") == "tool_result":
                            # Bug 5 fix: content may be a list or dict (structured tool result)
                            # only call .lower() on actual strings
                            raw_content = part.get("content")
                            if isinstance(raw_content, str):
                                text = raw_content
                            else:
                                text = json.dumps(raw_content, ensure_ascii=False)
                            if needle in text.lower():
                                emit(session, ts, "tool_result", text)
                                matches += 1
    if not matches:
        print("No matches.")


if __name__ == "__main__":
    main()
