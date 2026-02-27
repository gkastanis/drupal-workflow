---
name: drupal-rules
description: Core Drupal development rules covering code quality, security, services, and testing verification. ALWAYS consult when writing Drupal code.
---

# Drupal Development Rules

Consolidated rules for Drupal development. Follow these for every implementation task.

## Services & Dependency Injection

### Mandatory Rules

1. Use services + dependency injection -- NEVER use `\Drupal::*` static calls in classes.
2. Use Entity API for all CRUD operations -- NEVER use raw SQL queries.
3. New modules require: `.info.yml`, `.module`, `/src` (PSR-4), `.services.yml`.
4. Config defaults go in `config/install/`, not `hook_install()`.
5. Use the library system for front-end assets -- no inline JS/CSS.

### Service Design

- Register all services in `<module>.services.yml` with interface type-hints.
- Use constructor property promotion for dependency injection.
- Declare classes `final` unless explicitly designed for extension.
- Use `declare(strict_types=1)` in all custom PHP files.
- Minimize visibility: `private` > `protected` > `public`.

### After Service Changes

Verify Drupal service changes: after service or Twig changes, confirm service injections are correct, DB table and column names exist, and Twig filters actually exist in the project.

### Service Name Discovery

- **Never guess** service names -- read the module's `*.services.yml` file directly.
- Quick check: `Drupal::hasService("module_name.service_name")` before using any service.
- Common trap: module prefix may be singular (`group_permission`) even when docs or module name suggest plural (`group_permissions`).
- When a service name fails, check the YAML -- don't iterate through guesses.

---

## Security

### Input Sanitization

- Sanitize all user inputs using `Xss::filter()` or render arrays.
- Use Form API validation for all form submissions.
- Use parameterized queries or Entity API -- never concatenate user input into SQL.

### Output Protection

- Rely on Twig auto-escaping for output.
- Use `Html::escape()` for raw HTML output outside Twig.
- Never output unescaped user input.

### Access Control

- Define access control on all custom routes and entity operations.
- Use CSRF protection via Form API tokens on state-changing operations.
- Validate file uploads: type, size, and extension checks.

### Route Access vs Entity Access

- Routes can stack **multiple** access checkers -- all must pass for access to be granted.
- `$entity->access('update')` returning ALLOWED does NOT mean the route grants access. Other checkers (archived status, custom gates) may still deny.
- Debugging 403: read the route's `requirements` YAML and trace each `_*_access*` checker class individually.

### Credentials

- No hardcoded credentials or API keys in source code.
- Use environment variables or Drupal's key module for secrets.
- Never commit `.env`, `settings.local.php`, or credential files.

---

## Code Quality

### After Multi-File Changes

Grep the codebase for remaining references after modifying functions, constants, or variables across files. This catches missed locations that would cause runtime errors.

### Config Over Magic Numbers

Search for existing config constants before hardcoding values (e.g., `* 8` for hours, `* 5` for weekdays). Use system-configured values instead.

### Remove From ALL Locations

When removing or disabling something, remove from ALL locations (controller, template, Twig, JS, config) and grep to confirm nothing was missed.

### Implementation Preferences

- Use guard clauses to decrease cyclomatic complexity -- return early.
- Prefer `array_filter()`, `array_map()`, `array_reduce()` over `foreach` with nested `if/break/continue`.
- Use data objects instead of arrays. Convert arrays to objects ASAP.
- PHP 8.4+: Use property hooks for get/set methods.
- Exception: Drupal render/form APIs can use arrays.

### JSON & Logging

- Use `\GuzzleHttp\Utils::jsonDecode/jsonEncode` (not PHP's `json_*`).
- Use `LoggerInterface` methods (`debug`/`info`/`warning`/`error`) -- no custom debug flags.
- Avoid "Service" namespace (`Drupal\my_module\Service`) -- use logical groupings.

### Variable Naming

- `$snake_case` for local variables and function parameters.
- `$lowerCamelCase` for class properties/attributes.

### Comments

- End full sentences with `.`
- Exception: NO periods in Behat annotations (`@Then`, `@Given`, `@When`).

---

## Testing & Verification

### Verify Before Claiming Completion

**Mandatory gate**: Run tests, read output, confirm it proves your claim, THEN claim done.
Never say "should work", "looks correct", or "I've implemented X" without test output.

### Preferred Verification Methods (priority order)

#### 1. Curl Smoke Tests (most reliable)

```bash
# Status code + response size
ddev exec curl -s -o /dev/null -w "%{http_code} %{size_download}" -b <COOKIE> "http://localhost/<PATH>"

# Download full HTML
ddev exec curl -s -b <COOKIE> "http://localhost/<PATH>" > /tmp/page-output.html

# Get auth cookie
ddev drush uli --uid=1 --no-browser 2>/dev/null
```

#### 2. Drush Eval (secondary)

**Escaping rules**: Use `Drupal::` not `\Drupal::` in single quotes. Use `Exception` not `\Exception`. No `use` statements. Keep PHP on one line.

```bash
ddev drush eval 'print json_encode(["exists" => Drupal::hasService("my.service")]);' 2>/dev/null
```

#### 3. Test Scripts (complex scenarios)

Store in `scripts/tests/`. Update `scripts/tests/index.md` when creating scripts.

### Red Flags

These phrases signal unverified claims -- stop and test first:
- "should work now" / "looks correct" / "this will fix it"
- Claiming completion without test output in your response

### DDEV Shell Rules

- **Never** pass complex shell constructs (pipes, variables, nested quotes) through `ddev exec` -- write a script file and execute it.
- `drush uli` + `curl` must be in the **same script, same shell**, with `--uri=http://localhost` so the cookie domain matches.
- When checking form element visibility in curl output, search for Drupal HTML IDs (`edit-features`, `edit-moderation-state-0`) not generic machine names.

### Script Storage

- **ALWAYS**: `scripts/tests/` directory with index.
- Make executable: `chmod +x scripts/tests/*.sh`.

**Naming conventions:**
- `verify-{feature}.sh` -- feature verification.
- `debug-{feature}-{aspect}.php` -- investigation.
- `check-{aspect}.sh` -- quick checks.
- `list-{entities}.php` -- data listing.
- `fix-{issue}.php` -- one-time fixes.
