#!/bin/bash
# Find entity schema
# Usage: find-entity.sh <ENTITY_NAME>
# Example: find-entity.sh user

ENTITY="$1"
DOCS_DIR="${DOCS_DIR:-docs/semantic}"

if [ -z "$ENTITY" ]; then
  echo "Usage: find-entity.sh <ENTITY_NAME>"
  echo "Examples: user, node_article, paragraph_text"
  echo ""
  echo "Available schemas:"
  ls "$DOCS_DIR/schemas"/*.json 2>/dev/null | sed 's/.*\///' | sed 's/\.json$//'
  exit 1
fi

# Try exact match first
SCHEMA_FILE="$DOCS_DIR/schemas/${ENTITY}.json"

if [ ! -f "$SCHEMA_FILE" ]; then
  # Try with underscore variations
  SCHEMA_FILE=$(find "$DOCS_DIR/schemas" -iname "*${ENTITY}*.json" 2>/dev/null | head -1)
fi

if [ -n "$SCHEMA_FILE" ] && [ -f "$SCHEMA_FILE" ]; then
  echo "=== Entity Schema: $ENTITY ==="
  echo "File: $SCHEMA_FILE"
  echo ""

  # Check if jq is available for pretty printing
  if command -v jq &> /dev/null; then
    cat "$SCHEMA_FILE" | jq .
  else
    cat "$SCHEMA_FILE"
  fi
else
  echo "Entity schema '$ENTITY' not found."
  echo ""
  echo "Available schemas:"
  ls "$DOCS_DIR/schemas"/*.json 2>/dev/null | sed 's/.*\///' | sed 's/\.json$//'

  echo ""
  echo "Searching tech docs for entity references..."
  grep -ri "\"entity\": \"$ENTITY\"" "$DOCS_DIR/tech/" 2>/dev/null | head -5
fi
