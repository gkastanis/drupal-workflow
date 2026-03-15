#!/bin/bash

# teammate-quality-gate.sh
# Advisory hook for TeammateIdle and TaskCompleted events.
# Checks if verification output was produced before task completion.
# Always exits 0 (never blocks) - reminder only.

# Tool output from the triggering event
TOOL_OUTPUT="${CLAUDE_TOOL_OUTPUT:-}"

# Check for verification patterns matching the verification-before-completion skill's output format.
# Looks for: test result keywords, verification report markers, test framework invocations,
# and HTTP status codes in context (not bare numbers that match prose like "200 lines").
has_verification() {
  echo "$TOOL_OUTPUT" | grep -qiE "(PASS|FAIL|VERIFIED|NEEDS ATTENTION|Verification Results|drush eval|phpunit|behat|vitest|jest|curl -[sS]|smoke.test|assert|HTTP[/ ][0-9]{3}|status_code)" 2>/dev/null
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
