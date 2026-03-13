"""Eval: agent definition quality (non-behavioral).

Checks agent .md files for structural quality:
  - Proper YAML frontmatter with required fields
  - Has required sections (Role, Scope, Key Rules, etc.)
  - Skills are valid references
  - Consistent format across all agents
"""

import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
AGENTS_DIR = PLUGIN_DIR / "agents"
SKILLS_DIR = PLUGIN_DIR / "skills"
EVAL_DIR = PLUGIN_DIR / "eval" / "evals"


@dataclass
class AssertionResult:
    id: str
    description: str
    passed: bool
    detail: str = ""


@dataclass
class AgentResult:
    agent: str
    file: str
    assertions: list = field(default_factory=list)
    pass_count: int = 0
    total_count: int = 0

    @property
    def score(self) -> str:
        return f"{self.pass_count}/{self.total_count}"


def parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter between --- delimiters."""
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
        # Skip example blocks
        if line.strip().startswith("<example>") or line.strip().startswith("</example>"):
            continue
        if line.startswith("  - ") or line.startswith("    - "):
            if current_key and current_list is not None:
                current_list.append(line.strip().lstrip("- ").strip())
            continue
        if ":" in line and not line.startswith(" "):
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


def get_valid_skills() -> set:
    """Get set of valid skill names from skills directory."""
    return {d.name for d in SKILLS_DIR.iterdir() if d.is_dir() and (d / "SKILL.md").exists()}


def eval_agent(agent_file: Path) -> AgentResult:
    agent_name = agent_file.stem
    content = agent_file.read_text()
    fm = parse_frontmatter(content)
    valid_skills = get_valid_skills()

    result = AgentResult(agent=agent_name, file=str(agent_file))
    assertions = []

    # A01: Has YAML frontmatter
    has_fm = content.startswith("---") and content.find("---", 3) > 0
    assertions.append(AssertionResult(
        id="A01", description="Has YAML frontmatter",
        passed=has_fm, detail="Frontmatter found" if has_fm else "No frontmatter"
    ))

    # A02: Frontmatter has name field
    has_name = bool(fm.get("name"))
    assertions.append(AssertionResult(
        id="A02", description="Frontmatter has name field",
        passed=has_name, detail=f"name={fm.get('name', 'MISSING')}"
    ))

    # A03: Frontmatter has description field
    has_desc = bool(fm.get("description"))
    assertions.append(AssertionResult(
        id="A03", description="Frontmatter has description field",
        passed=has_desc, detail=f"description={'present' if has_desc else 'MISSING'}"
    ))

    # A04: Frontmatter has tools field
    has_tools = bool(fm.get("tools"))
    assertions.append(AssertionResult(
        id="A04", description="Frontmatter has tools field",
        passed=has_tools, detail=f"tools={fm.get('tools', 'MISSING')}"
    ))

    # A05: Frontmatter has model field (sonnet or opus)
    model = fm.get("model", "")
    valid_model = model in ("sonnet", "opus", "haiku")
    assertions.append(AssertionResult(
        id="A05", description="Frontmatter has valid model (sonnet/opus)",
        passed=valid_model, detail=f"model={model}"
    ))

    # A06: Frontmatter has color field
    has_color = bool(fm.get("color"))
    assertions.append(AssertionResult(
        id="A06", description="Frontmatter has color field",
        passed=has_color, detail=f"color={fm.get('color', 'MISSING')}"
    ))

    # A07: Frontmatter has skills field (list)
    skills_raw = fm.get("skills", "")
    if isinstance(skills_raw, str):
        skills_list = [s.strip() for s in skills_raw.split(",") if s.strip()]
    elif isinstance(skills_raw, list):
        skills_list = skills_raw
    else:
        skills_list = []
    has_skills = len(skills_list) > 0
    assertions.append(AssertionResult(
        id="A07", description="Frontmatter has skills list",
        passed=has_skills, detail=f"{len(skills_list)} skills"
    ))

    # A08: All referenced skills exist in skills/ directory
    invalid_skills = [s for s in skills_list if s not in valid_skills]
    assertions.append(AssertionResult(
        id="A08", description="All referenced skills exist in skills/ directory",
        passed=len(invalid_skills) == 0,
        detail=f"Invalid: {invalid_skills}" if invalid_skills else f"All {len(skills_list)} valid"
    ))

    # A09: Has H1 heading with agent name
    has_h1 = bool(re.search(r"^# .+", content, re.MULTILINE))
    assertions.append(AssertionResult(
        id="A09", description="Has H1 heading",
        passed=has_h1, detail="H1 found" if has_h1 else "No H1"
    ))

    # A10: Has Role description
    has_role = "**Role**" in content or "## Role" in content
    assertions.append(AssertionResult(
        id="A10", description="Has Role description",
        passed=has_role, detail="Role found" if has_role else "No role"
    ))

    # A11: Has Scope section
    has_scope = "## Scope" in content
    assertions.append(AssertionResult(
        id="A11", description="Has ## Scope section",
        passed=has_scope, detail="Found" if has_scope else "Missing"
    ))

    # A12: Has at least one example in frontmatter
    has_example = "<example>" in content
    assertions.append(AssertionResult(
        id="A12", description="Has at least one <example> block",
        passed=has_example, detail="Example found" if has_example else "No examples"
    ))

    # A13: Content is between 500 and 5000 chars (focused, not empty or bloated)
    content_len = len(content)
    good_length = 500 <= content_len <= 8000
    assertions.append(AssertionResult(
        id="A13", description="Content length between 500 and 8000 chars",
        passed=good_length, detail=f"{content_len} chars"
    ))

    # A14: Has at least one code block
    has_code = "```" in content
    assertions.append(AssertionResult(
        id="A14", description="Has at least one code block",
        passed=has_code, detail="Code block found" if has_code else "No code blocks"
    ))

    # A15: No TODO/FIXME/placeholder text
    placeholders = [r"\bTODO\b", r"\bFIXME\b", r"\bXXX\b", r"\[TBD\]"]
    found = [p for p in placeholders if re.search(p, content)]
    assertions.append(AssertionResult(
        id="A15", description="No TODO/FIXME/placeholder text",
        passed=len(found) == 0,
        detail=f"Found: {found}" if found else "Clean"
    ))

    result.assertions = assertions
    result.pass_count = sum(1 for a in assertions if a.passed)
    result.total_count = len(assertions)

    return result


def main():
    timestamp = time.strftime("%Y%m%d-%H%M%S")

    # Parse args
    single_agent = None
    if "--agent" in sys.argv:
        idx = sys.argv.index("--agent")
        if idx + 1 < len(sys.argv):
            single_agent = sys.argv[idx + 1]

    # Find all agents
    if single_agent:
        agents = [AGENTS_DIR / f"{single_agent}.md"]
    else:
        agents = sorted(AGENTS_DIR.glob("*.md"))

    print(f"=== AGENT DEFINITION EVAL ===")
    print(f"Agents: {len(agents)}\n")

    all_results = []
    total_pass = 0
    total_assertions = 0

    for agent_file in agents:
        result = eval_agent(agent_file)
        all_results.append(result)
        total_pass += result.pass_count
        total_assertions += result.total_count

        failed = [a for a in result.assertions if not a.passed]
        status = "PASS" if not failed else "FAIL"
        print(f"[{status}] {result.agent}: {result.score}")

        for a in failed:
            print(f"       [{a.id}] {a.description}")
            print(f"             {a.detail}")

    print(f"\n=== SUMMARY ===")
    print(f"  Total: {total_pass}/{total_assertions}")
    perfect = sum(1 for r in all_results if r.pass_count == r.total_count)
    print(f"  Perfect: {perfect}/{len(all_results)}")

    for r in all_results:
        pct = (r.pass_count / r.total_count * 100) if r.total_count > 0 else 0
        print(f"  {r.agent:25s} {r.score:>6s}  {pct:.0f}%")

    # Save results
    results_dir = EVAL_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    results_file = results_dir / f"agents-{timestamp}.json"
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "total_pass": total_pass,
            "total_assertions": total_assertions,
            "agents": [{
                "agent": r.agent,
                "score": r.score,
                "pass_count": r.pass_count,
                "total_count": r.total_count,
                "assertions": [asdict(a) for a in r.assertions],
            } for r in all_results],
        }, f, indent=2)

    print(f"\n  Results: {results_file}")
    return total_pass, total_assertions


if __name__ == "__main__":
    passed, total = main()
    sys.exit(0 if passed == total else 1)
