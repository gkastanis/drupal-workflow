---
description: "Analyze dependencies and blast radius for a feature or module"
argument-hint: "<feature-code-or-module-name>"
---
# /drupal-blast-radius - Dependency & Impact Analysis

## Purpose

Analyze what a feature or module depends on, what depends on it, and where changes would have the widest impact.

## Input

Read target from `$ARGUMENTS`. Accepts a feature code (e.g., AUTH, CONT) or a module machine name.

## Protocol

### Step 1: Validate Structural Index

Check that `docs/semantic/structural/` exists and is populated. If not, tell the user:

> Structural index not found. Run `/drupal-refresh` first.

Stop here if missing.

### Step 2: Get Dependency Graph

```bash
bash "$PLUGIN_DIR/skills/discover/scripts/discover.sh" "deps:$ARGUMENTS"
```

### Step 3: Search Structural Files

Grep the following files in `docs/semantic/structural/` for `$ARGUMENTS`:
- `services.md`
- `hooks.md`
- `routes.md`
- `plugins.md`
- `entities.md`

Collect all references.

### Step 4: Load Tech Spec (if feature code)

If `$ARGUMENTS` is 2-4 uppercase characters (a feature code), also read the matching tech spec from `docs/semantic/tech/`.

### Step 5: Present Blast Radius Report

```
## Blast Radius: $ARGUMENTS

### Direct Dependencies
What this module/feature uses (services, APIs, entities).

### Consumers
What uses this module/feature (dependents, hook subscribers).

### Hotspot Services
Services with the most cross-module references.

### Cross-Cutting Hooks
Hooks that affect or are affected by this module.

### Change Caution Zones
Areas where a change here would cascade into other features.
```

$ARGUMENTS
