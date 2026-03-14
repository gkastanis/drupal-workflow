---
name: drupal-config-management
description: Configuration management patterns for Drupal 10/11 — config split, config ignore, environments, import/export workflows, config readonly, and the sync/install/optional directory hierarchy. Use when working with config export/import, multi-environment deployments, config split setup, or managing configuration across dev/staging/prod.
---

# Drupal Config Management

Configuration is Drupal's declarative system for site building. It lives in YAML files and is the bridge between development and deployment. Getting config management right is the difference between smooth deploys and broken production sites.

## Config Directories

Drupal supports multiple config directories. Understanding which one to use is critical.

| Directory | Purpose | When Populated |
|-----------|---------|----------------|
| `config/sync` | Primary sync directory for `drush cim`/`drush cex` | `drush cex` writes here |
| `config/default` | Legacy name for sync (Drupal 8 projects) | Same as sync |
| `config/staging` | Alternative name used by some hosting platforms | Same as sync |
| `modules/custom/*/config/install` | Default config installed when module is enabled | Module install |
| `modules/custom/*/config/optional` | Config installed only if dependencies are met | Module install |

### install vs optional

- **install/**: Config that MUST exist when the module is enabled. If it fails to install, the module enable fails.
- **optional/**: Config that is installed IF the required dependencies (modules, entity types) exist. Silently skipped if dependencies are missing.

```yaml
# config/install/my_module.settings.yml
# Always installed with the module.

# config/optional/views.view.my_module_listing.yml
# Only installed if the Views module is enabled.
```

## Import and Export

```bash
# Export all active config to sync directory.
drush cex -y

# Import config from sync directory to active.
drush cim -y

# Import only specific config (partial import).
drush cim --partial --source=modules/custom/my_module/config/install -y

# Show differences between active and sync.
drush config:status

# Get a specific config value.
drush config:get system.site name

# Set a specific config value (use sparingly — prefer YAML files).
drush config:set system.site name "My Site" -y
```

## Config Split

Config Split (`config_split` module) is the standard tool for managing environment-specific configuration. It allows different config per environment (dev, staging, prod) from a single codebase.

### How it works

Config Split defines "splits" — named sets of config that can be:
- **Complete split**: Config exists ONLY in the split, not in sync. Used for dev-only modules.
- **Conditional split**: Config exists in sync with default values, but the split overrides specific values. Used for environment-specific settings.

### Setup

```yaml
# config/sync/config_split.config_split.dev.yml
id: dev
label: Development
folder: ../config/split/dev
status: true              # Active on dev, inactive elsewhere.
module:
  devel: 0                # Enable devel module on dev only.
  stage_file_proxy: 0     # Enable stage_file_proxy on dev only.
complete_list:
  system.logging: {}      # Verbose logging only on dev.
conditional_list: {}
```

### Activation per environment

In each environment's `settings.php` or `settings.local.php`:

```php
// settings.local.php (dev)
$config['config_split.config_split.dev']['status'] = TRUE;
$config['config_split.config_split.prod']['status'] = FALSE;

// settings.php (prod)
$config['config_split.config_split.dev']['status'] = FALSE;
$config['config_split.config_split.prod']['status'] = TRUE;
```

### Split directory structure

```
config/
  sync/           # Base config (shared across all environments)
  split/
    dev/          # Dev-only config (devel, verbose logging)
    staging/      # Staging-specific overrides
    prod/         # Prod-specific config (CDN, caching)
```

### Workflow

```bash
# On dev: export with splits active.
drush cex -y
# Both config/sync/ and config/split/dev/ are updated.

# On staging/prod: import with that environment's split active.
drush cim -y
# Config from config/sync/ + config/split/prod/ is imported.
```

## Config Ignore

`config_ignore` module prevents specific config from being overwritten during import. Useful for site-specific settings that should never be deployed from code.

```yaml
# config/sync/config_ignore.settings.yml
ignored_config_entities:
  - system.site           # Site name/slogan set per environment.
  - core.extension~module.devel  # Ignore devel module status.
  - webform.webform.*     # Ignore all webform submissions config.
```

**When to use config_ignore vs config_split:**
- **Config split**: Different values per environment (dev has devel enabled, prod doesn't).
- **Config ignore**: Config that should never be deployed from code (site name, contact form recipients set by site admins).

## Config Readonly

`config_readonly` module prevents config changes via the admin UI in production. All config changes must go through code deployment.

```php
// settings.php (production only)
$settings['config_readonly'] = TRUE;

// Allow specific forms to bypass readonly (e.g., site settings).
$settings['config_readonly_whitelist_patterns'] = [
  'system.site',
  'contact.form.*',
];
```

## Config Schema

Every config file should have a schema definition. Without it, `drush cim` may silently accept invalid config.

```yaml
# config/schema/my_module.schema.yml
my_module.settings:
  type: config_object
  label: 'My Module settings'
  mapping:
    enabled:
      type: boolean
      label: 'Enabled'
    max_items:
      type: integer
      label: 'Maximum items'
    api_endpoint:
      type: string
      label: 'API endpoint URL'
```

## Config Translation

For multilingual sites, config translation stores translated strings separately:

```yaml
# language/el/my_module.settings.yml (Greek translations)
label: 'Οι ρυθμίσεις μου'
description: 'Ρυθμίσεις του module'
```

Config translation files live in `config/sync/language/LANGCODE/` and are imported/exported with regular config.

## Common Pitfalls

**1. Editing config on production without config_readonly.**
Fix: Enable `config_readonly` on production. All changes via code.

**2. Conflicting UUIDs when sharing config across sites.**
Fix: Never copy `config/sync` between different Drupal installations. Use `config/install` in modules for portable config.

**3. Missing config dependencies.**
Fix: Add `dependencies.module` and `dependencies.config` to your config files. Without these, `drush cim` may import config before its dependencies exist.

**4. Config not importing because of config_ignore.**
Fix: Check `config_ignore.settings` for patterns that match your config.

**5. Forgetting to export after admin UI changes.**
Fix: Run `drush config:status` before committing. If it shows changes, run `drush cex -y`.

## Workflow Checklist

1. Make config changes in dev (UI or code).
2. Export: `drush cex -y`.
3. Review the diff: `git diff config/`.
4. Commit config changes with the code that uses them.
5. On staging: `drush cim -y && drush cr`.
6. On prod: `drush cim -y && drush cr` (with config_readonly re-enabled after).
