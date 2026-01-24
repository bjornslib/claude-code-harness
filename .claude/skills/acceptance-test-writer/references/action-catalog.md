# Action Catalog

Complete reference for all supported test step actions.

## Browser Actions

### navigate
Navigate to a URL path.

```yaml
- id: step-1
  action: navigate
  target: "/login"
  description: "Navigate to login page"
```

**Parameters:**
- `target` (required): URL path relative to base_url

**Notes:**
- Always use relative paths (e.g., `/login` not `http://localhost:3000/login`)
- Base URL comes from environment configuration

---

### fill
Enter text into an input field.

```yaml
- id: step-2
  action: fill
  selector: "[data-testid='email-input']"
  value: "user@example.com"
  description: "Enter email address"
```

**Parameters:**
- `selector` (required): CSS selector for input element
- `value` (required): Text to enter

**Notes:**
- Clears existing content before filling
- Works with `<input>`, `<textarea>`, and contenteditable elements

---

### click
Click an element.

```yaml
- id: step-3
  action: click
  selector: "[data-testid='submit-button']"
  description: "Click submit button"
```

**Parameters:**
- `selector` (required): CSS selector for clickable element

**Notes:**
- Waits for element to be visible and clickable
- Scrolls element into view if needed

---

### assert_visible
Verify an element is visible on the page.

```yaml
- id: step-4
  action: assert_visible
  selector: "[data-testid='success-message']"
  contains: "Login successful"
  description: "Success message displayed"
  screenshot: true
```

**Parameters:**
- `selector` (required): CSS selector
- `contains` (optional): Text that should be present in the element
- `screenshot` (optional): Capture screenshot after assertion

---

### assert_not_visible
Verify an element is NOT visible on the page.

```yaml
- id: step-5
  action: assert_not_visible
  selector: "[data-testid='error-message']"
  description: "No error message displayed"
```

**Parameters:**
- `selector` (required): CSS selector

---

### assert_url
Verify the current URL matches a pattern.

```yaml
- id: step-6
  action: assert_url
  pattern: "/dashboard"
  description: "Redirected to dashboard"
```

**Parameters:**
- `pattern` (required): URL pattern (can be partial match)

---

### assert_text
Verify text content within an element.

```yaml
- id: step-7
  action: assert_text
  selector: "[data-testid='user-name']"
  contains: "John Doe"
  description: "User name displayed correctly"
```

**Parameters:**
- `selector` (required): CSS selector
- `contains` (required): Expected text content

---

### wait_for_navigation
Wait for page navigation to complete.

```yaml
- id: step-8
  action: wait_for_navigation
  timeout_ms: 5000
  description: "Wait for page load after form submit"
```

**Parameters:**
- `timeout_ms` (required): Maximum wait time in milliseconds

**Notes:**
- Use after clicks that trigger page loads
- Fails if navigation doesn't complete within timeout

---

### wait_for_element
Wait for an element to appear.

```yaml
- id: step-9
  action: wait_for_element
  selector: "[data-testid='loading-complete']"
  timeout_ms: 10000
  description: "Wait for data to load"
```

**Parameters:**
- `selector` (required): CSS selector
- `timeout_ms` (required): Maximum wait time

---

### screenshot
Capture a screenshot.

```yaml
- id: step-10
  action: screenshot
  filename: "final-state.png"
  description: "Capture final page state"
```

**Parameters:**
- `filename` (required): Output filename

---

### select
Select an option from a dropdown.

```yaml
- id: step-11
  action: select
  selector: "[data-testid='country-select']"
  value: "AU"
  description: "Select Australia"
```

**Parameters:**
- `selector` (required): CSS selector for `<select>` element
- `value` (required): Option value to select

---

### check
Check or uncheck a checkbox.

```yaml
- id: step-12
  action: check
  selector: "[data-testid='terms-checkbox']"
  checked: true
  description: "Accept terms and conditions"
```

**Parameters:**
- `selector` (required): CSS selector
- `checked` (required): `true` to check, `false` to uncheck

---

### hover
Hover over an element.

```yaml
- id: step-13
  action: hover
  selector: "[data-testid='dropdown-trigger']"
  description: "Hover to reveal dropdown menu"
```

**Parameters:**
- `selector` (required): CSS selector

---

### press_key
Press a keyboard key.

```yaml
- id: step-14
  action: press_key
  key: "Enter"
  description: "Press Enter to submit"
```

**Parameters:**
- `key` (required): Key name (e.g., "Enter", "Escape", "Tab", "ArrowDown")

---

### clear
Clear an input field.

```yaml
- id: step-15
  action: clear
  selector: "[data-testid='search-input']"
  description: "Clear search field"
```

**Parameters:**
- `selector` (required): CSS selector

---

## API Actions

### api_request
Make an HTTP request.

```yaml
- id: step-1
  action: api_request
  method: POST
  url: "/api/auth/login"
  headers:
    Content-Type: "application/json"
  body:
    email: "user@example.com"
    password: "password123"
  description: "Submit login credentials"
```

**Parameters:**
- `method` (required): HTTP method (GET, POST, PUT, PATCH, DELETE)
- `url` (required): API endpoint path
- `headers` (optional): Request headers as key-value pairs
- `body` (optional): Request body (object for JSON, string for raw)

---

### assert_status
Assert the HTTP response status code.

```yaml
- id: step-2
  action: assert_status
  expected: 200
  description: "Login successful"
```

**Parameters:**
- `expected` (required): Expected HTTP status code

---

### assert_json
Assert a value in the JSON response.

```yaml
- id: step-3
  action: assert_json
  path: "$.data.user.email"
  expected: "user@example.com"
  description: "Response contains user email"
```

**Parameters:**
- `path` (required): JSONPath expression
- `expected` (required): Expected value

**JSONPath Examples:**
- `$.data` - Root level "data" field
- `$.data.user.id` - Nested field
- `$.items[0].name` - First item's name
- `$.items[*].id` - All item IDs

---

### assert_header
Assert a response header value.

```yaml
- id: step-4
  action: assert_header
  header: "Content-Type"
  expected: "application/json"
  description: "Response is JSON"
```

**Parameters:**
- `header` (required): Header name (case-insensitive)
- `expected` (required): Expected value (substring match)

---

### assert_response_contains
Assert the response body contains text.

```yaml
- id: step-5
  action: assert_response_contains
  text: "success"
  description: "Response indicates success"
```

**Parameters:**
- `text` (required): Text to find in response body

---

### store_value
Extract and store a value from the response for later use.

```yaml
- id: step-6
  action: store_value
  path: "$.data.token"
  variable: "auth_token"
  description: "Store auth token for subsequent requests"
```

**Parameters:**
- `path` (required): JSONPath expression
- `variable` (required): Variable name to store value

**Usage in subsequent steps:**
```yaml
- id: step-7
  action: api_request
  method: GET
  url: "/api/user/profile"
  headers:
    Authorization: "Bearer ${auth_token}"
```

---

## Hybrid Actions

### wait_for_api
Wait for a specific API call to complete (useful after UI actions that trigger API requests).

```yaml
- id: step-5
  action: wait_for_api
  url_pattern: "/api/user/profile"
  method: GET
  timeout_ms: 5000
  description: "Wait for profile API to be called"
```

**Parameters:**
- `url_pattern` (required): URL pattern to match
- `method` (required): Expected HTTP method
- `timeout_ms` (required): Maximum wait time

---

### assert_api_called
Verify that a UI action triggered an expected API call.

```yaml
- id: step-6
  action: assert_api_called
  url_pattern: "/api/analytics/track"
  method: POST
  expected_body:
    event: "page_view"
  description: "Analytics event was sent"
```

**Parameters:**
- `url_pattern` (required): URL pattern to match
- `method` (required): Expected HTTP method
- `expected_body` (optional): Expected request body

---

## Utility Actions

### wait
Wait for a fixed duration (use sparingly).

```yaml
- id: step-7
  action: wait
  duration_ms: 1000
  description: "Wait for animation to complete"
```

**Parameters:**
- `duration_ms` (required): Wait time in milliseconds

**Notes:**
- Avoid fixed waits when possible
- Prefer `wait_for_element` or `wait_for_navigation`

---

### log
Log a message (for debugging).

```yaml
- id: step-8
  action: log
  message: "About to submit form"
  description: "Debug checkpoint"
```

**Parameters:**
- `message` (required): Message to log

---

### if_visible
Conditional execution based on element visibility.

```yaml
- id: step-9
  action: if_visible
  selector: "[data-testid='cookie-banner']"
  then:
    - action: click
      selector: "[data-testid='accept-cookies']"
  description: "Dismiss cookie banner if present"
```

**Parameters:**
- `selector` (required): CSS selector to check
- `then` (required): Steps to execute if element is visible

---

## Selector Best Practices

### Preferred (most stable)
```yaml
selector: "[data-testid='login-button']"
selector: "[aria-label='Submit form']"
```

### Acceptable
```yaml
selector: "#unique-id"
selector: "button[type='submit']"
```

### Avoid (fragile)
```yaml
selector: ".btn-primary"
selector: "div > div > button"
selector: "button:nth-child(3)"
```

## Variable Substitution

Variables stored with `store_value` can be used in subsequent steps:

```yaml
# Store a value
- id: step-1
  action: store_value
  path: "$.data.userId"
  variable: "user_id"

# Use in URL
- id: step-2
  action: api_request
  url: "/api/users/${user_id}/profile"

# Use in assertion
- id: step-3
  action: assert_json
  path: "$.data.id"
  expected: "${user_id}"

# Use in body
- id: step-4
  action: api_request
  body:
    targetUserId: "${user_id}"
```
