---
name: discover
description: Docs-first discovery for efficient codebase exploration. Use before Glob/Grep/Explore to get Logic IDs and file paths directly from semantic documentation. Saves tokens by avoiding expensive file searches. Commands include `/discover FEATURE` for feature lookup, `/discover "search terms"` for keyword search, and `/discover --prime` to load the business index.
---

# Docs-First Discovery Skill

Fast, token-efficient codebase discovery using semantic documentation.

**Project-Agnostic:** Works with any project that has `docs/semantic/` documentation.

## Why Use This

**Before expensive file discovery:**
- Glob patterns: Can return hundreds of files
- Grep searches: Token-heavy output
- Explore agents: Multiple tool calls

**With /discover:**
- Direct Logic ID → file:line mapping
- Pre-indexed feature specs
- 70-90% token savings on discovery

## Quick Commands

### Feature Lookup
```bash
$SKILL_DIR/scripts/discover.sh AUTH
```
Returns: Full technical spec with all Logic IDs and code locations.

### Keyword Search
```bash
$SKILL_DIR/scripts/discover.sh "timer approval workflow"
```
Returns: QMD search results + matching Logic IDs.

### Prime Session Context
```bash
$SKILL_DIR/scripts/prime.sh
```
Returns: Business index summary for session context.

### List All Features
```bash
$SKILL_DIR/scripts/discover.sh --list
```
Returns: All available feature codes and descriptions.

### Check Status
```bash
$SKILL_DIR/scripts/discover.sh --status
```
Returns: Docs/QMD availability status for current project.

## Project Detection

The scripts automatically detect:
- **Project name**: From directory name (e.g., `timan` → `timan`)
- **QMD collection**: `{project-name}-docs` (e.g., `timan-docs`)
- **Docs path**: `docs/semantic/` in project root

## Usage Patterns

**Pattern 1: Feature Implementation**
```
User: "I need to modify the assignment approval workflow"
You: Run /discover ASGN
Result: Get ASGN-L1 through ASGN-L10 with exact file:line locations
Action: Read specific files instead of Glob/Grep
```

**Pattern 2: Code Location Search**
```
User: "Where is timer functionality implemented?"
You: Run /discover timer
Result: TIMR-L1 → TimerController.php:45:startTimer
Action: Direct file read
```

**Pattern 3: Session Setup**
```
User: "Let's work on the time tracking module"
You: Run /discover --prime
Result: Full business index loaded
Action: Reference Logic IDs throughout conversation
```

**Pattern 4: New Project Check**
```
User: "What features are documented?"
You: Run /discover --status
Result: Shows if docs exist and QMD collection is available
```

## Logic ID Format

Logic IDs map business logic to code:
- Format: `FEATURE-L#` (e.g., `AUTH-L3`, `TIME-L7`)
- Resolves to: `file:line:function`

## Setting Up for a New Project

1. **Generate semantic docs:**
   ```
   Run semantic-architect-agent
   ```

2. **Create QMD collection (optional, for fast search):**
   ```bash
   qmd collection add {project-name}-docs docs/
   ```

3. **Verify setup:**
   ```bash
   /discover --status
   ```

## Integration with Semantic Docs

This skill wraps:
- `/semantic-docs` for tech specs
- `qmd search` for fast full-text search
- Business index for feature registry

**Relationship:**
- `/semantic-docs`: Deep lookup by specific ID
- `/discover`: Broad discovery before deep lookup

## When This Triggers

- "Find where X is implemented"
- "Show me the code for X"
- "What handles X?"
- "Discover X feature"
- "Prime context for X"
- Before spawning Explore agents
- Before complex Glob/Grep searches

## Output Format

```
=== DISCOVER: [query] ===
Project: [project-name]

MATCHING FEATURES
[Feature table from business index]

TECHNICAL SPECS
[List of relevant tech spec files]

LOGIC ID MAPPINGS
[ID → file:line:function]

SUGGESTED ACTIONS
[Specific Read commands to run]
```

## Graceful Fallback

If no semantic docs exist:
- Hook silently skips (doesn't block agents)
- Skill shows helpful setup instructions
- Standard Glob/Grep still works as fallback
