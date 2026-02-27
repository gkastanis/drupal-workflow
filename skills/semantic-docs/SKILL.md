---
name: semantic-docs
description: Navigate semantic documentation in docs/semantic/ that maps business logic to Drupal code. Use this skill when asking how features work (authentication, content types, views, migrations, access control, workflows, caching, theming, forms, blocks, entities). Search by Logic ID (AUTH-L1), feature code (MIGR), user story (US-001), or entity schema. Answers "where is X implemented?", "how does X work?", "what code handles X?".
---

# Semantic Documentation Navigator

Search business-logic-to-code mappings in `docs/semantic/`.

## Quick Commands

**Find by Logic ID:**
```bash
$SKILL_DIR/scripts/find-logic-id.sh AUTH-L2
```
Returns: code location, file path, complexity

**Find by Feature:**
```bash
$SKILL_DIR/scripts/find-feature.sh ACCS
```
Returns: full technical spec

**Find Entity Schema:**
```bash
$SKILL_DIR/scripts/find-entity.sh user
```
Returns: JSON schema with fields and relationships

**Find User Story:**
```bash
$SKILL_DIR/scripts/find-user-story.sh US-004
```
Returns: user story with linked Logic IDs

**List All Features:**
```bash
$SKILL_DIR/scripts/list-features.sh
```
Returns: feature registry table from business index

**Trace Code Location:**
```bash
$SKILL_DIR/scripts/trace-code.sh ARCH-L1
```
Returns: exact file:line:function for implementation

## Documentation Structure

```
docs/semantic/
├── 00_BUSINESS_INDEX.md    # Master index (read first for overview)
├── tech/*.md               # Technical specs by feature
├── schemas/*.json          # Entity schemas
└── SUMMARY.md              # Quick reference (if available)
```

## Logic ID Format

Logic IDs follow the pattern: `FEATURE-L#`
- **FEATURE**: 3-4 letter feature code
- **L**: Literal "L" for "Logic"
- **#**: Sequential number

Examples: `AUTH-L1`, `ACCS-L3`, `MIGR-L10`

## Common Drupal Feature Codes

| Code | Feature Domain |
|------|----------------|
| AUTH | Authentication & Login |
| ACCS | Access Control |
| CONT | Content Types |
| MIGR | Migrations |
| VIEW | Views & Displays |
| FORM | Forms & Validation |
| BLOC | Blocks & Regions |
| CACH | Caching |
| THEM | Theming |
| HOOK | Hook Implementations |
| SERV | Services |
| PLUG | Plugins |
| ROUT | Routing |
| CONF | Configuration |

## When This Skill Triggers

- "Where is [business rule] implemented?"
- "What does [Logic ID] do?"
- "Show me the [feature] technical spec"
- "What fields does [entity] have?"
- "How does [workflow] execute?"
- "Which code handles [user story]?"
- "List all features"
- "Find [module] code locations"

## Manual Search

If scripts don't find what you need:

```bash
# Search business index
grep -i "keyword" docs/semantic/00_BUSINESS_INDEX.md

# Search all tech docs
grep -r "keyword" docs/semantic/tech/

# List available features
ls docs/semantic/tech/*.md | sed 's/.*\///' | sed 's/_.*$//' | sort -u

# List available schemas
ls docs/semantic/schemas/*.json | sed 's/.*\///' | sed 's/\.json$//'
```

## Advanced Search

For grep patterns and complex queries, see [SEARCH.md](SEARCH.md).
For entity schema details, see [ENTITY-LOOKUP.md](ENTITY-LOOKUP.md).
