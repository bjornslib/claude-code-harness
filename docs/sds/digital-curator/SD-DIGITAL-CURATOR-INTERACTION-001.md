---
title: "Digital Curator - Interaction Design Specification"
description: "Detailed screen-by-screen interaction design for every state of the Digital Curator Chrome extension, derived from Stitch UX screens"
version: "1.0.0"
last-updated: 2026-04-01
status: draft
type: sd
grade: authoritative
---

# SD-DIGITAL-CURATOR-INTERACTION-001: Interaction Design Specification

**PRD Reference**: PRD-DIGITAL-CURATOR-001
**Architecture Reference**: SD-DIGITAL-CURATOR-001
**Source**: Stitch Project `410074061814852727` — 5 reference screens

## 1. Screen Inventory

| Screen | Stitch ID | State | Primary Interaction |
|--------|-----------|-------|---------------------|
| S1: Annotate Trigger | `ead50854` | Empty / first-use | Text selection → "Add Note" button appears |
| S2: Active Annotations Sidebar | `5331a672` | Multiple annotations | Hover highlights, sidebar navigation, FAB |
| S3: Annotate Overlay (Claude.ai) | `ea95a7b1` | Single annotation with sidebar | Toolbar, highlight, annotation card |
| S4: Code Highlighting | `13aa6025` | Code block annotation | Inline comment editor popover |
| S5: IDE Split Pane | `02c56061` | Code editor + annotations | Multi-user annotations, resolve/reply |

## 2. Design System Tokens

### 2.1 Core Palette (Material Design 3 Mapping)

| Token | Light Value | Dark Value | Usage |
|-------|-------------|------------|-------|
| `primary` | `#D97757` / `#99462a` | `#fb9270` | Buttons, highlights, active accents |
| `on-primary` | `#ffffff` / `#fff6f3` | `#70280e` | Text on primary surfaces |
| `primary-container` | `#ffdbd0` | `#89391e` | Annotation highlight background, badges |
| `surface` | `#fffcf7` | `#1a1a17` | Main background |
| `surface-container` | `#f6f4ec` | `#2a2a26` | Card backgrounds, input areas |
| `surface-container-highest` | `#eae9de` | `#3d3d39` | Active nav items, code backgrounds |
| `outline-variant` | `#babab0` | `#4a4a44` | Borders, dividers (at 15% opacity) |
| `on-surface` | `#373831` | `#eae9de` | Primary text |
| `on-surface-variant` | `#64655d` | `#babab0` | Muted text, timestamps |
| `tertiary` | `#6a56b1` | `#a490ef` | AI indicator, secondary accent |
| `error` | `#a64542` | `#fe8983` | Delete actions, error states |

### 2.2 Typography Scale

| Style | Font | Weight | Size | Tracking | Usage |
|-------|------|--------|------|----------|-------|
| App Title | Inter | 800 | 18px | -0.02em | "The Digital Curator" |
| Section Header | Inter | 700 | 14px | 0 | "Active Annotations", nav items |
| Card Title | Inter | 700 | 10px | 0.1em | Annotation labels (uppercase) |
| Body | Inter | 400 | 13-14px | 0 | Comment text, content |
| Caption | Inter | 500-700 | 10px | 0.08em | Timestamps, counts (uppercase) |
| Code | JetBrains Mono | 400 | 13px | 0 | Code blocks, status bar |

### 2.3 Shape Scale

| Element | Radius | Shadow |
|---------|--------|--------|
| Buttons (pill) | `9999px` (full) | None |
| Buttons (rect) | `8px` (lg) | `shadow-sm` |
| Cards | `12px` (xl) | `shadow-sm`, `shadow-md` on hover |
| Input areas | `12px` (xl) | `shadow-sm` on focus |
| Avatar | `8px` (lg) for squares, `full` for circles | None |
| Tooltip | `4px` | `shadow-md` |

### 2.4 Iconography

Material Symbols Outlined, variable weight 400, no fill. Key icons:

| Icon | Name | Usage |
|------|------|-------|
| `add_comment` | Add Comment | FAB, floating trigger, new annotation |
| `comment` | Comment | Sidebar header |
| `edit` | Edit | Annotation card action |
| `delete` | Delete | Annotation card action |
| `title` | Title | Annotations nav item |
| `auto_awesome` | AI Sparkle | Claude/AI message indicator |
| `forum` | Forum | Empty state illustration |
| `arrow_upward` | Send | Chat input send button |
| `filter_list` | Filter | Annotation filter |
| `history` | History | Toolbar history action |

## 3. Screen State Specifications

### 3.1 S1: Annotate Trigger (Empty State)

**Context**: Extension is active, user is viewing a Claude conversation. No annotations exist yet.

#### Layout Structure

```
┌────────────────────────────────────────────────────────────────┐
│ HEADER BAR (h=56px, fixed top)                                 │
│ [Logo] [Workspace | Library | Collections]     [⏱ ⚙ Submit]  │
├──────────┬──────────────────────────────┬──────────────────────┤
│ LEFT NAV │ CONTENT AREA                 │ RIGHT PANEL (w=320px)│
│ (w=256px)│                              │                      │
│          │ [User message bubble]        │ ANNOTATIONS          │
│ Library  │                              │ 0 COMMENTS           │
│ Collect. │ [AI avatar]                  │                      │
│ Annotat. │ [AI response text]           │   ┌──────────────┐  │
│ Archive  │                              │   │  (forum icon) │  │
│          │ ┌────────────────────┐       │   │               │  │
│          │ │  CODE BLOCK        │       │   │ No comments   │  │
│          │ │  function debounce │       │   │ yet           │  │
│          │ │  ───────────────── │       │   │               │  │
│          │ │  [+ Add Note]      │       │   │ Select text   │  │
│          │ │  clearTimeout(...) │       │   │ to start...   │  │
│          │ └────────────────────┘       │   └──────────────┘  │
│          │                              │                      │
│ + New    │ [Follow-up input area]       │ WORKSPACE CONTEXT    │
│ Collect. │                              │ 📚 JS Best Practices │
│          │                              │                      │
│ Help     │                              │                      │
│ Feedback │                              │                      │
└──────────┴──────────────────────────────┴──────────────────────┘
```

#### Interaction States

| Element | Default | Hover | Active/Focus | Disabled |
|---------|---------|-------|-------------|----------|
| Code block highlight | No highlight | Subtle border-left appears if cursor enters code block | Lines highlighted with `tertiary/5` bg + 4px left border | — |
| "Add Note" button | Hidden | Appears within highlighted code region. Pill shape: `bg-surface/90 backdrop-blur-md border-primary/20`. Icon `add_comment` (filled) + "Add Note" label. | Scale 95%, brief color flash | — |
| Sidebar empty state | Shows forum icon (200 weight), "No comments yet" heading, subtext, "VIEW GUIDELINES" link | — | — | — |
| Left nav "Annotations" | Normal weight, muted color | `bg-surface-container-highest/50` | `bg-surface-container-highest text-primary font-bold` | — |

#### Transitions

| Trigger | From State | To State | Animation |
|---------|-----------|----------|-----------|
| User selects text in code block | No highlight | Lines highlighted, "Add Note" appears | 150ms fade-in for button, instant highlight |
| User clicks "Add Note" | Trigger visible | Comment editor opens (→ S4) | 200ms slide-down for editor |
| User deselects (clicks elsewhere) | Trigger visible | No highlight, button hides | 100ms fade-out |

---

### 3.2 S2: Active Annotations Sidebar

**Context**: User has created 2+ annotations. Sidebar shows annotation cards.

#### Layout Structure

Same 3-column layout as S1 but with populated sidebar and highlights in content.

#### Content Highlights

Each annotated text segment receives:

```css
/* Light mode */
background: #fef3c7;           /* warm yellow highlight */
padding: 0 4px;
border-radius: 2px;
border-bottom: 2px solid #ffdbd0; /* primary-container */
cursor: pointer;
transition: background-color 0.15s ease;

/* Hover (annotation is being focused) */
background: rgba(217, 119, 87, 0.3); /* primary at 30% */
```

#### Annotation Card Anatomy

```
┌─────────────────────────────────────────┐
│ PTOLEMAIC BREAK              [✏️] [🗑️] │  ← Label (10px bold uppercase primary)
│                               (on hover) │    + edit/delete icons (opacity 0→1)
│ ┌─────────────────────────────────────┐ │
│ │ "The inclusion of 'America'         │ │  ← Quoted text (italic, 13px, muted)
│ │  marked a definitive break from     │ │     bg-surface/50, border-left-2
│ │  the Ptolemaic tradition..."        │ │     border-primary-container
│ └─────────────────────────────────────┘ │
│                                         │
│ Compare this with the Mercator          │  ← Comment body (13px, on-surface)
│ projection's focus on navigation...     │
│                                         │
│ [👤 avatar] Curator • 2m ago            │  ← Author + timestamp (10px, muted)
└─────────────────────────────────────────┘
```

#### Card Interaction States

| State | Background | Shadow | Border | Actions |
|-------|-----------|--------|--------|---------|
| Default | `bg-surface-container-highest` | `shadow-sm` | `border-outline-variant/10` | Edit/delete hidden |
| Hover | Same | `shadow-md` | Same | Edit/delete visible (opacity transition 200ms) |
| Active (linked to hovered highlight) | `bg-primary-container/20` | `shadow-md` | `border-l-4 border-primary` | Always visible |
| Edit mode | Same | `shadow-lg` | `ring-2 ring-primary/20` | Textarea replaces body |

#### Sidebar → Content Bidirectional Linking

| User Action | Sidebar Response | Content Response |
|------------|-----------------|-----------------|
| Hover over highlight in content | Corresponding card scrolls into view + receives active state | Highlight intensifies (30% → 45% opacity) |
| Click card in sidebar | Card gets focus ring | Content scrolls to highlight, highlight pulses (2x 300ms) |
| Click "Edit" on card | Card body becomes textarea | Highlight remains |
| Click "Delete" on card | Card fades out (200ms), removed | Highlight fades out (200ms), removed |

#### FAB (Floating Action Button)

```
Position: fixed, bottom-right, offset from sidebar
Size: 56px circle
Background: primary-container
Icon: add_comment (filled)
Shadow: 0 4px 24px rgba(primary, 0.3)
Hover: scale 1.05, bg primary-fixed-dim
Active: scale 0.95
```

---

### 3.3 S3: Claude.ai Overlay Mode

**Context**: Extension overlay on actual Claude.ai page (background dimmed at 60% opacity).

#### Overlay Architecture

```
z-index layers:
  0: Claude.ai page (opacity 0.6, behind overlay)
  10: Annotation highlights (absolute positioned, pointer-events: none)
  50: Extension sidebar (fixed right, w=380px, full height)
  100: Floating toolbar (fixed top, right of sidebar)
  999: Comment popover (Shadow DOM)
```

#### Floating Toolbar

```
┌──────────────────────────────────────────┐
│ 🟢 Recording Session  │  ✏️  📷           │
└──────────────────────────────────────────┘
Position: fixed top-16px right-[400px] (sidebar width + 20px gap)
Background: curator-text (dark)
Text: white
Shape: rounded-full
Contents: green pulse dot + "Recording Session" label | pen tool | camera tool
```

#### Submit Button

```
┌──────────────────────────────────────────┐
│        Submit All Comments →              │
└──────────────────────────────────────────┘
Width: 100% of sidebar
Background: primary (#D97757)
Text: white, font-semibold
Height: 48px
Border-radius: 4px
Hover: primary/90
Group hover: arrow translates +4px right
```

#### Submit Button State Machine

```
idle ──click──► processing ──1500ms──► success ──2000ms──► idle
                  │                      │
                  ▼                      ▼
            "Processing..."        "Sent Successfully!"
            opacity 0.8             bg-green-600
            arrow hidden            checkmark icon
```

---

### 3.4 S4: Code Highlighting & Comment Editor

**Context**: User has selected a code block region. The inline comment editor appears.

#### Code Block Highlight

```css
.highlight-mask {
  background: rgba(217, 119, 87, 0.15);
  border: 1px solid rgba(217, 119, 87, 0.3);
  border-radius: 8px;
  pointer-events: none;
}
```

For line-level highlighting (IDE mode):
```css
.code-block-highlight {
  background: linear-gradient(90deg, rgba(primary, 0.1), rgba(primary-container, 0.2));
  border-left: 3px solid primary;
}
```

#### Floating "Add Comment" Button

```
Position: absolute, near top-right of selection
Size: 40px circle
Background: surface/90 backdrop-blur-md
Border: outline-variant/30
Icon: add_comment (primary color, filled)
Hover: border becomes primary/30, icon scales 1.1
Animation: float (translateY 0→-5px→0, 3s ease infinite)
Tooltip: "Add Comment" (bg-gray-800, 10px, opacity 0→1 on hover)
```

#### Comment Editor Popover

```
┌─────────────────────────────────────────┐
│ [BS avatar] You (Reviewing)              │  ← 12px semibold
│                                          │
│ ┌──────────────────────────────────────┐ │
│ │ What should be improved in this      │ │  ← textarea, 13px
│ │ block?                               │ │     h=96px, resize-none
│ │                                      │ │     placeholder text
│ └──────────────────────────────────────┘ │
│                                          │
│                     [Discard] [Save]     │  ← 11px buttons
└─────────────────────────────────────────┘
Width: 288px (w-72)
Background: curator-cream (#F4F1EA)
Border: outline-variant
Border-radius: 4px
Shadow: shadow-xl
Padding: 16px
```

#### Popover Interaction

| Element | Default | Hover | Active |
|---------|---------|-------|--------|
| Textarea | `bg-white border-curator-border` | — | `ring-primary border-primary` |
| "Discard" | `text-gray-500 11px` | `text-gray-700` | — |
| "Save" | `bg-primary text-white 11px` | `opacity-0.9` | `scale-0.98` |

#### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Cmd/Ctrl + Enter` | Save comment |
| `Escape` | Discard (close editor, remove highlight) |
| `Tab` | Focus moves: textarea → Discard → Save |

---

### 3.5 S5: IDE Split Pane (Advanced Mode)

**Context**: Full workspace mode with code editor on left, annotations panel on right, resizable splitter.

#### Split Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ HEADER (h=56px)                                                  │
│ [Logo] [Workspace|Analytics|History]     [⏱ ⚙] [Submit Comments]│
├──────────┬──────────────────────────────────────┬────────────────┤
│ LEFT NAV │ EDITOR INFO BAR (h=44px)             │                │
│ (w=256px)│ [EDITOR] src/curator_core/analyzer.py│ ANNOTATIONS    │
│          │                              AI Active│ 3 Active       │
│          ├──────────────────────┬─── ║ ──┤                │
│          │ CODE EDITOR          │ sp ║ li│ [Card: Claude] │
│          │ (line numbers + code)│ li ║ tt│  Lines 31-33   │
│          │                      │ tt ║ er│  Threshold 0.85│
│          │   HL: lines 31-33   │ er ║   │  [Resolve][Reply│
│          │   (tertiary highlight│    ║   │                │
│          │    + left border)    │    ║   │ [Card: Jane]   │
│          │                      │    ║   │  Line 25       │
│          │          [FAB: +]    │    ║   │  null buffers  │
│          │                      │    ║   │                │
│          │                      │    ║   │ [Card: Max]    │
│          │                      │    ║   │  Line 38       │
│          │                      │    ║   │  strategy pat. │
│          │                      │    ║   │                │
│          │                      │    ║   │ [Input area]   │
│          │                      │    ║   │ [Post Annotat.]│
├──────────┴──────────────────────┴────╨───┴────────────────┤
│ STATUS BAR (h=24px, bg=primary)                            │
│ CURATOR_NODE: STABLE | SESSION: RESEARCH_01  LN 31 UTF-8  │
└────────────────────────────────────────────────────────────┘
```

#### Resizable Splitter

```
Visual: 1px line (outline-variant/20)
Handle: 11px × 40px pill, centered vertically
  Default: bg-surface, border-outline-variant/30, 3 grip dots
  Hover: bg-primary-container, border-primary/30
  Dragging: cursor col-resize
Min pane width: 300px each
```

#### Enhanced Annotation Card (Multi-User)

```
┌─────────────────────────────────────────────┐
│ ▌ (tertiary left accent bar, 4px)           │
│                                              │
│ [CA avatar] Claude Assistant      #REF_31    │  ← Ref tag (mono, tertiary/5 bg)
│             Lines 31-33 • Just Now           │
│                                              │
│ This relevance threshold `0.85` seems        │  ← Inline code badges
│ arbitrary. Should we move this to a          │
│ configuration file or use a dynamic          │
│ quantile based on the dataset distribution?  │
│                                              │
│ [  Resolve  ] [  Reply  ]                    │  ← Action buttons
└─────────────────────────────────────────────┘

Resolve button: bg-surface-container-highest/50, border, 11px bold
Reply button: bg-primary, text-on-primary, 11px bold
```

#### Inline Annotation Input

```
┌─────────────────────────────────────────────┐
│ ┌─────────────────────────────────────────┐ │
│ │ Type an annotation...                   │ │  ← textarea, 13px, h=80px
│ │                                         │ │
│ └─────────────────────────────────────────┘ │
│ [@] [📎] [#]              [Post Annotation] │  ← Action bar
└─────────────────────────────────────────────┘
Input wrapper: bg-surface-container-low, rounded-xl, border
Focus: border-primary/40, ring-1 ring-primary/20
Post button: bg-primary text-on-primary, rounded-lg, 12px bold
```

#### Status Bar (Terminal Style)

```
Height: 24px
Background: primary (#D97757)
Text: on-primary, 10px, JetBrains Mono, tracking-widest
Content: CURATOR_NODE: [STABLE] | SESSION: RESEARCH_01 | LN 31, COL 12 | UTF-8 | 🟢 UPLINK ACTIVE
```

## 4. Responsive Behavior

### 4.1 Breakpoints

| Breakpoint | Sidebar | Left Nav | Content | Annotations Panel |
|-----------|---------|----------|---------|-------------------|
| ≥1440px | 320px | 256px | Flex | 320-420px |
| 1024-1439px | 280px | 200px | Flex | 280px |
| 768-1023px | Hidden (toggle) | Hidden (hamburger) | Full width | Overlay sheet |
| <768px | Not supported (desktop extension) | — | — | — |

### 4.2 Panel Collapse Behavior

When viewport is narrow, the Side Panel can collapse:
- **Collapsed**: Only badge icon visible (annotation count), click to expand
- **Expanded**: Full annotation list
- **Transition**: 200ms slide-in from right

## 5. Animation Specifications

| Animation | Duration | Easing | Trigger |
|-----------|----------|--------|---------|
| Card appear | 200ms | ease-out | New annotation saved |
| Card fade out (delete) | 200ms | ease-in | Delete confirmed |
| Highlight pulse | 2×300ms | ease-in-out | Click card → scroll to highlight |
| Floating button appear | 150ms | ease-out | Text selected |
| Comment editor slide | 200ms | ease-out | "Add Note" clicked |
| Submit button states | 1500ms + 2000ms | linear | Submit clicked |
| Hover shadow escalation | 200ms | ease | Card hover |
| FAB float | 3000ms | ease-in-out (infinite) | Always (subtle Y oscillation) |
| Splitter handle color | 200ms | ease | Hover |

## 6. Accessibility

| Requirement | Implementation |
|-------------|----------------|
| Focus management | Tab order: content → FAB → sidebar cards → submit button → input |
| Screen reader | `aria-label` on highlights: "Annotated text: [excerpt]". Cards: `role="article"` |
| Keyboard annotation | `Cmd+Shift+A` opens annotation for current selection |
| High contrast | All text meets WCAG 2.1 AA (4.5:1 minimum). Highlights have border fallback for color-blind users. |
| Reduced motion | Respect `prefers-reduced-motion`: disable FAB float, instant transitions |
| Focus visible | `ring-2 ring-primary/40 ring-offset-2` on all interactive elements |

## 7. Dark Mode

All design tokens map to dark mode values via Tailwind `dark:` classes. The `darkMode: "class"` strategy follows the system preference. Key changes:

| Element | Light | Dark |
|---------|-------|------|
| Surface | `#fffcf7` | `#1a1a17` |
| Cards | `#eae9de` | `#3d3d39` |
| Text | `#373831` | `#eae9de` |
| Highlights | `rgba(217,119,87,0.2)` | `rgba(251,146,112,0.25)` |
| Code bg | `#eae9de` | `#2d2d2a` |

## Implementation Status

- **Design tokens**: Extracted from Stitch, documented above
- **Screen specifications**: All 5 screens documented
- **Animation specs**: Complete
- **Accessibility**: Requirements defined
- **Dark mode**: Token mapping defined
- **Implementation**: Not started
