#!/bin/bash
# Trace from Logic ID to actual source code
# Usage: trace-code.sh <LOGIC_ID>
# Example: trace-code.sh AUTH-L2

LOGIC_ID="$1"
DOCS_DIR="${DOCS_DIR:-docs/semantic}"

if [ -z "$LOGIC_ID" ]; then
  echo "Usage: trace-code.sh <LOGIC_ID>"
  echo "Example: trace-code.sh AUTH-L2"
  exit 1
fi

# Get feature prefix
FEATURE=$(echo "$LOGIC_ID" | sed 's/-L[0-9]*$//')
TECH_FILE=$(find "$DOCS_DIR/tech" -iname "${FEATURE}_*.md" 2>/dev/null | head -1)

if [ -z "$TECH_FILE" ]; then
  echo "Feature '$FEATURE' not found"
  exit 1
fi

echo "=== Tracing: $LOGIC_ID ==="
echo "Tech Doc: $TECH_FILE"
echo ""

# Extract the mapping line from the table
MAPPING=$(grep -E "\| \*\*\[?${LOGIC_ID}\]?\*\* \|" "$TECH_FILE" 2>/dev/null | head -1)

if [ -z "$MAPPING" ]; then
  MAPPING=$(grep "$LOGIC_ID" "$TECH_FILE" 2>/dev/null | head -1)
fi

if [ -z "$MAPPING" ]; then
  echo "Logic ID '$LOGIC_ID' not found in tech doc."
  exit 1
fi

echo "=== Mapping ==="
echo "$MAPPING"
echo ""

# Extract file path from mapping (looks for paths in backticks)
FILE_PATH=$(echo "$MAPPING" | grep -oP '`/[^`]+\.(php|module|yml|inc)`' | head -1 | tr -d '`')

if [ -z "$FILE_PATH" ]; then
  # Try without leading slash
  FILE_PATH=$(echo "$MAPPING" | grep -oP '`[^`]+\.(php|module|yml|inc)`' | head -1 | tr -d '`')
fi

# Extract function/method name - try multiple patterns
FUNC=$(echo "$MAPPING" | grep -oP '`[a-zA-Z_]+\(\)`' | head -1 | tr -d '`()')

if [ -z "$FUNC" ]; then
  # Try hook_* pattern
  FUNC=$(echo "$MAPPING" | grep -oP 'hook_[a-zA-Z_]+' | head -1)
fi

if [ -z "$FUNC" ]; then
  # Try ::methodName pattern
  FUNC=$(echo "$MAPPING" | grep -oP '::[a-zA-Z_]+' | head -1 | tr -d ':')
fi

echo "=== Source Location ==="
echo "Documented path: $FILE_PATH"
echo "Function/Hook: $FUNC"
echo ""

if [ -n "$FILE_PATH" ]; then
  # Remove leading slash for find
  SEARCH_PATH=$(echo "$FILE_PATH" | sed 's/^\///')

  # Try to find the actual file (check common Drupal paths)
  ACTUAL_FILE=$(find . -path "*$SEARCH_PATH" 2>/dev/null | head -1)

  if [ -z "$ACTUAL_FILE" ]; then
    # Try just the filename in custom modules
    FILENAME=$(basename "$FILE_PATH")
    ACTUAL_FILE=$(find . -name "$FILENAME" \( -path "*modules/custom*" -o -path "*www/modules/custom*" -o -path "*web/modules/custom*" \) 2>/dev/null | head -1)
  fi

  if [ -n "$ACTUAL_FILE" ]; then
    echo "Actual file: $ACTUAL_FILE"

    if [ -n "$FUNC" ]; then
      echo ""
      echo "=== Code Preview ==="

      # For hooks, search for the implementation (module_name_hook_name pattern)
      if [[ "$FUNC" == hook_* ]]; then
        # Extract hook name without hook_ prefix
        HOOK_NAME=$(echo "$FUNC" | sed 's/^hook_//')
        # Search for any implementation of this hook
        grep -n "_${HOOK_NAME}\|Implements ${FUNC}" "$ACTUAL_FILE" -A 20 2>/dev/null | head -30
      else
        # Regular function search
        grep -n "function.*$FUNC\|public function $FUNC\|protected function $FUNC\|private function $FUNC" "$ACTUAL_FILE" -A 15 2>/dev/null | head -25
      fi

      if [ $? -ne 0 ]; then
        # Fallback: just search for the function name
        echo "Searching for '$FUNC'..."
        grep -n "$FUNC" "$ACTUAL_FILE" -B 2 -A 10 2>/dev/null | head -20
      fi
    fi
  else
    echo "File not found in codebase. Path may have changed."
    echo ""
    echo "Try searching manually:"
    echo "  find . -name '$(basename "$FILE_PATH")' -type f"
  fi
else
  echo "Could not extract file path from mapping."
  echo ""
  echo "Full mapping line:"
  echo "$MAPPING"
fi
