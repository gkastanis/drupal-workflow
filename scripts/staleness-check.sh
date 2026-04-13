#!/bin/bash
# staleness-check.sh
# PostToolUse Hook - Advisory check if edited file affects structural index.
# Always exits 0 (advisory only, never blocks).

INPUT_JSON=$(cat)

# Extract file_path (try file_path first, then path)
FILE_PATH=""
if command -v jq >/dev/null 2>&1; then
    FILE_PATH=$(echo "$INPUT_JSON" | jq -r '.tool_input.file_path // .tool_input.path // ""' 2>/dev/null)
fi
if [ -z "$FILE_PATH" ] || [ "$FILE_PATH" = "null" ]; then
    FILE_PATH=$(echo "$INPUT_JSON" | grep -o '"file_path":"[^"]*"' | head -1 | cut -d'"' -f4)
fi
if [ -z "$FILE_PATH" ] || [ "$FILE_PATH" = "null" ]; then
    FILE_PATH=$(echo "$INPUT_JSON" | grep -o '"path":"[^"]*"' | head -1 | cut -d'"' -f4)
fi

if [ -z "$FILE_PATH" ] || [ "$FILE_PATH" = "null" ]; then
    exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
STRUCTURAL_DIR="$PROJECT_DIR/docs/semantic/structural"
TECH_DIR="$PROJECT_DIR/docs/semantic/tech"

# Only check if structural index exists
if [[ ! -f "$STRUCTURAL_DIR/.generated-at" ]]; then
    exit 0
fi

# Early exit for clearly non-structural file types.
case "$FILE_PATH" in
    *.md|*.sh|*.json|*.txt|*.css|*.js|*.twig|*.html) exit 0 ;;
esac

# Check if file is a structural source (services.yml, routing.yml, .module, .install, etc.)
STALE_TYPE=""
case "$FILE_PATH" in
    *.services.yml)  STALE_TYPE="services" ;;
    *.routing.yml)   STALE_TYPE="routes" ;;
    *.module)         STALE_TYPE="hooks" ;;
    *.install)        STALE_TYPE="hooks" ;;
    *.permissions.yml) STALE_TYPE="permissions" ;;
    *.info.yml)       STALE_TYPE="dependencies" ;;
    *.links.menu.yml|*.links.task.yml) STALE_TYPE="routes" ;;
esac

# Check for plugin/entity annotations in PHP files
if [[ -z "$STALE_TYPE" ]] && [[ "$FILE_PATH" == *.php ]]; then
    if grep -qE '@(Block|FieldType|FieldFormatter|FieldWidget|Action|QueueWorker|ContentEntityType|ConfigEntityType)|#\[(Block|FieldType|FieldFormatter|FieldWidget|Action|QueueWorker|ContentEntityType|ConfigEntityType)' "$FILE_PATH" 2>/dev/null; then
        STALE_TYPE="plugins/entities"
    fi
    if grep -qE '#\[Hook\(' "$FILE_PATH" 2>/dev/null; then
        STALE_TYPE="hooks"
    fi
    # Public method changes affect the method index
    if grep -qE '^\s*public\s+(static\s+)?function\s+' "$FILE_PATH" 2>/dev/null; then
        if echo "$FILE_PATH" | grep -qE '/src/(Service|Controller|Form|EventSubscriber|Access|Manager|Builder)/'; then
            STALE_TYPE="${STALE_TYPE:+$STALE_TYPE+}methods"
        fi
    fi
fi

# Check if file is referenced in tech specs
TECH_MATCH=""
if [[ -d "$TECH_DIR" ]] && [[ -n "$FILE_PATH" ]]; then
    BASENAME=$(basename "$FILE_PATH")
    if grep -rlq "$BASENAME" "$TECH_DIR" 2>/dev/null; then
        TECH_MATCH="yes"
    fi
fi

# Advisory output
if [[ -n "$STALE_TYPE" ]]; then
    echo "STRUCTURAL INDEX: $FILE_PATH affects $STALE_TYPE index. Run /structural-index to regenerate."
fi

if [[ -n "$TECH_MATCH" ]]; then
    echo "SEMANTIC DOCS: $FILE_PATH is referenced in tech specs. Check Logic IDs are still accurate."
fi

exit 0
