---
name: drupal-brainstorming
description: |
  Explore requirements, constraints, and design options before implementing Drupal features.
  Use BEFORE writing code — when starting a new feature, module, or significant change.
  Produces a decision record with entity design, service architecture, and hook/event strategy.
metadata:
  status: stable
  drupal-version: "10+"
  last-reviewed: 2026-04
---

# Drupal Brainstorming

Structured exploration before implementation. Prevents the most expensive Drupal mistakes: wrong entity type, wrong test type, missing access control, unnecessary complexity.

## When to Use

- Starting a new feature or module
- Adding significant functionality to existing code
- Unsure whether to use a content entity, config entity, or neither
- Choosing between hooks, events, or plugins
- Multi-module changes with unclear blast radius

## Process (4 steps, ~5 minutes)

### Step 1: Clarify Intent

Ask yourself (or the user) these questions before anything else:

- **What problem does this solve?** (not what code to write)
- **Who uses it?** (admin, authenticated user, anonymous, API consumer, cron)
- **What already exists?** Run `discover deps:MODULE` or check the structural index
- **What's the simplest version that works?**

Do NOT skip this. The most common failure mode is building the wrong thing correctly.

### Step 2: Entity & Data Design

Drupal's most consequential early decision is how data is stored:

| If the data... | Use |
|----------------|-----|
| Has revisions, access control, fields, views | Content entity |
| Is site configuration (settings, mappings) | Config entity |
| Is transient/computed (cache, queue, state) | No entity — use State API, Queue, or cache |
| Is a simple key-value pair | `\Drupal::state()` or config |

**Common trap:** Creating a content entity when config entity or State API would suffice. Content entities are expensive (DB tables, access handlers, views integration). Only use them when you need the full entity lifecycle.

### Step 3: Architecture Sketch

For each component, decide:

| Concern | Options | Default choice |
|---------|---------|----------------|
| Business logic | Service class | Always a service, never in controller/hook |
| Data access | Entity API | Never raw SQL |
| User interaction | Form API + controller | Form for mutations, controller for display |
| Background work | Queue + AdvancedQueue | Not cron hooks |
| External calls | Guzzle via DI | Never `file_get_contents` |
| Events | EventSubscriber | Prefer over hooks for cross-module concerns |
| Display | Twig + preprocess | Heavy logic in preprocess, not Twig |

**Blast radius check:** Before multi-module changes, run `discover deps:FEATURE` to see what depends on what.

### Step 4: Decision Record

Document your decisions in 3-5 lines:

```
Entity: config entity (settings only, no revisions needed)
Services: my_module.processor (business logic), my_module.client (external API)
Hooks: hook_cron for scheduled check, #[Hook] attribute style
Access: custom permission 'administer my_module'
Test: Kernel test for service, Functional for admin form
```

This becomes the input for `writing-plans` or direct implementation.

## Anti-Patterns

- **Building before understanding** — writing code to "explore" instead of reading existing code
- **Entity sprawl** — creating entities for data that should be config or state
- **God services** — one service that does everything. Split by responsibility
- **Premature abstraction** — interfaces, plugins, and factories for things that have one implementation
- **Ignoring existing modules** — check if contrib already solves this before building custom

## Output

After brainstorming, you should have:

1. A clear problem statement (1-2 sentences)
2. Entity/data design decision with rationale
3. Service architecture sketch (which services, what they do)
4. Hook/event strategy
5. Test strategy (which test type, what to test)

Hand this to `writing-plans` for detailed implementation planning, or to `@drupal-builder` for direct implementation.
