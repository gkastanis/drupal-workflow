---
description: "Verify code changes are complete and consistent"
---
# /verify-changes - Post-Change Verification

## Purpose

Perform a comprehensive verification of recent code changes to catch incomplete modifications, orphaned references, broken integrations, and inconsistencies. This is the enforcement mechanism for Behavioral Rules #1 (grep after changes), #2 (verify Drupal service changes), and #4 (remove from ALL locations).

## Input

Read optional scope or file list from `$ARGUMENTS`. If no arguments are provided, verify all uncommitted changes in the working tree.

## Protocol

### Step 1: Identify What Changed

Determine the scope of changes to verify:

```bash
# If no arguments, check working tree
git diff --name-only
git diff --cached --name-only
git diff --name-only HEAD~1  # Also check last commit if working tree is clean
```

From the changed files, extract:
- Function/method names that were added, modified, or removed
- Class names that were added, modified, or removed
- Service IDs that were changed
- Hook implementations that were modified
- Config keys that were changed
- Route names, permission strings, menu links
- Template names and Twig variables
- CSS class names and JS function names

### Step 2: Grep for Orphaned References

For every identifier that was renamed, moved, or removed, grep the ENTIRE codebase:

```
Search for: old function names, old class names (including use statements),
            old service IDs (in .services.yml AND PHP code),
            old config keys, old route names, old permission strings,
            old template names, old Twig variable names
```

**Check these file types:**
- `.php`, `.module`, `.install`, `.theme` - PHP code
- `.services.yml`, `.routing.yml`, `.permissions.yml`, `.links.*.yml` - Drupal YAML
- `.info.yml`, `.libraries.yml` - Module/theme definitions
- `.html.twig` - Templates
- `.js`, `.css`, `.scss` - Frontend assets
- `*.schema.yml` - Config schema
- `config/install/*.yml`, `config/optional/*.yml` - Default config
- `*.test`, `*.php` in test directories - Test files

Flag any remaining references as **FAIL** items.

### Step 3: Verify Service Injection Consistency

For every `.services.yml` file that was modified:

1. Read the service definition (class, arguments)
2. Read the corresponding PHP class
3. Verify:
   - `__construct()` parameters match the service arguments in order and type
   - `create(ContainerInterface $container)` passes the correct services
   - The class path in `.services.yml` matches the actual namespace
   - Parent services are valid if `parent:` is used
   - Tagged services implement the required interface

For every PHP class whose `__construct()` was modified:
1. Check if it has a `.services.yml` entry
2. Verify the entry matches

### Step 4: Verify Database Schema Consistency

If any `.install` file was modified or any code references database tables:

1. Read `hook_schema()` definitions
2. Grep for all `db_select`, `db_query`, `$database->select()`, `$database->query()`, `$connection->select()`, `$connection->query()` calls
3. Verify:
   - Table names in queries match schema definitions
   - Column names in queries exist in the schema
   - Index definitions reference valid columns
   - `hook_update_N()` functions properly alter existing tables

### Step 5: Verify Twig Template Consistency

If any `.html.twig` file was modified:

1. For each Twig filter used (e.g., `|t`, `|raw`, `|without`, custom filters):
   - Verify it exists in Drupal core or a custom Twig extension in the project
2. For each variable used in the template:
   - Check the corresponding preprocess function or controller provides that variable
3. For each `{{ attach_library('module/library') }}`:
   - Verify the library exists in the corresponding `.libraries.yml`
4. For each `{% include %}` or `{% embed %}`:
   - Verify the referenced template exists

### Step 6: Verify Import/Use Statement Consistency

For every modified PHP file:

1. Check all `use` statements at the top of the file
2. Grep the file body for actual usage of each imported class/trait/interface
3. Flag:
   - **Orphaned imports**: `use` statements for classes not referenced in the file body
   - **Missing imports**: Classes referenced without a `use` statement (relying on FQCN or missing entirely)
   - **Wrong namespace**: `use` statements pointing to moved/renamed classes

### Step 7: Verify Configuration Consistency

If config files were modified:

1. Check `config/schema/*.schema.yml` matches the structure of `config/install/*.yml`
2. Verify config keys used in PHP code (`$config->get('key')`) exist in the schema
3. Check that `hook_install()` / `hook_update_N()` properly handle config changes
4. Verify form elements in settings forms match config keys

### Step 8: Cross-Reference Test Files

If implementation files changed, check corresponding tests:

1. Grep test directories for references to changed classes/functions
2. Flag tests that:
   - Reference old class names or methods that no longer exist
   - Mock services that have changed signatures
   - Assert against behavior that was modified
   - Are missing entirely for new functionality

### Step 9: Report Verification Results

Output a structured report:

```
## Verification Results

### Orphaned References
- PASS: No orphaned references found
  OR
- FAIL: Found N orphaned references:
  - `old_function_name` referenced in path/to/file.php:42
  - `old.service.id` referenced in path/to/module.services.yml:15
  - ...

### Service Injection
- PASS: All service definitions match implementations
  OR
- FAIL: Mismatches found:
  - my_module.my_service: __construct expects 3 args, .services.yml defines 2
  - ...

### Database Schema
- PASS: All queries reference valid tables/columns
  OR
- FAIL: Issues found:
  - ...
  OR
- N/A: No database changes detected

### Twig Templates
- PASS: All filters, variables, and libraries verified
  OR
- FAIL: Issues found:
  - ...
  OR
- N/A: No template changes detected

### Import Statements
- PASS: All use statements are valid and used
  OR
- FAIL: Issues found:
  - Orphaned: use Drupal\old_module\OldClass in path/to/file.php
  - ...

### Configuration
- PASS: Config schema, install, and code usage are consistent
  OR
- FAIL: Issues found:
  - ...
  OR
- N/A: No configuration changes detected

### Test Coverage
- PASS: Tests updated to match changes
  OR
- WARN: Tests may need updating:
  - path/to/Test.php references old method name
  - No test found for new class NewService
  - ...

### Overall: PASS / FAIL (N issues found)
```

$ARGUMENTS
