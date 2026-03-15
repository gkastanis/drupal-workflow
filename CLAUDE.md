# CLAUDE.md — drupal-workflow plugin development guide

## What This Is

A Claude Code plugin for Drupal 10/11 development. 16 skills, 4 agents, 10 commands, quality-gate hooks. Three-layer documentation architecture: structural index (bash scripts) → semantic docs (AI-generated tech specs) → CLAUDE.md hint.

## Quick Start (Development)

```bash
# Run all static evals (must pass before committing)
python3 eval/eval-skills.py && python3 eval/eval-agents.py && python3 eval/eval-hooks.py

# Run live integration test (requires a Drupal project)
bash eval/eval-hooks-integration.sh /path/to/drupal-project

# Validate all bash scripts
for f in scripts/*.sh skills/structural-index/scripts/*.sh; do bash -n "$f"; done

# Validate JSON
python3 -m json.tool hooks/hooks.json > /dev/null
python3 -m json.tool .claude-plugin/plugin.json > /dev/null
```

## Critical Rules

### Hook Exit Codes (CRITICAL)

**A SessionStart hook exiting non-zero kills the ENTIRE hook registry for the session.** All PreToolUse, PostToolUse, SubagentStart, and TaskCompleted hooks silently stop working. No error message — they just don't fire.

Every SessionStart hook command MUST either:
- End with `; exit 0`
- Use `|| echo 'message'` or `|| true` to swallow errors
- Be a simple command that cannot fail (e.g., `echo`)

Enforced by eval assertion H20. Discovered 2026-03-14 after weeks of silent quality gate failure.

### Plugin Cache Sync

The plugin runs from `~/.claude/plugins/cache/drupal-workflow/drupal-workflow/VERSION/`, NOT from `~/.claude/plugins/marketplaces/drupal-workflow/`. After `git push`, you must sync the cache:

```bash
git -C ~/.claude/plugins/marketplaces/drupal-workflow pull origin main
\cp -f ~/.claude/plugins/marketplaces/drupal-workflow/hooks/hooks.json \
       ~/.claude/plugins/cache/drupal-workflow/drupal-workflow/VERSION/hooks/hooks.json
```

Or copy all files: `rsync -a --exclude=.git ~/.claude/plugins/marketplaces/drupal-workflow/ ~/.claude/plugins/cache/drupal-workflow/drupal-workflow/VERSION/`

### Column Parsing in Generators

Downstream consumers (generate-feature-map.sh, generate-dependency-graph.sh) use named column parsing — they find the "Module" column by scanning the header row, not by hardcoded positional index. This eliminates silent column mismatch bugs when generators add or remove columns (e.g., the Fields column in entities.md).

If you add a new structural table consumed by feature-map, ensure it has a "Module" column header.

## Architecture

```
skills/                          # 16 SKILL.md files (auto-detected by Claude Code)
  structural-index/scripts/      # 13 bash generators (Layer 2 — deterministic)
agents/                          # 4 agent .md files (frontmatter: name, tools, skills, model)
commands/                        # 10 slash command .md files
hooks/hooks.json                 # 5 event types, 8 hook entries
scripts/                         # 7 hook scripts + lib/
  validate-semantic-docs.sh      # SessionStart: checks tech specs vs codebase
  block-sensitive-files.sh       # PreToolUse: blocks settings.php, .env, credentials
  php-lint-on-save.sh            # PostToolUse: php -l on PHP file edits
  staleness-check.sh             # PostToolUse: warns when structural source files change
  subagent-context-inject.sh     # SubagentStart: injects Drupal context
  teammate-quality-gate.sh       # TaskCompleted: checks for verification evidence
  inject-claude-md.sh            # Called by commands, not hooks
  validate-tech-specs.sh         # Called by commands, not hooks
eval/                            # 7 static evals + 1 integration test
```

## Adding Components

### New Skill

1. Create `skills/name/SKILL.md` with `name:` and `description:` frontmatter
2. Add to README skills table
3. Add to relevant agents' `skills:` frontmatter
4. Run `python3 eval/eval-skills.py` — new skill gets 7 universal assertions automatically

### New Agent

1. Create `agents/name.md` with frontmatter (name, description, tools, model, skills)
2. Only reference skills that exist in `skills/`
3. Add to README agents table
4. Run `python3 eval/eval-agents.py`

### New Hook

1. Add entry to `hooks/hooks.json` (must have `type`, `command`, `timeout`)
2. If SessionStart: MUST guarantee exit 0 (see Critical Rules above)
3. Create script in `scripts/` if needed, make executable
4. Run `python3 eval/eval-hooks.py`

### New Generator Script

1. Create in `skills/structural-index/scripts/`
2. Call from `generate-all.sh`
3. Document the column layout if producing a markdown table
4. Update `generate-feature-map.sh` column indices if the new output is consumed there

## Counts to Keep in Sync

When adding skills/agents/commands, update ALL of these:
- `README.md` (header line, section header, skills table, project structure)
- `.claude-plugin/plugin.json` description
- `.claude-plugin/marketplace.json` description
- `docs/PLUGIN_REVIEW_REPORT.md` (skills table, agent table, eval counts)
- `docs/DEVELOPER_DEPLOYMENT_GUIDE.md` (directory listing, eval counts)

The static eval catches skill/agent/hook structural issues but does NOT check that README counts match reality. Verify manually.

## Testing on a Drupal Project

The generators and hooks are tested against real Drupal projects. The default test project is timan at `/home/zorz/sites/timan`.

```bash
# Generate structural index
skills/structural-index/scripts/generate-all.sh /path/to/project

# Validate semantic docs
scripts/validate-semantic-docs.sh /path/to/project

# Test sensitive file blocking
echo '{"tool_input":{"file_path":"/path/to/project/web/sites/default/settings.php"}}' | \
  bash scripts/block-sensitive-files.sh

# Test staleness detection
echo '{"tool_input":{"file_path":"/path/to/project/web/modules/custom/mod/mod.services.yml"}}' | \
  CLAUDE_PROJECT_DIR=/path/to/project bash scripts/staleness-check.sh
```

## stream-json Behavior in claude -p

When testing hooks via `claude -p --output-format stream-json`:
- SessionStart hook events appear as `system` messages with `subtype: hook_response`
- PreToolUse and PostToolUse hook events do NOT appear in stream-json
- To verify Pre/PostToolUse hooks: check the assistant's text response or file modifications
- Plain text `claude -p` output goes empty when run in subshells — use `(cd dir && claude -p ...) > file 2>&1`

## Commit Convention

```
<type>: <description>

Types: feat, fix, refactor, docs, test, chore, perf, ci
```

No co-authored-by attribution (disabled in user settings).
