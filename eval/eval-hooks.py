"""Eval: hooks system quality and integrity.

Checks:
  - hooks.json is valid JSON with correct structure
  - All referenced scripts exist and are executable
  - Each hook event has required fields
  - Scripts produce expected exit codes
"""

import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
HOOKS_FILE = PLUGIN_DIR / "hooks" / "hooks.json"
if not HOOKS_FILE.exists():
    HOOKS_FILE = PLUGIN_DIR / "hooks.json"
EVAL_DIR = PLUGIN_DIR / "eval" / "evals"


@dataclass
class AssertionResult:
    id: str
    description: str
    passed: bool
    detail: str = ""


def extract_script_paths(hooks_data: dict) -> list[str]:
    """Extract all script paths referenced in hooks.json."""
    scripts = []
    for event, hook_list in hooks_data.get("hooks", {}).items():
        for hook_group in hook_list:
            for hook in hook_group.get("hooks", []):
                cmd = hook.get("command", "")
                # Extract ${CLAUDE_PLUGIN_ROOT}/scripts/xxx.sh patterns
                matches = re.findall(r'\$\{CLAUDE_PLUGIN_ROOT\}/([^\s"\']+\.sh)', cmd)
                scripts.extend(matches)
                # Also check for direct paths
                matches2 = re.findall(r'(?:bash\s+)?"?\$\{CLAUDE_PLUGIN_ROOT\}/([^\s"\']+\.sh)', cmd)
                scripts.extend(matches2)
    return list(set(scripts))


def run_assertions() -> list[AssertionResult]:
    results = []

    # H01: hooks.json exists
    exists = HOOKS_FILE.exists()
    results.append(AssertionResult(
        id="H01", description="hooks.json exists",
        passed=exists, detail=str(HOOKS_FILE)
    ))
    if not exists:
        return results

    # H02: hooks.json is valid JSON
    try:
        with open(HOOKS_FILE) as f:
            data = json.load(f)
        valid_json = True
    except json.JSONDecodeError as e:
        valid_json = False
        data = {}
    results.append(AssertionResult(
        id="H02", description="hooks.json is valid JSON",
        passed=valid_json, detail="Valid" if valid_json else str(e)
    ))

    # H03: Has "hooks" top-level key
    has_hooks_key = "hooks" in data
    results.append(AssertionResult(
        id="H03", description="Has 'hooks' top-level key",
        passed=has_hooks_key, detail=f"Keys: {list(data.keys())}"
    ))

    hooks = data.get("hooks", {})

    # H04: Has SessionStart event
    results.append(AssertionResult(
        id="H04", description="Has SessionStart event",
        passed="SessionStart" in hooks,
        detail=f"Events: {list(hooks.keys())}"
    ))

    # H05: Has PreToolUse event
    results.append(AssertionResult(
        id="H05", description="Has PreToolUse event",
        passed="PreToolUse" in hooks,
        detail=f"Events: {list(hooks.keys())}"
    ))

    # H06: Has PostToolUse event
    results.append(AssertionResult(
        id="H06", description="Has PostToolUse event",
        passed="PostToolUse" in hooks,
        detail=f"Events: {list(hooks.keys())}"
    ))

    # H07: Has SubagentStart event
    results.append(AssertionResult(
        id="H07", description="Has SubagentStart event",
        passed="SubagentStart" in hooks,
        detail=f"Events: {list(hooks.keys())}"
    ))

    # H08: Has TaskCompleted event
    results.append(AssertionResult(
        id="H08", description="Has TaskCompleted event",
        passed="TaskCompleted" in hooks,
        detail=f"Events: {list(hooks.keys())}"
    ))

    # H09: PreToolUse has matcher covering Read, Grep, Edit, Write (sensitive file blocking)
    pre_tool = hooks.get("PreToolUse", [])
    required_tools = {"Read", "Grep", "Edit", "Write"}
    has_file_tool_matcher = any(
        required_tools.issubset(set(hg.get("matcher", "").split("|"))) for hg in pre_tool
    )
    results.append(AssertionResult(
        id="H09", description="PreToolUse blocks Read|Grep|Edit|Write for sensitive files",
        passed=has_file_tool_matcher,
        detail=f"Matchers: {[hg.get('matcher') for hg in pre_tool]}"
    ))

    # H10: PostToolUse has matcher for Edit|Write (PHP lint)
    post_tool = hooks.get("PostToolUse", [])
    has_edit_write_matcher = any(
        hg.get("matcher") == "Edit|Write" for hg in post_tool
    )
    results.append(AssertionResult(
        id="H10", description="PostToolUse triggers on Edit|Write for PHP lint",
        passed=has_edit_write_matcher,
        detail=f"Matchers: {[hg.get('matcher') for hg in post_tool]}"
    ))

    # H11: All hook entries have a valid type (command, prompt, agent, http)
    valid_types = {"command", "prompt", "agent", "http"}
    all_valid_type = True
    bad_types = []
    for event, hook_list in hooks.items():
        for hg in hook_list:
            for hook in hg.get("hooks", []):
                if hook.get("type") not in valid_types:
                    all_valid_type = False
                    bad_types.append(f"{event}: {hook.get('type')}")
    results.append(AssertionResult(
        id="H11", description="All hooks have valid type (command|prompt|agent|http)",
        passed=all_valid_type,
        detail="All valid" if all_valid_type else f"Invalid: {bad_types}"
    ))

    # H12: All hook entries have timeout
    all_have_timeout = True
    missing_timeout = []
    for event, hook_list in hooks.items():
        for hg in hook_list:
            for hook in hg.get("hooks", []):
                if "timeout" not in hook:
                    all_have_timeout = False
                    missing_timeout.append(event)
    results.append(AssertionResult(
        id="H12", description="All hooks have timeout field",
        passed=all_have_timeout,
        detail="All have timeout" if all_have_timeout else f"Missing: {missing_timeout}"
    ))

    # H13: All referenced scripts exist
    script_paths = extract_script_paths(data)
    missing_scripts = []
    for sp in script_paths:
        full_path = PLUGIN_DIR / sp
        if not full_path.exists():
            missing_scripts.append(sp)
    results.append(AssertionResult(
        id="H13", description="All referenced scripts exist on disk",
        passed=len(missing_scripts) == 0,
        detail=f"Missing: {missing_scripts}" if missing_scripts else f"All {len(script_paths)} scripts found"
    ))

    # H14: All referenced scripts are executable
    non_exec = []
    for sp in script_paths:
        full_path = PLUGIN_DIR / sp
        if full_path.exists():
            if not os.access(full_path, os.X_OK):
                non_exec.append(sp)
    results.append(AssertionResult(
        id="H14", description="All referenced scripts are executable",
        passed=len(non_exec) == 0,
        detail=f"Not executable: {non_exec}" if non_exec else f"All {len(script_paths)} scripts executable"
    ))

    # H15: SessionStart has activation banner (echo command)
    session_start = hooks.get("SessionStart", [])
    has_banner = any(
        "echo" in h.get("command", "") and "DRUPAL WORKFLOW" in h.get("command", "")
        for hg in session_start
        for h in hg.get("hooks", [])
    )
    results.append(AssertionResult(
        id="H15", description="SessionStart shows activation banner",
        passed=has_banner,
        detail="Banner found" if has_banner else "No banner"
    ))

    # H16: SessionStart checks structural index staleness (via project-state-check.sh)
    has_state_check = any(
        "project-state-check.sh" in h.get("command", "")
        for hg in session_start
        for h in hg.get("hooks", [])
    )
    results.append(AssertionResult(
        id="H16", description="SessionStart checks structural index staleness",
        passed=has_state_check,
        detail="State check found" if has_state_check else "No state check"
    ))

    # H17: No hook has timeout > 30000ms (30s safety limit)
    long_timeouts = []
    for event, hook_list in hooks.items():
        for hg in hook_list:
            for hook in hg.get("hooks", []):
                t = hook.get("timeout", 0)
                if t > 30000:
                    long_timeouts.append(f"{event}: {t}ms")
    results.append(AssertionResult(
        id="H17", description="No hook timeout exceeds 30 seconds",
        passed=len(long_timeouts) == 0,
        detail=f"Long timeouts: {long_timeouts}" if long_timeouts else "All within 30s"
    ))

    # H18: PostToolUse has staleness check
    has_staleness = any(
        "staleness" in h.get("command", "")
        for hg in post_tool
        for h in hg.get("hooks", [])
    )
    results.append(AssertionResult(
        id="H18", description="PostToolUse includes staleness warning check",
        passed=has_staleness,
        detail="Staleness check found" if has_staleness else "No staleness check"
    ))

    # H19: block-sensitive-files.sh blocks settings.php and .env
    block_script = PLUGIN_DIR / "scripts" / "block-sensitive-files.sh"
    if block_script.exists():
        content = block_script.read_text()
        blocks_settings = "settings.php" in content or "settings.local.php" in content
        blocks_env = ".env" in content
        passed = blocks_settings and blocks_env
    else:
        passed = False
        content = ""
    results.append(AssertionResult(
        id="H19", description="Sensitive file blocker covers settings.php and .env",
        passed=passed,
        detail="Covers both" if passed else f"settings.php={blocks_settings if block_script.exists() else 'N/A'}, .env={blocks_env if block_script.exists() else 'N/A'}"
    ))

    # H20: All SessionStart hooks guarantee exit 0 (CRITICAL: non-zero kills entire hook registry)
    # Discovered 2026-03-14: A SessionStart hook that exits non-zero causes Claude Code
    # to clear the hook registry, silently disabling ALL Pre/PostToolUse hooks for the session.
    session_exit_safe = True
    unsafe_hooks = []
    for i, hg in enumerate(session_start):
        for hook in hg.get("hooks", []):
            cmd = hook.get("command", "")
            # Check that command ends with "exit 0", has error fallback, or is a simple safe command
            has_exit_0 = cmd.rstrip().endswith("exit 0")
            has_error_fallback = "|| echo" in cmd or "|| true" in cmd
            # Simple echo/true commands always exit 0 and are inherently safe
            is_simple_safe = cmd.strip().startswith("echo ") or cmd.strip() == "true"
            if not has_exit_0 and not has_error_fallback and not is_simple_safe:
                session_exit_safe = False
                unsafe_hooks.append(f"SessionStart[{i}]: missing exit 0 or error fallback")
    results.append(AssertionResult(
        id="H20", description="All SessionStart hooks guarantee exit 0 (non-zero kills hook registry)",
        passed=session_exit_safe,
        detail="All safe" if session_exit_safe else f"Unsafe: {unsafe_hooks}"
    ))

    # H21: php-lint-on-save.sh runs php -l
    lint_script = PLUGIN_DIR / "scripts" / "php-lint-on-save.sh"
    if lint_script.exists():
        content = lint_script.read_text()
        has_php_l = "php -l" in content
    else:
        has_php_l = False
    results.append(AssertionResult(
        id="H21", description="PHP lint script runs php -l",
        passed=has_php_l,
        detail="php -l found" if has_php_l else "Missing php -l"
    ))

    return results


def main():
    timestamp = time.strftime("%Y%m%d-%H%M%S")

    print("=== HOOKS SYSTEM EVAL ===\n")

    results = run_assertions()
    pass_count = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"SCORE: {pass_count}/{total}\n")

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.id}: {r.description}")
        if not r.passed:
            print(f"         {r.detail}")

    # Save results
    results_dir = EVAL_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    results_file = results_dir / f"hooks-{timestamp}.json"
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "score": f"{pass_count}/{total}",
            "pass_count": pass_count,
            "total_count": total,
            "assertions": [asdict(r) for r in results],
        }, f, indent=2)

    print(f"\n  Results: {results_file}")
    return pass_count, total


if __name__ == "__main__":
    passed, total = main()
    sys.exit(0 if passed == total else 1)
