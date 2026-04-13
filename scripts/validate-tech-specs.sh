#!/bin/bash
# validate-tech-specs.sh - Validate and auto-fix tech spec filenames and frontmatter.
# Checks CODE_01_Name.md naming convention and required YAML frontmatter fields.
# Pass --fix to auto-rename non-conforming files. Without --fix, report-only.
set -e

PROJECT_DIR="${1:-${CLAUDE_PROJECT_DIR:-$(pwd)}}"
TECH_DIR="$PROJECT_DIR/docs/semantic/tech"
FIX=false
[[ "${2:-}" == "--fix" || "${1:-}" == "--fix" ]] && FIX=true
[[ "${1:-}" == "--fix" ]] && PROJECT_DIR="${2:-${CLAUDE_PROJECT_DIR:-$(pwd)}}" && TECH_DIR="$PROJECT_DIR/docs/semantic/tech"

if ! ls "$TECH_DIR"/*.md &>/dev/null; then
    echo "  No tech specs found in $TECH_DIR"
    exit 0
fi

ERRORS=0
FIXED=0
VALID=0

REQUIRED_FIELDS="type feature_id feature_name module last_updated logic_id_count"

# Extract frontmatter content (between first and second ---)
extract_frontmatter() {
    awk '
        NR==1 && /^---$/ {in_fm=1; next}
        in_fm && /^---$/ {exit}
        in_fm {print}
    ' "$1"
}

# Extract a single frontmatter field value
get_frontmatter_field() {
    extract_frontmatter "$1" | grep "^${2}:" | head -1 | sed "s/^${2}:[[:space:]]*//"
}

for spec in "$TECH_DIR"/*.md; do
    [[ -f "$spec" ]] || continue
    BASENAME=$(basename "$spec")
    ISSUES=""

    # --- Check filename format: CODE_01_Name.md ---
    if ! echo "$BASENAME" | grep -qE '^[A-Z]{2,5}_[0-9]{2}_[A-Za-z]+\.md$'; then
        ISSUES="${ISSUES}  filename: expected CODE_01_Name.md, got $BASENAME\n"

        if $FIX; then
            # Try to derive correct name from frontmatter.
            FEAT_ID=$(get_frontmatter_field "$spec" "feature_id" | tr -d ' ')
            FEAT_NAME=$(get_frontmatter_field "$spec" "feature_name" | sed 's/^ *//')

            if [[ -n "$FEAT_ID" && -n "$FEAT_NAME" ]]; then
                # Convert feature name to PascalCase: strip non-alphanumeric, capitalize words.
                PASCAL=$(echo "$FEAT_NAME" | sed -E 's/[^a-zA-Z0-9 ]//g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1' | tr -d ' ')

                # Find next available sequence number.
                SEQ=1
                while [[ -f "$TECH_DIR/${FEAT_ID}_$(printf '%02d' $SEQ)_${PASCAL}.md" ]]; do
                    ((SEQ++)) || true
                done
                NEW_NAME="${FEAT_ID}_$(printf '%02d' $SEQ)_${PASCAL}.md"

                if [[ "$BASENAME" != "$NEW_NAME" ]]; then
                    mv "$spec" "$TECH_DIR/$NEW_NAME"
                    echo "  FIXED: $BASENAME → $NEW_NAME"
                    ((FIXED++)) || true
                    spec="$TECH_DIR/$NEW_NAME"
                    BASENAME="$NEW_NAME"
                    ISSUES=""
                fi
            else
                ISSUES="${ISSUES}  cannot auto-fix: missing feature_id or feature_name in frontmatter\n"
            fi
        fi
    fi

    # --- Check YAML frontmatter exists ---
    if ! head -1 "$spec" | grep -q '^---$'; then
        ISSUES="${ISSUES}  frontmatter: missing (file does not start with ---)\n"

        if $FIX; then
            # Try to infer fields from filename if it matches the pattern now.
            if echo "$BASENAME" | grep -qE '^[A-Z]{2,5}_[0-9]{2}_[A-Za-z]+\.md$'; then
                CODE=$(echo "$BASENAME" | sed -E 's/^([A-Z]+)_.*/\1/')
                NAME=$(echo "$BASENAME" | sed -E 's/^[A-Z]+_[0-9]+_//' | sed 's/\.md$//')
                # Count Logic IDs in the file.
                LID_COUNT=$(grep -cE '^\| [A-Z]+-L[0-9]' "$spec" 2>/dev/null || echo 0)
                # Find module from structural index.
                MODULE="unknown"
                SERVICES="$PROJECT_DIR/docs/semantic/structural/services.md"
                if [[ -f "$SERVICES" ]]; then
                    # Look for services whose class path contains a module matching the code.
                    MODULE_GUESS=$(grep -i "$(echo "$CODE" | tr '[:upper:]' '[:lower:]')" "$SERVICES" 2>/dev/null | head -1 | awk -F'|' '{gsub(/ /, "", $5); print $5}')
                    [[ -n "$MODULE_GUESS" ]] && MODULE="$MODULE_GUESS"
                fi

                FRONTMATTER="---\ntype: tech_spec\nfeature_id: $CODE\nfeature_name: $NAME\nmodule: $MODULE\nrelated_files: []\nlast_updated: $(date +%Y-%m-%d)\nlogic_id_count: $LID_COUNT\n---\n"
                TMPFILE=$(mktemp)
                printf "%b" "$FRONTMATTER" > "$TMPFILE"
                cat "$spec" >> "$TMPFILE"
                mv "$TMPFILE" "$spec"
                echo "  FIXED: added frontmatter to $BASENAME (verify module field)"
                ((FIXED++)) || true
                ISSUES=""
            fi
        fi
    else
        # Frontmatter exists — check required fields.
        FRONTMATTER_BLOCK=$(extract_frontmatter "$spec")
        for field in $REQUIRED_FIELDS; do
            if ! echo "$FRONTMATTER_BLOCK" | grep -q "^${field}:"; then
                ISSUES="${ISSUES}  frontmatter: missing field '$field'\n"
            fi
        done
    fi

    if [[ -n "$ISSUES" ]]; then
        echo "  FAIL: $BASENAME"
        printf '%b' "$ISSUES"
        ((ERRORS++)) || true
    else
        ((VALID++)) || true
    fi
done

echo ""
echo "  Validation: $VALID valid, $ERRORS errors, $FIXED fixed"
[[ $ERRORS -gt 0 ]] && exit 1
exit 0
