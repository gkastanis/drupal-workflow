#!/bin/bash
# Find full technical spec for a feature
# Usage: find-feature.sh <FEATURE_CODE>
# Example: find-feature.sh AUTH

FEATURE="$1"
DOCS_DIR="${DOCS_DIR:-docs/semantic}"

if [ -z "$FEATURE" ]; then
  echo "Usage: find-feature.sh <FEATURE_CODE>"
  echo "Examples: AUTH, ACCS, MIGR, VIEW, FORM"
  echo ""
  echo "Available features:"
  ls "$DOCS_DIR/tech"/*.md 2>/dev/null | sed 's/.*\///' | sed 's/_.*$//' | sort -u
  exit 1
fi

# Convert to uppercase for matching
FEATURE_UPPER=$(echo "$FEATURE" | tr '[:lower:]' '[:upper:]')

TECH_FILE=$(find "$DOCS_DIR/tech" -iname "${FEATURE_UPPER}_*.md" 2>/dev/null | head -1)

if [ -z "$TECH_FILE" ]; then
  # Try case-insensitive search
  TECH_FILE=$(find "$DOCS_DIR/tech" -iname "${FEATURE}_*.md" 2>/dev/null | head -1)
fi

if [ -n "$TECH_FILE" ]; then
  echo "=== Technical Spec: $FEATURE_UPPER ==="
  echo "File: $TECH_FILE"
  echo ""
  cat "$TECH_FILE"
else
  echo "Feature '$FEATURE' not found."
  echo ""
  echo "Available features:"
  ls "$DOCS_DIR/tech"/*.md 2>/dev/null | sed 's/.*\///' | sed 's/_.*$//' | sort -u

  echo ""
  echo "Searching business index for '$FEATURE'..."
  grep -i "$FEATURE" "$DOCS_DIR/00_BUSINESS_INDEX.md" | head -10
fi
