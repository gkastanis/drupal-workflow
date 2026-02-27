---
description: Run Drupal test script to verify implementation
argument-hint: <test-type> <target> [--verbose]
allowed-tools: Bash
---

<!--
Usage examples:
  /drupal-test service my_module.my_service
  /drupal-test entity node:article
  /drupal-test hook node_presave my_module
  /drupal-test access "administer nodes"
  /drupal-test service my_module.my_service --verbose
-->

Run a Drupal verification test using `ddev drush eval` with JSON output.

**Test type:** $1
**Target:** $2
**Options:** $3

## Test Type Instructions

Based on the test type, generate and execute the appropriate test:

### For `service` tests:
Test that a Drupal service exists and can be instantiated. Target is the service ID (e.g., `my_module.my_service`).

### For `entity` tests:
Test entity type/bundle operations. Target format is `entity_type:bundle` (e.g., `node:article`).

### For `hook` tests:
Verify hook implementations. Target is the hook name, optionally followed by a specific module to check (e.g., `node_presave my_module`).

### For `access` tests:
Test permissions and access control. Target is the permission name or route name.

## Execution

1. Load the `drupal-testing` skill for test script templates
2. Generate the appropriate PHP test code based on type and target
3. Execute using: `ddev drush eval 'PHP_CODE' 2>/dev/null`
4. Parse the JSON output
5. Report results clearly

If `--verbose` is specified, include timing and execution trace in output.

## Output Format

Present results as:
- **Status**: PASS or FAIL with emoji indicator
- **Target**: What was tested
- **Checks**: Individual check results
- **Errors**: Any error details if failed
- **Suggestions**: Remediation steps if failed
