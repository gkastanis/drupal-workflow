# Entity Schema Reference

## Using Entity Schemas

Entity schemas are stored in `docs/semantic/schemas/` as JSON files. They document:
- Field definitions with types
- Entity relationships
- Business purpose for each field
- Storage and cardinality information

## Quick Entity Lookup

```bash
# List all schemas
ls docs/semantic/schemas/

# View specific schema
cat docs/semantic/schemas/ENTITY_NAME.json

# Pretty print with jq
cat docs/semantic/schemas/ENTITY_NAME.json | jq .

# Find fields by type
grep -l "entity_reference" docs/semantic/schemas/*.json

# Find required fields
grep -r '"required": true' docs/semantic/schemas/
```

## Schema Structure

Each schema JSON follows this structure:

```json
{
  "entity": "entity_type",
  "bundle": "bundle_name",
  "fields": {
    "field_name": {
      "type": "field_type",
      "target_type": "target_entity (for references)",
      "target_bundle": "target_bundle (for references)",
      "cardinality": 1,
      "required": true,
      "description": "Technical description",
      "business_purpose": "Why this field exists"
    }
  }
}
```

## Drupal Field Type Reference

| Type | Description | Example |
|------|-------------|---------|
| `string` | Plain text | `field_external_id` |
| `text_long` | Rich text with format | `body` |
| `text_with_summary` | Body field with summary | `body` |
| `entity_reference` | Link to another entity | `field_author` -> user |
| `taxonomy_term_reference` | Link to taxonomy | `field_tags` -> tags |
| `datetime` | Date/time value | `field_event_date` |
| `boolean` | True/false | `field_published` |
| `file` | File attachment | `field_attachments` |
| `image` | Image field | `field_thumbnail` |
| `integer` | Whole number | `field_weight` |
| `decimal` | Decimal number | `field_price` |
| `list_string` | Select list | `field_status` |
| `computed` | Calculated value | `field_full_name` |
| `link` | URL field | `field_website` |
| `address` | Address field | `field_location` |
| `telephone` | Phone number | `field_phone` |
| `email` | Email address | `field_contact_email` |

## Common Drupal Field Patterns

### Access Control Fields
Fields that determine who can access content:
- `uid` / `field_author` - Content ownership
- `field_access_group` - Group-based access
- `field_visibility` - Public/private setting
- `status` - Published/unpublished

### Lifecycle Fields
Fields that manage content lifecycle:
- `created` / `changed` - Timestamps
- `field_publish_date` - Scheduled publishing
- `field_unpublish_date` - Scheduled unpublishing
- `field_archived` - Archive status
- `moderation_state` - Content moderation

### Categorization Fields
Fields for organizing content:
- `field_tags` - Tagging taxonomy
- `field_category` - Primary category
- `field_type` - Content subtype
- `field_topics` - Topic taxonomy

### Relationship Fields
Fields linking to other entities:
- `field_related_content` - Related nodes
- `field_parent` - Hierarchical parent
- `field_references` - General references
- `field_media` - Media references

### Media Fields
Fields for media handling:
- `field_image` - Image with alt text
- `field_media` - Media entity reference
- `field_file` - File attachments
- `field_gallery` - Multiple images

## Finding Entity Information

### From Business Index
```bash
# Find entities mentioned in user stories
grep -i "entity" docs/semantic/00_BUSINESS_INDEX.md

# Find entity relationship diagram
grep -A 50 "Entity Relationship" docs/semantic/00_BUSINESS_INDEX.md
```

### From Tech Specs
```bash
# Find data structure schemas in tech docs
grep -A 30 "Data Structure Schema" docs/semantic/tech/*.md

# Find entity references in logic mappings
grep "entity" docs/semantic/tech/*.md
```

### From Drupal Configuration
```bash
# List content types
drush config:list | grep "node.type"

# Get content type config
drush config:get node.type.article

# List field storage
drush config:list | grep "field.storage"

# Get field config
drush config:get field.field.node.article.body
```

## Cardinality Values

| Value | Meaning |
|-------|---------|
| `1` | Single value |
| `-1` | Unlimited values |
| `N` | Fixed limit of N values |

## Entity Types in Drupal

| Entity Type | Description | Base Table |
|-------------|-------------|------------|
| `node` | Content nodes | `node` |
| `user` | User accounts | `users` |
| `taxonomy_term` | Taxonomy terms | `taxonomy_term_data` |
| `file` | File entities | `file_managed` |
| `media` | Media entities | `media` |
| `paragraph` | Paragraph items | `paragraphs_item` |
| `block_content` | Custom blocks | `block_content` |
| `menu_link_content` | Menu links | `menu_link_content_data` |
| `comment` | Comments | `comment` |
