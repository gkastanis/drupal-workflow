#!/usr/bin/env bash
# workflow-reset.sh
# SessionStart Hook - Reset workflow tracking state for new session.
# Always exits 0 (never blocks session start).

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# Hooks do not receive a stable session or project identifier. Use a single
# well-known active state directory, namespaced by plugin root, so every hook
# resolves the same path regardless of cwd.
SESSION_KEY=$(printf '%s' "$PLUGIN_ROOT" | md5sum | cut -c1-12)
STATE_DIR="/tmp/drupal-workflow-states/active-${SESSION_KEY}"
OUTCOMES_FILE="$STATE_DIR/outcomes.jsonl"
mkdir -p "$STATE_DIR" 2>/dev/null
chmod 700 "$STATE_DIR" 2>/dev/null

# Archive previous session state before resetting (if it had any activity)
if [ -f "$STATE_DIR/state.json" ]; then
    PREV_EDITS=$(python3 -c "import json; print(json.load(open('$STATE_DIR/state.json')).get('edits',0))" 2>/dev/null || echo 0)
    if [ "$PREV_EDITS" -gt 0 ] 2>/dev/null; then
        python3 -c "
import json, datetime as dt, pathlib
state = json.load(open('$STATE_DIR/state.json'))
# Include intervention log entries in the outcome
log_path = pathlib.Path('$STATE_DIR/interventions.log')
interventions = []
if log_path.exists():
    for line in log_path.read_text().splitlines():
        line = line.strip()
        if line:
            try: interventions.append(json.loads(line))
            except: pass
outcome = {
    'archived_at': dt.datetime.now(dt.timezone.utc).isoformat(),
    'turn': state.get('turn', 0),
    'phase': state.get('phase', ''),
    'edits': state.get('edits', 0),
    'reads': state.get('reads', 0),
    'delegations': state.get('delegations', 0),
    'skills_used': state.get('skills_used', []),
    'plan_exists': state.get('plan_exists', False),
    'verification_done': state.get('verification_done', False),
    'tasks_created': state.get('tasks_created', 0),
    'drift_score': state.get('drift_score', 0.0),
    'intervention_count': state.get('intervention_count', 0),
    'intervention_history': state.get('intervention_history', {}),
    'policy_task_type': state.get('policy_task_type', ''),
    'budget_exceeded': state.get('budget_exceeded', False),
    'interventions': interventions,
}
with open('$OUTCOMES_FILE', 'a') as f:
    f.write(json.dumps(outcome) + '\n')
# Truncate intervention log for clean next session
log_path.write_text('')
" 2>/dev/null || true
    fi
fi

# Autopilot state vector (consumed by task-classifier.sh and autopilot-monitor.sh)
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
  "policy_task_type": "implementation",
  "intervention_history": {}
}
EOF
chmod 600 "$STATE_DIR/state.json"

exit 0
