---
name: drupal-conventions
description: Load Drupal-specific conventions (translations, CSS, error handling) on demand. Use when working on theming, translations, or exception handling.
---

# Drupal Conventions (JIT)

Load these conventions only when relevant to the current task.

## Translation Rules

- Wrap all user-facing text in `t()` or `TranslatableMarkup`.
- Use module name as context (PHP string, not constant).
- English in code, translations in `/translations/*.po` files with `msgctxt`.
- Twig: `|t` filter for strings, `{% trans %}` blocks for placeholders.
- PO format: `msgctxt "my_module"` / `msgid "English"` / `msgstr "Translated"`.

## CSS Conventions

- Target specific elements (`.parent .child`), not parent containers.
- BEM: `block__element--modifier` strictly for custom classes.
- Use `{{ attach_library('my_theme/component') }}` for all assets.
- Every asset bundle needs a matching `*.libraries.yml` entry.
- Mobile-first responsive design. Use Drupal breakpoints for responsive images.

## Error Handling

- Use exceptions for errors, not `NULL`/`FALSE` returns.
- Never catch `\Exception` — catch the narrowest exception you can handle.
- Don't catch just to log (unless error doesn't affect caller).
- Return early with clear error messages (fail fast).
