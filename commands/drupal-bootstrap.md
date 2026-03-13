---
description: "Auto-detect project state and bootstrap structural index, semantic docs, and CLAUDE.md hint"
---
# /drupal-bootstrap - Project Bootstrap

## Purpose

Auto-detect project state and run the 3-step documentation pipeline as needed:

```
Step 1: Structural index   (deterministic bash scripts)
Step 2: Semantic docs       (AI-generated tech specs + business index)
Step 3: CLAUDE.md hint      (compact pointer injected into CLAUDE.md)
```

Only runs what's missing. Idempotent — safe to run repeatedly.

## Protocol

### Step 1: Detect Project State

```bash
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
```

Check in order:
1. Does `$PROJECT_DIR/docs/semantic/structural/.generated-at` exist?
2. Is the structural index stale? Run `$CLAUDE_PLUGIN_ROOT/skills/structural-index/scripts/check-staleness.sh "$PROJECT_DIR"`
3. Do `$PROJECT_DIR/docs/semantic/tech/*.md` files exist?
4. Does `$PROJECT_DIR/CLAUDE.md` contain `## Codebase`?

### Step 2: Generate Structural Index (Layer 2)

If structural index is missing or stale:

```bash
bash "$CLAUDE_PLUGIN_ROOT/skills/structural-index/scripts/generate-all.sh" "$PROJECT_DIR"
```

This is deterministic — bash scripts parse `*.services.yml`, `*.routing.yml`, hooks, plugins, entities. No AI involved.

### Step 3: Generate Semantic Docs (Layer 3)

If `docs/semantic/tech/*.md` does not exist:

> Structural index generated. No semantic docs found.
> Run `/drupal-semantic init` to generate tech specs with Logic IDs and business index.
> This spawns the `@semantic-architect` agent per feature (~5 min for a large project).

Do NOT generate semantic docs inline — they require the `@semantic-architect` agent which the user should invoke explicitly via `/drupal-semantic init`.

Skip to Step 5.

### Step 4: Inject CLAUDE.md Hint

If tech specs exist but `CLAUDE.md` has no `## Codebase` section:

```bash
bash "$CLAUDE_PLUGIN_ROOT/scripts/inject-claude-md.sh" "$PROJECT_DIR"
```

This injects the compact hint (~45 words) that drives +61% speed improvement.

### Step 5: Validate Tech Specs

If tech specs exist, run the validator:

```bash
bash "$CLAUDE_PLUGIN_ROOT/scripts/validate-tech-specs.sh" "$PROJECT_DIR"
```

Report any non-conforming files. Suggest `/drupal-semantic validate --fix` if errors found.

### Step 6: Report

Summarize what was done and what the user should do next:

| State | Action taken | Next step |
|-------|-------------|-----------|
| No structural index | Generated | `/drupal-semantic init` |
| Stale structural index | Regenerated | Ready |
| No semantic docs | Skipped (needs AI) | `/drupal-semantic init` |
| No CLAUDE.md hint | Injected | Ready |
| Validation errors | Reported | `/drupal-semantic validate --fix` |
| Everything fresh | Nothing | Ready to work |

### Step 7: Check for Duplicate Hooks

Read `$PROJECT_DIR/.claude/settings.json` if it exists. Warn the user if it contains:
- PreToolUse hooks matching `Read` or `Grep`
- PostToolUse hooks matching `Edit` or `Write`

These duplicate the plugin's built-in hooks and should be removed.
