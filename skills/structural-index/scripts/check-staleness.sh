#!/bin/bash
# check-staleness.sh - Check if structural index is stale
# Usage: check-staleness.sh [project-dir]
# Reports which structural files need regeneration.
# Always exits 0 (advisory).
set -e

PROJECT_DIR="${1:-${CLAUDE_PROJECT_DIR:-$(pwd)}}"
STRUCTURAL_DIR="$PROJECT_DIR/docs/semantic/structural"
TIMESTAMP_FILE="$STRUCTURAL_DIR/.generated-at"

if [[ ! -f "$TIMESTAMP_FILE" ]]; then
    echo "STRUCTURAL INDEX: Not yet generated."
    echo "Run /structural-index to generate."
    exit 0
fi

GEN_TIME=$(cat "$TIMESTAMP_FILE")
echo "=== STRUCTURAL INDEX STALENESS CHECK ==="
echo "Generated at: $GEN_TIME"
echo ""

STALE=0

# Check services.yml files
STALE_SERVICES=$(find -L "$PROJECT_DIR" -newer "$TIMESTAMP_FILE" -name "*.services.yml" 2>/dev/null)
if [[ -n "$STALE_SERVICES" ]]; then
    echo "STALE: services.md (modified *.services.yml files):"
    echo "$STALE_SERVICES" | while read -r f; do echo "  - ${f#$PROJECT_DIR/}"; done
    STALE=1
fi

# Check routing.yml files
STALE_ROUTES=$(find -L "$PROJECT_DIR" -newer "$TIMESTAMP_FILE" -name "*.routing.yml" 2>/dev/null)
if [[ -n "$STALE_ROUTES" ]]; then
    echo "STALE: routes.md (modified *.routing.yml files):"
    echo "$STALE_ROUTES" | while read -r f; do echo "  - ${f#$PROJECT_DIR/}"; done
    STALE=1
fi

# Check .module files
STALE_MODULES=$(find -L "$PROJECT_DIR" -newer "$TIMESTAMP_FILE" -name "*.module" 2>/dev/null)
if [[ -n "$STALE_MODULES" ]]; then
    echo "STALE: hooks.md (modified *.module files):"
    echo "$STALE_MODULES" | while read -r f; do echo "  - ${f#$PROJECT_DIR/}"; done
    STALE=1
fi

# Check PHP files with plugin/entity annotations
STALE_PHP=$(find -L "$PROJECT_DIR" -newer "$TIMESTAMP_FILE" -name "*.php" \
    -path "*/modules/*" 2>/dev/null | head -50)
if [[ -n "$STALE_PHP" ]]; then
    # Only flag if they contain plugin/entity patterns
    PLUGIN_STALE=""
    while IFS= read -r php_file; do
        if grep -qlE '@(Block|FieldType|FieldFormatter|FieldWidget|Action|QueueWorker|ContentEntityType|ConfigEntityType)|#\[(Block|FieldType|FieldFormatter|FieldWidget|Action|QueueWorker|ContentEntityType|ConfigEntityType|Hook)' "$php_file" 2>/dev/null; then
            PLUGIN_STALE="${PLUGIN_STALE}"$'\n'"  - ${php_file#$PROJECT_DIR/}"
        fi
    done <<< "$STALE_PHP"

    if [[ -n "$PLUGIN_STALE" ]]; then
        echo "STALE: plugins.md / entities.md / hooks.md (modified PHP files with annotations):"
        printf '%s\n' "$PLUGIN_STALE"
        STALE=1
    fi
fi

# Check menu/task link files
STALE_LINKS=$(find -L "$PROJECT_DIR" -newer "$TIMESTAMP_FILE" \( -name "*.links.menu.yml" -o -name "*.links.task.yml" \) 2>/dev/null)
if [[ -n "$STALE_LINKS" ]]; then
    echo "STALE: routes.md (modified link definition files):"
    echo "$STALE_LINKS" | while read -r f; do echo "  - ${f#$PROJECT_DIR/}"; done
    STALE=1
fi

echo ""
if [[ "$STALE" -eq 0 ]]; then
    echo "Structural index is UP TO DATE."
else
    echo "Run /structural-index to regenerate stale files."
fi

exit 0
