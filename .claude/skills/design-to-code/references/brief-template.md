---
title: "Brief Template"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# Brief Template for Design Analysis

Use this template to generate a comprehensive brief from a design image.

## Analysis Prompt

When analyzing a design image, extract the following information:

---

# Design Brief: {Component/Page Name}

## Overview
{2-3 sentences describing what this UI does and its purpose}

## Source
- **Design Tool**: {Figma / Google Stitch / Screenshot}
- **HTML/CSS Provided**: {Yes/No}
- **Target Route**: {/path/to/page}

## Layout Structure

### Overall Layout
{Describe the main container, centering, max-width}

### Sections
1. **Header/Navigation**
   - {Description}

2. **Primary Content Area**
   - {Description}

3. **Secondary/Sidebar**
   - {Description}

4. **Footer (if applicable)**
   - {Description}

## Component Inventory

| Component | Description | Instances | Priority |
|-----------|-------------|-----------|----------|
| {Name} | {What it does} | {Count} | {High/Med/Low} |

## Visual Design

### Color Palette
| Usage | Extracted Color | Maps To Token |
|-------|-----------------|---------------|
| Primary CTA | {hex} | primary |
| Background | {hex} | background |
| Text | {hex} | foreground |
| Accent | {hex} | secondary |

### Typography
- **Headings**: {Style observations}
- **Body Text**: {Style observations}
- **Labels/Captions**: {Style observations}

### Spacing & Layout
- **Container Padding**: {Observations}
- **Card Padding**: {Observations}
- **Grid Gaps**: {Observations}

## Responsive Behavior

### Mobile (< 640px)
- {Layout changes}
- {Component stacking}
- {Hidden elements}

### Tablet (640px - 1024px)
- {Layout changes}
- {Grid columns}

### Desktop (> 1024px)
- {Full layout}
- {Sidebar behavior}

## Interactivity

### Hover States
- {Button hovers}
- {Card hovers}
- {Link hovers}

### Animations
- {Page load animations}
- {Transition effects}
- {Loading states}

### User Actions
- {Click actions}
- {Form submissions}
- {Navigation}

## Data Requirements

### Static Data
- {Labels, titles, descriptions}

### Dynamic Data
- {API endpoints needed}
- {Real-time updates}
- {User-specific data}

### Sample Data Structure
```typescript
interface {DataType} {
  // Fields observed in design
}
```

## Integration Points

### State Management
- {Zustand slices needed}
- {Local state requirements}

### API Integration
- {Endpoints to call}
- {SSE/WebSocket needs}

### Navigation
- {Links to other routes}
- {Breadcrumb structure}

## Accessibility Considerations
- {ARIA labels needed}
- {Focus management}
- {Screen reader announcements}

## Implementation Notes
- {Special considerations}
- {Potential challenges}
- {Suggested component reuse}

---

## Validation Prompt

After generating the brief, present it with:

> **Brief Review Required**
>
> I've analyzed the design and created this brief. Please review each section:
>
> 1. Does the **Overview** capture the purpose correctly?
> 2. Are all **Components** identified?
> 3. Does the **Responsive Behavior** match your expectations?
> 4. Are there any **Interactions** I missed?
>
> Once approved, I'll generate the detailed JSONC specification.

## Common Patterns to Look For

### Dashboard Layouts
- Metric cards in grid (typically 4 columns on desktop)
- Chart areas (usually wider, 2/3 width)
- Activity feeds (sidebar, 1/3 width)
- Status indicators (badges, dots)

### Form Layouts
- Label + input groupings
- Validation states
- Submit/cancel button placement
- Multi-step indicators

### List/Table Views
- Header row with sorting
- Row hover states
- Pagination controls
- Bulk action buttons

### Voice Agent UI Patterns
- Real-time status indicators (active/idle/connecting)
- Call duration displays
- Agent avatars with status dots
- Conversation timelines
