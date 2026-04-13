#!/usr/bin/env python3
"""Transform extracted magic-era session cases into behavioral evals that test
whether the drupal-workflow plugin produces the same delegation patterns.

Usage:
    python3 replay-eval.py eval-cases.json --output eval/behavioral/workflow-patterns/evals.json
"""
import argparse
import json
import re
import sys
from pathlib import Path


def warn(msg):
    print(f"warning: {msg}", file=sys.stderr)


# Fix 6: Anti-patterns that indicate direct implementation instead of delegation
ANTI_PATTERNS = [
    "I'll do this myself",
    "Let me just edit",
    "simple change",
    "I'll quickly",
    "Let me directly",
    "I'll handle this without",
]


def classify_prompt(prompt, response):
    """Determine what workflow pattern a prompt+response represents."""
    pl = prompt.lower()
    patterns = set()

    if any(s in pl for s in ["sprint", "implement", "build", "create", "milestone",
                             "all tasks", "entity", "service", "module"]):
        patterns.add("delegation")
    if any(s in pl for s in ["plan", "how should", "brainstorm", "strategy", "approach"]):
        patterns.add("planning")
    if any(s in pl for s in ["verify", "test", "check", "fix", "debug", "failing",
                             "broken", "error", "drush"]):
        patterns.add("verification")
    if response.get("agents_dispatched"):
        patterns.add("delegation")

    for skill in response.get("skills_invoked", []):
        sl = skill.lower()
        if "bootstrap" in sl or "semantic" in sl:
            patterns.add("bootstrapping")
        elif "plan" in sl or "writing" in sl:
            patterns.add("planning")
        elif "verify" in sl or "test" in sl:
            patterns.add("verification")
        elif "subagent" in sl or "driven" in sl:
            patterns.add("delegation")

    return patterns or {"general"}


def build_must_contain(response, patterns):
    """Build must_contain_any based on observed behavior and patterns."""
    candidates = []
    for skill in response.get("skills_invoked", []):
        candidates.append(skill.split(":")[-1] if ":" in skill else skill)
    for at in response.get("agent_types", {}):
        candidates.append(at.split(":")[-1] if ":" in at else at)

    # Fix 6: Use tool-call oriented keywords instead of generic words
    kw = {"delegation": ["Agent", "subagent_type", "drupal-builder", "drupal-verifier", "dispatch"],
          "planning": ["TaskCreate", "steps", "## Plan", "approach", "phases"],
          "verification": ["drupal-verifier", "phpunit", "drush", "test", "Bash"],
          "bootstrapping": ["bootstrap", "semantic", "documentation", "index"]}
    for pat in patterns:
        candidates.extend(kw.get(pat, []))

    seen, result = set(), []
    for c in candidates:
        if c.lower() not in seen:
            seen.add(c.lower())
            result.append(c)
    return result


def build_must_not_contain(patterns):
    """Fix 6: Build must_not_contain list of anti-patterns."""
    result = list(ANTI_PATTERNS)
    return result


def build_structural_rules(patterns):
    """Fix 6: Build structural rules for plan-like prompts."""
    rules = []
    if "planning" in patterns:
        rules.append({
            "type": "check_markdown_structure",
            "description": "Planning response should have headings and numbered/bulleted steps",
            "require_headings": True,
            "require_list_items": 2,
        })
    if "delegation" in patterns:
        rules.append({
            "type": "check_tool_references",
            "description": "Delegation response should reference specific tool calls (Agent, TaskCreate)",
            "require_any": ["Agent", "TaskCreate", "subagent_type"],
        })
    return rules


def sanitize_prompt(prompt):
    cleaned = re.sub(r"/home/[^\s]+", "<PATH>", prompt)
    cleaned = re.sub(r"[─│┌┐└┘├┤┬┴┼❯]+", "", cleaned)
    lines = [l.strip() for l in cleaned.split("\n") if len(l) < 500]
    while lines and not lines[0]:
        lines.pop(0)
    return "\n".join(lines).strip()[:500]


def generate_eval_case(case, eval_id):
    prompt = case["prompt"]
    response = case["observed_response"]
    patterns = classify_prompt(prompt, response)
    agent_count = len(response.get("agents_dispatched", []))
    skill_count = len(response.get("skills_invoked", []))
    task_tracking = response.get("task_tracking", False)

    teaching_parts = []
    if "delegation" in patterns:
        teaching_parts.append(f"Should delegate to specialized agents (observed: {agent_count} dispatches)")
    if "planning" in patterns:
        teaching_parts.append("Should plan before implementing")
    if "verification" in patterns:
        teaching_parts.append("Should verify with tests or drush")
    if "bootstrapping" in patterns:
        teaching_parts.append("Should bootstrap project context first")
    if task_tracking:
        teaching_parts.append("Should use task tracking")

    expectations = []
    if "delegation" in patterns:
        expectations.append(f"Dispatches specialized agents (original had {agent_count})")
    if skill_count > 0:
        expectations.append(f"Invokes relevant skills ({', '.join(response.get('skills_invoked', []))})")
    if task_tracking:
        expectations.append("Uses TaskCreate/TaskUpdate for tracking")
    if "planning" in patterns:
        expectations.append("Plans approach before implementation")
    if "verification" in patterns:
        expectations.append("Includes verification step")

    # Fix 6: Append grounding instruction to prompt for delegation patterns
    sanitized = sanitize_prompt(prompt)
    if "delegation" in patterns:
        sanitized += "\n\nShow the tool calls you would make to accomplish this."

    return {
        "id": eval_id,
        "prompt": sanitized,
        "expected_output": "; ".join(teaching_parts) or "Follows structured workflow",
        "expectations": expectations,
        "must_contain_any": build_must_contain(response, patterns)[:8],
        # Fix 6: Add anti-pattern detection
        "must_not_contain": build_must_not_contain(patterns),
        # Fix 6: Add structural rules for behavioral assertions
        "structural_rules": build_structural_rules(patterns),
        "source": {
            "session_id": case["session_id"], "date": case["date"],
            "prompt_index": case["prompt_index"], "patterns": sorted(patterns),
        },
    }


def main():
    ap = argparse.ArgumentParser(
        description="Transform extracted session cases into behavioral evals."
    )
    ap.add_argument("input", help="JSON file from extract-prompts.py")
    ap.add_argument("--output", default=None, help="Output evals.json file (default: stdout)")
    ap.add_argument("--skill-name", default="workflow-patterns",
                    help="Skill name for the eval suite (default: workflow-patterns)")
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    cases = json.loads(input_path.read_text())
    if not isinstance(cases, list):
        print("error: input must be a JSON array of cases", file=sys.stderr)
        sys.exit(1)

    eval_cases = []
    for i, case in enumerate(cases, 1):
        try:
            eval_cases.append(generate_eval_case(case, i))
        except Exception as exc:
            warn(f"case {i}: {exc}")

    evals_doc = {
        "skill_name": args.skill_name,
        "skill_file": f"skills/{args.skill_name}/SKILL.md",
        "description": (
            "Behavioral evals extracted from magic-era sessions (2026-03-29 to 2026-03-31). "
            "Tests whether the drupal-workflow plugin reproduces the structured delegation "
            "pattern: brainstorm -> plan -> delegate -> track -> verify."
        ),
        "evals": eval_cases,
    }

    output = json.dumps(evals_doc, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n")
        print(f"Wrote {len(eval_cases)} eval cases to {args.output}", file=sys.stderr)
    else:
        print(output)

    pattern_counts = {}
    for ec in eval_cases:
        for pat in ec.get("source", {}).get("patterns", []):
            pattern_counts[pat] = pattern_counts.get(pat, 0) + 1
    print(f"\nSummary: {len(eval_cases)} evals generated", file=sys.stderr)
    for pat, count in sorted(pattern_counts.items(), key=lambda x: -x[1]):
        print(f"  {pat}: {count}", file=sys.stderr)


if __name__ == "__main__":
    main()
