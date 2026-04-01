---
title: "Digital Curator - Chrome Extension Architecture"
description: "Technical architecture for the Digital Curator Chrome extension: Manifest V3, content scripts, Side Panel, text anchoring, and chat injection"
version: "1.0.0"
last-updated: 2026-04-01
status: draft
type: sd
grade: authoritative
---

# SD-DIGITAL-CURATOR-001: Chrome Extension Architecture

**PRD Reference**: PRD-DIGITAL-CURATOR-001
**Scope**: Epics E1-E7 (full extension architecture)

## 1. Architecture Overview

### 1.1 Extension Component Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Chrome Browser                            │
│                                                              │
│  ┌──────────────────┐    ┌────────────────────────────┐     │
│  │  Background       │    │  Side Panel                 │     │
│  │  Service Worker   │◄──►│  (React + Shadow DOM)       │     │
│  │                   │    │  - Annotation card list     │     │
│  │  - State manager  │    │  - Submit button            │     │
│  │  - Storage sync   │    │  - Empty/active states      │     │
│  │  - Message router │    └────────────────────────────┘     │
│  └────────┬─────────┘                                        │
│           │ chrome.runtime.sendMessage                        │
│           ▼                                                  │
│  ┌──────────────────────────────────────────────────┐       │
│  │  Content Script (claude.ai/*)                     │       │
│  │                                                    │       │
│  │  ┌──────────────┐  ┌─────────────────────────┐   │       │
│  │  │ Selection     │  │ Highlight Renderer       │   │       │
│  │  │ Detector      │  │ (CSS custom properties)  │   │       │
│  │  └──────┬───────┘  └─────────────────────────┘   │       │
│  │         │                                          │       │
│  │  ┌──────▼───────┐  ┌─────────────────────────┐   │       │
│  │  │ Comment       │  │ Chat Input Injector      │   │       │
│  │  │ Popover       │  │ (contenteditable writer) │   │       │
│  │  │ (Shadow DOM)  │  └─────────────────────────┘   │       │
│  │  └──────────────┘                                  │       │
│  └──────────────────────────────────────────────────┘       │
│                                                              │
│  Claude.ai DOM (React SPA)                                   │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Build** | Vite + CRXJS | Fast HMR for extension dev, Manifest V3 native support |
| **Language** | TypeScript 5.x | Type safety for DOM manipulation, message passing |
| **UI Framework** | Preact (Side Panel + Popover) | 3KB gzipped — minimal footprint for extension overlays |
| **Styling** | Tailwind CSS (compiled) | Design token fidelity from Stitch screens, no runtime CSS-in-JS |
| **State** | Zustand (lightweight) | Shared annotation state between content script and side panel |
| **Testing** | Vitest + Playwright | Unit tests + E2E browser extension testing |
| **Packaging** | Chrome Web Store CLI | Automated `.crx` / `.zip` build |

### 1.3 Manifest V3 Configuration

```json
{
  "manifest_version": 3,
  "name": "Digital Curator",
  "version": "1.0.0",
  "description": "Annotate Claude.ai responses with inline comments",
  "permissions": [
    "sidePanel",
    "storage",
    "activeTab"
  ],
  "host_permissions": [
    "https://claude.ai/*"
  ],
  "background": {
    "service_worker": "src/background/index.ts",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": ["https://claude.ai/*"],
      "js": ["src/content/index.ts"],
      "css": ["src/content/highlights.css"],
      "run_at": "document_idle"
    }
  ],
  "side_panel": {
    "default_path": "src/sidepanel/index.html"
  },
  "action": {
    "default_popup": "src/popup/index.html",
    "default_icon": {
      "16": "icons/icon-16.png",
      "48": "icons/icon-48.png",
      "128": "icons/icon-128.png"
    }
  },
  "icons": {
    "16": "icons/icon-16.png",
    "48": "icons/icon-48.png",
    "128": "icons/icon-128.png"
  }
}
```

## 2. Content Script Architecture (E2, E4, E5, E6)

### 2.1 Claude.ai DOM Detection Strategy

Claude.ai is a React SPA with hashed class names. The content script must use **structural selectors** and **MutationObserver** to find message containers reliably.

#### Message Container Detection

```typescript
// Strategy: Find messages by structural patterns, not class names
const MESSAGE_SELECTORS = {
  // Primary: data attributes (most stable if present)
  dataAttr: '[data-message-id]',
  // Secondary: structural pattern (assistant messages contain specific child structures)
  structural: 'div[class*="message"] > div > div',
  // Tertiary: role-based ARIA (if present)
  aria: '[role="presentation"] > div',
};

class ClaudeDOM {
  private observer: MutationObserver;

  /**
   * Detect the active selector strategy on first load.
   * Falls back through strategies in priority order.
   */
  detectStrategy(): SelectorStrategy {
    for (const [name, selector] of Object.entries(MESSAGE_SELECTORS)) {
      const matches = document.querySelectorAll(selector);
      if (matches.length > 0 && this.validateMessages(matches)) {
        return { name, selector };
      }
    }
    // Last resort: heuristic — find the largest scrollable container
    // with alternating child patterns (user/assistant)
    return this.heuristicDetection();
  }

  /**
   * Watch for new messages (streaming completion or navigation)
   */
  observeMessages(callback: (messages: Element[]) => void) {
    this.observer = new MutationObserver((mutations) => {
      const newMessages = this.findNewMessages(mutations);
      if (newMessages.length > 0) {
        callback(newMessages);
      }
    });
    // Observe the conversation container, not the whole document
    const container = this.findConversationContainer();
    if (container) {
      this.observer.observe(container, {
        childList: true,
        subtree: true,
      });
    }
  }
}
```

#### Streaming Response Detection

Annotations should only target **completed** messages. Detect streaming state:

```typescript
class StreamingDetector {
  /**
   * Returns true if a message element is still being streamed.
   * Detection heuristics:
   * 1. Cursor element present (blinking cursor at end of message)
   * 2. Message length is growing (tracked over 500ms window)
   * 3. Specific CSS class indicating streaming state
   */
  isStreaming(messageEl: Element): boolean {
    // Check for cursor element (most reliable)
    const cursor = messageEl.querySelector('[class*="cursor"], .animate-pulse');
    if (cursor) return true;

    // Check for streaming indicator in parent
    const parent = messageEl.closest('[class*="streaming"], [data-is-streaming]');
    if (parent) return true;

    return false;
  }

  /**
   * Wait for message to finish streaming before allowing annotation
   */
  waitForCompletion(messageEl: Element): Promise<void> {
    return new Promise((resolve) => {
      if (!this.isStreaming(messageEl)) {
        resolve();
        return;
      }
      const observer = new MutationObserver(() => {
        if (!this.isStreaming(messageEl)) {
          observer.disconnect();
          resolve();
        }
      });
      observer.observe(messageEl, { childList: true, subtree: true, characterData: true });
    });
  }
}
```

### 2.2 Text Selection & Anchoring Engine (E2)

The core challenge: selections must survive React re-renders. Use a **text-position anchoring** strategy inspired by Hypothesis.

#### Anchor Data Model

```typescript
interface TextAnchor {
  /** Unique annotation ID */
  id: string;
  /** The exact selected text (for re-anchoring) */
  exact: string;
  /** Text before the selection (context window) */
  prefix: string;  // 32 chars before
  /** Text after the selection (context window) */
  suffix: string;  // 32 chars after
  /** XPath to the closest stable ancestor */
  containerXPath: string;
  /** Character offset within the text content of the container */
  startOffset: number;
  /** Character offset for end */
  endOffset: number;
  /** Whether this is inside a code block */
  isCode: boolean;
  /** Language tag if code block (e.g., "javascript") */
  codeLanguage?: string;
  /** Message index (nth message in conversation) for disambiguation */
  messageIndex: number;
}
```

#### Selection Capture

```typescript
class SelectionEngine {
  /**
   * Capture the current browser selection and create an anchor.
   * Called on mouseup after a text selection within a message container.
   */
  captureSelection(): TextAnchor | null {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
      return null;
    }

    const range = selection.getRangeAt(0);

    // Verify selection is within a Claude message (not user message, not sidebar, etc.)
    const messageContainer = this.findMessageContainer(range.commonAncestorContainer);
    if (!messageContainer) return null;

    // Check if streaming
    if (this.streamingDetector.isStreaming(messageContainer)) return null;

    // Extract anchor data
    const exact = selection.toString();
    const textContent = messageContainer.textContent || '';
    const selectionStart = this.getTextOffset(messageContainer, range.startContainer, range.startOffset);
    const selectionEnd = selectionStart + exact.length;

    return {
      id: crypto.randomUUID(),
      exact,
      prefix: textContent.slice(Math.max(0, selectionStart - 32), selectionStart),
      suffix: textContent.slice(selectionEnd, selectionEnd + 32),
      containerXPath: this.getXPath(messageContainer),
      startOffset: selectionStart,
      endOffset: selectionEnd,
      isCode: this.isWithinCodeBlock(range.commonAncestorContainer),
      codeLanguage: this.detectCodeLanguage(range.commonAncestorContainer),
      messageIndex: this.getMessageIndex(messageContainer),
    };
  }

  /**
   * Re-anchor a stored anchor after DOM re-render.
   * Uses fuzzy text matching with prefix/suffix context.
   */
  reanchor(anchor: TextAnchor): Range | null {
    // Strategy 1: Try XPath + offset (fast, exact)
    const container = this.resolveXPath(anchor.containerXPath);
    if (container) {
      const range = this.createRangeFromOffset(container, anchor.startOffset, anchor.endOffset);
      if (range && range.toString() === anchor.exact) {
        return range;
      }
    }

    // Strategy 2: Find by message index + text search (handles re-renders)
    const message = this.getMessageByIndex(anchor.messageIndex);
    if (message) {
      const textContent = message.textContent || '';
      // Search for exact match with prefix/suffix context
      const searchPattern = anchor.prefix + anchor.exact + anchor.suffix;
      const idx = textContent.indexOf(searchPattern);
      if (idx !== -1) {
        const start = idx + anchor.prefix.length;
        return this.createRangeFromTextOffset(message, start, start + anchor.exact.length);
      }
      // Fallback: exact match only (less precise but more resilient)
      const exactIdx = textContent.indexOf(anchor.exact);
      if (exactIdx !== -1) {
        return this.createRangeFromTextOffset(message, exactIdx, exactIdx + anchor.exact.length);
      }
    }

    return null; // Anchor lost — notify user
  }
}
```

### 2.3 Highlight Renderer

Highlights are rendered using CSS custom highlights API (where supported) with a fallback to `<mark>` element injection.

```typescript
class HighlightRenderer {
  private highlights: Map<string, { range: Range; markElements: HTMLElement[] }> = new Map();

  /**
   * Render a highlight for an annotation.
   * Uses CSS Custom Highlight API (Chrome 105+) with <mark> fallback.
   */
  render(annotationId: string, range: Range): void {
    if ('Highlight' in window && CSS.highlights) {
      // Modern path: CSS Custom Highlight API (no DOM modification!)
      const highlight = new Highlight(range);
      CSS.highlights.set(`dc-${annotationId}`, highlight);
    } else {
      // Fallback: wrap in <mark> elements
      const marks = this.wrapRangeInMarks(range, annotationId);
      this.highlights.set(annotationId, { range, markElements: marks });
    }
  }

  /**
   * Remove a highlight.
   */
  remove(annotationId: string): void {
    if (CSS.highlights) {
      CSS.highlights.delete(`dc-${annotationId}`);
    } else {
      const data = this.highlights.get(annotationId);
      if (data) {
        data.markElements.forEach(mark => {
          const parent = mark.parentNode;
          if (parent) {
            while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
            parent.removeChild(mark);
          }
        });
      }
    }
    this.highlights.delete(annotationId);
  }

  /**
   * Re-render all highlights (called after DOM mutation).
   */
  reanchorAll(engine: SelectionEngine, annotations: Annotation[]): void {
    this.clear();
    for (const annotation of annotations) {
      const range = engine.reanchor(annotation.anchor);
      if (range) {
        this.render(annotation.id, range);
      }
    }
  }
}
```

#### Highlight CSS (injected by content script)

```css
/* CSS Custom Highlight API styles */
::highlight(dc-annotation) {
  background-color: rgba(217, 119, 87, 0.2);
  border-bottom: 2px solid #D97757;
}

::highlight(dc-annotation-hover) {
  background-color: rgba(217, 119, 87, 0.35);
  border-bottom: 2px solid #D97757;
}

/* Fallback <mark> styles */
mark[data-dc-annotation] {
  background-color: rgba(217, 119, 87, 0.2);
  border-bottom: 2px solid #D97757;
  padding: 0;
  margin: 0;
  border-radius: 0;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

mark[data-dc-annotation]:hover,
mark[data-dc-annotation].dc-active {
  background-color: rgba(217, 119, 87, 0.35);
}

/* Code block highlights preserve syntax coloring */
pre mark[data-dc-annotation],
code mark[data-dc-annotation] {
  color: inherit;
}
```

### 2.4 Comment Popover (E4)

The inline comment editor is rendered in a Shadow DOM container to isolate from Claude.ai's styles.

```typescript
class CommentPopover {
  private shadowHost: HTMLDivElement;
  private shadowRoot: ShadowRoot;

  constructor() {
    this.shadowHost = document.createElement('div');
    this.shadowHost.id = 'dc-comment-popover';
    this.shadowHost.style.cssText = 'position: absolute; z-index: 999999; pointer-events: none;';
    document.body.appendChild(this.shadowHost);
    this.shadowRoot = this.shadowHost.attachShadow({ mode: 'closed' });
  }

  /**
   * Show the comment editor near the selection.
   */
  show(anchor: TextAnchor, range: Range, onSave: (comment: string) => void): void {
    const rect = range.getBoundingClientRect();
    const viewportHeight = window.innerHeight;

    // Position: prefer above the selection, fallback below
    const spaceAbove = rect.top;
    const spaceBelow = viewportHeight - rect.bottom;
    const positionAbove = spaceAbove > 220; // editor height ~200px

    this.shadowHost.style.left = `${rect.left + window.scrollX}px`;
    this.shadowHost.style.top = positionAbove
      ? `${rect.top + window.scrollY - 220}px`
      : `${rect.bottom + window.scrollY + 8}px`;
    this.shadowHost.style.pointerEvents = 'auto';

    // Render Preact component into shadow DOM
    render(
      <CommentEditor
        quotedText={anchor.exact}
        onSave={(comment) => {
          onSave(comment);
          this.hide();
        }}
        onDiscard={() => this.hide()}
      />,
      this.shadowRoot
    );
  }

  hide(): void {
    render(null, this.shadowRoot);
    this.shadowHost.style.pointerEvents = 'none';
  }
}
```

### 2.5 Chat Input Injector (E5)

The most critical integration point: inserting formatted annotation text into Claude's chat input.

```typescript
class ChatInputInjector {
  /**
   * Find Claude's chat input element.
   * Claude uses a contenteditable div, not a textarea.
   */
  private findChatInput(): HTMLElement | null {
    // Strategy 1: contenteditable with specific parent structure
    const editables = document.querySelectorAll('[contenteditable="true"]');
    for (const el of editables) {
      // Filter to the main chat input (not in-message edit boxes)
      if (this.isChatInput(el as HTMLElement)) {
        return el as HTMLElement;
      }
    }
    // Strategy 2: ProseMirror editor (Claude may use this)
    const prosemirror = document.querySelector('.ProseMirror[contenteditable="true"]');
    if (prosemirror) return prosemirror as HTMLElement;

    return null;
  }

  /**
   * Format all annotations into a structured message.
   */
  formatAnnotations(annotations: Annotation[]): string {
    const lines: string[] = ['Here are my annotations on your response:\n'];

    for (const ann of annotations) {
      if (ann.anchor.isCode) {
        const lang = ann.anchor.codeLanguage || '';
        lines.push(`> \`\`\`${lang}`);
        lines.push(`> ${ann.anchor.exact.split('\n').join('\n> ')}`);
        lines.push(`> \`\`\``);
      } else {
        lines.push(`> "${ann.anchor.exact}"`);
      }
      lines.push('');
      lines.push(ann.comment);
      lines.push('');
      lines.push('---');
      lines.push('');
    }

    return lines.join('\n');
  }

  /**
   * Insert text into Claude's chat input.
   * Must handle contenteditable div with proper focus/selection/input events.
   */
  inject(annotations: Annotation[]): boolean {
    const input = this.findChatInput();
    if (!input) return false;

    const text = this.formatAnnotations(annotations);

    // Focus the input
    input.focus();

    // Strategy 1: execCommand (works with most contenteditable)
    const success = document.execCommand('insertText', false, text);
    if (success) return true;

    // Strategy 2: Direct DOM manipulation + input event dispatch
    input.textContent = text;
    input.dispatchEvent(new InputEvent('input', {
      bubbles: true,
      cancelable: true,
      inputType: 'insertText',
      data: text,
    }));

    // Strategy 3: Clipboard API fallback
    // Copy to clipboard and notify user to paste
    if (!input.textContent?.includes(text.substring(0, 50))) {
      navigator.clipboard.writeText(text).then(() => {
        this.showClipboardFallback();
      });
      return false;
    }

    return true;
  }
}
```

## 3. Side Panel Architecture (E3)

### 3.1 Side Panel Registration

```typescript
// background/index.ts
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

// Open side panel when extension icon is clicked
chrome.action.onClicked.addListener(async (tab) => {
  if (tab.id) {
    await chrome.sidePanel.open({ tabId: tab.id });
  }
});
```

### 3.2 Side Panel Component Tree

```
<SidePanelApp>
  ├── <Header>
  │   ├── "Active Annotations"
  │   └── <Badge count={annotations.length} />
  │
  ├── <AnnotationList>  (scrollable)
  │   ├── <AnnotationCard key={id}>
  │   │   ├── <UserAvatar initials="BJ" />
  │   │   ├── <Timestamp relative="2m ago" />
  │   │   ├── <QuotedText text="..." />
  │   │   ├── <CommentBody text="..." />
  │   │   └── <Actions onEdit onDelete />
  │   └── ...
  │
  ├── <EmptyState />  (when no annotations)
  │   ├── <Icon name="forum" />
  │   └── "Select text to start annotating"
  │
  └── <Footer>
      ├── <SubmitButton
      │   onClick={submitAll}
      │   state="idle" | "processing" | "success"
      │ />
      └── "Powered by Digital Curator"
```

### 3.3 State Management

```typescript
// shared/store.ts — Zustand store shared via chrome.storage.session
interface AnnotationStore {
  annotations: Annotation[];
  isActive: boolean;
  conversationId: string | null;

  // Actions
  addAnnotation: (anchor: TextAnchor, comment: string) => void;
  editAnnotation: (id: string, comment: string) => void;
  deleteAnnotation: (id: string) => void;
  clearAll: () => void;
  setActive: (active: boolean) => void;
  setConversationId: (id: string | null) => void;
}

interface Annotation {
  id: string;
  anchor: TextAnchor;
  comment: string;
  createdAt: number;
  updatedAt: number;
}
```

### 3.4 Message Passing Protocol

```typescript
// Content Script → Side Panel (via Background)
type ContentMessage =
  | { type: 'ANNOTATION_CREATED'; payload: Annotation }
  | { type: 'ANNOTATION_ANCHORS_UPDATED'; payload: { id: string; valid: boolean }[] }
  | { type: 'CONVERSATION_CHANGED'; payload: { conversationId: string } };

// Side Panel → Content Script (via Background)
type PanelMessage =
  | { type: 'HIGHLIGHT_ANNOTATION'; payload: { id: string } }
  | { type: 'SCROLL_TO_ANNOTATION'; payload: { id: string } }
  | { type: 'DELETE_ANNOTATION'; payload: { id: string } }
  | { type: 'SUBMIT_ALL'; payload: {} }
  | { type: 'TOGGLE_ACTIVE'; payload: { active: boolean } };

// Background routes messages between content script and side panel
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.tab) {
    // From content script → forward to side panel
    chrome.runtime.sendMessage(message);
  } else {
    // From side panel → forward to content script on active tab
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, message);
      }
    });
  }
});
```

## 4. Data Flow

### 4.1 Annotation Creation Flow

```
User selects text in Claude response
  │
  ▼
Content Script: SelectionEngine.captureSelection()
  │ Creates TextAnchor
  ▼
Content Script: Show floating comment icon near selection
  │
  ▼
User clicks comment icon
  │
  ▼
Content Script: CommentPopover.show(anchor)
  │ Renders Shadow DOM editor
  ▼
User types comment, clicks Save
  │
  ▼
Content Script: HighlightRenderer.render(id, range)
  │ Applies coral highlight to text
  ▼
Content Script → Background → Side Panel: ANNOTATION_CREATED
  │
  ▼
Side Panel: AnnotationCard appears in list
  │ Badge count increments
```

### 4.2 Submit Flow

```
User clicks "Submit All Comments" in Side Panel
  │
  ▼
Side Panel → Background → Content Script: SUBMIT_ALL
  │
  ▼
Content Script: ChatInputInjector.inject(annotations)
  │ Formats all annotations
  │ Inserts into contenteditable div
  ▼
Content Script: HighlightRenderer.clear()
  │ Removes all highlights
  ▼
Content Script → Side Panel: ANNOTATIONS_CLEARED
  │
  ▼
Side Panel: Shows "Sent Successfully!" → Resets to empty state
```

### 4.3 Re-anchoring Flow (after DOM mutation)

```
MutationObserver detects DOM change
  │
  ▼
Content Script: SelectionEngine.reanchor(anchor) for each annotation
  │ Tries XPath + offset → fuzzy text match → message index search
  ▼
Content Script: HighlightRenderer.reanchorAll()
  │ Re-renders all highlights at new positions
  ▼
Content Script → Side Panel: ANNOTATION_ANCHORS_UPDATED
  │ Reports which anchors are still valid
  ▼
Side Panel: Shows warning badge on lost anchors
```

## 5. Code Block Support (E6)

### 5.1 Code Block Detection

```typescript
class CodeBlockDetector {
  /**
   * Determine if a DOM node is within a code block.
   */
  isCodeBlock(node: Node): boolean {
    const el = node instanceof Element ? node : node.parentElement;
    if (!el) return false;
    return !!el.closest('pre > code, pre[class*="language"], pre[class*="code"]');
  }

  /**
   * Extract the language from a code block.
   */
  detectLanguage(node: Node): string | undefined {
    const el = node instanceof Element ? node : node.parentElement;
    const pre = el?.closest('pre');
    const code = pre?.querySelector('code');
    if (!code) return undefined;

    // Check class names for language hints
    const classes = Array.from(code.classList);
    for (const cls of classes) {
      const match = cls.match(/^(?:language-|lang-)(.+)$/);
      if (match) return match[1];
    }

    // Check data attributes
    return code.dataset.language || pre?.dataset.language;
  }

  /**
   * Extract selected text from code block preserving whitespace.
   * Syntax highlighting creates deeply nested <span> elements;
   * we need the raw text content with original indentation.
   */
  extractCodeText(range: Range): string {
    const fragment = range.cloneContents();
    // Walk text nodes and preserve whitespace
    const walker = document.createTreeWalker(fragment, NodeFilter.SHOW_TEXT);
    let text = '';
    while (walker.nextNode()) {
      text += walker.currentNode.textContent;
    }
    return text;
  }
}
```

## 6. Persistence Strategy (E7)

### 6.1 Storage Model

```typescript
// chrome.storage.session — per-tab, cleared on tab close
interface SessionStorage {
  [`dc_annotations_${conversationId}`]: Annotation[];
  dc_active: boolean;
  dc_currentConversation: string | null;
}
```

### 6.2 Conversation Change Detection

```typescript
class ConversationTracker {
  private currentUrl: string = '';

  /**
   * Detect conversation switches via URL changes.
   * Claude.ai URLs: /chat/{conversationId}
   */
  startTracking(onChange: (conversationId: string) => void): void {
    // Watch for pushState/replaceState (SPA navigation)
    const origPushState = history.pushState;
    const origReplaceState = history.replaceState;

    history.pushState = (...args) => {
      origPushState.apply(history, args);
      this.checkUrl(onChange);
    };
    history.replaceState = (...args) => {
      origReplaceState.apply(history, args);
      this.checkUrl(onChange);
    };

    window.addEventListener('popstate', () => this.checkUrl(onChange));

    // Initial check
    this.checkUrl(onChange);
  }

  private checkUrl(onChange: (id: string) => void): void {
    if (location.href !== this.currentUrl) {
      this.currentUrl = location.href;
      const match = location.pathname.match(/\/chat\/([a-f0-9-]+)/);
      if (match) {
        onChange(match[1]);
      }
    }
  }
}
```

## 7. Project Structure

```
digital-curator/
├── manifest.json
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
│
├── src/
│   ├── background/
│   │   └── index.ts              # Service worker, message routing
│   │
│   ├── content/
│   │   ├── index.ts              # Entry point, orchestrator
│   │   ├── claude-dom.ts         # Claude.ai DOM detection
│   │   ├── selection-engine.ts   # Text selection & anchoring
│   │   ├── highlight-renderer.ts # CSS Highlight API + <mark> fallback
│   │   ├── comment-popover.ts    # Shadow DOM comment editor
│   │   ├── chat-injector.ts      # Chat input text insertion
│   │   ├── streaming-detector.ts # Streaming response detection
│   │   ├── conversation-tracker.ts # URL-based conversation tracking
│   │   ├── code-block.ts         # Code block detection & extraction
│   │   └── highlights.css        # Highlight styles
│   │
│   ├── sidepanel/
│   │   ├── index.html            # Side panel HTML shell
│   │   ├── index.tsx             # Preact entry
│   │   ├── App.tsx               # Main side panel app
│   │   ├── components/
│   │   │   ├── Header.tsx
│   │   │   ├── AnnotationCard.tsx
│   │   │   ├── AnnotationList.tsx
│   │   │   ├── EmptyState.tsx
│   │   │   ├── SubmitButton.tsx
│   │   │   └── Footer.tsx
│   │   └── styles.css
│   │
│   ├── popup/
│   │   ├── index.html
│   │   └── Popup.tsx             # Toggle + settings
│   │
│   └── shared/
│       ├── store.ts              # Zustand annotation store
│       ├── types.ts              # Shared TypeScript types
│       ├── messages.ts           # Message passing types
│       └── design-tokens.ts      # Color/spacing constants
│
├── icons/
│   ├── icon-16.png
│   ├── icon-48.png
│   └── icon-128.png
│
└── tests/
    ├── unit/
    │   ├── selection-engine.test.ts
    │   ├── highlight-renderer.test.ts
    │   ├── chat-injector.test.ts
    │   └── code-block.test.ts
    └── e2e/
        ├── annotation-flow.spec.ts
        └── submit-flow.spec.ts
```

## 8. Performance Considerations

| Concern | Mitigation |
|---------|-----------|
| Long conversations (100+ messages) | Only attach selection listeners to messages in viewport (IntersectionObserver) |
| MutationObserver overhead | Debounce mutations, only process childList changes on conversation container |
| Shadow DOM memory | Single shadow host for popover, unmount when hidden |
| Highlight re-anchoring | Batch re-anchor operations, skip off-screen annotations |
| Side panel communication | Batch message sends with requestAnimationFrame |
| Content script size | Code-split content script; lazy-load popover and injector |

## 9. Security Considerations

| Concern | Approach |
|---------|---------|
| Content Security Policy | Content scripts are exempt from page CSP. Shadow DOM styles bypass page restrictions. |
| User data privacy | All annotation data stays in `chrome.storage.session` (local only). No external network requests. |
| XSS via annotation text | User comments are rendered as textContent, never innerHTML. Quoted text is escaped. |
| Claude.ai mutation | Extension never modifies Claude's functional DOM (only adds highlights and shadow DOM containers). |

## 10. Risks & Technical Debt

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Claude.ai redesign breaks DOM selectors | High | Multi-strategy selector fallback + auto-detection. Community reporting for selector updates. |
| CSS Highlight API gaps | Low | `<mark>` fallback already implemented. CSS Highlights supported in Chrome 105+. |
| contenteditable injection fails | Medium | Three-tier injection strategy (execCommand → DOM + event → clipboard fallback). |
| ProseMirror input model | Medium | If Claude uses ProseMirror, need to dispatch ProseMirror-specific transactions. Research needed. |
| React 19+ concurrent features | Low | MutationObserver approach is framework-agnostic. |

## Implementation Status

- **E1 (Infrastructure)**: Not started
- **E2 (Selection & Highlighting)**: Not started
- **E3 (Sidebar Panel)**: Not started
- **E4 (Comment Editor)**: Not started
- **E5 (Submit to Chat)**: Not started
- **E6 (Code Block Support)**: Not started
- **E7 (Persistence)**: Not started
