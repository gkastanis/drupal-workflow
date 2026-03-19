#!/bin/bash
# plan-mode-inject.sh
# PreToolUse hook for EnterPlanMode: inject todo list and agent assignment instructions.
# Returns JSON with additionalContext so Claude sees the instructions right before planning.

cat <<'JSON'
{
  "additionalContext": "PLAN MODE ACTIVATED — Follow this structure:\n\n1. Create a todo list using TaskCreate for each discrete step\n2. Assign each task to the appropriate agent:\n   - @drupal-builder: implementation tasks (create/modify code)\n   - @drupal-reviewer: code review tasks\n   - @drupal-verifier: testing and verification tasks\n   - @semantic-architect: documentation and tech spec tasks\n3. Each task must include: exact file paths, expected outcome, verification command\n4. Order tasks by dependency (what must complete before what)\n5. Start executing tasks in dependency order, using parallel agents for independent work\n\nRefer to the writing-plans skill for delegation format."
}
JSON
