#!/bin/bash
# generate-entity-schemas.sh - Parse config YAML for entity field definitions
# Output: docs/semantic/schemas/*.json, docs/semantic/structural/schemas.md
# Patches: docs/semantic/structural/entities.md (adds Fields column)
#
# Known limitations:
#   - Cannot read PHP $settings['config_sync_directory'] — searches common locations
#   - Base fields (uid, created, changed, etc.) from baseFieldDefinitions() not extracted
#   - Only configurable fields from YAML config are extracted
#   - config/optional/ is skipped (may not be active)
set -e

PROJECT_DIR="${1:-${CLAUDE_PROJECT_DIR:-$(pwd)}}"
STRUCTURAL_DIR="$PROJECT_DIR/docs/semantic/structural"
SCHEMA_DIR="$PROJECT_DIR/docs/semantic/schemas"
ENTITIES_FILE="$STRUCTURAL_DIR/entities.md"

mkdir -p "$SCHEMA_DIR"
mkdir -p "$STRUCTURAL_DIR"

# --- Helpers ---

json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

# --- Config directory detection ---
CONFIG_DIRS=()
for candidate in \
    "$PROJECT_DIR/config/sync" \
    "$PROJECT_DIR/config/default" \
    "$PROJECT_DIR/config/staging" \
    "$PROJECT_DIR/../config/sync"; do
    if [[ -d "$candidate" ]] && compgen -G "$candidate/field.storage.*.yml" >/dev/null 2>&1; then
        CONFIG_DIRS+=("$candidate")
        break
    fi
done

# Fallback: module config/install directories
if [[ ${#CONFIG_DIRS[@]} -eq 0 ]]; then
    for search_dir in "$PROJECT_DIR/web/modules/custom" "$PROJECT_DIR/www/modules/custom" "$PROJECT_DIR/modules/custom"; do
        if [[ -d "$search_dir" ]]; then
            while IFS= read -r d; do
                CONFIG_DIRS+=("$d")
            done < <(find "$search_dir" -type d -name "install" -path "*/config/install" 2>/dev/null)
            if [[ ${#CONFIG_DIRS[@]} -gt 0 ]]; then break; fi
        fi
    done
fi

if [[ ${#CONFIG_DIRS[@]} -eq 0 ]]; then
    echo "  schemas: No config directory found"
    echo "  schemas: 0 fields processed, 0 schemas generated"
    exit 0
fi

# --- Associative arrays ---
declare -A FIELD_TYPE FIELD_CARDINALITY FIELD_TARGET_TYPE FIELD_ALLOWED_VALUES
declare -A BUNDLE_FIELDS FIELD_LABEL FIELD_DESC FIELD_REQUIRED FIELD_TARGET_BUNDLES
declare -A ENTITY_FIELD_COUNT ENTITY_REF_COUNT ENTITY_LIST_COUNT

TOTAL_STORAGE=0
TOTAL_SCHEMAS=0

# --- Pass 1: Parse field.storage.*.yml ---
for config_dir in "${CONFIG_DIRS[@]}"; do
    for storage_file in "$config_dir"/field.storage.*.yml; do
        [[ -f "$storage_file" ]] || continue

        bn=$(basename "$storage_file" .yml)
        rest="${bn#field.storage.}"
        entity_type="${rest%%.*}"
        field_name="${rest#*.}"
        key="${entity_type}.${field_name}"

        # Type (top-level)
        ftype=$(grep -m1 -E '^type:\s' "$storage_file" | sed 's/^type:\s*//' | tr -d "'" | tr -d '"' | tr -d '[:space:]')
        [[ -z "$ftype" ]] && continue
        FIELD_TYPE["$key"]="$ftype"

        # Cardinality (top-level)
        card=$(grep -m1 -E '^cardinality:\s' "$storage_file" | sed 's/^cardinality:\s*//' | tr -d '[:space:]')
        FIELD_CARDINALITY["$key"]="${card:-1}"

        # Per-entity counts
        ENTITY_FIELD_COUNT["$entity_type"]=$(( ${ENTITY_FIELD_COUNT["$entity_type"]:-0} + 1 ))

        # Entity reference: extract settings.target_type
        if [[ "$ftype" == "entity_reference" || "$ftype" == "entity_reference_revisions" ]]; then
            target_type=$(awk '
                /^settings:/ { s=1; next }
                s && /^[a-z]/ { exit }
                s && /target_type:/ {
                    sub(/.*target_type:\s*/, "")
                    gsub(/["\047]/, "")
                    gsub(/[[:space:]]/, "")
                    print; exit
                }
            ' "$storage_file" 2>/dev/null)
            FIELD_TARGET_TYPE["$key"]="$target_type"
            ENTITY_REF_COUNT["$entity_type"]=$(( ${ENTITY_REF_COUNT["$entity_type"]:-0} + 1 ))
        fi

        # List types: extract settings.allowed_values
        if [[ "$ftype" == list_string || "$ftype" == list_integer ]]; then
            values=$(awk '
                /^settings:/ { s=1; next }
                s && /^[a-z]/ { exit }
                s && /allowed_values:/ { av=1; next }
                s && /allowed_values_function:/ { av=0; next }
                av && /value:/ {
                    sub(/.*value:\s*/, "")
                    gsub(/["\047]/, "")
                    gsub(/^[[:space:]]+|[[:space:]]+$/, "")
                    if (r != "") r = r "|"
                    r = r $0
                }
                END { print r }
            ' "$storage_file" 2>/dev/null)
            FIELD_ALLOWED_VALUES["$key"]="$values"
            ENTITY_LIST_COUNT["$entity_type"]=$(( ${ENTITY_LIST_COUNT["$entity_type"]:-0} + 1 ))
        fi

        ((TOTAL_STORAGE++)) || true
    done
done

# --- Pass 2: Parse field.field.*.yml ---
for config_dir in "${CONFIG_DIRS[@]}"; do
    for field_file in "$config_dir"/field.field.*.yml; do
        [[ -f "$field_file" ]] || continue

        bn=$(basename "$field_file" .yml)
        rest="${bn#field.field.}"
        entity_type="${rest%%.*}"
        rest2="${rest#*.}"
        bundle="${rest2%%.*}"
        field_name="${rest2#*.}"

        bundle_key="${entity_type}.${bundle}"
        field_key="${entity_type}.${bundle}.${field_name}"
        storage_key="${entity_type}.${field_name}"

        # Skip if no matching field.storage (orphaned field instance)
        [[ -z "${FIELD_TYPE[$storage_key]}" ]] && continue

        # Append to bundle field list
        if [[ -n "${BUNDLE_FIELDS[$bundle_key]}" ]]; then
            BUNDLE_FIELDS["$bundle_key"]+=" ${field_name}"
        else
            BUNDLE_FIELDS["$bundle_key"]="$field_name"
        fi

        # Label
        label=$(grep -m1 -E '^label:\s' "$field_file" | sed "s/^label:\s*//" | sed "s/^'//;s/'$//" | sed 's/^"//;s/"$//')
        FIELD_LABEL["$field_key"]="$label"

        # Description
        desc=$(grep -m1 -E '^description:\s' "$field_file" | sed "s/^description:\s*//" | sed "s/^'//;s/'$//" | sed 's/^"//;s/"$//')
        FIELD_DESC["$field_key"]="$desc"

        # Required
        req=$(grep -m1 -E '^required:\s' "$field_file" | sed 's/^required:\s*//' | tr -d '[:space:]')
        FIELD_REQUIRED["$field_key"]="$req"

        # Target bundles for entity_reference
        ftype="${FIELD_TYPE[$storage_key]}"
        if [[ "$ftype" == "entity_reference" || "$ftype" == "entity_reference_revisions" ]]; then
            bundles=$(awk '
                /target_bundles:/ {
                    found=1
                    match($0, /^[[:space:]]*/); base=RLENGTH
                    next
                }
                found && NF > 0 {
                    match($0, /^[[:space:]]*/); cur=RLENGTH
                    if (cur <= base) exit
                    line=$0
                    gsub(/^[[:space:]]+/, "", line)
                    if (line ~ /^[a-z_][a-z_0-9]*:/) {
                        sub(/:.*/, "", line)
                        if (r != "") r = r ","
                        r = r line
                    }
                }
                END { print r }
            ' "$field_file" 2>/dev/null)
            FIELD_TARGET_BUNDLES["$field_key"]="$bundles"
        fi
    done
done

# --- Output Phase ---

# 1. Generate JSON schemas per entity_type.bundle
for bundle_key in $(printf '%s\n' "${!BUNDLE_FIELDS[@]}" | sort); do
    entity_type="${bundle_key%%.*}"
    bundle="${bundle_key#*.}"
    fields="${BUNDLE_FIELDS[$bundle_key]}"

    json_file="$SCHEMA_DIR/${entity_type}.${bundle}.json"

    field_count=0
    ref_count=0
    list_count=0

    {
        printf '{\n'
        printf '  "entity_type": "%s",\n' "$entity_type"
        printf '  "bundle": "%s",\n' "$bundle"
        printf '  "fields": {\n'

        first=true
        for fn in $fields; do
            storage_key="${entity_type}.${fn}"
            field_key="${entity_type}.${bundle}.${fn}"
            ftype="${FIELD_TYPE[$storage_key]}"
            [[ -z "$ftype" ]] && continue

            if [[ "$first" == true ]]; then
                first=false
            else
                printf ',\n'
            fi

            printf '    "%s": {\n' "$fn"
            printf '      "type": "%s"' "$ftype"

            # Label
            [[ -n "${FIELD_LABEL[$field_key]}" ]] && \
                printf ',\n      "label": "%s"' "$(json_escape "${FIELD_LABEL[$field_key]}")"

            # Description
            [[ -n "${FIELD_DESC[$field_key]}" ]] && \
                printf ',\n      "description": "%s"' "$(json_escape "${FIELD_DESC[$field_key]}")"

            # Required
            if [[ "${FIELD_REQUIRED[$field_key]}" == "true" ]]; then
                printf ',\n      "required": true'
            else
                printf ',\n      "required": false'
            fi

            # Cardinality
            printf ',\n      "cardinality": %s' "${FIELD_CARDINALITY[$storage_key]:-1}"

            # Entity reference specifics
            if [[ "$ftype" == "entity_reference" || "$ftype" == "entity_reference_revisions" ]]; then
                ((ref_count++)) || true
                [[ -n "${FIELD_TARGET_TYPE[$storage_key]}" ]] && \
                    printf ',\n      "target_type": "%s"' "${FIELD_TARGET_TYPE[$storage_key]}"
                if [[ -n "${FIELD_TARGET_BUNDLES[$field_key]}" ]]; then
                    printf ',\n      "target_bundles": ['
                    IFS=',' read -ra tb_arr <<< "${FIELD_TARGET_BUNDLES[$field_key]}"
                    tb_first=true
                    for tb in "${tb_arr[@]}"; do
                        tb="${tb// /}"
                        [[ -z "$tb" ]] && continue
                        [[ "$tb_first" == true ]] && tb_first=false || printf ', '
                        printf '"%s"' "$tb"
                    done
                    printf ']'
                fi
            fi

            # List specifics
            if [[ "$ftype" == list_string || "$ftype" == list_integer ]]; then
                ((list_count++)) || true
                if [[ -n "${FIELD_ALLOWED_VALUES[$storage_key]}" ]]; then
                    printf ',\n      "allowed_values": ['
                    IFS='|' read -ra av_arr <<< "${FIELD_ALLOWED_VALUES[$storage_key]}"
                    av_first=true
                    for av in "${av_arr[@]}"; do
                        av="${av#"${av%%[![:space:]]*}"}"
                        av="${av%"${av##*[![:space:]]}"}"
                        [[ -z "$av" ]] && continue
                        [[ "$av_first" == true ]] && av_first=false || printf ', '
                        printf '"%s"' "$(json_escape "$av")"
                    done
                    printf ']'
                fi
            fi

            printf '\n    }'
            ((field_count++)) || true
        done

        printf '\n  },\n'
        printf '  "field_count": %d,\n' "$field_count"
        printf '  "ref_count": %d,\n' "$ref_count"
        printf '  "list_count": %d\n' "$list_count"
        printf '}\n'
    } > "$json_file"

    ((TOTAL_SCHEMAS++)) || true
done

# 2. Generate schemas.md summary
SUMMARY_FILE="$STRUCTURAL_DIR/schemas.md"
cat > "$SUMMARY_FILE" << 'HEADER'
# Entity Schemas
<!-- Auto-generated by generate-entity-schemas.sh — do not edit manually -->

| Entity Type | Bundle | Fields | References | Lists | Schema File |
|-------------|--------|--------|------------|-------|-------------|
HEADER

for bundle_key in $(printf '%s\n' "${!BUNDLE_FIELDS[@]}" | sort); do
    entity_type="${bundle_key%%.*}"
    bundle="${bundle_key#*.}"

    fc=0; rc=0; lc=0
    for fn in ${BUNDLE_FIELDS[$bundle_key]}; do
        storage_key="${entity_type}.${fn}"
        ftype="${FIELD_TYPE[$storage_key]}"
        [[ -z "$ftype" ]] && continue
        ((fc++)) || true
        [[ "$ftype" == "entity_reference" || "$ftype" == "entity_reference_revisions" ]] && { ((rc++)) || true; }
        [[ "$ftype" == list_string || "$ftype" == list_integer ]] && { ((lc++)) || true; }
    done

    echo "| \`$entity_type\` | \`$bundle\` | $fc | $rc | $lc | \`schemas/${entity_type}.${bundle}.json\` |" >> "$SUMMARY_FILE"
done

{
    echo ""
    echo "---"
    echo "**Total schemas**: $TOTAL_SCHEMAS"
    echo "**Total field.storage configs**: $TOTAL_STORAGE"
    echo "**Config dirs**: ${CONFIG_DIRS[*]}"
    echo "**Generated**: $(date -Iseconds)"
    echo ""
    echo "**Known limitations:**"
    echo "- Base fields (\`uid\`, \`created\`, \`changed\`, etc.) from PHP \`baseFieldDefinitions()\` are not included."
    echo "- Only configurable fields from YAML config are extracted."
    echo "- Config directory auto-detected from common locations (\`config/sync\`, \`config/default\`, etc.)."
} >> "$SUMMARY_FILE"

# 3. Patch entities.md with Fields column (skip if already patched)
if [[ -f "$ENTITIES_FILE" ]] && ! grep -q "| Fields |" "$ENTITIES_FILE" 2>/dev/null; then
    PATCHED_FILE="${ENTITIES_FILE}.tmp"
    > "$PATCHED_FILE"

    while IFS= read -r line; do
        if [[ "$line" == "| Entity Type | ID | Class | Handlers | Module | File |" ]]; then
            echo "| Entity Type | ID | Class | Handlers | Fields | Module | File |" >> "$PATCHED_FILE"
        elif [[ "$line" == "|------------|-----|-------|----------|--------|------|" ]]; then
            echo "|------------|-----|-------|----------|--------|--------|------|" >> "$PATCHED_FILE"
        elif echo "$line" | grep -qE '^\| .+ \| `[a-z_][a-z_0-9]*`' 2>/dev/null; then
            # Data row — extract entity ID from column 3
            entity_id=$(echo "$line" | awk -F'|' '{
                v=$3; gsub(/^[[:space:]]*`|`[[:space:]]*$/, "", v); print v
            }')

            fc="${ENTITY_FIELD_COUNT[$entity_id]:-0}"
            rc="${ENTITY_REF_COUNT[$entity_id]:-0}"
            lc="${ENTITY_LIST_COUNT[$entity_id]:-0}"

            if [[ "$fc" -eq 0 ]]; then
                fields_col="-"
            else
                parts=()
                [[ "$rc" -gt 0 ]] && parts+=("${rc} ref")
                [[ "$lc" -gt 0 ]] && parts+=("${lc} list")
                if [[ ${#parts[@]} -gt 0 ]]; then
                    fields_col="$fc ($(IFS=', '; echo "${parts[*]}"))"
                else
                    fields_col="$fc"
                fi
            fi

            # Insert Fields column after Handlers (column 5)
            echo "$line" | awk -F'|' -v fs=" $fields_col " '{
                for(i=1; i<=5; i++) printf "%s|", $i
                printf "%s", fs
                for(i=6; i<=NF; i++) {
                    if (i < NF) printf "|%s", $i
                    else printf "|"
                }
                printf "\n"
            }' >> "$PATCHED_FILE"
        else
            echo "$line" >> "$PATCHED_FILE"
        fi
    done < "$ENTITIES_FILE"

    mv "$PATCHED_FILE" "$ENTITIES_FILE"
fi

echo "  schemas: $TOTAL_STORAGE fields processed, $TOTAL_SCHEMAS schemas generated"
echo "  schemas: Config dirs: ${CONFIG_DIRS[*]}"
