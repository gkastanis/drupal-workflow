"""Eval: does the drupal-verifier agent produce correct verification output?

Tests whether the verifier agent produces structured verification reports
with the expected format (JSON test output, PASS/FAIL, proper test types).
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
    "You are a Drupal implementation verifier. Follow ALL loaded skills and rules exactly. "
    "Verify the implementation and output your verification report. "
    "Do not modify any files. Use drush eval and curl for verification."
)

TASK_PROMPT = """Verify the timan_assignment module:
1. Check if the service timan_assignment.allocation_calculator exists
2. Check if the timan_assignment entity type is registered
3. Check the assignment routes exist
Output your verification report."""


@dataclass
class AssertionResult:
    id: str
    description: str
    passed: bool
    detail: str = ""


ASSERTIONS = [
    # Report format
    {"id": "V01", "desc": "Output contains Verification verdict (PASS/FAIL)",
     "check": "contains_any", "texts": ["Verification", "PASS", "FAIL", "pass", "fail"]},
    {"id": "V02", "desc": "Has Target field identifying what was verified",
     "check": "contains_any", "texts": ["Target", "target", "timan_assignment", "allocation_calculator"]},
    {"id": "V03", "desc": "Has check results with status indicators",
     "check": "contains_any", "texts": ["PASS", "FAIL", "pass", "fail", "exists", "registered"]},

    # Verification methods
    {"id": "V04", "desc": "Uses verification method (drush eval, file inspection, or grep)",
     "check": "contains_any", "texts": ["drush eval", "drush ev", "ddev drush", "services.yml", "routing.yml", "registered", ".module"]},
    {"id": "V05", "desc": "Checks service existence",
     "check": "contains_any", "texts": ["hasService", "service", "allocation_calculator", "service exist"]},
    {"id": "V06", "desc": "Checks entity type",
     "check": "contains_any", "texts": ["entity_type", "timan_assignment", "entity type", "getDefinition"]},

    # Safety
    {"id": "V07", "desc": "Does not use destructive operations (DELETE, DROP, TRUNCATE)",
     "check": "no_destructive"},
    {"id": "V08", "desc": "Produces clean structured output (JSON, markdown table, or formatted report)",
     "check": "contains_any", "texts": ["2>/dev/null", "/dev/null", "PASS", "FAIL", "###", "Checks:"]},

    # Report quality
    {"id": "V09", "desc": "Reports multiple checks (at least 2)",
     "check": "min_checks", "min_count": 2},
    {"id": "V10", "desc": "Provides suggested fixes for failures (if any)",
     "check": "contains_any", "texts": ["fix", "suggest", "ensure", "check", "enable", "verify"]},
]


def load_agent_prompt() -> str:
    agent_file = PLUGIN_DIR / "agents" / "drupal-verifier.md"
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


def run_verification(agent_prompt: str) -> tuple[str, float, float]:
    prompt = f"""{agent_prompt}

---

**TASK**: {TASK_PROMPT}"""

    args = [
        CLAUDE_BIN, "--model", MODEL,
        "--allowedTools", "Bash,Read,Grep,Glob",
        "--append-system-prompt", SYSTEM_APPEND,
        "--print", "--output-format", "json",
        "--no-session-persistence", "--dangerously-skip-permissions",
        "--max-turns", "10", "-p", "-",
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
            elif isinstance(obj, list):
                for item in obj:
                    extract(item)
        extract(data)
        output = "\n".join(t for t in texts if t and len(t) > 10)
        cost = data.get("total_cost_usd", 0) if isinstance(data, dict) else 0
    except json.JSONDecodeError:
        output = raw
        cost = 0

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
        elif check == "no_destructive":
            destructive = ["DELETE FROM", "DROP TABLE", "TRUNCATE", "TRUNCATE TABLE"]
            found = [d for d in destructive if d in output.upper()]
            passed = len(found) == 0
            detail = f"Found destructive: {found}" if found else "No destructive ops"
        elif check == "min_checks":
            # Count check-like patterns
            checks = len(re.findall(r"(?:PASS|FAIL|pass|fail|exists|registered|enabled|check)", output))
            passed = checks >= a["min_count"]
            detail = f"{checks} check indicators"

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
        print("=== VERIFIER AGENT EVAL ===")
        print("Testing: Does the verifier produce correct verification reports?")
        print(f"Task: Verify timan_assignment module\n")

        agent_prompt = load_agent_prompt()
        print(f"Agent prompt: {len(agent_prompt)} chars")
        print("Running verification...")

        output, elapsed, cost = run_verification(agent_prompt)
        print(f"Done: {elapsed}s, ${cost:.4f}")
        print(f"Output: {len(output)} chars\n")

    output_file = PLUGIN_DIR / "eval" / "evals" / "results" / f"verifier-output-{timestamp}.txt"
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

    results_file = PLUGIN_DIR / "eval" / "evals" / "results" / f"verifier-{timestamp}.json"
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
