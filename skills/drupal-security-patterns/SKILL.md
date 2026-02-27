# Drupal Security Patterns

name: drupal-security-patterns
description: >
  OWASP prevention patterns, access control, input sanitization, and XSS
  protection for Drupal 10/11. Use when reviewing code for security issues,
  implementing access control, or hardening Drupal applications.

---

## SQL Injection Prevention

```php
// Bad: string concatenation.
$result = $connection->query("SELECT * FROM {node} WHERE title = '$title'");

// Good: parameterized query.
$result = $connection->query(
  "SELECT * FROM {node} WHERE title = :title",
  [':title' => $title]
);

// Best: Entity API.
$nids = \Drupal::entityQuery('node')
  ->condition('title', $title)
  ->accessCheck(TRUE)
  ->execute();
```

## XSS Protection

```php
// Twig auto-escapes by default - safe.
{{ node.title }}

// Explicit escaping for raw output.
use Drupal\Component\Utility\Html;
$safe = Html::escape($user_input);

// Xss filter for allowed HTML.
use Drupal\Component\Utility\Xss;
$filtered = Xss::filter($user_input);

// Admin filter (more tags allowed).
$filtered = Xss::filterAdmin($content);
```

## Access Control

### Route Access

```yaml
# my_module.routing.yml
my_module.admin:
  path: '/admin/my-module'
  defaults:
    _controller: '\Drupal\my_module\Controller\AdminController::page'
  requirements:
    _permission: 'administer my_module'

my_module.content:
  path: '/my-module/{node}'
  defaults:
    _controller: '\Drupal\my_module\Controller\ContentController::view'
  requirements:
    _entity_access: 'node.view'
```

### Custom Access Checker

```php
declare(strict_types=1);

namespace Drupal\my_module\Access;

use Drupal\Core\Access\AccessResult;
use Drupal\Core\Routing\Access\AccessInterface;
use Drupal\Core\Session\AccountInterface;

final class MyAccessChecker implements AccessInterface {

  public function access(AccountInterface $account): AccessResult {
    return AccessResult::allowedIfHasPermission($account, 'access my_module')
      ->cachePerPermissions();
  }

}
```

## Stacked Route Access Checks

Routes can have **multiple** `_*_access*` requirements that ALL must pass (AND logic). Don't assume `_permission` is the only gate.

```yaml
# Example: three access checkers on one route
my_module.entity_edit:
  path: '/entity/{entity}/edit'
  requirements:
    _entity_access: entity.update           # Entity-level check
    _custom_archived_check: 'TRUE'          # Custom: is entity archived?
    _custom_status_check: 'TRUE'            # Custom: additional gate
```

**Debugging 403s when entity access passes:**
1. Read the route's `requirements` in `*.routing.yml`
2. Trace each `_*_access*` checker service in `*.services.yml`
3. Check each checker class individually -- any one returning DENIED blocks the route

**During security review**: Examine ALL route requirements, not just `_permission`. Custom access checkers may silently block access even when entity-level access is granted.

## CSRF Protection

```php
// Form API handles CSRF automatically via form tokens.
// For custom AJAX endpoints:
use Drupal\Core\Access\CsrfTokenGenerator;

// Generate token.
$token = \Drupal::csrfToken()->get('my_module_action');

// Validate token.
if (!\Drupal::csrfToken()->validate($token, 'my_module_action')) {
  throw new AccessDeniedHttpException();
}
```

## File Upload Validation

```php
$validators = [
  'file_validate_extensions' => ['pdf doc docx'],
  'file_validate_size' => [25 * 1024 * 1024], // 25MB
  'file_validate_name_length' => [],
];
```

## Security Checklist

### Critical (Must Fix)
- No SQL injection (Entity API or parameterized queries).
- XSS protection (Twig auto-escape, `Html::escape`).
- Access control on all routes and entities.
- Input sanitization via Form API validation.
- No hardcoded credentials.
- CSRF protection via Form API.

### Important (Should Fix)
- Dependency injection used (no `\Drupal::` in classes).
- File upload validation (type, size, extension).
- Configuration exportable.
- No deprecated code.
- WCAG 2.1 AA compliance.

## Architecture Red Flags

- Multiple responsibilities in one module.
- Service exposes internal implementation details.
- Direct class dependencies instead of interfaces.
- Hidden side effects or implicit contracts.
- `\Drupal::` static calls in service classes.
