#!/bin/bash
# Find Logic ID and return code mapping
# Usage: find-logic-id.sh <LOGIC_ID>
# Example: find-logic-id.sh AUTH-L2

LOGIC_ID="$1"
DOCS_DIR="${DOCS_DIR:-docs/semantic}"

if [ -z "$LOGIC_ID" ]; then
  echo "Usage: find-logic-id.sh <LOGIC_ID>"
  echo "Examples: AUTH-L2, ACCS-L3, MIGR-L1"
  exit 1
fi

# Extract feature prefix (e.g., AUTH from AUTH-L2)
FEATURE=$(echo "$LOGIC_ID" | sed 's/-L[0-9]*$//')

# Find in tech docs
TECH_FILE=$(find "$DOCS_DIR/tech" -name "${FEATURE}_*.md" 2>/dev/null | head -1)

if [ -n "$TECH_FILE" ]; then
  echo "=== Logic ID: $LOGIC_ID ==="
  echo "Feature: $FEATURE"
  echo "Tech Doc: $TECH_FILE"
  echo ""
  echo "=== Code Mapping ==="
  # Get the mapping table row - try different formats
  grep -E "\*\*\[?${LOGIC_ID}\]?\*\*" "$TECH_FILE" -A 0 2>/dev/null || \
  grep -E "\| \*\*${LOGIC_ID}\*\* \|" "$TECH_FILE" 2>/dev/null || \
  grep "$LOGIC_ID" "$TECH_FILE" -B 1 -A 1 2>/dev/null

  echo ""
  echo "=== Context ==="
  # Show surrounding context if in a table
  grep -n "$LOGIC_ID" "$TECH_FILE" | head -3
else
  # Fall back to business index
  echo "Feature '$FEATURE' not found in tech docs."
  echo ""
  echo "Searching Business Index..."
  grep "$LOGIC_ID" "$DOCS_DIR/00_BUSINESS_INDEX.md" -B 2 -A 2 2>/dev/null || \
  echo "Logic ID '$LOGIC_ID' not found in documentation."
fi
