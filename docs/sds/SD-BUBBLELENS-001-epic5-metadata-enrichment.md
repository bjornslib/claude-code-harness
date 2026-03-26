---
title: "SD: BubbleLens Epic 5 - Video Metadata Enrichment Pipeline"
description: "Technical design for YouTube Data API v3 integration and background enrichment job processing"
version: "1.0.0"
last-updated: 2026-03-26
status: draft
type: sd
grade: authoritative
---

# SD-BUBBLELENS-001-Epic5: Video Metadata Enrichment Pipeline

**Parent PRD**: PRD-BUBBLELENS-P2-001 (Epic 5)
**Epic**: Video Metadata Enrichment Pipeline
**Worker Type**: `backend-solutions-engineer`

## Overview

A background job pipeline that discovers un-enriched video IDs from feed captures and calls the YouTube Data API v3 to fetch metadata (title, description, tags, channel info, view/like counts, published date, duration). Runs on a QStash cron schedule, processes in batches of 50, tracks API quota usage in Redis, and handles errors with exponential backoff.

## Architecture

```
QStash Cron (every 15 min)
    │
    ▼
POST /api/jobs/enrich  ──────────────────────────────────────────────────┐
    │                                                                     │
    ├── 1. Query un-enriched video IDs (WHERE enriched_at IS NULL)       │
    ├── 2. Check Redis quota counter (daily limit: 10,000 units)          │
    ├── 3. Batch video IDs (groups of 50)                                 │
    ├── 4. Call YouTube Data API v3 videos.list for each batch            │
    ├── 5. Update videos table with metadata + set enriched_at            │
    ├── 6. Increment Redis quota counter by videos processed              │
    └── 7. Return summary { processed, remaining, quotaUsed, quotaLeft }  │
                                                                          │
Redis: bubblelens:yt_quota:{YYYY-MM-DD} ◄────────────────────────────────┘
    TTL: 24 hours (auto-resets daily)
```

## Component Design

### YouTube API Client

```typescript
// src/lib/youtube.ts
import { google } from 'googleapis';

const youtube = google.youtube({
  version: 'v3',
  auth: process.env.YOUTUBE_API_KEY,
});

interface VideoMetadata {
  videoId: string;
  title: string;
  description: string;
  channelId: string;
  channelName: string;
  categoryId: number;
  tags: string[];
  viewCount: number;
  likeCount: number;
  publishedAt: string;
  durationSeconds: number;
}

async function fetchVideoMetadata(videoIds: string[]): Promise<VideoMetadata[]> {
  // YouTube API allows up to 50 IDs per request
  const response = await youtube.videos.list({
    part: ['snippet', 'statistics', 'contentDetails'],
    id: videoIds,
    maxResults: 50,
  });

  return (response.data.items || []).map((item) => ({
    videoId: item.id!,
    title: item.snippet?.title || '',
    description: item.snippet?.description || '',
    channelId: item.snippet?.channelId || '',
    channelName: item.snippet?.channelTitle || '',
    categoryId: parseInt(item.snippet?.categoryId || '0'),
    tags: item.snippet?.tags || [],
    viewCount: parseInt(item.statistics?.viewCount || '0'),
    likeCount: parseInt(item.statistics?.likeCount || '0'),
    publishedAt: item.snippet?.publishedAt || '',
    durationSeconds: parseDuration(item.contentDetails?.duration || 'PT0S'),
  }));
}

// Parse ISO 8601 duration (PT1H2M3S) to seconds
function parseDuration(iso: string): number {
  const match = iso.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
  if (!match) return 0;
  const hours = parseInt(match[1] || '0');
  const minutes = parseInt(match[2] || '0');
  const seconds = parseInt(match[3] || '0');
  return hours * 3600 + minutes * 60 + seconds;
}
```

### Quota Tracker

```typescript
// src/lib/quota-tracker.ts
import { redis } from './redis';

const DAILY_QUOTA_LIMIT = 9500; // Reserve 500 units for safety
const QUOTA_KEY_PREFIX = 'bubblelens:yt_quota';

function getQuotaKey(): string {
  const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
  return `${QUOTA_KEY_PREFIX}:${today}`;
}

async function getQuotaUsed(): Promise<number> {
  const used = await redis.get<number>(getQuotaKey());
  return used || 0;
}

async function incrementQuota(units: number): Promise<number> {
  const key = getQuotaKey();
  const newTotal = await redis.incrby(key, units);
  // Set TTL to 24 hours if this is the first increment today
  if (newTotal === units) {
    await redis.expire(key, 86400);
  }
  return newTotal;
}

async function hasQuotaRemaining(): Promise<{ allowed: boolean; remaining: number }> {
  const used = await getQuotaUsed();
  const remaining = DAILY_QUOTA_LIMIT - used;
  return { allowed: remaining > 0, remaining };
}
```

### Enrichment Job Handler

```typescript
// src/app/api/jobs/enrich/route.ts
import { verifySignatureAppRouter } from '@upstash/qstash/nextjs';
import { db } from '@/lib/db';
import { fetchVideoMetadata } from '@/lib/youtube';
import { hasQuotaRemaining, incrementQuota } from '@/lib/quota-tracker';

const BATCH_SIZE = 50;
const MAX_BATCHES_PER_RUN = 10; // Process up to 500 videos per run

async function handler(req: Request) {
  // 1. Check quota
  const quota = await hasQuotaRemaining();
  if (!quota.allowed) {
    return Response.json({
      status: 'quota_exhausted',
      remaining: 0,
    });
  }

  // 2. Get un-enriched video IDs
  const unenriched = await db.video.findMany({
    where: { enrichedAt: null },
    select: { videoId: true },
    take: BATCH_SIZE * MAX_BATCHES_PER_RUN,
  });

  if (unenriched.length === 0) {
    return Response.json({ status: 'no_work', processed: 0 });
  }

  // 3. Process in batches
  let processed = 0;
  const videoIds = unenriched.map((v) => v.videoId);

  for (let i = 0; i < videoIds.length; i += BATCH_SIZE) {
    // Re-check quota before each batch
    const batchQuota = await hasQuotaRemaining();
    if (!batchQuota.allowed) break;

    const batch = videoIds.slice(i, i + BATCH_SIZE);

    try {
      const metadata = await fetchVideoMetadata(batch);

      // Update videos in a transaction
      await db.$transaction(
        metadata.map((m) =>
          db.video.update({
            where: { videoId: m.videoId },
            data: {
              title: m.title,
              description: m.description,
              channelId: m.channelId,
              channelName: m.channelName,
              categoryId: m.categoryId,
              tags: m.tags,
              viewCount: BigInt(m.viewCount),
              likeCount: BigInt(m.likeCount),
              publishedAt: m.publishedAt,
              durationSeconds: m.durationSeconds,
              enrichedAt: new Date(),
            },
          })
        )
      );

      // 1 unit per video for videos.list with snippet+statistics+contentDetails
      await incrementQuota(batch.length);
      processed += metadata.length;
    } catch (error: any) {
      if (error?.code === 403) {
        // Quota exceeded at YouTube level
        break;
      }
      // Log and continue with next batch
      console.error(`Enrichment batch failed:`, error);
    }
  }

  return Response.json({
    status: 'completed',
    processed,
    totalPending: videoIds.length - processed,
    quota: await hasQuotaRemaining(),
  });
}

export const POST = verifySignatureAppRouter(handler);
```

### QStash Cron Configuration

Set up via QStash dashboard or API:
```
Schedule: */15 * * * *  (every 15 minutes)
Endpoint: https://bubblelens.app/api/jobs/enrich
Method: POST
Retries: 3
Timeout: 60s
```

### Admin Status Endpoint

```typescript
// GET /api/admin/enrichment-status
// Protected: admin-only (Clerk role check)
export async function GET() {
  const totalVideos = await db.video.count();
  const enriched = await db.video.count({ where: { enrichedAt: { not: null } } });
  const pending = totalVideos - enriched;
  const quota = await hasQuotaRemaining();

  return Response.json({
    totalVideos,
    enriched,
    pending,
    enrichedPercent: totalVideos > 0 ? ((enriched / totalVideos) * 100).toFixed(1) : '0',
    quotaUsedToday: 9500 - quota.remaining,
    quotaRemainingToday: quota.remaining,
  });
}
```

## Data Model

Updates the `videos` table (defined in Epic 1 schema). No new tables.

**Fields updated by enrichment**:
- `title`, `description`, `channel_id`, `channel_name`, `category_id`, `tags`
- `view_count`, `like_count`, `published_at`, `duration_seconds`
- `enriched_at` (set to current timestamp on successful enrichment)

## API Design

| Method | Path | Description | Auth | Trigger |
|--------|------|-------------|------|---------|
| POST | `/api/jobs/enrich` | Run enrichment batch | QStash signature | QStash cron (every 15 min) |
| GET | `/api/admin/enrichment-status` | View enrichment stats | Clerk (admin role) | Manual |

## Task Breakdown

| Task | Description | File Scope | Worker Type | Dependencies |
|------|-------------|-----------|-------------|-------------|
| T5.1 | YouTube Data API v3 client | `src/lib/youtube.ts` | backend-solutions-engineer | T1.1 |
| T5.2 | Batch video metadata fetcher | `src/lib/youtube.ts` | backend-solutions-engineer | T5.1 |
| T5.3 | Enrichment job handler | `src/app/api/jobs/enrich/route.ts` | backend-solutions-engineer | T5.2, T1.3 |
| T5.4 | Quota tracker (Redis) | `src/lib/quota-tracker.ts` | backend-solutions-engineer | T1.4 |
| T5.5 | QStash cron configuration | QStash dashboard / `src/lib/qstash.ts` | backend-solutions-engineer | T1.7, T5.3 |
| T5.6 | Error handling + exponential backoff | `src/lib/youtube.ts`, `src/app/api/jobs/enrich/route.ts` | backend-solutions-engineer | T5.3 |
| T5.7 | Admin enrichment status endpoint | `src/app/api/admin/enrichment-status/route.ts` | backend-solutions-engineer | T5.4 |
| T5.8 | Tests with mocked YouTube API | `src/app/api/jobs/enrich/__tests__/*` | tdd-test-engineer | T5.3 |

## Testing Strategy

- **Unit tests**: ISO 8601 duration parser (edge cases: hours only, minutes only, zero)
- **Unit tests**: Quota tracker (increment, daily reset, limit enforcement)
- **Integration tests**: Enrichment job with mocked YouTube API (successful batch, quota exceeded, API error)
- **Integration tests**: Verify deduplication (already enriched videos are skipped)
- **Integration tests**: Admin status endpoint returns correct counts

## Implementation Status

| Task | Status | Last Updated |
|------|--------|-------------|
| T5.1 | Not Started | 2026-03-26 |
| T5.2 | Not Started | 2026-03-26 |
| T5.3 | Not Started | 2026-03-26 |
| T5.4 | Not Started | 2026-03-26 |
| T5.5 | Not Started | 2026-03-26 |
| T5.6 | Not Started | 2026-03-26 |
| T5.7 | Not Started | 2026-03-26 |
| T5.8 | Not Started | 2026-03-26 |
