#!/bin/bash
# php-lint-on-save.sh
# PostToolUse Hook - Run php -l on PHP files after Edit/Write operations.
# Exit 0 on success or non-PHP file, exit 1 on lint failure.

# Read JSON input from stdin (Claude hook provides tool use context as JSON)
INPUT_JSON=$(cat)

# Extract file_path from the JSON
FILE_PATH=""
if command -v jq >/dev/null 2>&1; then
    FILE_PATH=$(echo "$INPUT_JSON" | jq -r '.tool_input.file_path // ""' 2>/dev/null)
fi

# Fallback to grep if jq unavailable or returned null
if [ -z "$FILE_PATH" ] || [ "$FILE_PATH" = "null" ]; then
    FILE_PATH=$(echo "$INPUT_JSON" | grep -o '"file_path":"[^"]*"' | head -1 | cut -d'"' -f4)
fi

# If no file path found, allow (might be a non-file operation)
if [ -z "$FILE_PATH" ] || [ "$FILE_PATH" = "null" ]; then
    exit 0
fi

# Check if the file extension matches PHP-related extensions
case "$FILE_PATH" in
    *.php|*.module|*.inc|*.install|*.theme)
        # Run PHP lint check
        LINT_OUTPUT=$(php -l "$FILE_PATH" 2>&1)
        LINT_EXIT=$?

        if [ $LINT_EXIT -ne 0 ]; then
            echo "PHP LINT FAILURE: $FILE_PATH" >&2
            echo "$LINT_OUTPUT" >&2
            exit 1
        fi
        ;;
    *)
        # Not a PHP file, skip linting
        ;;
esac

exit 0
