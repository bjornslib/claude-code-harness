# JSONC Schema Reference

Complete schema for design specifications.

## Root Structure

```jsonc
{
  // Required metadata
  "metadata": { ... },

  // Page/component layout
  "layout": { ... },

  // Major content sections
  "sections": [ ... ],

  // Detailed component specs
  "components": [ ... ],

  // Color token mappings
  "colors": { ... },

  // Typography definitions
  "typography": { ... },

  // Interactive behaviors
  "interactions": { ... },

  // Accessibility specs
  "accessibility": { ... },

  // State management (optional)
  "stateManagement": { ... }
}
```

## Metadata

```jsonc
{
  "metadata": {
    "name": "ComponentName",           // PascalCase component name
    "description": "Brief description of purpose",
    "route": "/path/to/route",         // Target route in app
    "version": "1.0",
    "source": {
      "tool": "Figma | GoogleStitch | Screenshot | GeminiImage",
      "hasHtmlCss": true | false,               // true when Stitch HTML/CSS available
      "stitchProjectId": "optional-project-id",  // For edit_screens iteration
      "stitchScreenId": "optional-screen-id",    // For edit_screens iteration
      "codeFile": "path/to/section-code.html"    // When hasHtmlCss=true
    }
  }
}
```

## Layout

```jsonc
{
  "layout": {
    "type": "page | component | modal | drawer",
    "structure": {
      "container": "min-h-screen bg-background",
      "content": "max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8",
      "grid": "grid grid-cols-1 lg:grid-cols-3 gap-6"
    },
    "responsive": {
      "sm": "Single column, stacked layout",
      "md": "2-column grid for main areas",
      "lg": "Full 3-column layout with sidebar",
      "xl": "Centered with max-width constraint"
    }
  }
}
```

## Sections

```jsonc
{
  "sections": [
    {
      "id": "unique-section-id",
      "description": "What this section contains",
      "layout": "flex flex-col gap-4",
      "gridSpan": "lg:col-span-2",        // Optional grid positioning
      "components": ["ComponentA", "ComponentB"],
      "responsive": {
        "sm": "Stack vertically",
        "lg": "Side by side"
      }
    }
  ]
}
```

## Components

```jsonc
{
  "components": [
    {
      "name": "MetricCard",
      "description": "Displays a single KPI with trend",
      "instances": 4,                     // How many in the UI
      "props": {
        "title": "string",
        "value": "string | number",
        "trend": "{ direction: 'up' | 'down', value: string }",
        "icon": "LucideIcon"
      },
      "structure": {
        "container": "bg-card rounded-lg border border-border p-6",
        "iconWrapper": "w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4",
        "icon": "w-5 h-5 text-primary",
        "title": "text-sm text-muted-foreground",
        "value": "text-3xl font-bold text-foreground mt-1",
        "trend": {
          "wrapper": "flex items-center gap-1 mt-2 text-sm",
          "up": "text-green-600 dark:text-green-400",
          "down": "text-destructive"
        }
      },
      "darkMode": {
        "container": "dark:bg-card dark:border-border",
        "iconWrapper": "dark:bg-primary/20"
      },
      "sampleData": [
        {
          "title": "Total Calls",
          "value": "1,247",
          "trend": { "direction": "up", "value": "+12.5%" },
          "icon": "Phone"
        }
      ]
    }
  ]
}
```

## Colors

```jsonc
{
  "colors": {
    // Map to AgenCheck design tokens
    "primary": {
      "usage": "Main CTAs, active states, brand elements",
      "token": "bg-primary text-primary-foreground",
      "extracted": "#1E3A8A"
    },
    "secondary": {
      "usage": "Secondary buttons, links",
      "token": "bg-secondary text-secondary-foreground",
      "extracted": "#3B82F6"
    },
    "muted": {
      "usage": "Backgrounds, disabled states",
      "token": "bg-muted text-muted-foreground"
    },
    "destructive": {
      "usage": "Errors, delete actions",
      "token": "bg-destructive text-destructive-foreground"
    },
    // Custom accents for charts/status
    "accentColors": {
      "success": "#22C55E",
      "warning": "#F59E0B",
      "chart1": "var(--chart-1)",
      "chart2": "var(--chart-2)"
    }
  }
}
```

## Typography

```jsonc
{
  "typography": {
    "headings": {
      "h1": "text-3xl font-bold tracking-tight",
      "h2": "text-2xl font-semibold",
      "h3": "text-xl font-medium",
      "h4": "text-lg font-medium"
    },
    "body": {
      "default": "text-base text-foreground",
      "small": "text-sm text-muted-foreground",
      "label": "text-sm font-medium"
    },
    "special": {
      "metric": "text-3xl font-bold tabular-nums",
      "badge": "text-xs font-medium uppercase tracking-wide"
    }
  }
}
```

## Interactions

```jsonc
{
  "interactions": {
    "buttons": {
      "default": "hover:bg-primary/90 transition-colors",
      "focus": "focus:ring-2 focus:ring-ring focus:ring-offset-2",
      "disabled": "disabled:opacity-50 disabled:cursor-not-allowed"
    },
    "cards": {
      "hover": "hover:shadow-md transition-shadow",
      "clickable": "cursor-pointer hover:border-primary/50"
    },
    "animations": {
      "fadeIn": "animate-in fade-in duration-200",
      "slideUp": "animate-in slide-in-from-bottom-4 duration-300",
      "pulse": "animate-pulse"
    },
    "transitions": {
      "color": "transition-colors duration-150",
      "all": "transition-all duration-200"
    }
  }
}
```

## Accessibility

```jsonc
{
  "accessibility": {
    "landmarks": {
      "main": "role='main'",
      "navigation": "role='navigation' aria-label='Main navigation'",
      "aside": "role='complementary'"
    },
    "labels": {
      "metricsSection": "aria-label='Key performance metrics'",
      "activityFeed": "aria-live='polite' aria-label='Recent activity'"
    },
    "keyboard": {
      "focusOrder": "Follow visual layout order",
      "skipLinks": "Include skip to main content",
      "escapeClose": "Escape closes modals/drawers"
    },
    "screenReader": {
      "statusAnnounce": "aria-live='polite' for status changes",
      "loadingAnnounce": "aria-busy='true' during loading"
    }
  }
}
```

## State Management

```jsonc
{
  "stateManagement": {
    // Only if component needs Zustand
    "required": true | false,
    "store": "useAppStore from @/stores",
    "slices": {
      "existing": ["uiSlice", "workflowSlice"],
      "new": {
        "name": "voiceAgentSlice",
        "state": {
          "agents": "Map<string, AgentStatus>",
          "activeCallsCount": "number"
        },
        "actions": ["fetchAgents", "updateStatus"]
      }
    },
    "realtime": {
      "source": "SSE endpoint /api/voice/events",
      "events": ["agent_status", "call_completed"]
    }
  }
}
```

## Complete Example Structure

See `examples/voice-dashboard.jsonc` for a complete implementation.

## Validation Rules

When generating JSONC, ensure:

1. **All Tailwind classes exist** in the design system
2. **No hardcoded hex values** in structure fields
3. **Dark mode variants** for all color-dependent classes
4. **Responsive classes** at appropriate breakpoints
5. **Component props** are TypeScript-valid types
6. **Icons** use lucide-react names
7. **Sample data** matches prop types
