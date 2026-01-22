# Interaction Design Document Template

Use this template to generate professional interaction design documentation from a design image.

---

# {Component/Feature Name}: Interaction Design Specification

**Version:** 1.0  
**Date:** {Current Date}  
**Author:** FAIE Labs

---

## 1. Overview

{2-3 paragraphs describing:}
- What this interface does and its purpose
- The core user problem it solves
- Key design principles guiding the implementation

### 1.1 Core Design Principles

{List 3-5 principles, e.g.:}
1. **Progressive Disclosure** — Show overview first, reveal details on interaction
2. **Visual Hierarchy** — Use colour/size to distinguish importance
3. **Fail-Safe Defaults** — Always fall back to sensible defaults
4. **Non-Destructive Editing** — Preserve user work, require explicit actions

---

## 2. Information Architecture

### 2.1 Navigation Structure

```
{Application Name}
├── {Route 1}
│   ├── {Sub-route}
│   └── {Sub-route}
├── {Route 2} (current)
│   ├── {View 1}
│   └── {View 2}
└── {Route 3}
```

### 2.2 Data Model

{Describe the key entities and relationships:}
- **{Entity 1}**: {Description}
- **{Entity 2}**: {Description}
- **Relationship**: {How entities relate}

---

## 3. Screen States

### 3.1 Primary States

| State | Trigger | Visual Indicators |
|-------|---------|-------------------|
| **{State Name}** | {What causes this state} | {How user recognises it} |
| **Loading** | Initial data fetch | Skeleton placeholders |
| **Empty** | No data exists | Empty state illustration + CTA |
| **Populated** | Data loaded | Content displayed |
| **Error** | Request failed | Error message + retry |
| **Draft** | Unsaved changes | Draft indicator in UI |

### 3.2 Component-Specific States

#### {Component Name}

| State | Visual Treatment |
|-------|------------------|
| **Default** | {Description} |
| **Hover** | {Description} |
| **Active/Selected** | {Description} |
| **Disabled** | {Description} |
| **Loading** | {Description} |

{Repeat for each major component}

---

## 4. Interaction Patterns

### 4.1 {Interaction Name}

**User Goal:** {What the user wants to accomplish}

**Flow:**
1. User {action}
2. System {response}
3. User {action}
4. System {response}
5. {Completion state}

**Edge Cases:**
- If {condition}: {behaviour}
- If {condition}: {behaviour}

### 4.2 {Interaction Name}

{Repeat pattern for each major interaction}

**Common interactions to document:**
- Creating new items
- Editing existing items
- Deleting items (with confirmation)
- Filtering/searching
- Sorting
- Selecting/multi-selecting
- Saving changes
- Navigating between views
- Opening modals/drawers
- Form submission
- Error recovery

---

## 5. Component Specifications

### 5.1 {Component Name}

**Dimensions:** {Width × Height or responsive behaviour}  
**Position:** {Where it appears, anchoring}

**Layout:**
```
┌─────────────────────────────────────┐
│ {Header area}                       │
├─────────────────────────────────────┤
│ {Content area}                      │
│                                     │
│                                     │
├─────────────────────────────────────┤
│ {Footer/actions}                    │
└─────────────────────────────────────┘
```

**Behaviour:**
- {How it appears/disappears}
- {How it responds to user input}
- {Keyboard interactions}

### 5.2 {Grid/Layout Component}

**Columns:**
- {Column 1}: {width}, {behaviour}
- {Column 2}: {width}, {behaviour}

**Rows:**
- {Row specification}

**Cell States:**
- Empty: {description}
- Populated: {description}
- Selected: {description}

---

## 6. Error States and Edge Cases

### 6.1 {Edge Case Name}

**Scenario:** {Description of the situation}

**Handling:**
- {What the system does}
- {What the user sees}
- {How to recover}

### 6.2 Common Edge Cases to Document

- Empty states (no data)
- Partial data (some fields missing)
- Maximum limits (too many items)
- Concurrent editing (multiple users)
- Network failure (offline/timeout)
- Validation errors
- Permission denied
- Deleted/moved resources
- Circular references
- Duplicate detection

---

## 7. Accessibility Considerations

### 7.1 Keyboard Navigation

- Tab: {Navigation order description}
- Arrow keys: {Grid/list navigation}
- Enter/Space: {Activation behaviour}
- Escape: {Cancel/close behaviour}

### 7.2 Screen Reader Support

- {Region/landmark} announced as "{announcement}"
- {Component} announced with "{ARIA label}"
- {Live region} for "{dynamic content}"

### 7.3 Colour Independence

- {How information is conveyed without colour alone}
- {Alternative indicators: icons, text, patterns}

### 7.4 Focus Management

- Focus {behaviour} when {event}
- Focus trap in {modals/dialogs}
- Skip links for {navigation}

---

## 8. Responsive Considerations

### 8.1 Desktop (>1200px)

- {Full layout description}
- {Multi-column arrangements}
- {Hover interactions available}

### 8.2 Tablet (768px-1200px)

- {Adapted layout}
- {Column changes}
- {Touch-friendly targets}

### 8.3 Mobile (<768px)

- {Single column or alternative layout}
- {Hidden elements / drawer navigation}
- {Touch gestures}
- {Minimum touch target: 44×44px}

---

## 9. Animation Specifications

| Interaction | Animation | Duration | Easing |
|-------------|-----------|----------|--------|
| Modal open | Fade + scale up | 150ms | ease-out |
| Modal close | Fade + scale down | 100ms | ease-in |
| Card hover | Elevation increase | 100ms | ease-out |
| Toast appear | Slide up + fade | 200ms | ease-out |
| Toast dismiss | Slide down + fade | 150ms | ease-in |
| Loading | Skeleton pulse | 1500ms | ease-in-out |
| Success | Check + fade | 300ms | ease-out |
| Error shake | Horizontal wiggle | 300ms | ease-out |

### Animation Principles

- Keep durations under 300ms for responsive feel
- Use ease-out for entrances, ease-in for exits
- Avoid animation on reduced-motion preference
- Loading animations should be subtle

---

## 10. Future Considerations

{List potential enhancements and extensions:}

1. **{Feature}:** {Description and rationale}
2. **{Feature}:** {Description and rationale}
3. **{Feature}:** {Description and rationale}

---

## Document Validation Checklist

Before presenting the document, verify:

- [ ] All screen states documented
- [ ] All major interactions have flows
- [ ] Component specs include dimensions and behaviour
- [ ] Edge cases and error states covered
- [ ] Accessibility requirements specified
- [ ] Responsive behaviour at all breakpoints
- [ ] Animation timings appropriate
- [ ] Future considerations identified

---

## Example Section: Configure Action Modal

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
- Closes on: ✕ click, Escape key, "Update Rule" click, click outside
- Natural language preview updates as values change
