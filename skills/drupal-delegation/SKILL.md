---
name: drupal-delegation
description: |
  Execute implementation plans by dispatching specialized Drupal agents in parallel.
  Use AFTER planning — when you have a plan with independent tasks to delegate.
  Dispatches @drupal-builder, @drupal-reviewer, @drupal-verifier with structural awareness.
metadata:
  status: stable
  drupal-version: "10+"
  last-reviewed: 2026-04
---

# Drupal Delegation

Parallel execution of implementation plans using the plugin's specialized agents.

## When to Use

- You have a plan with 2+ independent implementation tasks
- Multi-file or multi-module changes
- After `drupal-brainstorming` or `writing-plans` produced a plan
- The plan has tasks that can be worked on without shared state

## The Delegation Pattern

### Step 1: Check Preconditions

Before dispatching agents:

1. **Plan exists** — Do NOT delegate without a plan. If no plan exists, use `drupal-brainstorming` first
2. **Structural index is fresh** — Run `/drupal-status` to check. Agents need accurate structural data
3. **Tasks are independent** — Each agent task must be completable without waiting for another agent's output

### Step 2: Dispatch Specialized Agents

Use the right agent for each task type:

| Task Type | Agent | Model | When |
|-----------|-------|-------|------|
| New code, services, entities, hooks | `@drupal-builder` | opus | Implementation work |
| Architecture review, security audit | `@drupal-reviewer` | sonnet | After implementation |
| Smoke tests, drush eval, config checks | `@drupal-verifier` | sonnet | After implementation |
| Semantic docs, tech specs | `@semantic-architect` | sonnet | After structural changes |

**Dispatch in parallel** when tasks are independent:

```
Agent({ subagent_type: "drupal-workflow:drupal-builder", description: "Implement X", prompt: "..." })
Agent({ subagent_type: "drupal-workflow:drupal-builder", description: "Implement Y", prompt: "..." })
```

**Dispatch sequentially** when one depends on another:

```
1. @drupal-builder implements the feature
2. @drupal-reviewer reviews the implementation
3. @drupal-verifier verifies it works
```

### Step 3: Write Agent Prompts

Each agent prompt MUST be self-contained. The agent has NO context from this conversation.

Include in every prompt:
- **What** to implement (exact requirements)
- **Where** (file paths from the plan)
- **How** (specific patterns: DI, #[Hook] attributes, accessCheck)
- **Verification** (how to confirm it works)

Bad prompt: "Implement the feature from the plan"
Good prompt: "Create a service at code/my_module/src/Service/Calculator.php that implements CalculatorInterface with method add(int, int): int. Register in my_module.services.yml with interface type-hint. Verify with: ddev drush eval '...'"

### Step 4: Track Progress

Create a task for each delegated unit:

```
TaskCreate({ description: "Implement Calculator service" })
TaskCreate({ description: "Implement admin form" })
TaskCreate({ description: "Verify all services" })
```

Update tasks as agents complete. This creates a visible progress trail.

### Step 5: Verify After All Agents Complete

After all agents finish:

1. **Review outputs** — read what each agent produced
2. **Dispatch @drupal-verifier** — verify the combined result works
3. **Check blast radius** — run `discover deps:FEATURE` to confirm no unintended side effects

## Dispatch Rules

- **Use `run_in_background: true`** for agents that don't block subsequent work
- **Never dispatch more than 4 agents simultaneously** — diminishing returns on context
- **Include structural context** in prompts when agents need to understand dependencies
- **Do NOT delegate understanding** — you synthesize results, agents execute specific tasks

## Anti-Patterns

- Delegating without a plan (random agent dispatches)
- Using `general-purpose` agents for Drupal work (use specialized agents)
- Writing vague prompts ("based on the plan, implement it")
- Skipping verification after agent completion
- Dispatching dependent tasks in parallel

## Relationship to Other Skills

```
drupal-brainstorming → writing-plans → drupal-delegation → verification-before-completion
        ↑                                      ↓
        └─── If delegation reveals gaps ───────┘
```
