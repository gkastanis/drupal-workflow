# Drupal Service & Dependency Injection

name: drupal-service-di
description: >
  Service definitions, dependency injection patterns, and interface design
  for Drupal 10/11. Use when creating services, registering dependencies,
  or implementing the service container pattern.

---

## Service Definition

```yaml
# my_module.services.yml
services:
  my_module.content_manager:
    class: Drupal\my_module\ContentManager
    arguments:
      - '@entity_type.manager'
      - '@current_user'
      - '@logger.channel.my_module'

  my_module.event_subscriber:
    class: Drupal\my_module\EventSubscriber\MyEventSubscriber
    arguments:
      - '@my_module.content_manager'
    tags:
      - { name: event_subscriber }
```

## Constructor Property Promotion

```php
declare(strict_types=1);

namespace Drupal\my_module;

use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\Core\Session\AccountProxyInterface;
use Psr\Log\LoggerInterface;

final class ContentManager implements ContentManagerInterface {

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly AccountProxyInterface $currentUser,
    private readonly LoggerInterface $logger,
  ) {}

}
```

## Interface Design

```php
declare(strict_types=1);

namespace Drupal\my_module;

interface ContentManagerInterface {

  /**
   * Loads content items for the current user.
   *
   * @return \Drupal\node\NodeInterface[]
   *   Array of node entities.
   */
  public function loadUserContent(): array;

}
```

## Plugin Dependency Injection

```php
declare(strict_types=1);

namespace Drupal\my_module\Plugin\Block;

use Drupal\Core\Block\BlockBase;
use Drupal\Core\Plugin\ContainerFactoryPluginInterface;
use Drupal\my_module\ContentManagerInterface;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * Provides a content list block.
 *
 * @Block(
 *   id = "my_module_content_list",
 *   admin_label = @Translation("Content List"),
 * )
 */
final class ContentListBlock extends BlockBase implements ContainerFactoryPluginInterface {

  public function __construct(
    array $configuration,
    $plugin_id,
    $plugin_definition,
    private readonly ContentManagerInterface $contentManager,
  ) {
    parent::__construct($configuration, $plugin_id, $plugin_definition);
  }

  public static function create(
    ContainerInterface $container,
    array $configuration,
    $plugin_id,
    $plugin_definition,
  ): static {
    return new static(
      $configuration,
      $plugin_id,
      $plugin_definition,
      $container->get('my_module.content_manager'),
    );
  }

  public function build(): array {
    return $this->contentManager->loadUserContent();
  }

}
```

## Anti-Patterns

```php
// Bad: static service call.
$node = \Drupal::entityTypeManager()->getStorage('node')->load($nid);

// Good: injected dependency.
$node = $this->entityTypeManager->getStorage('node')->load($nid);

// Bad: no interface type-hint.
class MyService {
  public function __construct(private readonly ContentManager $manager) {}
}

// Good: interface type-hint.
class MyService {
  public function __construct(private readonly ContentManagerInterface $manager) {}
}
```

## Service Name Discovery

Service names follow no universal convention. Don't guess -- verify.

```bash
# Quick check: does a service exist?
ddev drush eval 'print json_encode(["exists" => Drupal::hasService("module_name.service_name")]);'
```

**When a service name fails**: Read the module's `*.services.yml` directly rather than guessing variations. The module prefix may be singular (`group_permission.checker`) when you expect plural (`group_permissions.checker`).

## Finding the Loaded File (Patched Modules)

When a module exists in both `vendor/drupal/` and `web/modules/contrib/`, only one is actually loaded by PHP.

```php
// Find which file is running at runtime
$ref = new \ReflectionMethod($service, 'methodName');
echo $ref->getFileName();
// Edit the file that ReflectionMethod reports, not the one you assume.
```

**Common scenario**: A composer-patched module. The original sits in `vendor/`, the patched version in `web/modules/contrib/`. Editing the vendor copy has no effect because the autoloader loads from contrib.

## Common Drupal Services

| Service ID | Interface | Purpose |
|---|---|---|
| `entity_type.manager` | `EntityTypeManagerInterface` | Entity CRUD |
| `current_user` | `AccountProxyInterface` | Current user |
| `config.factory` | `ConfigFactoryInterface` | Configuration |
| `logger.factory` | `LoggerChannelFactoryInterface` | Logging |
| `messenger` | `MessengerInterface` | User messages |
| `module_handler` | `ModuleHandlerInterface` | Module operations |
| `state` | `StateInterface` | Key-value state |
| `cache.default` | `CacheBackendInterface` | Default cache |
