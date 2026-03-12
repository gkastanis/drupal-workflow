---
description: "Load project context into session — feature map, business index, Logic IDs"
allowed-tools: Bash
---
# /drupal-prime - Load Session Context

## Purpose

Load the project's semantic documentation and structural index into the current session.

## Protocol

### Step 1: Run Prime

```bash
bash "$CLAUDE_PLUGIN_ROOT/skills/discover/scripts/prime.sh"
```

### Step 2: Output

Display the full result — feature map, business index, entity list, Logic ID counts, and available tech specs.
