# Drupal Coding Standards

name: drupal-coding-standards
description: >
  PHPCS, PHPStan, naming conventions, and code style enforcement for
  Drupal 10/11. Use when checking coding standards, running static analysis,
  or enforcing code quality.

---

## Validation Commands

```bash
# Check coding standards.
./vendor/bin/phpcs --standard=Drupal,DrupalPractice web/modules/custom/my_module/

# Auto-fix standards issues.
./vendor/bin/phpcbf --standard=Drupal web/modules/custom/my_module/

# Static analysis.
./vendor/bin/phpstan analyse web/modules/custom/my_module/

# Deprecation check.
drupal-check web/modules/custom/my_module/

# Security audit.
composer audit
```

## Required Code Patterns

### File Headers

```php
<?php

declare(strict_types=1);

namespace Drupal\my_module;
```

### Class Declaration

```php
/**
 * Manages content operations.
 */
final class ContentManager implements ContentManagerInterface {
```

### Constructor

```php
public function __construct(
  private readonly EntityTypeManagerInterface $entityTypeManager,
  private readonly LoggerInterface $logger,
) {}
```

## Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Local variables | `$snake_case` | `$user_name` |
| Class properties | `$lowerCamelCase` | `$this->entityManager` |
| Classes | `PascalCase` | `ContentManager` |
| Interfaces | `PascalCase` + `Interface` | `ContentManagerInterface` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| Services | `module.service_name` | `my_module.content_manager` |
| Hooks | `module_hook_name` | `my_module_form_alter` |

## Anti-Patterns to Report

| Anti-Pattern | Fix |
|---|---|
| `foreach` with nested `if/break/continue` | `array_filter`/`array_map`/`array_reduce` |
| Deep nesting (3+ levels) | Guard clauses, early returns |
| Non-final classes without reason | Declare `final` by default |
| Getters/setters where `public readonly` works | Use `public readonly` |
| `\Drupal::` calls in classes | Constructor dependency injection |
| PHP `json_encode/decode` | `\GuzzleHttp\Utils::jsonDecode/jsonEncode` |
| "Service" namespace | Use logical groupings |
| Catching `\Exception` | Catch narrowest exception type |

## PHPDoc Standards

```php
/**
 * Loads articles by category.
 *
 * @param int $category_id
 *   The taxonomy term ID.
 * @param int $limit
 *   Maximum number of results.
 *
 * @return \Drupal\node\NodeInterface[]
 *   Array of article nodes.
 *
 * @throws \Drupal\Component\Plugin\Exception\InvalidPluginDefinitionException
 */
public function loadByCategory(int $category_id, int $limit = 10): array {
```

## Module Structure

```
modules/custom/my_module/
  my_module.info.yml
  my_module.module
  my_module.services.yml
  my_module.routing.yml
  my_module.permissions.yml
  config/
    install/
    schema/
  src/
    Controller/
    Form/
    Plugin/
      Block/
    EventSubscriber/
  tests/
    src/
      Unit/
      Kernel/
      Functional/
```
