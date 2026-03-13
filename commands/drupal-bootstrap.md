---
description: "Auto-detect project state and bootstrap semantic docs, structural index, and session context"
---
# /drupal-bootstrap - Project Bootstrap

## Purpose

Auto-detect project state and do the right thing. Generates missing documentation, builds structural index, and primes the session.

## Protocol

### Step 1: Detect Project State

```bash
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
```

Check in order:
1. Does `$PROJECT_DIR/docs/semantic/` exist?
2. Does `$PROJECT_DIR/docs/semantic/structural/` exist?
3. Is the structural index stale? Run `$CLAUDE_PLUGIN_ROOT/skills/structural-index/scripts/check-staleness.sh "$PROJECT_DIR"`

### Step 2: Handle — No Semantic Docs

If `docs/semantic/` does not exist:

1. Create the directory: `mkdir -p docs/semantic/`
2. Proceed to Step 3 (generate the structural index first — it's a prerequisite for semantic docs)
3. After structural index is generated, tell the user:

> No semantic docs found. Structural index generated successfully.
> Run `/drupal-semantic init` to generate business index, tech specs, and business schemas.

Do NOT generate semantic docs inline — they require the `@semantic-architect` agent which the user should invoke explicitly via `/drupal-semantic init`.

Then proceed to Step 3.

### Step 3: Handle — No Structural Index

If `docs/semantic/structural/` does not exist or is empty:

```bash
bash "$CLAUDE_PLUGIN_ROOT/skills/structural-index/scripts/generate-all.sh" "$PROJECT_DIR"
```

Then proceed to Step 5.

### Step 4: Handle — Stale Structural Index

If check-staleness.sh reports staleness:

```bash
bash "$CLAUDE_PLUGIN_ROOT/skills/structural-index/scripts/generate-all.sh" "$PROJECT_DIR"
```

Then proceed to Step 5.

### Step 5: Prime Session

Everything is ready. Load context:

```bash
bash "$CLAUDE_PLUGIN_ROOT/skills/discover/scripts/prime.sh"
```

Output the result to give the user the full feature map, business index, entity list, Logic ID counts, and available tech specs.

### Step 6: Check for Duplicate Hooks

Read `$PROJECT_DIR/.claude/settings.json` if it exists. Warn the user if it contains:
- PreToolUse hooks matching `Read` or `Grep`
- PostToolUse hooks matching `Edit` or `Write`

These duplicate the plugin's built-in hooks and should be removed.
