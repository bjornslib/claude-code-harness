# Test Specification Format Standard

This document defines the standard markdown format for browser, API, and visual test specifications that Claude in Chrome agents can parse and execute. All test specs in `docs/tests/specs/` must conform to this format.

## Frontmatter (YAML)

Every test spec begins with YAML frontmatter delimited by `---`. All fields are required unless marked optional.

```yaml
---
title: "Human-readable test title"
type: e2e-browser|api|visual
service: frontend|backend|eddy-validate|user-chat
port: 5001|8000|5184|5185
prerequisites:
  - "Service X running on port Y"
  - "Test data seeded (if applicable)"
tags: [smoke, regression, critical]
estimated_duration: "2-5 minutes"
---
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Descriptive test name |
| `type` | enum | Yes | One of: `e2e-browser`, `api`, `visual` |
| `service` | enum | Yes | Target service: `frontend`, `backend`, `eddy-validate`, `user-chat` |
| `port` | integer | Yes | Port the service under test listens on |
| `prerequisites` | list | Yes | Conditions that must be true before execution |
| `tags` | list | Yes | Classification tags for filtering and reporting |
| `estimated_duration` | string | Yes | Human-readable time estimate |

### Service-to-Port Mapping

| Service | Default Port | Description |
|---------|-------------|-------------|
| `frontend` | 5001 | AgenCheck chat frontend (Next.js) |
| `backend` | 8000 | AgenCheck backend API (FastAPI) |
| `eddy-validate` | 5184 | Eddy validation service |
| `user-chat` | 5185 | User chat relay service |

---

## Steps Section

The `## Steps` section contains numbered steps. Each step starts with a bold **action verb** and includes target and expected result information.

### Supported Action Verbs

| Verb | Purpose | Requires Target | Produces Evidence |
|------|---------|-----------------|-------------------|
| **Navigate** | Load a URL in the browser | URL | No |
| **Click** | Click an element on the page | CSS selector or description | No |
| **Fill** | Enter text into a form field | CSS selector or description + value | No |
| **Wait** | Pause until a condition is met | Condition description + timeout | No |
| **Assert** | Verify page state or content | Expected content or condition | No |
| **Capture** | Take a screenshot for evidence | Screenshot filename | Yes |

### Step Structure

Each step follows this pattern:

```markdown
N. **Verb** description of the action
   - Target: `[data-testid="element-id"]` or natural language description
   - Expected: Description of the expected outcome after this step
```

The `Target` line is optional for steps where the target is embedded in the description (e.g., Navigate steps where the URL is inline). The `Expected` line is always required.

### Example Steps Section

```markdown
## Steps

1. **Navigate** to `http://localhost:5001`
   - Expected: Page loads with chat interface visible

2. **Fill** the message input with "Can you verify MIT credentials?"
   - Target: `[data-testid="message-input"]` or message input textarea
   - Expected: Text appears in input field

3. **Click** the Send button
   - Target: `[data-testid="send-button"]`
   - Expected: Message appears in chat thread

4. **Wait** for assistant response (timeout: 30s)
   - Expected: Assistant response appears below user message

5. **Assert** response contains credential verification information
   - Expected: Response mentions "MIT" and verification process

6. **Capture** screenshot of completed exchange
   - Target: `screenshots/06-exchange-complete.png`
   - Expected: Screenshot saved showing full conversation
```

### Step Verb Guidelines

- **Navigate**: Always provide a full URL including protocol and port. Use `http://localhost:{port}` for local services.
- **Click**: Prefer `[data-testid="..."]` selectors. Fall back to natural language descriptions when test IDs are unavailable.
- **Fill**: Specify both the target element and the text to enter. Quote the input value.
- **Wait**: Always include a timeout value in parentheses. Specify what condition to poll for.
- **Assert**: Describe the expected state clearly. Multiple conditions can be listed as sub-bullets.
- **Capture**: Provide a descriptive filename in `screenshots/` directory. Use zero-padded step numbers as prefix.

---

## Evidence Section

The `## Evidence` section maps steps to screenshots and provides descriptions for review.

```markdown
## Evidence

| Step | Screenshot | Description |
|------|-----------|-------------|
| 1 | `screenshots/01-page-loaded.png` | Initial page state after navigation |
| 3 | `screenshots/03-message-sent.png` | Chat thread after sending message |
| 5 | `screenshots/05-response-received.png` | Assistant response visible |
```

### Evidence Guidelines

- Not every step requires a screenshot. Focus on state transitions and assertion points.
- Screenshot filenames use the pattern: `screenshots/{step-number-zero-padded}-{description}.png`
- The `Description` column should explain what the screenshot proves.
- Capture steps automatically generate evidence entries. Assert and Navigate steps should have evidence when they represent key state changes.

---

## Pass/Fail Criteria

The `## Pass/Fail Criteria` section defines explicit conditions for the test to be considered passing.

```markdown
## Pass/Fail Criteria

- ALL Assert steps must pass
- Screenshots captured for all evidence steps listed above
- No unhandled console errors during execution
- Page renders without layout breakage (for visual tests)
- Response times within expected thresholds (for API tests)
```

### Standard Criteria by Test Type

**e2e-browser tests**:
- All Assert steps pass
- All evidence screenshots captured
- No unhandled JavaScript errors in console
- No network request failures (except expected ones)

**api tests**:
- All Assert steps on response status and body pass
- Response times within documented thresholds
- Response schemas match expected structure

**visual tests**:
- All Assert steps on visual appearance pass
- All evidence screenshots captured
- No layout shifts or rendering defects
- Responsive breakpoints render correctly (if tested)

---

## Tool Mapping (Claude in Chrome)

This section maps test spec action verbs to the actual MCP tools that a Claude in Chrome agent uses for execution.

| Step Verb | MCP Tool | Parameters | Notes |
|-----------|----------|------------|-------|
| **Navigate** | `mcp__claude-in-chrome__navigate` | `url` | Full URL with protocol and port |
| **Click** | `mcp__claude-in-chrome__computer` | `action: "click"`, coordinates or element | Use `find` first to locate element, then click at coordinates |
| **Fill** | `mcp__claude-in-chrome__form_input` | `uid`, `value` | Use `find` to get element UID first |
| **Wait** | Poll with `mcp__claude-in-chrome__read_page` | `smart: true` | Repeat until expected text appears or timeout |
| **Assert** | `mcp__claude-in-chrome__read_page` or `mcp__claude-in-chrome__get_page_text` | Varies | Read page content and verify against expected values |
| **Capture** | `mcp__claude-in-chrome__computer` | `action: "screenshot"` | Returns base64 screenshot for evidence |

### Tool Usage Patterns

**Locating Elements**:
Before Click or Fill, use `mcp__claude-in-chrome__find` to locate the target element:
```
1. find(query="[data-testid='send-button']") -> returns element with coordinates/uid
2. computer(action="click", coordinate=[x, y]) -> clicks at element location
```

**Polling for Wait Steps**:
```
loop (max_attempts = timeout_seconds / poll_interval):
    page_text = get_page_text()
    if expected_text in page_text:
        break
    sleep(poll_interval)
```

**Capturing Screenshots**:
```
result = computer(action="screenshot")
# result contains base64 image data
# Agent saves/logs as evidence for the step
```

---

## Complete Template

Below is a complete, copy-pasteable template for new test specifications:

```markdown
---
title: "Test Title Here"
type: e2e-browser
service: frontend
port: 5001
prerequisites:
  - "Frontend service running on port 5001"
  - "Backend API running on port 8000"
tags: [smoke]
estimated_duration: "2-5 minutes"
---

# Test Title Here

## Description

Brief description of what this test validates and why it matters.

## Steps

1. **Navigate** to `http://localhost:5001`
   - Expected: Page loads successfully

2. **Assert** page contains expected elements
   - Expected: Key UI elements are visible

3. **Capture** screenshot of final state
   - Target: `screenshots/03-final-state.png`
   - Expected: Screenshot saved

## Evidence

| Step | Screenshot | Description |
|------|-----------|-------------|
| 1 | `screenshots/01-initial-load.png` | Page after navigation |
| 3 | `screenshots/03-final-state.png` | Final state verification |

## Pass/Fail Criteria

- ALL Assert steps must pass
- Screenshots captured for all evidence steps
- No console errors during execution
```

---

## File Organization

Test specs live under `docs/tests/specs/` with descriptive filenames:

```
docs/tests/
├── TEST_SPEC_FORMAT.md          # This format standard
└── specs/
    ├── chat-send-message.md     # E2E: message send/receive
    ├── chat-session-management.md  # E2E: session CRUD
    ├── api-health-check.md      # API: health endpoints
    ├── api-credential-verification.md  # API: verification endpoint
    └── visual-chat-interface.md # Visual: UI rendering
```

### Naming Convention

- Use lowercase kebab-case: `{category}-{description}.md`
- Prefix with test category: `chat-`, `api-`, `visual-`, `auth-`, etc.
- Keep names concise but descriptive
