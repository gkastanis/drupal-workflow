#!/bin/bash

# teammate-quality-gate.sh
# Advisory hook for TeammateIdle and TaskCompleted events.
# Checks if verification output was produced before task completion.
# Always exits 0 (never blocks) - reminder only.

# Tool output from the triggering event
TOOL_OUTPUT="${CLAUDE_TOOL_OUTPUT:-}"

# Check for common verification patterns in recent output
has_verification() {
  echo "$TOOL_OUTPUT" | grep -qiE "(PASS|FAIL|OK|ERROR|200|301|302|404|500|drush eval|phpunit|behat|vitest|jest|curl|smoke.test|assert)" 2>/dev/null
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
