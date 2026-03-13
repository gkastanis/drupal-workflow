"""Eval: measure semantic-architect agent output quality.

For each test feature:
  1. Delete docs/semantic/tech/ and 00_BUSINESS_INDEX.md (keep structural/)
  2. Invoke claude CLI with the agent prompt to generate a tech spec
  3. Check generated output against 25 binary assertions
  4. Report pass/fail per assertion and total score

Usage:
  python eval/eval-semantic-architect.py                 # full eval (2 features)
  python eval/eval-semantic-architect.py --feature ASGN  # single feature
  python eval/eval-semantic-architect.py --check-only    # skip generation, check existing files
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from glob import glob
from pathlib import Path

CLAUDE_BIN = "claude"
PLUGIN_DIR = Path(__file__).resolve().parent.parent
EVAL_JSON = PLUGIN_DIR / "eval" / "evals" / "eval.json"
MODEL = "sonnet"
TIMEOUT = 600  # 10 min per feature
PROJECT_DIR = "/home/zorz/sites/timan"

SYSTEM_APPEND = (
    "You are a semantic documentation generation agent. "
    "Follow the instructions below EXACTLY. Generate the requested tech spec. "
    "Do NOT ask for confirmation. Do NOT summarize at the end. Just write the file."
)


@dataclass
class AssertionResult:
    id: str
    description: str
    category: str
    passed: bool
    detail: str = ""


@dataclass
class FeatureResult:
    feature: str
    time_seconds: float = 0.0
    cost_usd: float = 0.0
    num_turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str = ""
    generated_file: str = ""
    assertions: list = field(default_factory=list)
    pass_count: int = 0
    total_count: int = 0

    @property
    def score(self) -> str:
        return f"{self.pass_count}/{self.total_count}"


def load_eval_config() -> dict:
    with open(EVAL_JSON) as f:
        return json.load(f)


def load_agent_prompt() -> str:
    agent_file = PLUGIN_DIR / "agents" / "semantic-architect.md"
    with open(agent_file) as f:
        content = f.read()
    # Strip YAML frontmatter (between first two --- lines)
    parts = content.split("---", 2)
    if len(parts) >= 3:
        return parts[2].strip()
    return content


def clean_semantic_output(project_dir: str) -> None:
    """Delete generated semantic docs but keep structural index."""
    tech_dir = os.path.join(project_dir, "docs", "semantic", "tech")
    biz_index = os.path.join(project_dir, "docs", "semantic", "00_BUSINESS_INDEX.md")
    gen_summary = os.path.join(project_dir, "docs", "semantic", "GENERATION_SUMMARY.md")
    feature_map = os.path.join(project_dir, "docs", "semantic", "FEATURE_MAP.md")
    dep_graph = os.path.join(project_dir, "docs", "semantic", "DEPENDENCY_GRAPH.md")
    schemas_dir = os.path.join(project_dir, "docs", "semantic", "schemas")

    if os.path.isdir(tech_dir):
        shutil.rmtree(tech_dir)
    for f in [biz_index, gen_summary, feature_map, dep_graph]:
        if os.path.isfile(f):
            os.remove(f)
    # Remove only .business.json schemas (keep .base-fields.json)
    if os.path.isdir(schemas_dir):
        for f in glob(os.path.join(schemas_dir, "*.business.json")):
            os.remove(f)

    # Recreate tech dir
    os.makedirs(tech_dir, exist_ok=True)
    print("  Cleaned semantic output (kept structural/)")


def clean_env() -> dict:
    env = {**os.environ}
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    env["DISABLE_PROMPT_CACHING_SONNET"] = "1"
    return env


def generate_feature(feature_code: str, module_name: str, agent_prompt: str) -> FeatureResult:
    """Run claude CLI to generate a tech spec for one feature."""
    result = FeatureResult(feature=feature_code)

    prompt = f"""{agent_prompt}

---

**TASK**: Generate a new tech spec for feature **{feature_code}** (module: `{module_name}`).

**Steps**:
1. Read `docs/semantic/structural/services.md`, `methods.md`, `routes.md`, `hooks.md`, `permissions.md`, `entities.md`, `plugins.md` — filter for rows belonging to `{module_name}`
2. Read the source code files in `www/modules/custom/{module_name}/`
3. Write a complete tech spec to `docs/semantic/tech/{feature_code}_01_<Name>.md`
4. Include YAML frontmatter with ALL required fields
5. Map every public service method, route, and hook to a Logic ID
6. Include mermaid execution flow diagram

Output ONLY the file. Do not explain what you did."""

    args = [
        CLAUDE_BIN,
        "--model", MODEL,
        "--append-system-prompt", SYSTEM_APPEND,
        "--print",
        "--output-format", "json",
        "--no-session-persistence",
        "--dangerously-skip-permissions",
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

        try:
            data = json.loads(stdout.strip())
            result.cost_usd = data.get("total_cost_usd", 0)
            result.num_turns = data.get("num_turns", 0)
            usage = data.get("usage", {})
            result.input_tokens = usage.get("input_tokens", 0)
            result.output_tokens = usage.get("output_tokens", 0)
        except json.JSONDecodeError:
            result.error = "JSON parse failed"

        if proc.returncode != 0 and not result.cost_usd:
            result.error = (stderr or stdout or "non-zero exit")[:500]

    except Exception as e:
        result.time_seconds = round(time.monotonic() - start, 1)
        result.error = str(e)

    return result


# =================== ASSERTION CHECKERS ===================

def parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter as a dict (simple parser, no PyYAML needed)."""
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end < 0:
        return {}
    fm_text = content[3:end].strip()
    result = {}
    current_key = None
    current_list = None
    for line in fm_text.split("\n"):
        if line.startswith("  - "):
            if current_key and current_list is not None:
                current_list.append(line.strip("  - ").strip())
            continue
        if ":" in line:
            if current_key and current_list is not None:
                result[current_key] = current_list
                current_list = None
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if not val:
                current_key = key
                current_list = []
            else:
                result[key] = val
                current_key = key
                current_list = None
    if current_key and current_list is not None:
        result[current_key] = current_list
    return result


def get_section_content(content: str, heading: str) -> str:
    """Extract content between a ## heading and the next ## heading."""
    pattern = re.escape(heading) + r"\s*\n"
    m = re.search(pattern, content)
    if not m:
        return ""
    start = m.end()
    next_heading = re.search(r"\n## ", content[start:])
    if next_heading:
        return content[start:start + next_heading.start()]
    return content[start:]


def count_logic_ids(content: str, feature_code: str) -> int:
    """Count Logic ID rows in the Logic-to-Code Mapping table."""
    section = get_section_content(content, "## Logic-to-Code Mapping")
    pattern = rf"\|\s*{re.escape(feature_code)}-L\d+"
    return len(re.findall(pattern, section))


def check_assertions(config: dict, feature_code: str, project_dir: str) -> list[AssertionResult]:
    """Run all assertions against the generated output."""
    results = []

    # Find generated file(s)
    tech_dir = os.path.join(project_dir, "docs", "semantic", "tech")
    generated = glob(os.path.join(tech_dir, f"{feature_code}_*.md"))
    all_files = glob(os.path.join(tech_dir, "*.md"))

    # If no matching file, try finding any file
    if not generated and all_files:
        generated = all_files

    content = ""
    filename = ""
    frontmatter = {}

    if generated:
        filepath = generated[0]
        filename = os.path.basename(filepath)
        with open(filepath) as f:
            content = f.read()
        frontmatter = parse_frontmatter(content)

    for assertion in config["assertions"]:
        aid = assertion["id"]
        desc = assertion["description"]
        cat = assertion["category"]
        check = assertion["check"]

        passed = False
        detail = ""

        try:
            if check == "glob_match":
                passed = len(generated) >= assertion.get("min_count", 1)
                detail = f"Found {len(generated)} file(s)" if generated else "No files found"

            elif check == "regex_filename":
                if filename:
                    passed = bool(re.match(assertion["pattern"], filename))
                    detail = f"Filename: {filename}"
                else:
                    detail = "No file generated"

            elif check == "no_freeform_filenames":
                if all_files:
                    bad = []
                    for f in all_files:
                        bn = os.path.basename(f)
                        for bp in assertion["bad_patterns"]:
                            if re.search(bp, bn):
                                bad.append(bn)
                                break
                    passed = len(bad) == 0
                    detail = f"Bad filenames: {bad}" if bad else "All filenames conform"
                else:
                    detail = "No files to check"

            elif check == "starts_with":
                passed = content.startswith(assertion["value"])
                detail = f"First 10 chars: {repr(content[:10])}"

            elif check == "frontmatter_field":
                val = frontmatter.get(assertion["field"], "")
                passed = str(val) == assertion["expected"]
                detail = f"{assertion['field']}={val}"

            elif check == "frontmatter_field_exists":
                val = frontmatter.get(assertion["field"], "")
                passed = bool(val)
                detail = f"{assertion['field']}={val}" if val else f"Missing: {assertion['field']}"

            elif check == "frontmatter_list_min":
                val = frontmatter.get(assertion["field"], [])
                if isinstance(val, list):
                    passed = len(val) >= assertion["min_count"]
                    detail = f"{assertion['field']}: {len(val)} items"
                else:
                    detail = f"{assertion['field']} is not a list: {val}"

            elif check == "frontmatter_date":
                val = str(frontmatter.get(assertion["field"], ""))
                passed = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", val))
                detail = f"{assertion['field']}={val}"

            elif check == "frontmatter_int_min":
                val = frontmatter.get(assertion["field"], "0")
                try:
                    num = int(val)
                    passed = num >= assertion["min_value"]
                    detail = f"{assertion['field']}={num}"
                except (ValueError, TypeError):
                    detail = f"Not an integer: {val}"

            elif check == "contains_heading":
                heading = assertion["heading"]
                passed = heading in content
                detail = f"Found: {heading}" if passed else f"Missing: {heading}"

            elif check == "table_rows_min":
                section = get_section_content(content, f"## {assertion['section']}")
                rows = [l for l in section.split("\n") if l.strip().startswith("|") and "---" not in l and "Logic ID" not in l]
                passed = len(rows) >= assertion["min_rows"]
                detail = f"Table rows: {len(rows)}"

            elif check == "logic_id_pattern":
                section = get_section_content(content, "## Logic-to-Code Mapping")
                ids = re.findall(r"\|\s*([A-Z]+-L\d+)", section)
                if ids:
                    bad = [i for i in ids if not re.match(assertion["pattern"], i)]
                    passed = len(bad) == 0
                    detail = f"{len(ids)} IDs, {len(bad)} malformed" + (f": {bad[:3]}" if bad else "")
                else:
                    detail = "No Logic IDs found"

            elif check == "logic_count_matches":
                fm_count = int(frontmatter.get("logic_id_count", 0))
                actual = count_logic_ids(content, frontmatter.get("feature_id", feature_code))
                passed = fm_count == actual
                detail = f"frontmatter={fm_count}, actual={actual}"

            elif check == "related_files_exist":
                files = frontmatter.get("related_files", [])
                if isinstance(files, list) and files:
                    existing = sum(1 for f in files if os.path.isfile(os.path.join(project_dir, f)))
                    pct = (existing / len(files)) * 100
                    passed = pct >= assertion["min_pct"]
                    detail = f"{existing}/{len(files)} exist ({pct:.0f}%)"
                else:
                    detail = "No related_files"

            elif check == "feature_id_matches_filename":
                fm_id = frontmatter.get("feature_id", "")
                if filename and fm_id:
                    passed = filename.startswith(f"{fm_id}_")
                    detail = f"feature_id={fm_id}, filename={filename}"
                else:
                    detail = f"feature_id={fm_id}, filename={filename}"

            elif check == "contains_string":
                passed = assertion["value"] in content
                detail = f"Found: {assertion['value']}" if passed else f"Missing: {assertion['value']}"

            elif check == "section_word_count":
                section = get_section_content(content, f"## {assertion['section']}")
                words = len(section.split())
                passed = assertion["min_words"] <= words <= assertion["max_words"]
                detail = f"{words} words (want {assertion['min_words']}-{assertion['max_words']})"

            elif check == "h1_pattern":
                h1_match = re.search(r"^# .+", content, re.MULTILINE)
                if h1_match:
                    h1 = h1_match.group()
                    passed = bool(re.match(assertion["pattern"], h1))
                    detail = f"H1: {h1}"
                else:
                    detail = "No H1 heading found"

            else:
                detail = f"Unknown check type: {check}"

        except Exception as e:
            detail = f"Error: {e}"

        results.append(AssertionResult(id=aid, description=desc, category=cat, passed=passed, detail=detail))

    return results


# =================== MODULE MAP ===================

FEATURE_MODULES = {
    "ASGN": "timan_assignment",
    "HDAY": "timan_holiday",
    "TIME": "timan_time_entry",
    "AUTH": "timan_core",
    "LEAV": "timan_leave",
    "RMDR": "timan_reminder",
    "AI": "timan_ai",
    "AEMD": "ai_email_digest",
    "MCP": "timan_mcp",
    "PWA": "timan_pwa",
    "MIGR": "timan_migration",
    "DOCS": "timan_docs",
    "CLNT": "timan_core",
    "USER": "timan_core",
}


def main():
    config = load_eval_config()
    agent_prompt = load_agent_prompt()
    timestamp = time.strftime("%Y%m%d-%H%M%S")

    # Parse args
    check_only = "--check-only" in sys.argv
    single_feature = None
    if "--feature" in sys.argv:
        idx = sys.argv.index("--feature")
        if idx + 1 < len(sys.argv):
            single_feature = sys.argv[idx + 1].upper()

    features = [single_feature] if single_feature else config.get("test_features", ["ASGN"])
    project_dir = config.get("test_project", PROJECT_DIR)

    print(f"=== SEMANTIC ARCHITECT EVAL ===")
    print(f"Features: {features}")
    print(f"Project: {project_dir}")
    print(f"Check only: {check_only}")
    print(f"Agent prompt: {len(agent_prompt)} chars")
    print()

    all_results = []

    for feature in features:
        module = FEATURE_MODULES.get(feature, f"timan_{feature.lower()}")
        print(f"--- Feature: {feature} (module: {module}) ---")

        if not check_only:
            # Clean output
            clean_semantic_output(project_dir)

            # Generate
            print(f"  Generating {feature} tech spec...")
            result = generate_feature(feature, module, agent_prompt)

            if result.error:
                print(f"  ERROR: {result.error}")
            else:
                print(f"  Done: {result.time_seconds}s, ${result.cost_usd:.4f}, {result.num_turns} turns")
        else:
            result = FeatureResult(feature=feature)

        # Find generated file
        tech_dir = os.path.join(project_dir, "docs", "semantic", "tech")
        generated = glob(os.path.join(tech_dir, f"{feature}_*.md"))
        if not generated:
            generated = glob(os.path.join(tech_dir, "*.md"))
        if generated:
            result.generated_file = os.path.basename(generated[0])
            print(f"  Generated: {result.generated_file}")

        # Check assertions
        print(f"  Checking 25 assertions...")
        assertions = check_assertions(config, feature, project_dir)
        result.assertions = assertions
        result.pass_count = sum(1 for a in assertions if a.passed)
        result.total_count = len(assertions)

        print(f"\n  SCORE: {result.score}")
        print()

        for a in assertions:
            status = "PASS" if a.passed else "FAIL"
            print(f"    [{status}] {a.id}: {a.description}")
            if not a.passed:
                print(f"           {a.detail}")

        print()
        all_results.append(result)

    # Summary
    total_pass = sum(r.pass_count for r in all_results)
    total_assertions = sum(r.total_count for r in all_results)
    total_cost = sum(r.cost_usd for r in all_results)
    total_time = sum(r.time_seconds for r in all_results)

    print(f"=== SUMMARY ===")
    print(f"  Total: {total_pass}/{total_assertions} assertions passed")
    print(f"  Time: {total_time:.1f}s")
    print(f"  Cost: ${total_cost:.4f}")

    for r in all_results:
        print(f"  {r.feature}: {r.score} ({r.generated_file})")

    # Save results
    results_dir = PLUGIN_DIR / "eval" / "evals" / "results"
    results_dir.mkdir(exist_ok=True)
    results_file = results_dir / f"result-{timestamp}.json"

    output = {
        "timestamp": timestamp,
        "model": MODEL,
        "features": features,
        "total_pass": total_pass,
        "total_assertions": total_assertions,
        "total_cost": total_cost,
        "total_time": total_time,
        "results": [],
    }

    for r in all_results:
        output["results"].append({
            "feature": r.feature,
            "score": r.score,
            "pass_count": r.pass_count,
            "total_count": r.total_count,
            "time_seconds": r.time_seconds,
            "cost_usd": r.cost_usd,
            "num_turns": r.num_turns,
            "generated_file": r.generated_file,
            "error": r.error,
            "assertions": [asdict(a) for a in r.assertions],
        })

    with open(results_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  Results: {results_file}")

    # Return pass rate for scripting
    return total_pass, total_assertions


if __name__ == "__main__":
    passed, total = main()
    sys.exit(0 if passed == total else 1)
