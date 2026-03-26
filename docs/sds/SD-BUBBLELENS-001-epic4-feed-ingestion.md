---
title: "SD: BubbleLens Epic 4 - Feed Ingestion API"
description: "Technical design for feed capture ingestion, validation, normalization, and storage API"
version: "1.0.0"
last-updated: 2026-03-26
status: draft
type: sd
grade: authoritative
---

# SD-BUBBLELENS-001-Epic4: Feed Ingestion API & Storage

**Parent PRD**: PRD-BUBBLELENS-P1-001 (Epic 4)
**Epic**: Feed Ingestion API & Storage
**Worker Type**: `backend-solutions-engineer`

## Overview

Build the API layer that receives feed captures from the Chrome extension, validates payloads, normalizes video data into relational tables, applies rate limiting, and provides feed retrieval endpoints. This is the critical data pipeline connecting the extension to the database.

## Architecture

```
src/app/api/feeds/
├── route.ts                    # POST (submit feed), GET (list feeds)
└── [id]/
    └── route.ts                # GET (single feed with items)

src/lib/
├── rate-limit.ts               # Upstash Redis sliding window rate limiter
├── feed-schema.ts              # Zod validation schemas for feed payloads
└── db.ts                       # Prisma client (from Epic 1)
```

## Component Design

### Feed Ingestion Pipeline

```
Extension → POST /api/feeds → Validate (Zod) → Rate Check (Redis, IP-based)
    → Upsert Browser record (by anonymous browser UUID)
    → Create FeedSnapshot (Prisma transaction)
    → For each video:
        → Upsert Video record (video_id as natural key)
        → Create FeedItem (linking snapshot to video with position)
    → Return 201 { snapshotId }
```

### Validation Schema

```typescript
import { z } from 'zod';

const videoItemSchema = z.object({
  videoId: z.string().regex(/^[a-zA-Z0-9_-]{11}$/, 'Invalid YouTube video ID'),
  title: z.string().min(1).max(500),
  channelName: z.string().min(1).max(200),
  thumbnailUrl: z.string().url(),
  position: z.number().int().min(0).max(200),
});

const feedCaptureSchema = z.object({
  browserId: z.string().uuid(), // Anonymous browser UUID from extension
  feedType: z.enum(['homepage', 'up_next', 'search']),
  capturedAt: z.string().datetime(),
  videos: z.array(videoItemSchema).min(1).max(200),
});

type FeedCapturePayload = z.infer<typeof feedCaptureSchema>;
```

### Rate Limiting

Using Upstash Redis sliding window:

```typescript
import { Ratelimit } from '@upstash/ratelimit';
import { redis } from './redis';

const feedRateLimiter = new Ratelimit({
  redis,
  limiter: Ratelimit.slidingWindow(10, '1 h'), // 10 captures per hour
  analytics: true,
  prefix: 'ratelimit:feeds',
});
```

### Feed Ingestion Handler

```typescript
// POST /api/feeds
export async function POST(req: Request) {
  // 1. Rate limit check (IP-based, no auth for PoC)
  const ip = req.headers.get('x-forwarded-for') || 'unknown';
  const { success, remaining, reset } = await feedRateLimiter.limit(ip);
  if (!success) {
    return new Response('Too Many Requests', {
      status: 429,
      headers: {
        'Retry-After': String(Math.ceil((reset - Date.now()) / 1000)),
        'X-RateLimit-Remaining': String(remaining),
      },
    });
  }

  // 2. Validate payload
  const body = await req.json();
  const result = feedCaptureSchema.safeParse(body);
  if (!result.success) {
    return Response.json({ error: result.error.flatten() }, { status: 400 });
  }

  // 3. Ingest in a transaction
  const snapshot = await db.$transaction(async (tx) => {
    // Upsert browser record (anonymous, no auth)
    const browser = await tx.browser.upsert({
      where: { browserId: result.data.browserId },
      create: { browserId: result.data.browserId },
      update: {},
    });

    // Create snapshot
    const snapshot = await tx.feedSnapshot.create({
      data: {
        browserId: browser.id,
        feedType: result.data.feedType,
        capturedAt: result.data.capturedAt,
        rawData: result.data as any,
      },
    });

    // Upsert videos and create feed items
    for (const video of result.data.videos) {
      await tx.video.upsert({
        where: { videoId: video.videoId },
        create: {
          videoId: video.videoId,
          title: video.title,
          channelName: video.channelName,
        },
        update: {
          // Only update title/channel if not already enriched
          title: video.title,
          channelName: video.channelName,
        },
      });

      await tx.feedItem.create({
        data: {
          snapshotId: snapshot.id,
          videoId: video.videoId,
          position: video.position,
          context: 'recommended',
        },
      });
    }

    return snapshot;
  });

  return Response.json({ snapshotId: snapshot.id }, { status: 201 });
}
```

### Feed Retrieval

```typescript
// GET /api/feeds - List feed snapshots by browser ID (no auth)
export async function GET(req: Request) {
  const url = new URL(req.url);
  const browserId = url.searchParams.get('browserId');
  if (!browserId) return Response.json({ error: 'browserId query param required' }, { status: 400 });

  const browser = await db.browser.findUnique({ where: { browserId } });
  if (!browser) return Response.json({ snapshots: [], pagination: { page: 1, limit: 20, total: 0, pages: 0 } });

  const page = parseInt(url.searchParams.get('page') || '1');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '20'), 50);

  const snapshots = await db.feedSnapshot.findMany({
    where: { browserId: browser.id },
    orderBy: { capturedAt: 'desc' },
    skip: (page - 1) * limit,
    take: limit,
    include: {
      _count: { select: { items: true } },
    },
  });

  const total = await db.feedSnapshot.count({ where: { browserId: browser.id } });

  return Response.json({
    snapshots: snapshots.map((s) => ({
      id: s.id,
      feedType: s.feedType,
      capturedAt: s.capturedAt,
      videoCount: s._count.items,
    })),
    pagination: { page, limit, total, pages: Math.ceil(total / limit) },
  });
}
```

```typescript
// GET /api/feeds/[id] - Get single feed with items and video metadata (no auth)
export async function GET(
  req: Request,
  { params }: { params: { id: string } }
) {
  const snapshot = await db.feedSnapshot.findFirst({
    where: { id: params.id },
    include: {
      items: {
        orderBy: { position: 'asc' },
        include: {
          video: {
            select: {
              videoId: true,
              title: true,
              channelName: true,
              categoryId: true,
              viewCount: true,
              politicalLeaning: true,
              topics: true,
              sentiment: true,
              enrichedAt: true,
              classifiedAt: true,
            },
          },
        },
      },
    },
  });

  if (!snapshot) return new Response('Not Found', { status: 404 });

  return Response.json(snapshot);
}
```

## Data Model

Uses tables from Epic 1 schema:
- `browsers` — one record per anonymous browser UUID (upserted on first capture)
- `feed_snapshots` — one record per capture event, linked to browser
- `feed_items` — one record per video in a capture, linked to snapshot and video
- `videos` — upserted on ingestion, enriched later (Epic 4)

**Key relationships**:
```
Browser 1:N FeedSnapshot 1:N FeedItem N:1 Video
```

## API Design

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|-----------|
| POST | `/api/feeds` | Submit feed capture from extension | None (anonymous browser ID) | 10/hour/IP |
| GET | `/api/feeds?browserId=X` | List feed snapshots for a browser ID | None | None |
| GET | `/api/feeds/[id]` | Get single feed with items and video data | None | None |

**Error responses**:

| Status | Body | When |
|--------|------|------|
| 400 | `{ error: { fieldErrors: {...} } }` | Validation failure (including missing browserId) |
| 404 | `Not Found` | Feed snapshot not found |
| 429 | `Too Many Requests` + `Retry-After` header | Rate limit exceeded |

## Task Breakdown

| Task | Description | File Scope | Worker Type | Dependencies |
|------|-------------|-----------|-------------|-------------|
| T3.1 | POST /api/feeds handler (no auth, browser UUID) | `src/app/api/feeds/route.ts` | backend-solutions-engineer | T1.3 |
| T3.2 | Zod validation schema (with browserId) | `src/lib/feed-schema.ts` | backend-solutions-engineer | T3.1 |
| T3.3 | Browser upsert + feed snapshot + item creation (Prisma transaction) | `src/app/api/feeds/route.ts` | backend-solutions-engineer | T3.2 |
| T3.4 | Rate limiting middleware (IP-based) | `src/lib/rate-limit.ts` | backend-solutions-engineer | T1.4 |
| T3.5 | GET /api/feeds (list by browserId) | `src/app/api/feeds/route.ts` | backend-solutions-engineer | T3.1 |
| T3.6 | GET /api/feeds/[id] (detail) | `src/app/api/feeds/[id]/route.ts` | backend-solutions-engineer | T3.1 |
| T3.7 | Error handling + logging | `src/app/api/feeds/route.ts` | backend-solutions-engineer | T3.1-T3.6 |
| T3.8 | Integration tests | `src/app/api/feeds/__tests__/*` | tdd-test-engineer | T3.1-T3.7 |

## Testing Strategy

- **Unit tests**: Zod schema validation (valid payloads, malformed payloads, edge cases like 11-char video IDs)
- **Unit tests**: Rate limiter behavior (allow, deny, reset)
- **Integration tests**: Full POST flow (validate -> upsert browser -> insert -> verify DB state)
- **Integration tests**: GET list with browserId param and pagination
- **Integration tests**: GET detail with nested video data
- **Integration tests**: 400 on missing browserId
- **Integration tests**: 429 on rate limit exceeded
- **Load test** (manual): Verify 10 concurrent captures from different users succeed

## Implementation Status

| Task | Status | Last Updated |
|------|--------|-------------|
| T3.1 | Not Started | 2026-03-26 |
| T3.2 | Not Started | 2026-03-26 |
| T3.3 | Not Started | 2026-03-26 |
| T3.4 | Not Started | 2026-03-26 |
| T3.5 | Not Started | 2026-03-26 |
| T3.6 | Not Started | 2026-03-26 |
| T3.7 | Not Started | 2026-03-26 |
| T3.8 | Not Started | 2026-03-26 |
