# AgenCheck Workflow Matrix: Interaction Design Specification

**Version:** 1.0  
**Date:** 15 January 2026  
**Author:** FAIE Labs

---

## 1. Overview

The Workflow Matrix is a configuration interface that enables AgenCheck customers to define automated retry and channel fallback rules for agent communications. Users can create default workflows that apply globally, or override these with client-specific rules for individual end-customers.

### 1.1 Core Design Principles

1. **Progressive Disclosure** — Show the matrix overview first, reveal configuration details on interaction
2. **Visual Hierarchy** — Use colour coding to distinguish rule types at a glance
3. **Fail-Safe Defaults** — Always fall back to default rules when client-specific rules don't exist
4. **Non-Destructive Editing** — Local saves with explicit publish actions; version history available

---

## 2. Information Architecture

### 2.1 Navigation Structure

```
VoiceAgent.ai (AgenCheck)
├── Workflow (current)
│   ├── Default Workflows
│   └── Client-Specific Workflows
├── Analytics
├── Team
└── Logs
```

### 2.2 Data Model

- **Workflow Scope**: Default | Client-Specific
- **Client**: Selected organisation when scope is Client-Specific
- **Rule Group**: A communication channel category (e.g., Phone Calls, SMS/WhatsApp)
- **Action**: A specific communication task placed within the timeline
- **Action Configuration**: Retry count, retry interval, fallback channel

---

## 3. Screen States

### 3.1 Primary States

| State | Trigger | Visual Indicators |
|-------|---------|-------------------|
| **Default Mode** | Initial load or "Default" toggle selected | Default toggle active (outlined), no client selector visible |
| **Client-Specific Mode** | "Client Specific" toggle selected | Client Specific toggle active (filled blue), client dropdown visible |
| **Empty Matrix** | No rules configured for selected scope | Empty cells with "+" affordances only |
| **Populated Matrix** | Rules exist for selected scope | Coloured action cards in appropriate cells |
| **Draft State** | Unsaved changes present | Footer shows "RULE_SET: Vx.x (DRAFT)", green checkmark "All changes saved locally" |
| **Published State** | All changes saved to server | Footer shows "RULE_SET: Vx.x (PUBLISHED)" |
| **Modal Open** | User configuring an action | Configure Action modal overlays matrix, background dimmed |

### 3.2 Workflow Scope Toggle States

The scope toggle is a mutually exclusive button group:

**Default Selected:**
- "Default" button: White background, grey border, black text
- "Client Specific" button: Transparent background, grey border, grey text
- Client dropdown: Hidden

**Client Specific Selected:**
- "Default" button: Transparent background, grey border, grey text
- "Client Specific" button: Blue (#2563EB) background, white text
- Client dropdown: Visible with selected client name and icon

### 3.3 Action Card States

Each action card in the matrix can exist in these states:

| State | Visual Treatment |
|-------|------------------|
| **Primary** | Blue dot indicator (●), solid card background |
| **Fallback Active** | Orange dot indicator (●), indicates this action activates when another fails |
| **Multi-step** | Purple dot indicator (●), indicates part of a sequence |
| **Hover** | Subtle elevation/shadow, cursor pointer |
| **Selected/Editing** | Blue border highlight, Configure Action modal open |
| **Drag in Progress** | Elevated with drop shadow, ghost in original position |

---

## 4. Interaction Patterns

### 4.1 Switching Workflow Scope

**User Goal:** View or edit default workflows vs client-specific workflows

**Flow:**
1. User clicks "Default" or "Client Specific" toggle
2. If switching to Client Specific and no client selected:
   - Client dropdown auto-opens
   - Matrix shows empty state with prompt "Select a client to view their workflow rules"
3. If switching to Default:
   - Client dropdown hides
   - Matrix loads default rules
4. If switching to Client Specific with client already selected:
   - Matrix loads that client's rules (or inherits from default with visual indicator)

**Edge Cases:**
- If client has no specific rules: Show inherited default rules with visual distinction (dashed borders or reduced opacity) and tooltip "Inherited from Default"
- Unsaved changes on scope switch: Warning dialog "You have unsaved changes. Save before switching?"

### 4.2 Selecting a Client

**User Goal:** Choose which client's workflow to configure

**Flow:**
1. User clicks client dropdown
2. Dropdown expands showing searchable client list
3. User types to filter or scrolls to find client
4. User clicks client name
5. Dropdown closes, matrix updates to show client's rules
6. Footer updates to show "CLIENT_ID: [ID]"

**Dropdown Contents:**
- Search input at top
- Scrollable list of clients
- Each row: Client icon, client name, optional badge for "Has custom rules"
- Recent clients at top (separated by divider)

### 4.3 Creating a New Action

**User Goal:** Add a new communication action to the workflow

**Flow:**
1. User clicks "+" button in empty cell (intersection of Rule Group row and Day column)
2. Configure Action modal opens with default values:
   - Max Retries: 3
   - Interval: 10 min
   - Fallback Channel: None
3. User adjusts settings using controls
4. User clicks "Add Rule" (primary button)
5. Modal closes, new action card appears in cell
6. Footer updates to show "DRAFT" status

**Alternative Entry:**
- User can drag existing action from another cell to copy
- User can right-click cell for context menu: "Add Action", "Paste Action"

### 4.4 Configuring an Existing Action

**User Goal:** Edit retry settings, interval, or fallback channel for an existing action

**Flow:**
1. User clicks existing action card in matrix
2. Configure Action modal opens populated with current values
3. User modifies settings:
   - **Max Retries:** Click +/- buttons or type number (range: 1-10)
   - **Interval:** Select from dropdown (5 min, 10 min, 15 min, 30 min, 1 hour, 4 hours, 24 hours)
   - **Fallback Channel:** Select from dropdown (SMS Message, Email, WhatsApp, None)
4. User clicks "Update Rule" (primary button)
5. Modal closes, action card updates to reflect changes
6. If fallback channel set: Orange indicator appears on action card

**Real-time Preview:**
- Modal shows natural language summary: "If all 3 retries fail, the system will switch to SMS channel automatically."
- This updates as user changes values

### 4.5 Deleting an Action

**User Goal:** Remove an action from the workflow

**Flow:**
1. User clicks action card to open Configure Action modal
2. User clicks "Delete" (red text button, bottom-left of modal)
3. Confirmation dialog: "Delete this action? This will remove [Action Name] from [Rule Group]. This cannot be undone."
4. User clicks "Delete" in confirmation dialog
5. Modal closes, action card removed from matrix
6. If client-specific and underlying default exists: Cell shows inherited default action (dashed style)

**Alternative:**
- Keyboard shortcut: Select action, press Delete/Backspace
- Right-click context menu: "Delete Action"

### 4.6 Moving/Reordering Actions

**User Goal:** Move an action to a different day in the timeline

**Flow:**
1. User clicks and holds action card
2. After 150ms delay, drag mode activates:
   - Card elevates with shadow
   - Ghost remains in original position (50% opacity)
   - Valid drop targets highlight (blue dashed border)
3. User drags to new cell
4. User releases:
   - If valid cell: Card animates to new position
   - If invalid cell (already occupied): Card returns to original position with shake animation
5. Matrix updates, draft status shown

**Constraints:**
- Actions can only move within their Rule Group row
- Cannot drop on occupied cells (must delete existing first)

### 4.7 Saving Changes

**User Goal:** Persist workflow configuration

**Flow:**
1. User makes changes (any of the above interactions)
2. Changes auto-save locally (green checkmark in footer: "All changes saved locally")
3. User clicks "Save Rules" button (blue, top-right)
4. Loading state: Button shows spinner, "Saving..."
5. Success: Toast notification "Workflow rules saved successfully"
6. Footer updates: "RULE_SET: V3.2 (PUBLISHED)"
7. Version increments

**Error Handling:**
- Network failure: Toast "Failed to save. Your changes are preserved locally. Try again?"
- Validation error: Modal with specific issues "Phone Calls cannot have SMS as fallback when SMS rule is inactive"

### 4.8 Viewing History

**User Goal:** See previous versions of workflow configuration

**Flow:**
1. User clicks "View History" button (top-right, secondary style)
2. Side panel slides in from right showing version list:
   - Version number
   - Timestamp
   - Author
   - Change summary
3. User clicks version to preview
4. Matrix dims, overlay shows that version's configuration (read-only)
5. User can click "Restore This Version" or "Close"
6. If restore: Confirmation dialog, then version restored as new draft

---

## 5. Component Specifications

### 5.1 Configure Action Modal

**Dimensions:** 360px wide × auto height  
**Position:** Anchored to selected action card (pointer arrow), or centred for new actions

**Layout:**
```
┌─────────────────────────────────────┐
│ Configure Action                  ✕ │
├─────────────────────────────────────┤
│ MAX RETRIES              INTERVAL   │
│ [−] [3] [+]              [10 min ▼] │
│                                     │
│ FALLBACK CHANNEL                    │
│ [SMS Message                     ▼] │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ If all 3 retries fail, the      │ │
│ │ system will switch to SMS       │ │
│ │ channel automatically.          │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [Delete]              [Update Rule] │
└─────────────────────────────────────┘
```

**Behaviour:**
- Appears on action card click or "+" click
- Closes on: ✕ click, Escape key, "Update Rule"/"Add Rule" click, click outside modal
- Unsaved changes on close: Discard without warning (consider adding warning)

### 5.2 Matrix Grid

**Columns:**
- Rule Groups (Channels): ~300px, fixed
- Immediate: 120px
- Day 1: 120px
- Day 2: 120px
- Day 3: 120px
- Day 4: 120px (expandable for more days)

**Rows:**
- Header row: Column titles, sticky
- Rule Group rows: Variable height based on content, minimum 80px

**Cell States:**
- Empty: Light grey dashed border, "+" centre-aligned
- Populated: Action card with icon, title, subtitle, status indicators

### 5.3 Action Card

**Dimensions:** Fills cell with 8px padding  
**Contents:**
- Icon (top-left): Channel-specific icon
- Title: Action name (e.g., "Initial Call", "Email Request")
- Subtitle: Additional info (e.g., "1x → SMS", "No retry")
- Status indicator: Coloured dot (top-right corner)

**Visual Variants:**
- Primary (blue): Standard action
- Fallback (orange): Activated by another action's failure
- Multi-step (purple): Part of a sequence

---

## 6. Error States and Edge Cases

### 6.1 Circular Fallback Prevention

**Scenario:** User tries to set SMS as fallback for Email, but Email is already fallback for SMS

**Handling:**
- Fallback dropdown disables circular options
- Tooltip on disabled option: "Cannot select: would create circular fallback"

### 6.2 Empty Client Workflows

**Scenario:** Client has no specific rules configured

**Handling:**
- Matrix shows inherited default rules with visual distinction:
  - Dashed card borders
  - Muted colours (60% opacity)
  - Tooltip: "Inherited from Default. Click to customise for this client."
- First customisation creates a client-specific override

### 6.3 Default Rule Deletion Impact

**Scenario:** User deletes a default rule that client-specific rules inherit

**Handling:**
- Warning dialog: "This default rule is inherited by 3 clients. Deleting it will affect: Acme Corp, Beta Ltd, Gamma Inc. Continue?"
- Option to "View affected clients" before confirming

### 6.4 Client Without Fallback Rules

**Scenario:** Client has custom primary rule but no fallback configured

**Handling:**
- Soft warning indicator (yellow) on action card
- Tooltip: "No fallback configured. If this action fails, no retry will occur."
- Does not block saving (user may intentionally want no fallback)

---

## 7. Accessibility Considerations

### 7.1 Keyboard Navigation

- Tab moves between: Scope toggle → Client dropdown → Matrix cells → Action buttons
- Arrow keys navigate within matrix grid
- Enter/Space opens Configure Action modal on focused cell
- Escape closes modal

### 7.2 Screen Reader Support

- Scope toggle announced as "Workflow scope, button group, Default selected" or "Client Specific selected"
- Matrix announced as "Workflow matrix, grid with 4 rule groups and 5 time columns"
- Action cards announced with full context: "Phone Calls, Day 1, Follow-up, 3 retries, falls back to SMS"

### 7.3 Colour Independence

- Status indicators use colour + shape (filled circle vs outlined vs dotted)
- Error states use icon + colour
- All interactive elements have visible focus rings

---

## 8. Responsive Considerations

### 8.1 Desktop (>1200px)
- Full matrix visible
- Side-by-side controls
- Configure Action modal positioned relative to card

### 8.2 Tablet (768px-1200px)
- Matrix horizontally scrollable
- Sticky Rule Groups column
- Configure Action modal centred

### 8.3 Mobile (<768px)
- Not recommended for this interface
- Show read-only summary with link to "Edit on desktop"
- Or: Collapse to list view with expandable rule groups

---

## 9. Animation Specifications

| Interaction | Animation | Duration | Easing |
|-------------|-----------|----------|--------|
| Modal open | Fade + scale up | 150ms | ease-out |
| Modal close | Fade + scale down | 100ms | ease-in |
| Action card drag | Elevation increase | 100ms | ease-out |
| Card drop (valid) | Slide to position | 200ms | ease-out |
| Card drop (invalid) | Return + shake | 300ms | ease-out + wiggle |
| Scope toggle | Slide highlight | 150ms | ease-in-out |
| Toast appear | Slide up + fade | 200ms | ease-out |
| Toast dismiss | Slide down + fade | 150ms | ease-in |

---

## 10. Future Considerations

1. **Bulk Actions:** Select multiple actions for batch configuration changes
2. **Templates:** Save workflow configurations as templates for quick client setup
3. **A/B Testing:** Support for testing different retry strategies per client segment
4. **Analytics Integration:** Show success rates per action directly in matrix
5. **Conditional Logic:** "If time is outside business hours, use SMS instead of Call"
6. **Day Extensions:** Configurable timeline length beyond Day 4
