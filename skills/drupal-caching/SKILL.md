# Drupal Caching

name: drupal-caching
description: >
  Cache bins, tags, contexts, invalidation strategies, and external caching
  for Drupal 10/11. Use when implementing caching, optimizing performance,
  or configuring cache backends.

---

## Cache Metadata (Render Arrays)

Every render array should include cache metadata:

```php
$build = [
  '#theme' => 'my_template',
  '#data' => $data,
  '#cache' => [
    'keys' => ['my_module', 'block', $id],
    'contexts' => ['user', 'url.query_args'],
    'tags' => ['node:' . $nid, 'node_list'],
    'max-age' => 3600,
  ],
];
```

## Cache Contexts

| Context | Varies By | Use When |
|---|---|---|
| `user` | Current user ID | Content per user |
| `user.roles` | User roles | Content per role |
| `user.permissions` | Permissions | Access-dependent |
| `url` | Full URL | Page-specific |
| `url.path` | URL path only | Path-dependent |
| `url.query_args` | Query parameters | Filtered content |
| `languages` | Current language | Multilingual |
| `theme` | Active theme | Theme-specific |
| `session` | Session ID | Session-dependent |

## Cache Tags

```php
// Entity-based tags (auto-invalidated).
'tags' => ['node:42']           // Specific node.
'tags' => ['node_list']         // Any node list.
'tags' => ['taxonomy_term:5']   // Specific term.
'tags' => ['config:system.site'] // Config object.

// Custom tags.
'tags' => ['my_module:feature_x']
```

## Cache Invalidation

```php
// Invalidate by tags.
\Drupal::service('cache_tags.invalidator')
  ->invalidateTags(['node:42', 'my_module:feature_x']);

// Clear specific cache bin.
\Drupal::cache('render')->invalidateAll();

// Delete specific cache item.
\Drupal::cache('default')->delete('my_module:cache_key');
```

## Cache Bins

| Bin | Purpose |
|---|---|
| `default` | General-purpose |
| `render` | Render arrays |
| `page` | Full page cache |
| `dynamic_page_cache` | Authenticated pages |
| `discovery` | Plugin discovery |
| `data` | Data processing |
| `config` | Configuration |
| `menu` | Menu trees |

## External Cache Backends

### Redis Configuration

```php
// settings.php
$settings['redis.connection']['interface'] = 'PhpRedis';
$settings['redis.connection']['host'] = '127.0.0.1';
$settings['cache']['default'] = 'cache.backend.redis';
```

### Varnish Headers

```php
// Ensure proper cache headers.
$response->headers->set('Cache-Control', 'public, max-age=3600');
$response->headers->set('Surrogate-Control', 'max-age=86400');
```

## Caching Layers

1. **Internal Page Cache** - Anonymous users (built-in).
2. **Dynamic Page Cache** - Authenticated users (built-in).
3. **Render Cache** - Render arrays (`#cache`).
4. **Cache Backends** - Redis, Memcached.
5. **Reverse Proxy** - Varnish, CDN.

## Avoiding N+1 Queries

```php
// Bad: N queries.
foreach ($nids as $nid) {
  $node = Node::load($nid);
}

// Good: 1 query.
$nodes = Node::loadMultiple($nids);
```

## Performance Checklist

- CSS/JS aggregation enabled in production.
- Redis/Memcache configured for cache backend.
- No N+1 query problems.
- Image optimization enabled (WebP, lazy loading).
- BigPipe enabled for authenticated users.
- Entity queries use `accessCheck()` explicitly.
- Views use caching with appropriate tags.
