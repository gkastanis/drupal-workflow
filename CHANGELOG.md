# Changelog

## [2.0.1] - 2026-04-15

### Added

- **Autopilot Phase 2**: Weighted drift formula (plan=0.3, delegate=0.3, skill=0.2, verify=0.2), 3-level escalation (hint → command → suppress, MAX_FIRES_PER_TYPE=2), phase budget enforcement from policy files.
- **`maintenance` task type**: New classifier category for config/update/tweak tasks — no plan or delegation required. Keywords: update, config, settings, tweak, adjust, bump, cleanup, tidy, enable, disable, toggle, patch, minor, change, modify, set, tune, swap, switch.
- **`autopilot-tuner` skill**: Self-improvement skill that reads session data (intervention logs, outcomes), computes acceptance rates, and proposes policy/threshold/classifier changes with confidence levels.
- **`analyze-replays.py`**: Session analysis script with `--compare` mode (before/after Phase 2 deployment) and `--json` output. `--verbose` for per-session breakdown.
- **`diagnose.py`**: Structured diagnostic script outputting acceptance rates, outcome correlations, classification accuracy, threshold sensitivity, and actionable proposals.
- **Outcome archival**: `workflow-reset.sh` archives previous session state + intervention log to `outcomes.jsonl` before resetting. Intervention log truncated per session (no cross-session accumulation).
- **One-time banner**: PostToolUse monitor prints autopilot status on first tool call of session.
- **10 behavioral eval cases** (`test-autopilot-phase2.sh`): Classifier, weighted drift, escalation levels, suppression, phase budgets, maintenance policy, verification.

### Fixed

- **Monitor on wrong hook**: Rebase artifact placed autopilot-monitor under `Stop` instead of `PostToolUse` — monitor never received per-tool payloads. (Found by Codex review)
- **flock race condition**: `flock -n` (non-blocking) → `flock -w 1` (1s wait) — prevents concurrent tool calls from clobbering `intervention_history`, which was defeating the escalation cap.
- **Cache desync**: Plugin cache had old version printing to stderr (invisible to agents), no escalation, no maintenance type. Synced marketplace → cache.
- **verification-before-completion not detected**: Added to verification skill detection patterns alongside drupal-test/drupal-verif.
- **Dead code**: `workflow-nudge.sh` deprecated (not in hooks.json), `counters.state` init removed from `workflow-reset.sh`.

### Changed

- **19 skills** (was 18). Added `autopilot-tuner`.
- **6 task types** (was 5). Added `maintenance`.
- **min_skills**: 2 → 1 in implementation and refactoring policies.
- **plan_missing threshold**: edits > 3 → edits > 5.
- **verify_remind**: Removed `delegations >= 1` gate — solo sessions now get verification nudges.
- README updated with Phase 2 features, autopilot-tuner in skills table, project structure.

## [2.0.0] - 2026-04-13

### Added

- **Magic Loop Autopilot (Phase 1)**: Live workflow policy engine. Task classifier at SessionStart categorizes prompts into 5 types (implementation, investigation, refactoring, documentation, debugging). Autopilot monitor replaces workflow-nudge with state-vector-based drift detection. Context-specific interventions: plan_missing, delegate_suggest, skill_suggest, verify_remind. Kill switch via `DRUPAL_WORKFLOW_AUTOPILOT=off`.
- **`drupal-brainstorming` skill**: Structured exploration before implementation — entity/data design, service architecture, hook/event strategy, anti-patterns.
- **`drupal-delegation` skill**: Execute plans via specialized agent dispatch with progress tracking. Documents the brainstorm→plan→delegate→verify workflow.
- **Behavioral eval framework**: `run-behavioral.py` (static + behavioral runner, 4 providers: Claude, Codex, Gemini, Mistral) and `compare.py` (A/B skill comparison with cost tracking, automatic git baseline). Ported from ai_best_practices.
- **23 behavioral eval cases** across 6 skills (drupal-rules, service-di, entity-api, security-patterns, caching, hook-patterns) + 48 static checks.
- **Session replay eval**: `extract-prompts.py` extracts eval cases from JSONL session logs, `replay-eval.py` converts to behavioral evals, `pattern-score.py` scores sessions 0-100 against magic-era benchmarks. 31 replay cases from 11 magic-era sessions.
- **Session analysis toolkit** (10 scripts): overview, timeline, costs, tools, search, quality, thinking, subagents, branches, dashboard. Shared `_common.py` with per-model pricing.
- **5 policy templates** in `scripts/policies/` for task-type-specific workflow expectations.
- **Freshness metadata** on all 18 SKILL.md files: `status`, `drupal-version`, `last-reviewed`.
- **Autopilot spec** (`docs/AUTOPILOT_SPEC.md`, 447 lines) covering Phases 2-3: drift formula, escalation, provider routing, replay feedback loop.

### Fixed

- **30 bug fixes** from 3-way review (Claude + Codex GPT-5.4 + claude-code-guide agent).
- **Security**: `block-sensitive-files.sh` shebang `#!/bin/sh`→`#!/usr/bin/env bash` (was failing open on dash), state file sourcing replaced with grep/cut, agent name sanitization, flock for concurrency.
- **Correctness**: `.tool_input.path` fallback in lint/staleness hooks, atomic writes (temp+mv) in all 10 generators, frontmatter extraction with awk, feature code anchoring, check-staleness expanded to `.install`/`.profile`, nullglob for `ls` under `set -e`, event subscriber grep pipeline fix.
- **Eval framework**: frontmatter parser handles `---` in body, missing file emits failing assertion, dual hooks.json path resolution, unused imports removed.

### Changed

- **18 skills** (was 16). `drupal-builder` agent loads `drupal-brainstorming` and `drupal-delegation`.
- **12 hooks** (was 8). Added: `task-classifier.sh` (SessionStart), `autopilot-monitor.sh` (PostToolUse `.*`), `workflow-reset.sh` (SessionStart).
- **hooks.json**: SessionStart watches 8 file types (was 4), `/tmp` info leak removed.
- **pattern-score.py**: 6 scoring dimensions (was 5, added verification), recognizes in-house skills (no superpowers dependency).

## [1.8.0] - 2026-03-14

### Added

- **`drupal-config-management` skill**: Config split, config ignore, config readonly, environments, import/export workflows, config schema, and config translation patterns.
- **Entity API skill**: AccessControlHandler example, `integer`/`decimal`/`float` field types.
- **Caching skill**: `CacheableMetadata` class (OOP cache API) and `#lazy_builder` patterns.
- **Hook patterns skill**: Install/update/post-update hooks (`hook_install`, `hook_update_N`, `hook_post_update_NAME`) with batch processing example. Fixed `$this->t()` by adding `StringTranslationTrait`.
- **Testing skill**: Environment detection snippet (DDEV/Lando/bare drush fallback).
- **Method index generator**: Scans `src/EventSubscriber/`, `src/Access/`, `src/Manager/`, `src/Builder/` in addition to Service/Controller/Form.
- **Route map generator**: Captures `_entity_access` requirement type. Accumulates multiple access requirements per route (was overwriting).
- **Hook registry generator**: Scans `.install` and `.profile` files for `hook_install`, `hook_update_N`, `hook_schema`, `hook_requirements`, etc.
- **Staleness check**: Watches `.install`, `.info.yml`, `.permissions.yml` files and PHP method changes.
- **Builder agent**: `WebSearch` tool added for API lookup.
- **Feature map generator**: Infrastructure module detection — modules referenced by >50% of features excluded from per-feature counts (listed separately). Feature code deduplication in cross-cutting concerns.

### Fixed

- **Feature map**: entities.md column index was wrong (col 6 → col 7) after Fields column was added in v1.3.0. Field counts like "6", "8", "9" were being treated as module names in cross-cutting concerns.
- **Entity API skill**: CRUD examples replaced `\Drupal::` static calls with dependency injection patterns.
- **Caching skill**: Cache invalidation examples replaced `\Drupal::service()` with injected `CacheTagsInvalidatorInterface`.
- **Writing-plans skill**: Wrong cache tag `node_list:article` → `node_list` (no bundle qualifier in core).
- **verify-changes command**: Replaced removed `db_select`/`db_query` (Drupal 9) with `$this->database->select()`.
- **block-sensitive-files.sh**: Now blocks `sites/default/services.yml` (was only blocking dev/local variants).

### Changed

- **Reviewer agent**: Loads 14 skills (added `drupal-caching`, `drupal-config-management`, `drupal-hook-patterns`, `twig-templating`, `drupal-conventions`).
- **Builder agent**: Loads 14 skills (added `drupal-config-management`).
- **Verifier agent**: Loads `verification-before-completion` skill (was missing from the verification agent).

## [1.7.0] - 2026-03-14

### Added

- **Eval framework** (7 scripts, 315 assertions): Automated quality checks for all skills, agents, hooks, and behavioral tests.
  - `eval-skills.py`: 165 assertions across 15 reference skills (content quality, key terms, imperatives).
  - `eval-agents.py`: 60 assertions across 4 agent definitions (structure, frontmatter, skills).
  - `eval-hooks.py`: 20 assertions for hooks system integrity.
  - `eval-semantic-architect.py`: 25 assertions for tech spec output quality (behavioral).
  - `eval-builder-agent.py`: 20 assertions for skill application (behavioral — does the agent use its loaded skills?).
  - `eval-reviewer-agent.py`: 15 assertions for issue detection (behavioral).
  - `eval-verifier-agent.py`: 10 assertions for verification output (behavioral).
- **Playground pages**: Interactive HTML docs for Discover (search/query routing) and Agents (team/skills/hooks). Navigation across all 3 pages.

### Fixed

- **All commands**: Replace `$PLUGIN_DIR` (nonexistent) with `$CLAUDE_PLUGIN_ROOT` (actual env var). This was causing "PLUGIN_DIR: not found" on all projects.

### Improved

- **11 skill definitions**: Fixed YAML frontmatter format (7 skills), added imperative language (8 skills), added missing key terms like `baseFieldDefinitions`, `accessCheck`, `#cache`, `|t` (5 skills).
- **drupal-verifier agent**: Added `## Scope` section.
- **semantic-architect agent**: Added `## Scope` section, trimmed content from 8592 to 7989 chars.
- **drupal-rules**: Added `accessCheck`, `#cache` metadata, and `TranslatableMarkup` rules.

## [1.6.0] - 2026-03-13

### Added

- **CLAUDE.md auto-injection** (`scripts/inject-claude-md.sh`): After semantic doc generation, injects a compact `## Codebase` section into the project's CLAUDE.md with feature counts, Logic ID totals, and CODE:Name pairs. This is the prompt hint that drives +61% speed improvement from the v4 eval.
  - Creates CLAUDE.md if missing, replaces existing `## Codebase` section, or appends. Idempotent.
  - Wired into `/drupal-semantic init` (Step 7), `feature` (Step 3), and `index` (Step 3).
- **Tech spec validator** (`scripts/validate-tech-specs.sh`): Checks `CODE_01_Name.md` naming and YAML frontmatter. `--fix` auto-renames and adds missing frontmatter. Fixes non-deterministic agent output.
- **New `/drupal-semantic` subcommands**: `validate [--fix]` and `inject` for standalone use without spawning the architect agent.

### Changed

- **`@semantic-architect` agent**: Hardened file naming constraints with explicit MUST rules and forbidden examples to reduce non-deterministic output across repos.
- **`/drupal-bootstrap`**: Rewritten to follow the 3-step pipeline (structural → semantic → CLAUDE.md hint). No longer runs `prime.sh`.
- **`/drupal-refresh`**: Runs `inject-claude-md.sh` instead of heavy `prime.sh` after regenerating structural index.
- **`/drupal-prime`**: Documented as debug/overview command (~2500 tokens), not part of the main pipeline.
- **All commands**: Standardized variable references (later fixed to `$CLAUDE_PLUGIN_ROOT` in v1.7.0).
- **`prime.sh`**: Fixed Logic ID counting (use frontmatter instead of broken grep pattern), fixed stale command references.
- **README**: New Workflow section explaining the 3-step pipeline, updated command descriptions, project structure.

## [1.5.0] - 2026-03-13

### Added

- **Semantic Architect agent** (`@semantic-architect`): AI-powered Layer 3 documentation generator.
  - Reads structural index (Layer 2) + source code to produce business index, tech specs with Logic IDs, and business schemas.
  - Incremental update protocol preserves existing Logic IDs.
  - Quality checklist ensures every service method, route, and hook has a Logic ID.
  - Context window management: one feature per agent spawn.
- **`/drupal-semantic` command** with 5 subcommands:
  - `status` — check semantic doc coverage and staleness
  - `feature FEAT` — generate/update tech spec for a feature
  - `index` — generate/update the business index
  - `schema ENTITY` — generate/update a business schema
  - `init` — full project semantic doc generation (orchestrates multiple agent spawns)
- **`*.business.json` schema format**: AI-authored entity schemas containing only business rules, related entities, and examples — no field definitions. Separates AI-authored content from auto-generated `*.base-fields.json` and `*.BUNDLE.json`.
- **Schema auto-migration**: Agent detects conflicting `*.json` with `business_rules`, strips field definitions, renames to `*.business.json`.
- **SessionStart auto-regen**: Structural index automatically regenerates when source files have changed since last generation (~10s cost, 0s when fresh).

### Changed

- `drupal-bootstrap.md`: Step 2 now nudges user toward `/drupal-semantic init` instead of generating semantic docs inline.
- `semantic-docs/SKILL.md`: Documentation structure updated to show all three schema types (`*.base-fields.json`, `*.BUNDLE.json`, `*.business.json`).
- `structural-index/SKILL.md`: Layer diagram references `@semantic-architect` as Layer 3 generator.
- `hooks.json`: SessionStart hook adds staleness check with auto-regen.
- README: Updated to 4 agents, 10 commands, schema tree with `*.business.json`.

## [1.4.0] - 2026-03-13

### Added

- Base field generator (`generate-base-fields.sh`): parses PHP `baseFieldDefinitions()` and entity type attributes.
  - Generates per-entity JSON schemas in `docs/semantic/schemas/*.base-fields.json` with entity metadata, field types, settings, cardinality.
  - Summary table in `docs/semantic/structural/base-fields.md`.
  - Patches `entities.md` Fields column with base+config format (e.g., `19+8`).
- Permission registry generator (`generate-permission-registry.sh`): parses `*.permissions.yml` in custom modules.
  - Outputs `docs/semantic/structural/permissions.md` with permission names, titles, modules, restrictions.
- Method index generator (`generate-method-index.sh`): indexes public methods in Service/Controller/Form classes.
  - Outputs `docs/semantic/structural/methods.md` with 3 sections, return types, and line numbers.
- `discover perm:NAME` and `discover method:NAME` query prefixes for structural discovery.

## [1.3.0] - 2026-03-13

### Added

- Entity schema generation from config YAML (`field.storage.*.yml` + `field.field.*.yml`).
  - Generates per-bundle JSON schemas in `docs/semantic/schemas/` with field types, labels, cardinality, target types/bundles, and allowed values.
  - Summary table in `docs/semantic/structural/schemas.md`.
  - Enhances `entities.md` with Fields column showing count breakdown (e.g., `8 (3 ref, 1 list)`).
- `discover schema:ENTITY` query prefix for on-demand schema lookup.
- Config directory auto-detection: `config/sync`, `config/default`, `config/staging`, `../config/sync`, with fallback to `modules/custom/*/config/install`.

## [1.2.0] - 2026-03-12

### Added

- `/drupal-bootstrap` command: auto-detect project state and run appropriate setup
- `/drupal-prime` command: load project context into session
- `/drupal-refresh` command: regenerate structural index and re-prime
- `/drupal-status` command: check docs, structural index, and staleness
- `/drupal-blast-radius` command: dependency and blast radius analysis

## [1.1.0] - 2026-03-12

### Added

- **structural-index skill**: Auto-generated structural awareness layer for Drupal projects.
  - 9 generator scripts parse `*.services.yml`, `*.routing.yml`, `*.module`, PHP plugin annotations/attributes, and entity type definitions.
  - Produces 5 structural index files (`services.md`, `routes.md`, `hooks.md`, `plugins.md`, `entities.md`) + 2 cross-reference files (`DEPENDENCY_GRAPH.md`, `FEATURE_MAP.md`).
  - No external dependencies — grep/sed state machines handle Drupal's declarative YAML.
  - Supports `web/`, `www/`, and top-level `modules/` docroot layouts.
- **Structural query prefixes** in discover skill: `service:`, `route:`, `hook:`, `plugin:`, `entity:`, `deps:`, `impact:`.
- **Staleness detection**: PostToolUse hook warns when structural source files are edited. `check-staleness.sh` provides full staleness reports. `prime.sh` shows staleness warnings during session priming.
- **FEATURE_MAP.md**: Compact feature overview loaded during session priming, with structural artifact counts and hotspot scoring.
- **DEPENDENCY_GRAPH.md**: Service dependency chains, most-injected service hotspots, hook/event chains, entity cross-references, external boundaries, and feature adjacency matrix (for projects with <=15 features).
- **Agent integration**: All three agents (`drupal-builder`, `drupal-reviewer`, `drupal-verifier`) now include `structural-index` in their skill sets with structural awareness workflows.
- **Subagent context injection**: Hints about structural index availability injected when agents spawn.

### Changed

- `discover.sh`: Added structural query helper functions and 6 new case branches. `search_docs()` falls through to structural index. `check_status()` reports structural index availability. All discovery queries use fixed-string grep (`-F`) for safety.
- `prime.sh`: Loads `FEATURE_MAP.md` as primary context when available, with staleness warning.
- `drupal-reviewer.md`: Validation workflow expanded to 7 steps (added structural impact review). Three new red flags for structural-related issues.
- `drupal-verifier.md`: Added "Structural" verification type.

## [1.0.1] - 2026-03-10

### Fixed

- Use explicit matchers and `once` flag in `hooks.json`.
- Correct `marketplace.json` schema with `owner`, `source` fields.
- Move `marketplace.json` to `.claude-plugin/` where plugin system expects it.

## [1.0.0] - 2026-03-09

### Added

- Initial release with 14 skills, 3 agents, 4 commands, and quality-gate hooks.
- Consolidated 10 agents into 3 (builder, reviewer, verifier).
