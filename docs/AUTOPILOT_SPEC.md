# Magic Loop Autopilot -- Build Specification

Live workflow policy engine for drupal-workflow. Monitors session behavior in real time, detects drift from proven patterns, and intervenes with targeted nudges to reproduce the delegation pattern observed in magic-era sessions (Mar 29-31, avg score 58/100 vs. 17/100 in later sessions).

## 1. Architecture Overview

```
                          hooks/hooks.json
                              |
    SessionStart -----> [task-classifier.sh] ----> policy.json (in /tmp)
                              |
                              v
    PostToolUse  -----> [autopilot-monitor.sh] --> state-vector.json (in /tmp)
      (every tool)           |
                             |--- drift > threshold? ---> [intervention-select.sh]
                             |                                    |
                             |                                    v
                             |                            emit advisory text
                             |
    TaskCompleted ----> [teammate-quality-gate.sh] (existing, unchanged)
                              |
    Session ends -----> [session-score.sh] ---------> replay log (per-session JSON)
                              |
                              v
                     pattern-score.py + replay-eval.py (existing eval toolchain)
```

**Integration points:**
- `hooks/hooks.json` -- add 1 new SessionStart hook (classifier), replace workflow-nudge.sh with autopilot-monitor.sh
- `scripts/workflow-reset.sh` -- expand to initialize state vector + policy
- `scripts/workflow-nudge.sh` -- superseded by autopilot-monitor.sh (kept as fallback)
- `eval/session-replay/pattern-score.py` -- unchanged, consumes replay logs
- `eval/compare.py` -- Phase 2 provider routing uses its A/B framework

## 2. Session Policy Model

### Task Classification

The classifier examines the user's first substantive prompt (skipping injected system content) and assigns a task type:

```bash
# scripts/task-classifier.sh
# Input: first user message via $CLAUDE_TOOL_INPUT or stdin
# Output: JSON policy written to $STATE_DIR/policy.json

TASK_TYPES:
  implementation  -- "create", "add", "build", "implement", "module", "entity", "service"
  investigation   -- "why", "how does", "trace", "find", "what", "explain", "where"
  refactoring     -- "refactor", "rename", "move", "clean up", "reorganize", "extract"
  documentation   -- "document", "README", "spec", "write up", "describe"
  debugging       -- "fix", "broken", "error", "failing", "bug", "not working", "crash"
```

Classification is keyword-based with priority ordering (debugging > implementation > investigation > refactoring > documentation). If no match, defaults to `implementation`.

### Policy Templates

Each task type maps to an expected workflow sequence. Stored as static JSON in `scripts/policies/`:

```json
// scripts/policies/implementation.json
{
  "task_type": "implementation",
  "expected_phases": ["planning", "implementing", "verifying"],
  "min_skills": 2,
  "min_delegations": 1,
  "require_plan": true,
  "require_verification": true,
  "recommended_agents": ["drupal-builder", "drupal-verifier"],
  "recommended_skills": ["discover", "writing-plans", "drupal-rules"],
  "phase_budget": {
    "planning": { "max_edits": 0, "max_turns": 5 },
    "implementing": { "max_turns": 30 },
    "verifying": { "min_checks": 1 }
  },
  "provider_hints": {
    "planning": "opus",
    "implementing": "opus",
    "verifying": "sonnet"
  }
}
```

```json
// scripts/policies/investigation.json
{
  "task_type": "investigation",
  "expected_phases": ["exploring"],
  "min_skills": 1,
  "min_delegations": 0,
  "require_plan": false,
  "require_verification": false,
  "recommended_skills": ["discover", "semantic-docs", "structural-index"],
  "phase_budget": {},
  "provider_hints": {}
}
```

```json
// scripts/policies/debugging.json
{
  "task_type": "debugging",
  "expected_phases": ["exploring", "implementing", "verifying"],
  "min_skills": 1,
  "min_delegations": 1,
  "require_plan": false,
  "require_verification": true,
  "recommended_agents": ["drupal-verifier"],
  "recommended_skills": ["drupal-testing", "discover"],
  "phase_budget": {
    "verifying": { "min_checks": 2 }
  },
  "provider_hints": {}
}
```

Refactoring and documentation follow similar structures with appropriate constraints.

### Policy Storage

```
/tmp/drupal-workflow-session-${CLAUDE_SESSION_ID}/
  policy.json          # Task type + expected workflow (written once at session start)
  state.json           # Live state vector (updated every PostToolUse)
  interventions.log    # Newline-delimited JSON of all interventions emitted
```

Directory created by workflow-reset.sh at SessionStart.

## 3. Live State Vector

Updated by `autopilot-monitor.sh` on every PostToolUse event.

```json
{
  "turn": 14,
  "phase": "implementing",
  "edits": 8,
  "reads": 22,
  "delegations": 2,
  "skills_used": ["discover", "writing-plans"],
  "agents_dispatched": ["drupal-builder", "drupal-builder"],
  "plan_exists": true,
  "verification_done": false,
  "tasks_created": 3,
  "last_intervention_turn": 7,
  "intervention_count": 1,
  "drift_score": 0.3,
  "policy_task_type": "implementation"
}
```

**Field definitions:**

| Field | Source | Update trigger |
|-------|--------|----------------|
| `turn` | Increment on each user message (detect via tool_name context) | Every hook |
| `phase` | Inferred from recent tool mix (see Phase Detection below) | Every hook |
| `edits` | Count of Edit/Write tool calls | Edit, Write |
| `reads` | Count of Read/Grep/Glob tool calls | Read, Grep, Glob |
| `delegations` | Count of Agent tool calls | Agent |
| `skills_used` | Array of unique Skill names | Skill |
| `agents_dispatched` | Array of Agent names (with duplicates) | Agent |
| `plan_exists` | True if writing-plans skill was invoked or TaskCreate count > 2 | Skill, TaskCreate |
| `verification_done` | True if drupal-verifier dispatched or drupal-testing skill used | Agent, Skill |
| `tasks_created` | Count of TaskCreate calls | TaskCreate |
| `last_intervention_turn` | Turn number of last intervention | Intervention |
| `intervention_count` | Total interventions this session | Intervention |
| `drift_score` | 0.0-1.0 composite (see Drift Calculation) | Every hook |
| `policy_task_type` | Cached from policy.json | Session start |

### Phase Detection

Phase is inferred from the tool call distribution in the last N=5 tool calls:

```
if last_5_tools are mostly Read/Grep/Glob/Skill -> "exploring"
if plan_exists == false AND edits == 0           -> "planning"
if edits > 0 AND verification_done == false      -> "implementing"
if verification_done == true                     -> "verifying"
```

### Drift Calculation

Drift is a 0.0-1.0 score comparing current state against policy expectations:

```python
drift = 0.0
policy = load_policy()

# Missing plan when required (weight: 0.3)
if policy.require_plan and not state.plan_exists and state.edits > 3:
    drift += 0.3

# Edit-heavy without delegation (weight: 0.3)
if policy.min_delegations > 0:
    expected_ratio = 0.52  # magic-era benchmark
    actual_ratio = state.delegations / max(state.turn, 1)
    if actual_ratio < expected_ratio * 0.3:
        drift += 0.3 * (1 - actual_ratio / (expected_ratio * 0.3))

# No skills consulted (weight: 0.2)
if len(state.skills_used) < policy.min_skills and state.turn > 5:
    drift += 0.2

# No verification in late session (weight: 0.2)
if policy.require_verification and not state.verification_done and state.edits > 8:
    drift += 0.2

# Clamp to [0, 1]
drift = min(1.0, drift)
```

## 4. Intervention Engine

### Trigger Conditions

Interventions fire when ALL of:
1. `drift_score >= 0.4` (moderate drift) OR a phase transition is detected
2. At least 3 turns since last intervention (`turn - last_intervention_turn >= 3`)
3. Total intervention count < 5 per session
4. Current tool is Edit or Write (don't interrupt reads)

### Intervention Types

| ID | Type | Trigger condition | Message template |
|----|------|-------------------|------------------|
| `plan_missing` | Planning checkpoint | edits > 3, plan_exists == false, policy.require_plan | "You've made {edits} edits without a plan. Consider: use writing-plans skill or /implement to structure the approach." |
| `delegate_suggest` | Agent recommendation | edits > 5, delegations < 1 | "Direct editing without delegation. Consider: @drupal-builder for implementation, @drupal-verifier after changes." |
| `skill_suggest` | Skill suggestion | skills_used is empty, turn > 5 | "No skills consulted yet. Consider: /discover for codebase navigation, /drupal-blast-radius before multi-file changes." |
| `verify_remind` | Verification request | edits > 8, verification_done == false, policy.require_verification | "Implementation looks substantial ({edits} edits). Dispatch @drupal-verifier or run /drupal-test before marking complete." |
| `provider_switch` | Provider routing | Phase 2 only -- see section 5 | "Current subtask ({subtask_type}) may benefit from {suggested_model}." |

### Intervention Selection Logic

Priority order: `plan_missing` > `delegate_suggest` > `skill_suggest` > `verify_remind`. First matching condition wins. Each check uses the specific trigger condition from the table above.

### Annoyance Prevention

1. **Cooldown**: Minimum 3 turns between any two interventions
2. **Session cap**: Maximum 5 interventions per session
3. **Escalation levels**: First occurrence is a one-line hint. Second occurrence (same type) adds a concrete command. Third occurrence is suppressed (user has chosen to ignore it).
4. **Edit-only trigger**: Interventions only fire on Edit/Write hooks, never on Read/Grep (don't interrupt exploration)
5. **Override**: Set `DRUPAL_WORKFLOW_AUTOPILOT=off` env var to disable all interventions

Intervention log format: NDJSON appended to `interventions.log` with fields `{turn, type, drift_score, phase, escalation, message, timestamp}`.

## 5. Provider Routing (Phase 2)

### Subtask-to-Provider Mapping

Built from compare.py A/B results. Initial routing table based on existing eval data:

```json
// scripts/policies/provider-routing.json
{
  "routing_table": {
    "planning": {
      "preferred": "opus",
      "fallback": "sonnet",
      "reason": "Planning requires deep reasoning and multi-step strategy"
    },
    "implementation": {
      "preferred": "opus",
      "fallback": "sonnet",
      "reason": "Implementation needs accurate code generation"
    },
    "verification": {
      "preferred": "sonnet",
      "fallback": "haiku",
      "reason": "Verification is pattern-matching; cheaper model sufficient"
    },
    "research": {
      "preferred": "sonnet",
      "fallback": "haiku",
      "reason": "Reading docs and summarizing; speed over depth"
    },
    "documentation": {
      "preferred": "sonnet",
      "fallback": "sonnet",
      "reason": "Structured writing; mid-tier sufficient"
    }
  },
  "version": "0.1.0",
  "last_updated_from_evals": null
}
```

### Building the Routing Table from A/B Data

Add `--routing-export` flag to `eval/compare.py`. This groups eval cases by their `source.patterns` field (from replay-eval.py), computes per-pattern-per-model pass_rate and avg_cost, then picks best pass_rate as preferred and next-best as fallback.

```bash
python3 eval/compare.py --skill workflow-patterns --no-baseline \
    --models sonnet opus haiku --runs 5 --routing-export
```

### Fallback Behavior

If preferred provider is unavailable (API error, timeout > 30s):
1. Use fallback from routing table
2. If fallback also fails, use session's default model
3. Log the fallback event to interventions.log with type `provider_fallback`

## 6. Post-Session Replay Loop

### On Session End

`scripts/session-score.sh` runs manually or via cron. It reads `state.json` and `policy.json` from the session dir, computes a final magic score (using pattern-score.py's algorithm adapted for state vectors), determines intervention acceptance from the log (accepted = relevant tool call within 2 turns of intervention), and writes `replay.json`.

### Replay Feedback

`eval/session-replay/analyze-replays.py` (new, Phase 2) aggregates replay.json files across 20+ sessions. Outputs: intervention trigger frequency, acceptance rates per type, task types scoring below policy expectations, and suggested policy adjustments.

### Regression Testing

Use existing `replay-eval.py` to verify policy changes don't break known-good patterns:

```bash
# Extract magic-era cases
python3 eval/session-replay/extract-prompts.py sessions/ \
    --date-range 2026-03-29:2026-03-31 --output magic-cases.json

# Generate behavioral evals
python3 eval/session-replay/replay-eval.py magic-cases.json \
    --output eval/behavioral/workflow-patterns/evals.json

# Run evals against current plugin (with autopilot active)
python3 eval/compare.py --skill workflow-patterns --no-baseline --runs 3
```

## 7. Implementation Plan

### Phase 1: State Vector + Task Classifier + Basic Interventions (2 weeks)

**Goal**: Replace workflow-nudge.sh with a state-aware monitor that classifies tasks and tracks session behavior.

| Step | Files | Description |
|------|-------|-------------|
| 1 | `scripts/policies/` (new dir) | Create 5 policy template JSON files (implementation, investigation, refactoring, documentation, debugging) |
| 2 | `scripts/task-classifier.sh` (new) | Keyword-based classifier, writes policy.json to session dir |
| 3 | `scripts/workflow-reset.sh` (modify) | Create session dir, initialize state.json with zero values, invoke task-classifier on first user prompt |
| 4 | `scripts/autopilot-monitor.sh` (new) | PostToolUse hook: update state vector, compute drift, select intervention, emit advisory |
| 5 | `hooks/hooks.json` (modify) | Add SessionStart hook for classifier, replace workflow-nudge.sh matcher with autopilot-monitor.sh |
| 6 | `scripts/session-score.sh` (new) | Post-session scoring from state vector |
| 7 | Tests | Behavioral evals: 5 prompts (one per task type), verify correct classification and at least one intervention fires when drift is simulated |

**hooks.json changes**: Add `task-classifier.sh` as SessionStart hook (after workflow-reset). Replace `workflow-nudge.sh` PostToolUse entry with `autopilot-monitor.sh` (same matcher `.*`, same timeout 3000ms).

**Verification**: Run pattern-score.py on 10 test sessions, confirm average score increases from 17 to 30+.

### Phase 2: Policy Model + Drift Detection + Context-Specific Interventions (2 weeks)

**Goal**: Interventions become context-aware. Drift detection uses the full composite formula. Escalation levels work.

| Step | Files | Description |
|------|-------|-------------|
| 1 | `scripts/autopilot-monitor.sh` (modify) | Full drift calculation with weighted components, phase detection |
| 2 | `scripts/policies/*.json` (modify) | Add phase_budget constraints, expected_min_score |
| 3 | `scripts/lib/intervention-select.sh` (new) | Intervention selection with escalation levels, cooldown, per-type tracking |
| 4 | `scripts/lib/drift-calc.sh` (new) | Drift formula extracted for testability |
| 5 | `eval/session-replay/analyze-replays.py` (new) | Aggregate replay logs, compute acceptance rates, suggest policy tweaks |
| 6 | Tests | Behavioral evals: 10 prompts testing drift scenarios (edit-without-plan, no-verification, no-skills) |

**Verification**: Run on 20 real sessions, confirm intervention acceptance rate > 50%.

### Phase 3: Provider Routing + Replay Feedback Loop (2 weeks)

**Goal**: Autopilot suggests model switches. Replay loop feeds back into policies.

| Step | Files | Description |
|------|-------|-------------|
| 1 | `scripts/policies/provider-routing.json` (new) | Initial routing table from manual eval analysis |
| 2 | `eval/compare.py` (modify) | Add `--routing-export` flag for per-pattern-per-model aggregation |
| 3 | `scripts/autopilot-monitor.sh` (modify) | Add provider_switch intervention type using routing table |
| 4 | `scripts/lib/replay-feedback.sh` (new) | Cron-friendly script: aggregate replays, detect underperforming policies, emit adjustment suggestions |
| 5 | Docs | Update README.md with autopilot section, env var reference |
| 6 | Tests | A/B eval: run compare.py with autopilot-enabled vs autopilot-disabled across 5 workflow-pattern evals |

**Verification**: Average magic score across sessions reaches 50+. Cost per question <= $3.00.

## 8. Data Model

All files use `schema_version: 1` for forward compatibility. All JSON, all in `/tmp/drupal-workflow-session-${CLAUDE_SESSION_ID}/`.

| File | Schema | Notes |
|------|--------|-------|
| `state.json` | See section 3 (Live State Vector) | Updated every PostToolUse |
| `policy.json` | See section 2 (Policy Templates) + `classified_from` (string) + `expected_min_score` (int) | Written once at session start |
| `interventions.log` | NDJSON: `{turn, type, drift_score, phase, escalation, message, timestamp}` | Append-only |
| `replay.json` | `{session_id, task_type, final_score, final_state, policy_applied, interventions: [{turn, type, accepted}], drift_history: [{turn, drift}], timestamp}` | Written at session end |

Provider routing table lives in `scripts/policies/provider-routing.json` (see section 5).

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Intervention fatigue** -- user ignores or is annoyed by nudges | HIGH | Kills adoption | Session cap (5 max), cooldown (3 turns), escalation suppression (same type fires max 2x), `DRUPAL_WORKFLOW_AUTOPILOT=off` env var |
| **False drift detection** -- classifier picks wrong task type, drift fires inappropriately | MEDIUM | Trust erosion | Conservative thresholds (0.4 drift minimum), investigation tasks have no plan/delegation requirements, classifier can be overridden by user saying "this is a debugging session" |
| **Wrong provider routing** -- model suggestion is worse for the actual subtask | MEDIUM | Wasted cost, slower session | Phase 2 only, routing table is advisory (user decides), fallback chain, table is rebuilt from eval data not assumptions |
| **State file corruption** -- concurrent writes from rapid tool calls | LOW | Missed counters | Single-writer design (bash is sequential per hook), atomic write via temp file + mv |
| **Performance overhead** -- hook adds latency to every tool call | LOW | Slower interaction | Budget: 50ms max for autopilot-monitor.sh (state file read + increment + write, no network calls), timeout 3000ms in hooks.json same as current workflow-nudge.sh |
| **Stale policies** -- workflow patterns change but policies don't update | MEDIUM | Drift detection becomes irrelevant | Replay feedback loop (Phase 3) detects underperforming policies, policy version tracked in schema_version |

### Escape Hatches

1. **Env var disable**: `export DRUPAL_WORKFLOW_AUTOPILOT=off` -- autopilot-monitor.sh exits immediately
2. **Per-session disable**: User says "stop suggesting" -- detected by keyword match, sets intervention cap to 0
3. **Fallback mode**: If autopilot-monitor.sh fails (non-zero exit), falls through to original workflow-nudge.sh behavior (kept as dead code)
4. **Policy override**: User can place a custom `policy.json` in the session dir before classification runs, classifier skips if file exists

## 10. Success Metrics

### Primary

| Metric | Baseline | Phase 1 Target | Phase 3 Target |
|--------|----------|----------------|----------------|
| Average magic score | 17/100 | 30/100 | 50/100 |
| Sessions scoring "Good" (60+) or "Magic" (80+) | 5% | 15% | 40% |

### Secondary

| Metric | Baseline | Target |
|--------|----------|--------|
| Avg cost per question | $2.55 (magic era) / unknown (current) | <= $3.00 |
| Delegation rate (agents/turn) | 0.08 (post-magic) | >= 0.30 |
| Skills consulted per session | 0.5 (post-magic) | >= 2.0 |
| Plan-before-implement rate | ~10% (post-magic) | >= 60% |

### Guardrails

| Guardrail | Threshold | Action if breached |
|-----------|-----------|-------------------|
| Intervention acceptance rate | >= 60% | If < 60% for 20 sessions, review intervention text and thresholds |
| Intervention-to-override ratio | <= 20% user overrides | If > 20%, reduce intervention frequency (raise cooldown to 5 turns) |
| Hook latency p95 | <= 100ms | If exceeded, profile autopilot-monitor.sh, reduce state file reads |
| Session abandonment after intervention | <= 10% | If sessions end within 2 turns of an intervention, suppress that intervention type for analysis |

### Measurement

All metrics are computed from:
- `pattern-score.py` (existing) -- runs on session JSONL, produces magic scores
- `replay.json` (new) -- per-session intervention acceptance data
- `analyze-replays.py` (new, Phase 2) -- aggregates across sessions

Weekly cadence: run pattern-score.py on all sessions from the past week, compare to previous week. Trend line in `--trend` output tells the story.
