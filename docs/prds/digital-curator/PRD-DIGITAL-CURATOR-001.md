---
title: "Digital Curator - Claude.ai Annotation Chrome Extension"
description: "Chrome browser extension enabling Google Docs-style inline text annotation on Claude.ai conversations with comment aggregation and submission"
version: "1.0.0"
last-updated: 2026-04-01
status: draft
type: prd
grade: authoritative
prd_id: PRD-DIGITAL-CURATOR-001
---

# PRD-DIGITAL-CURATOR-001: Digital Curator — Claude.ai Annotation Chrome Extension

## 1. Problem Statement

### The Gap in AI Chat Interfaces

Claude.ai — like all major AI chat interfaces — treats conversations as linear message streams. When Claude generates a multi-paragraph response containing a plan, code, analysis, or creative writing, users who want to provide targeted feedback on specific sections face a frustrating workflow:

1. **Manual quoting**: Copy-paste the relevant section, wrap it in quotes, then write the feedback
2. **Positional references**: "In the third paragraph, where you mention X..." — fragile and ambiguous
3. **Bulk rewrites**: "Rewrite section 2 with these changes..." — loses the precision of inline feedback
4. **Sequential feedback**: One comment per message, losing the ability to batch multiple annotations

This contrasts sharply with mature document collaboration tools (Google Docs, Notion, Figma) where users highlight text, attach comments in context, and submit batched feedback — all without losing their place in the document.

### Competitive Context

**Google Antigravity** (launched November 2025) introduced "Google-Doc-style comments directly on agent Artifacts" — users can annotate proposed plans and code segments with inline comments, and the AI agent incorporates feedback without halting its work. This represents the state of the art for human-AI plan review, but it is locked within Antigravity's proprietary IDE.

**No equivalent capability exists for Claude.ai users.** The annotation gap means Claude users provide lower-quality feedback (less specific, less contextual) compared to Antigravity users, resulting in more revision cycles and slower convergence on desired outputs.

### Existing Solutions Fall Short

Web annotation extensions (Hypothesis, Glasp, Liner) solve generic web highlighting but fail for AI chat interfaces because:

- They don't understand chat message boundaries (highlights bleed across messages)
- They have no mechanism to submit annotations back to the AI
- They struggle with dynamically rendered SPA content (React virtual DOM)
- They persist highlights to external services, not to the conversation context
- They don't handle code blocks with syntax highlighting

## 2. Vision

**Digital Curator** is a Chrome browser extension that brings Google Docs-style inline annotation to Claude.ai. Users highlight any text or code in Claude's responses, attach comments in a right-hand sidebar, and submit all annotations as structured feedback directly into Claude's chat input — turning imprecise conversational feedback into precise, contextual revision instructions.

### Design Principles

1. **Non-destructive overlay**: The extension overlays on Claude.ai without modifying its functionality. If the extension is disabled, Claude.ai works exactly as before.
2. **Familiar interaction model**: Highlight text → click comment icon → write comment. Identical to Google Docs.
3. **Batch submission**: Users accumulate multiple annotations before submitting, enabling comprehensive feedback in a single message.
4. **Contextual precision**: Every comment is anchored to specific highlighted text, eliminating ambiguity.
5. **Zero friction activation**: One-click toggle. No account creation, no external services, no configuration.

## 3. Target Users

| Persona | Description | Primary Use Case |
|---------|-------------|------------------|
| **Power Prompter** | Uses Claude daily for writing, analysis, coding. Sends 20+ messages per conversation. | Iterating on long-form outputs — plans, essays, code reviews |
| **Team Reviewer** | Reviews Claude-generated artifacts (plans, specs, designs) shared by colleagues. | Providing structured feedback on AI-generated deliverables |
| **Developer** | Uses Claude for code generation, debugging, architecture discussions. | Annotating specific code blocks, pointing out bugs, requesting changes |
| **Content Creator** | Uses Claude for drafting articles, scripts, marketing copy. | Line-editing AI-generated content with precision |

## 4. User Stories

### Core Annotation Flow

- **US-1**: As a user, I can select any text within a Claude response and see a comment icon appear, so that I can initiate an annotation on specific content.
- **US-2**: As a user, I can click the comment icon to open a comment editor positioned near my selection, so that I can write feedback in context.
- **US-3**: As a user, I can save my comment and see the annotated text remain highlighted with a subtle visual indicator, so that I know which parts I've commented on.
- **US-4**: As a user, I can hover over highlighted text to see the associated comment displayed in a right-hand sidebar, so that I can review my annotations.
- **US-5**: As a user, I can edit or delete any of my comments, so that I can refine my feedback before submission.

### Sidebar Management

- **US-6**: As a user, I can see all my annotations listed in a persistent right-hand sidebar panel, so that I have an overview of all my feedback.
- **US-7**: As a user, I can click on any annotation in the sidebar to scroll to and highlight the corresponding text in the conversation, so that I can navigate between annotations.
- **US-8**: As a user, I can see the count of new/unsent annotations in the sidebar header badge, so that I know how many comments I've accumulated.

### Submit to Chat

- **US-9**: As a user, I can click "Submit All Comments" to have all my annotations formatted and pasted into Claude's chat input area, so that Claude receives my structured feedback.
- **US-10**: As a user, I can see the submitted message formatted with each annotation showing the quoted highlighted text followed by my comment, so that Claude can understand exactly which text each comment refers to.
- **US-11**: As a user, after submission I can see the annotations cleared from the sidebar and highlights removed, so that I start fresh for the next round of feedback.

### Code Block Annotation

- **US-12**: As a user, I can select and annotate text within code blocks (including syntax-highlighted code), so that I can provide feedback on specific lines of code.
- **US-13**: As a user, I can see code annotations formatted with code fencing in the submitted message, so that Claude receives properly formatted code references.

### Session Management

- **US-14**: As a user, I can see a "Recording Session" indicator when the extension is active, so that I know annotations are being tracked.
- **US-15**: As a user, I can toggle the extension on/off via the toolbar or extension popup, so that I can control when annotation mode is active.
- **US-16**: As a user, my annotations persist within the current browser tab session (surviving page scrolls and soft navigations within Claude.ai), so that I don't lose work while composing feedback.

## 5. Interaction Patterns

### 5.1 Annotation Creation (Google Docs Model)

```
1. User reads Claude's response
2. User selects text by clicking and dragging
3. A floating comment icon (pencil/bubble) appears near the selection
4. User clicks the icon
5. An inline comment editor appears (popover near the selection)
6. User types their comment
7. User clicks "Save" (or presses Cmd+Enter)
8. The selected text receives a persistent subtle highlight (coral/orange underline)
9. The annotation appears in the right sidebar
10. The comment editor closes
```

### 5.2 Annotation Review

```
1. User hovers over highlighted text in the conversation
2. The corresponding annotation card in the sidebar receives visual emphasis (border highlight, scroll-into-view)
3. The annotation card shows: user avatar, timestamp, quoted text excerpt, full comment
4. User can click Edit (pencil icon) or Delete (trash icon) on the card
```

### 5.3 Submit All Comments

```
1. User clicks "Submit All Comments" button in sidebar footer
2. Extension formats all annotations into a structured message:

   --- Annotations ---

   > "The FAIE Origin/Hero Story (Illustrate Section)"

   This needs more detail on the origin story. We should mention the specific challenges faced in 1998 to make the "win" feel more earned.

   > ```json
   > "confidence": 0.8,
   > "verified_data": { ... }
   > ```

   The filter should use `cases_verification_results` → `employment_status` directly from the JSONB.

   ---

3. The formatted text is inserted into Claude's chat input textarea
4. User can review/edit before pressing Enter to send
5. After insertion, annotations are cleared (or optionally archived)
```

### 5.4 Extension States

| State | Visual Indicator | Behavior |
|-------|-----------------|----------|
| **Inactive** | Extension icon greyed out | No overlay, no interception |
| **Active (No annotations)** | Green dot + "Recording Session" toolbar | Text selection triggers comment icon |
| **Active (With annotations)** | Sidebar visible, annotation count badge | Full annotation + review + submit |
| **Submitting** | "Processing..." button state | Formatting and inserting into chat |
| **Submitted** | "Sent Successfully!" confirmation | Annotations cleared, fresh state |

## 6. UX Reference Screens

Two reference screens have been designed in Stitch (Project ID: `410074061814852727`):

### Screen 1: Annotate Overlay — Active Sidebar

**Screen ID**: `ea95a7b19f43459dad4d6cf7506d3c24`

Shows the primary annotation experience:
- Claude.ai conversation visible in background (dimmed when sidebar is open)
- Right sidebar (380px) titled "Active Annotations" with "1 NEW" badge
- Annotation card with: user avatar (initials), name, timestamp, quoted text reference (coral left-border blockquote), comment body
- Edit/Delete action icons on each card
- Floating toolbar at top: "Recording Session" indicator (green pulse dot), pen tool, camera tool
- Text highlight on conversation: coral (#D97757) background with 30% opacity + 2px solid bottom border
- "Submit All Comments →" button (full-width, coral primary) in sidebar footer
- "Powered by Digital Curator" branding

### Screen 2: Annotate Overlay — Code Highlighting

**Screen ID**: `13aa60257e154fa9adefc44b394a7a21`

Shows code block annotation:
- Full-width review mode with header bar ("Digital Curator Review" + Cancel/Submit buttons)
- Code block highlighted with semi-transparent coral overlay (15% opacity + 1px border)
- Floating "Add Comment" button (circular, with tooltip) positioned at selection point
- Inline comment editor popover: user avatar, "You (Reviewing)" label, textarea, Discard/Save buttons
- Status bar footer: selection context ("JSON Verification Structure"), cursor position, "Extension Active" indicator

### Design System

| Token | Value | Usage |
|-------|-------|-------|
| `curator-primary` | `#D97757` | Highlights, buttons, accents |
| `curator-bg` | `#F9F8F6` | Sidebar background |
| `curator-border` | `#E5E4E2` | Card/section borders |
| `curator-text` | `#2D2926` | Primary text |
| `curator-muted` | `#716B64` | Secondary text, timestamps |
| `curator-cream` | `#F4F1EA` | Comment editor background |
| Font | Inter 300-700 | All UI text |
| Border radius | 4px | Buttons, cards, inputs |

## 7. Technical Constraints

### Claude.ai DOM Considerations

- Claude.ai is a **React single-page application** with virtual DOM rendering
- Message content is rendered inside `div[class*="message"]` containers (class names are obfuscated/hashed)
- Code blocks use `<pre><code>` elements with syntax highlighting via Prism/Shiki
- The chat input is a **contenteditable div** (not a `<textarea>`), requiring specialized insertion logic
- Soft navigations (switching conversations) replace DOM content without full page reloads
- Claude.ai uses **streaming responses** — text appears incrementally, so annotations should only target completed messages

### Extension Architecture Constraints

- **Manifest V3** is mandatory (MV2 deprecated since June 2025)
- **Side Panel API** (`chrome.sidePanel`) for the annotation sidebar — persists across navigations
- **Content Script** for DOM injection, text selection handling, highlight rendering
- **Shadow DOM** for extension UI elements (comment popover, floating toolbar) to isolate from Claude.ai's CSS
- **chrome.storage.session** for annotation persistence within browser session
- No external backend required — all processing is client-side

### Text Selection Challenges

- Selections may span multiple DOM nodes (e.g., bold + regular text, or across paragraph boundaries)
- Code blocks have deeply nested DOM for syntax highlighting tokens
- Text positions must be re-anchored after Claude.ai re-renders (React reconciliation)
- Serialization of selections must survive DOM mutations (use XPath or CSS selector + text offset anchoring, similar to Hypothesis)

## 8. Epics

### E1: Extension Infrastructure & Manifest V3 Scaffold

**Priority**: P0 — Foundation for all other epics

Set up the Chrome extension project with Manifest V3, content script injection on `claude.ai/*`, Side Panel registration, extension popup for toggle/settings, and build pipeline (TypeScript, bundler, hot reload).

**Acceptance Criteria**:
- Extension loads on `claude.ai` without errors
- Content script injects and logs to console on every Claude.ai page load
- Side Panel opens via extension action click
- Extension popup shows on/off toggle
- Build produces production-ready `.crx` / `.zip`

### E2: Text Selection & Highlight Engine

**Priority**: P0 — Core interaction mechanism

Implement text selection detection within Claude.ai message containers, floating comment icon positioning, highlight rendering (coral overlay), and selection serialization/deserialization for persistence across re-renders.

**Acceptance Criteria**:
- Selecting text in any Claude response message shows a floating comment icon
- Selecting text in code blocks shows the comment icon (code-aware selection)
- Saving a highlight renders a persistent coral underline/background on the text
- Highlights survive soft navigation within the same conversation
- Highlights re-anchor correctly after minor DOM re-renders
- Selections spanning multiple DOM nodes (bold + regular, across paragraphs) are handled
- Only completed messages are annotatable (streaming responses are excluded)

### E3: Annotation Sidebar Panel

**Priority**: P0 — Annotation management and review

Build the right-hand sidebar using Chrome Side Panel API with: annotation card list (avatar, name, timestamp, quoted text, comment), annotation count badge, click-to-scroll navigation, and empty state.

**Acceptance Criteria**:
- Side Panel opens showing "Active Annotations" header with count badge
- Each annotation card shows: user initials avatar, "Just now" / relative timestamp, quoted text excerpt (coral left-border), full comment text
- Clicking an annotation card scrolls the conversation to the highlighted text and pulses the highlight
- Edit and Delete icons are visible on each card
- Empty state shows helpful guidance ("Select text to start annotating")
- Cards are ordered chronologically (newest first)

### E4: Inline Comment Editor

**Priority**: P0 — Comment creation and editing

Implement the floating comment editor popover that appears near the text selection. Supports create, edit, and discard flows. Uses Shadow DOM for CSS isolation.

**Acceptance Criteria**:
- Comment editor appears positioned near the text selection (above or below, depending on viewport space)
- Editor shows: user label ("You (Reviewing)"), textarea with placeholder, Discard/Save buttons
- Save creates the annotation and closes the editor
- Discard removes the selection highlight and closes the editor
- Cmd+Enter keyboard shortcut saves the comment
- Escape key discards
- Editor is rendered in Shadow DOM (Claude.ai CSS does not affect it)
- Editor repositions if the viewport scrolls while open

### E5: Submit Comments to Chat Integration

**Priority**: P0 — Core value proposition (annotation → feedback loop)

Implement the "Submit All Comments" flow: format all annotations into a structured message, insert into Claude's chat input (contenteditable div), handle the post-submission cleanup.

**Acceptance Criteria**:
- "Submit All Comments →" button appears in sidebar footer when annotations exist
- Clicking formats all annotations as: quoted highlighted text + comment, separated by blank lines
- Code block annotations are wrapped in fenced code blocks (``` language)
- Formatted message is inserted into Claude's chat input div with correct cursor positioning
- Button shows "Processing..." → "Sent Successfully!" → resets to default
- After insertion, all highlights are removed from the conversation
- Annotations are cleared from the sidebar
- User can edit the inserted text before pressing Enter to send
- Button is disabled when no annotations exist

### E6: Code Block Annotation Support

**Priority**: P1 — Enhanced developer experience

Extend the highlight engine to handle code blocks: selection within syntax-highlighted tokens, preserving indentation in quoted text, language detection for fenced code output.

**Acceptance Criteria**:
- Users can select partial lines within code blocks
- Highlights render correctly over syntax-highlighted tokens (without breaking coloring)
- Quoted text in annotations preserves whitespace and indentation
- Submitted code annotations use fenced code blocks with detected language tag
- Multi-line code selections are handled correctly
- Code block annotations show a "Code" badge in the sidebar card

### E7: Annotation Persistence & Session Management

**Priority**: P1 — Quality of life

Persist annotations within browser tab session using `chrome.storage.session`. Handle conversation switches, page refreshes within the same conversation, and annotation archival.

**Acceptance Criteria**:
- Annotations persist when user scrolls away and returns to the conversation
- Annotations persist across soft navigations within the same conversation
- Switching to a different conversation clears annotations (or stores per-conversation)
- Extension state (active/inactive) persists across tab refreshes
- "Recording Session" toolbar indicator is visible when extension is active
- Optional: export annotations as JSON for external use

## 9. Out of Scope (v1.0)

- **Multi-user collaboration**: v1 is single-user, single-tab
- **Annotation history across sessions**: Annotations don't survive tab close
- **Claude Code terminal support**: Terminal annotation requires a separate solution (tmux split pane with TUI — future PRD)
- **AI-powered annotation suggestions**: No automatic feedback generation
- **Claude API integration**: The extension operates purely on the web UI, not the API
- **Firefox / Safari support**: Chrome-only for v1
- **Annotation on user messages**: Only Claude's responses are annotatable
- **Image/file annotation**: Text and code only

## 10. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to first annotation | < 3 seconds from text selection | Extension telemetry (opt-in) |
| Annotations per submit | 3-5 average | Extension telemetry |
| Submit success rate | > 99% | Error logging |
| Extension load impact on Claude.ai | < 50ms added page load | Performance profiling |
| User retention (weekly active) | > 40% of installers | Chrome Web Store analytics |

## 11. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Claude.ai DOM structure changes break selectors | High — highlights and injection fail | Use resilient selectors (data attributes, structural patterns, not class names). Implement MutationObserver to detect and adapt. |
| React re-rendering removes highlights | Medium — annotations visually disappear | Re-anchor highlights after re-renders using text content + offset matching (Hypothesis approach) |
| Chat input injection fails (contenteditable changes) | High — core submit feature broken | Abstract input detection, support multiple insertion strategies, fallback to clipboard |
| Claude.ai deploys Content Security Policy blocking injection | High — extension stops working | Content scripts are exempt from page CSP. Use Shadow DOM for inline styles. |
| Performance degradation on long conversations | Medium — sluggish highlighting | Virtualize annotation tracking, only render highlights in viewport |

## 12. Competitive Landscape

| Feature | Digital Curator (this) | Antigravity | Hypothesis | Glasp |
|---------|----------------------|-------------|------------|-------|
| Inline text annotation | Yes | Yes (on Artifacts) | Yes | Yes |
| Code block annotation | Yes | Yes | No | No |
| Submit to AI chat | Yes | Built-in (agent loop) | No | No |
| Works on Claude.ai | Yes | No (own IDE) | Partial (breaks on SPA) | Partial |
| Batch submission | Yes | Real-time | N/A | N/A |
| No account required | Yes | No (Google login) | No (account) | No (account) |
| Open source | TBD | No | Yes | No |

## Implementation Status

- **E1**: Not started
- **E2**: Not started
- **E3**: Not started
- **E4**: Not started
- **E5**: Not started
- **E6**: Not started
- **E7**: Not started
