# Changelog

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
