#!/usr/bin/env bash
# autopilot-monitor.sh — Live session monitor for Magic Loop Autopilot
# PostToolUse hook (matcher: .*) — fires on every tool call
# Updates state vector, detects drift, emits interventions
# Always exits 0 (advisory only, never blocks)

set -u

# Kill switch: set DRUPAL_WORKFLOW_AUTOPILOT=off to disable
[ "${DRUPAL_WORKFLOW_AUTOPILOT:-on}" = "off" ] && exit 0

INPUT_JSON=$(cat 2>/dev/null || true)
[ -z "$INPUT_JSON" ] && exit 0

# Extract tool_name from JSON (with jq fallback to grep)
TOOL_NAME=""
if command -v jq >/dev/null 2>&1; then
    TOOL_NAME=$(echo "$INPUT_JSON" | jq -r '.tool_name // ""' 2>/dev/null)
fi
if [ -z "$TOOL_NAME" ] || [ "$TOOL_NAME" = "null" ]; then
    TOOL_NAME=$(echo "$INPUT_JSON" | grep -o '"tool_name":"[^"]*"' | head -1 | cut -d'"' -f4 || true)
fi

# No tool name? Nothing to track
[ -z "$TOOL_NAME" ] || [ "$TOOL_NAME" = "null" ] && exit 0

# Session ID and project dir are not exposed to hooks. Use a single well-known
# active state directory, namespaced by plugin root, so every hook resolves the
# same path regardless of cwd.
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SESSION_KEY=$(printf '%s' "$PLUGIN_ROOT" | md5sum | cut -c1-12)
STATE_DIR="/tmp/drupal-workflow-states/active-${SESSION_KEY}"
STATE_FILE="$STATE_DIR/state.json"
POLICY_FILE="$STATE_DIR/policy.json"
LOCK_FILE="$STATE_DIR/state.lock"
LOG_FILE="$STATE_DIR/interventions.log"

# Create state dir if missing
mkdir -p "$STATE_DIR" 2>/dev/null || exit 0
chmod 700 "$STATE_DIR" 2>/dev/null || exit 0

# Initialize state if missing
if [ ! -f "$STATE_FILE" ]; then
    cat > "$STATE_FILE" << 'INIT'
{
  "turn": 0,
  "phase": "planning",
  "edits": 0,
  "reads": 0,
  "delegations": 0,
  "skills_used": [],
  "agents_dispatched": [],
  "plan_exists": false,
  "verification_done": false,
  "tasks_created": 0,
  "last_intervention_turn": 0,
  "intervention_count": 0,
  "drift_score": 0.0,
  "policy_task_type": "implementation"
}
INIT
    chmod 600 "$STATE_FILE"
fi

# Atomic read-modify-write with flock
(
    flock -n 9 || exit 0

    # Create Python script to read/update state (using separate file to avoid heredoc issues)
    PYUPDATE="/tmp/autopilot-update-$$.py"
    cat > "$PYUPDATE" << 'PYEOF'
import json
import sys
import datetime as _dt

state_file = sys.argv[1]
policy_file = sys.argv[2]
tool_name = sys.argv[3]
raw_input = sys.argv[4] if len(sys.argv) > 4 else "{}"
try:
    input_json = json.loads(raw_input) if isinstance(raw_input, str) else raw_input
except:
    input_json = {}

# Read current state
with open(state_file) as f:
    state = json.load(f)

# Read policy if exists
policy = {}
try:
    with open(policy_file) as f:
        policy = json.load(f)
except:
    policy = {
        "require_plan": False,
        "min_delegations": 0,
        "min_skills": 0,
        "require_verification": False
    }

# Update counters based on tool type
if tool_name in ["Edit", "Write"]:
    state["edits"] += 1
    state["turn"] += 1
elif tool_name in ["Read", "Grep", "Glob"]:
    state["reads"] += 1
elif tool_name == "Agent":
    state["delegations"] += 1
    state["turn"] += 1
elif tool_name == "Skill":
    state["turn"] += 1
    # Track skill usage
    tool_input = input_json.get("tool_input", {}) if isinstance(input_json, dict) else {}
    if isinstance(tool_input, str):
        try: tool_input = json.loads(tool_input)
        except: tool_input = {}
    skill = tool_input.get("skill", "") if isinstance(tool_input, dict) else ""
    if skill:
        if skill not in state["skills_used"]:
            state["skills_used"].append(skill)
        # Check for planning and verification skills
        if any(x in skill for x in ["writing-plans", "brainstorm"]):
            state["plan_exists"] = True
        if any(x in skill for x in ["drupal-test", "drupal-verif"]):
            state["verification_done"] = True
elif tool_name in ["TaskCreate", "TaskUpdate"]:
    state["tasks_created"] += 1
    state["turn"] += 1
    if state["tasks_created"] >= 2:
        state["plan_exists"] = True

# Compute phase
if state["plan_exists"] == False and state["edits"] == 0:
    state["phase"] = "planning"
elif state["edits"] > 0 and state["verification_done"] == False:
    state["phase"] = "implementing"
elif state["verification_done"] == True:
    state["phase"] = "verifying"
else:
    state["phase"] = "exploring"

# Compute drift score
drift = 0.0
plan_drift = False
delegate_drift = False
skill_drift = False
verify_drift = False

# Plan missing when required
if policy.get("require_plan", False) and not state["plan_exists"] and state["edits"] > 3:
    plan_drift = True
    drift = max(drift, 0.3)

# Delegation missing when required
if policy.get("min_delegations", 0) > 0 and state["delegations"] < policy.get("min_delegations", 0) and state["edits"] > 5:
    delegate_drift = True
    drift = max(drift, 0.3)

# Skills not consulted
if len(state["skills_used"]) < policy.get("min_skills", 0) and state["turn"] > 5:
    skill_drift = True
    drift = max(drift, 0.2)

# No verification when required
if policy.get("require_verification", False) and not state["verification_done"] and state["edits"] > 8:
    verify_drift = True
    drift = max(drift, 0.2)

state["drift_score"] = drift

# Check if intervention should fire
should_intervene = False
intervention_type = ""
intervention_msg = ""

turns_since = state["turn"] - state["last_intervention_turn"]
if turns_since >= 3 and state["intervention_count"] < 5:
    if tool_name in ["Edit", "Write"]:
        # Priority: plan > delegate > skill
        if plan_drift and policy.get("require_plan", False):
            should_intervene = True
            intervention_type = "plan_missing"
            skills_hint = ", ".join(policy.get("recommended_skills", [])[:3])
            intervention_msg = (
                f"STOP. You have made {state['edits']} edits without a plan. "
                f"This is an implementation task — the policy requires planning before coding.\n"
                f"You MUST invoke the Skill tool now:\n"
                f'  Skill({{skill: "drupal-brainstorming"}})\n'
                f"Then after brainstorming:\n"
                f'  Skill({{skill: "writing-plans"}})\n'
                f"Do not make further edits until you have a plan."
            )
        elif delegate_drift:
            should_intervene = True
            intervention_type = "delegate_suggest"
            intervention_msg = (
                f"You have made {state['edits']} direct edits without delegating. "
                f"Use the Agent tool to dispatch specialized agents:\n"
                f'  Agent({{subagent_type: "drupal-workflow:drupal-builder", description: "...", prompt: "..."}})\n'
                f"Specialized agents produce higher-quality code and can work in parallel."
            )
        elif skill_drift:
            should_intervene = True
            intervention_type = "skill_suggest"
            skills_hint = ", ".join(policy.get("recommended_skills", [])[:3])
            intervention_msg = (
                f"No skills consulted yet. Before continuing, invoke:\n"
                f'  Skill({{skill: "discover"}})\n'
                f"Recommended for this task: {skills_hint}"
            )

    # Verification nudge fires on ANY tool when edits are substantial and no verification yet
    if not should_intervene and verify_drift and policy.get("require_verification", False):
        if state["edits"] >= 5 and state["delegations"] >= 1:
            should_intervene = True
            intervention_type = "verify_remind"
            intervention_msg = (
                f"Implementation appears complete ({state['edits']} edits, {state['delegations']} agents dispatched). "
                f"You MUST verify before claiming completion. Invoke:\n"
                f'  Agent({{subagent_type: "drupal-workflow:drupal-verifier", description: "Verify implementation", prompt: "..."}})\n'
                f"Or run: Skill({{skill: \"drupal-workflow:drupal-verify\"}})"
            )

# Log intervention if fired
if should_intervene and intervention_type:
    state["intervention_count"] += 1
    state["last_intervention_turn"] = state["turn"]

    # Append to interventions log
    log_entry = {
        "turn": state["turn"],
        "type": intervention_type,
        "drift_score": drift,
        "phase": state["phase"],
        "message": intervention_msg,
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat()
    }

    try:
        with open(sys.argv[5]) as f:
            log_data = f.read()
    except:
        log_data = ""

    with open(sys.argv[5], "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    # Print to stdout — PostToolUse stdout is injected into the conversation as
    # actionable context the agent must process (stderr is ignored as noise)
    print(f"AUTOPILOT [{intervention_type}]: {intervention_msg}")

# Write updated state
with open(state_file, "w") as f:
    json.dump(state, f, indent=2)

sys.exit(0)
PYEOF

    python3 "$PYUPDATE" "$STATE_FILE" "$POLICY_FILE" "$TOOL_NAME" "$INPUT_JSON" "$LOG_FILE" 2>&1
    rm -f "$PYUPDATE"

) 9>"$LOCK_FILE"

exit 0
