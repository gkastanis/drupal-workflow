#!/usr/bin/env python3
import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from _common import warn, dt, jsonl_files, model_cost


def scan(path):
    data = {
        "id": path.stem,
        "date": "-",
        "branch": "-",
        "tokens": Counter(),
        "cost": 0.0,
        "questions": 0,
    }
    first = None
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
        if ts and not first:
            first = ts
            data["date"] = ts.date().isoformat()
        data["branch"] = obj.get("gitBranch") or data["branch"]
        if obj.get("type") == "assistant":
            usage = obj.get("message", {}).get("usage", {})
            in_tok = usage.get("input_tokens", 0)
            out_tok = usage.get("output_tokens", 0)
            cr_tok = usage.get("cache_read_input_tokens", 0)
            cc_tok = usage.get("cache_creation", {}).get(
                "ephemeral_1h_input_tokens", usage.get("cache_creation_input_tokens", 0)
            )
            data["tokens"]["input"] += in_tok
            data["tokens"]["output"] += out_tok
            data["tokens"]["cache_read"] += cr_tok
            data["tokens"]["cache_create"] += cc_tok
            model = obj.get("message", {}).get("model", "")
            data["cost"] += model_cost(model, in_tok, out_tok, cc_tok, cr_tok)
        elif obj.get("type") == "user":
            content = obj.get("message", {}).get("content")
            if isinstance(content, str) and content.strip():
                data["questions"] += 1
            elif isinstance(content, list) and any(
                isinstance(p, dict) and p.get("type") != "tool_result" and (p.get("text") or p.get("content"))
                for p in content
            ):
                data["questions"] += 1
    data["question_cost"] = data["cost"] / data["questions"] if data["questions"] else 0.0
    return data


def print_group(title, mapping):
    print(title)
    print("-" * len(title))
    for key, val in sorted(mapping.items(), key=lambda kv: kv[0]):
        print(
            f"{key:20} cost=${val['cost']:.2f} questions={val['questions']:,} "
            f"q_cost=${val['question_cost']:.2f} cache_hit={val['cache_hit']:.1%}"
        )
    print()


def main():
    ap = argparse.ArgumentParser(description="Cost analysis for Claude Code session JSONL logs.")
    ap.add_argument("path", help="Directory or single JSONL file")
    ap.add_argument("--by-date", action="store_true", help="Aggregate costs by session date")
    ap.add_argument("--by-branch", action="store_true", help="Aggregate costs by git branch")
    ap.add_argument("--top", type=int, default=0, help="Show top N most expensive sessions")
    args = ap.parse_args()
    sessions = [scan(p) for p in jsonl_files(args.path)]
    total_tokens = Counter()
    total_cost = 0.0
    total_questions = 0
    for s in sessions:
        total_tokens.update(s["tokens"])
        total_cost += s["cost"]
        total_questions += s["questions"]
    denom = total_tokens["cache_create"] + total_tokens["cache_read"]
    cache_hit = total_tokens["cache_read"] / denom if denom else 0.0
    print(f"Sessions:       {len(sessions)}")
    print(f"Total cost:     ${total_cost:.2f}")
    print(
        f"Tokens:         input={total_tokens['input']:,} output={total_tokens['output']:,} "
        f"cache_create={total_tokens['cache_create']:,} cache_read={total_tokens['cache_read']:,}"
    )
    print(f"Questions:      {total_questions:,}")
    print(f"Question cost:  ${total_cost / total_questions:.2f}" if total_questions else "Question cost:  n/a")
    print(f"Cache hit rate: {cache_hit:.1%}")
    print()
    if args.by_date:
        # Bug 3 fix: initialize ALL token fields including cache_create and cache_read
        grouped = defaultdict(lambda: {
            "cost": 0.0, "questions": 0,
            "input": 0, "output": 0, "cache_create": 0, "cache_read": 0,
        })
        for s in sessions:
            g = grouped[s["date"]]
            g["cost"] += s["cost"]
            g["questions"] += s["questions"]
            g["input"] += s["tokens"]["input"]
            g["output"] += s["tokens"]["output"]
            g["cache_create"] += s["tokens"]["cache_create"]
            g["cache_read"] += s["tokens"]["cache_read"]
        for val in grouped.values():
            denom = val["cache_create"] + val["cache_read"]
            val["cache_hit"] = val["cache_read"] / denom if denom else 0.0
            val["question_cost"] = val["cost"] / val["questions"] if val["questions"] else 0.0
        print_group("By Date", grouped)
    if args.by_branch:
        # Bug 3 fix: initialize ALL token fields including cache_create and cache_read
        grouped = defaultdict(lambda: {
            "cost": 0.0, "questions": 0,
            "input": 0, "output": 0, "cache_create": 0, "cache_read": 0,
        })
        for s in sessions:
            g = grouped[s["branch"]]
            g["cost"] += s["cost"]
            g["questions"] += s["questions"]
            g["input"] += s["tokens"]["input"]
            g["output"] += s["tokens"]["output"]
            g["cache_create"] += s["tokens"]["cache_create"]
            g["cache_read"] += s["tokens"]["cache_read"]
        for val in grouped.values():
            denom = val["cache_create"] + val["cache_read"]
            val["cache_hit"] = val["cache_read"] / denom if denom else 0.0
            val["question_cost"] = val["cost"] / val["questions"] if val["questions"] else 0.0
        print_group("By Branch", grouped)
    if args.top:
        print(f"Top {args.top} Sessions")
        print("-" * (len(str(args.top)) + 13))
        for s in sorted(sessions, key=lambda x: x["cost"], reverse=True)[: args.top]:
            print(
                f"{s['id'][:8]} {s['date']} {s['branch'][:32]:32} "
                f"cost=${s['cost']:.2f} q={s['questions']:<3} q_cost=${s['question_cost']:.2f}"
            )


if __name__ == "__main__":
    main()
