---
name: verification-before-completion
description: Gate function ensuring implementations are tested before claiming completion. Prevents rationalization and untested claims. Use at the end of any implementation task to validate work actually functions.
---

# Verification Before Completion Skill

Mandatory verification gate for all implementation tasks.

## The Gate (5 Steps)

Before claiming ANY task is complete:

1. **IDENTIFY** - What specific test proves the implementation works?
2. **RUN** - Execute the test (curl, drush eval, or test script)
3. **READ** - Read the actual output (don't assume)
4. **VERIFY** - Does the output confirm the claim?
5. **THEN** - Only now claim completion, including test output

If any step fails, fix and re-test. Do not skip to claiming completion.

## Verification Requirements

| Claim | Requires | NOT Sufficient |
|---|---|---|
| "Service works" | drush eval or curl test passes | "Code looks correct" |
| "Page renders" | curl smoke test HTTP 200 + content check | "Template created" |
| "Config imports" | `ddev drush cim -y` succeeds | "Exported config" |
| "Hook fires" | drush eval or behavioral test | "Added the hook" |
| "Module enabled" | `ddev drush pm:list --status=enabled` shows it | "Created .info.yml" |
| "Route works" | curl returns expected response | "Added routing.yml" |
| "Field exists" | drush eval field definition check | "Added field config" |
| "Permission works" | Login as role + curl test | "Added permission" |
| "Form submits" | Curl POST or Behat test | "Created form class" |
| "Cache works" | Two requests, second faster or cached | "Added cache tags" |

## Completion Report Template

Include in your completion message:

```
## Verification Results

**Tested**: [what was tested]
**Method**: [curl/drush eval/test script]
**Results**:
- [Test 1]: PASS/FAIL - [details]
- [Test 2]: PASS/FAIL - [details]

**Scripts created**: [list any scripts in scripts/tests/]
**Status**: [VERIFIED/NEEDS ATTENTION]
```

## Rationalization Prevention

Common excuses that are NOT verification:

| Excuse | Reality | Do Instead |
|---|---|---|
| "The code follows best practices" | Best practices don't guarantee it works | Run a test |
| "I've seen this pattern work before" | This specific implementation may differ | Run a test |
| "It should work after cache clear" | "Should" is not "does" | Clear cache AND test |
| "The logic is straightforward" | Typos and misconfigurations are common | Run a test |
| "I've created all required files" | Files existing != system working | Run a test |
| "The service definition looks correct" | YAML indentation, class names can be wrong | `drush eval` to check |

## When to Use This Skill

- End of any module development task
- After creating or modifying services, plugins, or config
- After theme changes that affect rendering
- After any "fix" or "update" task
- Before any handoff to another agent

## Quick Verification Checklist

```
[ ] Ran at least one verification test
[ ] Read the actual test output (not assumed)
[ ] Test output confirms the specific claim
[ ] Included test results in completion message
[ ] Scripts stored in scripts/tests/ (if created)
[ ] Updated scripts/tests/index.md (if scripts created)
```
