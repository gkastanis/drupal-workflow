# Changelog

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
