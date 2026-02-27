#!/bin/bash
# discover.sh - Main entry point for docs-first discovery
# PROJECT-AGNOSTIC: Works with any project that has docs/semantic/
# Usage: discover.sh <FEATURE|"search terms"|--list|--prime>

set -e

QUERY="$*"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
DOCS_DIR="$PROJECT_DIR/docs/semantic"
TECH_DIR="$DOCS_DIR/tech"
BUSINESS_INDEX="$DOCS_DIR/00_BUSINESS_INDEX.md"

# Derive project name and QMD collection from directory
PROJECT_NAME=$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
QMD_COLLECTION="${PROJECT_NAME}-docs"

# Check if semantic docs exist
check_docs() {
    if [[ ! -d "$DOCS_DIR" ]]; then
        echo "⚠️  No semantic documentation found at: $DOCS_DIR"
        echo ""
        echo "To generate semantic docs for this project:"
        echo "  1. Run semantic-architect-agent"
        echo "  2. Or create docs/semantic/ manually with:"
        echo "     - 00_BUSINESS_INDEX.md (feature registry)"
        echo "     - tech/*.md (technical specs)"
        echo ""
        echo "QMD collection expected: $QMD_COLLECTION"
        echo "Create with: qmd collection add $QMD_COLLECTION docs/"
        exit 1
    fi
}

show_help() {
    echo "Docs-First Discovery Tool"
    echo "========================="
    echo ""
    echo "Project: $PROJECT_NAME"
    echo "Docs:    $DOCS_DIR"
    echo "QMD:     $QMD_COLLECTION"
    echo ""
    echo "Usage:"
    echo "  discover.sh <FEATURE_CODE>    Lookup feature (e.g., AUTH, ASGN)"
    echo "  discover.sh \"search terms\"    Search docs for keywords"
    echo "  discover.sh --list            List all available features"
    echo "  discover.sh --prime           Output business index for context"
    echo "  discover.sh --status          Check docs/QMD status"
    echo ""
    echo "Examples:"
    echo "  discover.sh AUTH              Full authentication spec"
    echo "  discover.sh timer             Search for timer-related docs"
    echo "  discover.sh \"user login\"      Search for user login docs"
}

check_status() {
    echo "=== DOCS-FIRST STATUS ==="
    echo ""
    echo "Project:    $PROJECT_NAME"
    echo "Project Dir: $PROJECT_DIR"
    echo ""

    # Check semantic docs
    if [[ -d "$DOCS_DIR" ]]; then
        echo "✅ Semantic docs: $DOCS_DIR"
        if [[ -f "$BUSINESS_INDEX" ]]; then
            FEATURE_COUNT=$(grep -cE '^\| \*\*[A-Z]+\*\*' "$BUSINESS_INDEX" 2>/dev/null || echo 0)
            echo "   Features: $FEATURE_COUNT"
        fi
        if [[ -d "$TECH_DIR" ]]; then
            SPEC_COUNT=$(ls "$TECH_DIR"/*.md 2>/dev/null | wc -l)
            echo "   Tech specs: $SPEC_COUNT"
        fi
    else
        echo "❌ Semantic docs: Not found"
    fi

    # Check QMD collection
    echo ""
    if command -v qmd &>/dev/null; then
        if qmd collection list 2>/dev/null | grep -q "$QMD_COLLECTION"; then
            echo "✅ QMD collection: $QMD_COLLECTION"
            qmd collection list 2>/dev/null | grep -A2 "$QMD_COLLECTION" | head -4
        else
            echo "❌ QMD collection: $QMD_COLLECTION not found"
            echo "   Create with: qmd collection add $QMD_COLLECTION docs/"
        fi
    else
        echo "⚠️  QMD not installed (optional)"
    fi
}

list_features() {
    check_docs

    echo "=== AVAILABLE FEATURES ==="
    echo "Project: $PROJECT_NAME"
    echo ""

    if [[ -f "$BUSINESS_INDEX" ]]; then
        # Extract feature registry table
        grep -E '^\| \*\*[A-Z]+\*\*' "$BUSINESS_INDEX" 2>/dev/null | head -30
    else
        # Fallback: list tech spec files
        echo "Tech specs available:"
        ls "$TECH_DIR"/*.md 2>/dev/null | while read -r f; do
            basename "$f" .md | sed 's/-[0-9]*-/ - /' | sed 's/_[0-9]*_/ - /'
        done
    fi
}

prime_context() {
    check_docs

    # Delegate to prime.sh
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -x "$SCRIPT_DIR/prime.sh" ]]; then
        "$SCRIPT_DIR/prime.sh"
    else
        echo "=== BUSINESS INDEX PRIMER ==="
        echo "Project: $PROJECT_NAME"
        echo ""

        if [[ -f "$BUSINESS_INDEX" ]]; then
            echo "📋 Feature Registry:"
            grep -E '^\| \*\*[A-Z]+\*\*' "$BUSINESS_INDEX" 2>/dev/null | head -25
            echo ""
            echo "💡 Use /discover FEATURE for detailed specs"
        fi
    fi
}

lookup_feature() {
    check_docs

    local feature="$1"
    local feature_upper=$(echo "$feature" | tr '[:lower:]' '[:upper:]')

    echo "=== DISCOVER: $feature_upper ==="
    echo "Project: $PROJECT_NAME"
    echo ""

    # Find matching tech spec (try multiple naming patterns)
    local tech_file=""
    for pattern in "${feature_upper}_*.md" "${feature_upper}-*.md" "*${feature_upper}*.md" "${feature}*.md"; do
        tech_file=$(find "$TECH_DIR" -maxdepth 1 -iname "$pattern" 2>/dev/null | head -1)
        if [[ -n "$tech_file" ]]; then
            break
        fi
    done

    if [[ -n "$tech_file" && -f "$tech_file" ]]; then
        echo "📄 Technical Spec: $(basename "$tech_file")"
        echo "   Path: $tech_file"
        echo ""

        # Output the full spec
        cat "$tech_file"
        echo ""

        # Extract Logic IDs for quick reference
        echo "🔗 LOGIC ID QUICK REFERENCE:"
        grep -E '^\| \*\*\[' "$tech_file" 2>/dev/null | head -15

    else
        echo "No exact match for '$feature_upper'"
        echo ""

        # Search business index
        echo "📋 Business Index matches:"
        grep -i "$feature" "$BUSINESS_INDEX" 2>/dev/null | \
            grep -E '^\|' | head -10
        echo ""

        # QMD search
        if command -v qmd &>/dev/null && qmd collection list 2>/dev/null | grep -q "$QMD_COLLECTION"; then
            echo "🔍 QMD Search Results:"
            qmd search "$feature" -c "$QMD_COLLECTION" -n 5 2>/dev/null
        fi

        echo ""
        echo "Available features:"
        ls "$TECH_DIR"/*.md 2>/dev/null | xargs -I{} basename {} | \
            sed 's/_[0-9]*_.*$//' | sed 's/-[0-9]*-.*$//' | \
            tr '[:lower:]' '[:upper:]' | sort -u
    fi
}

search_docs() {
    check_docs

    local query="$*"

    echo "=== DISCOVER: \"$query\" ==="
    echo "Project: $PROJECT_NAME"
    echo ""

    # QMD search (primary method)
    if command -v qmd &>/dev/null && qmd collection list 2>/dev/null | grep -q "$QMD_COLLECTION"; then
        echo "🔍 QMD Search Results:"
        qmd search "$query" -c "$QMD_COLLECTION" -n 7 2>/dev/null
        echo ""
    fi

    # Business index search
    if [[ -f "$BUSINESS_INDEX" ]]; then
        echo "📋 Business Index matches:"
        grep -i "$query" "$BUSINESS_INDEX" 2>/dev/null | \
            grep -E '^\|' | head -10
        echo ""
    fi

    # Find related tech specs
    echo "📄 Related Technical Specs:"
    for word in $query; do
        local found=$(find "$TECH_DIR" -iname "*${word}*" 2>/dev/null | head -3)
        if [[ -n "$found" ]]; then
            echo "$found"
        fi
    done
    echo ""

    # Extract any Logic IDs from matches
    echo "🔗 Potentially Relevant Logic IDs:"
    grep -ri "$query" "$TECH_DIR" 2>/dev/null | \
        grep -oE '[A-Z]{2,4}-L[0-9]+' | sort -u | head -10

    echo ""
    echo "💡 SUGGESTED NEXT STEPS:"
    echo "   - Use /semantic-docs to get full spec for a feature"
    echo "   - Read specific tech spec files listed above"
}

# Main logic
if [[ -z "$QUERY" ]]; then
    show_help
    exit 0
fi

case "$QUERY" in
    -h|--help)
        show_help
        ;;
    --list|-l)
        list_features
        ;;
    --prime|-p)
        prime_context
        ;;
    --status|-s)
        check_status
        ;;
    *)
        # Check if it looks like a feature code (2-4 uppercase letters)
        if echo "$QUERY" | grep -qE '^[A-Za-z]{2,4}$'; then
            lookup_feature "$QUERY"
        else
            search_docs "$QUERY"
        fi
        ;;
esac
