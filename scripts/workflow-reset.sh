#!/usr/bin/env bash
# workflow-reset.sh
# SessionStart Hook - Reset workflow tracking state for new session.
# Always exits 0 (never blocks session start).

# Unique session ID fallback: PID + epoch when CLAUDE_SESSION_ID is empty
SESSION_ID="${CLAUDE_SESSION_ID:-$$_$(date +%s)}"

# Session-scoped state directory with restrictive permissions
STATE_DIR="/tmp/drupal-workflow-states/session-${SESSION_ID}"
mkdir -p "$STATE_DIR" 2>/dev/null
chmod 700 "$STATE_DIR" 2>/dev/null

# Legacy flat counters (consumed by workflow-nudge.sh)
STATE_FILE="$STATE_DIR/counters.state"
cat > "$STATE_FILE" << 'EOF'
direct_edits=0
agent_dispatches=0
skill_invocations=0
task_creates=0
last_nudge_at=0
EOF
chmod 600 "$STATE_FILE"

# Autopilot state vector (consumed by task-classifier.sh and future nudge logic)
cat > "$STATE_DIR/state.json" << 'EOF'
{
  "turn": 0,
  "phase": "planning",
  "edits": 0,
  "delegations": 0,
  "skills_used": [],
  "agents_dispatched": [],
  "plan_exists": false,
  "verification_done": false,
  "task_tracking": 0,
  "tasks_created": 0,
  "reads": 0,
  "drift_score": 0.0,
  "intervention_count": 0,
  "last_intervention_turn": 0,
  "policy_task_type": "implementation"
}
EOF
chmod 600 "$STATE_DIR/state.json"

exit 0
