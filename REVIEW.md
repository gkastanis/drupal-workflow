# Plugin Review: drupal-workflow v1.5.5

**Date**: 2026-03-13
**Reviewer**: Claude (automated best-practices review)
**Scope**: Full plugin — 4 agents, 15 skills, 10 commands, 7 scripts, hooks, metadata

---

## CRITICAL Issues

### 1. Malformed YAML frontmatter in `skills/drupal-hook-patterns/SKILL.md`

The file starts with `# Drupal Hook Patterns` on line 1 instead of `---`. The frontmatter fields (`name:`, `description:`) are present but not wrapped in `---` delimiters. Claude Code will not parse this skill correctly.

**Fix**: Add `---` as the first line and a closing `---` after the `description:` block.

### 2. Version mismatch between `plugin.json` and `marketplace.json`

- `plugin.json`: version `1.5.5`
- `marketplace.json` metadata: version `1.5.4`
- `marketplace.json` plugins[0]: version `1.5.4`

**Fix**: Sync `marketplace.json` versions to `1.5.5`.

### 3. `$PLUGIN_DIR` undefined in `commands/drupal-semantic.md`

All other commands use `$CLAUDE_PLUGIN_ROOT` (the official env var set by Claude Code), but `drupal-semantic.md` references `$PLUGIN_DIR` in 8 places (lines 99, 109, 142, 246, 256, 280, 286, 303). This variable is never defined — those script invocations will fail.

**Fix**: Replace all `$PLUGIN_DIR` references with `$CLAUDE_PLUGIN_ROOT`.

---

## HIGH Issues

### 4. Log files write to world-readable `/tmp` paths

- `scripts/lib/hook-utils.sh:6` → `/tmp/test-driven-handoff.log`
- `scripts/block-sensitive-files.sh:8` → `/tmp/blocked-sensitive-files.log`
- `scripts/subagent-context-inject.sh:23` → `/tmp/subagent-context-inject.log`

These logs could expose file access patterns and project paths to other users on shared systems.

**Fix**: Use `$HOME/.cache/drupal-workflow/` or `mktemp -d` with restrictive permissions.

### 5. `hooks.json` references `TaskCompleted` event

The `TaskCompleted` hook event (line 61-69) may not be a standard Claude Code hook event. Verify this is a supported event name in the Claude Code plugin spec. If unsupported, the quality gate reminder never fires.

### 6. `teammate-quality-gate.sh` reads `CLAUDE_TOOL_OUTPUT` env var instead of stdin

Line 9: `TOOL_OUTPUT="${CLAUDE_TOOL_OUTPUT:-}"` — the hook system provides JSON on stdin (like all other hooks in this plugin), but this script reads from an env var. This means the `has_verification()` check likely always runs against an empty string, making the reminder fire on every task completion.

**Fix**: Read from stdin like the other hooks, or verify the env var is actually provided for this event type.

---

## MEDIUM Issues

### 7. `block-sensitive-files.sh` blocks `development.services.yml`

Lines 172-176: Drupal's `development.services.yml` typically contains only debugging settings (twig debug, cache disable) — not credentials. Blocking it may frustrate developers.

**Fix**: Consider allowing `development.services.yml` or making it configurable.

### 8. No `set -e` in most scripts

Only `inject-claude-md.sh` and `validate-tech-specs.sh` use `set -e`. The other 5 scripts silently swallow intermediate command failures.

### 9. `hook-utils.sh` log file name is misleading

Default log file is `test-driven-handoff.log` — a remnant from an earlier version. Should reflect current purpose (e.g., `drupal-workflow-hooks.log`).

### 10. `SubagentStart` hook warns about non-plugin agents

Any subagent not matching the 4 plugin-defined agents triggers a warning. This produces false positives for Claude Code's built-in agents or agents from other plugins.

### 11. `SessionStart` inline command is fragile

`hooks.json` line 15: The structural index auto-regeneration is a 200+ character inline command. Should be extracted to a standalone script.

---

## LOW Issues

### 12. `marketplace.json` email field uses handle, not email

Line 5: `"email": "github@gkastanis"` — not a valid email format.

### 13. `staleness-check.sh` references wrong command

Line 65: `Run /structural-index to regenerate` — the actual command is `/drupal-refresh`.

### 14. `drupal-bootstrap.md` Step 2 flow is confusing

Step 2 says "Proceed to Step 3" twice with different conditions, making the control flow unclear.

### 15. Agent model selection for reviewer

`drupal-reviewer` uses `sonnet` — given its security audit responsibilities, consider `opus` for better vulnerability detection.

---

## Strengths

- Excellent 3-layer doc architecture (raw → structural → semantic)
- Real evaluation data with methodology in README
- Thorough 6-step duplicate prevention in builder agent
- Well-implemented sensitive file blocker with allowlist
- Effective verification gate preventing false claims
- Automatic structural index staleness detection

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 3 |
| High | 3 |
| Medium | 5 |
| Low | 4 |

The plugin is well-architected with strong Drupal domain knowledge. The 3 critical issues (broken frontmatter, undefined `$PLUGIN_DIR`, version mismatch) cause runtime failures and should be fixed immediately.
