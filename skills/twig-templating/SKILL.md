# Twig Templating

name: twig-templating
description: >
  Twig template patterns, filters, theme suggestions, and component architecture
  for Drupal 10/11. Use when creating or modifying Twig templates, implementing
  theme hooks, or building front-end components.

---

## Template Naming Conventions

Drupal uses suggestion-based template discovery:

```
node.html.twig                    # Base node template.
node--article.html.twig           # Article content type.
node--article--teaser.html.twig   # Article teaser view mode.
node--42.html.twig                # Specific node by ID.

block.html.twig                   # Base block template.
block--system-branding-block.html.twig  # Specific block.

field.html.twig                   # Base field template.
field--field-image.html.twig      # Specific field.
field--node--field-image--article.html.twig  # Field + bundle.

page.html.twig                    # Base page template.
page--front.html.twig             # Front page.
page--node--42.html.twig          # Specific node page.
```

## Template Structure

```twig
{# node--article.html.twig #}
{% set classes = [
  'node',
  'node--' ~ node.bundle,
  node.isPromoted() ? 'node--promoted',
  node.isSticky() ? 'node--sticky',
  view_mode ? 'node--' ~ view_mode,
] %}

<article{{ attributes.addClass(classes) }}>
  {% if label %}
    <h2{{ title_attributes }}>
      <a href="{{ url }}" rel="bookmark">{{ label }}</a>
    </h2>
  {% endif %}

  <div{{ content_attributes.addClass('node__content') }}>
    {{ content }}
  </div>
</article>
```

## Common Filters

| Filter | Purpose | Example |
|---|---|---|
| `|t` | Translate string | `{{ 'Hello'|t }}` |
| `|raw` | Skip auto-escape (CAUTION) | `{{ safe_html|raw }}` |
| `|escape` | Explicit escape | `{{ text|escape }}` |
| `|clean_class` | CSS-safe class | `{{ title|clean_class }}` |
| `|clean_id` | HTML-safe ID | `{{ title|clean_id }}` |
| `|date` | Format date | `{{ date|date('Y-m-d') }}` |
| `|length` | Array/string length | `{{ items|length }}` |
| `|without` | Render without fields | `{{ content|without('field_tags') }}` |
| `|safe_join` | Join array with separator | `{{ items|safe_join(', ') }}` |

## Drupal-Specific Functions

```twig
{# Attach library assets. #}
{{ attach_library('my_theme/component') }}

{# Link to a route. #}
{{ path('entity.node.canonical', {'node': nid}) }}

{# Create a link. #}
{{ link('Click here', url) }}

{# Translate with context. #}
{{ 'Submit'|t({}, {'context': 'my_module'}) }}

{# Access Drupal URL. #}
{{ url('<front>') }}

{# File URL from URI. #}
{{ file_url(node.field_image.entity.fileuri) }}
```

## Preprocess Functions

```php
/**
 * Implements hook_preprocess_HOOK() for node templates.
 */
function my_theme_preprocess_node(array &$variables): void {
  $node = $variables['node'];

  // Add custom variables.
  $variables['reading_time'] = ceil(str_word_count(strip_tags($node->body->value)) / 200);

  // Add conditional classes.
  if ($node->isPublished()) {
    $variables['attributes']['class'][] = 'node--published';
  }
}
```

## Template Suggestions

```php
/**
 * Implements hook_theme_suggestions_HOOK_alter() for node templates.
 */
function my_theme_theme_suggestions_node_alter(array &$suggestions, array $variables): void {
  $node = $variables['elements']['#node'];

  // Add suggestion based on custom field value.
  if ($node->hasField('field_layout') && !$node->get('field_layout')->isEmpty()) {
    $layout = $node->get('field_layout')->value;
    $suggestions[] = 'node__' . $node->bundle() . '__' . $layout;
  }
}
```

## BEM Component Pattern

```twig
{# components/card.html.twig #}
{% set card_classes = [
  'card',
  variant ? 'card--' ~ variant,
  size ? 'card--' ~ size,
] %}

<div{{ attributes.addClass(card_classes) }}>
  {% if image %}
    <div class="card__image">
      {{ image }}
    </div>
  {% endif %}

  <div class="card__content">
    {% if title %}
      <h3 class="card__title">{{ title }}</h3>
    {% endif %}

    {% if body %}
      <div class="card__body">{{ body }}</div>
    {% endif %}
  </div>

  {% if actions %}
    <div class="card__actions">{{ actions }}</div>
  {% endif %}
</div>
```

## Template Best Practices

1. Keep logic minimal in Twig - heavy logic goes to preprocess functions.
2. Use BEM naming convention (`block__element--modifier`).
3. Always use `{{ attach_library() }}` for component assets.
4. Use `|t` filter for all translatable strings.
5. Templates receive data only - no data fetching in Twig.
6. Disable Twig debug in production configuration.
7. Use `{{ content|without('field_name') }}` to exclude specific fields.
