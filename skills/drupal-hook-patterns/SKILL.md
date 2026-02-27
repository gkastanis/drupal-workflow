# Drupal Hook Patterns

name: drupal-hook-patterns
description: >
  OOP hooks (Drupal 11), form alters, entity hooks, and legacy bridges for
  Drupal 10/11. Use when implementing hooks, form alterations, or event
  subscribers.

---

## OOP Hooks (Drupal 11+)

### Hook Attribute Pattern

```php
declare(strict_types=1);

namespace Drupal\my_module\Hook;

use Drupal\Core\Hook\Attribute\Hook;

/**
 * Hook implementations for my_module.
 */
final class MyModuleHooks {

  #[Hook('form_alter')]
  public function formAlter(array &$form, FormStateInterface $form_state, string $form_id): void {
    if ($form_id === 'node_article_form') {
      $form['title']['#description'] = $this->t('Enter a descriptive title.');
    }
  }

  #[Hook('entity_presave')]
  public function entityPresave(EntityInterface $entity): void {
    if ($entity->getEntityTypeId() === 'node' && $entity->bundle() === 'article') {
      // Set default values before saving.
    }
  }

}
```

### Legacy Bridge (Drupal 10 Compatibility)

```php
// my_module.module

use Drupal\Core\Hook\Attribute\LegacyHook;

/**
 * Implements hook_form_alter().
 */
#[LegacyHook]
function my_module_form_alter(array &$form, FormStateInterface $form_state, string $form_id): void {
  \Drupal::classResolver(MyModuleHooks::class)->formAlter($form, $form_state, $form_id);
}
```

## Common Hooks

### Form Alter

```php
/**
 * Implements hook_form_FORM_ID_alter() for node_article_form.
 */
function my_module_form_node_article_form_alter(array &$form, FormStateInterface $form_state): void {
  // Add validation.
  $form['#validate'][] = '_my_module_article_validate';

  // Modify field widgets.
  $form['field_category']['widget']['#required'] = TRUE;
}
```

### Entity Hooks

```php
/**
 * Implements hook_entity_presave().
 */
function my_module_entity_presave(EntityInterface $entity): void {
  if ($entity instanceof NodeInterface && $entity->bundle() === 'event') {
    // Set computed field values.
  }
}

/**
 * Implements hook_entity_insert().
 */
function my_module_entity_insert(EntityInterface $entity): void {
  if ($entity instanceof NodeInterface) {
    // Post-creation actions (notifications, indexing).
  }
}

/**
 * Implements hook_entity_access().
 */
function my_module_entity_access(EntityInterface $entity, string $operation, AccountInterface $account): AccessResultInterface {
  if ($entity->getEntityTypeId() === 'node' && $entity->bundle() === 'private_content') {
    return AccessResult::forbiddenIf(
      $operation === 'view' && !$account->hasPermission('view private content')
    )->cachePerPermissions();
  }
  return AccessResult::neutral();
}
```

### Theme Hooks

```php
/**
 * Implements hook_theme().
 */
function my_module_theme(): array {
  return [
    'my_module_component' => [
      'variables' => [
        'title' => NULL,
        'items' => [],
        'attributes' => NULL,
      ],
    ],
  ];
}

/**
 * Implements hook_preprocess_HOOK() for node templates.
 */
function my_module_preprocess_node(array &$variables): void {
  $node = $variables['node'];
  if ($node->bundle() === 'article') {
    $variables['reading_time'] = _my_module_calculate_reading_time($node);
  }
}
```

## Event Subscribers

```php
declare(strict_types=1);

namespace Drupal\my_module\EventSubscriber;

use Symfony\Component\EventDispatcher\EventSubscriberInterface;
use Symfony\Component\HttpKernel\Event\RequestEvent;
use Symfony\Component\HttpKernel\KernelEvents;

final class MyEventSubscriber implements EventSubscriberInterface {

  public static function getSubscribedEvents(): array {
    return [
      KernelEvents::REQUEST => ['onRequest', 100],
    ];
  }

  public function onRequest(RequestEvent $event): void {
    // Handle incoming request.
  }

}
```

## Hook Implementation Checklist

1. Prefer OOP hooks with `#[Hook]` attribute (Drupal 11+).
2. Provide `#[LegacyHook]` bridge for Drupal 10 compatibility.
3. Delegate hook logic to injectable services.
4. Keep `.module` file thin - hooks call services.
5. Use specific form alter hooks (`hook_form_FORM_ID_alter`) over generic.
6. Add cache metadata to access results.
