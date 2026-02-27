---
name: writing-plans
description: |
  Use when delegating tasks to sub-agents or creating implementation plans.
  Write comprehensive plans assuming the engineer has zero codebase context.
  Include exact file paths, complete code, verification commands, and bite-sized tasks.
---

# Writing Implementation Plans

## Core Principle

**Write plans assuming the engineer has zero codebase context.**

Document everything: which files to touch, complete code (not "add validation"), how to test, verification commands with expected output.

## Plan Structure for Delegations

When delegating to a sub-agent, structure the prompt as:

```markdown
## Task: [Clear Task Name]

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

### Files

| Action | Path |
|--------|------|
| CREATE | `exact/path/to/file.php` |
| MODIFY | `exact/path/to/existing.php` (lines ~50-75) |
| TEST | `tests/exact/path/test.php` |

### Implementation Steps

#### Step 1: [Action]

**File:** `exact/path/to/file.php`

```php
// Complete code - not "add validation"
<?php

declare(strict_types=1);

namespace Drupal\my_module\Service;

final class MyService {
  // Full implementation
}
```

#### Step 2: [Next Action]

[Continue with complete code...]

### Verification

**Command:** `ddev drush cr && ddev drush my:command`
**Expected:** `Success message here`

**Test Command:** `Skill(skill: "drupal-testing")`
**Expected:** All checks pass
```

## Bite-Sized Task Granularity

Each step should be ONE action (2-5 minutes):

✅ GOOD (atomic):
- "Create the service class with interface"
- "Register service in .services.yml"
- "Run drush cr and verify service exists"
- "Write the failing test"
- "Implement minimal code to pass test"

❌ BAD (too broad):
- "Create the service" (which files? what code?)
- "Add tests" (what tests? where?)
- "Wire it up" (wire what to what?)

## Required Context Elements

Every delegation MUST include:

1. **File Paths** - Exact paths, not "in the module"
2. **Complete Code** - Full implementations, not placeholders
3. **Dependencies** - What services to inject, what modules required
4. **Verification** - Exact commands with expected output
5. **Existing Patterns** - Reference similar code in codebase if exists

## Anti-Patterns

| Don't Say | Say Instead |
|-----------|-------------|
| "Add appropriate validation" | "Add validation: `if (empty($value)) { throw new \InvalidArgumentException('Value required'); }`" |
| "Create a service" | "Create `web/modules/custom/my_module/src/MyService.php` with..." |
| "Update the config" | "Edit `config/sync/my_module.settings.yml` line 15, change `enabled: false` to `enabled: true`" |
| "Test it works" | "Run `ddev drush my:command arg1` - expect output: `Success: processed 5 items`" |

## Example Delegation

```
Task(subagent_type="drupal-builder",
     prompt="""
## Task: Create ArticleManager Service

**Goal:** Service to fetch published articles with caching

**Architecture:** Injectable service using EntityTypeManager, CacheBackend

### Files

| Action | Path |
|--------|------|
| CREATE | `web/modules/custom/my_article/src/ArticleManager.php` |
| CREATE | `web/modules/custom/my_article/src/ArticleManagerInterface.php` |
| MODIFY | `web/modules/custom/my_article/my_article.services.yml` |

### Step 1: Create Interface

**File:** `web/modules/custom/my_article/src/ArticleManagerInterface.php`

```php
<?php

declare(strict_types=1);

namespace Drupal\my_article;

interface ArticleManagerInterface {
  public function getPublishedArticles(int $limit = 10): array;
}
```

### Step 2: Create Service Implementation

**File:** `web/modules/custom/my_article/src/ArticleManager.php`

```php
<?php

declare(strict_types=1);

namespace Drupal\my_article;

use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\Core\Cache\CacheBackendInterface;

final class ArticleManager implements ArticleManagerInterface {

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly CacheBackendInterface $cache,
  ) {}

  public function getPublishedArticles(int $limit = 10): array {
    $cid = 'my_article:published:' . $limit;
    if ($cached = $this->cache->get($cid)) {
      return $cached->data;
    }

    $storage = $this->entityTypeManager->getStorage('node');
    $ids = $storage->getQuery()
      ->accessCheck(TRUE)
      ->condition('type', 'article')
      ->condition('status', 1)
      ->range(0, $limit)
      ->sort('created', 'DESC')
      ->execute();

    $articles = $storage->loadMultiple($ids);
    $this->cache->set($cid, $articles, time() + 3600, ['node_list:article']);

    return $articles;
  }
}
```

### Step 3: Register Service

**File:** `web/modules/custom/my_article/my_article.services.yml` (append)

```yaml
services:
  my_article.article_manager:
    class: Drupal\my_article\ArticleManager
    arguments:
      - '@entity_type.manager'
      - '@cache.default'
```

### Verification

1. `ddev drush cr` - expect: Cache rebuild successful
2. `Skill(skill: "drupal-testing")` - check service_exists for my_article.article_manager
""")
```

## Before Delegating Checklist

- [ ] Exact file paths specified
- [ ] Complete code provided (not "add X")
- [ ] Dependencies listed (services to inject)
- [ ] Verification command with expected output
- [ ] Referenced existing patterns if applicable
