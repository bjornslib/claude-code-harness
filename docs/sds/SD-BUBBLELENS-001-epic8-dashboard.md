---
title: "SD: BubbleLens Epic 8 - Dashboard & Visualization"
description: "Technical design for the user-facing dashboard with feed analysis, charts, and Walk in Their Shoes integration"
version: "1.0.0"
last-updated: 2026-03-26
status: draft
type: sd
grade: authoritative
---

# SD-BUBBLELENS-001-Epic8: Dashboard & Visualization

**Parent PRD**: PRD-BUBBLELENS-P2-001 (Epic 8)
**Epic**: Dashboard & Visualization
**Worker Type**: `frontend-dev-expert`

## Overview

The user-facing dashboard that ties together all BubbleLens features: displays the user's captured feed with classification overlays, shows topic distribution and political leaning charts, prominently features the "Walk in Their Shoes" CTA, and handles the empty state for new users. Built with React Server Components where possible, Recharts for standard visualizations, and responsive design for desktop and tablet.

## Architecture

```
src/app/(dashboard)/
├── page.tsx                    # Dashboard home (server component, data fetching)
├── layout.tsx                  # Dashboard shell with navigation
├── walk-in-their-shoes/
│   └── page.tsx                # Persona simulation page
└── settings/
    └── profile/
        └── page.tsx            # Profile management (Epic 3)

src/components/
├── dashboard/
│   ├── feed-grid.tsx           # Video card grid (user's captured feed)
│   ├── video-card.tsx          # Individual video card with classification overlay
│   ├── topic-chart.tsx         # Topic distribution (radar/pie chart)
│   ├── political-spectrum.tsx  # Political leaning bar chart
│   ├── feed-selector.tsx       # Dropdown to switch between past captures
│   ├── dashboard-skeleton.tsx  # Loading skeleton
│   ├── empty-state.tsx         # No feeds captured yet
│   └── walk-cta.tsx            # "Walk in Their Shoes" call-to-action panel
├── persona/                    # (From Epic 7)
│   ├── persona-selector.tsx
│   ├── simulated-feed.tsx
│   └── comparison-view.tsx
└── ui/                         # shadcn/ui components
    ├── button.tsx
    ├── card.tsx
    ├── select.tsx
    ├── badge.tsx
    └── skeleton.tsx
```

## Component Design

### Dashboard Page (Server Component)

```typescript
// src/app/(dashboard)/page.tsx
import { auth } from '@clerk/nextjs/server';
import { db } from '@/lib/db';
import { DashboardClient } from '@/components/dashboard/dashboard-client';
import { EmptyState } from '@/components/dashboard/empty-state';

export default async function DashboardPage() {
  const { userId } = await auth();
  const user = await db.user.findUnique({ where: { clerkId: userId! } });

  // Fetch latest feed snapshot with items and video metadata
  const latestFeed = await db.feedSnapshot.findFirst({
    where: { userId: user!.id },
    orderBy: { capturedAt: 'desc' },
    include: {
      items: {
        orderBy: { position: 'asc' },
        include: {
          video: {
            select: {
              videoId: true, title: true, channelName: true,
              politicalLeaning: true, topics: true, sentiment: true,
              classifiedAt: true,
            },
          },
        },
      },
    },
  });

  // Fetch feed history for selector
  const feedHistory = await db.feedSnapshot.findMany({
    where: { userId: user!.id },
    orderBy: { capturedAt: 'desc' },
    take: 20,
    select: { id: true, capturedAt: true, _count: { select: { items: true } } },
  });

  if (!latestFeed) {
    return <EmptyState />;
  }

  return (
    <DashboardClient
      feed={latestFeed}
      feedHistory={feedHistory}
    />
  );
}
```

### VideoCard Component

```typescript
// src/components/dashboard/video-card.tsx
interface VideoCardProps {
  videoId: string;
  title: string;
  channelName: string;
  politicalLeaning: number | null;
  topics: string[];
  sentiment: number | null;
  position: number;
  overlapBadge?: 'user_only' | 'persona_only' | 'overlap';
}

// Political leaning badge colors
const LEANING_COLORS: Record<number, { bg: string; text: string; label: string }> = {
  1: { bg: 'bg-blue-600', text: 'text-white', label: 'Left' },
  2: { bg: 'bg-blue-400', text: 'text-white', label: 'Center-Left' },
  3: { bg: 'bg-gray-400', text: 'text-white', label: 'Center' },
  4: { bg: 'bg-red-400', text: 'text-white', label: 'Center-Right' },
  5: { bg: 'bg-red-600', text: 'text-white', label: 'Right' },
};

// Card renders:
// - YouTube thumbnail (lazy loaded, mqdefault quality)
// - Title (max 2 lines, truncated)
// - Channel name
// - Political leaning badge (color-coded pill)
// - Topic tags (max 2, truncated)
// - Optional overlap badge for comparison view
```

### Topic Distribution Chart

```typescript
// src/components/dashboard/topic-chart.tsx
'use client';
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from 'recharts';

interface TopicChartProps {
  distribution: Record<string, number>; // topic -> percentage
}

// Takes top 8 topics for readability
// Radar chart with:
// - Polar grid with concentric circles at 25%, 50%, 75%, 100%
// - Topic labels around the perimeter
// - Filled area showing user's distribution
// - Tooltip showing exact percentage on hover
// For comparison mode: overlaid second radar (user vs persona)
```

### Political Spectrum Chart

```typescript
// src/components/dashboard/political-spectrum.tsx
'use client';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface PoliticalSpectrumProps {
  distribution: Array<{ leaning: string; count: number; color: string }>;
}

// Horizontal stacked bar chart:
// - X-axis: Left → Center → Right
// - Bar segments colored: blue gradient (left) → gray (center) → red gradient (right)
// - Tooltip shows count and percentage
// - For comparison: two bars stacked (user on top, persona below)
```

### Walk in Their Shoes CTA Panel

```typescript
// src/components/dashboard/walk-cta.tsx
// Prominent card component:
// - Icon (shoes/perspective metaphor)
// - Headline: "Walk in Their Shoes"
// - Subtext: "See what YouTube recommends to someone with different life experiences"
// - Primary CTA button: "Try it now"
// - Links to /walk-in-their-shoes page
// - Positioned above the fold in the dashboard grid
```

### Empty State

```typescript
// src/components/dashboard/empty-state.tsx
// Displayed when user has no captured feeds:
// 1. Welcome message
// 2. "How it works" in 3 steps:
//    Step 1: Install Chrome Extension (link to Chrome Web Store)
//    Step 2: Visit YouTube and click "Capture Feed"
//    Step 3: See your bubble analyzed
// 3. Extension install button (primary CTA)
// 4. Link to demo/example dashboard with sample data
```

### Feed Selector

```typescript
// src/components/dashboard/feed-selector.tsx
// Dropdown (shadcn Select component):
// - Shows date/time of each past capture + video count
// - Default: most recent capture
// - On change: re-fetches dashboard data for selected snapshot
// - Uses React Query / SWR for client-side data fetching
```

### Dashboard Layout

```
Desktop (≥1024px):
┌──────────────────────────────────────────────────────────┐
│  Navigation Bar (BubbleLens logo, nav links, user menu)  │
├──────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐ ┌────────────────────────────┐ │
│  │  Walk in Their Shoes │ │  Feed Selector             │ │
│  │  CTA Panel           │ │  (dropdown)                │ │
│  └──────────────────────┘ └────────────────────────────┘ │
├──────────────────────────────────────────────────────────┤
│  ┌──────────────────────────┐ ┌────────────────────────┐ │
│  │  Topic Distribution      │ │  Political Spectrum    │ │
│  │  (Radar Chart)           │ │  (Bar Chart)           │ │
│  └──────────────────────────┘ └────────────────────────┘ │
├──────────────────────────────────────────────────────────┤
│  Your Feed                                                │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐          │
│  │Video │ │Video │ │Video │ │Video │ │Video │          │
│  │Card  │ │Card  │ │Card  │ │Card  │ │Card  │          │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘          │
│  (3-5 columns, scrollable)                                │
└──────────────────────────────────────────────────────────┘

Tablet (768px - 1023px):
- Single column layout
- Charts stack vertically
- Video grid: 2 columns
- Walk CTA remains above fold
```

### Data Fetching Strategy

- **Server-side**: Initial dashboard page load fetches latest feed via RSC (no loading state)
- **Client-side**: Feed selector switches use SWR with `GET /api/feeds/[id]` (shows skeleton while loading)
- **Stale-while-revalidate**: SWR default behavior for smooth transitions between feeds
- **Prefetching**: On hover over feed selector options, prefetch that feed's data

```typescript
// src/hooks/use-feed.ts
import useSWR from 'swr';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export function useFeed(snapshotId: string | null) {
  return useSWR(
    snapshotId ? `/api/feeds/${snapshotId}` : null,
    fetcher,
    { revalidateOnFocus: false }
  );
}
```

## Data Model

No new tables. Consumes data from:
- `feed_snapshots` + `feed_items` + `videos` (dashboard display)
- `demographic_profiles` (persona engine, Epic 7)
- `comparisons` (cached comparison results, optional)

## API Design

Dashboard primarily uses existing endpoints from Epics 4 and 7:
- `GET /api/feeds` — feed list for selector
- `GET /api/feeds/[id]` — single feed with video data for display
- `GET /api/persona/simulate` — persona simulation
- `GET /api/persona/compare` — side-by-side comparison

No new API endpoints needed for this epic.

## Task Breakdown

| Task | Description | File Scope | Worker Type | Dependencies |
|------|-------------|-----------|-------------|-------------|
| T8.1 | Dashboard layout (responsive grid) | `src/app/(dashboard)/layout.tsx`, `src/app/(dashboard)/page.tsx` | frontend-dev-expert | T1.1, T3.1 |
| T8.2 | VideoCard component with classification overlays | `src/components/dashboard/video-card.tsx` | frontend-dev-expert | T8.1 |
| T8.3 | Topic distribution chart (Recharts radar) | `src/components/dashboard/topic-chart.tsx` | frontend-dev-expert | T8.1 |
| T8.4 | Political leaning spectrum chart (Recharts bar) | `src/components/dashboard/political-spectrum.tsx` | frontend-dev-expert | T8.1 |
| T8.5 | Walk in Their Shoes CTA panel | `src/components/dashboard/walk-cta.tsx` | frontend-dev-expert | T8.1 |
| T8.6 | Empty state component | `src/components/dashboard/empty-state.tsx` | frontend-dev-expert | T8.1 |
| T8.7 | Data fetching with SWR | `src/hooks/use-feed.ts`, `src/app/(dashboard)/page.tsx` | frontend-dev-expert | T4.5, T4.6 |
| T8.8 | Feed history selector | `src/components/dashboard/feed-selector.tsx` | frontend-dev-expert | T8.7 |
| T8.9 | Performance optimization (lazy images, skeletons, code splitting) | `src/components/dashboard/*` | frontend-dev-expert | T8.1-T8.8 |
| T8.10 | Component tests | `src/components/dashboard/__tests__/*` | tdd-test-engineer | T8.1-T8.8 |

## Testing Strategy

- **Component tests**: VideoCard renders all states (with/without classification, overlap badges)
- **Component tests**: TopicChart renders with various distributions (empty, single topic, many topics)
- **Component tests**: PoliticalSpectrum renders correct colors and proportions
- **Component tests**: EmptyState shows all 3 steps and extension install link
- **Component tests**: FeedSelector triggers data refetch on selection change
- **Integration tests**: Dashboard page renders with server-side data
- **Visual regression**: Screenshot tests for dashboard at desktop and tablet breakpoints
- **Performance test**: Dashboard loads within 2 seconds with 30 classified videos (Lighthouse)
- **Accessibility test**: All charts have ARIA labels; keyboard navigation works

## Implementation Status

| Task | Status | Last Updated |
|------|--------|-------------|
| T8.1 | Not Started | 2026-03-26 |
| T8.2 | Not Started | 2026-03-26 |
| T8.3 | Not Started | 2026-03-26 |
| T8.4 | Not Started | 2026-03-26 |
| T8.5 | Not Started | 2026-03-26 |
| T8.6 | Not Started | 2026-03-26 |
| T8.7 | Not Started | 2026-03-26 |
| T8.8 | Not Started | 2026-03-26 |
| T8.9 | Not Started | 2026-03-26 |
| T8.10 | Not Started | 2026-03-26 |
