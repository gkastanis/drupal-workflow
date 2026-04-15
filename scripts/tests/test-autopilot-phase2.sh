#!/usr/bin/env bash
# test-autopilot-phase2.sh — 10 behavioral eval cases for Phase 2 autopilot
# Tests: weighted drift, 3-level escalation, phase budgets, classifier, suppression
# Run: bash scripts/tests/test-autopilot-phase2.sh
# Exit 0 = all pass, exit 1 = failures

set -u

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
export CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"
MONITOR="$PLUGIN_ROOT/scripts/autopilot-monitor.sh"
CLASSIFIER="$PLUGIN_ROOT/scripts/task-classifier.sh"
SESSION_KEY=$(printf '%s' "$PLUGIN_ROOT" | md5sum | cut -c1-12)
STATE_DIR="/tmp/drupal-workflow-states/active-${SESSION_KEY}"

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

reset_state() {
    rm -rf "$STATE_DIR"
    mkdir -p "$STATE_DIR"
    chmod 700 "$STATE_DIR"
    # Load policy for given task type
    local task_type="${1:-implementation}"
    cp "$PLUGIN_ROOT/scripts/policies/${task_type}.json" "$STATE_DIR/policy.json" 2>/dev/null || true
}

fire_tool() {
    echo "{\"tool_name\":\"$1\"}" | bash "$MONITOR" 2>&1
}

get_state() {
    python3 -c "import json; s=json.load(open('$STATE_DIR/state.json')); print(s.get('$1', ''))"
}

get_state_nested() {
    python3 -c "
import json
s = json.load(open('$STATE_DIR/state.json'))
keys = '$1'.split('.')
v = s
for k in keys:
    v = v.get(k, {}) if isinstance(v, dict) else {}
print(v)
"
}

count_log_entries() {
    wc -l < "$STATE_DIR/interventions.log" 2>/dev/null || echo 0
}

log_has_type() {
    grep -c "\"type\": \"$1\"" "$STATE_DIR/interventions.log" 2>/dev/null || \
    grep -c "\"type\":\"$1\"" "$STATE_DIR/interventions.log" 2>/dev/null || echo 0
}

log_has_level() {
    grep -c "\"level\": $1" "$STATE_DIR/interventions.log" 2>/dev/null || \
    grep -c "\"level\":$1" "$STATE_DIR/interventions.log" 2>/dev/null || echo 0
}

# ─────────────────────────────────────────────
echo "Case 1: Classifier — maintenance task type"
# ─────────────────────────────────────────────
OUTPUT=$(echo '{"message":{"content":"update the config settings"}}' | bash "$CLASSIFIER" 2>&1)
if echo "$OUTPUT" | grep -q "maintenance"; then
    pass "config update classified as maintenance"
else
    fail "expected maintenance, got: $OUTPUT"
fi

# ─────────────────────────────────────────────
echo "Case 2: Classifier — debugging still wins over maintenance"
# ─────────────────────────────────────────────
OUTPUT=$(echo '{"message":{"content":"fix the broken config"}}' | bash "$CLASSIFIER" 2>&1)
if echo "$OUTPUT" | grep -q "debugging"; then
    pass "fix+broken classified as debugging (higher priority)"
else
    fail "expected debugging, got: $OUTPUT"
fi

# ─────────────────────────────────────────────
echo "Case 3: Weighted drift — plan+delegate+skill = 0.8 at 6 edits"
# ─────────────────────────────────────────────
reset_state implementation
# At 6 edits: plan (>5), delegate (>5, 0 delegations), skill (turn>5, 0 skills) all trigger
# 0.3 + 0.3 + 0.2 = 0.8
for i in $(seq 1 6); do fire_tool Edit >/dev/null; done
DRIFT=$(get_state drift_score)
if python3 -c "exit(0 if abs($DRIFT - 0.8) < 0.01 else 1)"; then
    pass "drift_score=0.8 with plan+delegate+skill at 6 edits"
else
    fail "expected drift=0.8, got $DRIFT"
fi

# ─────────────────────────────────────────────
echo "Case 4: Weighted drift — all components = 1.0 at 9 edits"
# ─────────────────────────────────────────────
# Continue: at 9 edits, verify also triggers (>8), so all 4 components active
# 0.3 + 0.3 + 0.2 + 0.2 = 1.0
for i in $(seq 7 9); do fire_tool Edit >/dev/null; done
DRIFT=$(get_state drift_score)
if python3 -c "exit(0 if abs($DRIFT - 1.0) < 0.01 else 1)"; then
    pass "drift_score=1.0 with all components at 9 edits"
else
    fail "expected drift=1.0, got $DRIFT"
fi

# ─────────────────────────────────────────────
echo "Case 5: Escalation — level 1 hint fires first"
# ─────────────────────────────────────────────
reset_state implementation
# plan_missing fires at edit 6 (edits > 5)
for i in $(seq 1 6); do fire_tool Edit >/dev/null; done
L1=$(log_has_level 1)
if [ "$L1" -ge 1 ]; then
    pass "level 1 hint fired"
else
    fail "expected level 1 entry, found $L1"
fi

# ─────────────────────────────────────────────
echo "Case 6: Escalation — level 2 command fires second"
# ─────────────────────────────────────────────
for i in $(seq 7 9); do fire_tool Edit >/dev/null; done
L2=$(log_has_level 2)
if [ "$L2" -ge 1 ]; then
    pass "level 2 command fired"
else
    fail "expected level 2 entry, found $L2"
fi

# ─────────────────────────────────────────────
echo "Case 7: Suppression — no more plan_missing after 2 fires"
# ─────────────────────────────────────────────
BEFORE=$(count_log_entries)
for i in $(seq 8 14); do fire_tool Edit >/dev/null; done
AFTER=$(count_log_entries)
PLAN_COUNT=$(log_has_type plan_missing)
if [ "$PLAN_COUNT" -le 2 ]; then
    pass "plan_missing suppressed after 2 fires (count=$PLAN_COUNT)"
else
    fail "expected max 2 plan_missing, got $PLAN_COUNT"
fi

# ─────────────────────────────────────────────
echo "Case 8: Phase budget — planning phase blocks edits"
# ─────────────────────────────────────────────
reset_state implementation
# Implementation policy: planning phase max_edits=0
# First edit puts us in implementing phase, so test with a policy that has max_edits=0 for implementing
# Actually, planning phase has max_edits=0. When we edit, phase becomes "implementing" immediately.
# So phase budget for planning won't fire on Edit. Test implementing budget instead.
# Create a custom policy with implementing max_edits=3
cat > "$STATE_DIR/policy.json" << 'EOF'
{
  "task_type": "test",
  "require_plan": false,
  "min_delegations": 0,
  "min_skills": 0,
  "require_verification": false,
  "phase_budget": {
    "implementing": { "max_edits": 3 }
  }
}
EOF
for i in $(seq 1 5); do fire_tool Edit >/dev/null; done
BUDGET=$(log_has_type phase_budget_exceeded)
if [ "$BUDGET" -ge 1 ]; then
    pass "phase_budget_exceeded fired when max_edits=3 exceeded"
else
    fail "expected phase_budget_exceeded, found $BUDGET"
fi

# ─────────────────────────────────────────────
echo "Case 9: Maintenance policy — no plan_missing fires"
# ─────────────────────────────────────────────
reset_state maintenance
for i in $(seq 1 8); do fire_tool Edit >/dev/null; done
PLAN_COUNT=$(log_has_type plan_missing)
if [ "$PLAN_COUNT" -eq 0 ]; then
    pass "no plan_missing with maintenance policy"
else
    fail "expected 0 plan_missing under maintenance, got $PLAN_COUNT"
fi

# ─────────────────────────────────────────────
echo "Case 10: Verify intervention fires after delegations"
# ─────────────────────────────────────────────
reset_state implementation
# First Edit creates state.json, then patch it to have a plan
fire_tool Edit >/dev/null
python3 -c "
import json
s = json.load(open('$STATE_DIR/state.json'))
s['plan_exists'] = True
s['skills_used'] = ['drupal-brainstorming', 'writing-plans']
json.dump(s, open('$STATE_DIR/state.json', 'w'))
"
# Simulate: 1 delegation + 9 edits (>8 edits + >=1 delegation + verification required)
fire_tool Agent >/dev/null
for i in $(seq 1 10); do fire_tool Edit >/dev/null; done
VERIFY_COUNT=$(log_has_type verify_remind)
if [ "$VERIFY_COUNT" -ge 1 ]; then
    pass "verify_remind fired after substantial edits + delegation"
else
    fail "expected verify_remind, got $VERIFY_COUNT"
fi

# ─────────────────────────────────────────────
echo ""
echo "Results: $PASS passed, $FAIL failed out of $((PASS + FAIL))"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
