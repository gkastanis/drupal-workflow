#!/usr/bin/env python3
"""Behavioral eval runner for drupal-workflow skills.

Ported from ai_best_practices/evals/run-evals.py. Adapted paths to the
drupal-workflow plugin layout:
  - Skills:  skills/<name>/SKILL.md
  - Evals:   eval/behavioral/<skill-name>/evals.json
  - Static:  eval/behavioral/<skill-name>/static-checks.json

Two modes:
  python3 eval/run-behavioral.py --static                          # structural checks only
  python3 eval/run-behavioral.py --behavioral --skill SKILL_NAME   # live AI checks via claude -p

List available evals:
  python3 eval/run-behavioral.py --list

Trace logging (behavioral mode):
  python3 eval/run-behavioral.py --behavioral --skill SKILL_NAME --output-dir ./traces

  Saves one JSON file per case with the full prompt, raw response, assertions,
  and pass/fail result. Reviewable without re-running.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BEHAVIORAL_DIR = REPO_ROOT / "eval" / "behavioral"
SKILLS_DIR = REPO_ROOT / "skills"


def load_evals(skill_name: str) -> dict:
    path = BEHAVIORAL_DIR / skill_name / "evals.json"
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def load_static_checks(skill_name: str) -> dict | None:
    path = BEHAVIORAL_DIR / skill_name / "static-checks.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def read_skill(skill_file: str) -> str:
    """Read a skill file. Accepts relative path from REPO_ROOT or bare skill name."""
    # If it looks like a path, resolve from REPO_ROOT.
    path = REPO_ROOT / skill_file
    if path.exists():
        with open(path) as f:
            return f.read()
    # Try as a skill name: skills/<name>/SKILL.md
    skill_path = SKILLS_DIR / skill_file / "SKILL.md"
    if skill_path.exists():
        with open(skill_path) as f:
            return f.read()
    return ""


# ---------------------------------------------------------------------------
# PHP lint check on generated code blocks
# ---------------------------------------------------------------------------

def check_php_lint(response: str) -> tuple[bool, str]:
    """Extract PHP code blocks from response and run php -l on them."""
    php_blocks = re.findall(r"```php[^\n]*\n(.*?)```", response, re.DOTALL)
    if not php_blocks:
        return True, "No PHP code blocks to lint"

    errors = []
    for i, block in enumerate(php_blocks):
        code = block if block.strip().startswith("<?php") else "<?php\n" + block
        try:
            proc = subprocess.run(
                ["php", "-l"],
                input=code, capture_output=True, text=True, timeout=10,
            )
            if proc.returncode != 0:
                errors.append(f"Block {i+1}: {proc.stdout.strip()}")
        except FileNotFoundError:
            return True, "php not available, skipping lint"
        except subprocess.TimeoutExpired:
            errors.append(f"Block {i+1}: lint timed out")

    if errors:
        return False, "; ".join(errors)
    return True, f"{len(php_blocks)} PHP block(s) pass syntax check"


def check_markdown_structure(response: str, rules: dict) -> tuple[bool, str]:
    """Check markdown structural quality. Deterministic, no LLM calls.

    Supported rules:
        min_headings (int): minimum number of markdown headings
        max_heading_level (int): deepest allowed heading (e.g. 4 = ####)
        required_sections (list[str]): heading texts that must appear (case-insensitive)
        forbidden_patterns (list[str]): literal strings that must not appear
        min_code_blocks (int): minimum fenced code blocks
        min_paragraphs (int): minimum non-empty paragraph lines
        no_h1 (bool): H1 (# ) is forbidden (docs should start at ##)
    """
    errors = []

    # Parse headings: lines starting with one or more #.
    headings = []
    for line in response.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+)", line)
        if m:
            headings.append((len(m.group(1)), m.group(2).strip()))

    # min_headings
    min_h = rules.get("min_headings", 0)
    if min_h and len(headings) < min_h:
        errors.append(f"headings: {len(headings)} < {min_h} required")

    # max_heading_level
    max_level = rules.get("max_heading_level", 6)
    deep = [f"{'#'*lvl} {txt}" for lvl, txt in headings if lvl > max_level]
    if deep:
        errors.append(f"heading too deep: {deep[0]}")

    # no_h1
    if rules.get("no_h1", False):
        h1s = [txt for lvl, txt in headings if lvl == 1]
        if h1s:
            errors.append(f"H1 found (use ## or deeper): {h1s[0]}")

    # required_sections
    heading_texts_lower = [txt.lower() for _, txt in headings]
    for section in rules.get("required_sections", []):
        if not any(section.lower() in ht for ht in heading_texts_lower):
            errors.append(f"missing section: {section}")

    # forbidden_patterns
    for pat in rules.get("forbidden_patterns", []):
        if pat in response:
            errors.append(f"forbidden pattern found: {pat!r}")

    # min_code_blocks
    code_blocks = re.findall(r"```", response)
    n_blocks = len(code_blocks) // 2
    min_cb = rules.get("min_code_blocks", 0)
    if min_cb and n_blocks < min_cb:
        errors.append(f"code blocks: {n_blocks} < {min_cb} required")

    # min_paragraphs
    min_para = rules.get("min_paragraphs", 0)
    if min_para:
        para_count = sum(
            1 for line in response.splitlines()
            if line.strip() and not line.startswith("#") and not line.startswith("```")
        )
        if para_count < min_para:
            errors.append(f"paragraphs: {para_count} < {min_para} required")

    if errors:
        return False, "; ".join(errors)

    parts = []
    if headings:
        parts.append(f"{len(headings)} headings")
    if n_blocks:
        parts.append(f"{n_blocks} code blocks")
    return True, ", ".join(parts) if parts else "OK"


# ---------------------------------------------------------------------------
# Static assertions
# ---------------------------------------------------------------------------

def run_static(static: dict) -> list[tuple[str, str, bool, str]]:
    results = []
    skill_file = static.get("skill_file", "")
    content = read_skill(skill_file) if skill_file else ""

    for a in static.get("assertions", []):
        aid = a["id"]
        desc = a["description"]
        check = a["check"]

        if check == "file_exists":
            target = REPO_ROOT / a["path"]
            passed = target.exists()
            detail = f"{'exists' if passed else 'missing'}: {a['path']}"

        elif check == "frontmatter_fields":
            fm_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
            if not fm_match:
                passed = False
                detail = "No YAML frontmatter found"
            else:
                fm = fm_match.group(1)
                missing = [f for f in a["fields"] if f + ":" not in fm]
                passed = len(missing) == 0
                detail = f"Missing: {missing}" if missing else "All fields present"

        elif check == "contains":
            passed = a["text"] in content
            detail = f"Found '{a['text']}'" if passed else f"'{a['text']}' not found"

        elif check == "order":
            first_pos = content.find(a["first"])
            second_pos = content.find(a["second"])
            if first_pos == -1 or second_pos == -1:
                passed = False
                detail = f"'{a['first']}' at {first_pos}, '{a['second']}' at {second_pos}"
            else:
                passed = first_pos < second_pos
                detail = (
                    f"'{a['first']}' at line {content[:first_pos].count(chr(10))+1}, "
                    f"'{a['second']}' at line {content[:second_pos].count(chr(10))+1}"
                )

        elif check == "max_lines":
            lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            passed = lines <= a["limit"]
            detail = f"{lines} lines (limit: {a['limit']})"

        else:
            passed = False
            detail = f"Unknown check type: {check}"

        results.append((aid, desc, passed, detail))

    return results


# ---------------------------------------------------------------------------
# Behavioral assertions
# ---------------------------------------------------------------------------

def run_behavioral(
    evals: dict,
    output_dir: str | None = None,
) -> list[tuple[str, str, bool, str]]:
    results = []
    skill_file = evals.get("skill_file", f"skills/{evals.get('skill_name', 'unknown')}/SKILL.md")
    skill_content = read_skill(skill_file)
    if not skill_content:
        return [("--", "Skill file missing", False, f"{skill_file} not found or empty")]

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Support both agentskills.io ("evals") and legacy ("behavioral_cases") key.
    cases = evals.get("evals", evals.get("behavioral_cases", []))
    for case in cases:
        cid = f"B{case['id']:02d}" if isinstance(case["id"], int) else case["id"]
        prompt = case["prompt"]
        teaching = case.get("expected_output", case.get("teaching", ""))

        full_prompt = f"{skill_content}\n\n---\n\n{prompt}"

        try:
            proc = subprocess.run(
                ["claude", "-p", "-", "--no-session-persistence", "--permission-mode", "auto",
                 "--setting-sources", "", "--strict-mcp-config"],
                input=full_prompt,
                capture_output=True, text=True, timeout=120,
            )
            response = proc.stdout.strip()
        except FileNotFoundError:
            results.append((cid, teaching, False, "claude CLI not found"))
            continue
        except subprocess.TimeoutExpired:
            results.append((cid, teaching, False, "Timed out after 120s"))
            continue

        if proc.returncode != 0:
            err = proc.stderr.strip()[:200] if proc.stderr else "no details"
            results.append((cid, teaching, False, f"claude exited {proc.returncode}: {err}"))
            continue

        if not response:
            results.append((cid, teaching, False, "Empty response"))
            continue

        response_lower = response.lower()

        # Check must_contain_any.
        must_any = case.get("must_contain_any", [])
        found_any = [t for t in must_any if t.lower() in response_lower]
        any_pass = len(found_any) > 0 if must_any else True

        # Check must_not_contain.
        must_not = case.get("must_not_contain", [])
        found_bad = [t for t in must_not if t.lower() in response_lower]
        not_pass = len(found_bad) == 0

        # Check php_lint if requested.
        lint_pass = True
        lint_detail = ""
        if case.get("check_php_lint", False):
            lint_pass, lint_detail = check_php_lint(response)

        # Check markdown structure if requested.
        md_pass = True
        md_detail = ""
        if case.get("check_markdown_structure"):
            md_pass, md_detail = check_markdown_structure(
                response, case["check_markdown_structure"],
            )

        passed = any_pass and not_pass and lint_pass and md_pass

        detail_parts = []
        if must_any:
            detail_parts.append(f"found: {found_any}" if found_any else f"missing all of: {must_any}")
        if found_bad:
            detail_parts.append(f"unwanted: {found_bad}")
        if lint_detail:
            detail_parts.append(f"php-lint: {lint_detail}")
        if md_detail:
            detail_parts.append(f"markdown: {md_detail}")
        detail = "; ".join(detail_parts) if detail_parts else "OK"

        results.append((cid, teaching, passed, detail))

        # Save trace for offline review.
        if output_dir:
            trace = {
                "id": cid,
                "teaching": teaching,
                "prompt": prompt,
                "response": response,
                "assertions": {
                    "must_contain_any": must_any,
                    "found": found_any,
                    "must_not_contain": must_not,
                    "found_bad": found_bad,
                    "php_lint": lint_detail if case.get("check_php_lint") else None,
                    "markdown_structure": md_detail if case.get("check_markdown_structure") else None,
                },
                "passed": passed,
                "detail": detail,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            trace_path = os.path.join(output_dir, f"{cid}.json")
            with open(trace_path, "w") as f:
                json.dump(trace, f, indent=2)

    return results


# ---------------------------------------------------------------------------
# List available evals
# ---------------------------------------------------------------------------

def list_evals() -> None:
    """List all available behavioral eval directories."""
    if not BEHAVIORAL_DIR.exists():
        print(f"No behavioral eval directory found at {BEHAVIORAL_DIR}")
        print("Create eval/behavioral/<skill-name>/evals.json to get started.")
        return

    found = []
    for d in sorted(BEHAVIORAL_DIR.iterdir()):
        if not d.is_dir():
            continue
        has_evals = (d / "evals.json").exists()
        has_static = (d / "static-checks.json").exists()
        if has_evals or has_static:
            parts = []
            if has_evals:
                with open(d / "evals.json") as f:
                    data = json.load(f)
                cases = data.get("evals", data.get("behavioral_cases", []))
                parts.append(f"{len(cases)} behavioral")
            if has_static:
                with open(d / "static-checks.json") as f:
                    data = json.load(f)
                assertions = data.get("assertions", [])
                parts.append(f"{len(assertions)} static")
            found.append((d.name, ", ".join(parts)))

    if not found:
        print(f"No eval suites found in {BEHAVIORAL_DIR}")
        print("Create eval/behavioral/<skill-name>/evals.json to get started.")
        return

    print(f"Available behavioral evals ({len(found)} skill(s)):\n")
    for name, counts in found:
        print(f"  {name:<35} {counts}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def print_results(results: list[tuple[str, str, bool, str]]) -> int:
    failures = 0
    for aid, desc, passed, detail in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            failures += 1
        print(f"  [{status}] {aid}: {desc}")
        print(f"         {detail}")
    return failures


def main():
    parser = argparse.ArgumentParser(description="Behavioral eval runner for drupal-workflow skills")
    parser.add_argument("--static", action="store_true", help="Run static structural assertions")
    parser.add_argument("--behavioral", action="store_true", help="Run behavioral test cases (requires claude CLI)")
    parser.add_argument("--skill", default=None, help="Skill name to evaluate (default: all)")
    parser.add_argument("--output-dir", default=None, help="Save behavioral traces as JSON to this directory")
    parser.add_argument("--list", action="store_true", help="List all available behavioral eval directories")
    args = parser.parse_args()

    if args.list:
        list_evals()
        return

    if not args.static and not args.behavioral:
        args.static = True

    if args.skill:
        skills = [args.skill]
    else:
        if not BEHAVIORAL_DIR.exists():
            print(f"No behavioral eval directory at {BEHAVIORAL_DIR}")
            sys.exit(1)
        skills = [
            d.name for d in BEHAVIORAL_DIR.iterdir()
            if d.is_dir() and ((d / "evals.json").exists() or (d / "static-checks.json").exists())
        ]

    total_failures = 0

    for skill_name in sorted(skills):
        print(f"\n=== {skill_name} ===\n")

        if args.static:
            static = load_static_checks(skill_name)
            if static:
                print("Static assertions:")
                results = run_static(static)
                total_failures += print_results(results)
                passed = sum(1 for _, _, p, _ in results if p)
                print(f"\n  Score: {passed}/{len(results)}")
            else:
                print("No static-checks.json found, skipping static assertions.")

        if args.behavioral:
            evals = load_evals(skill_name)
            trace_dir = None
            if args.output_dir:
                trace_dir = os.path.join(args.output_dir, skill_name)
            print("\nBehavioral cases:")
            results = run_behavioral(evals, output_dir=trace_dir)
            total_failures += print_results(results)
            passed = sum(1 for _, _, p, _ in results if p)
            print(f"\n  Score: {passed}/{len(results)}")
            if trace_dir:
                print(f"  Traces saved to: {trace_dir}")

    print()
    sys.exit(1 if total_failures > 0 else 0)


if __name__ == "__main__":
    main()
