# Implementation Rules

Detailed guidelines for Step 3: JSONC to Code implementation.

## File Structure

### Page Route Structure
```
app/{route}/
├── page.tsx              # Main page component (server or client)
├── layout.tsx            # Route-specific layout (optional)
└── _components/          # Route-specific components
    ├── MetricsGrid.tsx
    ├── ActivityFeed.tsx
    └── index.ts          # Re-exports
```

### Component File Pattern
```tsx
// _components/MetricCard.tsx
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Phone } from "lucide-react"

interface MetricCardProps {
  title: string
  value: string | number
  trend?: {
    direction: "up" | "down"
    value: string
  }
  icon: React.ReactNode
}

export function MetricCard({ title, value, trend, icon }: MetricCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <span className="text-sm text-muted-foreground">{title}</span>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold">{value}</div>
        {trend && (
          <p className={`text-sm ${
            trend.direction === "up"
              ? "text-green-600 dark:text-green-400"
              : "text-destructive"
          }`}>
            {trend.value}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
```

## Import Conventions

### UI Components
```tsx
// From shadcn/ui
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogHeader } from "@/components/ui/dialog"
```

### Icons
```tsx
// Always from lucide-react
import {
  Phone,
  Clock,
  CheckCircle,
  Users,
  TrendingUp,
  TrendingDown,
  MoreHorizontal
} from "lucide-react"
```

### State Management
```tsx
// Zustand store
import { useAppStore } from "@/stores"

// Usage
const { threads, setActiveThread } = useAppStore()
```

### Utilities
```tsx
// Class merging
import { cn } from "@/lib/utils"

// Usage
<div className={cn(
  "base-classes",
  condition && "conditional-classes",
  className
)} />
```

## Styling Rules

### Never Use
```tsx
// WRONG: Hardcoded values
<div style={{ color: "#1E3A8A" }}>
<div className="text-[#1E3A8A]">
<div className="w-[200px] p-[10px]">
```

### Always Use
```tsx
// CORRECT: Design tokens
<div className="text-primary">
<div className="text-foreground">
<div className="w-48 p-4">
```

### Dark Mode
```tsx
// Include dark mode variants
<div className="bg-card dark:bg-card border-border dark:border-border">
<span className="text-green-600 dark:text-green-400">
```

### Responsive Classes
```tsx
// Mobile-first approach
<div className="
  grid grid-cols-1
  sm:grid-cols-2
  lg:grid-cols-4
  gap-4
">
```

## Component Patterns

### Metric Card with Icon
```tsx
function MetricCard({ title, value, icon: Icon, trend }) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center gap-4">
          <div className="p-2 rounded-lg bg-primary/10">
            <Icon className="w-5 h-5 text-primary" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold">{value}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
```

### Status Indicator
```tsx
const statusStyles = {
  active: "bg-green-500/10 text-green-600 dark:text-green-400",
  idle: "bg-muted text-muted-foreground",
  error: "bg-destructive/10 text-destructive",
  connecting: "bg-secondary/10 text-secondary animate-pulse"
}

function StatusBadge({ status, label }) {
  return (
    <Badge variant="secondary" className={statusStyles[status]}>
      <span className={cn(
        "w-2 h-2 rounded-full mr-2",
        status === "active" && "bg-green-500",
        status === "connecting" && "animate-pulse"
      )} />
      {label}
    </Badge>
  )
}
```

### Data Grid
```tsx
function MetricsGrid({ metrics }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {metrics.map((metric) => (
        <MetricCard key={metric.id} {...metric} />
      ))}
    </div>
  )
}
```

## Data Management

### Sample Data File
```tsx
// data/voice-dashboard.ts
export const sampleMetrics = [
  {
    id: "calls",
    title: "Total Calls Today",
    value: "1,247",
    trend: { direction: "up" as const, value: "+12.5%" },
    icon: "Phone"
  },
  // ...
]

export const sampleAgents = [
  {
    id: "aura",
    name: "Aura",
    role: "Customer Support",
    status: "active" as const,
    currentCall: "John D. - Billing inquiry"
  },
  // ...
]
```

### Type Definitions
```tsx
// types/voice-dashboard.ts
export interface Metric {
  id: string
  title: string
  value: string | number
  trend?: {
    direction: "up" | "down"
    value: string
  }
  icon: string
}

export interface Agent {
  id: string
  name: string
  role: string
  status: "active" | "idle" | "connecting" | "error"
  currentCall?: string
  lastActive?: string
}
```

## Zustand Integration

### When to Use
- Real-time data updates (SSE/WebSocket)
- Shared state across routes
- Complex state transformations

### Slice Pattern
```tsx
// stores/slices/voiceAgentSlice.ts
import { StateCreator } from 'zustand'
import { immer } from 'zustand/middleware/immer'

export interface VoiceAgentSlice {
  agents: Map<string, Agent>
  activeCallsCount: number
  updateAgentStatus: (id: string, status: Agent['status']) => void
}

export const createVoiceAgentSlice: StateCreator<
  VoiceAgentSlice,
  [['zustand/immer', never]]
> = (set) => ({
  agents: new Map(),
  activeCallsCount: 0,
  updateAgentStatus: (id, status) =>
    set((state) => {
      const agent = state.agents.get(id)
      if (agent) {
        agent.status = status
      }
    }),
})
```

## Validation Checklist

After implementation, verify:

- [ ] `npm run type-check` passes
- [ ] `npm run build` succeeds
- [ ] No hardcoded color values
- [ ] Dark mode toggles correctly
- [ ] Responsive at all breakpoints
- [ ] Components split appropriately
- [ ] Sample data in separate file
- [ ] TypeScript types defined
- [ ] Accessibility labels included

## Common Issues

### Missing shadcn Component
If a component isn't available, install it:
```bash
npx shadcn@latest add [component-name]
```

### Dark Mode Not Working
Ensure using CSS variable-based classes:
```tsx
// Uses CSS variables, works with dark mode
className="bg-card text-foreground"

// Doesn't adapt to dark mode
className="bg-white text-gray-900"
```

### Icon Not Found
Check lucide-react exports:
```tsx
// See full list at https://lucide.dev/icons
import { IconName } from "lucide-react"
```
