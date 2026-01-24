# Chrome DevTools MCP Action Patterns

Patterns for executing browser acceptance tests using chrome-devtools MCP.

## Setup

Before running browser tests, ensure Chrome is available:

```python
# Check if browser is ready
tabs = mcp__chrome-devtools__list_tabs()

# If no tabs, may need to launch browser
# (depends on MCP server configuration)
```

## Action Implementations

### navigate

```python
# YAML:
# - action: navigate
#   target: "/login"

mcp__chrome-devtools__navigate(
    url=f"{base_url}/login"  # Combine with environment base_url
)

# Wait for page load
import time
time.sleep(1)  # Basic wait, prefer wait_for_element when possible
```

### fill

```python
# YAML:
# - action: fill
#   selector: "[data-testid='email-input']"
#   value: "test@example.com"

# Clear existing content and fill
mcp__chrome-devtools__evaluate(
    expression=f"""
    const el = document.querySelector('[data-testid="email-input"]');
    el.value = '';
    el.value = 'test@example.com';
    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
    """
)

# Or use fill if available
mcp__chrome-devtools__fill(
    selector="[data-testid='email-input']",
    value="test@example.com"
)
```

### click

```python
# YAML:
# - action: click
#   selector: "[data-testid='login-button']"

mcp__chrome-devtools__click(
    selector="[data-testid='login-button']"
)

# Or via evaluate:
mcp__chrome-devtools__evaluate(
    expression="""
    document.querySelector('[data-testid="login-button"]').click();
    """
)
```

### assert_visible

```python
# YAML:
# - action: assert_visible
#   selector: "[data-testid='success-message']"
#   contains: "Welcome"

result = mcp__chrome-devtools__evaluate(
    expression="""
    (() => {
        const el = document.querySelector('[data-testid="success-message"]');
        if (!el) return { visible: false, text: null };
        const style = window.getComputedStyle(el);
        const visible = style.display !== 'none' &&
                       style.visibility !== 'hidden' &&
                       style.opacity !== '0';
        return { visible, text: el.textContent };
    })()
    """
)

# Check visibility
assert result['visible'], f"Element not visible"

# Check text content if specified
if contains:
    assert contains in result['text'], f"Expected '{contains}' not found in '{result['text']}'"
```

### assert_not_visible

```python
# YAML:
# - action: assert_not_visible
#   selector: "[data-testid='error-message']"

result = mcp__chrome-devtools__evaluate(
    expression="""
    (() => {
        const el = document.querySelector('[data-testid="error-message"]');
        if (!el) return { exists: false };
        const style = window.getComputedStyle(el);
        const visible = style.display !== 'none' &&
                       style.visibility !== 'hidden' &&
                       style.opacity !== '0';
        return { exists: true, visible };
    })()
    """
)

assert not result.get('visible', False), "Element should not be visible"
```

### assert_url

```python
# YAML:
# - action: assert_url
#   pattern: "/dashboard"

result = mcp__chrome-devtools__evaluate(
    expression="window.location.href"
)

assert "/dashboard" in result, f"Expected URL to contain '/dashboard', got '{result}'"
```

### assert_text

```python
# YAML:
# - action: assert_text
#   selector: "[data-testid='user-name']"
#   contains: "John Doe"

result = mcp__chrome-devtools__evaluate(
    expression="""
    document.querySelector('[data-testid="user-name"]')?.textContent || ''
    """
)

assert "John Doe" in result, f"Expected 'John Doe' in '{result}'"
```

### wait_for_navigation

```python
# YAML:
# - action: wait_for_navigation
#   timeout_ms: 5000

import time
start = time.time()
initial_url = mcp__chrome-devtools__evaluate(expression="window.location.href")

while time.time() - start < 5:  # 5 seconds
    current_url = mcp__chrome-devtools__evaluate(expression="window.location.href")
    if current_url != initial_url:
        break
    time.sleep(0.5)
else:
    raise TimeoutError("Navigation did not occur within timeout")
```

### wait_for_element

```python
# YAML:
# - action: wait_for_element
#   selector: "[data-testid='loading-complete']"
#   timeout_ms: 10000

import time
start = time.time()

while time.time() - start < 10:  # 10 seconds
    result = mcp__chrome-devtools__evaluate(
        expression=f"""
        document.querySelector('[data-testid="loading-complete"]') !== null
        """
    )
    if result:
        break
    time.sleep(0.5)
else:
    raise TimeoutError("Element did not appear within timeout")
```

### screenshot

```python
# YAML:
# - action: screenshot
#   filename: "login-success.png"

mcp__chrome-devtools__screenshot(
    path=f"validation-reports/{prd_id}/evidence/{filename}"
)
```

### select (dropdown)

```python
# YAML:
# - action: select
#   selector: "[data-testid='country-select']"
#   value: "AU"

mcp__chrome-devtools__evaluate(
    expression="""
    const select = document.querySelector('[data-testid="country-select"]');
    select.value = 'AU';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    """
)
```

### check (checkbox)

```python
# YAML:
# - action: check
#   selector: "[data-testid='terms-checkbox']"
#   checked: true

mcp__chrome-devtools__evaluate(
    expression="""
    const checkbox = document.querySelector('[data-testid="terms-checkbox"]');
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event('change', { bubbles: true }));
    """
)
```

### hover

```python
# YAML:
# - action: hover
#   selector: "[data-testid='dropdown-trigger']"

mcp__chrome-devtools__evaluate(
    expression="""
    const el = document.querySelector('[data-testid="dropdown-trigger"]');
    el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
    el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
    """
)
```

### press_key

```python
# YAML:
# - action: press_key
#   key: "Enter"

mcp__chrome-devtools__evaluate(
    expression="""
    document.activeElement.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })
    );
    document.activeElement.dispatchEvent(
        new KeyboardEvent('keyup', { key: 'Enter', bubbles: true })
    );
    """
)
```

### clear

```python
# YAML:
# - action: clear
#   selector: "[data-testid='search-input']"

mcp__chrome-devtools__evaluate(
    expression="""
    const el = document.querySelector('[data-testid="search-input"]');
    el.value = '';
    el.dispatchEvent(new Event('input', { bubbles: true }));
    """
)
```

## Error Handling

### Element Not Found

```python
def find_element(selector, timeout_ms=5000):
    """Find element with retry."""
    start = time.time()
    while time.time() - start < timeout_ms / 1000:
        result = mcp__chrome-devtools__evaluate(
            expression=f"document.querySelector('{selector}') !== null"
        )
        if result:
            return True
        time.sleep(0.2)
    raise ElementNotFoundError(f"Element '{selector}' not found after {timeout_ms}ms")
```

### Page Load Issues

```python
def wait_for_page_ready(timeout_ms=10000):
    """Wait for page to be fully loaded."""
    start = time.time()
    while time.time() - start < timeout_ms / 1000:
        result = mcp__chrome-devtools__evaluate(
            expression="document.readyState"
        )
        if result == "complete":
            return True
        time.sleep(0.5)
    raise TimeoutError("Page did not fully load")
```

## Network Request Capture (for hybrid tests)

```python
# Start capturing network requests
mcp__chrome-devtools__evaluate(
    expression="""
    window.__capturedRequests = [];
    const origFetch = window.fetch;
    window.fetch = async (...args) => {
        const response = await origFetch(...args);
        window.__capturedRequests.push({
            url: args[0],
            options: args[1],
            status: response.status
        });
        return response;
    };
    """
)

# After UI action, check if API was called
result = mcp__chrome-devtools__evaluate(
    expression="""
    window.__capturedRequests.find(r => r.url.includes('/api/auth'))
    """
)
```

## Best Practices

1. **Always wait for elements** before interacting with them
2. **Use data-testid selectors** for stability
3. **Capture screenshots** at key verification points
4. **Add delays after navigation** to ensure page is ready
5. **Check element visibility** not just existence
6. **Handle dynamic content** with polling/retries
