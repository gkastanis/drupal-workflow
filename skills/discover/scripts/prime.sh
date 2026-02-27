#!/bin/bash
# prime.sh - Load business index for session context
# PROJECT-AGNOSTIC: Works with any project that has docs/semantic/
# Usage: prime.sh

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
DOCS_DIR="$PROJECT_DIR/docs/semantic"
BUSINESS_INDEX="$DOCS_DIR/00_BUSINESS_INDEX.md"
TECH_DIR="$DOCS_DIR/tech"

# Derive project name from directory
PROJECT_NAME=$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
QMD_COLLECTION="${PROJECT_NAME}-docs"

echo "=== DOCS-FIRST SESSION PRIMER ==="
echo "Project: $PROJECT_NAME"
echo ""

if [[ ! -f "$BUSINESS_INDEX" ]]; then
    echo "⚠️  Business index not found at: $BUSINESS_INDEX"
    echo ""
    echo "To generate semantic docs:"
    echo "  1. Run semantic-architect-agent"
    echo "  2. Or create docs/semantic/00_BUSINESS_INDEX.md manually"
    echo ""
    echo "Expected QMD collection: $QMD_COLLECTION"
    exit 1
fi

echo "📋 FEATURE REGISTRY"
echo "==================="
# Extract feature table (skip header lines, get actual features)
grep -E '^\| \*\*[A-Z]+\*\*' "$BUSINESS_INDEX" 2>/dev/null | head -25
echo ""

echo "📊 KEY ENTITIES"
echo "==============="
# Extract entity list from Domain Context (multiple patterns)
grep -E '^- `[A-Za-z]+`|^\* `[A-Za-z]+`' "$BUSINESS_INDEX" 2>/dev/null | head -15
echo ""

echo "🎯 CORE CAPABILITIES"
echo "===================="
# Extract numbered capabilities
grep -E '^[0-9]+\.' "$BUSINESS_INDEX" 2>/dev/null | head -15
echo ""

echo "🔗 LOGIC ID COUNT BY FEATURE"
echo "============================"
echo "Feature | Logic IDs | File"
echo "--------|-----------|-----"
if [[ -d "$TECH_DIR" ]]; then
    for tech_file in "$TECH_DIR"/*.md; do
        if [[ -f "$tech_file" ]]; then
            # Extract feature code from filename (handles FEAT_01_Name.md and feat-01-name.md)
            feature=$(basename "$tech_file" .md | sed 's/_[0-9]*_.*$//' | sed 's/-[0-9]*-.*$//' | tr '[:lower:]' '[:upper:]')
            count=$(grep -cE '^\| \*\*\[' "$tech_file" 2>/dev/null || echo 0)
            if [[ -n "$count" && "$count" -gt 0 ]]; then
                short_file=$(basename "$tech_file")
                printf "%-7s | %-9s | %s\n" "$feature" "$count" "$short_file"
            fi
        fi
    done
fi
echo ""

echo "📄 AVAILABLE TECH SPECS"
echo "======================="
if [[ -d "$TECH_DIR" ]]; then
    ls "$TECH_DIR"/*.md 2>/dev/null | while read -r f; do
        basename "$f" .md
    done
else
    echo "(no tech specs found)"
fi
echo ""

echo "💡 QUICK REFERENCE"
echo "=================="
echo "- /discover FEATURE    Get full technical spec"
echo "- /discover \"query\"    Search all docs"
echo "- /discover --status   Check docs/QMD status"
echo "- /semantic-docs       Deep Logic ID lookup"
if command -v qmd &>/dev/null; then
    echo "- qmd search \"query\" -c $QMD_COLLECTION"
fi
echo ""
echo "📖 Full index: $BUSINESS_INDEX"
