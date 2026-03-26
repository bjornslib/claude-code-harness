---
title: "SD: BubbleLens Epic 6 - Content Classification Pipeline"
description: "Technical design for AI-powered video classification along political, topic, and sentiment axes"
version: "1.0.0"
last-updated: 2026-03-26
status: draft
type: sd
grade: authoritative
---

# SD-BUBBLELENS-001-Epic6: Content Classification Pipeline

**Parent PRD**: PRD-BUBBLELENS-P2-001 (Epic 6)
**Epic**: Content Classification Pipeline
**Worker Type**: `backend-solutions-engineer`

## Overview

An AI-powered classification pipeline that analyzes enriched video metadata (title, description, tags, channel history) to assign political leaning, topic categories, and sentiment scores. Runs as a background job after enrichment, processing newly enriched videos in batches. Targets >75% agreement with human annotators on political leaning and >80% on topic classification.

## Architecture

```
QStash Cron (every 15 min, offset from enrichment)
    │
    ▼
POST /api/jobs/classify
    │
    ├── 1. Query enriched but unclassified videos (enriched_at IS NOT NULL, classified_at IS NULL)
    ├── 2. Batch into groups of 20 (LLM context window optimization)
    ├── 3. For each batch:
    │   ├── Build classification prompt with video metadata
    │   ├── Call Claude API (claude-haiku-4-5 for cost efficiency)
    │   ├── Parse structured JSON response
    │   └── Update videos table with classifications + set classified_at
    └── 4. Update channel-level classification cache (Redis)

Classification Model:
    Input: title + description + tags + channel history
    Output: { politicalLeaning, topics[], sentiment }
```

## Component Design

### Classification Taxonomy

**Political Leaning Scale** (1-5):
| Value | Label | Description |
|-------|-------|-------------|
| 1 | Left | Progressive, social justice, environmental, democratic socialism |
| 2 | Center-Left | Liberal, moderate progressive, mainstream Democratic |
| 3 | Center | Balanced, non-partisan, factual reporting, educational |
| 4 | Center-Right | Conservative, traditional values, mainstream Republican |
| 5 | Right | Strong conservative, nationalist, libertarian right |

**Topic Taxonomy** (40+ categories):
```typescript
const TOPIC_TAXONOMY = [
  // Politics & Society
  'us_politics', 'world_politics', 'elections', 'policy_debate',
  'social_justice', 'civil_rights', 'lgbtq_issues', 'immigration',
  'gun_policy', 'climate_policy', 'economics_policy',
  // News & Current Events
  'breaking_news', 'investigative_journalism', 'opinion_commentary',
  'satire_comedy_news', 'local_news', 'international_affairs',
  // Technology
  'tech_industry', 'ai_ml', 'programming', 'gadgets_reviews',
  'cybersecurity', 'startups',
  // Entertainment
  'movies_tv', 'music', 'celebrity', 'comedy', 'gaming',
  'anime_manga', 'true_crime',
  // Education & Science
  'science', 'history', 'philosophy', 'math', 'language_learning',
  'self_improvement', 'finance_investing',
  // Lifestyle
  'health_fitness', 'cooking_food', 'travel', 'fashion_beauty',
  'home_diy', 'parenting', 'pets_animals',
  // Sports
  'team_sports', 'combat_sports', 'individual_sports', 'esports',
  // Religion & Spirituality
  'religion', 'spirituality', 'meditation',
] as const;
```

**Sentiment Scale**: -1.0 (very negative) to 1.0 (very positive), 0.0 = neutral.

### Classification Prompt

```typescript
function buildClassificationPrompt(videos: VideoForClassification[]): string {
  return `You are a content classifier for a filter bubble analysis tool. Classify each YouTube video along three axes.

## Classification Axes

### Political Leaning (1-5 scale)
1 = Left (progressive, social justice)
2 = Center-Left (liberal, moderate progressive)
3 = Center (balanced, non-partisan, educational)
4 = Center-Right (conservative, traditional)
5 = Right (strong conservative, nationalist)
Use 3 for truly non-political content (cooking, gaming, etc.)

### Topics (1-3 from taxonomy)
Select 1-3 topics from: ${TOPIC_TAXONOMY.join(', ')}

### Sentiment (-1.0 to 1.0)
-1.0 = very negative/angry, 0.0 = neutral/factual, 1.0 = very positive/uplifting

## Videos to Classify

${videos.map((v, i) => `
### Video ${i + 1} (ID: ${v.videoId})
- Title: ${v.title}
- Channel: ${v.channelName}
- Description (first 500 chars): ${v.description?.slice(0, 500) || 'N/A'}
- Tags: ${v.tags?.join(', ') || 'None'}
- Category: ${v.categoryId}
`).join('\n')}

## Response Format

Return a JSON array with one object per video:
\`\`\`json
[
  {
    "videoId": "...",
    "politicalLeaning": 3,
    "topics": ["tech_industry", "ai_ml"],
    "sentiment": 0.2,
    "confidence": 0.85
  }
]
\`\`\`

Classify ALL ${videos.length} videos. Use your best judgment. When uncertain, lean toward Center (3) for political leaning and 0.0 for sentiment.`;
}
```

### Classification Pipeline

```typescript
// src/lib/classifier.ts
import Anthropic from '@anthropic-ai/sdk';

const anthropic = new Anthropic();

interface ClassificationResult {
  videoId: string;
  politicalLeaning: number;
  topics: string[];
  sentiment: number;
  confidence: number;
}

async function classifyVideos(
  videos: VideoForClassification[]
): Promise<ClassificationResult[]> {
  const prompt = buildClassificationPrompt(videos);

  const response = await anthropic.messages.create({
    model: 'claude-haiku-4-5-20251001',
    max_tokens: 4096,
    messages: [{ role: 'user', content: prompt }],
  });

  // Extract JSON from response
  const text = response.content[0].type === 'text' ? response.content[0].text : '';
  const jsonMatch = text.match(/\[[\s\S]*\]/);
  if (!jsonMatch) throw new Error('No JSON array found in classification response');

  const results: ClassificationResult[] = JSON.parse(jsonMatch[0]);

  // Validate results
  return results.filter(
    (r) =>
      r.videoId &&
      r.politicalLeaning >= 1 && r.politicalLeaning <= 5 &&
      Array.isArray(r.topics) && r.topics.length > 0 &&
      r.sentiment >= -1 && r.sentiment <= 1
  );
}
```

### Classification Job Handler

```typescript
// src/app/api/jobs/classify/route.ts
import { verifySignatureAppRouter } from '@upstash/qstash/nextjs';
import { db } from '@/lib/db';
import { classifyVideos } from '@/lib/classifier';

const BATCH_SIZE = 20; // Optimized for LLM context window
const MAX_BATCHES_PER_RUN = 5; // Max 100 videos per run

async function handler(req: Request) {
  const unclassified = await db.video.findMany({
    where: {
      enrichedAt: { not: null },
      classifiedAt: null,
    },
    select: {
      videoId: true,
      title: true,
      description: true,
      channelName: true,
      channelId: true,
      tags: true,
      categoryId: true,
    },
    take: BATCH_SIZE * MAX_BATCHES_PER_RUN,
  });

  if (unclassified.length === 0) {
    return Response.json({ status: 'no_work', processed: 0 });
  }

  let processed = 0;

  for (let i = 0; i < unclassified.length; i += BATCH_SIZE) {
    const batch = unclassified.slice(i, i + BATCH_SIZE);

    try {
      const results = await classifyVideos(batch);

      await db.$transaction(
        results.map((r) =>
          db.video.update({
            where: { videoId: r.videoId },
            data: {
              politicalLeaning: r.politicalLeaning,
              topics: r.topics,
              sentiment: r.sentiment,
              classifiedAt: new Date(),
            },
          })
        )
      );

      // Update channel classification cache
      await updateChannelCache(results);

      processed += results.length;
    } catch (error) {
      console.error(`Classification batch failed:`, error);
      // Continue with next batch
    }
  }

  return Response.json({
    status: 'completed',
    processed,
    totalPending: unclassified.length - processed,
  });
}

export const POST = verifySignatureAppRouter(handler);
```

### Channel Classification Cache

Aggregate political leaning per channel to improve future classifications and enable channel-level analysis:

```typescript
async function updateChannelCache(results: ClassificationResult[]): Promise<void> {
  const byChannel: Record<string, number[]> = {};

  for (const r of results) {
    const video = await db.video.findUnique({
      where: { videoId: r.videoId },
      select: { channelId: true },
    });
    if (video?.channelId) {
      byChannel[video.channelId] = byChannel[video.channelId] || [];
      byChannel[video.channelId].push(r.politicalLeaning);
    }
  }

  for (const [channelId, leanings] of Object.entries(byChannel)) {
    const avg = leanings.reduce((a, b) => a + b, 0) / leanings.length;
    await redis.set(
      `bubblelens:channel_leaning:${channelId}`,
      JSON.stringify({ average: avg, sampleSize: leanings.length }),
      { ex: 86400 * 7 } // Cache for 7 days
    );
  }
}
```

## Data Model

Updates the `videos` table (defined in Epic 1 schema). No new tables.

**Fields updated by classification**:
- `political_leaning` (SMALLINT 1-5)
- `topics` (TEXT[] array)
- `sentiment` (REAL -1.0 to 1.0)
- `classified_at` (TIMESTAMPTZ)

**Redis cache**:
- `bubblelens:channel_leaning:{channelId}` -> `{ average: number, sampleSize: number }` (TTL 7 days)

## API Design

| Method | Path | Description | Auth | Trigger |
|--------|------|-------------|------|---------|
| POST | `/api/jobs/classify` | Run classification batch | QStash signature | QStash cron (every 15 min) |
| GET | `/api/admin/classification-status` | View classification stats | Clerk (admin role) | Manual |

## Task Breakdown

| Task | Description | File Scope | Worker Type | Dependencies |
|------|-------------|-----------|-------------|-------------|
| T6.1 | Classification taxonomy design | `src/lib/taxonomy.ts` | backend-solutions-engineer | None |
| T6.2 | LLM classification prompt + parser | `src/lib/classifier.ts` | backend-solutions-engineer | T6.1 |
| T6.3 | Classification job handler | `src/app/api/jobs/classify/route.ts` | backend-solutions-engineer | T6.2, T1.3 |
| T6.4 | Channel classification cache (Redis) | `src/lib/classifier.ts` | backend-solutions-engineer | T6.3, T1.4 |
| T6.5 | QStash cron configuration | QStash dashboard | backend-solutions-engineer | T1.7, T6.3 |
| T6.6 | Create 200-video human-annotated test set | `tests/fixtures/classification-test-set.json` | backend-solutions-engineer | T6.1 |
| T6.7 | Accuracy measurement script | `scripts/measure-classification-accuracy.ts` | backend-solutions-engineer | T6.2, T6.6 |
| T6.8 | Confidence scores + future community correction hooks | `src/lib/classifier.ts` | backend-solutions-engineer | T6.2 |

## Testing Strategy

- **Unit tests**: Prompt construction with various video metadata combinations
- **Unit tests**: JSON response parsing (valid, malformed, missing fields)
- **Unit tests**: Taxonomy validation (all topics are in the predefined list)
- **Integration tests**: Full classification pipeline with mocked LLM responses
- **Accuracy tests**: Run classifier on 200-video test set, measure agreement with human labels
- **Cost estimation**: Track token usage per classification batch to project monthly costs

## Implementation Status

| Task | Status | Last Updated |
|------|--------|-------------|
| T6.1 | Not Started | 2026-03-26 |
| T6.2 | Not Started | 2026-03-26 |
| T6.3 | Not Started | 2026-03-26 |
| T6.4 | Not Started | 2026-03-26 |
| T6.5 | Not Started | 2026-03-26 |
| T6.6 | Not Started | 2026-03-26 |
| T6.7 | Not Started | 2026-03-26 |
| T6.8 | Not Started | 2026-03-26 |
