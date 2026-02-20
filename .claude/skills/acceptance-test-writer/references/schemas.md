---
title: "Schemas"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# YAML Schemas for Acceptance Tests

Complete schema definitions for acceptance test files.

## Manifest Schema

```yaml
# acceptance-tests/PRD-XXX/manifest.yaml

# Required fields
prd_id: string                    # Unique PRD identifier (e.g., "PRD-AUTH-001")
prd_title: string                 # Human-readable title
prd_source: string                # Relative path to source PRD markdown
generated: string                 # ISO8601 timestamp of generation
generated_by: string              # Should be "acceptance-test-writer"

# Features list (required, at least one)
features:
  - id: string                    # Feature identifier (e.g., "F1")
    name: string                  # Feature name
    description: string           # Brief description
    acceptance_criteria:          # List of AC IDs belonging to this feature
      - string                    # e.g., "AC-user-login"

# Optional fields
task_mapping:                     # Map features to task IDs for traceability
  F1: ["TASK-101", "TASK-102"]
  F2: ["TASK-103"]

environment:                      # Environment requirements
  base_url: string                # e.g., "http://localhost:3000"
  api_url: string                 # e.g., "http://localhost:8000"

test_data:                        # Shared test data
  users:
    - email: string
      password: string
      role: string
```

## Acceptance Criterion Schema

```yaml
# acceptance-tests/PRD-XXX/AC-{name}.yaml

# Identity (required)
id: string                        # Unique ID matching filename (e.g., "AC-user-login")
feature: string                   # Parent feature ID (e.g., "F1")
title: string                     # One-line description
description: |                    # Multi-line detailed description
  Full description of what this criterion validates.

# Traceability (required)
prd_reference: string             # "PRD-XXX, Section X.X, Requirement RX"

# Classification (required)
validation_type: enum             # browser | api | hybrid
priority: enum                    # critical | high | medium | low

# Preconditions (required, can be empty list)
preconditions:
  - description: string           # What must be true
    details: string               # Specific values/setup needed

# Test Steps (required, at least one)
steps:
  - id: string                    # Step identifier (e.g., "step-1")
    action: string                # Action type (see action-catalog.md)
    # Action-specific fields vary by action type
    description: string           # Human-readable step description
    screenshot: boolean           # Optional: capture screenshot after step

# Expected Outcome (required)
expected_outcome: |
  Multi-line description of what success looks like.

# Failure Indicators (required)
failure_indicators:
  - string                        # Ways to recognize this test failed

# Evidence Requirements (required)
evidence:
  - type: enum                    # screenshot | api_response | console_log
    when: enum                    # on_success | on_failure | always | on_step
    step_id: string               # If when=on_step, which step
    filename: string              # Output filename
    description: string           # What this evidence shows
    capture: enum                 # For api_response: full | body_only | headers_only
```

## Step Action Schemas

### Browser Actions

```yaml
# Navigate to URL
- id: string
  action: navigate
  target: string                  # URL path (e.g., "/login")
  description: string

# Fill input field
- id: string
  action: fill
  selector: string                # CSS selector
  value: string                   # Value to enter
  description: string

# Click element
- id: string
  action: click
  selector: string                # CSS selector
  description: string

# Assert element visible
- id: string
  action: assert_visible
  selector: string                # CSS selector
  contains: string                # Optional: text that should be present
  description: string
  screenshot: boolean             # Optional

# Assert URL
- id: string
  action: assert_url
  pattern: string                 # URL pattern to match
  description: string

# Wait for navigation
- id: string
  action: wait_for_navigation
  timeout_ms: integer             # Timeout in milliseconds
  description: string

# Wait for element
- id: string
  action: wait_for_element
  selector: string                # CSS selector
  timeout_ms: integer             # Timeout in milliseconds
  description: string

# Assert text content
- id: string
  action: assert_text
  selector: string                # CSS selector
  contains: string                # Text to find
  description: string

# Assert element not visible
- id: string
  action: assert_not_visible
  selector: string                # CSS selector
  description: string

# Capture screenshot
- id: string
  action: screenshot
  filename: string                # Output filename
  description: string

# Select dropdown option
- id: string
  action: select
  selector: string                # CSS selector
  value: string                   # Option value
  description: string

# Check/uncheck checkbox
- id: string
  action: check
  selector: string                # CSS selector
  checked: boolean                # true to check, false to uncheck
  description: string

# Hover over element
- id: string
  action: hover
  selector: string                # CSS selector
  description: string

# Press keyboard key
- id: string
  action: press_key
  key: string                     # Key name (e.g., "Enter", "Escape")
  description: string

# Clear input field
- id: string
  action: clear
  selector: string                # CSS selector
  description: string
```

### API Actions

```yaml
# Make API request
- id: string
  action: api_request
  method: enum                    # GET | POST | PUT | PATCH | DELETE
  url: string                     # API endpoint path
  headers:                        # Optional headers
    Authorization: string
    Content-Type: string
  body: object | string           # Optional request body
  description: string

# Assert HTTP status
- id: string
  action: assert_status
  expected: integer               # Expected status code
  description: string

# Assert JSON response
- id: string
  action: assert_json
  path: string                    # JSONPath expression (e.g., "$.data.id")
  expected: any                   # Expected value
  description: string

# Assert response header
- id: string
  action: assert_header
  header: string                  # Header name
  expected: string                # Expected value
  description: string

# Assert response contains
- id: string
  action: assert_response_contains
  text: string                    # Text to find in response body
  description: string

# Store response value
- id: string
  action: store_value
  path: string                    # JSONPath to extract
  variable: string                # Variable name to store
  description: string

# Use stored value
# In subsequent steps, use ${variable_name} syntax
```

### Hybrid Actions

```yaml
# Wait for API response (after UI action)
- id: string
  action: wait_for_api
  url_pattern: string             # URL pattern to match
  method: enum                    # Expected method
  timeout_ms: integer
  description: string

# Assert API called (verify UI triggered API)
- id: string
  action: assert_api_called
  url_pattern: string
  method: enum
  expected_body: object           # Optional: expected request body
  description: string
```

### Utility Actions

```yaml
# Wait fixed time (use sparingly)
- id: string
  action: wait
  duration_ms: integer
  description: string

# Log message (for debugging)
- id: string
  action: log
  message: string
  description: string

# Conditional step
- id: string
  action: if_visible
  selector: string                # Check if element exists
  then:                           # Steps to run if visible
    - action: click
      selector: string
  description: string
```

## Validation Rules

### Required Field Combinations

| validation_type | Required step actions |
|-----------------|----------------------|
| browser | At least one of: navigate, click, fill, assert_visible |
| api | At least one of: api_request, assert_status |
| hybrid | At least one browser action AND one API action |

### ID Naming Conventions

- Manifest `prd_id`: `PRD-{CATEGORY}-{NUMBER}` (e.g., `PRD-AUTH-001`)
- Feature `id`: `F{NUMBER}` (e.g., `F1`, `F2`)
- Criterion `id`: `AC-{descriptive-name}` (e.g., `AC-user-login`)
- Step `id`: `step-{number}` (e.g., `step-1`, `step-2`)

### Filename Conventions

- Criterion files: `AC-{id-without-AC-prefix}.yaml` matching the `id` field
- Evidence files: `{criterion-id}-{description}.{ext}`
