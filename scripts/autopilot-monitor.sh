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
  "policy_task_type": "implementation",
  "intervention_history": {}
}
INIT
    chmod 600 "$STATE_FILE"
fi

# Atomic read-modify-write with flock
(
    flock -w 1 9 || exit 0

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

# One-time banner on first tool call of the session
if state["turn"] == 0 and state["edits"] == 0 and state["reads"] == 0:
    task_type = policy.get("task_type", state.get("policy_task_type", "unknown"))
    req = []
    if policy.get("require_plan"): req.append("plan")
    if policy.get("require_verification"): req.append("verify")
    if policy.get("min_delegations", 0) > 0: req.append("delegate")
    skills_hint = ", ".join(policy.get("recommended_skills", [])[:3])
    banner = f"AUTOPILOT active | task={task_type}"
    if req: banner += f" | requires: {', '.join(req)}"
    if skills_hint: banner += f" | skills: {skills_hint}"
    print(banner)

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

# Check phase budgets
phase_budgets = policy.get("phase_budget", {})
current_budget = phase_budgets.get(state["phase"], {})
budget_exceeded = False
budget_msg = ""

if "max_edits" in current_budget and state["edits"] > current_budget["max_edits"]:
    budget_exceeded = True
    budget_msg = f"Phase '{state['phase']}' allows max {current_budget['max_edits']} edits, you have {state['edits']}."

if "max_turns" in current_budget and state["turn"] > current_budget["max_turns"]:
    budget_exceeded = True
    budget_msg += f" Phase '{state['phase']}' allows max {current_budget['max_turns']} turns, you are at {state['turn']}."

state["budget_exceeded"] = budget_exceeded
state["_budget_msg"] = budget_msg.strip()

# Compute drift score (weighted sum)
drift_components = {
    "plan": 0.0,
    "delegate": 0.0,
    "skill": 0.0,
    "verify": 0.0,
}

if policy.get("require_plan", False) and not state["plan_exists"] and state["edits"] > 5:
    drift_components["plan"] = 1.0

if policy.get("min_delegations", 0) > 0 and state["delegations"] < policy.get("min_delegations", 0) and state["edits"] > 5:
    drift_components["delegate"] = 1.0

if len(state["skills_used"]) < policy.get("min_skills", 0) and state["turn"] > 5:
    drift_components["skill"] = 1.0

if policy.get("require_verification", False) and not state["verification_done"] and state["edits"] > 8:
    drift_components["verify"] = 1.0

DRIFT_WEIGHTS = {"plan": 0.3, "delegate": 0.3, "skill": 0.2, "verify": 0.2}
drift = sum(drift_components[k] * DRIFT_WEIGHTS[k] for k in drift_components)

plan_drift = drift_components["plan"] > 0
delegate_drift = drift_components["delegate"] > 0
skill_drift = drift_components["skill"] > 0
verify_drift = drift_components["verify"] > 0

state["drift_score"] = drift

# Escalation levels: 1=hint (gentle), 2=command (firm), 3+=suppress (silent)
MAX_FIRES_PER_TYPE = 2

def get_escalation_level(itype):
    hist = state.get("intervention_history", {})
    return hist.get(itype, {}).get("count", 0) + 1

def record_intervention(itype):
    hist = state.setdefault("intervention_history", {})
    entry = hist.setdefault(itype, {"count": 0, "turns": []})
    entry["count"] += 1
    entry["turns"].append(state["turn"])

# Check if intervention should fire
should_intervene = False
intervention_type = ""
intervention_msg = ""

turns_since = state["turn"] - state["last_intervention_turn"]
if turns_since >= 3 and state["intervention_count"] < 8:
    if tool_name in ["Edit", "Write"]:
        # Highest priority: phase budget exceeded
        if state.get("budget_exceeded", False):
            level = get_escalation_level("phase_budget_exceeded")
            if level <= MAX_FIRES_PER_TYPE:
                should_intervene = True
                intervention_type = "phase_budget_exceeded"
                if level == 1:
                    intervention_msg = (
                        f"Phase budget warning: you are in '{state['phase']}' phase. "
                        f"{state.get('_budget_msg', '')} "
                        f"Consider moving to the next phase."
                    )
                else:
                    intervention_msg = (
                        f"Phase budget EXCEEDED for '{state['phase']}' — second warning. "
                        f"{state.get('_budget_msg', '')} "
                        f"You MUST transition to the next workflow phase NOW."
                    )

        # Priority: plan > delegate > skill
        elif plan_drift and policy.get("require_plan", False):
            level = get_escalation_level("plan_missing")
            if level <= MAX_FIRES_PER_TYPE:
                should_intervene = True
                intervention_type = "plan_missing"
                if level == 1:
                    skills_hint = ", ".join(policy.get("recommended_skills", [])[:3])
                    intervention_msg = (
                        f"You have made {state['edits']} edits without a plan. "
                        f"Consider invoking Skill({{skill: \"drupal-brainstorming\"}}) "
                        f"followed by Skill({{skill: \"writing-plans\"}}) before continuing. "
                        f"Recommended: {skills_hint}"
                    )
                else:
                    intervention_msg = (
                        f"STOP. You have made {state['edits']} edits without a plan — this is the second warning. "
                        f"You MUST invoke the Skill tool NOW:\n"
                        f'  Skill({{skill: "drupal-brainstorming"}})\n'
                        f"Then:\n"
                        f'  Skill({{skill: "writing-plans"}})\n'
                        f"Do not make further edits until you have a plan."
                    )

        elif delegate_drift:
            level = get_escalation_level("delegate_suggest")
            if level <= MAX_FIRES_PER_TYPE:
                should_intervene = True
                intervention_type = "delegate_suggest"
                if level == 1:
                    intervention_msg = (
                        f"You have made {state['edits']} direct edits. "
                        f"Consider using the Agent tool to dispatch specialized agents for parallel work."
                    )
                else:
                    intervention_msg = (
                        f"You have made {state['edits']} direct edits without delegating — second warning. "
                        f"Use the Agent tool NOW:\n"
                        f'  Agent({{subagent_type: "drupal-workflow:drupal-builder", description: "...", prompt: "..."}})\n'
                        f"Specialized agents produce higher-quality code."
                    )

        elif skill_drift:
            level = get_escalation_level("skill_suggest")
            if level <= MAX_FIRES_PER_TYPE:
                should_intervene = True
                intervention_type = "skill_suggest"
                skills_hint = ", ".join(policy.get("recommended_skills", [])[:3])
                if level == 1:
                    intervention_msg = (
                        f"No skills consulted yet. Consider invoking: "
                        f'Skill({{skill: "discover"}}). '
                        f"Recommended: {skills_hint}"
                    )
                else:
                    intervention_msg = (
                        f"Still no skills consulted — second warning. Invoke NOW:\n"
                        f'  Skill({{skill: "discover"}})\n'
                        f"Recommended: {skills_hint}"
                    )

    # Verification nudge fires on ANY tool when edits are substantial and no verification yet
    if not should_intervene and verify_drift and policy.get("require_verification", False):
        if state["edits"] >= 5:
            level = get_escalation_level("verify_remind")
            if level <= MAX_FIRES_PER_TYPE:
                should_intervene = True
                intervention_type = "verify_remind"
                if level == 1:
                    intervention_msg = (
                        f"Implementation looks substantial ({state['edits']} edits). "
                        f"Consider verifying before claiming completion."
                    )
                else:
                    intervention_msg = (
                        f"You MUST verify before completion — second warning. Invoke:\n"
                        f'  Agent({{subagent_type: "drupal-workflow:drupal-verifier", description: "Verify", prompt: "..."}})\n'
                        f'Or: Skill({{skill: "drupal-workflow:drupal-verify"}})'
                    )

# Log intervention if fired
if should_intervene and intervention_type:
    fired_level = get_escalation_level(intervention_type)
    record_intervention(intervention_type)
    state["intervention_count"] += 1
    state["last_intervention_turn"] = state["turn"]

    # Append to interventions log
    log_entry = {
        "turn": state["turn"],
        "type": intervention_type,
        "level": fired_level,
        "drift_score": drift,
        "drift_components": drift_components,
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
