"""Eval: measure reference skill definition quality.

Checks each SKILL.md against binary assertions:
  - Structural: has clear sections, examples, concrete guidance
  - Content: contains key domain-specific rules
  - Consistency: matches plugin conventions

Usage:
  python3 eval/eval-skills.py                    # all skills
  python3 eval/eval-skills.py --skill discover   # single skill
  python3 eval/eval-skills.py --fix              # auto-fix (with improvement loop)
"""

import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from glob import glob
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = PLUGIN_DIR / "skills"
EVAL_DIR = PLUGIN_DIR / "eval" / "evals"


@dataclass
class AssertionResult:
    id: str
    description: str
    passed: bool
    detail: str = ""


@dataclass
class SkillResult:
    skill: str
    file: str
    assertions: list = field(default_factory=list)
    pass_count: int = 0
    total_count: int = 0
    word_count: int = 0

    @property
    def score(self) -> str:
        return f"{self.pass_count}/{self.total_count}"


# =================== UNIVERSAL ASSERTIONS (apply to ALL skills) ===================

UNIVERSAL_ASSERTIONS = [
    {
        "id": "U01",
        "description": "Has YAML frontmatter with name and description",
        "check": "frontmatter_fields",
        "fields": ["name", "description"],
    },
    {
        "id": "U02",
        "description": "Has at least one H1 or H2 heading after frontmatter",
        "check": "has_heading",
    },
    {
        "id": "U03",
        "description": "Contains at least one code block (``` fenced)",
        "check": "has_code_block",
    },
    {
        "id": "U04",
        "description": "Word count is between 100 and 3000 (focused, not bloated)",
        "check": "word_count_range",
        "min": 100,
        "max": 3000,
    },
    {
        "id": "U05",
        "description": "Does not contain TODO, FIXME, or placeholder text",
        "check": "no_placeholders",
        "patterns": [r"\bTODO\b", r"\bFIXME\b", r"\bXXX\b", r"<INSERT", r"\[TBD\]"],
    },
    {
        "id": "U06",
        "description": "Has actionable guidance (contains imperative verbs: use, avoid, prefer, check, run)",
        "check": "has_imperatives",
        "words": ["use ", "avoid ", "prefer ", "check ", "run ", "never ", "always ", "must "],
        "min_count": 3,
    },
    {
        "id": "U07",
        "description": "No broken markdown (unclosed code blocks, malformed tables)",
        "check": "valid_markdown",
    },
]


# =================== SKILL-SPECIFIC ASSERTIONS ===================

SKILL_ASSERTIONS = {
    "drupal-rules": [
        {"id": "S01", "description": "Mentions declare(strict_types=1)", "check": "contains", "text": "strict_types"},
        {"id": "S02", "description": "Mentions dependency injection over \\Drupal::", "check": "contains", "text": "\\Drupal::"},
        {"id": "S03", "description": "Mentions final classes", "check": "contains", "text": "final"},
        {"id": "S04", "description": "Mentions guard clauses or early return", "check": "contains_any", "texts": ["guard clause", "early return", "return early"]},
        {"id": "S05", "description": "Mentions access checks on entity queries", "check": "contains", "text": "accessCheck"},
        {"id": "S06", "description": "Covers security (sanitize, XSS, or SQL injection)", "check": "contains_any", "texts": ["sanitize", "XSS", "SQL injection", "Xss::filter"]},
        {"id": "S07", "description": "Mentions cache metadata (#cache)", "check": "contains_any", "texts": ["#cache", "cache metadata", "CacheableMetadata"]},
        {"id": "S08", "description": "Mentions translatable strings (t() or |t)", "check": "contains_any", "texts": ["->t(", "|t", "TranslatableMarkup"]},
    ],
    "drupal-coding-standards": [
        {"id": "S01", "description": "Mentions PHPCS", "check": "contains", "text": "PHPCS"},
        {"id": "S02", "description": "Mentions PHPStan", "check": "contains_any", "texts": ["PHPStan", "phpstan"]},
        {"id": "S03", "description": "Mentions Drupal coding standard", "check": "contains_any", "texts": ["Drupal,DrupalPractice", "DrupalPractice", "coding standard"]},
        {"id": "S04", "description": "Has naming convention guidance", "check": "contains_any", "texts": ["camelCase", "snake_case", "PascalCase", "naming"]},
    ],
    "drupal-service-di": [
        {"id": "S01", "description": "Mentions .services.yml", "check": "contains", "text": ".services.yml"},
        {"id": "S02", "description": "Mentions constructor injection", "check": "contains_any", "texts": ["constructor injection", "__construct", "constructor property"]},
        {"id": "S03", "description": "Mentions interface type-hints", "check": "contains_any", "texts": ["Interface", "interface", "type-hint"]},
        {"id": "S04", "description": "Has services.yml code example", "check": "contains", "text": "arguments:"},
    ],
    "drupal-entity-api": [
        {"id": "S01", "description": "Mentions baseFieldDefinitions", "check": "contains", "text": "baseFieldDefinitions"},
        {"id": "S02", "description": "Mentions entity types (Content/Config)", "check": "contains_any", "texts": ["ContentEntityType", "ConfigEntityType", "ContentEntityBase"]},
        {"id": "S03", "description": "Covers CRUD operations", "check": "contains_any", "texts": ["create(", "save()", "delete()", "load("]},
        {"id": "S04", "description": "Mentions access control handlers", "check": "contains_any", "texts": ["AccessControlHandler", "access control", "checkAccess"]},
    ],
    "drupal-hook-patterns": [
        {"id": "S01", "description": "Mentions #[Hook] attribute (Drupal 11)", "check": "contains_any", "texts": ["#[Hook", "Hook attribute", "OOP hook"]},
        {"id": "S02", "description": "Mentions LegacyHook bridge", "check": "contains_any", "texts": ["LegacyHook", "legacy hook", "procedural hook"]},
        {"id": "S03", "description": "Covers form_alter hooks", "check": "contains_any", "texts": ["form_alter", "formAlter", "hook_form"]},
        {"id": "S04", "description": "Covers entity hooks (presave, insert, update)", "check": "contains_any", "texts": ["presave", "preSave", "entity_insert", "entity_update"]},
    ],
    "drupal-caching": [
        {"id": "S01", "description": "Mentions cache tags", "check": "contains", "text": "cache tag"},
        {"id": "S02", "description": "Mentions cache contexts", "check": "contains", "text": "cache context"},
        {"id": "S03", "description": "Mentions cache bins", "check": "contains_any", "texts": ["cache bin", "cache.default", "CacheBackend"]},
        {"id": "S04", "description": "Mentions max-age", "check": "contains", "text": "max-age"},
        {"id": "S05", "description": "Mentions cache invalidation", "check": "contains_any", "texts": ["invalidat", "Cache::invalidate", "invalidateAll"]},
    ],
    "drupal-security-patterns": [
        {"id": "S01", "description": "Mentions OWASP or common vulnerabilities", "check": "contains_any", "texts": ["OWASP", "XSS", "SQL injection", "CSRF"]},
        {"id": "S02", "description": "Mentions input sanitization", "check": "contains_any", "texts": ["sanitize", "filter", "Xss::filter", "Html::escape"]},
        {"id": "S03", "description": "Mentions access control", "check": "contains_any", "texts": ["permission", "access check", "_permission", "AccessResult"]},
        {"id": "S04", "description": "Mentions CSRF protection", "check": "contains_any", "texts": ["CSRF", "csrf_token", "form token"]},
    ],
    "drupal-testing": [
        {"id": "S01", "description": "Mentions drush eval for verification", "check": "contains", "text": "drush eval"},
        {"id": "S02", "description": "Mentions curl smoke tests", "check": "contains", "text": "curl"},
        {"id": "S03", "description": "Has concrete test command examples", "check": "contains_any", "texts": ["ddev drush", "php -l", "phpunit"]},
        {"id": "S04", "description": "Mentions JSON output format", "check": "contains_any", "texts": ["JSON", "json_encode", "json output"]},
    ],
    "drupal-conventions": [
        {"id": "S01", "description": "Mentions BEM CSS convention", "check": "contains", "text": "BEM"},
        {"id": "S02", "description": "Mentions translation conventions (t() or TranslatableMarkup)", "check": "contains_any", "texts": ["t()", "TranslatableMarkup", "translation"]},
        {"id": "S03", "description": "Mentions error handling patterns", "check": "contains_any", "texts": ["exception", "error handling", "try/catch", "Exception"]},
    ],
    "twig-templating": [
        {"id": "S01", "description": "Mentions Twig filters (|t, |raw, |escape)", "check": "contains_any", "texts": ["|t", "|raw", "|escape", "filter"]},
        {"id": "S02", "description": "Mentions theme suggestions or preprocess", "check": "contains_any", "texts": ["theme_suggestions", "preprocess", "hook_theme"]},
        {"id": "S03", "description": "Mentions template naming conventions", "check": "contains_any", "texts": [".html.twig", "template", "naming"]},
    ],
    "verification-before-completion": [
        {"id": "S01", "description": "Has the 5-step gate (IDENTIFY, RUN, READ, VERIFY, THEN)", "check": "contains_all", "texts": ["IDENTIFY", "RUN", "READ", "VERIFY", "THEN"]},
        {"id": "S02", "description": "Has verification requirements table", "check": "contains", "text": "NOT Sufficient"},
        {"id": "S03", "description": "Has rationalization prevention section", "check": "contains_any", "texts": ["rationalization", "excuse", "NOT verification"]},
        {"id": "S04", "description": "Has completion report template", "check": "contains_any", "texts": ["VERIFIED", "Verification Results", "completion"]},
    ],
    "writing-plans": [
        {"id": "S01", "description": "Mentions file paths in plans", "check": "contains_any", "texts": ["file path", "exact path", "File:"]},
        {"id": "S02", "description": "Mentions verification commands", "check": "contains_any", "texts": ["verification", "verify", "test command"]},
        {"id": "S03", "description": "Mentions task breakdown", "check": "contains_any", "texts": ["task", "step", "phase", "breakdown"]},
    ],
    "discover": [
        {"id": "S01", "description": "Mentions query prefixes (service:, route:, hook:)", "check": "contains_all", "texts": ["service:", "route:", "hook:"]},
        {"id": "S02", "description": "Mentions Logic IDs", "check": "contains_any", "texts": ["Logic ID", "FEAT-L", "logic_id"]},
        {"id": "S03", "description": "Mentions structural index files", "check": "contains_any", "texts": ["structural/", "services.md", "routes.md"]},
        {"id": "S04", "description": "Has prime or business index reference", "check": "contains_any", "texts": ["BUSINESS_INDEX", "FEATURE_MAP", "--prime", "prime"]},
    ],
    "semantic-docs": [
        {"id": "S01", "description": "Mentions tech specs with Logic IDs", "check": "contains_all", "texts": ["tech spec", "Logic ID"]},
        {"id": "S02", "description": "Mentions business index", "check": "contains_any", "texts": ["business index", "BUSINESS_INDEX", "00_BUSINESS_INDEX"]},
        {"id": "S03", "description": "Mentions feature codes", "check": "contains_any", "texts": ["feature code", "feature_id", "CODE_01"]},
    ],
    "structural-index": [
        {"id": "S01", "description": "Mentions structural file types (services, routes, hooks)", "check": "contains_all", "texts": ["services", "routes", "hooks"]},
        {"id": "S02", "description": "Mentions generation scripts or /drupal-refresh", "check": "contains_any", "texts": ["generate", "/drupal-refresh", "generate-all"]},
        {"id": "S03", "description": "Mentions dependency graph", "check": "contains_any", "texts": ["dependency", "DEPENDENCY_GRAPH", "cross-reference"]},
    ],
}


# =================== ASSERTION CHECKERS ===================

def parse_frontmatter(content: str) -> dict:
    """Simple YAML frontmatter parser."""
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end < 0:
        return {}
    fm_text = content[3:end].strip()
    result = {}
    for line in fm_text.split("\n"):
        if ":" in line and not line.startswith("  "):
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip()
    return result


def check_assertion(assertion: dict, content: str, content_lower: str) -> AssertionResult:
    aid = assertion["id"]
    desc = assertion["description"]
    check = assertion["check"]
    passed = False
    detail = ""

    try:
        if check == "frontmatter_fields":
            fm = parse_frontmatter(content)
            missing = [f for f in assertion["fields"] if not fm.get(f)]
            passed = len(missing) == 0
            detail = f"Missing: {missing}" if missing else "All present"

        elif check == "has_heading":
            passed = bool(re.search(r"^#{1,2} ", content, re.MULTILINE))
            detail = "Found heading" if passed else "No H1/H2 headings"

        elif check == "has_code_block":
            passed = "```" in content
            detail = "Has code blocks" if passed else "No code blocks"

        elif check == "word_count_range":
            # Strip frontmatter for word count
            body = content
            if content.startswith("---"):
                end = content.find("---", 3)
                if end > 0:
                    body = content[end + 3:]
            words = len(body.split())
            passed = assertion["min"] <= words <= assertion["max"]
            detail = f"{words} words"

        elif check == "no_placeholders":
            found = []
            for p in assertion["patterns"]:
                if re.search(p, content):
                    found.append(p)
            passed = len(found) == 0
            detail = f"Found: {found}" if found else "Clean"

        elif check == "has_imperatives":
            count = sum(1 for w in assertion["words"] if w.lower() in content_lower)
            passed = count >= assertion["min_count"]
            detail = f"{count} imperative words found"

        elif check == "valid_markdown":
            # Check for unclosed code blocks
            backtick_count = content.count("```")
            passed = backtick_count % 2 == 0
            detail = f"{backtick_count} ``` markers" + (" (unclosed!)" if not passed else "")

        elif check == "contains":
            text = assertion["text"]
            passed = text in content
            detail = f"Found: {text}" if passed else f"Missing: {text}"

        elif check == "contains_any":
            found = [t for t in assertion["texts"] if t in content or t.lower() in content_lower]
            passed = len(found) > 0
            detail = f"Found: {found[:3]}" if passed else f"None of: {assertion['texts'][:3]}"

        elif check == "contains_all":
            missing = [t for t in assertion["texts"] if t not in content and t.lower() not in content_lower]
            passed = len(missing) == 0
            detail = f"Missing: {missing}" if missing else "All present"

        else:
            detail = f"Unknown check: {check}"

    except Exception as e:
        detail = f"Error: {e}"

    return AssertionResult(id=aid, description=desc, passed=passed, detail=detail)


def eval_skill(skill_name: str) -> SkillResult:
    """Evaluate a single skill's SKILL.md."""
    skill_dir = SKILLS_DIR / skill_name
    skill_file = skill_dir / "SKILL.md"

    if not skill_file.exists():
        return SkillResult(skill=skill_name, file=str(skill_file))

    content = skill_file.read_text()
    content_lower = content.lower()

    result = SkillResult(
        skill=skill_name,
        file=str(skill_file),
        word_count=len(content.split()),
    )

    # Run universal assertions
    for assertion in UNIVERSAL_ASSERTIONS:
        ar = check_assertion(assertion, content, content_lower)
        result.assertions.append(ar)

    # Run skill-specific assertions
    specific = SKILL_ASSERTIONS.get(skill_name, [])
    for assertion in specific:
        ar = check_assertion(assertion, content, content_lower)
        result.assertions.append(ar)

    result.pass_count = sum(1 for a in result.assertions if a.passed)
    result.total_count = len(result.assertions)

    return result


def main():
    timestamp = time.strftime("%Y%m%d-%H%M%S")

    # Parse args
    single_skill = None
    if "--skill" in sys.argv:
        idx = sys.argv.index("--skill")
        if idx + 1 < len(sys.argv):
            single_skill = sys.argv[idx + 1]

    # Discover all skills
    if single_skill:
        skills = [single_skill]
    else:
        skills = sorted([d.name for d in SKILLS_DIR.iterdir() if d.is_dir() and (d / "SKILL.md").exists()])

    print(f"=== SKILL CONTENT EVAL ===")
    print(f"Skills: {len(skills)}")
    print()

    all_results = []
    total_pass = 0
    total_assertions = 0

    for skill_name in skills:
        result = eval_skill(skill_name)
        all_results.append(result)
        total_pass += result.pass_count
        total_assertions += result.total_count

        failed = [a for a in result.assertions if not a.passed]
        status = "PASS" if not failed else "FAIL"
        print(f"[{status}] {skill_name}: {result.score} ({result.word_count} words)")

        for a in failed:
            print(f"       [{a.id}] {a.description}")
            print(f"             {a.detail}")

    print(f"\n=== SUMMARY ===")
    print(f"  Total: {total_pass}/{total_assertions} assertions passed")
    print(f"  Skills: {len(all_results)}")
    perfect = sum(1 for r in all_results if r.pass_count == r.total_count)
    print(f"  Perfect: {perfect}/{len(all_results)}")

    # Per-skill scores
    print()
    for r in sorted(all_results, key=lambda x: x.pass_count / max(x.total_count, 1)):
        pct = (r.pass_count / r.total_count * 100) if r.total_count > 0 else 0
        bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
        print(f"  {r.skill:35s} {r.score:>6s}  [{bar}] {pct:.0f}%")

    # Save results
    results_dir = EVAL_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    results_file = results_dir / f"skills-{timestamp}.json"

    output = {
        "timestamp": timestamp,
        "total_pass": total_pass,
        "total_assertions": total_assertions,
        "skills": [{
            "skill": r.skill,
            "score": r.score,
            "pass_count": r.pass_count,
            "total_count": r.total_count,
            "word_count": r.word_count,
            "assertions": [asdict(a) for a in r.assertions],
        } for r in all_results],
    }

    with open(results_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  Results: {results_file}")

    return total_pass, total_assertions


if __name__ == "__main__":
    passed, total = main()
    sys.exit(0 if passed == total else 1)
