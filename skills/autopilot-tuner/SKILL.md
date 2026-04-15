---
name: autopilot-tuner
description: |
  Analyze autopilot effectiveness and tune the drupal-workflow plugin based on real session data.
  Use when the autopilot feels too noisy, too quiet, or is being ignored. Also use when you want to
  check if recent changes to the plugin are actually working, review intervention acceptance rates,
  or improve classifier accuracy. Trigger on: "tune autopilot", "autopilot stats", "self-improve",
  "is the autopilot working", "too many warnings", "interventions being ignored", "plugin health",
  or after any conversation about autopilot effectiveness.
metadata:
  status: stable
  drupal-version: "all"
  last-reviewed: 2026-04
---

# Autopilot Tuner

Closes the feedback loop on the drupal-workflow plugin. Reads real session data, identifies what's working and what isn't, and proposes targeted changes to policies, thresholds, classifier keywords, and escalation behavior.

The plugin generates data every session (intervention logs, outcome archives, state snapshots). This skill turns that data into actionable improvements instead of letting it sit unread.

## When to Use

- Autopilot interventions are being ignored (low acceptance rates)
- Interventions feel too aggressive or too passive
- Tasks are being misclassified (e.g., small config fix triggers full planning workflow)
- After deploying plugin changes, to measure before/after impact
- Periodic health check (weekly or after ~10 sessions)
- User says "the autopilot is annoying" or "it's not helping"

## Process

### Step 1: Collect Data

Run the diagnostic script to gather all session data into a single report:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/autopilot-tuner/scripts/diagnose.py" --json
```

This outputs a structured JSON report with:
- **acceptance_rates**: per-intervention-type fire count, acceptance rate, avg escalation level
- **outcome_summary**: how sessions ended (avg drift, % with verification, % with plans)
- **classification_breakdown**: task types seen and their outcome quality
- **threshold_analysis**: at what edit count do agents actually comply?
- **proposals**: specific changes with reasoning and confidence

If the data is sparse (< 5 sessions), say so. Recommendations from small samples are directional, not definitive.

Also run the compare mode if Phase 2 is deployed:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/session-analysis/analyze-replays.py" --compare --json
```

### Step 1.5: Read the Actual Code

The diagnostic script gives you numbers. Numbers alone miss structural issues. Before diagnosing, skim these three files to understand what the data means:

```bash
# The monitor — where interventions fire, what conditions trigger them, what tool types are checked
Read ${CLAUDE_PLUGIN_ROOT}/scripts/autopilot-monitor.sh

# The classifier — keyword priority order, what falls through to default
Read ${CLAUDE_PLUGIN_ROOT}/scripts/task-classifier.sh

# Check for competing hooks that might duplicate or conflict with the monitor
grep -l "skill\|nudge\|workflow" ${CLAUDE_PLUGIN_ROOT}/scripts/*.sh
```

Look for things the data can't tell you:
- **Timing**: Does the intervention fire on Edit/Write only, or on Read/Grep too? An intervention that only fires during edits misses the exploration phase entirely.
- **Competing hooks**: Are there other hooks (like a workflow-nudge.sh) that fire similar messages? Two hooks nagging about the same thing desensitizes agents.
- **Keyword overlaps**: Do classifier keywords create ambiguity? ("add a config" matches implementation's "add" before maintenance's "config")
- **Dead code**: Are there hooks referenced in scripts but removed from hooks.json, or vice versa?

For broad health checks, also scan:
- Plugin cache vs source sync: do files in the cache directory match the marketplace source?
- Documentation accuracy: do README/CLAUDE.md skill counts match what's on disk?

### Step 2: Diagnose

Read the diagnostic output and your code investigation together. Present the highest-impact findings to the user in priority order — focus on what matters most, not an exhaustive dump.

**Five questions to answer:**

1. **Are interventions being followed?** Look at acceptance rates. Below 30% means the intervention is noise — agents have learned to ignore it. Above 70% means it's working well.

2. **Does escalation help?** Compare acceptance at level 1 (hint) vs level 2 (command). If level 2 doesn't improve compliance, the problem isn't volume — it's the message content or the rule itself.

3. **Are tasks classified correctly?** If "maintenance" sessions routinely exceed 10 edits or need delegation, they were probably implementation tasks that got misclassified. If "implementation" sessions finish in 3 edits, they were probably maintenance.

4. **Do plans actually help?** Compare outcomes of sessions with plans vs without. If planned sessions don't end better (lower drift, more verification), then requiring plans is adding friction without value.

5. **Are thresholds calibrated?** If plan_missing fires at edit 3 but agents only comply at edit 8+, the threshold is too eager. Move it closer to where compliance actually happens.

### Step 3: Propose Changes

Number every proposal as `[P1]`, `[P2]`, etc. for easy reference. For each one:

- **What to change**: exact file, exact field, old value → new value
- **Why**: the data that supports this change
- **Risk**: what could go wrong (e.g., "agents might skip planning entirely")
- **Confidence**: high (strong data), medium (directional), low (speculative)

**Types of changes this skill can propose:**

| Category | Files affected | Example |
|----------|---------------|---------|
| Policy thresholds | `scripts/policies/*.json` | Lower `min_skills` from 2 to 1 |
| Classifier keywords | `scripts/task-classifier.sh` | Add "remove" to debugging keywords |
| Escalation behavior | `scripts/autopilot-monitor.sh` | Change edit threshold from 3 to 5 |
| Intervention text | `scripts/autopilot-monitor.sh` | Reword hint to be more specific |
| Phase budgets | `scripts/policies/*.json` | Increase implementing max_turns |
| Structural | `scripts/*.sh`, `hooks/hooks.json` | Remove competing hook, consolidate logic |
| Classifier logic | `scripts/task-classifier.sh` | Add post-classification reclassification heuristic |

**Think laterally, not just parametrically.** Threshold tuning is the obvious lever, but it's not always the right one. Consider:
- Can the classifier be smarter? (e.g., reclassify "implementation" → "maintenance" when the prompt mentions config terms but no entity/module/service terms)
- Can the intervention fire at a different point in the workflow? (e.g., on Read/Grep tools during exploration, not just on Edit/Write during implementation)
- Are there competing hooks that should be consolidated?
- Would a new task type (beyond the existing 5) better fit a common workflow?

The best proposals change the structure, not just the numbers.

### Step 4: Apply with Approval

Present each proposal to the user. For each one:
1. Show the change as a diff preview
2. Explain the reasoning in plain language
3. Wait for approval before applying

Never auto-apply. The user knows their workflow better than the data does.

After applying changes, remind the user:
- Changes take effect on the next session (SessionStart reloads policies)
- Run this skill again after ~5-10 sessions to measure impact
- Use `analyze-replays.py --compare` to see before/after

### Step 5: Log What Changed

After applying, append a summary to the plugin's changelog:

```bash
echo "$(date -Iseconds) | autopilot-tuner | <summary of changes>" >> "${CLAUDE_PLUGIN_ROOT}/CHANGELOG.log"
```

This creates an audit trail so future tuning runs can see what was tried before.

## Reading the Diagnostic Output

The `diagnose.py` script outputs JSON with these sections:

```json
{
  "summary": {
    "sessions_analyzed": 12,
    "date_range": ["2026-04-10", "2026-04-14"],
    "total_interventions": 34,
    "total_outcomes": 10
  },
  "acceptance": {
    "plan_missing": {"fires": 8, "accepted": 3, "rate": 0.375, "avg_level": 1.5},
    ...
  },
  "outcomes": {
    "avg_drift": 0.35,
    "pct_verified": 0.40,
    "pct_planned": 0.60,
    "by_task_type": { "implementation": {...}, "maintenance": {...} }
  },
  "proposals": [
    {
      "id": "P1",
      "category": "threshold",
      "target": "scripts/policies/implementation.json",
      "field": "min_skills",
      "old_value": 2,
      "new_value": 1,
      "reason": "skill_suggest has 0% acceptance across 11 fires — agents consistently ignore this. Reducing to 1 means the first skill invocation clears the requirement.",
      "confidence": "high",
      "risk": "Agents may consult fewer skills, reducing code quality."
    }
  ]
}
```

## What Not to Tune

Some things should stay fixed regardless of data:

- **require_verification on implementation/refactoring** — this is a quality gate, not a suggestion. Even if agents resist, verification catches real bugs.
- **Sensitive file blocking** — security rules don't get relaxed based on convenience metrics.
- **Escalation suppression limit** (MAX_FIRES_PER_TYPE=2) — nagging past 2 fires has no upside. If 2 commands don't work, a 3rd won't either.

## Interpreting Low-Data Situations

With fewer than 5 sessions:
- Acceptance rates are unreliable (one session can swing 30%)
- Outcome correlations are meaningless
- Focus on obvious issues: types that never fire, 0% acceptance, classifier mismatches you can see in the logs
- Say "not enough data for confident recommendations" and suggest running more sessions
