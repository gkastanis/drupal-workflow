#!/bin/bash
# project-state-check.sh
# SessionStart hook: detect project documentation state and hint the next step.
# Chain: /drupal-bootstrap (structural index) → /drupal-semantic init (tech specs
#        + business index + CLAUDE.md hint via @semantic-architect agent).
# Outputs the first gap found and its fix command. Exit 0 always.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
STRUCTURAL_DIR="$PROJECT_DIR/docs/semantic/structural"
TECH_DIR="$PROJECT_DIR/docs/semantic/tech"
BUSINESS_INDEX="$PROJECT_DIR/docs/semantic/00_BUSINESS_INDEX.md"

# --- Step 1: Structural index (bash scripts) ---
if [[ ! -f "$STRUCTURAL_DIR/.generated-at" ]]; then
    echo "DOCS: No structural index. Next: /drupal-bootstrap"
    exit 0
fi

# Auto-regenerate if stale.
STALE=$(find "$PROJECT_DIR" -newer "$STRUCTURAL_DIR/.generated-at" \
    \( -name '*.services.yml' -o -name '*.routing.yml' -o -name '*.module' -o -name '*.permissions.yml' \) \
    -path '*/modules/*' 2>/dev/null | head -1)
if [[ -n "$STALE" ]]; then
    bash "$PLUGIN_ROOT/skills/structural-index/scripts/generate-all.sh" "$PROJECT_DIR" >/dev/null 2>&1 \
        && echo "STRUCTURAL INDEX: Auto-regenerated (source files changed)." \
        || echo "STRUCTURAL INDEX: Auto-regeneration failed (non-critical)."
fi

# --- Step 2: Semantic docs (@semantic-architect agent) ---
TECH_SPECS=("$TECH_DIR"/*.md)
if [[ ! -d "$TECH_DIR" ]] || [[ ! -f "${TECH_SPECS[0]}" ]]; then
    echo "DOCS: Structural index OK. Next: /drupal-semantic init"
    exit 0
fi

if [[ ! -f "$BUSINESS_INDEX" ]]; then
    echo "DOCS: Tech specs exist but no business index. Next: /drupal-semantic index"
    exit 0
fi

# --- All layers present: run validation ---
bash "$PLUGIN_ROOT/scripts/validate-semantic-docs.sh" "$PROJECT_DIR" 2>/dev/null

exit 0
