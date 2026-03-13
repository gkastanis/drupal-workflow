---
description: "Check documentation, structural index, and staleness status"
allowed-tools: Bash
---
# /drupal-status - Project Status Check

## Purpose

Report current state of semantic docs, structural index, and staleness. Suggest the appropriate next command.

## Protocol

### Step 1: Check Discovery Status

```bash
bash "$CLAUDE_PLUGIN_ROOT/skills/discover/scripts/discover.sh" --status
```

### Step 2: Check Staleness

```bash
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
bash "$CLAUDE_PLUGIN_ROOT/skills/structural-index/scripts/check-staleness.sh" "$PROJECT_DIR"
```

### Step 3: Suggest Next Action

Based on results:
- **No semantic docs** — Suggest `/drupal-bootstrap`
- **No structural index or stale** — Suggest `/drupal-refresh`
- **Everything fresh** — Ready to work (CLAUDE.md hint provides context automatically)
