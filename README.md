# drupal-workflow

A comprehensive Claude Code plugin for Drupal development. Provides 15 skills, 3 specialized agents, 9 commands, and quality-gate hooks for testing, dependency injection, entity API, caching, security, and verification.

## Installation

### As a local plugin

```bash
claude --plugin-dir ./drupal-workflow
```

### As an npm package (future)

```bash
npm install drupal-workflow
```

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- [DDEV](https://ddev.readthedocs.io/) local development environment
- Drupal 10+ or 11+ project
- PHP 8.2+

## Skills (15)

Skills provide domain knowledge that Claude can consult during development.

| Skill | Description |
|-------|-------------|
| **drupal-rules** | Core development rules: code quality, security, services, testing. Auto-consulted when writing Drupal code. |
| **drupal-testing** | Practical testing patterns: curl smoke tests, drush eval, test scripts. Verifies implementations actually work. |
| **drupal-service-di** | Service definitions, dependency injection patterns, and interface design. |
| **drupal-entity-api** | Field types, entity CRUD, view modes, and content modeling. |
| **drupal-caching** | Cache bins, tags, contexts, invalidation strategies, and external caching. |
| **drupal-hook-patterns** | OOP hooks (Drupal 11), form alters, entity hooks, and legacy bridges. |
| **drupal-security-patterns** | OWASP prevention patterns, access control, input sanitization, XSS protection. |
| **drupal-coding-standards** | PHPCS, PHPStan, naming conventions, and code style enforcement. |
| **drupal-conventions** | Translations, CSS conventions, error handling patterns. |
| **twig-templating** | Twig template patterns, filters, theme suggestions, and component architecture. |
| **verification-before-completion** | Gate function preventing untested claims. Validates work before marking complete. |
| **semantic-docs** | Navigate business-logic-to-code mappings in `docs/semantic/`. Search by Logic ID, feature code, or entity schema. |
| **discover** | Docs-first codebase discovery. Use before Glob/Grep to get Logic IDs and file paths from semantic documentation. Now supports structural queries (`service:`, `hook:`, `deps:`, etc.). |
| **structural-index** | Auto-generated structural awareness for Drupal projects. Parses `*.services.yml`, `*.routing.yml`, hooks, plugins, and entity types to build dependency graphs and feature maps. |
| **writing-plans** | Write comprehensive implementation plans for sub-agents or complex tasks. |

## Agents (3)

Three focused agents covering the full Drupal development lifecycle: build, review, verify.

| Agent | Description |
|-------|-------------|
| **drupal-builder** | Full-stack implementation: modules, themes, config, migrations, performance. |
| **drupal-reviewer** | Architecture, security audit, coding standards, and test writing. |
| **drupal-verifier** | Implementation verification via ddev drush eval, curl smoke tests, config checks. |

## Commands (9)

Slash commands for common development workflows.

| Command | Usage | Description |
|---------|-------|-------------|
| `/drupal-test` | `/drupal-test service` | Run Drupal verification tests (services, entities, routes, config). |
| `/drupal-verify` | `/drupal-verify` | Verify implementation using smoke tests and drush checks. |
| `/implement` | `/implement` | Implement changes across all affected files with validation. |
| `/verify-changes` | `/verify-changes` | Verify code changes are complete and consistent. |
| `/drupal-bootstrap` | `/drupal-bootstrap` | Auto-detect project state and bootstrap semantic docs, structural index, and session context. |
| `/drupal-prime` | `/drupal-prime` | Load project context into session (feature map, business index, Logic IDs). |
| `/drupal-refresh` | `/drupal-refresh` | Regenerate structural index and reload session context. |
| `/drupal-status` | `/drupal-status` | Check documentation, structural index, and staleness status. |
| `/drupal-blast-radius` | `/drupal-blast-radius AUTH` | Analyze dependencies and blast radius for a feature or module. |

## Hooks

The plugin registers hooks for quality gates:

| Event | Trigger | Action |
|-------|---------|--------|
| **SessionStart** | Plugin loaded | Displays activation message with available commands. |
| **PreToolUse** | `Read` or `Grep` | Blocks access to sensitive files (`settings.php`, `.env`, credentials). |
| **PostToolUse** | `Edit` or `Write` | Runs `php -l` lint on modified PHP files. Advisory staleness warning when structural source files are edited. |
| **SubagentStart** | Any subagent | Injects Drupal context (version detection, agent memory paths). |
| **TaskCompleted** | Task marked done | Runs quality gate checks on completed work. |

## Project Structure

```
drupal-workflow/
├── .claude-plugin/
│   └── plugin.json          # Plugin metadata
├── skills/                   # 15 Drupal development skills
│   ├── structural-index/     # Auto-generated structural awareness
│   │   └── scripts/          # 9 generator + check scripts
│   └── ...                   # 14 other skills
├── agents/                   # 3 specialized agents
├── commands/                 # 4 slash commands
├── hooks/
│   └── hooks.json            # Hook event definitions
├── scripts/                  # Hook implementation scripts
│   ├── block-sensitive-files.sh
│   ├── php-lint-on-save.sh
│   ├── staleness-check.sh    # PostToolUse structural staleness advisory
│   ├── subagent-context-inject.sh
│   ├── teammate-quality-gate.sh
│   └── lib/
│       └── hook-utils.sh
└── README.md
```

## Getting Started — Suggested Prompts

Copy-paste these prompts when starting a Claude Code session in a Drupal project.

### Fresh project (no docs/semantic/)

> Run `/drupal-bootstrap`

This auto-detects project state and bootstraps semantic docs, structural index, and session context in one step.

### Existing project (docs/semantic/ exists)

> Run `/drupal-status` then `/drupal-refresh` if needed.

This checks documentation and structural index staleness, then regenerates and re-primes if anything is out of date.

### Quick session (skip generation, just prime)

> Run `/drupal-prime`

This loads the feature map, business index, and Logic ID counts in one shot. Best when the structural index is already up to date.

### Context efficiency

On a real Drupal project (~85k LOC custom code, 26 features, 433 Logic IDs), `/discover --prime` outputs **~2,500 tokens** (~190 lines) covering:

- Full feature map with structural counts and hotspot scoring
- Cross-cutting module dependencies
- Feature registry with descriptions
- Key entities and core capabilities
- Logic ID counts per feature (26 tech specs)
- Available tech specs and query commands

That's ~1.2% of a 200k context window — roughly **34 lines of code awareness per token spent**.

## Semantic Documentation (Optional)

For large Drupal projects, create `docs/semantic/` in your project root to enable logic-to-code mapping:

```
docs/semantic/
├── 00_BUSINESS_INDEX.md      # Master feature index
├── tech/*.md                 # Logic-to-code mappings
├── schemas/*.json            # Entity schemas
├── structural/               # Auto-generated by structural-index
│   ├── services.md           # Service graph
│   ├── routes.md             # Route map
│   ├── hooks.md              # Hook registry
│   ├── plugins.md            # Plugin registry
│   ├── entities.md           # Entity map
│   └── .generated-at         # Generation timestamp
├── DEPENDENCY_GRAPH.md       # Auto-generated cross-references
└── FEATURE_MAP.md            # Auto-generated feature overview
```

The `semantic-docs` and `discover` skills automatically use this documentation when available.

<details>
<summary><strong>Structural Index</strong> — automated Drupal structural awareness</summary>

### Overview

The structural index is a script-generated **Layer 2** that sits between human-authored semantic docs and raw codebase searches:

```
Layer 3: Semantic docs       (human-authored, business "why")
Layer 2: Structural index    (script-generated, Drupal-aware "what" + "how connected")
Layer 1: Raw codebase        (Glob/Grep/Read)
```

It leverages Drupal's highly declarative architecture (YAML configs, PHP attributes/annotations) to extract ~80% of the structural graph via targeted parse scripts — no external dependencies required.

### Generating the Index

Run the generator against your Drupal project:

```bash
# From the plugin directory:
skills/structural-index/scripts/generate-all.sh /path/to/drupal-project

# Or from within the Drupal project (CLAUDE_PROJECT_DIR set):
generate-all.sh
```

This produces 5 structural files + 2 cross-reference files:

| File | Parses | Contents |
|------|--------|----------|
| `structural/services.md` | `*.services.yml` | Service ID, class, injected dependencies, module, tags |
| `structural/routes.md` | `*.routing.yml` | Route name, path, controller/form, access, module |
| `structural/hooks.md` | `*.module` + `#[Hook]` | Hook name, implementation, type (procedural/attribute), file |
| `structural/plugins.md` | `@Block`, `#[Block]`, etc. | Plugin type, ID, class, module, file |
| `structural/entities.md` | `@ContentEntityType`, etc. | Entity type, ID, class, handlers, module |
| `DEPENDENCY_GRAPH.md` | Cross-references all above | Service dep chains, hook chains, hotspots, external boundaries |
| `FEATURE_MAP.md` | Tech specs + structural data | Feature overview with structural counts, hotspot scoring |

### Querying via Discover

Once generated, query structural data through the discover skill with prefix syntax:

```bash
discover service:entity_type.manager   # Find a service and its consumers
discover route:/admin/config           # Find routes by path
discover hook:node_presave             # Find all hook implementations
discover plugin:Block                  # Find block plugins
discover entity:node                   # Find entity type definitions
discover deps:AUTH                     # Blast radius / dependency analysis
discover impact:my_module              # What depends on this module
```

### Staleness Detection

A PostToolUse hook automatically warns when you edit a structural source file (e.g., `*.services.yml`, `*.routing.yml`, `*.module`, or PHP files with plugin annotations). The `prime.sh` session primer also shows a staleness warning when source files are newer than the index.

Run `check-staleness.sh` for a full report, or regenerate with `generate-all.sh`.

### YAML Parsing Approach

The generators use grep/sed state machines — no Python or `yq` dependency. This handles the ~95% case for Drupal's consistently structured YAML. The `IN_SERVICES` state tracker ensures only entries under the `services:` top-level key are parsed (ignoring `parameters:` sections).

### Agent Integration

All three agents are aware of the structural index:

- **drupal-builder**: Checks `discover deps:FEATURE` before multi-file changes, reviews hotspots
- **drupal-reviewer**: Validates structural impact (step 6 in validation workflow), flags changes to hotspot services without consumer checks
- **drupal-verifier**: Can verify structural index matches actual codebase state

### Supported Docroot Layouts

The generators automatically detect `web/`, `www/`, and top-level `modules/` directory layouts.

</details>

<details>
<summary><strong>Evaluation</strong> — semantic docs impact on AI agent performance</summary>

### Setup

Tested how a one-line prompt hint ("read `docs/semantic/00_BUSINESS_INDEX.md` before exploring code") affects AI agent response quality, speed, and cost on real developer questions.

- **Model**: Claude Sonnet
- **Method**: Same question asked twice per project — once without hint, once with
- **Scope**: 8 questions across 6 Drupal projects (D9/D10/D11, 6-43 custom modules each)
- **Agent**: Read-only with file exploration tools, two runs to measure variance

### Results

| # | Question Type | Without | With | Speed Delta | Cost Delta |
|---|--------------|---------|------|-------------|------------|
| 1 | Status overview | 20.2s | 35.0s | +73% slower | +23% |
| 2 | Hook/service tracing | 86.0s | 85.4s | ~same | ~same |
| 3 | Debugging (find function) | 25.5s | 28.1s | ~same | +45% |
| 4 | Scope new feature | 53.2s | 58.4s | ~same | ~same |
| 5 | Feature status check | 78.3s | 24.1s | **69% faster** | **53% cheaper** |
| 6 | Module inventory | 64.6s | 88.8s | +37% slower | +8% |
| 7 | Impact analysis | 37.2s | 31.2s | 16% faster | +12% |
| 8 | Onboarding overview | 60.4s | 19.3s | **68% faster** | **69% cheaper** |

**Totals across 2 runs:**

| Metric | Without | With | Delta |
|--------|---------|------|-------|
| Time (Run 1) | 509.5s | 272.9s | **-46% faster** |
| Time (Run 2) | 425.4s | 370.3s | **-13% faster** |
| Cost (Run 2) | $1.033 | $0.891 | **-14% cheaper** |
| Output tokens | 7,074 | 8,196 | +16% more detail |

### Where semantic docs help most

- **Broad questions**: "what features exist?", "project overview", "feature status" — 30-80s saved
- Agent reads the business index once instead of grep-exploring dozens of files
- Answers include business context, known limitations, and architecture details that grep can't surface

**Quality examples:**
- Onboarding question found 4 content types without hint, **7 with hint** (including role-gated private types)
- Feature status question included "Known Limitations" and "What's Not Built Yet" sections

### Where they don't help

- **Narrow grep-friendly questions**: "where is function X?" — grep finds it in seconds regardless
- **Deep source-code tracing**: "what hooks touch X?" — agent must read actual PHP regardless
- **Small-surface-area questions**: theme with 5 preprocess functions — no index needed
- **Debugging**: "X is broken, find it" — needs code-level tracing, not docs

### When to prime vs. skip

| Prime (`/drupal-prime`) | Skip priming |
|------------------------|--------------|
| "What's the status of X?" | "Where is function X?" |
| "Overview for a new dev" | "What hooks touch X?" |
| "List all modules/features" | "X is broken, find it" |
| "What would I need to change?" | Theme/template questions |
| "Scope a new feature" | "Trace this execution flow" |

**Rule of thumb**: If the answer requires knowing about things across many files, semantic docs win big. If the answer lives in one specific file, grep is just as fast.

### Cost analysis

With hint is 14% cheaper despite reading 41% more total tokens, because fewer tool-use turns (reads index then answers, vs. grep-read-grep-read-answer cycles) and cache reads replace expensive cache creation.

</details>

## License

MIT
