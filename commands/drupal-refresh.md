---
description: "Regenerate structural index and reload session context"
allowed-tools: Bash
---
# /drupal-refresh - Regenerate and Reload

## Purpose

Regenerate the structural index from current codebase state, then reload session context.

## Protocol

### Step 1: Regenerate Structural Index

```bash
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
bash "$CLAUDE_PLUGIN_ROOT/skills/structural-index/scripts/generate-all.sh" "$PROJECT_DIR"
```

Report what was generated (service count, route count, hook count, entity count, etc.).

### Step 2: Reload Session Context

```bash
bash "$CLAUDE_PLUGIN_ROOT/skills/discover/scripts/prime.sh"
```

### Step 3: Check Staleness

```bash
bash "$CLAUDE_PLUGIN_ROOT/skills/structural-index/scripts/check-staleness.sh" "$PROJECT_DIR"
```

Show any staleness warnings. If everything is fresh, confirm the index is up to date.
