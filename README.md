# drupal-workflow

A Claude Code plugin for Drupal development with live workflow optimization. Provides 18 skills, 4 specialized agents, 10 commands, behavioral evals, session analysis, and the Magic Loop Autopilot — a live policy engine that classifies tasks, tracks session behavior, and nudges toward proven high-productivity patterns.

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

## Skills (18)

Skills provide domain knowledge that Claude can consult during development.

| Skill | Description |
|-------|-------------|
| **drupal-brainstorming** | Explore requirements and design options before implementing. Entity design, service architecture, hook/event strategy. |
| **drupal-delegation** | Execute plans by dispatching specialized agents in parallel. Structured agent dispatch with tracking. |
| **drupal-rules** | Core development rules: code quality, security, services, testing. Auto-consulted when writing Drupal code. |
| **drupal-testing** | Practical testing patterns: curl smoke tests, drush eval, test scripts. Verifies implementations actually work. |
| **drupal-service-di** | Service definitions, dependency injection patterns, and interface design. |
| **drupal-entity-api** | Field types, entity CRUD, view modes, access control handlers, and content modeling. |
| **drupal-caching** | Cache bins, tags, contexts, CacheableMetadata, lazy builders, invalidation, and external caching. |
| **drupal-hook-patterns** | OOP hooks (Drupal 11), form alters, entity hooks, install/update hooks, and legacy bridges. |
| **drupal-security-patterns** | OWASP prevention patterns, access control, input sanitization, XSS protection. |
| **drupal-coding-standards** | PHPCS, PHPStan, naming conventions, and code style enforcement. |
| **drupal-conventions** | Translations, CSS conventions, error handling patterns. |
| **drupal-config-management** | Config split, config ignore, config readonly, environments, import/export workflows. |
| **twig-templating** | Twig template patterns, filters, theme suggestions, and component architecture. |
| **verification-before-completion** | Gate function preventing untested claims. Validates work before marking complete. |
| **semantic-docs** | Navigate business-logic-to-code mappings in `docs/semantic/`. Search by Logic ID, feature code, or entity schema. |
| **discover** | Docs-first codebase discovery. Use before Glob/Grep to get Logic IDs and file paths from semantic documentation. Now supports structural queries (`service:`, `hook:`, `deps:`, etc.). |
| **structural-index** | Auto-generated structural awareness for Drupal projects. Parses `*.services.yml`, `*.routing.yml`, hooks, plugins, and entity types to build dependency graphs and feature maps. |
| **writing-plans** | Write comprehensive implementation plans for sub-agents or complex tasks. |

## Agents (4)

Four focused agents covering the full Drupal development lifecycle: build, review, verify, document.

| Agent | Description |
|-------|-------------|
| **drupal-builder** | Full-stack implementation: modules, themes, config, migrations, performance. |
| **drupal-reviewer** | Architecture, security audit, coding standards, and test writing. |
| **drupal-verifier** | Implementation verification via ddev drush eval, curl smoke tests, config checks. |
| **semantic-architect** | Generates semantic docs (Layer 3): business index, tech specs with Logic IDs, business schemas. |

## Commands (10)

Slash commands for common development workflows.

| Command | Usage | Description |
|---------|-------|-------------|
| `/drupal-test` | `/drupal-test service` | Run Drupal verification tests (services, entities, routes, config). |
| `/drupal-verify` | `/drupal-verify` | Verify implementation using smoke tests and drush checks. |
| `/implement` | `/implement` | Implement changes across all affected files with validation. |
| `/verify-changes` | `/verify-changes` | Verify code changes are complete and consistent. |
| `/drupal-bootstrap` | `/drupal-bootstrap` | Auto-detect project state, run the 3-step pipeline as needed. |
| `/drupal-prime` | `/drupal-prime` | Load full project overview into session (~2500 tokens, debug/overview). |
| `/drupal-refresh` | `/drupal-refresh` | Regenerate structural index and update CLAUDE.md hint. |
| `/drupal-status` | `/drupal-status` | Check documentation, structural index, and staleness status. |
| `/drupal-blast-radius` | `/drupal-blast-radius AUTH` | Analyze dependencies and blast radius for a feature or module. |
| `/drupal-semantic` | `/drupal-semantic init` | Generate/manage semantic docs. Subcommands: `init`, `feature FEAT`, `index`, `schema ENTITY`, `status`, `validate [--fix]`, `inject`. |

## Hooks

The plugin registers hooks for quality gates:

| Event | Trigger | Action |
|-------|---------|--------|
| **SessionStart** | Plugin loaded | Displays activation message with available commands. Auto-regenerates structural index if stale. |
| **PreToolUse** | `Read` or `Grep` | Blocks access to sensitive files (`settings.php`, `.env`, credentials). |
| **PostToolUse** | `Edit` or `Write` | Runs `php -l` lint on modified PHP files. Advisory staleness warning when structural source files are edited. |
| **SubagentStart** | Any subagent | Injects Drupal context (version detection, agent memory paths). |
| **TaskCompleted** | Task marked done | Runs quality gate checks on completed work. |

## Project Structure

```
drupal-workflow/
├── .claude-plugin/
│   └── plugin.json          # Plugin metadata
├── skills/                   # 16 Drupal development skills
│   ├── structural-index/     # Auto-generated structural awareness
│   │   └── scripts/          # 13 generator + check scripts
│   └── ...                   # 15 other skills
├── agents/                   # 4 specialized agents
├── commands/                 # 10 slash commands
├── hooks/
│   └── hooks.json            # Hook event definitions
├── scripts/                  # Hook + utility scripts
│   ├── block-sensitive-files.sh
│   ├── php-lint-on-save.sh
│   ├── staleness-check.sh    # PostToolUse structural staleness advisory
│   ├── subagent-context-inject.sh
│   ├── teammate-quality-gate.sh
│   ├── inject-claude-md.sh   # Add/update ## Codebase section in CLAUDE.md
│   ├── validate-tech-specs.sh # Check/fix tech spec filenames and frontmatter
│   └── lib/
│       └── hook-utils.sh
└── README.md
```

## Workflow

Documentation is generated in three layers. Each layer builds on the previous one.

```
Step 1: /drupal-refresh          → Structural index (Layer 2, deterministic bash scripts)
Step 2: /drupal-semantic init    → Semantic docs (Layer 3, AI-generated tech specs + business index)
Step 3: /drupal-semantic inject  → CLAUDE.md hint (compact pointer that drives +61% speed improvement)
```

**Step 1** parses `*.services.yml`, `*.routing.yml`, hooks, plugins, and entities via bash scripts. No AI involved. Produces `docs/semantic/structural/`.

**Step 2** spawns the `@semantic-architect` agent per feature to read structural data + source code and produce tech specs with Logic IDs. Produces `docs/semantic/tech/` and `docs/semantic/00_BUSINESS_INDEX.md`.

**Step 3** reads the generated tech specs and injects a compact `## Codebase` section into the project's CLAUDE.md — feature counts, Logic ID totals, and CODE:Name pairs. This is the prompt hint that tells the agent "these docs exist, read them first." Step 3 runs automatically at the end of Step 2, but can also be run standalone.

### Getting started

| Scenario | Command |
|----------|---------|
| Fresh project (no docs) | `/drupal-bootstrap` (runs Step 1, nudges you to run Steps 2-3) |
| Docs exist, check staleness | `/drupal-status` then `/drupal-refresh` if needed |
| Quick session, docs are fresh | CLAUDE.md hint handles it automatically. `/drupal-prime` for full debug dump. |
| Just update CLAUDE.md counts | `/drupal-semantic inject` |
| Validate tech spec format | `/drupal-semantic validate` (add `--fix` to auto-repair) |

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
├── schemas/*.json            # Config field schemas (auto-generated per bundle)
├── schemas/*.base-fields.json # Base field schemas (auto-generated from PHP)
├── schemas/*.business.json   # Business schemas (AI-authored: rules, relationships)
├── structural/               # Auto-generated by structural-index
│   ├── services.md           # Service graph
│   ├── routes.md             # Route map
│   ├── hooks.md              # Hook registry
│   ├── plugins.md            # Plugin registry
│   ├── entities.md           # Entity map (with Fields column)
│   ├── schemas.md            # Entity schema summary
│   ├── base-fields.md        # Base field registry
│   ├── permissions.md        # Permission registry
│   ├── methods.md            # Method index (Service/Controller/Form)
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
Layer 3: Semantic docs       (AI-generated, business "why")
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

This produces 9 structural files + per-bundle/entity JSON schemas + 2 cross-reference files:

| File | Parses | Contents |
|------|--------|----------|
| `structural/services.md` | `*.services.yml` | Service ID, class, injected dependencies, module, tags |
| `structural/routes.md` | `*.routing.yml` | Route name, path, controller/form, access, module |
| `structural/hooks.md` | `*.module` + `#[Hook]` | Hook name, implementation, type (procedural/attribute), file |
| `structural/plugins.md` | `@Block`, `#[Block]`, etc. | Plugin type, ID, class, module, file |
| `structural/entities.md` | `@ContentEntityType`, etc. | Entity type, ID, class, handlers, fields, module |
| `structural/schemas.md` | `field.storage.*.yml`, `field.field.*.yml` | Per-bundle field counts, references, lists |
| `structural/base-fields.md` | PHP `baseFieldDefinitions()` | Base field types, settings, entity metadata |
| `structural/permissions.md` | `*.permissions.yml` | Permission names, titles, modules, restrictions |
| `structural/methods.md` | `src/Service/`, `src/Controller/`, `src/Form/` | Public methods, return types, line numbers |
| `schemas/*.json` | Config YAML | Field types, labels, cardinality, target types/bundles, allowed values |
| `schemas/*.base-fields.json` | PHP `baseFieldDefinitions()` | Entity metadata, base field types, settings, cardinality |
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
discover schema:node                   # Show field schemas for entity bundles
discover perm:administer               # Find permissions
discover method:Timesheet              # Find methods related to timesheets
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

### Setup (v4)

Branch-based eval comparing three variants to measure whether semantic docs improve AI agent responses — and whether the agent discovers them on its own or needs a hint.

- **Model**: Claude Sonnet (agent) + Haiku (automated judge) + Sonnet & Opus (manual quality review)
- **Variants**: 3 — baseline (no docs), with_docs (docs present, no hint), with_hint (docs + prompt guidance)
- **Scope**: 9 questions across 6 Drupal projects (D9/D10/D11, 6-43 custom modules each)
- **Agent**: Read-only with file exploration tools, 2 runs per variant (54 total agent calls)
- **Bias control**: Randomized variant order per question, prompt caching disabled
- **Quality**: LLM-as-judge scoring (completeness, accuracy, business context, actionability) + manual side-by-side review by Sonnet and Opus

### Results

| # | Question Type | Project | Baseline | +Docs | +Hint | Hint Speed | Hint Cost |
|---|--------------|---------|----------|-------|-------|-----------|----------|
| 1 | Onboarding overview | technocan | 71.5s | 73.9s | 31.4s | **+56%** | **+35%** |
| 2 | Status overview | elvial | 41.0s | 42.0s | 24.0s | **+42%** | **+49%** |
| 3 | Commerce feature inventory | candia-b2b | 128.9s | 105.2s | 56.8s | **+56%** | **+23%** |
| 4 | Cross-module impact | candia-b2b | 107.5s | 126.8s | 38.9s | **+64%** | -10% |
| 5 | Scope new feature | elvial | 148.3s | 98.8s | 33.0s | **+78%** | **+29%** |
| 6 | Architecture / data model | hellasfin | 127.2s | 113.7s | 37.2s | **+71%** | +5% |
| 7 | Architecture overview | istolab | 113.8s | 62.8s | 29.3s | **+74%** | **+40%** |
| 8 | Service dependency chain | candia-b2b | 104.9s | 84.3s | 108.1s | -3% | +5% |
| 9 | Access control mapping | technocan | 164.3s | 178.7s | 34.6s | **+79%** | **+17%** |

**Totals (averaged across 2 runs):**

| Metric | Baseline | +Docs | +Hint | Docs Δ | Hint Δ |
|--------|----------|-------|-------|--------|--------|
| Time | 1007.5s | 886.1s | 393.3s | +12% faster | **+61% faster** |
| Cost | $2.19 | $1.99 | $1.77 | +9% cheaper | **+19% cheaper** |
| Quality | 3.38/5 | 3.47/5 | 3.49/5 | +0.09 | +0.11 |

### Quality (manual review by Sonnet + Opus)

Both reviewers evaluated all 9 questions side-by-side across all 3 variants:

| Question Type | Winner | Notes |
|--------------|--------|-------|
| Onboarding overview | **with_hint** | Baseline mischaracterizes project; hint provides audience mapping, DB-only roles |
| Status overview | baseline (weak) | All similar; baseline has recent ticket detail |
| Commerce features | **with_hint** | Finds edge cases: disabled VAT, ERP limits, min-order qty |
| Cross-module impact | baseline | Baseline discovers double-discount gotcha from code |
| Scope new feature | **with_hint** | Adds path processor insight, structured checklist |
| Architecture / data model | tie | All three strong |
| Architecture overview | **with_hint** | Best dependency tree, domain context |
| Service dependency chain | **baseline** | Finds 8 consumers vs 5-6; raw code tracing wins |
| Access control mapping | **with_hint** | Role matrix is superior to narrative lists |

**Tally**: with_hint wins 5/9, baseline wins 2/9, ties 2/9. with_docs wins 0/9.

### Key finding: docs without hint are nearly useless

The with_docs variant (docs present, agent not told) performs almost identically to baseline:
- Only +12% faster, +9% cheaper
- Agent sometimes discovers docs, sometimes doesn't — making results unpredictable
- **The hint does all the heavy lifting** (+61% speed, +19% cost, +0.11 quality)

### Where semantic docs help most

- **Onboarding / overview**: 56-74% faster, eliminates project mischaracterization
- **Architecture**: Clean dependency trees from docs vs grep-discovered spaghetti
- **Feature inventory / scoping**: Surfaces edge cases, operational constraints, business context
- Agent reads the business index once instead of grep-exploring dozens of files

### Where baseline still wins

- **Deep code tracing** (service dependency chains): Baseline found 8 consumers including \Drupal::service() anti-patterns; docs-based variants found 5-6
- **Blast radius with code-level gotchas**: Baseline discovered a double-discount bug risk that docs didn't capture
- **Recent activity questions**: git log provides the same context as docs

### When semantic docs help vs. when raw grep wins

| Semantic docs (CLAUDE.md hint) | Raw grep (no docs needed) |
|-------------------------------|--------------------------|
| "What's the status of X?" | "Trace this service dependency chain" |
| "Overview for a new dev" | "Where is function X?" |
| "List all modules/features" | "X is broken, find it" |
| "Scope a new feature" | "What hooks touch X?" |
| "What's the access control model?" | "Find all callers of this service" |

**Rule of thumb**: If the answer spans many files, semantic docs win big (+61% speed). If it requires exhaustive code-level tracing, raw grep is irreplaceable.

### Variance

with_hint produces the most consistent results across runs (avg stddev 4.5s vs 15.6s for baseline), making it more predictable for automated use (e.g., Slack bots answering developer questions).

</details>

## License

MIT
