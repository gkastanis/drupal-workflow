# Drupal Entity API

name: drupal-entity-api
description: >
  Field type selection, entity CRUD operations, view modes, and content modeling
  patterns for Drupal 10/11. Use when designing content types, selecting field types,
  or working with the Entity API.

---

## Field Type Selection Matrix

| Content Need | Field Type | Widget | Notes |
|---|---|---|---|
| Event date/time | `datetime` | `datetime_default` | Single datetime |
| Date range | `daterange` | `daterange_default` | Start/end dates |
| Location (simple) | `string` | `string_textfield` | Text-based |
| Location (structured) | `address` (contrib) | `address_default` | Full address |
| Short text | `string` | `string_textfield` | Max 255 chars |
| Long text | `text_long` | `text_textarea` | Unlimited plain text |
| Rich content | `text_with_summary` | `text_textarea_with_summary` | Formatted with summary |
| Email | `email` | `email_default` | Validated email |
| Phone | `telephone` | `telephone_default` | Phone number |
| Website | `link` | `link_default` | URL with title |
| Document | `file` | `file_generic` | Any file type |
| Image | `image` | `image_image` | With alt text |
| Content reference | `entity_reference` (node) | `entity_reference_autocomplete` | Links to nodes |
| Term reference | `entity_reference` (taxonomy_term) | `entity_reference_autocomplete` | Categories |
| Yes/No flag | `boolean` | `boolean_checkbox` | True/false |
| Flexible components | `entity_reference_revisions` (paragraphs) | `paragraphs` | Nested content |

## Entity Type Selection

- **Nodes**: Published content (articles, pages, events).
- **Custom entities**: Non-published data (rarely needed - prefer nodes).
- **Taxonomy terms**: Categorization and metadata.
- **Paragraphs**: Flexible content components.
- **Media**: Files, images, videos.
- **Users**: User profiles (extend, don't replace).

## Entity CRUD Operations

```php
// Load single entity.
$node = \Drupal::entityTypeManager()->getStorage('node')->load($nid);

// Load multiple entities (avoids N+1).
$nodes = \Drupal::entityTypeManager()->getStorage('node')->loadMultiple($nids);

// Create entity.
$node = Node::create([
  'type' => 'article',
  'title' => 'My Article',
  'field_tags' => [['target_id' => $tid]],
]);
$node->save();

// Query entities.
$nids = \Drupal::entityQuery('node')
  ->condition('type', 'article')
  ->condition('status', 1)
  ->accessCheck(TRUE)
  ->range(0, 10)
  ->execute();
```

## Field Storage Reusability

Share field storage across content types when the same concept applies:

```
# Good: shared storage
field_location (on event, venue, office)
field_contact_email (on person, organization, department)

# Bad: duplicated storage
field_event_location, field_venue_location, field_office_location
```

## View Modes

- `full`: Full content display.
- `teaser`: Summary/listing display.
- `search_result`: Search listing.
- Custom view modes for specific contexts (e.g., `card`, `sidebar`).

## Content Modeling Checklist

1. Identify fields that can share storage across bundles.
2. Select appropriate field types (not just "string" for everything).
3. Plan widget types for optimal editor experience.
4. Consider cardinality (single vs multi-value).
5. Plan required fields vs optional.
6. Document field purposes and usage.
7. Consider field display in different view modes.
