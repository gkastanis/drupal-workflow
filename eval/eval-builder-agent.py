"""Eval: does the drupal-builder agent actually apply its loaded skills?

Tests whether the builder agent, when given a coding task, produces output
that follows the rules from its loaded skills (drupal-rules, drupal-service-di,
drupal-coding-standards, etc).

Approach:
  1. Prompt the agent to generate a Drupal service class
  2. Parse the generated PHP from the response (--print mode, no file writes)
  3. Check against skill-derived assertions
  4. Report which skills were effectively applied

Usage:
  python3 eval/eval-builder-agent.py
  python3 eval/eval-builder-agent.py --check-only /path/to/output.txt
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
MODEL = "sonnet"  # Use sonnet for cost efficiency in eval
TIMEOUT = 300
PROJECT_DIR = "/home/zorz/sites/timan"

SYSTEM_APPEND = (
    "You are a Drupal implementation agent. Follow ALL loaded skills and rules exactly. "
    "Output ONLY the complete PHP file content and services.yml entry. "
    "Do not write files to disk. Do not explain. Just output the code."
)

# Test task: generate a service that exercises multiple skill rules
TASK_PROMPT = """Create a new Drupal service class for the timan_core module.

Service name: `timan_core.project_stats`
Class: `Drupal\\timan_core\\Service\\ProjectStatsService`
Interface: `Drupal\\timan_core\\Service\\ProjectStatsServiceInterface`

The service should:
1. Accept EntityTypeManagerInterface and ConfigFactoryInterface as dependencies
2. Have a method `getProjectStats(int $project_id): array` that:
   - Loads a project node (throw an exception if not found)
   - Counts related assignments
   - Returns a render array with cache metadata
3. Have a method `getActiveProjectCount(): int` that queries active projects

Output:
1. The complete PHP interface file
2. The complete PHP service class file
3. The services.yml entry

Follow all Drupal 11 conventions."""


@dataclass
class AssertionResult:
    id: str
    skill_source: str
    description: str
    passed: bool
    detail: str = ""


@dataclass
class BuilderResult:
    time_seconds: float = 0.0
    cost_usd: float = 0.0
    num_turns: int = 0
    output: str = ""
    error: str = ""
    assertions: list = field(default_factory=list)
    pass_count: int = 0
    total_count: int = 0
    skill_coverage: dict = field(default_factory=dict)

    @property
    def score(self) -> str:
        return f"{self.pass_count}/{self.total_count}"


# Assertions derived from loaded skills
ASSERTIONS = [
    # From drupal-rules skill
    {"id": "B01", "skill": "drupal-rules", "desc": "Uses declare(strict_types=1)",
     "check": "contains", "text": "declare(strict_types=1)"},
    {"id": "B02", "skill": "drupal-rules", "desc": "No \\Drupal:: static calls in class body",
     "check": "no_static_drupal"},
    {"id": "B03", "skill": "drupal-rules", "desc": "Uses guard clauses / early return pattern",
     "check": "contains_any", "texts": ["return [];", "return 0;", "throw new", "if (!"]},

    # From drupal-coding-standards skill
    {"id": "B04", "skill": "drupal-coding-standards", "desc": "Class is declared final",
     "check": "contains", "text": "final class"},
    {"id": "B05", "skill": "drupal-coding-standards", "desc": "Has PHPDoc comments on class",
     "check": "contains", "text": "/**"},
    {"id": "B06", "skill": "drupal-coding-standards", "desc": "Uses PascalCase for class name",
     "check": "contains", "text": "ProjectStatsService"},

    # From drupal-service-di skill
    {"id": "B07", "skill": "drupal-service-di", "desc": "Uses constructor property promotion (private readonly)",
     "check": "contains_any", "texts": ["private readonly", "protected readonly"]},
    {"id": "B08", "skill": "drupal-service-di", "desc": "Has .services.yml entry with arguments",
     "check": "contains", "text": "arguments:"},
    {"id": "B09", "skill": "drupal-service-di", "desc": "Services.yml uses interface type for service class or argument references",
     "check": "contains_any", "texts": ["@entity_type.manager", "@config.factory", "'@"]},
    {"id": "B10", "skill": "drupal-service-di", "desc": "Implements an interface",
     "check": "contains", "text": "implements ProjectStatsServiceInterface"},

    # From drupal-entity-api skill
    {"id": "B11", "skill": "drupal-entity-api", "desc": "Uses accessCheck on entity queries",
     "check": "contains", "text": "accessCheck"},
    {"id": "B12", "skill": "drupal-entity-api", "desc": "Uses entity storage load pattern (not raw SQL)",
     "check": "contains_any", "texts": ["getStorage(", "entityQuery(", "->load("]},

    # From drupal-caching skill
    {"id": "B13", "skill": "drupal-caching", "desc": "Includes #cache metadata in render array",
     "check": "contains", "text": "'#cache'"},
    {"id": "B14", "skill": "drupal-caching", "desc": "Has cache tags",
     "check": "contains_any", "texts": ["'tags'", "'cache_tags'", "CacheableMetadata"]},
    {"id": "B15", "skill": "drupal-caching", "desc": "Has cache contexts or max-age",
     "check": "contains_any", "texts": ["'contexts'", "'max-age'", "max_age"]},

    # From drupal-conventions skill
    {"id": "B16", "skill": "drupal-conventions", "desc": "Uses exceptions for errors, not null returns",
     "check": "contains_any", "texts": ["throw new", "Exception("]},

    # Structural quality
    {"id": "B17", "skill": "drupal-coding-standards", "desc": "Has namespace declaration",
     "check": "contains_any", "texts": ["namespace Drupal", "namespace Drupal\\timan_core", "namespace Drupal\\\\timan_core"]},
    {"id": "B18", "skill": "drupal-coding-standards", "desc": "Has use statements for type-hints",
     "check": "contains_any", "texts": ["EntityTypeManagerInterface", "use Drupal\\Core\\Entity", "use Drupal\\\\Core"]},
    {"id": "B19", "skill": "drupal-service-di", "desc": "Interface defines method signatures with return types",
     "check": "contains_any", "texts": ["): array", "): int"]},
    {"id": "B20", "skill": "drupal-rules", "desc": "Uses type declarations on method parameters",
     "check": "contains", "text": "int $project_id"},
]


def load_agent_prompt() -> str:
    """Load the drupal-builder agent definition."""
    agent_file = PLUGIN_DIR / "agents" / "drupal-builder.md"
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


def generate_code(agent_prompt: str) -> BuilderResult:
    """Run the builder agent to generate code."""
    result = BuilderResult()

    prompt = f"""{agent_prompt}

---

{TASK_PROMPT}"""

    args = [
        CLAUDE_BIN,
        "--model", MODEL,
        "--disallowedTools", "Write,Edit",
        "--append-system-prompt", SYSTEM_APPEND,
        "--print",
        "--output-format", "json",
        "--no-session-persistence",
        "--dangerously-skip-permissions",
        "--max-turns", "3",
        "-p", "-",
    ]

    start = time.monotonic()
    try:
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=PROJECT_DIR,
            env=clean_env(),
        )
        try:
            stdout, stderr = proc.communicate(input=prompt, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            result.time_seconds = TIMEOUT
            result.error = "TIMEOUT"
            return result

        result.time_seconds = round(time.monotonic() - start, 1)

        raw = stdout.strip()
        # Debug: save raw stdout
        debug_file = PLUGIN_DIR / "eval" / "evals" / "results" / "builder-raw-stdout.txt"
        with open(debug_file, "w") as df:
            df.write(f"STDOUT ({len(raw)} chars):\n{raw[:5000]}\n\nSTDERR:\n{stderr[:2000]}")

        try:
            data = json.loads(raw)
            # Extract text content from various JSON formats
            texts = []

            def extract_text(obj):
                """Recursively extract text content from JSON."""
                if isinstance(obj, str):
                    texts.append(obj)
                elif isinstance(obj, dict):
                    # Look for common text keys
                    for key in ["result", "text", "content"]:
                        if key in obj:
                            extract_text(obj[key])
                    # Also check nested structures
                    for key in ["message", "data"]:
                        if key in obj:
                            extract_text(obj[key])
                    # Extract cost/usage metadata
                    if "total_cost_usd" in obj:
                        result.cost_usd = obj["total_cost_usd"]
                    if "num_turns" in obj:
                        result.num_turns = obj["num_turns"]
                elif isinstance(obj, list):
                    for item in obj:
                        extract_text(item)

            extract_text(data)
            result.output = "\n".join(t for t in texts if t and len(t) > 20)

        except json.JSONDecodeError:
            # Not JSON — treat as raw text output
            result.output = raw
            if not raw:
                result.error = "No output from CLI"

        if proc.returncode != 0 and not result.output:
            result.error = (stderr or stdout or "non-zero exit")[:500]

    except Exception as e:
        result.time_seconds = round(time.monotonic() - start, 1)
        result.error = str(e)

    return result


def normalize_output(output: str) -> str:
    """Normalize output: unescape JSON, extract readable content."""
    # Handle double-escaped backslashes from JSON
    normalized = output.replace("\\\\n", "\n").replace("\\\\t", "\t")
    normalized = normalized.replace("\\n", "\n").replace("\\t", "\t")
    # Unescape remaining JSON escapes
    normalized = normalized.replace('\\"', '"')
    return normalized


def check_assertions(output: str) -> list[AssertionResult]:
    """Check all assertions against the generated output."""
    # Normalize the output to handle JSON escaping
    output = normalize_output(output)
    results = []

    for a in ASSERTIONS:
        aid = a["id"]
        skill = a["skill"]
        desc = a["desc"]
        check = a["check"]
        passed = False
        detail = ""

        try:
            if check == "contains":
                text = a["text"]
                passed = text in output
                detail = f"Found: {text}" if passed else f"Missing: {text}"

            elif check == "contains_any":
                found = [t for t in a["texts"] if t in output]
                passed = len(found) > 0
                detail = f"Found: {found[:3]}" if passed else f"None of: {a['texts'][:3]}"

            elif check == "no_static_drupal":
                # Check that \Drupal:: doesn't appear inside PHP class bodies
                # Extract only PHP code blocks from the output
                php_blocks = re.findall(r"```php\n(.*?)```", output, re.DOTALL)
                bad_lines = []
                for block in php_blocks:
                    in_class = False
                    for i, line in enumerate(block.split("\n")):
                        stripped = line.strip()
                        if "final class" in line or "class " in line:
                            in_class = True
                        if in_class and "\\Drupal::" in stripped:
                            if not stripped.startswith("//") and not stripped.startswith("*") and not stripped.startswith("#"):
                                bad_lines.append(f"{stripped[:60]}")
                passed = len(bad_lines) == 0
                detail = f"Static calls: {bad_lines[:3]}" if bad_lines else "No static calls in classes"

        except Exception as e:
            detail = f"Error: {e}"

        results.append(AssertionResult(id=aid, skill_source=skill, description=desc, passed=passed, detail=detail))

    return results


def main():
    timestamp = time.strftime("%Y%m%d-%H%M%S")

    check_only = "--check-only" in sys.argv
    output_text = ""

    if check_only:
        # Read from file
        if len(sys.argv) > sys.argv.index("--check-only") + 1:
            filepath = sys.argv[sys.argv.index("--check-only") + 1]
            with open(filepath) as f:
                output_text = f.read()
        result = BuilderResult(output=output_text)
    else:
        print("=== BUILDER AGENT EVAL ===")
        print(f"Testing: Does the builder agent apply its loaded skills?")
        print(f"Task: Generate ProjectStatsService for timan_core")
        print()

        agent_prompt = load_agent_prompt()
        print(f"Agent prompt: {len(agent_prompt)} chars")
        print("Generating code...")

        result = generate_code(agent_prompt)

        if result.error:
            print(f"ERROR: {result.error}")
        else:
            print(f"Done: {result.time_seconds}s, ${result.cost_usd:.4f}, {result.num_turns} turns")
            print(f"Output: {len(result.output)} chars")
        print()

        output_text = result.output

    # Save raw output for debugging
    output_file = PLUGIN_DIR / "eval" / "evals" / "results" / f"builder-output-{timestamp}.txt"
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, "w") as f:
        f.write(output_text)

    # Check assertions
    print("Checking 20 assertions (skill application)...")
    assertions = check_assertions(output_text)
    result.assertions = assertions
    result.pass_count = sum(1 for a in assertions if a.passed)
    result.total_count = len(assertions)

    # Calculate per-skill coverage
    skill_groups = {}
    for a in assertions:
        if a.skill_source not in skill_groups:
            skill_groups[a.skill_source] = {"pass": 0, "total": 0}
        skill_groups[a.skill_source]["total"] += 1
        if a.passed:
            skill_groups[a.skill_source]["pass"] += 1
    result.skill_coverage = skill_groups

    print(f"\nSCORE: {result.score}")
    print()

    for a in assertions:
        status = "PASS" if a.passed else "FAIL"
        print(f"  [{status}] {a.id} ({a.skill_source}): {a.description}")
        if not a.passed:
            print(f"         {a.detail}")

    # Skill coverage report
    print(f"\n=== SKILL APPLICATION REPORT ===")
    print(f"Did the agent use its loaded skills?\n")
    for skill, counts in sorted(skill_groups.items()):
        pct = (counts["pass"] / counts["total"] * 100) if counts["total"] > 0 else 0
        status = "YES" if pct == 100 else ("PARTIAL" if pct > 0 else "NO")
        print(f"  {skill:30s} {counts['pass']}/{counts['total']}  [{status}]")

    total_pct = (result.pass_count / result.total_count * 100) if result.total_count > 0 else 0
    print(f"\n  Overall skill application: {total_pct:.0f}%")

    # Save results
    results_file = PLUGIN_DIR / "eval" / "evals" / "results" / f"builder-{timestamp}.json"
    output_data = {
        "timestamp": timestamp,
        "model": MODEL,
        "task": "ProjectStatsService generation",
        "score": result.score,
        "pass_count": result.pass_count,
        "total_count": result.total_count,
        "time_seconds": result.time_seconds,
        "cost_usd": result.cost_usd,
        "skill_coverage": result.skill_coverage,
        "assertions": [asdict(a) for a in assertions],
    }
    with open(results_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n  Results: {results_file}")
    print(f"  Output: {output_file}")

    return result.pass_count, result.total_count


if __name__ == "__main__":
    passed, total = main()
    sys.exit(0 if passed == total else 1)
