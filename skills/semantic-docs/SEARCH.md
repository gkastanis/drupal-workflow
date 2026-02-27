# Advanced Search Patterns

## Grep Patterns for Semantic Docs

### Search by Logic Type Tag
```bash
# Find all validation logic
grep -r "#LogicType:Validation" docs/semantic/tech/

# Find all storage logic
grep -r "#LogicType:Storage" docs/semantic/tech/

# Find all routing logic
grep -r "#LogicType:Routing" docs/semantic/tech/

# Find all transformation logic
grep -r "#LogicType:Transformation" docs/semantic/tech/
```

### Search by Drupal Component Type
```bash
# Find all hooks
grep -r "| Hook |" docs/semantic/tech/

# Find all services
grep -r "| Service |" docs/semantic/tech/

# Find all event subscribers
grep -r "| EventSubscriber |" docs/semantic/tech/

# Find all plugins
grep -r "| Plugin |" docs/semantic/tech/

# Find all controllers
grep -r "| Controller |" docs/semantic/tech/

# Find all forms
grep -r "| Form |" docs/semantic/tech/
```

### Search by Complexity
```bash
# Find high complexity implementations
grep -r "| High |" docs/semantic/tech/

# Find medium complexity
grep -r "| Medium |" docs/semantic/tech/

# Find low complexity
grep -r "| Low |" docs/semantic/tech/
```

### Search by File Path
```bash
# Find all references to a specific module
grep -r "module_name" docs/semantic/

# Find all controller references
grep -r "Controller" docs/semantic/tech/

# Find all form references
grep -r "Form" docs/semantic/tech/

# Find all service references
grep -r "Service" docs/semantic/tech/
```

### Search Business Index
```bash
# Find user stories mentioning a term
grep -i "keyword" docs/semantic/00_BUSINESS_INDEX.md

# Find all user stories
grep "^\- \*\*\[US-" docs/semantic/00_BUSINESS_INDEX.md

# Find cross-reference for a Logic ID
grep "FEATURE-L" docs/semantic/00_BUSINESS_INDEX.md

# List all features
grep "^\| \*\*" docs/semantic/00_BUSINESS_INDEX.md
```

### Search Entity Relationships
```bash
# Find all entity references
grep -r "field_" docs/semantic/schemas/

# Find entity relationships
grep -r "entity_reference" docs/semantic/schemas/

# Find required fields
grep -r '"required": true' docs/semantic/schemas/

# Find computed fields
grep -r '"computed": true' docs/semantic/schemas/
```

## Common Query Patterns

### "How does X work?"
1. Find feature code: `list-features.sh | grep -i "X"`
2. Read tech spec: `find-feature.sh FEATURE_CODE`
3. Check execution flow (Mermaid diagrams in tech specs)

### "Where is X implemented?"
1. Search business index: `grep -i "X" docs/semantic/00_BUSINESS_INDEX.md`
2. Get Logic ID from result
3. Trace to code: `trace-code.sh LOGIC-ID`

### "What triggers X?"
1. Find feature: `find-feature.sh FEATURE`
2. Look at "Execution Flow" section
3. Check "Integration Points" section

### "What fields does X have?"
1. Find entity schema: `find-entity.sh entity_name`
2. Review JSON structure
3. Check "business_purpose" for context

### "What depends on X?"
1. Search for references: `grep -r "LOGIC-ID" docs/semantic/`
2. Check "Code Dependencies" sections
3. Review integration points

## Logic ID Format

Logic IDs follow the pattern: `FEATURE-L#`

- **FEATURE**: 3-4 letter feature code (e.g., AUTH, ACCS)
- **L**: Literal "L" for "Logic"
- **#**: Sequential number (1, 2, 3...)

Examples:
- `AUTH-L1` - First authentication logic unit
- `ACCS-L3` - Third access control logic unit
- `MIGR-L10` - Tenth migration logic unit

## Semantic Tags Reference

Standard Drupal semantic tags used in documentation:

| Tag | Description | Example |
|-----|-------------|---------|
| `#LogicType:Validation` | Form validation, access checks | `hook_form_validate` |
| `#LogicType:Transformation` | Data processing, preprocessing | `hook_preprocess_*` |
| `#LogicType:Storage` | CRUD operations, presave | `hook_entity_presave` |
| `#LogicType:Routing` | Routes, controllers | `*.routing.yml` |
| `#LogicType:Rendering` | Output, theming | `build()` methods |
| `#LogicType:Query` | Database queries, entity queries | `hook_query_*_alter` |
| `#LogicType:Access` | Access control, permissions | `hook_access` |
| `#LogicType:Cache` | Caching logic | `#cache` metadata |
