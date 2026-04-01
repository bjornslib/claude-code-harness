---
title: "Digital Curator - Testing Strategy & Autonomous Validation"
description: "Comprehensive testing strategy for Chrome extension development: unit tests, browser integration via chrome-devtools MCP, vertical slice E2E gates, and autonomous install/test/trace workflow"
version: "1.0.0"
last-updated: 2026-04-01
status: draft
type: sd
grade: authoritative
---

# SD-DIGITAL-CURATOR-TESTING-001: Testing Strategy & Autonomous Validation

**PRD Reference**: PRD-DIGITAL-CURATOR-001
**Architecture Reference**: SD-DIGITAL-CURATOR-001

## 1. Testing Philosophy

Every vertical slice delivers **working, testable software**. No slice is complete until:

1. All unit tests pass (`npm test`)
2. The extension builds cleanly (`npm run build`)
3. The extension loads in Chrome without errors
4. The slice's E2E behavior is verified via browser automation
5. Console logs show no errors, warnings, or uncaught exceptions

Testing is not a phase — it's built into every pipeline node.

## 2. Test Pyramid

```
         ┌─────────┐
         │  E2E    │  chrome-devtools MCP + Playwright
         │ Browser │  (6 slices x 3-8 assertions each)
         ├─────────┤
         │ Integr. │  Playwright with --load-extension
         │         │  (content script <-> side panel <-> background)
         ├─────────┤
         │  Unit   │  Vitest + jsdom/happy-dom
         │         │  (all pure logic: anchoring, formatting,
         │         │   store, detection, serialization)
         └─────────┘

Target coverage: 90%+ unit, 80%+ integration, 100% E2E per slice
```

## 3. Unit Testing (Vitest)

### 3.1 Configuration

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'happy-dom',
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      thresholds: {
        statements: 90,
        branches: 85,
        functions: 90,
        lines: 90,
      },
    },
    include: ['src/**/*.test.ts', 'src/**/*.spec.ts'],
  },
});
```

### 3.2 Unit Test Matrix

| Module | Test File | What's Tested | Mocking Strategy |
|--------|-----------|---------------|------------------|
| `selection-engine.ts` | `selection-engine.test.ts` | `captureSelection()` with various DOM structures, `reanchor()` with mutated DOM, XPath generation, text offset calculation | Create DOM fixtures simulating Claude.ai message structure |
| `highlight-renderer.ts` | `highlight-renderer.test.ts` | `render()` / `remove()` with mark fallback, `reanchorAll()` batch re-rendering, CSS highlight API detection | Mock `CSS.highlights` for API path, test mark fallback directly |
| `chat-injector.ts` | `chat-injector.test.ts` | `formatAnnotations()` output format (prose + code), `inject()` with contenteditable div, 3-tier fallback strategy | Create contenteditable div fixture, mock `document.execCommand` |
| `code-block.ts` | `code-block.test.ts` | `isCodeBlock()` detection, `detectLanguage()` from class names, `extractCodeText()` preserving whitespace | Create pre/code DOM fixtures with syntax highlighting spans |
| `claude-dom.ts` | `claude-dom.test.ts` | `detectStrategy()` selector fallback, `observeMessages()` MutationObserver, `findConversationContainer()` | Create DOM fixtures matching Claude.ai structural patterns |
| `streaming-detector.ts` | `streaming-detector.test.ts` | `isStreaming()` cursor detection, `waitForCompletion()` promise resolution | Create DOM fixtures with/without streaming indicators |
| `conversation-tracker.ts` | `conversation-tracker.test.ts` | URL change detection via pushState/popstate, conversation ID extraction | Mock `history.pushState`, `history.replaceState` |
| `shared/store.ts` | `store.test.ts` | CRUD operations, `clearAll()`, annotation ordering, conversation scoping | Direct Zustand store testing (no mocks needed) |
| `shared/messages.ts` | `messages.test.ts` | Message type validation, serialization round-trip | Pure type checking |

### 3.3 DOM Fixture Strategy

Reusable fixtures simulate Claude.ai's DOM structure. Each fixture creates message containers with configurable options (streaming state, code blocks, language tags). Fixtures use `document.createElement` and `textContent` assignment (never raw HTML injection) to build safe DOM trees for testing selection, anchoring, and highlighting.

Key fixtures:
- `createMessageContainer(text, opts)` — single assistant message with optional code block + streaming indicator
- `createConversation(messages[])` — full conversation with alternating user/assistant messages
- `createChatInput()` — contenteditable div mimicking Claude's input area

### 3.4 Running Unit Tests

```bash
npm test                          # All unit tests
npm run test:coverage             # With coverage report
npm run test:watch                # Watch mode for development
npm test -- src/content/selection-engine.test.ts  # Specific module
```

## 4. Integration Testing (Playwright + Extension)

### 4.1 Playwright Extension Loading

Playwright supports loading Chrome extensions via persistent contexts:

```typescript
// tests/integration/setup.ts
import { chromium, type BrowserContext } from 'playwright';
import path from 'path';

const EXTENSION_PATH = path.resolve(__dirname, '../../dist');

export async function createExtensionContext(): Promise<BrowserContext> {
  const context = await chromium.launchPersistentContext('', {
    headless: false, // Extensions require headed mode
    args: [
      `--disable-extensions-except=${EXTENSION_PATH}`,
      `--load-extension=${EXTENSION_PATH}`,
      '--no-first-run',
      '--disable-default-apps',
    ],
  });
  return context;
}

export async function getExtensionId(context: BrowserContext): Promise<string> {
  let [background] = context.serviceWorkers();
  if (!background) {
    background = await context.waitForEvent('serviceworker');
  }
  const extensionId = background.url().split('/')[2];
  return extensionId;
}
```

### 4.2 Running Integration Tests

```bash
npm run build && npx playwright test tests/integration/
```

## 5. E2E Validation via chrome-devtools MCP (Guardian)

This is the **autonomous validation path** — how CoBuilder independently verifies each vertical slice without human intervention.

### 5.1 The Autonomous Install/Test/Trace Workflow

```
STEP 1: BUILD
  Worker (Sonnet) runs: npm run ci
  Output: dist/ folder with manifest.json + bundled JS

STEP 2: INSTALL (Guardian helper script)
  python3 scripts/load-extension.py --path dist/
  This script:
  a) Kills any existing Chrome DevTools test instance
  b) Launches Chrome with:
     --remote-debugging-port=9222
     --load-extension=dist/
     --user-data-dir=/tmp/dc-test-profile
     --no-first-run --disable-default-apps
  c) Waits for CDP ready on port 9222
  d) Outputs: "Chrome ready with extension loaded"

STEP 3: CONNECT (chrome-devtools MCP reconnects)
  The MCP server auto-connects to localhost:9222
  Guardian can now use all chrome-devtools tools

STEP 4: NAVIGATE + TEST
  mcp__chrome-devtools__navigate_page(url="https://claude.ai")
  mcp__chrome-devtools__list_console_messages(types=["error"])
  mcp__chrome-devtools__evaluate_script(...)
  mcp__chrome-devtools__take_screenshot(...)

STEP 5: TRACE
  Read all console messages: list_console_messages()
  Filter for [DC] prefix logs
  Check for uncaught exceptions
  Screenshot evidence for visual verification

STEP 6: VERDICT
  Score: 0.0-1.0 per test assertion
  Pass gate if all critical assertions pass
```

### 5.2 Extension Loader Script

```python
#!/usr/bin/env python3
"""load-extension.py - Launch Chrome with Digital Curator extension for testing."""

import subprocess, sys, time, urllib.request, json, os

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
]

def find_chrome():
    for path in CHROME_PATHS:
        if os.path.exists(path):
            return path
    raise FileNotFoundError("Chrome not found")

def kill_existing_chrome_debug():
    subprocess.run(
        ["pkill", "-f", "remote-debugging-port=9222"],
        capture_output=True
    )
    time.sleep(1)

def launch_chrome(extension_path, debug_port=9222):
    chrome = find_chrome()
    user_data = "/tmp/dc-test-profile"
    subprocess.run(["rm", "-rf", user_data], capture_output=True)

    cmd = [
        chrome,
        f"--remote-debugging-port={debug_port}",
        f"--load-extension={os.path.abspath(extension_path)}",
        f"--user-data-dir={user_data}",
        "--no-first-run", "--disable-default-apps",
        "--disable-popup-blocking", "--disable-translate",
        "--no-default-browser-check", "about:blank",
    ]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    for attempt in range(30):
        try:
            resp = urllib.request.urlopen(
                f"http://localhost:{debug_port}/json/version"
            )
            data = json.loads(resp.read())
            print(f"Chrome ready: {data.get('Browser', 'unknown')}")
            print(f"PID: {proc.pid}")
            print(f"CDP: http://localhost:{debug_port}")
            return proc
        except Exception:
            time.sleep(1)

    proc.kill()
    raise TimeoutError("Chrome failed to start with CDP")

if __name__ == "__main__":
    ext_path = sys.argv[1] if len(sys.argv) > 1 else "dist"
    kill_existing_chrome_debug()
    proc = launch_chrome(ext_path)
    print(f"Extension loaded from: {os.path.abspath(ext_path)}")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
```

### 5.3 Console Log Tracing Convention

All extension code uses a prefixed logging convention for traceable debugging:

```typescript
// src/shared/logger.ts
const PREFIX = '[DC]';

export const logger = {
  info: (msg: string, ...args: any[]) =>
    console.log(`${PREFIX} ${msg}`, ...args),
  warn: (msg: string, ...args: any[]) =>
    console.warn(`${PREFIX} ${msg}`, ...args),
  error: (msg: string, ...args: any[]) =>
    console.error(`${PREFIX} ${msg}`, ...args),
  // Structured event logging for guardian tracing
  event: (event: string, data?: Record<string, any>) =>
    console.log(`${PREFIX}:EVENT:${event}`, JSON.stringify(data || {})),
};
```

Guardian reads these via:
```
mcp__chrome-devtools__list_console_messages(types=["log"])
  -> Filter for "[DC]:EVENT:" prefix
  -> Parse structured event data
  -> Verify expected event sequence per slice
```

## 6. Vertical Slice Definitions

Each slice is a **fully testable increment** that adds one user-visible capability.

### Slice 1: Proof of Life (E1)

**Delivers**: Extension installs, content script injects on claude.ai, side panel opens with empty state.

| Component | Deliverable | Unit Tests |
|-----------|-------------|------------|
| `manifest.json` | Manifest V3 config, permissions, content script registration | Schema validation test |
| `background/index.ts` | Service worker, side panel registration | Message routing test |
| `content/index.ts` | Injection entry point, `__DIGITAL_CURATOR_LOADED__` flag, logger | Injection test |
| `sidepanel/App.tsx` | Empty state UI ("No comments yet") | Render test |
| `shared/logger.ts` | Prefixed logging with event tracing | Log format test |
| Build pipeline | Vite + CRXJS config, `npm run build` | Build completes without errors |

**E2E Gate Assertions**:
1. `window.__DIGITAL_CURATOR_LOADED__ === true` on claude.ai
2. Console shows `[DC] Content script loaded` (no errors)
3. Side panel renders "No comments yet" text
4. Extension icon visible in Chrome toolbar
5. Build produces valid `manifest.json` in dist/

### Slice 2: Select + Highlight (E2)

**Delivers**: User can select text in Claude responses and see a coral highlight.

| Component | Deliverable | Unit Tests |
|-----------|-------------|------------|
| `content/claude-dom.ts` | Message container detection (3-strategy fallback) | Selector strategy tests with DOM fixtures |
| `content/selection-engine.ts` | `captureSelection()`, anchor creation, `reanchor()` | Selection capture, re-anchor after mutation |
| `content/highlight-renderer.ts` | `render()`, `remove()`, CSS highlight + mark fallback | Render/remove, fallback path |
| `content/streaming-detector.ts` | `isStreaming()`, `waitForCompletion()` | Streaming detection |
| `content/highlights.css` | Highlight styles (coral overlay) | CSS snapshot |

**E2E Gate Assertions**:
1. Selecting text in assistant message -> `[DC]:EVENT:selection.captured` in console
2. Highlight mark elements present in DOM after selection
3. Selecting text in user message -> no event (filtered out)
4. Selecting streaming text -> no event (excluded)
5. Highlight visual matches design (screenshot comparison)

### Slice 3: Comment + Sidebar (E3 + E4)

**Delivers**: User can click comment icon, type a comment, see it in the sidebar.

| Component | Deliverable | Unit Tests |
|-----------|-------------|------------|
| `content/comment-popover.ts` | Shadow DOM popover, Save/Discard, Cmd+Enter | Popover show/hide, keyboard shortcut |
| `sidepanel/components/AnnotationCard.tsx` | Card UI (avatar, quote, comment, timestamp) | Render with mock data |
| `sidepanel/components/AnnotationList.tsx` | Card list, empty/populated states | List ordering |
| `sidepanel/components/Header.tsx` | "Active Annotations" + count badge | Badge count |
| `shared/store.ts` | Zustand store (add, edit, delete annotation) | Full CRUD suite |
| `background/index.ts` | Message routing content<->sidepanel | Message relay |

**E2E Gate Assertions**:
1. After selection -> floating icon appears -> click -> popover opens
2. Type comment + Save -> `[DC]:EVENT:annotation.created` in console
3. Sidebar shows annotation card with quoted text and comment
4. Badge shows "1 NEW"
5. Edit action on card -> comment editable
6. Delete action on card -> card removed + highlight removed

### Slice 4: Submit to Chat (E5)

**Delivers**: "Submit All Comments" pastes formatted annotations into Claude's chat input.

| Component | Deliverable | Unit Tests |
|-----------|-------------|------------|
| `content/chat-injector.ts` | `findChatInput()`, `formatAnnotations()`, `inject()` 3-tier fallback | Format output (prose + code), injection with contenteditable fixture |
| `sidepanel/components/SubmitButton.tsx` | Button state machine (idle->processing->success->idle) | State transition |
| `sidepanel/components/Footer.tsx` | Footer with submit button + branding | Render |

**E2E Gate Assertions**:
1. Create 2+ annotations -> "Submit All Comments" button enabled
2. Click Submit -> `[DC]:EVENT:submit.started` in console
3. Claude's chat input contains formatted text with `>` quoted blocks
4. Highlights removed from conversation
5. Sidebar cleared, shows empty state
6. Button shows "Sent Successfully!" then resets
7. User can edit the inserted text before sending

### Slice 5: Code Blocks (E6)

**Delivers**: User can annotate code blocks with language-aware formatting.

| Component | Deliverable | Unit Tests |
|-----------|-------------|------------|
| `content/code-block.ts` | `isCodeBlock()`, `detectLanguage()`, `extractCodeText()` | Detection with various code block DOMs |
| Update `selection-engine.ts` | Code-aware anchor creation | Code selection |
| Update `chat-injector.ts` | Fenced code block formatting | Code format |
| Update `AnnotationCard.tsx` | "Code" badge on code annotations | Badge render |

**E2E Gate Assertions**:
1. Select text within code block -> `isCode: true` in event
2. Highlight renders over syntax tokens without breaking colors
3. Submit with code annotation -> fenced code block in chat input
4. Language tag detected and included
5. Whitespace/indentation preserved

### Slice 6: Persistence + Polish (E7)

**Delivers**: Annotations survive scrolling, conversation tracking, session management.

| Component | Deliverable | Unit Tests |
|-----------|-------------|------------|
| `content/conversation-tracker.ts` | URL change detection, conversation ID extraction | pushState mock, URL parsing |
| Storage integration | `chrome.storage.session` read/write | Storage CRUD (mock chrome.storage) |
| `content/index.ts` | MutationObserver for re-anchoring | Re-anchor after simulated mutation |
| Popup UI | Toggle on/off, active indicator | Toggle state |

**E2E Gate Assertions**:
1. Create annotation -> scroll away -> scroll back -> highlight visible
2. `[DC]:EVENT:reanchor.success` after DOM mutation
3. Toggle extension off -> highlights disappear -> on -> restore
4. Navigate to different conversation -> annotations cleared
5. "Recording Session" indicator visible when active

## 7. Test Commands Summary

```bash
# Development
npm test                          # All unit tests (Vitest)
npm run test:watch                # Watch mode
npm run test:coverage             # Coverage report (must be >90%)

# Build
npm run build                     # Production build to dist/
npm run build:dev                 # Dev build with source maps

# Integration (requires headed Chrome)
npm run test:integration          # Playwright with extension loading

# Extension loading for manual/guardian testing
python3 scripts/load-extension.py dist/

# Lint + Type Check
npm run lint                      # ESLint
npm run typecheck                 # tsc --noEmit

# Full CI gate (what each pipeline node runs)
npm run ci                        # lint + typecheck + test:coverage + build
```

## 8. Guardian Validation Protocol (wait.cobuilder Gates)

At each `wait.cobuilder` gate in the pipeline, the guardian:

1. **Build**: Run `npm run ci` in the worktree -> must exit 0
2. **Load**: Run `python3 scripts/load-extension.py dist/` -> Chrome ready
3. **Navigate**: `mcp__chrome-devtools__navigate_page(url="https://claude.ai")`
4. **Wait**: 3 seconds for content script injection
5. **Trace**: `mcp__chrome-devtools__list_console_messages(types=["error"])` -> 0 DC errors
6. **Assert**: Run slice-specific assertions via `evaluate_script()`
7. **Evidence**: `mcp__chrome-devtools__take_screenshot()` -> save to evidence/
8. **Score**: 0.0-1.0 per assertion, weighted average for gate verdict
9. **Cleanup**: Kill Chrome test instance

### Gate Pass Criteria

| Gate | Required Score | Critical Assertions (must all pass) |
|------|---------------|-------------------------------------|
| Slice 1 | 0.80 | Content script loads, no errors, build succeeds |
| Slice 2 | 0.85 | Selection captured, highlight rendered, streaming excluded |
| Slice 3 | 0.85 | Comment saved, sidebar updated, edit/delete work |
| Slice 4 | 0.90 | Submit injects formatted text, chat input populated |
| Slice 5 | 0.85 | Code detection, language tag, fenced output |
| Slice 6 | 0.80 | Persistence across scroll, conversation tracking |

## Implementation Status

- **Unit test framework (Vitest)**: Not started
- **DOM fixtures**: Not started
- **Integration tests (Playwright)**: Not started
- **Extension loader script**: Not started
- **E2E validation scripts**: Not started
- **Console tracing convention**: Not started
- **CI pipeline**: Not started
