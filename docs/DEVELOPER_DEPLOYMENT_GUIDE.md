# Developer Deployment Guide

**Plugin:** drupal-workflow v1.7.0
**Last Updated:** 2026-03-14

---

## Prerequisites

| Component | Version | Required |
|-----------|---------|----------|
| Claude Code CLI | Latest | Yes |
| Drupal | 10.x or 11.x | Yes |
| PHP | 8.2+ | Yes |
| DDEV | Latest stable | Yes |
| Bash | 4.0+ | Yes |
| grep/sed/awk | Standard | Yes (included on all Unix systems) |
| jq | 1.6+ | Recommended (for JSON parsing in hooks) |
| curl | Any | Required for smoke tests (usually pre-installed) |
| drush | 12+ | Required for verification (usually in DDEV) |

### Supported Platforms

- **macOS** — Fully supported (Intel and Apple Silicon)
- **Linux** — Fully supported (all distributions)
- **Windows** — Supported via WSL2 with DDEV
- **Windows native (CMD.exe)** — Not supported (bash dependency)

### Supported Drupal Project Layouts

The plugin auto-detects these docroot structures:

```
project/web/modules/custom/     # Standard Composer (most common)
project/www/modules/custom/     # Alternative docroot
project/modules/custom/         # Top-level modules (no docroot subdirectory)
```

---

## Installation

### Method 1: Local Plugin (Recommended for Development)

Best for testing, customization, and contributing.

```bash
# Clone the plugin
git clone https://github.com/gkastanis/drupal-workflow.git

# Run Claude Code with the plugin loaded
cd /path/to/your/drupal-project
claude --plugin-dir /path/to/drupal-workflow
```

On startup you should see:
```
DRUPAL WORKFLOW PLUGIN ACTIVE | Start: /drupal-bootstrap | Prime: /drupal-prime | Status: /drupal-status | Semantic: /drupal-semantic | Test: /drupal-test | Verify: /drupal-verify
```

### Method 2: Global Install (Teams)

For shared team usage across multiple projects.

```bash
# Clone to a standard location
git clone https://github.com/gkastanis/drupal-workflow.git /opt/claude-plugins/drupal-workflow

# Add a shell alias (~/.zshrc or ~/.bashrc)
alias claude-drupal='claude --plugin-dir /opt/claude-plugins/drupal-workflow'

# Use with any Drupal project
cd /path/to/drupal-project
claude-drupal
```

### Method 3: Claude Code Marketplace

When available in the Claude Code plugin marketplace:

```bash
# From within Claude Code settings:
# Settings → Plugins → Search "drupal-workflow" → Install
```

---

## Initial Setup

### Step 1: Bootstrap the Project

Run once per Drupal project:

```
/drupal-bootstrap
```

This does three things:
1. Detects your project structure (docroot layout, modules, config directory)
2. Generates the **structural index** (Layer 2) — parses YAML and PHP to create `docs/semantic/structural/`
3. Suggests running `/drupal-semantic init` if no semantic docs exist

Expected output:
```
STRUCTURAL INDEX: Generated (or auto-regenerated if stale)
Semantic docs (docs/semantic/tech/*.md): FOUND or NOT FOUND
CLAUDE.md hint: INJECTED or MISSING
```

### Step 2: Generate Semantic Documentation (Optional but Recommended)

For the full +61% speed improvement:

```
/drupal-semantic init
```

This spawns the `@semantic-architect` agent per feature to produce:
- `docs/semantic/00_BUSINESS_INDEX.md` — Master feature registry
- `docs/semantic/tech/CODE_01_Feature.md` — Logic ID tables per feature
- `docs/semantic/schemas/*.business.json` — Business rule schemas
- CLAUDE.md `## Codebase` hint — auto-injected at the end

**Time estimate:** 5-15 minutes depending on project size and number of custom modules.

### Step 3: Verify Setup

```
/drupal-status
```

Expected output when fully configured:
```
=== PROJECT STATUS ===
Structural index: FRESH
Semantic docs: FOUND (N tech specs, M Logic IDs)
CLAUDE.md hint: PRESENT
```

---

## Daily Workflow

### Quick Start (Docs Already Generated)

```
/drupal-status              # Check freshness
# If stale:
/drupal-refresh             # Regenerate structural index
```

The CLAUDE.md hint tells the agent where docs are. Skills auto-trigger based on context.

### Typical Development Session

```
# Ask the builder agent to implement something
@drupal-builder "Create a custom block plugin that displays recent articles"

# After implementation, review it
@drupal-reviewer "Review the RecentArticlesBlock plugin"

# Verify it actually works
@drupal-verifier "Verify the recent_articles_block plugin is registered and renders"

# Update semantic docs if significant changes were made
/drupal-semantic feature ARTICLE
```

### Available Commands Reference

| Command | When to Use |
|---------|-------------|
| `/drupal-bootstrap` | First time, or when project structure changes |
| `/drupal-status` | Start of a session, to check doc freshness |
| `/drupal-refresh` | After editing `*.services.yml`, `*.routing.yml`, or `*.module` files |
| `/drupal-prime` | When you want a full project overview (~2500 tokens) |
| `/drupal-semantic init` | First time, or after major feature additions |
| `/drupal-semantic feature FEAT` | After changing a specific feature |
| `/drupal-semantic status` | Check semantic doc coverage |
| `/drupal-semantic validate` | Validate tech spec format (add `--fix` to auto-repair) |
| `/drupal-semantic inject` | Manually update CLAUDE.md hint |
| `/drupal-test service` | Test service registration |
| `/drupal-verify` | Full implementation verification |
| `/drupal-blast-radius AUTH` | Analyze dependencies for a feature or module |
| `/implement` | Guided implementation across multiple files |
| `/verify-changes` | Verify recent changes are complete |

### Discover Queries

The `discover` skill supports structural query prefixes:

```
discover service:entity_type.manager   # Find a service and its consumers
discover route:/admin/config           # Find routes by path
discover hook:node_presave             # Find all hook implementations
discover plugin:Block                  # Find block plugins
discover entity:node                   # Find entity type definitions
discover schema:node                   # Show field schemas for entity bundles
discover perm:administer              # Find permissions
discover method:Timesheet             # Find methods in Service/Controller/Form
discover deps:AUTH                    # Blast radius / dependency analysis
discover impact:my_module             # What depends on this module
```

---

## Plugin Structure

```
drupal-workflow/
├── .claude-plugin/
│   ├── plugin.json              # Plugin metadata (name, version, description)
│   └── marketplace.json         # Marketplace listing metadata
├── agents/                      # 4 specialized agent definitions
│   ├── drupal-builder.md        # Full-stack implementation
│   ├── drupal-reviewer.md       # Architecture review + security audit
│   ├── drupal-verifier.md       # Implementation verification (model: sonnet)
│   └── semantic-architect.md    # Semantic doc generation
├── commands/                    # 10 slash commands
│   ├── drupal-bootstrap.md
│   ├── drupal-prime.md
│   ├── drupal-refresh.md
│   ├── drupal-semantic.md
│   ├── drupal-status.md
│   ├── drupal-test.md
│   ├── drupal-verify.md
│   ├── drupal-blast-radius.md
│   ├── implement.md
│   └── verify-changes.md
├── skills/                      # 15 domain knowledge skills
│   ├── discover/                # Docs-first codebase discovery
│   ├── drupal-caching/          # Cache bins, tags, contexts
│   ├── drupal-coding-standards/ # PHPCS, PHPStan, naming
│   ├── drupal-conventions/      # Translations, CSS, error handling
│   ├── drupal-entity-api/       # Entity CRUD, field types, view modes
│   ├── drupal-hook-patterns/    # OOP hooks (D11), form alters, legacy
│   ├── drupal-rules/            # Core development rules
│   ├── drupal-security-patterns/# OWASP, access control, XSS
│   ├── drupal-service-di/       # Services, dependency injection
│   ├── drupal-testing/          # Smoke tests, drush eval
│   ├── semantic-docs/           # Logic ID navigation
│   ├── structural-index/        # Auto-generated structural awareness
│   │   └── scripts/             # 13 generator + check scripts
│   ├── twig-templating/         # Twig patterns, components
│   ├── verification-before-completion/ # Gate function
│   └── writing-plans/           # Implementation plan templates
├── hooks/
│   └── hooks.json               # 5 hook event definitions
├── scripts/                     # Hook scripts + utilities
│   ├── block-sensitive-files.sh # PreToolUse security gate
│   ├── php-lint-on-save.sh      # PostToolUse PHP linter
│   ├── staleness-check.sh       # PostToolUse staleness warning
│   ├── subagent-context-inject.sh # SubagentStart context injection
│   ├── teammate-quality-gate.sh # TaskCompleted quality gate
│   ├── inject-claude-md.sh      # CLAUDE.md hint injector
│   ├── validate-tech-specs.sh   # Tech spec filename/frontmatter validator
│   └── lib/
│       └── hook-utils.sh        # Shared hook utilities
├── eval/                        # 7 evaluation scripts (315 assertions)
├── playground-*.html            # 3 interactive documentation pages
├── README.md                    # Comprehensive documentation
└── CHANGELOG.md                 # Version history
```

---

## Configuration Options

### Sensitive File Blocking

The PreToolUse hook blocks access to files matching patterns like `settings.php`, `.env`, and credential files.

To customize, create `.claude/sensitive-files.json` in your Drupal project:

```json
{
  "patterns": {
    "custom_patterns": [
      ".*\\.secrets\\.json$",
      ".*/credentials/.*",
      "^config/.*\\.prod\\.yml$"
    ]
  },
  "allowlist": [
    "^config/default/.*",
    "^public/api.*"
  ]
}
```

- `custom_patterns` — Additional file patterns to block
- `allowlist` — Patterns that bypass all blocking

### Hook Timeouts

Default timeouts in `hooks/hooks.json`:

| Hook | Default Timeout | Configurable |
|------|----------------|--------------|
| SessionStart banner | 3s | Yes |
| SessionStart auto-regen | 15s | Yes |
| PreToolUse security | 5s | Yes |
| PostToolUse PHP lint | 10s | Yes |
| PostToolUse staleness | 5s | Yes |
| SubagentStart inject | 5s | Yes |
| TaskCompleted gate | 10s | Yes |

Edit `hooks/hooks.json` to change timeouts.

### Agent Model Selection

Agent models are declared in their frontmatter:

| Agent | Default Model | Override |
|-------|--------------|---------|
| drupal-builder | (inherits from parent) | Edit `agents/drupal-builder.md` frontmatter |
| drupal-reviewer | (inherits from parent) | Edit `agents/drupal-reviewer.md` frontmatter |
| drupal-verifier | sonnet | Edit `agents/drupal-verifier.md` frontmatter |
| semantic-architect | (inherits from parent) | Edit `agents/semantic-architect.md` frontmatter |

---

## Extending the Plugin

### Adding a Custom Skill

1. Create a directory under `skills/`:

```bash
mkdir -p skills/my-custom-skill
```

2. Create `skills/my-custom-skill/SKILL.md` with YAML frontmatter:

```markdown
---
name: my-custom-skill
description: One-line description of what this skill provides
---

# My Custom Skill

## When This Triggers

- When the user asks about [topic]
- When working with [specific Drupal subsystem]

## Content

[Your domain knowledge, patterns, rules, examples]
```

3. Claude Code auto-detects the new skill. No restart needed.

### Adding a Custom Agent

Create a file in `agents/`:

```markdown
---
name: my-agent
description: What this agent does and when to deploy it

<example>
user: "Example prompt that triggers this agent"
assistant: "I'll use my-agent to handle this"
</example>

tools: Read, Write, Edit, Glob, Grep, Bash
model: sonnet
skills: drupal-rules, drupal-testing, my-custom-skill
---

# Agent Instructions

[Role definition, rules, workflow, output format]
```

### Adding a Custom Command

Create a file in `commands/`:

```markdown
---
description: "What /my-command does"
allowed-tools: Bash, Read, Glob, Grep
---

# /my-command

## Purpose

[What problem this command solves]

## Protocol

1. Step 1...
2. Step 2...
3. Step 3...
```

### Adding a Custom Hook

Edit `hooks/hooks.json` to add new hook events:

```json
{
  "PostToolUse": [
    {
      "matcher": "Edit|Write",
      "hooks": [{
        "type": "command",
        "command": "${CLAUDE_PLUGIN_ROOT}/scripts/my-custom-hook.sh",
        "timeout": 5000
      }]
    }
  ]
}
```

Create the hook script in `scripts/`:

```bash
#!/bin/bash
# scripts/my-custom-hook.sh
# Receives tool context via environment variables

# Your logic here
exit 0
```

Make it executable:

```bash
chmod +x scripts/my-custom-hook.sh
```

---

## Developing the Plugin

### Setting Up Your Development Environment

```bash
# Clone the repo
git clone https://github.com/gkastanis/drupal-workflow.git
cd drupal-workflow

# Test against a real Drupal project
cd /path/to/drupal-project
claude --plugin-dir /path/to/drupal-workflow
```

### Running the Evaluation Suite

The eval suite has 315 assertions across 7 scripts:

```bash
cd /path/to/drupal-workflow

# Run all evaluations
python3 eval/eval-skills.py            # 165 assertions — skill content quality
python3 eval/eval-agents.py            # 60 assertions — agent structure + frontmatter
python3 eval/eval-hooks.py             # 20 assertions — hooks system integrity
python3 eval/eval-semantic-architect.py # 25 assertions — tech spec output (behavioral)
python3 eval/eval-builder-agent.py     # 20 assertions — skill application (behavioral)
python3 eval/eval-reviewer-agent.py    # 15 assertions — issue detection (behavioral)
python3 eval/eval-verifier-agent.py    # 10 assertions — verification output (behavioral)
```

All assertions should PASS. Run these after any changes to skills, agents, or hooks.

### Bash Script Testing

Validate syntax before committing:

```bash
# Check all hook scripts
bash -n scripts/*.sh

# Check structural index generators
bash -n skills/structural-index/scripts/*.sh

# Check shared libraries
bash -n scripts/lib/*.sh
```

### JSON Validation

```bash
python3 -m json.tool hooks/hooks.json > /dev/null
python3 -m json.tool .claude-plugin/plugin.json > /dev/null
python3 -m json.tool .claude-plugin/marketplace.json > /dev/null
```

### Testing Structural Index Generation

Test against a Drupal project to verify generators produce correct output:

```bash
# Generate structural index for a test project
skills/structural-index/scripts/generate-all.sh /path/to/drupal-project

# Verify output files were created
ls /path/to/drupal-project/docs/semantic/structural/

# Check for expected files:
# services.md, routes.md, hooks.md, plugins.md, entities.md,
# schemas.md, base-fields.md, permissions.md, methods.md,
# DEPENDENCY_GRAPH.md, FEATURE_MAP.md, .generated-at
```

### Making a Release

1. Update version in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
2. Update `CHANGELOG.md` with new entries
3. Run the full evaluation suite
4. Commit, tag, and push:

```bash
git add -A
git commit -m "chore: bump version to X.Y.Z, update changelog"
git tag -a vX.Y.Z -m "Version X.Y.Z: brief description"
git push origin main --tags
```

---

## Troubleshooting

### "PLUGIN_DIR: not found"

**Cause:** Using deprecated `$PLUGIN_DIR` variable.
**Fix:** Update to v1.7.0+ which uses `$CLAUDE_PLUGIN_ROOT`.

### "Structural index is stale"

**Cause:** Source files (`*.services.yml`, `*.routing.yml`, `*.module`) changed after last generation.
**Fix:** Run `/drupal-refresh`.

### "Cannot detect project directory"

**Cause:** `$CLAUDE_PROJECT_DIR` not set and current directory isn't a Drupal project root.
**Fix:** `cd` into your Drupal project root before starting Claude Code, or set `CLAUDE_PROJECT_DIR` explicitly.

### "Blocked access to file I need"

**Cause:** File matches a sensitive pattern (settings.php, .env, credentials).
**Fix:** Add the file to the `allowlist` in `.claude/sensitive-files.json` (see Configuration section above).

### "Agent doesn't know about structural index"

**Cause:** Structural index missing or SubagentStart hook failed.
**Fix:**
1. Verify index exists: `ls docs/semantic/structural/`
2. If missing, run `/drupal-refresh`
3. Verify hook is enabled in `hooks/hooks.json` (look for `SubagentStart`)

### "Semantic docs generated but CLAUDE.md not updated"

**Cause:** CLAUDE.md hint injection was skipped or failed.
**Fix:** Run `/drupal-semantic inject` to manually inject the hint.

### SessionStart hook takes too long

**Cause:** Auto-regeneration of structural index on a large project.
**Fix:** Increase the timeout in `hooks/hooks.json` (default is 15s), or optimize by ensuring the structural index stays fresh with regular `/drupal-refresh` runs.

### PHP lint errors after editing

**Cause:** The PostToolUse hook runs `php -l` on every PHP file edit.
**Fix:** Fix the syntax error. The hook is advisory — it warns but doesn't block.

---

## Environment Variables

| Variable | Set By | Purpose |
|----------|--------|---------|
| `CLAUDE_PLUGIN_ROOT` | Claude Code | Absolute path to the plugin directory |
| `CLAUDE_PROJECT_DIR` | Claude Code | Absolute path to the user's project directory |
| `TOOL_INPUT` | Claude Code hooks | JSON input to the tool being hooked |

---

## Generated Documentation (in Drupal Projects)

After running the full pipeline, your Drupal project will contain:

```
your-drupal-project/
├── docs/semantic/
│   ├── 00_BUSINESS_INDEX.md          # Master feature registry
│   ├── tech/
│   │   ├── ASGN_01_Assignment.md     # Per-feature tech specs with Logic IDs
│   │   ├── AUTH_01_Authentication.md
│   │   └── ...
│   ├── schemas/
│   │   ├── node.article.json         # Config field schemas (per bundle)
│   │   ├── node.base-fields.json     # Base field schemas (from PHP)
│   │   └── node.article.business.json # AI-authored business rules
│   ├── structural/
│   │   ├── services.md               # Service dependency graph
│   │   ├── routes.md                 # Route map
│   │   ├── hooks.md                  # Hook registry
│   │   ├── plugins.md                # Plugin registry
│   │   ├── entities.md               # Entity map with field counts
│   │   ├── schemas.md                # Schema summary
│   │   ├── base-fields.md            # Base field registry
│   │   ├── permissions.md            # Permission registry
│   │   ├── methods.md                # Method index
│   │   └── .generated-at             # Timestamp for staleness detection
│   ├── DEPENDENCY_GRAPH.md           # Cross-reference analysis
│   └── FEATURE_MAP.md               # Feature overview with hotspot scoring
└── CLAUDE.md                         # Contains ## Codebase hint section
```

This documentation is gitignore-friendly — you can commit it or `.gitignore` it depending on your team's preference. Committing it means team members benefit from semantic docs immediately without running `/drupal-semantic init`.
