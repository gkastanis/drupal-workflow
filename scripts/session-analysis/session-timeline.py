#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from _common import warn, dt, parts


def shorten(text, size=80):
    text = " ".join((text or "").split())
    return text if len(text) <= size else text[: size - 3] + "..."


def relstamp(ts, base):
    secs = max(0, int((ts - base).total_seconds())) if ts and base else 0
    return f"[{secs // 60:02d}:{secs % 60:02d}]"


def emit(ts, base, label, body, limit=80):
    text = body if limit is None else shorten(body, limit)
    print(f"{relstamp(ts, base)} {label}: {text}")


def main():
    ap = argparse.ArgumentParser(description="Chronological timeline for a Claude Code session JSONL file.")
    ap.add_argument("file", help="Session JSONL file")
    ap.add_argument("--tools", action="store_true", help="Show full tool input")
    ap.add_argument("--tokens", action="store_true", help="Show token counts for assistant events")
    ap.add_argument("--thinking", action="store_true", help="Include thinking blocks (first 200 chars)")
    args = ap.parse_args()
    path = Path(args.file)
    if not path.is_file():
        raise SystemExit(f"not a file: {path}")
    rows = []
    for lineno, raw in enumerate(path.open("r", encoding="utf-8", errors="replace"), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            warn(f"{path}:{lineno}: {exc}")
            continue
        ts = dt(obj.get("timestamp") or obj.get("snapshot", {}).get("timestamp"))
        rows.append((ts, obj))
    # Bug 1 fix: use timezone-aware datetime.min as fallback sort key
    # Bug 2 fix: sort ALL events first, then derive base from the sorted first event
    rows.sort(key=lambda item: item[0] or datetime.min.replace(tzinfo=timezone.utc))
    base = rows[0][0] if rows and rows[0][0] else None
    for ts, obj in rows:
        kind = obj.get("type", "unknown")
        if kind == "user":
            content = obj.get("message", {}).get("content")
            items = parts(content) if isinstance(content, list) else [{"type": "text", "text": content or ""}]
            for part in items:
                label = "USER"
                body = part.get("text") or part.get("content") or json.dumps(part, ensure_ascii=False)
                if part.get("type") == "tool_result":
                    label = "TOOL_RESULT"
                emit(ts, base, label, body)
        elif kind == "assistant":
            usage = obj.get("message", {}).get("usage", {})
            suffix = ""
            if args.tokens:
                suffix = (
                    f" [tok in={usage.get('input_tokens',0)} out={usage.get('output_tokens',0)}"
                    f" cache_create={usage.get('cache_creation',{}).get('ephemeral_1h_input_tokens', usage.get('cache_creation_input_tokens',0))}"
                    f" cache_read={usage.get('cache_read_input_tokens',0)}]"
                )
            for part in parts(obj.get("message", {}).get("content")):
                ptype = part.get("type")
                if ptype == "thinking":
                    if args.thinking:
                        emit(ts, base, "THINKING", part.get("thinking", ""), limit=200)
                elif ptype == "text":
                    emit(ts, base, "ASSISTANT", (part.get("text", "") + suffix).strip())
                elif ptype == "tool_use":
                    body = f"{part.get('name','unknown')} {json.dumps(part.get('input', {}), ensure_ascii=False, sort_keys=True)}"
                    emit(ts, base, "TOOL_USE", body + suffix, None if args.tools else 80)
                else:
                    emit(ts, base, ptype.upper(), json.dumps(part, ensure_ascii=False) + suffix)
        elif kind == "system":
            body = obj.get("subtype", "system")
            if obj.get("hookInfos"):
                body += " " + "; ".join(h.get("command", "") for h in obj["hookInfos"])
            if obj.get("hookErrors"):
                body += " errors=" + json.dumps(obj["hookErrors"], ensure_ascii=False)
            emit(ts, base, "SYSTEM", body)
        elif kind == "queue-operation":
            emit(ts, base, "QUEUE", f"{obj.get('operation', '?')} {obj.get('content', '')}")
        elif kind == "file-history-snapshot":
            emit(ts, base, "SNAPSHOT", f"message={obj.get('messageId', '-')}")
        elif kind == "last-prompt":
            emit(ts, base, "LAST_PROMPT", obj.get("lastPrompt", ""))
        else:
            emit(ts, base, kind.upper(), json.dumps(obj, ensure_ascii=False))


if __name__ == "__main__":
    main()
