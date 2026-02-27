#!/bin/sh
# block-sensitive-files.sh
# PreToolUse Hook - Block access to sensitive Drupal files
# Exit code 2 = BLOCK execution, Exit code 0 = ALLOW execution

# Set up logging
LOG_FILE="/tmp/blocked-sensitive-files.log"
timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

log() {
    echo "[$(timestamp)] $1" >> "$LOG_FILE"
}

# Configuration file location
CONFIG_FILE=".claude/sensitive-files.json"

# Load custom patterns from config file if it exists
load_custom_patterns() {
    if [ ! -f "$CONFIG_FILE" ]; then
        log "Config file not found: $CONFIG_FILE (using defaults)"
        return
    fi

    # Extract custom patterns from JSON (if jq available)
    if command -v jq >/dev/null 2>&1; then
        CUSTOM_PATTERNS=$(jq -r '.patterns.custom_patterns[]? | select(startswith("#") | not)' "$CONFIG_FILE" 2>/dev/null)
        ALLOWLIST=$(jq -r '.allowlist[]? | select(startswith("#") | not)' "$CONFIG_FILE" 2>/dev/null)
        log "Loaded custom patterns from $CONFIG_FILE"
    fi
}

# Read JSON input from stdin
INPUT_JSON=$(cat)

# Parse JSON using robust extraction
TOOL_NAME=""
FILE_PATH=""
PATTERN=""
PATH_PARAM=""

# Try direct jq extraction first
if command -v jq >/dev/null 2>&1; then
    TOOL_NAME=$(echo "$INPUT_JSON" | jq -r '.tool_name' 2>/dev/null)
    FILE_PATH=$(echo "$INPUT_JSON" | jq -r '.tool_input.file_path // ""' 2>/dev/null)
    PATTERN=$(echo "$INPUT_JSON" | jq -r '.tool_input.pattern // ""' 2>/dev/null)
    PATH_PARAM=$(echo "$INPUT_JSON" | jq -r '.tool_input.path // ""' 2>/dev/null)
fi

# Fallback to grep/sed if jq fails or returns null
if [ -z "$TOOL_NAME" ] || [ "$TOOL_NAME" = "null" ]; then
    TOOL_NAME=$(echo "$INPUT_JSON" | grep -o '"tool_name":"[^"]*"' | cut -d'"' -f4)
fi

if [ -z "$FILE_PATH" ] || [ "$FILE_PATH" = "null" ]; then
    FILE_PATH=$(echo "$INPUT_JSON" | grep -o '"file_path":"[^"]*"' | sed 's/.*"file_path":"\([^"]*\)".*/\1/')
fi

if [ -z "$PATH_PARAM" ] || [ "$PATH_PARAM" = "null" ]; then
    PATH_PARAM=$(echo "$INPUT_JSON" | grep -o '"path":"[^"]*"' | sed 's/.*"path":"\([^"]*\)".*/\1/')
fi

# Only check Read and Grep tools
if [ "$TOOL_NAME" != "Read" ] && [ "$TOOL_NAME" != "Grep" ]; then
    log "Skipping non-Read/Grep tool: $TOOL_NAME"
    exit 0
fi

# Determine which path to check
CHECK_PATH="$FILE_PATH"
if [ -z "$CHECK_PATH" ] || [ "$CHECK_PATH" = "null" ]; then
    CHECK_PATH="$PATH_PARAM"
fi

# If still no path, allow (might be searching by pattern only)
if [ -z "$CHECK_PATH" ] || [ "$CHECK_PATH" = "null" ]; then
    log "No file path specified, allowing operation"
    exit 0
fi

log "Checking $TOOL_NAME access to: $CHECK_PATH"

# Load custom patterns
load_custom_patterns

# Check if path is in allowlist
check_allowlist() {
    local path="$1"

    if [ -n "$ALLOWLIST" ]; then
        for allowed_path in $ALLOWLIST; do
            if echo "$path" | grep -qE "$allowed_path"; then
                log "Path is in allowlist, allowing access: $path"
                exit 0
            fi
        done
    fi
}

# Check custom patterns
check_custom_patterns() {
    local path="$1"

    if [ -n "$CUSTOM_PATTERNS" ]; then
        for pattern in $CUSTOM_PATTERNS; do
            if echo "$path" | grep -qE "$pattern"; then
                block_access "matches custom sensitive pattern: $pattern" "$path"
            fi
        done
    fi
}

# Function to block access with reason
block_access() {
    local reason="$1"
    local path="$2"

    echo "BLOCKED: $reason" >&2
    echo "Attempted to access: $path" >&2
    echo "Sensitive Drupal configuration files are protected for security" >&2
    echo "" >&2
    echo "If you need to review configuration:" >&2
    echo "   - Ask the user to provide specific config values" >&2
    echo "   - Use drush config:get for specific settings" >&2
    echo "   - Request manual review of the file" >&2
    echo "   - Or add the file to .claude/sensitive-files.json allowlist" >&2

    log "BLOCKED: $reason - Path: $path"
    exit 2  # Claude Code convention for blocking
}

# Check for .env files (various formats)
check_env_files() {
    local path="$1"

    # .env and variants (.env.local, .env.production, etc.)
    if echo "$path" | grep -qiE "\.env(\.[a-z]+)?$|^\.env$"; then
        block_access "environment file (.env) contains sensitive credentials" "$path"
    fi

    # .env in any directory
    if echo "$path" | grep -qE "/\.env(\.[a-z]+)?$"; then
        block_access "environment file contains sensitive credentials" "$path"
    fi
}

# Check for Drupal settings files
check_drupal_settings() {
    local path="$1"

    # Main settings.php
    if echo "$path" | grep -qE "settings\.php$"; then
        block_access "Drupal settings.php contains database credentials and secrets" "$path"
    fi

    # Pattern: *.settings.php (e.g., local.settings.php, dev.settings.php)
    if echo "$path" | grep -qE "[^/]*\.settings\.php$"; then
        block_access "Drupal environment settings file contains sensitive configuration" "$path"
    fi

    # Pattern: settings.*.php (e.g., settings.local.php, settings.prod.php)
    if echo "$path" | grep -qE "settings\.[^/]*\.php$"; then
        block_access "Drupal environment settings file contains sensitive configuration" "$path"
    fi
}

# Check for other sensitive Drupal files
check_other_sensitive_files() {
    local path="$1"

    # services.yml with database connection details
    if echo "$path" | grep -qE "services\.yml$"; then
        # Allow sites/default/services.yml but not development.services.yml with DB credentials
        if echo "$path" | grep -qE "(local|dev|development)\.services\.yml$"; then
            block_access "development services.yml may contain sensitive configuration" "$path"
        fi
    fi

    # Private key files
    if echo "$path" | grep -qE "\.(key|pem|crt|p12|pfx)$"; then
        block_access "private key or certificate file" "$path"
    fi

    # SSH keys
    if echo "$path" | grep -qE "id_rsa|id_ed25519|authorized_keys|known_hosts"; then
        block_access "SSH key or configuration file" "$path"
    fi

    # Database dumps (might contain sensitive data)
    if echo "$path" | grep -qE "\.(sql|dump|backup)$"; then
        log "WARNING: Access to database dump file: $path"
        # Don't block, just log - user might need to analyze structure
    fi

    # Backup files with credentials
    if echo "$path" | grep -qE "backup.*settings|settings.*backup"; then
        block_access "backup of settings file may contain credentials" "$path"
    fi
}

# Check for credential patterns in the path itself
check_credential_patterns() {
    local path="$1"

    # Files with "secret", "password", "credential" in name
    if echo "$path" | grep -qiE "(secret|password|credential|token|apikey)"; then
        log "WARNING: Accessing file with sensitive keyword in name: $path"
        # Don't block automatically, but log for review
    fi
}

# Run all security checks (order matters - allowlist first!)
check_allowlist "$CHECK_PATH"
check_env_files "$CHECK_PATH"
check_drupal_settings "$CHECK_PATH"
check_other_sensitive_files "$CHECK_PATH"
check_custom_patterns "$CHECK_PATH"
check_credential_patterns "$CHECK_PATH"

log "Access allowed to: $CHECK_PATH"
exit 0
