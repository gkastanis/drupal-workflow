#!/usr/bin/env bash
# task-classifier.sh — Classify user's task and write session policy
# SessionStart hook: reads first user message, selects policy template
# Always exits 0 (SessionStart requirement)

set -u

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SESSION_ID="${CLAUDE_SESSION_ID:-$$_$(date +%s)}"
STATE_DIR="/tmp/drupal-workflow-states/session-${SESSION_ID}"
POLICIES_DIR="${PLUGIN_ROOT}/scripts/policies"

mkdir -p "$STATE_DIR" 2>/dev/null
chmod 700 "$STATE_DIR" 2>/dev/null

# Read input from stdin (Claude provides session context as JSON)
INPUT=$(cat 2>/dev/null || true)

# Extract first user message text
PROMPT=""
if command -v jq >/dev/null 2>&1; then
    PROMPT=$(echo "$INPUT" | jq -r '.message.content // .content // ""' 2>/dev/null | head -c 500)
fi
if [ -z "$PROMPT" ] || [ "$PROMPT" = "null" ]; then
    PROMPT=$(echo "$INPUT" | grep -oE '"text":"[^"]*"' | head -1 | cut -d'"' -f4 | head -c 500)
fi

PROMPT_LOWER=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')

# Classify by keyword priority: debugging > implementation > investigation > refactoring > documentation
TASK_TYPE="implementation"  # default

if echo "$PROMPT_LOWER" | grep -qE 'fix|broken|error|failing|bug|not working|crash|debug'; then
    TASK_TYPE="debugging"
elif echo "$PROMPT_LOWER" | grep -qE 'create|add|build|implement|module|entity|service|feature|write a|make a'; then
    TASK_TYPE="implementation"
elif echo "$PROMPT_LOWER" | grep -qE 'why|how does|trace|find|what|explain|where|show me|look at'; then
    TASK_TYPE="investigation"
elif echo "$PROMPT_LOWER" | grep -qE 'refactor|rename|move|clean.up|reorganize|extract|split|merge'; then
    TASK_TYPE="refactoring"
elif echo "$PROMPT_LOWER" | grep -qE 'document|readme|spec|write.up|describe|changelog'; then
    TASK_TYPE="documentation"
fi

# Copy policy template to session dir
POLICY_FILE="${POLICIES_DIR}/${TASK_TYPE}.json"
if [ -f "$POLICY_FILE" ]; then
    cp "$POLICY_FILE" "$STATE_DIR/policy.json"
else
    echo '{"task_type":"implementation","min_skills":1,"min_delegations":0,"require_plan":false,"require_verification":false}' > "$STATE_DIR/policy.json"
fi

# Emit classification for session context
echo "AUTOPILOT: Task classified as '${TASK_TYPE}'. Policy loaded."

# Show recommended skills for this task type
SKILLS=""
if command -v jq >/dev/null 2>&1 && [ -f "$STATE_DIR/policy.json" ]; then
    SKILLS=$(jq -r '.recommended_skills // [] | join(", ")' "$STATE_DIR/policy.json" 2>/dev/null)
fi
if [ -n "$SKILLS" ] && [ "$SKILLS" != "null" ]; then
    echo "  Recommended skills: $SKILLS"
fi

if echo "$TASK_TYPE" | grep -qE 'implementation|refactoring'; then
    echo "  Workflow: brainstorm -> plan -> delegate -> verify"
fi

exit 0
