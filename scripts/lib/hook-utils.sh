#!/bin/bash
# hook-utils.sh
# Shared utilities for Claude Code hook scripts.
# Provides JSON parsing, Unicode normalization, handoff detection, and logging.

LOG_FILE="${HOOK_LOG_FILE:-/tmp/test-driven-handoff.log}"

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

log() {
    echo "[$(timestamp)] $1" >> "$LOG_FILE"
}

# Parse a JSON field using jq with grep/sed fallback.
# Usage: json_field "$json_string" ".path.to.field" "fallback_key"
# The fallback_key is the bare key name for grep extraction.
json_field() {
    local json="$1" jq_path="$2" fallback_key="$3"
    local value=""

    if command -v jq >/dev/null 2>&1; then
        value=$(echo "$json" | jq -r "$jq_path" 2>/dev/null)
    fi

    if [[ -z "$value" || "$value" == "null" ]]; then
        value=$(echo "$json" | grep -o "\"$fallback_key\":\"[^\"]*\"" | head -1 | cut -d'"' -f4)
    fi

    echo "$value"
}

# Extract agent output text from hook JSON.
# Tries jq, then python3, then transcript file fallback.
extract_agent_output() {
    local json="$1" transcript_path="$2"
    local output=""

    output=$(echo "$json" | jq -r '.tool_response.content[].text' 2>/dev/null)

    if [[ -z "$output" || "$output" == "null" ]]; then
        output=$(echo "$json" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for item in data.get('tool_response', {}).get('content', []):
        if 'text' in item:
            print(item['text']); break
except: pass
" 2>/dev/null)
    fi

    if [[ -z "$output" && -n "$transcript_path" && -f "$transcript_path" ]]; then
        output=$(tail -10 "$transcript_path" | jq -r 'select(.type == "assistant") | .message.content[]? | select(type == "string")' 2>/dev/null | tail -1)
    fi

    echo "$output"
}

# Normalize Unicode dashes to ASCII hyphen and collapse whitespace.
normalize_text() {
    local input="$1"
    echo "$input" | sed 's/[–—‑−]/-/g' | tr -s '[:space:]' ' '
}

# Detect handoff directive pattern: "Use the <agent-name> subagent to ..."
# Echoes the agent name if found, returns 0. Returns 1 if not found.
detect_handoff_pattern() {
    local text
    text=$(normalize_text "$1")

    local agent
    agent=$(echo "$text" | grep -io 'Use the [a-z0-9-]* subagent to' | head -1 | sed 's/[Uu]se the //' | sed 's/ subagent to.*//')

    if [[ -n "$agent" ]]; then
        echo "$agent"
        return 0
    fi
    return 1
}
