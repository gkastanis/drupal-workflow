#!/bin/bash
# discover.sh - Main entry point for docs-first discovery
# PROJECT-AGNOSTIC: Works with any project that has docs/semantic/
# Usage: discover.sh <FEATURE|"search terms"|--list|--prime>

set -e

QUERY="$*"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
DOCS_DIR="$PROJECT_DIR/docs/semantic"
TECH_DIR="$DOCS_DIR/tech"
STRUCTURAL_DIR="$DOCS_DIR/structural"
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
    echo "Structural queries:"
    echo "  discover.sh service:NAME      Find a service"
    echo "  discover.sh route:/PATH       Find routes by path"
    echo "  discover.sh hook:NAME         Find hook implementations"
    echo "  discover.sh plugin:TYPE       Find plugins"
    echo "  discover.sh entity:NAME       Find entity types"
    echo "  discover.sh schema:ENTITY     Show entity field schema (JSON)"
    echo "  discover.sh perm:NAME         Find permissions"
    echo "  discover.sh method:KEYWORD    Find public methods (searches class, method, module)"
    echo "  discover.sh deps:FEATURE      Blast radius / dependency analysis"
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
            FEATURE_COUNT=$(grep -cE '^\| \*\*[A-Z]+\*\*' "$BUSINESS_INDEX" 2>/dev/null)
            FEATURE_COUNT=${FEATURE_COUNT:-0}
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

    # Check structural index
    echo ""
    if [[ -d "$STRUCTURAL_DIR" ]]; then
        echo "✅ Structural index: $STRUCTURAL_DIR"
        STRUCT_COUNT=$(ls "$STRUCTURAL_DIR"/*.md 2>/dev/null | wc -l)
        echo "   Files: $STRUCT_COUNT"
        if [[ -f "$STRUCTURAL_DIR/.generated-at" ]]; then
            echo "   Generated: $(cat "$STRUCTURAL_DIR/.generated-at")"
        fi
    else
        echo "⚠️  Structural index: Not generated"
        echo "   Run /structural-index to generate"
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
        grep -iF "$feature" "$BUSINESS_INDEX" 2>/dev/null | \
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
    grep -riF "$query" "$TECH_DIR" 2>/dev/null | \
        grep -oE '[A-Z]{2,4}-L[0-9]+' | sort -u | head -10

    # Structural index fallthrough
    if [[ -d "$STRUCTURAL_DIR" ]]; then
        echo "🏗️ Structural Index matches:"
        for struct_file in "$STRUCTURAL_DIR"/*.md; do
            if [[ -f "$struct_file" ]]; then
                local matches=$(grep -icF "$query" "$struct_file" 2>/dev/null || echo 0)
                if [[ "$matches" -gt 0 ]]; then
                    echo "  $(basename "$struct_file"): $matches matches"
                    grep -iF "$query" "$struct_file" 2>/dev/null | head -3
                fi
            fi
        done
        echo ""
    fi

    echo ""
    echo "💡 SUGGESTED NEXT STEPS:"
    echo "   - Use /semantic-docs to get full spec for a feature"
    echo "   - Read specific tech spec files listed above"
}

# Structural index query helpers
query_structural() {
    local type="$1" query="$2"
    local file="$STRUCTURAL_DIR/${type}.md"

    if [[ ! -f "$file" ]]; then
        echo "Structural index not found: $file"
        echo "Run /structural-index to generate."
        return 1
    fi

    echo "=== STRUCTURAL: ${type} ==="
    echo ""
    grep -iF "$query" "$file" 2>/dev/null | head -20
    echo ""
}

query_dependencies() {
    local query="$1"
    local dep_graph="$DOCS_DIR/DEPENDENCY_GRAPH.md"

    if [[ ! -f "$dep_graph" ]]; then
        echo "Dependency graph not found."
        echo "Run /structural-index to generate."
        return 1
    fi

    echo "=== DEPENDENCY ANALYSIS: $query ==="
    echo ""
    # Search for the query in the dependency graph
    grep -iF -A5 "$query" "$dep_graph" 2>/dev/null | head -30
    echo ""

    # Also check #UsedBy tags in tech specs
    if [[ -d "$TECH_DIR" ]]; then
        echo "Tech spec references:"
        grep -riF "$query" "$TECH_DIR" 2>/dev/null | grep -i "UsedBy" | head -10
    fi
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
    service:*|svc:*)
        query_structural "services" "${QUERY#*:}"
        ;;
    route:*|path:*)
        query_structural "routes" "${QUERY#*:}"
        ;;
    hook:*)
        query_structural "hooks" "${QUERY#*:}"
        ;;
    plugin:*)
        query_structural "plugins" "${QUERY#*:}"
        ;;
    entity:*|ent:*)
        query_structural "entities" "${QUERY#*:}"
        ;;
    perm:*|permission:*)
        query_structural "permissions" "${QUERY#*:}"
        ;;
    method:*)
        query_structural "methods" "${QUERY#*:}"
        ;;
    schema:*)
        SCHEMA_DIR="$DOCS_DIR/schemas"
        SCHEMA_QUERY="${QUERY#*:}"

        if [[ ! -d "$SCHEMA_DIR" ]]; then
            echo "No schemas found at: $SCHEMA_DIR"
            echo "Run /structural-index to generate."
            exit 1
        fi

        echo "=== SCHEMA: $SCHEMA_QUERY ==="
        echo ""

        SCHEMA_FOUND=false
        for sf in "$SCHEMA_DIR"/*.json; do
            [[ -f "$sf" ]] || continue
            sfn=$(basename "$sf")
            if [[ "$sfn" == *"$SCHEMA_QUERY"* ]]; then
                echo "--- $sfn ---"
                cat "$sf"
                echo ""
                SCHEMA_FOUND=true
            fi
        done

        if [[ "$SCHEMA_FOUND" == false ]]; then
            echo "No schema matching '$SCHEMA_QUERY'"
            echo ""
            echo "Available schemas:"
            ls "$SCHEMA_DIR"/*.json 2>/dev/null | xargs -I{} basename {} .json
        fi
        ;;
    deps:*|impact:*)
        query_dependencies "${QUERY#*:}"
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
