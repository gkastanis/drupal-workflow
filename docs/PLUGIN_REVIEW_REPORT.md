# drupal-workflow Plugin Review Report

**Plugin:** drupal-workflow v1.8.0
**Author:** Zorz
**License:** MIT
**Review Date:** 2026-03-14

---

## Executive Summary

The drupal-workflow plugin is a mature, production-ready Claude Code plugin for Drupal 10/11 development. It delivers 16 skills, 4 agents, 10 commands, and 5 hook events with 28+ supporting scripts. The architecture is built on a novel three-layer documentation system (raw code, structural index, semantic docs) that has been evaluated on 6 real-world Drupal projects and shown to deliver a **+61% speed improvement** and **+19% cost reduction** compared to baseline AI-assisted development.

**Overall Rating: A+ (Production-Ready)**

---

## 1. Architecture Overview

### Three-Layer Documentation System

The plugin's core innovation is a layered approach to codebase understanding:

```
Layer 3: Semantic docs       (AI-generated, business "why")
Layer 2: Structural index    (script-generated, Drupal-aware "what" + "how connected")
Layer 1: Raw codebase        (Glob/Grep/Read)
```

**Layer 1 (Raw Codebase):** Standard file search and reading. Always available.

**Layer 2 (Structural Index):** Deterministic bash scripts parse Drupal's declarative YAML (`*.services.yml`, `*.routing.yml`, `*.permissions.yml`) and PHP annotations/attributes to produce 9 structural index files + JSON schemas + 2 cross-reference files. No external dependencies (grep/sed state machines). Auto-regenerates on SessionStart when source files change.

**Layer 3 (Semantic Docs):** The `@semantic-architect` agent reads Layer 2 + source code to produce business index, tech specs with Logic IDs, and business schemas. This is the "business why" layer that maps features to code.

**CLAUDE.md Hint:** A compact pointer injected into the project's CLAUDE.md that tells the agent "semantic docs exist, read them first." This hint alone drives the bulk of the speed improvement (+61%) — docs without the hint perform only marginally better than baseline (+12%).

### Pipeline Flow

```
/drupal-bootstrap
  └── /drupal-refresh (Layer 2: structural index, ~10-30s)
        └── /drupal-semantic init (Layer 3: semantic docs, 5-15 min)
              └── /drupal-semantic inject (CLAUDE.md hint, <1s)
```

---

## 2. Component Inventory

### 2.1 Skills (16)

| # | Skill | Type | Description |
|---|-------|------|-------------|
| 1 | `drupal-rules` | Core | Code quality, security, services, testing verification rules |
| 2 | `drupal-testing` | Core | Practical testing: curl smoke tests, drush eval, test scripts |
| 3 | `drupal-service-di` | Knowledge | Service definitions, dependency injection patterns |
| 4 | `drupal-entity-api` | Knowledge | Field types, entity CRUD, view modes, access control handlers |
| 5 | `drupal-caching` | Knowledge | Cache bins, tags, CacheableMetadata, lazy builders, invalidation |
| 6 | `drupal-hook-patterns` | Knowledge | OOP hooks (D11), form alters, install/update hooks, legacy bridges |
| 7 | `drupal-security-patterns` | Knowledge | OWASP prevention, access control, input sanitization, XSS |
| 8 | `drupal-coding-standards` | Knowledge | PHPCS, PHPStan, naming conventions, code style |
| 9 | `drupal-conventions` | Knowledge | Translations, CSS conventions, error handling |
| 10 | `drupal-config-management` | Knowledge | Config split, config ignore, config readonly, environments |
| 11 | `twig-templating` | Knowledge | Twig patterns, filters, theme suggestions, components |
| 12 | `verification-before-completion` | Gate | Prevents untested claims; validates work before marking done |
| 13 | `semantic-docs` | Navigation | Business-logic-to-code mappings via Logic IDs and feature codes |
| 14 | `discover` | Navigation | Docs-first discovery with structural query prefixes |
| 15 | `structural-index` | Generation | Auto-generated structural awareness from Drupal declarative configs |
| 16 | `writing-plans` | Workflow | Comprehensive implementation plans for sub-agents |

### 2.2 Agents (4)

| Agent | Model | Purpose | Skills Loaded |
|-------|-------|---------|---------------|
| `drupal-builder` | opus | Full-stack implementation: modules, themes, config, migrations | 14 skills including config-management |
| `drupal-reviewer` | sonnet | Architecture review, security audit, coding standards | 14 skills including config-management |
| `drupal-verifier` | sonnet | Implementation verification via drush eval, curl, config checks | drupal-testing + structural-index |
| `semantic-architect` | (default) | Generates Layer 3 semantic docs from Layer 2 + source code | semantic-docs + structural-index |

### 2.3 Commands (10)

| Command | Category | Description |
|---------|----------|-------------|
| `/drupal-bootstrap` | Setup | Auto-detect project state, run 3-step pipeline |
| `/drupal-status` | Status | Check documentation, structural index, staleness |
| `/drupal-prime` | Debug | Load full project context (~2500 tokens) |
| `/drupal-refresh` | Maintenance | Regenerate structural index + update CLAUDE.md hint |
| `/drupal-semantic` | Documentation | 7 subcommands: init, feature, index, schema, status, validate, inject |
| `/drupal-test` | Testing | Run verification tests (services, entities, routes, config) |
| `/drupal-verify` | Verification | Smoke tests and drush checks |
| `/drupal-blast-radius` | Analysis | Dependency and blast radius analysis for a feature |
| `/implement` | Development | Implement changes across all affected files |
| `/verify-changes` | Development | Verify code changes are complete and consistent |

### 2.4 Hooks (5 events)

| Event | Matcher | Script | Purpose |
|-------|---------|--------|---------|
| `SessionStart` | (none) | inline echo | Displays activation message with available commands |
| `SessionStart` | (none) | inline + `generate-all.sh` | Auto-regenerates structural index if stale |
| `PreToolUse` | `Read\|Grep` | `block-sensitive-files.sh` | Blocks access to `settings.php`, `.env`, credentials |
| `PostToolUse` | `Edit\|Write` | `php-lint-on-save.sh` | Runs `php -l` lint on modified PHP files |
| `PostToolUse` | `Edit\|Write` | `staleness-check.sh` | Advisory warning when structural source files edited |
| `SubagentStart` | `.*` | `subagent-context-inject.sh` | Injects Drupal context into spawned sub-agents |
| `TaskCompleted` | `.*` | `teammate-quality-gate.sh` | Quality gate checks on completed work |

### 2.5 Scripts (28+)

**Root scripts (`scripts/`):**
- `block-sensitive-files.sh` — PreToolUse security gate
- `php-lint-on-save.sh` — PostToolUse PHP syntax checker
- `staleness-check.sh` — PostToolUse structural staleness advisor
- `subagent-context-inject.sh` — SubagentStart context injection
- `teammate-quality-gate.sh` — TaskCompleted quality gate
- `inject-claude-md.sh` — Injects `## Codebase` section into CLAUDE.md
- `validate-tech-specs.sh` — Validates/fixes tech spec filenames and frontmatter
- `lib/hook-utils.sh` — Shared utilities for hook scripts

**Structural index scripts (`skills/structural-index/scripts/`):**
- `generate-all.sh` — Orchestrator: runs all generators in sequence
- `generate-service-graph.sh` — Parses `*.services.yml`
- `generate-route-map.sh` — Parses `*.routing.yml`
- `generate-hook-registry.sh` — Parses `*.module` and `#[Hook]` attributes
- `generate-plugin-registry.sh` — Parses `@Block`, `#[Block]`, etc.
- `generate-entity-map.sh` — Parses `@ContentEntityType`, etc.
- `generate-entity-schemas.sh` — Parses `field.storage.*.yml` + `field.field.*.yml`
- `generate-base-fields.sh` — Parses PHP `baseFieldDefinitions()`
- `generate-permission-registry.sh` — Parses `*.permissions.yml`
- `generate-method-index.sh` — Indexes public methods in Service/Controller/Form
- `generate-dependency-graph.sh` — Cross-references all structural data
- `generate-feature-map.sh` — Produces feature overview with hotspot scoring
- `check-staleness.sh` — Full staleness report

### 2.6 Evaluation Suite (7 scripts, 315 assertions)

| Script | Assertions | Scope |
|--------|-----------|-------|
| `eval-skills.py` | 172 | Content quality, key terms, imperatives across 16 skills |
| `eval-agents.py` | 60 | Structure, frontmatter, skills across 4 agents |
| `eval-hooks.py` | 20 | Hooks system integrity |
| `eval-semantic-architect.py` | 25 | Tech spec output quality (behavioral) |
| `eval-builder-agent.py` | 20 | Skill application (behavioral) |
| `eval-reviewer-agent.py` | 15 | Issue detection (behavioral) |
| `eval-verifier-agent.py` | 10 | Verification output (behavioral) |

### 2.7 Interactive Playgrounds (3)

- `playground-workflow.html` — Visual workflow documentation
- `playground-discover.html` — Interactive discover query routing demo
- `playground-agents.html` — Agent team, skills, and hooks visualization

---

## 3. How the Pieces Fit Together

```
                    ┌─────────────────────────┐
                    │    /drupal-bootstrap     │
                    │    (entry point)         │
                    └───────────┬─────────────┘
                                │
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                   ▼
   ┌──────────────────┐ ┌────────────────┐ ┌──────────────────┐
   │  /drupal-refresh  │ │/drupal-semantic│ │  CLAUDE.md hint   │
   │  (Layer 2)        │ │  init          │ │  (auto-injected)  │
   │                   │ │  (Layer 3)     │ │                   │
   │  13 bash scripts  │ │  @semantic-    │ │  Compact pointer  │
   │  parse YAML/PHP   │ │  architect     │ │  to docs          │
   └───────┬──────────┘ └──────┬─────────┘ └────────┬──────────┘
           │                   │                     │
           ▼                   ▼                     ▼
   ┌────────────────────────────────────────────────────────────┐
   │                 Development Agents                         │
   │  @drupal-builder  @drupal-reviewer  @drupal-verifier       │
   │                                                            │
   │  ┌─────────────────────────────────────────────────────┐   │
   │  │              15 Knowledge Skills                    │   │
   │  │  drupal-rules, caching, entity-api, security, ...   │   │
   │  └─────────────────────────────────────────────────────┘   │
   └──────────────────────┬─────────────────────────────────────┘
                          │
   ┌──────────────────────┼──────────────────────┐
   ▼                      ▼                      ▼
┌──────────┐    ┌──────────────────┐    ┌─────────────────┐
│ PreToolUse│    │   PostToolUse    │    │  SubagentStart  │
│ Security  │    │ PHP lint +       │    │ Context inject  │
│ gate      │    │ staleness check  │    │                 │
└──────────┘    └──────────────────┘    └─────────────────┘
```

**Lifecycle:**
1. Session starts → activation banner + auto-regen if stale
2. Developer runs `/drupal-bootstrap` → generates structural index, nudges semantic docs
3. Developer runs `/drupal-semantic init` → AI generates tech specs, injects CLAUDE.md hint
4. During development → agents use skills + structural data; hooks enforce quality
5. After implementation → `@drupal-verifier` validates; `verification-before-completion` gates claims

---

## 4. Strengths

### Architecture
- **Layered documentation** is genuinely innovative — separating deterministic structural parsing from AI-generated business context creates a reliable foundation
- **Deterministic generation** via bash scripts (no AI drift) for Layer 2 means reproducible, auditable structural data
- **No external dependencies** — grep/sed state machines handle Drupal's YAML without requiring Python, yq, or node

### Security
- **Sensitive file blocking** is a strong default — prevents accidental exposure of `settings.php`, `.env`, and credential files
- **PHP lint on save** catches syntax errors immediately
- **OWASP-focused security skill** covers the Drupal-specific attack surface

### Developer Experience
- **Three-step onboarding** (`bootstrap` → `semantic init` → work) is clear and progressive
- **Staleness detection** with auto-regeneration eliminates stale documentation problems
- **`discover` skill** with prefix syntax (`service:`, `hook:`, `deps:`) provides fast structured queries
- **Playground pages** offer visual, interactive documentation

### Evaluation
- **315 automated assertions** across 7 eval scripts provide regression safety
- **Real-world evaluation** on 6 Drupal projects with measured speed/cost/quality improvements
- **Behavioral evals** test agent skill application, not just file structure

### Context Efficiency
- **~2,500 tokens** for full project priming (~1.2% of a 200k context window)
- **34 lines of code awareness per token** is exceptionally efficient

---

## 5. Areas for Improvement

### Coverage Gaps
- **No contrib module guides** — Views, Commerce, Rules, Paragraphs, and other major contrib modules lack dedicated skills
- **No D9 support** — While D10/D11 is the focus, migration guidance from D9 would help teams upgrading
- **No multilingual patterns** — Content translation, interface translation, and language negotiation are missing
- **No REST/JSON:API skill** — API-first Drupal development is increasingly common

### Agent Design
- **No performance optimization agent** — Caching skill exists, but a dedicated agent for query optimization, database indexing, and profiling would add value
- **No migration agent** — D9 → D10 → D11 upgrade path guidance would be useful for teams maintaining legacy sites

### Technical
- **YAML parsing limitations** — grep/sed state machines handle ~95% of cases but may miss edge cases in complex YAML (nested services, multiline values)
- **No Windows native support** — Bash dependency limits usage to macOS/Linux/WSL
- **Hook timeouts** — Some hooks have 15s timeouts which could slow down workflows on large projects

### Documentation
- **No dedicated deployment guide** — README covers installation but lacks detailed configuration, troubleshooting, and extension documentation (this report addresses that gap)
- **Eval results only in README** — Could benefit from a standalone eval report with methodology details

---

## 6. Claude Code Plugin Best Practices Comparison

| Best Practice | Status | Notes |
|--------------|--------|-------|
| `plugin.json` with name, version, description | Present | Clean, minimal metadata |
| `marketplace.json` with owner, source | Present | Correctly located in `.claude-plugin/` |
| Skills with YAML frontmatter | All 16 present | Fixed in v1.7.0 (7 had format issues) |
| Agent definitions with frontmatter | All 4 present | Model, tools, skills properly declared |
| Commands with description + allowed-tools | All 10 present | Clear purpose and tool scoping |
| Hooks with proper matchers | Present | `once` flags, matchers, timeouts all correct |
| No hardcoded paths | Fixed in v1.7.0 | `$PLUGIN_DIR` → `$CLAUDE_PLUGIN_ROOT` |
| Evaluation/testing | 315 assertions | Comprehensive coverage |
| README documentation | 360+ lines | Thorough with eval results |
| Changelog | Present | Semantic versioning, detailed entries |
| License | MIT | Declared in plugin.json |

**Grade: A** — Follows all established best practices with comprehensive evaluation coverage.

---

## 7. Version History Summary

| Version | Date | Highlights |
|---------|------|------------|
| 1.0.0 | 2026-03-09 | Initial release: 14 skills, 3 agents, 4 commands, quality hooks |
| 1.0.1 | 2026-03-10 | Fix hook matchers, marketplace.json schema |
| 1.1.0 | 2026-03-12 | Structural index (9 generators), staleness detection, agent integration |
| 1.2.0 | 2026-03-12 | 5 new commands: bootstrap, prime, refresh, status, blast-radius |
| 1.3.0 | 2026-03-13 | Entity schema generation from config YAML |
| 1.4.0 | 2026-03-13 | Base fields, permission registry, method index generators |
| 1.5.0 | 2026-03-13 | Semantic architect agent, `/drupal-semantic` with 5 subcommands |
| 1.6.0 | 2026-03-13 | CLAUDE.md auto-injection, tech spec validator, +61% speed eval |
| 1.7.0 | 2026-03-14 | Eval framework (315 assertions), fix `$PLUGIN_DIR`, skill improvements |
| 1.8.0 | 2026-03-14 | 16 skills (+config-management), P1/P2 architecture fixes, feature map fixes |

---

## 8. Conclusion

The drupal-workflow plugin represents a sophisticated, well-tested approach to AI-assisted Drupal development. Its three-layer architecture is its standout feature — providing deterministic structural awareness that AI agents can reliably build upon. The evaluation data (61% speed improvement, 19% cost reduction) validates the approach across real-world projects.

The plugin is production-ready for Drupal 10/11 custom module development teams. The main areas for growth are contrib module coverage, multilingual support, and API-first development patterns.
