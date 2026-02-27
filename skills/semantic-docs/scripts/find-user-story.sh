#!/bin/bash
# Find user story and linked Logic IDs
# Usage: find-user-story.sh <USER_STORY_ID>
# Example: find-user-story.sh US-004

US_ID="$1"
DOCS_DIR="${DOCS_DIR:-docs/semantic}"

if [ -z "$US_ID" ]; then
  echo "Usage: find-user-story.sh <USER_STORY_ID>"
  echo "Examples: US-001, US-004, US-010"
  echo ""
  echo "Listing all user stories..."
  grep -E "^\- \*\*\[US-[0-9]+\]" "$DOCS_DIR/00_BUSINESS_INDEX.md" 2>/dev/null | head -20
  exit 1
fi

# Normalize format (ensure US- prefix)
if [[ ! "$US_ID" =~ ^US- ]]; then
  US_ID="US-$US_ID"
fi

echo "=== User Story: $US_ID ==="
echo ""

# Find in business index
RESULT=$(grep -E "\[$US_ID\]" "$DOCS_DIR/00_BUSINESS_INDEX.md" 2>/dev/null)

if [ -n "$RESULT" ]; then
  echo "$RESULT"
  echo ""

  # Extract Logic IDs from the user story
  LOGIC_IDS=$(echo "$RESULT" | grep -oE '[A-Z]{3,4}-L[0-9]+' | sort -u)

  if [ -n "$LOGIC_IDS" ]; then
    echo "=== Linked Logic IDs ==="
    echo "$LOGIC_IDS"
    echo ""
    echo "Use 'find-logic-id.sh <ID>' to trace each to code."
  fi
else
  echo "User story '$US_ID' not found."
  echo ""
  echo "Available user stories:"
  grep -E "^\- \*\*\[US-[0-9]+\]" "$DOCS_DIR/00_BUSINESS_INDEX.md" 2>/dev/null | head -15
fi
