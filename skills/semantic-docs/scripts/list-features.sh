#!/bin/bash
# List all documented features
# Usage: list-features.sh

DOCS_DIR="${DOCS_DIR:-docs/semantic}"

echo "=== Documented Features ==="
echo ""

# Check if business index exists
if [ -f "$DOCS_DIR/00_BUSINESS_INDEX.md" ]; then
  # Extract feature registry table
  echo "From Business Index:"
  echo ""

  # Find and display the feature registry table
  sed -n '/Feature Registry/,/High-Level User Stories/p' "$DOCS_DIR/00_BUSINESS_INDEX.md" 2>/dev/null | \
    grep -E "^\| \*\*[A-Z]+" | head -30

  echo ""
  echo "---"
fi

# List tech doc files
echo ""
echo "Tech Spec Files:"
echo ""

for file in "$DOCS_DIR/tech"/*.md; do
  if [ -f "$file" ]; then
    FILENAME=$(basename "$file")
    FEATURE=$(echo "$FILENAME" | sed 's/_.*$//')
    TITLE=$(grep -m1 "^# " "$file" 2>/dev/null | sed 's/^# //')
    echo "  $FEATURE - $TITLE"
  fi
done 2>/dev/null

echo ""
echo "---"
echo "Total features: $(ls "$DOCS_DIR/tech"/*.md 2>/dev/null | wc -l)"
