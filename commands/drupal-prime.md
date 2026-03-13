---
description: "Load full project context into session (debug/overview — heavy, ~2500 tokens)"
allowed-tools: Bash
---
# /drupal-prime - Load Full Session Context

## Purpose

Dump the full project overview into the conversation: feature map, business index, entity list, Logic ID counts, and available tech specs. This is a **debug/overview** command (~2500 tokens).

For normal workflows, the CLAUDE.md `## Codebase` hint (~45 words) is sufficient — the agent reads it automatically. Use `/drupal-semantic inject` to update that hint instead.

## Protocol

### Step 1: Run Prime

```bash
bash "$CLAUDE_PLUGIN_ROOT/skills/discover/scripts/prime.sh"
```

### Step 2: Output

Display the full result.
