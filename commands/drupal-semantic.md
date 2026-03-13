---
description: "Generate and manage semantic documentation (business index, tech specs, business schemas)"
argument-hint: "<init|feature FEAT|index|schema ENTITY|status>"
---
# /drupal-semantic - Semantic Documentation Manager

## Purpose

Generate and manage Layer 3 semantic documentation: business index, tech specs with Logic IDs, and business schemas. Orchestrates the `@semantic-architect` agent.

## Input

Read subcommand from `$ARGUMENTS`. Supported subcommands:

- `status` — Check semantic doc coverage and staleness
- `feature FEAT` — Generate/update tech spec for a feature
- `index` — Generate/update the business index
- `schema ENTITY` — Generate/update a business schema
- `init` — Full project semantic doc generation

If no argument given, default to `status`.

---

## Subcommand: `status`

No agent needed. Inline check.

### Step 1: Check Prerequisites

```bash
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
```

Verify `docs/semantic/structural/.generated-at` exists. If not:
> Structural index not found. Run `/drupal-refresh` first.

### Step 2: List Documented Features

Read all files in `docs/semantic/tech/*.md`. Extract `feature_id` and `feature_name` from frontmatter. List them.

### Step 3: Find Undocumented Modules

Read `docs/semantic/structural/services.md`. Extract unique module names. Compare against modules covered by existing tech specs. Report any modules without a tech spec.

### Step 4: Check Schema Conflicts

Look for `docs/semantic/schemas/*.json` files (excluding `*.base-fields.json`, `*.business.json`) that contain `business_rules`. If a corresponding `*.base-fields.json` also exists, flag as conflicting — needs migration to `*.business.json`.

### Step 5: Report Staleness

For each `docs/semantic/tech/*.md`, compare `last_updated` frontmatter against modification times of files listed in `related_files`. Flag stale specs.

### Step 6: Summary

```
## Semantic Documentation Status

**Documented features**: X (list)
**Undocumented modules**: Y (list)
**Schema conflicts**: Z (list needing migration)
**Stale tech specs**: W (list)

### Suggested Actions
- /drupal-semantic feature FEAT — generate missing spec
- /drupal-semantic init — generate all missing docs
- /drupal-semantic schema ENTITY — fix schema conflict
```

---

## Subcommand: `feature FEAT`

### Step 1: Validate

Check structural index exists. Check if `FEAT` matches a known feature code or module name.

### Step 2: Spawn Agent

Spawn `@semantic-architect` with task:

> Generate or update the tech spec for feature **FEAT**.
>
> - Read `docs/semantic/structural/` files for module context
> - Read source code for the module(s) associated with FEAT
> - If tech spec exists at `docs/semantic/tech/FEAT_*.md`, update incrementally (preserve Logic IDs)
> - If tech spec does not exist, create it from scratch
> - Output: `docs/semantic/tech/FEAT_01_<Name>.md`
> - If this feature includes entity types, also generate `docs/semantic/schemas/<entity>.business.json`
> - Run schema auto-migration if needed (see agent instructions)

### Step 3: Report

Show the generated/updated file paths and Logic ID count.

---

## Subcommand: `index`

### Step 1: Validate

Check structural index exists. Check that at least one `docs/semantic/tech/*.md` file exists.

### Step 2: Spawn Agent

Spawn `@semantic-architect` with task:

> Generate or update `docs/semantic/00_BUSINESS_INDEX.md`.
>
> - Read ALL existing `docs/semantic/tech/*.md` files to build the feature registry
> - Read `docs/semantic/FEATURE_MAP.md` for structural counts
> - Read `docs/semantic/DEPENDENCY_GRAPH.md` for module dependencies
> - Do NOT analyze source code directly — the tech specs are your source of truth
> - If business index exists, update incrementally (preserve user stories and business rules)
> - Output: `docs/semantic/00_BUSINESS_INDEX.md`

### Step 3: Report

Show feature count and any new/updated entries.

---

## Subcommand: `schema ENTITY`

### Step 1: Validate

Check structural index exists. Verify the entity type exists in `docs/semantic/structural/entities.md`.

### Step 2: Spawn Agent

Spawn `@semantic-architect` with task:

> Generate or update `docs/semantic/schemas/ENTITY.business.json`.
>
> - Read `docs/semantic/schemas/ENTITY.base-fields.json` for field context
> - Read the entity class source code
> - Read any existing `ENTITY.business.json` to update incrementally
> - Run schema auto-migration if an old `ENTITY.json` with `business_rules` exists
> - Output: `docs/semantic/schemas/ENTITY.business.json`

### Step 3: Report

Show the generated file path. If migration occurred, report what was migrated.

---

## Subcommand: `init`

Full project semantic doc generation.

### Step 1: Validate Structural Index

```bash
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
```

Check `docs/semantic/structural/.generated-at` exists. If not:
> Structural index not found. Run `/drupal-refresh` first.

### Step 2: Discover Modules

Read `docs/semantic/structural/services.md`. Extract all unique custom module names.

### Step 3: Derive Feature Codes

Auto-derive feature codes from module names:
- Strip common project prefix (first `_`-delimited segment if shared by >50% of modules)
- Take meaningful abbreviation, 3-4 uppercase letters
- Examples: `timan_assignment` → `ASGN`, `timan_time_entry` → `TIME`, `timan_holiday` → `HDAY`

No user confirmation needed.

### Step 4: Generate Tech Specs

For each feature, spawn `@semantic-architect` with the `feature FEAT` task (see above). Generate one feature at a time to manage context window.

Report progress: "Generating FEAT (X of Y)..."

### Step 5: Generate Business Index

After all features are done, spawn `@semantic-architect` with the `index` task (see above).

### Step 6: Write Generation Summary

Create `docs/semantic/GENERATION_SUMMARY.md`:

```markdown
# Semantic Documentation Generation Summary

**Generated**: <YYYY-MM-DD HH:MM>
**Plugin version**: 1.5.0

## Features Generated

| Code | Feature | Logic IDs | Entities | Status |
|------|---------|-----------|----------|--------|
| ASGN | Assignment | 15 | timan_assignment | new |

## Business Schemas

| Entity | File | Migrated |
|--------|------|----------|
| timan_assignment | timan_assignment.business.json | yes/no |

## Statistics

- Tech specs: X
- Total Logic IDs: Y
- Business schemas: Z
- Migrated schemas: W
```

### Step 7: Report

Output the full summary to the user.

$ARGUMENTS
