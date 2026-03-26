---
title: "SD: BubbleLens Epic 7 - Persona Engine (Walk in Their Shoes)"
description: "Technical design for demographic persona simulation engine with feed aggregation and comparison"
version: "1.0.0"
last-updated: 2026-03-26
status: draft
type: sd
grade: authoritative
---

# SD-BUBBLELENS-001-Epic7: Persona Engine - "Walk in Their Shoes" Simulation

**Parent PRD**: PRD-BUBBLELENS-P2-001 (Epic 7)
**Epic**: Persona Engine - "Walk in Their Shoes" Simulation
**Worker Type**: `backend-solutions-engineer` (engine) + `frontend-dev-expert` (UI)

## Overview

The core differentiating feature of BubbleLens. Users select demographic attributes (political leaning, sexual orientation, gender, ethnicity, age range, country) to create a "persona." The system finds real users matching those attributes, aggregates their captured YouTube feeds, and presents a simulated feed ranked by video frequency across matching users. Users can then compare this simulated feed side-by-side with their own.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Frontend                                                                │
│                                                                          │
│  PersonaSelector ──► SimulatedFeedView ──► ComparisonView               │
│  (attribute controls)  (aggregated feed)    (side-by-side)              │
│                                                                          │
└──────────────┬──────────────────────┬───────────────────────────────────┘
               │                      │
               ▼                      ▼
  GET /api/persona/simulate    GET /api/persona/compare
               │                      │
               ▼                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Persona Engine (Backend)                                                │
│                                                                          │
│  1. Match users by demographic attributes (SQL query with dynamic WHERE) │
│  2. Aggregate their feed_items (rank videos by frequency, weight by      │
│     recency)                                                             │
│  3. Enrich with video metadata + classification data                     │
│  4. Return top 20-40 videos as simulated feed                           │
│  5. Cache result by attribute hash (Redis, TTL 1 hour)                  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Component Design

### Persona Attributes Schema

```typescript
// src/types/persona.ts
interface PersonaAttributes {
  politicalLeaning?: 1 | 2 | 3 | 4 | 5;  // undefined = "Any"
  sexualOrientation?: 'straight' | 'gay' | 'lesbian' | 'bisexual';
  gender?: 'male' | 'female' | 'non_binary';
  ageRange?: '18-24' | '25-34' | '35-44' | '45-54' | '55+';
  country?: string;
  ethnicity?: string[];
}

// Preset personas for quick selection
const PERSONA_PRESETS: Record<string, { label: string; attributes: PersonaAttributes }> = {
  conservative_american: {
    label: 'Conservative American',
    attributes: { politicalLeaning: 4, gender: 'male', ageRange: '45-54', country: 'US' },
  },
  progressive_european: {
    label: 'Progressive European',
    attributes: { politicalLeaning: 2, ageRange: '25-34' },
    // country handled via European country list
  },
  young_urban_lgbtq: {
    label: 'Young Urban LGBTQ+',
    attributes: { politicalLeaning: 2, sexualOrientation: 'gay', ageRange: '18-24' },
  },
  centrist_parent: {
    label: 'Centrist Parent',
    attributes: { politicalLeaning: 3, ageRange: '35-44' },
  },
};
```

### Persona Matching Query

Dynamic SQL construction based on selected attributes:

```typescript
// src/lib/persona-engine.ts
import { Prisma } from '@prisma/client';

function buildPersonaMatchQuery(attrs: PersonaAttributes): Prisma.DemographicProfileWhereInput {
  const where: Prisma.DemographicProfileWhereInput = {};

  if (attrs.politicalLeaning !== undefined) {
    // Match exact or +/- 1 on the scale for broader matching
    where.politicalLeaning = {
      gte: Math.max(1, attrs.politicalLeaning - 1),
      lte: Math.min(5, attrs.politicalLeaning + 1),
    };
  }

  if (attrs.sexualOrientation) {
    where.sexualOrientation = attrs.sexualOrientation;
  }

  if (attrs.gender) {
    where.gender = attrs.gender;
  }

  if (attrs.ageRange) {
    where.ageRange = attrs.ageRange;
  }

  if (attrs.country) {
    where.country = attrs.country;
  }

  if (attrs.ethnicity && attrs.ethnicity.length > 0) {
    where.ethnicity = { hasSome: attrs.ethnicity };
  }

  return where;
}

async function getMatchingUserIds(attrs: PersonaAttributes): Promise<{
  userIds: string[];
  matchCount: number;
}> {
  const where = buildPersonaMatchQuery(attrs);

  const profiles = await db.demographicProfile.findMany({
    where,
    select: { userId: true },
  });

  return {
    userIds: profiles.map((p) => p.userId),
    matchCount: profiles.length,
  };
}
```

### Feed Aggregation Algorithm

```typescript
interface SimulatedFeedVideo {
  videoId: string;
  title: string;
  channelName: string;
  thumbnailUrl: string | null;
  politicalLeaning: number | null;
  topics: string[];
  sentiment: number | null;
  frequency: number;        // How many matching users saw this video
  recencyScore: number;     // Higher = more recent across all feeds
  aggregateScore: number;   // Combined ranking score
}

async function generateSimulatedFeed(
  attrs: PersonaAttributes,
  limit: number = 30
): Promise<{ videos: SimulatedFeedVideo[]; matchCount: number; insufficient: boolean }> {
  const { userIds, matchCount } = await getMatchingUserIds(attrs);

  // Minimum threshold for meaningful simulation
  if (matchCount < 10) {
    return { videos: [], matchCount, insufficient: true };
  }

  // Aggregate: find videos that appear in matching users' recent feeds
  // Rank by: frequency (how many matching users saw it) * recency weight
  const results = await db.$queryRaw<Array<{
    video_id: string;
    frequency: number;
    avg_position: number;
    latest_capture: Date;
  }>>`
    SELECT
      fi.video_id,
      COUNT(DISTINCT fs.user_id) as frequency,
      AVG(fi.position) as avg_position,
      MAX(fs.captured_at) as latest_capture
    FROM feed_items fi
    JOIN feed_snapshots fs ON fi.snapshot_id = fs.id
    WHERE fs.user_id = ANY(${userIds}::uuid[])
      AND fs.captured_at > NOW() - INTERVAL '30 days'
    GROUP BY fi.video_id
    HAVING COUNT(DISTINCT fs.user_id) >= 2  -- Appears in at least 2 users' feeds
    ORDER BY
      COUNT(DISTINCT fs.user_id) DESC,
      MAX(fs.captured_at) DESC
    LIMIT ${limit}
  `;

  // Enrich with video metadata
  const videoIds = results.map((r) => r.video_id);
  const videos = await db.video.findMany({
    where: { videoId: { in: videoIds } },
  });

  const videoMap = new Map(videos.map((v) => [v.videoId, v]));
  const now = Date.now();

  const simulatedFeed: SimulatedFeedVideo[] = results.map((r) => {
    const video = videoMap.get(r.video_id);
    const daysSinceCapture = (now - r.latest_capture.getTime()) / (1000 * 60 * 60 * 24);
    const recencyScore = Math.max(0, 1 - daysSinceCapture / 30); // 1.0 = today, 0.0 = 30 days ago

    return {
      videoId: r.video_id,
      title: video?.title || 'Unknown',
      channelName: video?.channelName || 'Unknown',
      thumbnailUrl: video ? `https://i.ytimg.com/vi/${r.video_id}/mqdefault.jpg` : null,
      politicalLeaning: video?.politicalLeaning ?? null,
      topics: video?.topics || [],
      sentiment: video?.sentiment ?? null,
      frequency: Number(r.frequency),
      recencyScore,
      aggregateScore: Number(r.frequency) * 0.7 + recencyScore * 0.3,
    };
  });

  // Sort by aggregate score
  simulatedFeed.sort((a, b) => b.aggregateScore - a.aggregateScore);

  return { videos: simulatedFeed, matchCount, insufficient: false };
}
```

### Comparison Engine

```typescript
interface ComparisonResult {
  userFeed: SimulatedFeedVideo[];
  personaFeed: SimulatedFeedVideo[];
  overlap: {
    videoIds: string[];
    overlapPercent: number;
  };
  topicDivergence: Record<string, { user: number; persona: number }>;
  politicalDivergence: {
    userAverage: number;
    personaAverage: number;
    delta: number;
  };
}

async function compareFeedWithPersona(
  userId: string,
  personaAttrs: PersonaAttributes
): Promise<ComparisonResult> {
  // Get user's latest feed
  const latestSnapshot = await db.feedSnapshot.findFirst({
    where: { userId },
    orderBy: { capturedAt: 'desc' },
    include: {
      items: {
        include: { video: true },
        orderBy: { position: 'asc' },
      },
    },
  });

  if (!latestSnapshot) {
    throw new Error('No feed captured yet');
  }

  // Get simulated persona feed
  const personaResult = await generateSimulatedFeed(personaAttrs);

  // Compute overlap
  const userVideoIds = new Set(latestSnapshot.items.map((i) => i.videoId));
  const personaVideoIds = new Set(personaResult.videos.map((v) => v.videoId));
  const overlapIds = [...userVideoIds].filter((id) => personaVideoIds.has(id));

  const totalUnique = new Set([...userVideoIds, ...personaVideoIds]).size;
  const overlapPercent = totalUnique > 0 ? (overlapIds.length / totalUnique) * 100 : 0;

  // Topic divergence
  const userTopics = computeTopicDistribution(latestSnapshot.items.map((i) => i.video));
  const personaTopics = computeTopicDistribution(personaResult.videos);
  const allTopics = new Set([...Object.keys(userTopics), ...Object.keys(personaTopics)]);
  const topicDivergence: Record<string, { user: number; persona: number }> = {};
  for (const topic of allTopics) {
    topicDivergence[topic] = {
      user: userTopics[topic] || 0,
      persona: personaTopics[topic] || 0,
    };
  }

  // Political divergence
  const userLeanings = latestSnapshot.items
    .map((i) => i.video.politicalLeaning)
    .filter((l): l is number => l !== null);
  const personaLeanings = personaResult.videos
    .map((v) => v.politicalLeaning)
    .filter((l): l is number => l !== null);

  const userAvg = userLeanings.length > 0
    ? userLeanings.reduce((a, b) => a + b, 0) / userLeanings.length
    : 3;
  const personaAvg = personaLeanings.length > 0
    ? personaLeanings.reduce((a, b) => a + b, 0) / personaLeanings.length
    : 3;

  return {
    userFeed: latestSnapshot.items.map((i) => ({
      videoId: i.videoId,
      title: i.video.title || 'Unknown',
      channelName: i.video.channelName || 'Unknown',
      thumbnailUrl: `https://i.ytimg.com/vi/${i.videoId}/mqdefault.jpg`,
      politicalLeaning: i.video.politicalLeaning,
      topics: i.video.topics || [],
      sentiment: i.video.sentiment,
      frequency: 1,
      recencyScore: 1,
      aggregateScore: 1,
    })),
    personaFeed: personaResult.videos,
    overlap: {
      videoIds: overlapIds,
      overlapPercent: Math.round(overlapPercent * 10) / 10,
    },
    topicDivergence,
    politicalDivergence: {
      userAverage: Math.round(userAvg * 100) / 100,
      personaAverage: Math.round(personaAvg * 100) / 100,
      delta: Math.round(Math.abs(userAvg - personaAvg) * 100) / 100,
    },
  };
}

function computeTopicDistribution(videos: Array<{ topics: string[] | null }>): Record<string, number> {
  const counts: Record<string, number> = {};
  let total = 0;
  for (const v of videos) {
    for (const topic of v.topics || []) {
      counts[topic] = (counts[topic] || 0) + 1;
      total++;
    }
  }
  // Convert to percentages
  const dist: Record<string, number> = {};
  for (const [topic, count] of Object.entries(counts)) {
    dist[topic] = Math.round((count / total) * 1000) / 10; // One decimal %
  }
  return dist;
}
```

### Caching Layer

```typescript
// Cache simulated feeds by attribute hash
function personaCacheKey(attrs: PersonaAttributes): string {
  const sorted = JSON.stringify(attrs, Object.keys(attrs).sort());
  const hash = crypto.createHash('sha256').update(sorted).digest('hex').slice(0, 16);
  return `bubblelens:persona:${hash}`;
}

async function getCachedOrSimulate(
  attrs: PersonaAttributes
): Promise<ReturnType<typeof generateSimulatedFeed>> {
  const key = personaCacheKey(attrs);
  const cached = await redis.get<string>(key);
  if (cached) return JSON.parse(cached);

  const result = await generateSimulatedFeed(attrs);

  // Only cache successful results
  if (!result.insufficient) {
    await redis.set(key, JSON.stringify(result), { ex: 3600 }); // 1 hour TTL
  }

  return result;
}
```

### Frontend Components

#### PersonaSelector

```typescript
// src/components/persona/persona-selector.tsx
// - Grid of attribute controls (radio groups, dropdowns)
// - Preset buttons at top for quick selection
// - "See Their Feed" primary action button
// - "Any" default for all attributes (shows broadest possible simulation)
// - Attribute count badge showing how many attributes are set
```

#### SimulatedFeedView

```typescript
// src/components/persona/simulated-feed.tsx
// - Grid of video cards matching dashboard style
// - Each card: thumbnail, title, channel, political leaning badge, topic tags
// - Frequency indicator (e.g., "Seen by 8 of 12 matching users")
// - Loading skeleton while simulation runs
// - "Not enough data" empty state with sharing CTA
```

#### ComparisonView

```typescript
// src/components/persona/comparison-view.tsx
// - Two-column layout: "Your Feed" | "Their Feed"
// - Overlap percentage header
// - Videos in both feeds highlighted with overlap badge
// - Topic distribution comparison (side-by-side bar chart)
// - Political leaning comparison (two position markers on spectrum)
```

## Data Model

No new tables. Uses existing tables with these key queries:
- `demographic_profiles` — match users by attributes
- `feed_snapshots` + `feed_items` — aggregate videos across matching users
- `videos` — enrich with metadata and classification
- `comparisons` — cache comparison results (optional, for heavy comparisons)

**Redis cache**:
- `bubblelens:persona:{hash}` -> simulated feed JSON (TTL 1 hour)

## API Design

### `GET /api/persona/simulate`
Generate a simulated feed for a persona.

**Query parameters**:
```
?politicalLeaning=2&sexualOrientation=gay&ageRange=25-34
```
All parameters optional. Omitted = "Any".

**Response** (200):
```json
{
  "videos": [
    {
      "videoId": "abc123xyz00",
      "title": "...",
      "channelName": "...",
      "thumbnailUrl": "...",
      "politicalLeaning": 2,
      "topics": ["us_politics", "lgbtq_issues"],
      "sentiment": 0.3,
      "frequency": 8,
      "recencyScore": 0.9,
      "aggregateScore": 0.83
    }
  ],
  "matchCount": 47,
  "insufficient": false
}
```

**Response** (200, insufficient data):
```json
{
  "videos": [],
  "matchCount": 3,
  "insufficient": true
}
```

### `GET /api/persona/compare`
Compare user's feed with a simulated persona feed.

**Query parameters**: Same as `/simulate` plus authenticated user context.

**Response** (200): Full `ComparisonResult` object.

### `GET /api/persona/presets`
Return available preset personas.

**Response** (200):
```json
{
  "presets": [
    { "id": "conservative_american", "label": "Conservative American", "attributes": {...} },
    ...
  ]
}
```

## Task Breakdown

| Task | Description | File Scope | Worker Type | Dependencies |
|------|-------------|-----------|-------------|-------------|
| T7.1 | Persona selector component | `src/components/persona/persona-selector.tsx` | frontend-dev-expert | T1.1 |
| T7.2 | Preset persona definitions | `src/lib/persona-presets.ts` | backend-solutions-engineer | None |
| T7.3 | Persona matching query (dynamic WHERE) | `src/lib/persona-engine.ts` | backend-solutions-engineer | T1.3 |
| T7.4 | Feed aggregation algorithm | `src/lib/persona-engine.ts` | backend-solutions-engineer | T7.3 |
| T7.5 | GET /api/persona/simulate endpoint | `src/app/api/persona/simulate/route.ts` | backend-solutions-engineer | T7.4 |
| T7.6 | Comparison engine | `src/lib/comparison.ts` | backend-solutions-engineer | T7.4 |
| T7.7 | Simulated feed display component | `src/components/persona/simulated-feed.tsx` | frontend-dev-expert | T7.5 |
| T7.8 | Side-by-side comparison view | `src/components/persona/comparison-view.tsx` | frontend-dev-expert | T7.6 |
| T7.9 | Redis caching layer | `src/lib/persona-engine.ts` | backend-solutions-engineer | T7.5, T1.4 |
| T7.10 | Insufficient data handling + sharing CTA | `src/components/persona/insufficient-data.tsx` | frontend-dev-expert | T7.7 |

## Testing Strategy

- **Unit tests**: Persona matching query construction (all attribute combinations, wildcards)
- **Unit tests**: Feed aggregation algorithm (frequency ranking, recency weighting, minimum threshold)
- **Unit tests**: Comparison engine (overlap calculation, topic divergence, political divergence)
- **Unit tests**: Cache key generation (deterministic for same attributes regardless of property order)
- **Integration tests**: Full simulation flow with seeded test data (10+ users with diverse profiles)
- **Integration tests**: Insufficient data response when <10 matching users
- **Component tests**: PersonaSelector renders all controls, preset buttons work
- **Component tests**: ComparisonView displays overlap badges correctly
- **Performance test**: Simulation query completes in <3 seconds with 1000+ users in database

## Implementation Status

| Task | Status | Last Updated |
|------|--------|-------------|
| T7.1 | Not Started | 2026-03-26 |
| T7.2 | Not Started | 2026-03-26 |
| T7.3 | Not Started | 2026-03-26 |
| T7.4 | Not Started | 2026-03-26 |
| T7.5 | Not Started | 2026-03-26 |
| T7.6 | Not Started | 2026-03-26 |
| T7.7 | Not Started | 2026-03-26 |
| T7.8 | Not Started | 2026-03-26 |
| T7.9 | Not Started | 2026-03-26 |
| T7.10 | Not Started | 2026-03-26 |
