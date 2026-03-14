#!/bin/bash
# generate-feature-map.sh - Build feature map from tech specs + structural data
# Output: docs/semantic/FEATURE_MAP.md
# Reads tech specs to derive feature codes, counts structural artifacts per feature.
set -e

PROJECT_DIR="${1:-${CLAUDE_PROJECT_DIR:-$(pwd)}}"
DOCS_DIR="$PROJECT_DIR/docs/semantic"
STRUCTURAL_DIR="$DOCS_DIR/structural"
TECH_DIR="$DOCS_DIR/tech"
OUTPUT="$DOCS_DIR/FEATURE_MAP.md"

PROJECT_NAME=$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')

SERVICES_MD="$STRUCTURAL_DIR/services.md"
HOOKS_MD="$STRUCTURAL_DIR/hooks.md"
ROUTES_MD="$STRUCTURAL_DIR/routes.md"
PLUGINS_MD="$STRUCTURAL_DIR/plugins.md"
ENTITIES_MD="$STRUCTURAL_DIR/entities.md"

# Count features
FEATURE_COUNT=0
if [[ -d "$TECH_DIR" ]]; then
    FEATURE_COUNT=$(ls "$TECH_DIR"/*.md 2>/dev/null | wc -l)
fi

cat > "$OUTPUT" << HEADER
# Feature Map
Generated: $(date +%Y-%m-%d) | Project: $PROJECT_NAME | Features: $FEATURE_COUNT

HEADER

if [[ ! -d "$TECH_DIR" ]] || [[ "$FEATURE_COUNT" -eq 0 ]]; then
    echo "_No tech specs found in $TECH_DIR. Generate semantic docs first._" >> "$OUTPUT"
    echo "  FEATURE_MAP.md generated (no tech specs found)"
    exit 0
fi

# Main feature table
echo "| Code | Name | Services | Hooks | Routes | Plugins | Entities | Hotspots | Spec |" >> "$OUTPUT"
echo "|------|------|----------|-------|--------|---------|----------|----------|------|" >> "$OUTPUT"

# Build list of known module names from the structural index.
# Each table has Module in a specific column (awk -F'|' counts from $1="" before first pipe):
#   services.md: col 5 (| SvcID | Class | Deps | Module | Tags |)
#   hooks.md: col 6 (| Hook | Impl | Type | File | Module |)
#   routes.md: col 6 (| Route | Path | Ctrl | Access | Module |)
#   plugins.md: col 5 (| Type | ID | Class | Module | File |)
#   entities.md: col 7 (| Type | ID | Class | Handlers | Fields | Module | File |)
KNOWN_MODULES=()
extract_module_col() {
    local file="$1" col="$2"
    grep '^|' "$file" 2>/dev/null | tail -n +3 | awk -F'|' -v c="$col" '{print $c}' | \
        sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//' | sort -u
}
for km in $(extract_module_col "$SERVICES_MD" 5) \
          $(extract_module_col "$HOOKS_MD" 6) \
          $(extract_module_col "$ROUTES_MD" 6) \
          $(extract_module_col "$PLUGINS_MD" 5) \
          $(extract_module_col "$ENTITIES_MD" 7); do
    if [[ -n "$km" && "$km" != "-" ]] && ! printf '%s\n' "${KNOWN_MODULES[@]}" | grep -qxF "$km" 2>/dev/null; then
        KNOWN_MODULES+=("$km")
    fi
done

# Track all modules referenced per feature for hotspot detection
declare -A MODULE_FEATURE_MAP

for tech_file in "$TECH_DIR"/*.md; do
    [[ -f "$tech_file" ]] || continue

    SPEC_NAME=$(basename "$tech_file" .md)
    FEATURE_CODE=$(echo "$SPEC_NAME" | sed 's/_[0-9]*_.*$//' | sed 's/-[0-9]*-.*$//' | tr '[:lower:]' '[:upper:]')
    FEATURE_NAME=$(echo "$SPEC_NAME" | sed 's/^[A-Z]*_[0-9]*_//' | sed 's/^[a-z]*-[0-9]*-//' | tr '_-' ' ')

    # Find modules associated with this feature
    # Strategy 1: Match known module names from structural index against tech spec text
    FEATURE_MODULES=()
    if [[ ${#KNOWN_MODULES[@]} -gt 0 ]]; then
        for km in "${KNOWN_MODULES[@]}"; do
            if grep -qF "$km" "$tech_file" 2>/dev/null; then
                FEATURE_MODULES+=("$km")
            fi
        done
    fi

    # Strategy 2: Look for explicit module references with _module suffix
    while IFS= read -r mod; do
        mod=$(echo "$mod" | sed 's/[[:space:]]*$//')
        if [[ -n "$mod" ]] && ! printf '%s\n' "${FEATURE_MODULES[@]}" | grep -qxF "$mod"; then
            FEATURE_MODULES+=("$mod")
        fi
    done < <(grep -oE '[a-z][a-z_]+_module\b' "$tech_file" 2>/dev/null | sort -u)

    # Track module-to-feature mapping for cross-cutting detection
    for mod in "${FEATURE_MODULES[@]}"; do
        if [[ -n "${MODULE_FEATURE_MAP[$mod]}" ]]; then
            MODULE_FEATURE_MAP[$mod]="${MODULE_FEATURE_MAP[$mod]}, $FEATURE_CODE"
        else
            MODULE_FEATURE_MAP[$mod]="$FEATURE_CODE"
        fi
    done

    # Count structural artifacts matching this feature's modules
    SVC_COUNT=0
    HOOK_COUNT=0
    ROUTE_COUNT=0
    PLUGIN_COUNT=0
    ENTITY_COUNT=0

    for mod in "${FEATURE_MODULES[@]}"; do
        if [[ -f "$SERVICES_MD" ]]; then
            n=$(grep -cF "| $mod |" "$SERVICES_MD" 2>/dev/null) || true; SVC_COUNT=$((SVC_COUNT + ${n:-0}))
        fi
        if [[ -f "$HOOKS_MD" ]]; then
            n=$(grep -cF "| $mod |" "$HOOKS_MD" 2>/dev/null) || true; HOOK_COUNT=$((HOOK_COUNT + ${n:-0}))
        fi
        if [[ -f "$ROUTES_MD" ]]; then
            n=$(grep -cF "| $mod |" "$ROUTES_MD" 2>/dev/null) || true; ROUTE_COUNT=$((ROUTE_COUNT + ${n:-0}))
        fi
        if [[ -f "$PLUGINS_MD" ]]; then
            n=$(grep -cF "| $mod |" "$PLUGINS_MD" 2>/dev/null) || true; PLUGIN_COUNT=$((PLUGIN_COUNT + ${n:-0}))
        fi
        if [[ -f "$ENTITIES_MD" ]]; then
            n=$(grep -cF "| $mod |" "$ENTITIES_MD" 2>/dev/null) || true; ENTITY_COUNT=$((ENTITY_COUNT + ${n:-0}))
        fi
    done

    # Hotspot: count how many structural artifacts total
    HOTSPOT_SCORE=$((SVC_COUNT + HOOK_COUNT + ROUTE_COUNT + PLUGIN_COUNT + ENTITY_COUNT))
    if [[ "$HOTSPOT_SCORE" -gt 10 ]]; then
        HOTSPOT="HIGH"
    elif [[ "$HOTSPOT_SCORE" -gt 5 ]]; then
        HOTSPOT="MED"
    elif [[ "$HOTSPOT_SCORE" -gt 0 ]]; then
        HOTSPOT="LOW"
    else
        HOTSPOT="-"
    fi

    echo "| $FEATURE_CODE | $FEATURE_NAME | $SVC_COUNT | $HOOK_COUNT | $ROUTE_COUNT | $PLUGIN_COUNT | $ENTITY_COUNT | $HOTSPOT | \`$SPEC_NAME\` |" >> "$OUTPUT"
done

echo "" >> "$OUTPUT"

# Cross-Cutting Concerns
echo "## Cross-Cutting Concerns" >> "$OUTPUT"
echo "" >> "$OUTPUT"
echo "Modules/services shared across multiple features:" >> "$OUTPUT"
echo "" >> "$OUTPUT"

CROSS_CUTTING=0
for mod in "${!MODULE_FEATURE_MAP[@]}"; do
    FEATURES="${MODULE_FEATURE_MAP[$mod]}"
    # Count commas to determine number of features
    COMMA_COUNT=$(echo "$FEATURES" | tr -cd ',' | wc -c)
    if [[ "$COMMA_COUNT" -gt 0 ]]; then
        echo "- **\`$mod\`**: $FEATURES" >> "$OUTPUT"
        ((CROSS_CUTTING++)) || true
    fi
done

if [[ "$CROSS_CUTTING" -eq 0 ]]; then
    echo "_No cross-cutting modules detected._" >> "$OUTPUT"
fi
echo "" >> "$OUTPUT"

# Staleness Section
echo "## Staleness" >> "$OUTPUT"
echo "" >> "$OUTPUT"

if [[ -f "$STRUCTURAL_DIR/.generated-at" ]]; then
    GEN_TIME=$(cat "$STRUCTURAL_DIR/.generated-at")
    echo "Last generated: $GEN_TIME" >> "$OUTPUT"
    echo "" >> "$OUTPUT"

    STALE_COUNT=$(find "$PROJECT_DIR" -newer "$STRUCTURAL_DIR/.generated-at" \
        \( -name "*.services.yml" -o -name "*.routing.yml" -o -name "*.module" -o -name "*.php" \) \
        2>/dev/null | wc -l)

    if [[ "$STALE_COUNT" -gt 0 ]]; then
        echo "**WARNING**: $STALE_COUNT source files modified since last generation." >> "$OUTPUT"
        echo "Run \`/structural-index\` to regenerate." >> "$OUTPUT"
    else
        echo "Index is up to date." >> "$OUTPUT"
    fi
else
    echo "_No generation timestamp found._" >> "$OUTPUT"
fi
echo "" >> "$OUTPUT"

echo "---" >> "$OUTPUT"
echo "_Feature map generated from tech specs and structural index._" >> "$OUTPUT"

echo "  FEATURE_MAP.md generated ($FEATURE_COUNT features)"
