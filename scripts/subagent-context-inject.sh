#!/bin/bash
# subagent-context-inject.sh - Injects project context when agents spawn.
# SubagentStart hook: provides environment hints, validates agent name
# against dynamically discovered agents, and injects memory path hints.

# Resolve plugin root directory.
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# Source shared utilities with inline fallback.
source "$PLUGIN_ROOT/scripts/lib/hook-utils.sh" 2>/dev/null || {
    timestamp() { date '+%Y-%m-%d %H:%M:%S'; }
    log() { echo "[$(timestamp)] $1" >> "$LOG_FILE"; }
    json_field() {
        local json="$1" jq_path="$2" fallback_key="$3" value=""
        if command -v jq >/dev/null 2>&1; then value=$(echo "$json" | jq -r "$jq_path" 2>/dev/null); fi
        if [[ -z "$value" || "$value" == "null" ]]; then value=$(echo "$json" | grep -o "\"$fallback_key\":\"[^\"]*\"" | head -1 | cut -d'"' -f4); fi
        echo "$value"
    }
}

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
AGENT_NAME="${SUBAGENT_NAME:-unknown}"
LOG_FILE="${LOG_FILE:-/tmp/subagent-context-inject.log}"

log "SubagentStart hook triggered for agent: $AGENT_NAME"

# Dynamically discover valid agents from plugin agent files.
VALID_AGENTS=""
if [ -d "$PLUGIN_ROOT/agents" ]; then
    for agent_file in "$PLUGIN_ROOT"/agents/*.md; do
        if [ -f "$agent_file" ]; then
            agent_basename=$(basename "$agent_file" .md)
            if [ -n "$VALID_AGENTS" ]; then
                VALID_AGENTS="$VALID_AGENTS $agent_basename"
            else
                VALID_AGENTS="$agent_basename"
            fi
        fi
    done
fi

# Validate agent name against discovered registry.
AGENT_VALID=0
for valid in $VALID_AGENTS; do
    if [[ "$AGENT_NAME" == "$valid" ]]; then
        AGENT_VALID=1
        break
    fi
done

if [[ "$AGENT_VALID" -eq 0 && "$AGENT_NAME" != "unknown" && "$AGENT_NAME" != "mock-"* ]]; then
    log "WARNING: Unknown agent name '$AGENT_NAME' - not in discovered agent registry"
    if [ -n "$VALID_AGENTS" ]; then
        echo "WARNING: Agent '$AGENT_NAME' is not in the plugin agent registry. Valid agents: $VALID_AGENTS"
    else
        echo "WARNING: Agent '$AGENT_NAME' could not be validated (no agents discovered in $PLUGIN_ROOT/agents/)"
    fi
fi

# Inject agent memory path hint.
MEMORY_DIR="$PROJECT_DIR/.claude/agent-memory/$AGENT_NAME"
if [[ -d "$MEMORY_DIR" ]]; then
    log "Agent memory directory exists: $MEMORY_DIR"
    echo "AGENT MEMORY: Review .claude/agent-memory/$AGENT_NAME/MEMORY.md for project-specific knowledge. Update on completion."
fi

# Inject project environment hints.
if [[ -f "$PROJECT_DIR/composer.json" ]]; then
    DRUPAL_VERSION=""
    if command -v jq >/dev/null 2>&1; then
        DRUPAL_VERSION=$(jq -r '.require["drupal/core"] // .require["drupal/core-recommended"] // "unknown"' "$PROJECT_DIR/composer.json" 2>/dev/null)
    fi
    if [[ -n "$DRUPAL_VERSION" && "$DRUPAL_VERSION" != "null" && "$DRUPAL_VERSION" != "unknown" ]]; then
        echo "PROJECT ENVIRONMENT: Drupal $DRUPAL_VERSION"
    fi
fi

log "Context injection complete for $AGENT_NAME"
