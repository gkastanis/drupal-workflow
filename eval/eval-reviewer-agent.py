"""Eval: does the drupal-reviewer agent produce correct review reports?

Tests whether the reviewer agent, given code with known issues,
catches them and produces a properly formatted PASS/FAIL report.
"""

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

CLAUDE_BIN = "claude"
PLUGIN_DIR = Path(__file__).resolve().parent.parent
MODEL = "sonnet"
TIMEOUT = 300
PROJECT_DIR = "/home/zorz/sites/timan"

SYSTEM_APPEND = (
    "You are a Drupal code reviewer. Follow ALL loaded skills and rules exactly. "
    "Review the code and output a report in the specified format. "
    "Do not write or modify any files."
)

# Code with intentional issues for the reviewer to catch
BAD_CODE = '''```php
<?php

namespace Drupal\\timan_core\\Service;

class ReportGenerator {

  private $entityTypeManager;

  public function __construct($entityTypeManager) {
    $this->entityTypeManager = $entityTypeManager;
  }

  public function generateReport($project_id) {
    $node = \\Drupal::entityTypeManager()->getStorage("node")->load($project_id);
    $query = \\Drupal::database()->query("SELECT * FROM {timan_assignment} WHERE project_id = $project_id");
    $results = $query->fetchAll();
    $output = [];
    foreach ($results as $result) {
      if ($result->status == "active") {
        $output[] = [
          "#markup" => "<div>" . $result->title . "</div>",
        ];
      }
    }
    return $output;
  }
}
```

This is a service class in the timan_core module. Review it.'''


@dataclass
class AssertionResult:
    id: str
    description: str
    passed: bool
    detail: str = ""


ASSERTIONS = [
    # Report format
    {"id": "R01", "desc": "Output contains REVIEW: or PASS/FAIL verdict",
     "check": "contains_any", "texts": ["REVIEW:", "## REVIEW", "PASS", "FAIL"]},
    {"id": "R02", "desc": "Report has severity levels (CRITICAL, HIGH, or MEDIUM)",
     "check": "contains_any", "texts": ["CRITICAL", "HIGH", "MEDIUM"]},
    {"id": "R03", "desc": "Report has Standards section or check",
     "check": "contains_any", "texts": ["Standards", "PHPCS", "coding standard", "standards"]},
    {"id": "R04", "desc": "Report has Security section or check",
     "check": "contains_any", "texts": ["Security", "security", "SQL injection", "XSS"]},

    # Issue detection
    {"id": "R05", "desc": "Catches missing declare(strict_types=1)",
     "check": "contains_any", "texts": ["strict_types", "declare(strict"]},
    {"id": "R06", "desc": "Catches \\Drupal:: static calls in service class",
     "check": "contains_any", "texts": ["\\Drupal::", "static call", "dependency injection", "DI"]},
    {"id": "R07", "desc": "Catches SQL injection vulnerability (raw query with variable)",
     "check": "contains_any", "texts": ["SQL injection", "sql injection", "raw query", "parameterized", "Entity API"]},
    {"id": "R08", "desc": "Catches XSS risk (unescaped output in #markup)",
     "check": "contains_any", "texts": ["XSS", "escape", "sanitize", "#markup", "Html::escape", "Xss::filter"]},
    {"id": "R09", "desc": "Catches non-final class",
     "check": "contains_any", "texts": ["final", "not final", "non-final", "should be final"]},
    {"id": "R10", "desc": "Catches missing interface / no type-hints",
     "check": "contains_any", "texts": ["interface", "type-hint", "type hint", "typed", "Interface"]},
    {"id": "R11", "desc": "Catches missing cache metadata on render array",
     "check": "contains_any", "texts": ["cache", "#cache", "cache metadata", "CacheableMetadata"]},
    {"id": "R12", "desc": "Catches entity access issue (raw SQL bypasses access or missing accessCheck)",
     "check": "contains_any", "texts": ["accessCheck", "access check", "access_check", "Entity API", "entityQuery", "getQuery", "entity query"]},

    # Report quality
    {"id": "R13", "desc": "Provides remediation steps or fix suggestions",
     "check": "contains_any", "texts": ["Remediation", "Fix", "fix", "should", "replace", "instead"]},
    {"id": "R14", "desc": "Report is FAIL (code has multiple issues)",
     "check": "contains_any", "texts": ["FAIL", "fail", "issues found", "Issues Found"]},
    {"id": "R15", "desc": "Report contains at least 4 distinct issues",
     "check": "min_issue_count", "min_count": 4},
]


def load_agent_prompt() -> str:
    agent_file = PLUGIN_DIR / "agents" / "drupal-reviewer.md"
    with open(agent_file) as f:
        content = f.read()
    parts = content.split("---", 2)
    if len(parts) >= 3:
        return parts[2].strip()
    return content


def clean_env() -> dict:
    env = {**os.environ}
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    env["DISABLE_PROMPT_CACHING_SONNET"] = "1"
    return env


def run_review(agent_prompt: str) -> tuple[str, float, float]:
    prompt = f"""{agent_prompt}

---

**TASK**: Review the following Drupal service code for security, coding standards, and architecture quality. Output your review report.

{BAD_CODE}"""

    args = [
        CLAUDE_BIN, "--model", MODEL,
        "--disallowedTools", "Write,Edit",
        "--append-system-prompt", SYSTEM_APPEND,
        "--print", "--output-format", "json",
        "--no-session-persistence", "--dangerously-skip-permissions",
        "--max-turns", "5", "-p", "-",
    ]

    start = time.monotonic()
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, cwd=PROJECT_DIR, env=clean_env())
    try:
        stdout, stderr = proc.communicate(input=prompt, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return "", TIMEOUT, 0

    elapsed = round(time.monotonic() - start, 1)
    raw = stdout.strip()

    # Extract text from JSON
    try:
        data = json.loads(raw)
        texts = []
        def extract(obj):
            if isinstance(obj, str):
                texts.append(obj)
            elif isinstance(obj, dict):
                for k in ["result", "text", "content"]:
                    if k in obj:
                        extract(obj[k])
                cost_val = obj.get("total_cost_usd", 0)
            elif isinstance(obj, list):
                for item in obj:
                    extract(item)
        extract(data)
        output = "\n".join(t for t in texts if t and len(t) > 20)
        cost = data.get("total_cost_usd", 0) if isinstance(data, dict) else 0
    except json.JSONDecodeError:
        output = raw
        cost = 0

    # Unescape
    output = output.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
    return output, elapsed, cost


def check_assertions(output: str) -> list[AssertionResult]:
    results = []
    output_lower = output.lower()

    for a in ASSERTIONS:
        aid = a["id"]
        desc = a["desc"]
        check = a["check"]
        passed = False
        detail = ""

        if check == "contains_any":
            found = [t for t in a["texts"] if t in output or t.lower() in output_lower]
            passed = len(found) > 0
            detail = f"Found: {found[:3]}" if passed else f"None of: {a['texts'][:3]}"
        elif check == "min_issue_count":
            # Count issue indicators
            indicators = re.findall(r"(?:CRITICAL|HIGH|MEDIUM|Issue|issue|\d+\.\s)", output)
            count = len(set(indicators))
            # Also count bullet points in Issues section
            bullets = len(re.findall(r"^[-*]\s", output, re.MULTILINE))
            total = max(count, bullets)
            passed = total >= a["min_count"]
            detail = f"{total} issues detected"

        results.append(AssertionResult(id=aid, description=desc, passed=passed, detail=detail))

    return results


def main():
    timestamp = time.strftime("%Y%m%d-%H%M%S")

    check_only = "--check-only" in sys.argv
    if check_only and len(sys.argv) > sys.argv.index("--check-only") + 1:
        filepath = sys.argv[sys.argv.index("--check-only") + 1]
        with open(filepath) as f:
            output = f.read()
        elapsed, cost = 0, 0
    else:
        print("=== REVIEWER AGENT EVAL ===")
        print("Testing: Does the reviewer catch known code issues?")
        print("Code: ReportGenerator with 8+ intentional issues\n")

        agent_prompt = load_agent_prompt()
        print(f"Agent prompt: {len(agent_prompt)} chars")
        print("Running review...")

        output, elapsed, cost = run_review(agent_prompt)
        print(f"Done: {elapsed}s, ${cost:.4f}")
        print(f"Output: {len(output)} chars\n")

    # Save output
    output_file = PLUGIN_DIR / "eval" / "evals" / "results" / f"reviewer-output-{timestamp}.txt"
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, "w") as f:
        f.write(output)

    assertions = check_assertions(output)
    pass_count = sum(1 for a in assertions if a.passed)
    total = len(assertions)

    print(f"SCORE: {pass_count}/{total}\n")
    for a in assertions:
        status = "PASS" if a.passed else "FAIL"
        print(f"  [{status}] {a.id}: {a.description}")
        if not a.passed:
            print(f"         {a.detail}")

    # Save results
    results_file = PLUGIN_DIR / "eval" / "evals" / "results" / f"reviewer-{timestamp}.json"
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": timestamp, "score": f"{pass_count}/{total}",
            "pass_count": pass_count, "total_count": total,
            "time_seconds": elapsed, "cost_usd": cost,
            "assertions": [asdict(a) for a in assertions],
        }, f, indent=2)

    print(f"\n  Results: {results_file}")
    return pass_count, total


if __name__ == "__main__":
    passed, total = main()
    sys.exit(0 if passed == total else 1)
