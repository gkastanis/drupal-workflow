#!/bin/bash
# inject-claude-md.sh - Add/update ## Codebase section in CLAUDE.md
# Creates CLAUDE.md if it doesn't exist. Idempotent — safe to run repeatedly.
set -e

PROJECT_DIR="${1:-${CLAUDE_PROJECT_DIR:-$(pwd)}}"
CLAUDE_MD="$PROJECT_DIR/CLAUDE.md"
TECH_DIR="$PROJECT_DIR/docs/semantic/tech"
PROJECT_NAME=$(basename "$PROJECT_DIR" | tr '[:lower:]' '[:upper:]' | tr '-' ' ')

# Bail if no tech specs exist.
if ! ls "$TECH_DIR"/*.md &>/dev/null; then
    echo "  No tech specs found in $TECH_DIR — skipping CLAUDE.md injection"
    exit 0
fi

# --- Gather stats ---

# Feature count.
FEATURE_COUNT=$(ls "$TECH_DIR"/*.md 2>/dev/null | wc -l)
FEATURE_COUNT=$(echo "$FEATURE_COUNT" | tr -d ' ')

# Logic ID count from frontmatter logic_id_count fields.
LOGIC_IDS=$(grep -h '^logic_id_count:' "$TECH_DIR"/*.md 2>/dev/null | awk -F': ' '{s+=$2} END {print s+0}')

# Module count from tech spec frontmatter (more complete than services.md).
MODULE_COUNT=$(grep -h '^module:' "$TECH_DIR"/*.md 2>/dev/null \
    | awk -F': ' '{print $2}' \
    | tr ',' '\n' \
    | sed 's/^ *//;s/ *$//' \
    | grep -v '(contrib)' \
    | sort -u \
    | wc -l)
MODULE_COUNT=$(echo "$MODULE_COUNT" | tr -d ' ')

# --- Build feature code listing ---
# CODE:Name pairs, pipe-separated, ~6 per line.
FEATURES=""
PER_LINE=0
for spec in "$TECH_DIR"/*.md; do
    [[ -f "$spec" ]] || continue
    CODE=$(basename "$spec" | sed -E 's/^([A-Z]+)_.*/\1/')
    NAME=$(basename "$spec" .md | sed -E 's/^[A-Z]+_[0-9]+_//')
    ENTRY="${CODE}:${NAME}"

    if [[ -z "$FEATURES" ]]; then
        FEATURES="$ENTRY"
        PER_LINE=1
    elif [[ $PER_LINE -ge 6 ]]; then
        FEATURES="${FEATURES}"$'\n'"${ENTRY}"
        PER_LINE=1
    else
        FEATURES="${FEATURES}|${ENTRY}"
        ((PER_LINE++)) || true
    fi
done

# --- Compose section ---
SECTION="## Codebase

- ${FEATURE_COUNT} features, ${LOGIC_IDS} Logic IDs across ${MODULE_COUNT} custom modules
- **Read \`docs/semantic/00_BUSINESS_INDEX.md\` first** — feature registry with Logic IDs
- Logic ID lookup: \`docs/semantic/tech/{CODE}_*.md\` | \`/discover \"terms\"\` for cross-feature search
- Tech specs: \`docs/semantic/tech/*.md\` | Structural: \`docs/semantic/structural/*.md\`

${FEATURES}"

# --- Inject into CLAUDE.md ---

if [[ ! -f "$CLAUDE_MD" ]]; then
    # Create new CLAUDE.md.
    printf "# %s\n\n%s\n" "$PROJECT_NAME" "$SECTION" > "$CLAUDE_MD"
    echo "  Created CLAUDE.md with Codebase section ($FEATURE_COUNT features, $LOGIC_IDS Logic IDs)"
elif grep -q '^## Codebase' "$CLAUDE_MD"; then
    # Replace existing ## Codebase section (up to next ## or EOF).
    awk -v section="$SECTION" '
        /^## Codebase/ { replacing=1; print section; next }
        replacing && /^## / { replacing=0; print "" }
        !replacing { print }
    ' "$CLAUDE_MD" > "${CLAUDE_MD}.tmp" && mv "${CLAUDE_MD}.tmp" "$CLAUDE_MD"
    echo "  Updated CLAUDE.md Codebase section ($FEATURE_COUNT features, $LOGIC_IDS Logic IDs)"
else
    # Append to existing CLAUDE.md.
    printf "\n%s\n" "$SECTION" >> "$CLAUDE_MD"
    echo "  Appended Codebase section to CLAUDE.md ($FEATURE_COUNT features, $LOGIC_IDS Logic IDs)"
fi
