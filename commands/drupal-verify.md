---
description: "Verify Drupal implementation using smoke tests and drush checks"
argument-hint: "<what-to-verify> [--verbose]"
---
# /drupal-verify - Drupal Implementation Verification

## Purpose

Run practical verification tests against the current DDEV Drupal environment to confirm implementations actually work. Uses curl smoke tests and drush eval as primary verification methods.

## Input

Read verification target from `$ARGUMENTS`. Examples:
- `/drupal-verify my_module` - Verify module is enabled and functional
- `/drupal-verify service my_module.my_service` - Verify a specific service
- `/drupal-verify route my_module.page` - Verify a route is accessible
- `/drupal-verify config my_module.settings` - Verify configuration
- `/drupal-verify page /admin/custom-page` - Smoke test a page
- `/drupal-verify --verbose` - Run all recent change verification with details

## Protocol

### Step 1: Load Testing Skill

Read the `drupal-testing` skill for test patterns.

### Step 2: Analyze What to Verify

Based on `$ARGUMENTS`, determine which tests to run:

| Argument Pattern | Tests to Run |
|---|---|
| Module name | Module enabled + services + routes |
| `service <id>` | Service exists via drush eval |
| `route <name>` | Route exists + curl smoke test |
| `config <name>` | Config value via drush eval |
| `page <path>` | Curl smoke test with auth |
| `field <entity> <bundle> <field>` | Field definition check |
| No arguments | Analyze recent git changes, verify all |

### Step 3: Run Tests

Execute appropriate verification commands using DDEV:

1. **Check DDEV is running**: `ddev status`
2. **Run each test**: Use patterns from drupal-testing skill
3. **Capture output**: Store results for reporting

### Step 4: Report Results

Output structured results:

```
## Drupal Verification: <target>

| Test | Result | Details |
|------|--------|---------|
| ... | PASS/FAIL | ... |

**Overall**: X/Y tests passed
**Scripts**: [any scripts created in scripts/tests/]
```

### Step 5: Store Test Scripts (if complex)

If verification required a custom script:
1. Save to `scripts/tests/verify-<feature>.sh`
2. Make executable: `chmod +x`
3. Update `scripts/tests/index.md`
