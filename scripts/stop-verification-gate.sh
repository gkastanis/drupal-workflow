#!/bin/bash
# stop-verification-gate.sh
# Stop hook: advisory nudge when Drupal code was edited without verification.
# Checks last_assistant_message for edit mentions + transcript tail for tool output.
# Advisory only — exits 0 always.

INPUT_JSON=$(cat)

LAST_MESSAGE=""
STOP_HOOK_ACTIVE=""
TRANSCRIPT_PATH=""
if command -v jq >/dev/null 2>&1; then
    LAST_MESSAGE=$(echo "$INPUT_JSON" | jq -r '.last_assistant_message // ""' 2>/dev/null)
    STOP_HOOK_ACTIVE=$(echo "$INPUT_JSON" | jq -r '.stop_hook_active // ""' 2>/dev/null)
    TRANSCRIPT_PATH=$(echo "$INPUT_JSON" | jq -r '.transcript_path // ""' 2>/dev/null)
fi

# Prevent infinite loops.
if [[ "$STOP_HOOK_ACTIVE" == "true" ]]; then
    exit 0
fi

# No message to check.
if [[ -z "$LAST_MESSAGE" ]]; then
    exit 0
fi

# Check if this response mentions editing Drupal/PHP files.
if ! echo "$LAST_MESSAGE" | grep -qiE "\.(php|module|install|theme|inc|services\.yml|routing\.yml|permissions\.yml)"; then
    exit 0
fi

# Build verification search text: assistant message + last chunk of transcript
# (transcript contains actual Bash tool output like drush/curl results).
SEARCH_TEXT="$LAST_MESSAGE"
if [[ -n "$TRANSCRIPT_PATH" && -f "$TRANSCRIPT_PATH" ]]; then
    SEARCH_TEXT="$SEARCH_TEXT $(tail -c 10000 "$TRANSCRIPT_PATH" 2>/dev/null)"
fi

# Check for verification evidence in both message and recent tool output.
if echo "$SEARCH_TEXT" | grep -qiE "(drush |phpunit|behat|curl -[sS]|smoke.test|HTTP[/ ][0-9]{3}|PASS|FAIL|VERIFIED|status_code|test.*passed|drupal-test)"; then
    exit 0
fi

# Drupal code edited, no verification in message or recent tool output.
cat <<'JSON'
{
  "additionalContext": "Unverified Drupal code change. Run /drupal-test or a quick drush eval."
}
JSON
