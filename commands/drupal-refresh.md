---
description: "Regenerate structural index and update CLAUDE.md hint"
allowed-tools: Bash
---
# /drupal-refresh - Regenerate Structural Index

## Purpose

Regenerate the structural index (Layer 2) from current codebase state. This is Step 1 of the 3-step pipeline.

## Protocol

### Step 0: Resolve Environment

```bash
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
PLUGIN_ROOT=$(cat /tmp/drupal-workflow-plugin-root 2>/dev/null || echo "${CLAUDE_PLUGIN_ROOT:-}")
```

### Step 1: Regenerate Structural Index

```bash
bash "$PLUGIN_ROOT/skills/structural-index/scripts/generate-all.sh" "$PROJECT_DIR"
```

Report what was generated (service count, route count, hook count, entity count, etc.).

### Step 2: Update CLAUDE.md Hint

If tech specs exist, update the CLAUDE.md Codebase section to keep counts in sync:

```bash
bash "$PLUGIN_ROOT/scripts/inject-claude-md.sh" "$PROJECT_DIR"
```

### Step 3: Check Staleness

```bash
bash "$PLUGIN_ROOT/skills/structural-index/scripts/check-staleness.sh" "$PROJECT_DIR"
```

Show any staleness warnings. If everything is fresh, confirm the index is up to date.

### Step 4: Suggest Next Steps

If no `docs/semantic/tech/*.md` exist, suggest:
> Run `/drupal-semantic init` to generate tech specs with Logic IDs.
