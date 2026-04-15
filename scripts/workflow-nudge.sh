#!/usr/bin/env bash
# DEPRECATED: superseded by autopilot-monitor.sh (Phase 2). Not in hooks.json.
# workflow-nudge.sh
# PostToolUse Hook - Track session behavior and nudge toward delegation.
# Fires on ALL tool calls (matcher: .*). Tracks counters in a temp state
# file and emits an advisory when direct edits outpace agent delegation.
# Always exits 0 (advisory only, never blocks).

INPUT_JSON=$(cat)

# Extract tool_name from JSON
TOOL_NAME=""
if command -v jq >/dev/null 2>&1; then
    TOOL_NAME=$(echo "$INPUT_JSON" | jq -r '.tool_name // ""' 2>/dev/null)
fi
if [ -z "$TOOL_NAME" ] || [ "$TOOL_NAME" = "null" ]; then
    TOOL_NAME=$(echo "$INPUT_JSON" | grep -o '"tool_name":"[^"]*"' | head -1 | cut -d'"' -f4)
fi

# No tool name? Nothing to track.
if [ -z "$TOOL_NAME" ] || [ "$TOOL_NAME" = "null" ]; then
    exit 0
fi

# Use CLAUDE_PLUGIN_ROOT as stable anchor — always set, same across all hooks.
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SESSION_KEY=$(printf '%s' "$PLUGIN_ROOT" | md5sum | cut -c1-12)
STATE_DIR="/tmp/drupal-workflow-states/active-${SESSION_KEY}"
mkdir -p "$STATE_DIR" 2>/dev/null
chmod 700 "$STATE_DIR" 2>/dev/null
STATE_FILE="$STATE_DIR/counters.state"

# Safe state reader: grep/cut instead of sourcing arbitrary shell
read_state() {
    local key="$1"
    grep "^${key}=" "$STATE_FILE" 2>/dev/null | cut -d= -f2 || echo "0"
}

# Safe state writer: sed existing or append new key=value
write_state() {
    local key="$1" val="$2"
    if grep -q "^${key}=" "$STATE_FILE" 2>/dev/null; then
        sed -i "s/^${key}=.*/${key}=${val}/" "$STATE_FILE"
    else
        echo "${key}=${val}" >> "$STATE_FILE"
    fi
}

# Initialize state file if missing (e.g. session started without reset hook)
if [ ! -f "$STATE_FILE" ]; then
    cat > "$STATE_FILE" << 'INIT'
direct_edits=0
agent_dispatches=0
skill_invocations=0
task_creates=0
last_nudge_at=0
INIT
    chmod 600 "$STATE_FILE"
fi

# Update counters based on tool type (locked to prevent races)
(
    flock -n 9 || exit 0

    direct_edits=$(read_state direct_edits)
    agent_dispatches=$(read_state agent_dispatches)
    skill_invocations=$(read_state skill_invocations)
    task_creates=$(read_state task_creates)
    last_nudge_at=$(read_state last_nudge_at)

    case "$TOOL_NAME" in
        Edit|Write)
            direct_edits=$((direct_edits + 1))
            ;;
        Agent)
            agent_dispatches=$((agent_dispatches + 1))
            ;;
        Skill)
            skill_invocations=$((skill_invocations + 1))
            ;;
        TaskCreate)
            task_creates=$((task_creates + 1))
            ;;
    esac

    # Write updated state
    write_state direct_edits "$direct_edits"
    write_state agent_dispatches "$agent_dispatches"
    write_state skill_invocations "$skill_invocations"
    write_state task_creates "$task_creates"
    write_state last_nudge_at "$last_nudge_at"

    # Only evaluate nudge on Edit/Write calls
    case "$TOOL_NAME" in
        Edit|Write) ;;
        *) exit 0 ;;
    esac

    # Check if nudge conditions are met:
    # - More than 5 direct edits
    # - Fewer than 2 agent dispatches
    # - Zero skill invocations
    # - At least 5 edits since last nudge
    if [ "$direct_edits" -gt 5 ] \
        && [ "$agent_dispatches" -lt 2 ] \
        && [ "$skill_invocations" -lt 1 ] \
        && [ $((direct_edits - last_nudge_at)) -ge 5 ]; then

        write_state last_nudge_at "$direct_edits"

        echo "WORKFLOW HINT: You've made $direct_edits direct edits without delegating to specialized agents."
        echo "Consider: /drupal-blast-radius before multi-file changes, @drupal-builder for implementation, @drupal-verifier after."
    fi
) 9>"$STATE_FILE.lock"

exit 0
