#!/usr/bin/env python3
"""A/B comparison of skill effectiveness for drupal-workflow.

Ported from ai_best_practices/evals/compare.py. Adapted paths to the
drupal-workflow plugin layout:
  - Skills:  skills/<name>/SKILL.md
  - Evals:   eval/behavioral/<skill-name>/evals.json
  - Results:  eval/behavioral/<skill-name>/comparison-*.json

Two modes:
  1. Editing a skill (default): compares the old version against your changes.
     Save the old version first, then edit the skill file and run compare.
  2. Proving a skill helps: compares no-skill baseline against the skill.
     Use --no-baseline to run this mode.

Both configs use identical flags -- the only variable is which skill content
is prepended to the prompt. The --setting-sources "" flag ensures no user
settings, plugins, or CLAUDE.md files contaminate the run.

Usage:
    # Editing workflow: compare old version vs your changes
    cp skills/drupal-testing/SKILL.md /tmp/old-skill.md
    # ... edit skills/drupal-testing/SKILL.md ...
    python3 eval/compare.py --skill drupal-testing --baseline /tmp/old-skill.md --runs 3

    # Proving a skill helps: no-skill baseline vs skill
    python3 eval/compare.py --skill drupal-testing --no-baseline --runs 3

    # Test on a different model
    python3 eval/compare.py --skill drupal-testing --no-baseline --model haiku

    # Compare multiple models in one run
    python3 eval/compare.py --skill drupal-testing --no-baseline --models sonnet haiku --runs 3

    # Run against a different provider
    python3 eval/compare.py --skill drupal-testing --no-baseline --provider codex --runs 1

    # Provider-specific model selection
    python3 eval/compare.py --skill drupal-testing --no-baseline --provider gemini --model gemini-2.5-flash

    # Dry run
    python3 eval/compare.py --skill drupal-testing --dry-run
"""

from __future__ import annotations

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

PROVIDER_DEFAULTS = {
    "claude": "sonnet",
    "codex": "gpt-5.4",
    "gemini": "gemini-2.5-pro",
    "mistral": "codestral-latest",
}

MODEL_PRICING = {
    "gpt-5.4": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.15, 0.60),
    "devstral-2": (0.40, 2.00),
    "codestral-latest": (0.30, 0.90),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Conservative cost estimate. Cache tokens are charged at full input rate.

    Claude reports its own cost via total_cost_usd, so this is only used
    for providers that don't report cost natively (Codex, Gemini, Mistral).
    """
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return 0.0
    return round((input_tokens * pricing[0] + output_tokens * pricing[1]) / 1_000_000, 6)


def load_evals(skill_name: str) -> list[dict]:
    path = BEHAVIORAL_DIR / skill_name / "evals.json"
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        data = json.load(f)
    return data.get("evals", [])


def load_skill(skill_name: str) -> str:
    """Load a skill file. Tries skills/<name>/SKILL.md."""
    skill_file = SKILLS_DIR / skill_name / "SKILL.md"
    if skill_file.exists():
        with open(skill_file) as f:
            return f.read()
    print(f"Error: skill not found at {skill_file}", file=sys.stderr)
    sys.exit(1)


def clean_env() -> dict:
    """Strip Claude Code nesting variables."""
    env = {**os.environ}
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    return env


def _default_result() -> dict:
    return {
        "response": "",
        "elapsed": 0.0,
        "exit_code": -1,
        "input_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
    }


def run_claude(prompt: str, model: str, cwd: str | None = None) -> dict:
    """Run claude -p with JSON output and return parsed result."""
    start = time.monotonic()
    result = _default_result()
    try:
        proc = subprocess.run(
            [
                "claude", "-p", "-",
                "--model", model,
                "--no-session-persistence",
                "--permission-mode", "auto",
                "--output-format", "json",
                "--setting-sources", "",
                "--strict-mcp-config",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=180,
            env=clean_env(),
            cwd=cwd or str(REPO_ROOT),
        )
        result["elapsed"] = round(time.monotonic() - start, 1)
        result["exit_code"] = proc.returncode
        raw = proc.stdout.strip()

        try:
            data = json.loads(raw)
            # --output-format json may return a list or a single object.
            if isinstance(data, list):
                result_obj = next(
                    (item for item in data
                     if isinstance(item, dict) and item.get("type") == "result"),
                    {},
                )
            else:
                result_obj = data
            result["response"] = result_obj.get("result", "")
            result["cost_usd"] = result_obj.get("total_cost_usd", 0) or 0
            usage = result_obj.get("usage", {})
            result["input_tokens"] = usage.get("input_tokens", 0) or 0
            result["cache_creation_tokens"] = usage.get("cache_creation_input_tokens", 0) or 0
            result["cache_read_tokens"] = usage.get("cache_read_input_tokens", 0) or 0
            result["output_tokens"] = usage.get("output_tokens", 0) or 0
        except json.JSONDecodeError:
            result["response"] = raw

    except FileNotFoundError:
        return result
    except subprocess.TimeoutExpired:
        result["elapsed"] = round(time.monotonic() - start, 1)

    return result


def run_codex(prompt: str, model: str, cwd: str | None = None) -> dict:
    start = time.monotonic()
    result = _default_result()
    try:
        proc = subprocess.run(
            [
                "codex", "exec", "--json",
                "--full-auto",
                "-m", model,
                "-",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=300,
            env=clean_env(),
            cwd=cwd or str(REPO_ROOT),
        )
        result["elapsed"] = round(time.monotonic() - start, 1)
        result["exit_code"] = proc.returncode

        messages = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            item = event.get("item", {})
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str) and text:
                    messages.append(text)

            if event.get("type") == "turn.completed":
                usage = event.get("usage", {}) or {}
                result["input_tokens"] = usage.get("input_tokens", 0) or 0
                result["cache_creation_tokens"] = usage.get("cache_creation_input_tokens", 0) or 0
                result["cache_read_tokens"] = usage.get("cached_input_tokens", 0) or 0
                result["output_tokens"] = usage.get("output_tokens", 0) or 0

        result["response"] = "\n\n".join(messages)
        if proc.returncode == 0 and not messages:
            print("  WARNING: codex exited 0 but no agent_message found in NDJSON",
                  file=sys.stderr)
        result["cost_usd"] = estimate_cost(
            model,
            result["input_tokens"] + result["cache_creation_tokens"] + result["cache_read_tokens"],
            result["output_tokens"],
        )
    except FileNotFoundError:
        return result
    except subprocess.TimeoutExpired:
        result["elapsed"] = round(time.monotonic() - start, 1)

    return result


def run_gemini(prompt: str, model: str, cwd: str | None = None) -> dict:
    start = time.monotonic()
    result = _default_result()
    try:
        proc = subprocess.run(
            [
                "gemini",
                "--output-format", "json",
                "--model", model,
                "--approval-mode", "yolo",
                "-p", "-",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=180,
            env=clean_env(),
            cwd=cwd or str(REPO_ROOT),
        )
        result["elapsed"] = round(time.monotonic() - start, 1)
        result["exit_code"] = proc.returncode
        raw = proc.stdout.strip()

        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            result["response"] = raw
            return result

        result["response"] = data.get("response", "") or ""
        stats_models = ((data.get("stats") or {}).get("models") or {})
        for stats in stats_models.values():
            tokens = (stats or {}).get("tokens", {}) or {}
            result["input_tokens"] += tokens.get("input", 0) or 0
            result["output_tokens"] += tokens.get("candidates", 0) or 0
            result["cache_read_tokens"] += tokens.get("cached", 0) or 0

        result["cost_usd"] = estimate_cost(
            model,
            result["input_tokens"] + result["cache_read_tokens"],
            result["output_tokens"],
        )
    except FileNotFoundError:
        return result
    except subprocess.TimeoutExpired:
        result["elapsed"] = round(time.monotonic() - start, 1)

    return result


def run_mistral(prompt: str, model: str, cwd: str | None = None) -> dict:
    """Call the Mistral/Codestral API directly via urllib. No CLI dependency.

    Uses MISTRAL_API_KEY or CODESTRAL_API_KEY env var.
    Default endpoint: https://codestral.mistral.ai/v1/chat/completions
    Override with MISTRAL_API_BASE env var.
    """
    import urllib.request
    import urllib.error
    start = time.monotonic()
    result = _default_result()
    api_key = os.environ.get("CODESTRAL_API_KEY") or os.environ.get("MISTRAL_API_KEY", "")
    api_base = os.environ.get("MISTRAL_API_BASE", "https://codestral.mistral.ai/v1")
    if not api_key:
        result["response"] = "[error: set CODESTRAL_API_KEY or MISTRAL_API_KEY]"
        print("  WARNING: no Mistral API key found", file=sys.stderr)
        return result
    try:
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }).encode()
        req = urllib.request.Request(
            f"{api_base}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
        result["elapsed"] = round(time.monotonic() - start, 1)
        result["exit_code"] = 0

        choices = data.get("choices", [])
        if choices:
            result["response"] = choices[0].get("message", {}).get("content", "")

        usage = data.get("usage", {})
        result["input_tokens"] = usage.get("prompt_tokens", 0) or 0
        result["output_tokens"] = usage.get("completion_tokens", 0) or 0
        result["cost_usd"] = estimate_cost(model, result["input_tokens"], result["output_tokens"])
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        result["elapsed"] = round(time.monotonic() - start, 1)
        result["response"] = f"[API error: {type(e).__name__}]"
    except TimeoutError:
        result["elapsed"] = round(time.monotonic() - start, 1)

    return result


PROVIDERS = {
    "claude": run_claude,
    "codex": run_codex,
    "gemini": run_gemini,
    "mistral": run_mistral,
}


def check_php_lint(response: str) -> tuple[bool, str]:
    """Extract PHP code blocks and run php -l."""
    blocks = re.findall(r"```php[^\n]*\n(.*?)```", response, re.DOTALL)
    if not blocks:
        return True, "no PHP blocks"

    errors = []
    for i, block in enumerate(blocks):
        code = block if block.strip().startswith("<?php") else "<?php\n" + block
        try:
            proc = subprocess.run(
                ["php", "-l"], input=code,
                capture_output=True, text=True, timeout=10,
            )
            if proc.returncode != 0:
                errors.append(f"block {i+1}: {proc.stdout.strip()}")
        except FileNotFoundError:
            return True, "php not found -- lint skipped"
        except subprocess.TimeoutExpired:
            errors.append(f"block {i+1}: lint timed out")

    if errors:
        return False, "; ".join(errors)
    return True, f"{len(blocks)} block(s) OK"


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


def grade_case(response: str, case: dict) -> dict:
    """Grade a response against a case's assertions."""
    response_lower = response.lower()

    must_any = case.get("must_contain_any", [])
    found_any = [t for t in must_any if t.lower() in response_lower]
    any_pass = len(found_any) > 0 if must_any else True

    must_not = case.get("must_not_contain", [])
    found_bad = [t for t in must_not if t.lower() in response_lower]
    not_pass = len(found_bad) == 0

    lint_pass, lint_detail = True, ""
    if case.get("check_php_lint", False):
        lint_pass, lint_detail = check_php_lint(response)

    md_pass, md_detail = True, ""
    if case.get("check_markdown_structure"):
        md_pass, md_detail = check_markdown_structure(
            response, case["check_markdown_structure"],
        )

    passed = any_pass and not_pass and lint_pass and md_pass

    return {
        "passed": passed,
        "must_contain_any": {"required": must_any, "found": found_any, "pass": any_pass},
        "must_not_contain": {"forbidden": must_not, "found": found_bad, "pass": not_pass},
        "php_lint": {"pass": lint_pass, "detail": lint_detail},
        "markdown_structure": {"pass": md_pass, "detail": md_detail},
    }


def run_config(cases: list[dict], skill_content: str | None,
               model: str, provider: str, config_name: str, run_id: int,
               output_dir: Path | None = None,
               cwd: str | None = None) -> list[dict]:
    """Run all cases for one config, one run."""
    results = []

    for case in cases:
        cid = f"B{case['id']:02d}" if isinstance(case["id"], int) else case["id"]
        prompt = case["prompt"]

        if skill_content:
            full_prompt = f"{skill_content}\n\n---\n\n{prompt}"
        else:
            full_prompt = prompt

        result = PROVIDERS[provider](full_prompt, model, cwd=cwd)
        response = result["response"]

        if result["exit_code"] != 0 or not response:
            grade = {"passed": False, "error": f"exit={result['exit_code']}, empty={not response}"}
        else:
            grade = grade_case(response, case)

        case_result = {
            "case_id": cid,
            "config": config_name,
            "run": run_id,
            "passed": grade.get("passed", False),
            "elapsed": result["elapsed"],
            "grade": grade,
            "response_chars": len(response),
            "input_tokens": result["input_tokens"],
            "cache_creation_tokens": result["cache_creation_tokens"],
            "cache_read_tokens": result["cache_read_tokens"],
            "output_tokens": result["output_tokens"],
            "cost_usd": result["cost_usd"],
        }
        results.append(case_result)

        status = "PASS" if case_result["passed"] else "FAIL"
        cost_str = f"${case_result['cost_usd']:.4f}" if case_result["cost_usd"] else "$?.????"
        cache_str = ""
        if case_result["cache_read_tokens"]:
            cache_str = f", cache:{case_result['cache_read_tokens']}"
        tokens_str = f"{case_result['input_tokens']}in/{case_result['output_tokens']}out{cache_str}"
        print(f"  [{status}] {config_name}/run{run_id}/{cid} ({result['elapsed']}s, {tokens_str}, {cost_str})")

        if output_dir:
            trace_dir = output_dir / config_name / f"run{run_id}"
            trace_dir.mkdir(parents=True, exist_ok=True)
            trace = {**case_result, "prompt": prompt, "response": response[:2000],
                 "response_truncated": len(response) > 2000}
            with open(trace_dir / f"{cid}.json", "w") as f:
                json.dump(trace, f, indent=2)

    return results


def compute_stats(results: list[dict], config_name: str, n_runs: int) -> dict:
    """Aggregate pass rates, tokens, and cost across runs."""
    case_ids = sorted(set(r["case_id"] for r in results))
    per_case = {}
    for cid in case_ids:
        case_results = [r for r in results if r["case_id"] == cid]
        passes = sum(1 for r in case_results if r["passed"])
        per_case[cid] = {
            "passes": passes,
            "runs": len(case_results),
            "pass_rate": passes / len(case_results) if case_results else 0,
        }

    total_passes = sum(1 for r in results if r["passed"])
    total_results = len(results)
    avg_elapsed = sum(r["elapsed"] for r in results) / total_results if total_results else 0
    total_input_tokens = sum(r.get("input_tokens", 0) for r in results)
    total_cache_creation = sum(r.get("cache_creation_tokens", 0) for r in results)
    total_cache_read = sum(r.get("cache_read_tokens", 0) for r in results)
    total_output_tokens = sum(r.get("output_tokens", 0) for r in results)
    total_cost = sum(r.get("cost_usd", 0) for r in results)

    return {
        "config": config_name,
        "n_runs": n_runs,
        "n_cases": len(case_ids),
        "total_results": total_results,
        "total_pass_rate": total_passes / total_results if total_results else 0,
        "total_passes": total_passes,
        "avg_elapsed": round(avg_elapsed, 1),
        "total_input_tokens": total_input_tokens,
        "total_cache_creation_tokens": total_cache_creation,
        "total_cache_read_tokens": total_cache_read,
        "total_output_tokens": total_output_tokens,
        "avg_input_tokens": round(total_input_tokens / total_results) if total_results else 0,
        "avg_output_tokens": round(total_output_tokens / total_results) if total_results else 0,
        "total_cost_usd": round(total_cost, 4),
        "avg_cost_usd": round(total_cost / total_results, 4) if total_results else 0,
        "per_case": per_case,
    }


def print_comparison(baseline_stats: dict, treatment_stats: dict,
                     skill_name: str, model: str):
    """Print the comparison table."""
    print(f"\n{'=' * 70}")
    print(f"  COMPARISON: {skill_name} | model: {model}")
    print(f"{'=' * 70}\n")

    case_ids = sorted(set(
        list(baseline_stats["per_case"].keys())
        + list(treatment_stats["per_case"].keys())
    ))

    b_label = baseline_stats["config"][:14]
    t_label = treatment_stats["config"][:14]

    print(f"{'Case':<8} {b_label:>14} {t_label:>14} {'Delta':>10}")
    print(f"{'-' * 8} {'-' * 14} {'-' * 14} {'-' * 10}")

    for cid in case_ids:
        b = baseline_stats["per_case"].get(cid, {})
        t = treatment_stats["per_case"].get(cid, {})
        b_rate = b.get("pass_rate", 0)
        t_rate = t.get("pass_rate", 0)
        delta = t_rate - b_rate
        delta_str = f"{delta:+.0%}" if delta != 0 else "="

        b_str = f"{b.get('passes', 0)}/{b.get('runs', 0)} ({b_rate:.0%})"
        t_str = f"{t.get('passes', 0)}/{t.get('runs', 0)} ({t_rate:.0%})"
        print(f"{cid:<8} {b_str:>14} {t_str:>14} {delta_str:>10}")

    b_total = baseline_stats["total_pass_rate"]
    t_total = treatment_stats["total_pass_rate"]
    total_delta = t_total - b_total

    print(f"{'-' * 8} {'-' * 14} {'-' * 14} {'-' * 10}")
    print(f"{'TOTAL':<8} {b_total:>13.0%}  {t_total:>13.0%}  {total_delta:>+9.0%}")
    print(f"{'Avg time':<8} {baseline_stats['avg_elapsed']:>12.1f}s  {treatment_stats['avg_elapsed']:>12.1f}s")
    print()

    print(f"  {'':>20} {b_label:>14} {t_label:>14} {'Delta':>10}")
    print(f"  {'Avg input tokens':>20} {baseline_stats['avg_input_tokens']:>14,} {treatment_stats['avg_input_tokens']:>14,} {treatment_stats['avg_input_tokens'] - baseline_stats['avg_input_tokens']:>+10,}")
    print(f"  {'Avg output tokens':>20} {baseline_stats['avg_output_tokens']:>14,} {treatment_stats['avg_output_tokens']:>14,} {treatment_stats['avg_output_tokens'] - baseline_stats['avg_output_tokens']:>+10,}")
    b_cache = baseline_stats.get("total_cache_read_tokens", 0)
    t_cache = treatment_stats.get("total_cache_read_tokens", 0)
    if b_cache or t_cache:
        print(f"  {'Cache read tokens':>20} {b_cache:>14,} {t_cache:>14,} {t_cache - b_cache:>+10,}")
    print(f"  {'Total cost':>20} ${baseline_stats['total_cost_usd']:>13.4f} ${treatment_stats['total_cost_usd']:>13.4f} ${treatment_stats['total_cost_usd'] - baseline_stats['total_cost_usd']:>+9.4f}")
    print(f"  {'Avg cost/question':>20} ${baseline_stats['avg_cost_usd']:>13.4f} ${treatment_stats['avg_cost_usd']:>13.4f} ${treatment_stats['avg_cost_usd'] - baseline_stats['avg_cost_usd']:>+9.4f}")
    print()


def print_cross_model_summary(all_model_results: dict, skill_name: str):
    """Print a cross-model summary table comparing all models."""
    print(f"\n{'=' * 70}")
    print(f"  CROSS-MODEL SUMMARY: {skill_name}")
    print(f"{'=' * 70}\n")

    print(f"{'Model':<10} {'Baseline':>10} {'Treatment':>10} {'Delta':>8} {'Avg In':>8} {'Avg Out':>9} {'Avg Cost':>10}")
    print(f"{'-' * 10} {'-' * 10} {'-' * 10} {'-' * 8} {'-' * 8} {'-' * 9} {'-' * 10}")

    for model, mr in all_model_results.items():
        b = mr["baseline"]
        t = mr["treatment"]
        delta = mr["delta"]
        delta_str = f"{delta:+.0%}" if delta != 0 else "="

        print(
            f"{model:<10}"
            f" {b['total_pass_rate']:>9.0%} "
            f" {t['total_pass_rate']:>9.0%} "
            f" {delta_str:>8}"
            f" {t['avg_input_tokens']:>7,}"
            f" {t['avg_output_tokens']:>9,}"
            f" ${t['avg_cost_usd']:>8.4f}"
        )

    print()

    benefiting = [m for m, mr in all_model_results.items() if mr["delta"] > 0]
    neutral = [m for m, mr in all_model_results.items() if mr["delta"] == 0]
    regressing = [m for m, mr in all_model_results.items() if mr["delta"] < 0]

    if benefiting:
        print(f"  Skill helps:    {', '.join(benefiting)}")
    if neutral:
        print(f"  No effect:      {', '.join(neutral)}")
    if regressing:
        print(f"  Skill hurts:    {', '.join(regressing)}")
    print()


def _git_baseline(skill_name: str) -> str | None:
    """Try to get the last committed version of the skill from git."""
    skill_path = f"skills/{skill_name}/SKILL.md"
    try:
        proc = subprocess.run(
            ["git", "show", f"HEAD:{skill_path}"],
            capture_output=True, text=True, timeout=5,
            cwd=str(REPO_ROOT),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def main():
    parser = argparse.ArgumentParser(
        description="A/B comparison of skill effectiveness",
    )
    parser.add_argument("--skill", required=True,
                        help="Skill name to compare (e.g., drupal-testing)")
    parser.add_argument("--baseline", default=None,
                        help="Path to old version of the skill file (for editing workflow)")
    parser.add_argument("--no-baseline", action="store_true",
                        help="Compare no-skill vs skill (for proving a skill helps)")
    parser.add_argument("--runs", type=int, default=1,
                        help="Runs per config (default: 1, recommend: 3)")
    parser.add_argument("--provider", choices=list(PROVIDERS.keys()), default="claude",
                        help="Provider CLI to use (default: claude)")
    parser.add_argument("--model", default=None,
                        help="Model to test (default depends on provider)")
    parser.add_argument("--models", nargs="+", default=None,
                        help="Multiple models to compare (e.g., --models sonnet haiku opus)")
    parser.add_argument("--output-dir", default=None,
                        help="Save traces to this directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would run")
    parser.add_argument("--cwd", default=None,
                        help="Working directory for provider CLI execution (default: repo root). "
                             "Use a temp dir to prevent the model from seeing eval files.")
    args = parser.parse_args()

    if args.models and args.model is not None:
        parser.error("--model and --models are mutually exclusive")
    if len(set(args.models or [])) != len(args.models or []):
        parser.error("--models contains duplicate model names")
    default_model = PROVIDER_DEFAULTS[args.provider]
    models = args.models if args.models else [args.model or default_model]

    cases = load_evals(args.skill)
    skill_content = load_skill(args.skill)
    output_dir = Path(args.output_dir) if args.output_dir else None

    # Determine baseline content.
    if args.no_baseline:
        # No-skill vs skill: proves the skill has value.
        baseline_content = None
        baseline_label = "no skill"
        treatment_label = "with skill"
    elif args.baseline:
        # Old version vs new version: measures editing impact.
        baseline_path = Path(args.baseline)
        if not baseline_path.exists():
            print(f"Error: baseline file not found: {baseline_path}", file=sys.stderr)
            sys.exit(1)
        with open(baseline_path) as f:
            baseline_content = f.read()
        baseline_label = f"old ({baseline_path.name})"
        treatment_label = "new (current)"
    else:
        # Default: use git to get the previous committed version.
        baseline_content = _git_baseline(args.skill)
        if baseline_content is None:
            print("No --baseline path provided and git baseline not available.")
            print("Use --baseline /path/to/old-skill.md or --no-baseline for no-skill comparison.")
            sys.exit(1)
        baseline_label = "old (git)"
        treatment_label = "new (working copy)"

    if args.dry_run:
        n_models = len(models)
        total = len(cases) * 2 * args.runs * n_models
        est_min = total * 30 / 60
        print(f"Would run {len(cases)} cases x 2 configs x {args.runs} runs x {n_models} model(s) = {total} invocations")
        print(f"Skill: {args.skill} | Provider: {args.provider} | Models: {', '.join(models)}")
        print(f"Comparison: {baseline_label} vs {treatment_label}")
        print(f"Estimated time: ~{est_min:.0f} min")
        print()
        for case in cases:
            cid = f"B{case['id']:02d}" if isinstance(case["id"], int) else case["id"]
            lint = " [php-l]" if case.get("check_php_lint") else ""
            print(f"  {cid}: {case['prompt'][:70]}...{lint}")
        return

    # Resolve working directory for provider CLI.
    run_cwd = args.cwd
    if run_cwd:
        run_cwd = str(Path(run_cwd).resolve())

    print(f"\nA/B Comparison: {args.skill}")
    print(f"Provider: {args.provider} | Models: {', '.join(models)} | Runs: {args.runs} | Cases: {len(cases)}")
    print(f"Comparison: {baseline_label} vs {treatment_label}")
    isolation_modes = {
        "claude": "--setting-sources '' (no user config loaded)",
        "codex": "--full-auto (autonomous mode)",
        "gemini": "--approval-mode yolo",
        "mistral": "direct API (no CLI config)",
    }
    print(f"Isolation: {isolation_modes.get(args.provider, 'unknown')}")
    print(f"CWD: {run_cwd or REPO_ROOT}\n")

    all_model_results = {}

    for model in models:
        if len(models) > 1:
            print(f"\n{'#' * 70}")
            print(f"  MODEL: {model}")
            print(f"{'#' * 70}")

        model_output_dir = output_dir / model if output_dir and len(models) > 1 else output_dir

        all_baseline = []
        all_treatment = []

        for run_id in range(1, args.runs + 1):
            print(f"\n--- Run {run_id}/{args.runs} ---\n")

            print(f"Config: {baseline_label}")
            all_baseline.extend(
                run_config(cases, baseline_content, model, args.provider,
                           "baseline", run_id, model_output_dir,
                           cwd=run_cwd))

            print(f"\nConfig: {treatment_label}")
            all_treatment.extend(
                run_config(cases, skill_content, model, args.provider,
                           "treatment", run_id, model_output_dir,
                           cwd=run_cwd))

        baseline_stats = compute_stats(all_baseline, baseline_label, args.runs)
        treatment_stats = compute_stats(all_treatment, treatment_label, args.runs)

        print_comparison(baseline_stats, treatment_stats, args.skill, model)

        all_model_results[model] = {
            "baseline": baseline_stats,
            "treatment": treatment_stats,
            "delta": round(
                treatment_stats["total_pass_rate"] - baseline_stats["total_pass_rate"], 4,
            ),
        }

    if len(models) > 1:
        print_cross_model_summary(all_model_results, args.skill)

    # Save results JSON to eval/behavioral/<skill-name>/.
    results_dir = BEHAVIORAL_DIR / args.skill
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    results_file = results_dir / f"comparison-{timestamp}.json"

    if len(models) == 1:
        # Single-model: backwards-compatible JSON format.
        model = models[0]
        mr = all_model_results[model]
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "skill": args.skill,
            "provider": args.provider,
            "model": model,
            "n_runs": args.runs,
            "comparison": f"{baseline_label} vs {treatment_label}",
            "isolation": "setting_sources_empty",
            "baseline": mr["baseline"],
            "treatment": mr["treatment"],
            "delta": mr["delta"],
        }
    else:
        # Multi-model: per-model results + summary.
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "skill": args.skill,
            "provider": args.provider,
            "models": models,
            "n_runs": args.runs,
            "comparison": f"{baseline_label} vs {treatment_label}",
            "isolation": "setting_sources_empty",
            "per_model": {
                m: {
                    "baseline": mr["baseline"],
                    "treatment": mr["treatment"],
                    "delta": mr["delta"],
                }
                for m, mr in all_model_results.items()
            },
            "summary": {
                m: {
                    "baseline_pass_rate": mr["baseline"]["total_pass_rate"],
                    "treatment_pass_rate": mr["treatment"]["total_pass_rate"],
                    "delta": mr["delta"],
                    "total_cost_usd": round(
                        mr["baseline"]["total_cost_usd"] + mr["treatment"]["total_cost_usd"], 4,
                    ),
                }
                for m, mr in all_model_results.items()
            },
        }

    with open(results_file, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Results saved to {results_file}")


if __name__ == "__main__":
    main()
