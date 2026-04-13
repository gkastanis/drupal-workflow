#!/bin/bash
# validate-semantic-docs.sh
# Validates that semantic docs (Layer 3) are consistent with the codebase and structural index.
# Can run standalone or as a SessionStart hook.
# Exit code 0 always (advisory only). Warnings printed to stdout.

PROJECT_DIR="${1:-${CLAUDE_PROJECT_DIR:-$(pwd)}}"
DOCS_DIR="$PROJECT_DIR/docs/semantic"
TECH_DIR="$DOCS_DIR/tech"
STRUCTURAL_DIR="$DOCS_DIR/structural"
BUSINESS_INDEX="$DOCS_DIR/00_BUSINESS_INDEX.md"
FEATURE_MAP="$DOCS_DIR/FEATURE_MAP.md"

WARNINGS=0
CHECKS=0

warn() {
    echo "SEMANTIC DOCS WARNING: $1"
    ((WARNINGS++)) || true
}

pass() {
    ((CHECKS++)) || true
}

# Extract frontmatter content (between first and second ---)
extract_frontmatter() {
    awk '
        NR==1 && /^---$/ {in_fm=1; next}
        in_fm && /^---$/ {exit}
        in_fm {print}
    ' "$1"
}

# --- Guard: skip if no semantic docs exist ---
if [[ ! -d "$TECH_DIR" ]]; then
    echo "SEMANTIC DOCS: No tech specs found (run /drupal-bootstrap to set up)"
    exit 0
fi

TECH_SPECS=("$TECH_DIR"/*.md)
if [[ ! -f "${TECH_SPECS[0]}" ]]; then
    echo "SEMANTIC DOCS: No tech specs found (run /drupal-bootstrap to set up)"
    exit 0
fi

SPEC_COUNT=${#TECH_SPECS[@]}

# --- Check 1: Business index exists and lists all tech specs ---
if [[ ! -f "$BUSINESS_INDEX" ]]; then
    warn "00_BUSINESS_INDEX.md is missing. Run /drupal-semantic index to generate it."
else
    pass
    # Check each tech spec has an entry in the business index
    for spec in "${TECH_SPECS[@]}"; do
        SPEC_NAME=$(basename "$spec" .md)
        FEATURE_CODE=$(echo "$SPEC_NAME" | sed 's/_[0-9]*_.*$//')
        if ! grep -qE "(^|\|)[[:space:]]*${FEATURE_CODE}[[:space:]]*(\||$)" "$BUSINESS_INDEX" 2>/dev/null; then
            warn "$SPEC_NAME not listed in 00_BUSINESS_INDEX.md"
        else
            pass
        fi
    done
fi

# --- Check 2: FEATURE_MAP lists all tech specs ---
if [[ -f "$FEATURE_MAP" ]]; then
    for spec in "${TECH_SPECS[@]}"; do
        SPEC_NAME=$(basename "$spec" .md)
        if ! grep -qF "$SPEC_NAME" "$FEATURE_MAP" 2>/dev/null; then
            warn "$SPEC_NAME not listed in FEATURE_MAP.md"
        else
            pass
        fi
    done
else
    warn "FEATURE_MAP.md is missing. Run /drupal-refresh to generate it."
fi

# --- Check 3: related_files in frontmatter point to existing files ---
for spec in "${TECH_SPECS[@]}"; do
    SPEC_NAME=$(basename "$spec" .md)

    # Extract related_files from YAML frontmatter
    IN_FRONTMATTER=0
    IN_RELATED=0
    while IFS= read -r line; do
        # Track frontmatter boundaries
        if [[ "$line" == "---" ]]; then
            if [[ "$IN_FRONTMATTER" -eq 1 ]]; then
                break  # End of frontmatter
            fi
            IN_FRONTMATTER=1
            continue
        fi

        [[ "$IN_FRONTMATTER" -eq 0 ]] && continue

        # Detect related_files section
        if [[ "$line" =~ ^related_files: ]]; then
            IN_RELATED=1
            continue
        fi

        # End of related_files when we hit a non-list line
        if [[ "$IN_RELATED" -eq 1 ]]; then
            if [[ "$line" =~ ^[[:space:]]*-[[:space:]]+(.*) ]]; then
                FILE_PATH="${BASH_REMATCH[1]}"
                # Strip quotes if present
                FILE_PATH=$(echo "$FILE_PATH" | sed "s/^['\"]//;s/['\"]$//")
                FULL_PATH="$PROJECT_DIR/$FILE_PATH"
                if [[ ! -f "$FULL_PATH" ]]; then
                    warn "$SPEC_NAME: related_file not found: $FILE_PATH"
                else
                    pass
                fi
            else
                IN_RELATED=0
            fi
        fi
    done < "$spec"
done

# --- Check 4: Structural index is newer than tech specs (means specs may be stale) ---
if [[ -f "$STRUCTURAL_DIR/.generated-at" ]]; then
    STRUCTURAL_TS=$(stat -c %Y "$STRUCTURAL_DIR/.generated-at" 2>/dev/null || stat -f %m "$STRUCTURAL_DIR/.generated-at" 2>/dev/null)
    STALE_SPECS=()

    for spec in "${TECH_SPECS[@]}"; do
        SPEC_TS=$(stat -c %Y "$spec" 2>/dev/null || stat -f %m "$spec" 2>/dev/null)
        if [[ -n "$STRUCTURAL_TS" && -n "$SPEC_TS" && "$SPEC_TS" -lt "$STRUCTURAL_TS" ]]; then
            STALE_SPECS+=("$(basename "$spec" .md)")
        fi
    done

    if [[ ${#STALE_SPECS[@]} -gt 0 ]]; then
        STALE_COUNT=${#STALE_SPECS[@]}
        if [[ "$STALE_COUNT" -gt 5 ]]; then
            warn "$STALE_COUNT/$SPEC_COUNT tech specs are older than structural index. Run /drupal-semantic init to refresh."
        else
            for s in "${STALE_SPECS[@]}"; do
                warn "Tech spec $s is older than structural index. Run /drupal-semantic feature ${s%%_*} to refresh."
            done
        fi
    else
        pass
    fi
fi

# --- Check 5: Logic IDs reference files that still exist ---
# Logic ID table uses module-relative paths (e.g., src/Service/Foo.php).
# Resolve to project-relative using the module from frontmatter + docroot detection.
MODULES_DIR=""
for d in "$PROJECT_DIR/web/modules/custom" "$PROJECT_DIR/www/modules/custom" "$PROJECT_DIR/modules/custom"; do
    [[ -d "$d" ]] && MODULES_DIR="$d" && break
done

for spec in "${TECH_SPECS[@]}"; do
    SPEC_NAME=$(basename "$spec" .md)

    # Get module name from frontmatter to resolve relative paths
    SPEC_MODULE=$(extract_frontmatter "$spec" | grep '^module:' | head -1 | sed 's/^module:[[:space:]]*//' | sed 's/[[:space:]]*$//')
    MODULE_DIR=""
    if [[ -n "$SPEC_MODULE" && -n "$MODULES_DIR" ]]; then
        MODULE_DIR="$MODULES_DIR/$SPEC_MODULE"
    fi

    # Extract file paths from the Logic-to-Code table (column 4 via awk: |_|LogicID|Desc|File|...)
    IN_TABLE=0
    CHECKED_FILES=()  # Deduplicate: don't warn twice for same file
    while IFS= read -r line; do
        # Detect table start (header row with "Logic ID")
        if echo "$line" | grep -qF "Logic ID"; then
            IN_TABLE=1
            continue
        fi
        # Skip separator row
        if [[ "$IN_TABLE" -eq 1 ]] && echo "$line" | grep -qE '^\|[-| ]+\|$'; then
            continue
        fi
        # Parse table rows
        if [[ "$IN_TABLE" -eq 1 ]] && [[ "$line" =~ ^\| ]]; then
            # Extract file path from column 4 (awk counts from empty $1 before first pipe)
            FILE_REF=$(echo "$line" | awk -F'|' '{print $4}' | sed 's/`//g' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
            if [[ -n "$FILE_REF" && "$FILE_REF" != "-" && "$FILE_REF" != "File" && "$FILE_REF" == *"/"* ]]; then
                # Skip if already checked this file for this spec
                if printf '%s\n' "${CHECKED_FILES[@]}" | grep -qxF "$FILE_REF" 2>/dev/null; then
                    continue
                fi
                CHECKED_FILES+=("$FILE_REF")

                # Try resolving: module-relative path first, then project-relative
                FOUND=0
                if [[ -n "$MODULE_DIR" && -f "$MODULE_DIR/$FILE_REF" ]]; then
                    FOUND=1
                elif [[ -f "$PROJECT_DIR/$FILE_REF" ]]; then
                    FOUND=1
                fi

                if [[ "$FOUND" -eq 1 ]]; then
                    pass
                else
                    warn "$SPEC_NAME: Logic ID references missing file: $FILE_REF (module: $SPEC_MODULE)"
                fi
            fi
        fi
        # End of table when we hit a non-table line
        if [[ "$IN_TABLE" -eq 1 ]] && [[ ! "$line" =~ ^\| ]] && [[ -n "$line" ]]; then
            IN_TABLE=0
        fi
    done < "$spec"
done

# --- Check 6: Module in frontmatter exists in structural index ---
if [[ -f "$STRUCTURAL_DIR/services.md" ]]; then
    for spec in "${TECH_SPECS[@]}"; do
        SPEC_NAME=$(basename "$spec" .md)
        # Extract module from frontmatter only
        MODULE=$(extract_frontmatter "$spec" | grep '^module:' | head -1 | sed 's/^module:[[:space:]]*//' | sed 's/[[:space:]]*$//')
        if [[ -n "$MODULE" && "$MODULE" != "-" ]]; then
            # Check if module appears anywhere in structural index
            if ! grep -qF "$MODULE" "$STRUCTURAL_DIR/services.md" 2>/dev/null && \
               ! grep -qF "$MODULE" "$STRUCTURAL_DIR/hooks.md" 2>/dev/null && \
               ! grep -qF "$MODULE" "$STRUCTURAL_DIR/routes.md" 2>/dev/null; then
                warn "$SPEC_NAME: module '$MODULE' not found in structural index (module may be uninstalled or renamed)"
            else
                pass
            fi
        fi
    done
fi

# --- Summary ---
if [[ "$WARNINGS" -gt 0 ]]; then
    echo "SEMANTIC DOCS: $WARNINGS warnings across $SPEC_COUNT tech specs ($CHECKS checks passed)"
else
    echo "SEMANTIC DOCS: All checks passed ($CHECKS checks across $SPEC_COUNT tech specs)"
fi

exit 0
