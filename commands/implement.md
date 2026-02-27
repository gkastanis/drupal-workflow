---
description: "Implement changes across all affected files with validation"
---
# /implement - Cross-File Implementation with Validation

## Purpose

Implement a described change across all affected files in the codebase, ensuring nothing is missed and all modifications are validated. This enforces Behavioral Rule #1 (grep after multi-file changes) and Rule #2 (verify Drupal service changes) automatically.

## Input

Read the plan or description from `$ARGUMENTS`. If no arguments are provided, check the recent conversation context for the most recent implementation plan, task description, or user request.

## Protocol

### Step 1: Understand the Change Scope

Parse the implementation request and identify:
- What is being added, changed, or removed
- Which functions, classes, services, hooks, or templates are affected
- What naming changes are involved (old name -> new name)
- What new files need to be created vs existing files modified

### Step 2: Discover All Affected Files

Use Grep and Glob to find every file that references the components being changed:

```
Grep for: function names, class names, service IDs, hook names,
          config keys, route names, permission names, Twig variables,
          template names, library names, form IDs
```

Build a complete list of files that must be touched. Do NOT rely on memory alone -- grep the codebase.

### Step 3: Implement Changes File by File

For each affected file:
1. Read the current file content
2. Make the required modifications
3. Maintain existing code style and indentation
4. Preserve comments and documentation blocks
5. Update any inline documentation that references changed components

**Order of operations for Drupal changes:**
1. `.info.yml` and `.services.yml` files (service definitions)
2. Interface files (if contracts are changing)
3. Service/class implementation files
4. Hook implementations in `.module` files
5. Plugin classes (Block, Field, etc.)
6. Form classes
7. Controller and routing files
8. Twig templates
9. Config files (`config/install/`, `config/schema/`)
10. Test files
11. JavaScript and CSS asset files

### Step 4: Validate PHP Syntax

Run `php -l` on every modified `.php` and `.module` file:

```bash
php -l <file>
```

If any file fails syntax check, fix the issue immediately before proceeding.

### Step 5: Validate Drupal-Specific Integrity

**Service injection checks:**
- For every `__construct()` that was modified, verify the parameters match the service definition in `.services.yml`
- Verify `create()` methods pass the correct container services

**Database checks (if schema was involved):**
- Verify table names in queries match `hook_schema()` definitions
- Verify column names referenced in code exist in the schema

**Twig checks (if templates were modified):**
- Verify every Twig filter used in templates actually exists (core or custom)
- Verify variables passed to templates match what the preprocess function provides
- Verify `{{ attach_library() }}` references exist in `.libraries.yml`

**Config checks (if configuration was involved):**
- Verify config schema matches the config install YAML
- Verify config keys used in code match what is defined

### Step 6: Grep for Remaining References

After all changes are applied, grep the entire codebase for:
- Old function/method names that should have been renamed
- Old service IDs that should have been updated
- Old class names or namespaces
- Old config keys
- Old route names or permission strings
- Old template names or Twig variables

Any remaining references indicate missed locations. Fix them.

### Step 7: Report Results

Output a summary:

```
## Implementation Complete

### Files Modified
- path/to/file1.php - [what changed]
- path/to/file2.module - [what changed]
- ...

### Files Created
- path/to/new-file.php - [purpose]

### Validation Results
- PHP syntax: PASS/FAIL (N files checked)
- Service injection: PASS/FAIL
- Twig filters: PASS/FAIL or N/A
- DB schema: PASS/FAIL or N/A
- Remaining old references: NONE / [list any found]

### Notes
[Any warnings, edge cases, or follow-up items]
```

$ARGUMENTS
