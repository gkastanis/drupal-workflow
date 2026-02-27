# drupal-workflow

A comprehensive Claude Code plugin for Drupal development. Provides 14 skills, 3 specialized agents, 4 commands, and quality-gate hooks for testing, dependency injection, entity API, caching, security, and verification.

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

## Skills (14)

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
| **discover** | Docs-first codebase discovery. Use before Glob/Grep to get Logic IDs and file paths from semantic documentation. |
| **writing-plans** | Write comprehensive implementation plans for sub-agents or complex tasks. |

## Agents (3)

Three focused agents covering the full Drupal development lifecycle: build, review, verify.

| Agent | Description |
|-------|-------------|
| **drupal-builder** | Full-stack implementation: modules, themes, config, migrations, performance. |
| **drupal-reviewer** | Architecture, security audit, coding standards, and test writing. |
| **drupal-verifier** | Implementation verification via ddev drush eval, curl smoke tests, config checks. |

## Commands (4)

Slash commands for common development workflows.

| Command | Usage | Description |
|---------|-------|-------------|
| `/drupal-test` | `/drupal-test service` | Run Drupal verification tests (services, entities, routes, config). |
| `/drupal-verify` | `/drupal-verify` | Verify implementation using smoke tests and drush checks. |
| `/implement` | `/implement` | Implement changes across all affected files with validation. |
| `/verify-changes` | `/verify-changes` | Verify code changes are complete and consistent. |

## Hooks

The plugin registers hooks for quality gates:

| Event | Trigger | Action |
|-------|---------|--------|
| **SessionStart** | Plugin loaded | Displays activation message with available commands. |
| **PreToolUse** | `Read` or `Grep` | Blocks access to sensitive files (`settings.php`, `.env`, credentials). |
| **PostToolUse** | `Edit` or `Write` | Runs `php -l` lint on modified PHP files (`.php`, `.module`, `.inc`, `.install`, `.theme`). |
| **SubagentStart** | Any subagent | Injects Drupal context (version detection, agent memory paths). |
| **TaskCompleted** | Task marked done | Runs quality gate checks on completed work. |

## Project Structure

```
drupal-workflow/
├── .claude-plugin/
│   └── plugin.json          # Plugin metadata
├── skills/                   # 14 Drupal development skills
├── agents/                   # 3 specialized agents
├── commands/                 # 4 slash commands
├── hooks/
│   └── hooks.json            # Hook event definitions
├── scripts/                  # Hook implementation scripts
│   ├── block-sensitive-files.sh
│   ├── php-lint-on-save.sh
│   ├── subagent-context-inject.sh
│   ├── teammate-quality-gate.sh
│   └── lib/
│       └── hook-utils.sh
└── README.md
```

## Semantic Documentation (Optional)

For large Drupal projects, create `docs/semantic/` in your project root to enable logic-to-code mapping:

```
docs/semantic/
├── 00_BUSINESS_INDEX.md      # Master feature index
├── tech/*.md                 # Logic-to-code mappings
└── schemas/*.json            # Entity schemas
```

The `semantic-docs` and `discover` skills will automatically use this documentation when available.

## License

MIT
