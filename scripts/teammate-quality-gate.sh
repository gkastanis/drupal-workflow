#!/bin/bash

# teammate-quality-gate.sh
# Advisory hook for TeammateIdle and TaskCompleted events.
# Checks if verification output was produced before task completion.
# Always exits 0 (never blocks) - reminder only.
#
# Input: JSON on stdin with fields: task_id, task_subject, task_description,
#        teammate_name, team_name, transcript_path, session_id.

# Read JSON input from stdin.
INPUT_JSON=$(cat)

# Extract fields from stdin JSON.
TASK_SUBJECT=""
TASK_DESCRIPTION=""
TRANSCRIPT_PATH=""
if command -v jq >/dev/null 2>&1; then
    TASK_SUBJECT=$(echo "$INPUT_JSON" | jq -r '.task_subject // ""' 2>/dev/null)
    TASK_DESCRIPTION=$(echo "$INPUT_JSON" | jq -r '.task_description // ""' 2>/dev/null)
    TRANSCRIPT_PATH=$(echo "$INPUT_JSON" | jq -r '.transcript_path // ""' 2>/dev/null)
fi

# Build the text to search for verification patterns.
# Combine task subject + description + last portion of transcript if available.
SEARCH_TEXT="$TASK_SUBJECT $TASK_DESCRIPTION"
if [[ -n "$TRANSCRIPT_PATH" && -f "$TRANSCRIPT_PATH" ]]; then
    TAIL_TEXT=$(tail -50 "$TRANSCRIPT_PATH" 2>/dev/null || true)
    SEARCH_TEXT="$SEARCH_TEXT $TAIL_TEXT"
fi

# Check for verification patterns matching the verification-before-completion skill's output format.
# Looks for: test result keywords, verification report markers, test framework invocations,
# and HTTP status codes in context (not bare numbers that match prose like "200 lines").
has_verification() {
  echo "$SEARCH_TEXT" | grep -qiE "(PASS|FAIL|VERIFIED|NEEDS ATTENTION|Verification Results|drush eval|phpunit|behat|vitest|jest|curl -[sS]|smoke.test|assert|HTTP[/ ][0-9]{3}|status_code)" 2>/dev/null
}

# If verification patterns found, nothing to do
if has_verification; then
  exit 0
fi

# No verification detected - output advisory reminder
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "VERIFICATION REMINDER (advisory)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "No test output detected in recent activity."
echo "Remember: verify before completion (curl smoke test or drush eval)."
echo ""
echo "Quick checks:"
echo "  ddev exec curl -s -o /dev/null -w '%{http_code}' http://localhost/PATH"
echo "  ddev drush eval 'print Drupal::hasService(\"my.service\");'"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

exit 0
