---
name: acceptance-test-writer
description: >
  This skill should be used when the user asks to "generate acceptance tests",
  "create acceptance criteria tests", "write E2E test scripts from PRD",
  "set up acceptance testing for PRD-XXX", "convert PRD to testable criteria",
  or when starting implementation of a new PRD and acceptance tests don't exist.
  Generates executable YAML test scripts from PRD documents.
title: "Acceptance Test Writer"
status: active
---

# Acceptance Test Writer

Generate executable YAML acceptance test scripts from PRD documents, enabling automated validation that implementations meet business requirements.

## Purpose

Transform PRD acceptance criteria into structured, executable test definitions that:
- Define clear PASS/FAIL conditions linked to PRD requirements
- Specify exact validation steps (browser actions, API calls)
- Capture evidence requirements (screenshots, response bodies)
- Enable the `acceptance-test-runner` skill to validate implementations

## When to Use

Invoke this skill:
- After finalizing a PRD document
- Before starting implementation of a new feature
- When acceptance tests don't exist for a PRD (`acceptance-tests/PRD-XXX/` missing)

## Input Requirements

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--prd` | **Auto-detected** | PRD identifier - extracted from YAML frontmatter if present |
| `--source` | Yes | Path to PRD markdown file |

**PRD ID Detection Priority:**
1. **YAML frontmatter** (preferred) - Look for `prd_id:` in the source document
2. **`--prd` argument** - Explicit override if frontmatter missing
3. **Error** - If neither is found, fail with clear message

Example invocations:
```bash
# Auto-detect from frontmatter (PREFERRED)
Skill("acceptance-test-writer", args="--source=docs/prds/auth-system.md")

# Explicit override (when frontmatter missing or for legacy PRDs)
Skill("acceptance-test-writer", args="--prd=PRD-AUTH-001 --source=docs/prds/auth-system.md")
```

### PRD Frontmatter Format

The PRD source document should have YAML frontmatter with `prd_id`:

```yaml
prd_id: PRD-AUTH-001
title: "User Authentication System"
product: "AgenCheck"
version: "1.0"
status: active
created: "2026-01-15"
author: "Product Team"
```

**Parsing Logic:**
1. Read source file
2. Look for YAML block (between triple backticks with `yaml` or fenced with `---`)
3. Extract `prd_id` field
4. If `--prd` argument provided, use it as override
5. If no `prd_id` found and no `--prd` argument, fail with:
   ```
   ERROR: No PRD ID found. Either:
   - Add prd_id to document frontmatter, or
   - Provide --prd=PRD-XXX argument
   ```

## Output Structure

```
acceptance-tests/
└── PRD-{identifier}/
    ├── manifest.yaml           # PRD metadata, feature list
    ├── AC-{criterion-1}.yaml   # One file per acceptance criterion
    ├── AC-{criterion-2}.yaml
    └── ...
```

## Workflow

### Step 0: Extract PRD ID (MANDATORY)

**Before anything else, determine the canonical PRD ID.**

```python
# Pseudocode for PRD ID extraction
def extract_prd_id(source_path, prd_override=None):
    content = read_file(source_path)

    # Look for YAML frontmatter (```yaml ... ``` or --- ... ---)
    yaml_match = regex_search(r'```yaml\n(.*?)\n```', content, DOTALL)
    if not yaml_match:
        yaml_match = regex_search(r'^---\n(.*?)\n---', content, DOTALL)

    if yaml_match:
        frontmatter = parse_yaml(yaml_match.group(1))
        prd_id = frontmatter.get('prd_id')
        if prd_id:
            return prd_override or prd_id  # Override wins if provided

    if prd_override:
        return prd_override

    raise Error("No PRD ID found. Add prd_id to frontmatter or provide --prd argument")
```

**Output**: Canonical `prd_id` string (e.g., `PRD-AUTH-001`)

### Step 1: Read and Parse PRD

Read the source PRD document. Extract:
- PRD title and identifier (use `prd_id` from Step 0)
- Features/epics with descriptions
- Acceptance criteria (look for sections titled "Acceptance Criteria", "Definition of Done", "Success Criteria", or numbered requirements)
- User flows and scenarios
- API contracts (if specified)
- UI requirements (if specified)

### Step 2: Identify Acceptance Criteria

For each feature, identify testable acceptance criteria. Common patterns in PRDs:

| PRD Pattern | Maps To |
|-------------|---------|
| "User can..." | Browser test with user flow |
| "System shall..." | API or integration test |
| "When X, then Y" | Conditional behavior test |
| "API returns..." | API response validation |
| "Page displays..." | UI element assertion |

### Step 3: Determine Validation Type

For each criterion, classify:

| Type | When to Use | Tools |
|------|-------------|-------|
| `browser` | UI interactions, visual verification | chrome-devtools MCP |
| `api` | Backend endpoints, data validation | curl, httpx |
| `hybrid` | UI triggers API, verify both | Both |

### Step 4: Generate Test Steps

Convert acceptance criteria into executable steps. Map natural language to actions:

| PRD Language | Action | Example |
|--------------|--------|---------|
| "navigate to", "go to" | `navigate` | `target: "/login"` |
| "enter", "fill in", "type" | `fill` | `selector: "[data-testid='email']"` |
| "click", "press", "submit" | `click` | `selector: "[data-testid='submit']"` |
| "should see", "displays" | `assert_visible` | `selector: ".success-message"` |
| "redirected to" | `assert_url` | `pattern: "/dashboard"` |
| "returns", "responds with" | `assert_status` | `expected: 200` |
| "contains", "shows" | `assert_text` | `contains: "Welcome"` |

### Step 5: Define Evidence Requirements

Each criterion should specify evidence to capture:
- **Browser tests**: Screenshots at key steps and on completion
- **API tests**: Full response capture (headers + body)
- **Hybrid tests**: Both screenshots and API responses

### Step 6: Create Manifest

Generate `manifest.yaml` linking all criteria to features and PRD source.

### Step 7: Write YAML Files

Create all files in `acceptance-tests/PRD-XXX/`:
1. Write `manifest.yaml` first
2. Write one `AC-{name}.yaml` per criterion
3. Verify all files are valid YAML

## YAML Schemas

### Manifest Schema

See `references/schemas.md` for complete manifest.yaml schema.

Key fields:
```yaml
prd_id: string          # PRD identifier
prd_title: string       # Human-readable title
prd_source: string      # Path to source PRD
generated: ISO8601      # Generation timestamp
features: []            # List of features with criteria
task_mapping: {}        # Optional: feature to task IDs
```

### Acceptance Criterion Schema

See `references/schemas.md` for complete AC-*.yaml schema.

Key fields:
```yaml
id: string              # Unique criterion ID (e.g., AC-user-login)
feature: string         # Feature ID this belongs to
title: string           # One-line description
description: string     # Detailed description
prd_reference: string   # Section/requirement in PRD
validation_type: browser|api|hybrid
priority: critical|high|medium|low
preconditions: []       # What must be true before test
steps: []               # Executable test steps
expected_outcome: string
failure_indicators: []  # How to recognize failure
evidence: []            # What to capture
```

## Best Practices

### Selector Strategy

Prefer selectors in this order:
1. `[data-testid='...']` - Most stable, designed for testing
2. `[aria-label='...']` - Accessibility-friendly
3. `#id` - Unique but may change
4. `.class` - Least stable, avoid if possible

### Step Granularity

- One action per step (don't combine fill + click)
- Include `screenshot: true` at verification points
- Add `wait_for_navigation` after clicks that trigger page loads

### Preconditions

Be explicit about test data requirements:
- User accounts that must exist
- Database state required
- Services that must be running
- Environment variables needed

### Failure Indicators

Help the runner understand what failure looks like:
- Error messages that might appear
- URLs that indicate wrong navigation
- HTTP status codes that indicate problems

## Example Workflow

Given a PRD section:
```markdown
## 3.1 User Login

Users must be able to log in with their email and password.

**Acceptance Criteria:**
1. User can log in with valid credentials and see dashboard
2. Invalid credentials show error message
3. Locked accounts show "account locked" message
```

Generate:
1. `AC-user-login-valid.yaml` - Happy path login
2. `AC-user-login-invalid.yaml` - Error handling
3. `AC-user-login-locked.yaml` - Account lock handling

## Additional Resources

### Reference Files

- **`references/schemas.md`** - Complete YAML schemas for manifest and criteria
- **`references/action-catalog.md`** - All supported test actions with parameters

### Example Files

- **`examples/manifest.yaml`** - Sample manifest file
- **`examples/AC-browser-test.yaml`** - Browser validation example
- **`examples/AC-api-test.yaml`** - API validation example
- **`examples/AC-hybrid-test.yaml`** - Hybrid validation example

## Validation Checklist

Before completing, verify:
- [ ] All PRD acceptance criteria have corresponding AC-*.yaml files
- [ ] Manifest lists all features and their criteria
- [ ] Each criterion has valid `validation_type`
- [ ] All steps use supported actions (see `references/action-catalog.md`)
- [ ] Evidence requirements specified for each criterion
- [ ] Preconditions are explicit and achievable
- [ ] YAML files are syntactically valid
