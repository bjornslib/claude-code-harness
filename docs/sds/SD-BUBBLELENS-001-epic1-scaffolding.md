---
title: "SD: BubbleLens Epic 1 - Project Scaffolding & DevOps"
description: "Technical design for Next.js application setup, Neon PostgreSQL provisioning, CI/CD pipeline, and deployment infrastructure"
version: "1.0.0"
last-updated: 2026-03-26
status: draft
type: sd
grade: authoritative
---

# SD-BUBBLELENS-001-Epic1: Project Scaffolding & DevOps

**Parent PRD**: PRD-BUBBLELENS-P1-001 (Epic 1)
**Epic**: Project Scaffolding & DevOps
**Worker Type**: `backend-solutions-engineer`

## Overview

This epic establishes the foundational infrastructure for BubbleLens: a Next.js 14+ application deployed to Vercel, backed by Neon serverless PostgreSQL with Prisma ORM, Upstash Redis for caching/rate-limiting, and Upstash QStash for background job scheduling. A GitHub Actions CI pipeline ensures code quality on every PR.

## Architecture

```
Repository: bubblelens/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── (dashboard)/        # Dashboard routes (no auth for PoC)
│   │   ├── (marketing)/        # Public marketing/landing pages
│   │   ├── api/                # API Route Handlers
│   │   │   ├── feeds/          # Feed ingestion endpoints
│   │   │   ├── persona/        # Persona simulation endpoints
│   │   │   ├── admin/          # Admin endpoints (enrichment/classification status)
│   │   │   └── jobs/           # QStash background job endpoints
│   │   ├── layout.tsx          # Root layout with providers
│   │   └── page.tsx            # Landing page
│   ├── components/             # Shared React components
│   │   ├── ui/                 # shadcn/ui components
│   │   └── ...
│   ├── lib/                    # Shared utilities
│   │   ├── db.ts               # Prisma client singleton
│   │   ├── redis.ts            # Upstash Redis client
│   │   ├── rate-limit.ts       # Rate limiting utility
│   │   └── youtube.ts          # YouTube API client
│   └── types/                  # Shared TypeScript types
├── prisma/
│   ├── schema.prisma           # Database schema
│   └── migrations/             # Migration files
├── extension/                  # Chrome extension (separate build)
│   ├── manifest.json
│   ├── src/
│   └── ...
├── .github/
│   └── workflows/
│       └── ci.yml              # CI pipeline
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

## Component Design

### Next.js Application

- **Framework**: Next.js 14+ with App Router, React Server Components where possible
- **Language**: TypeScript (strict mode)
- **Styling**: Tailwind CSS v3 with shadcn/ui component library
- **Route Groups**: `(dashboard)` for app pages, `(marketing)` for public pages
- **Middleware**: None for PoC (no auth). Auth middleware added in post-MVP Phase 3.

### Database (Neon PostgreSQL)

- **Provider**: Neon serverless PostgreSQL
- **Connection**: `@neondatabase/serverless` driver with WebSocket support for serverless environments
- **Pooling**: Neon's built-in connection pooling (pooler endpoint) for Prisma in serverless context
- **Branching**: `main` branch for production, `dev` branch for development, `staging` branch for staging
- **Extensions**: Enable `pgcrypto` (UUID generation), `pg_trgm` (text search) on provisioning

### Prisma Schema

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider  = "postgresql"
  url       = env("DATABASE_URL")
  directUrl = env("DIRECT_DATABASE_URL")
}

// Anonymous browser sessions (no auth for PoC)
model Browser {
  id        String   @id @default(uuid()) @db.Uuid
  browserId String   @unique @map("browser_id") // UUID generated client-side
  createdAt DateTime @default(now()) @map("created_at") @db.Timestamptz

  demographicProfile DemographicProfile?
  feedSnapshots      FeedSnapshot[]

  @@map("browsers")
}

// Demographic profiles (seeded from research accounts for PoC)
model DemographicProfile {
  id                String   @id @default(uuid()) @db.Uuid
  browserId         String   @unique @map("browser_id") @db.Uuid
  label             String?  // Human-readable label, e.g. "Left-leaning Gay Male 25-34"
  politicalLeaning  Int?     @map("political_leaning") @db.SmallInt
  country           String?
  region            String?
  ageRange          String?  @map("age_range")
  gender            String?
  sexualOrientation String?  @map("sexual_orientation")
  ethnicity         String[] @default([])
  interests         String[] @default([])
  isSeed            Boolean  @default(false) @map("is_seed") // true for research accounts
  updatedAt         DateTime @default(now()) @updatedAt @map("updated_at") @db.Timestamptz

  browser Browser @relation(fields: [browserId], references: [id], onDelete: Cascade)

  @@map("demographic_profiles")
}

model FeedSnapshot {
  id         String   @id @default(uuid()) @db.Uuid
  browserId  String   @map("browser_id") @db.Uuid
  capturedAt DateTime @default(now()) @map("captured_at") @db.Timestamptz
  feedType   String   @map("feed_type")
  rawData    Json     @map("raw_data")

  browser Browser    @relation(fields: [browserId], references: [id], onDelete: Cascade)
  items   FeedItem[]

  @@map("feed_snapshots")
}

model FeedItem {
  id         String @id @default(uuid()) @db.Uuid
  snapshotId String @map("snapshot_id") @db.Uuid
  videoId    String @map("video_id")
  position   Int
  context    String @default("recommended")

  snapshot FeedSnapshot @relation(fields: [snapshotId], references: [id], onDelete: Cascade)
  video    Video        @relation(fields: [videoId], references: [videoId])

  @@map("feed_items")
}

model Video {
  videoId          String    @id @map("video_id")
  title            String?
  channelId        String?   @map("channel_id")
  channelName      String?   @map("channel_name")
  categoryId       Int?      @map("category_id")
  description      String?
  tags             String[]  @default([])
  viewCount        BigInt?   @map("view_count")
  likeCount        BigInt?   @map("like_count")
  publishedAt      DateTime? @map("published_at") @db.Timestamptz
  durationSeconds  Int?      @map("duration_seconds")
  politicalLeaning Int?      @map("political_leaning") @db.SmallInt
  topics           String[]  @default([])
  sentiment        Float?
  enrichedAt       DateTime? @map("enriched_at") @db.Timestamptz
  classifiedAt     DateTime? @map("classified_at") @db.Timestamptz

  feedItems FeedItem[]

  @@map("videos")
}

model Comparison {
  id                  String   @id @default(uuid()) @db.Uuid
  personaA            Json     @map("persona_a")
  personaB            Json     @map("persona_b")
  overlapScore        Float    @map("overlap_score")
  topicDivergence     Json     @map("topic_divergence")
  politicalDivergence Json     @map("political_divergence")
  computedAt          DateTime @default(now()) @map("computed_at") @db.Timestamptz

  @@map("comparisons")
}
```

### Redis (Upstash)

- **Client**: `@upstash/redis` (REST-based, works in serverless)
- **Use Cases**:
  - Rate limiting: sliding window counters per IP (no auth for PoC)
  - Enrichment quota: daily YouTube API quota counter
  - Persona simulation cache: keyed by attribute hash, TTL 1 hour
  - Channel classification cache: aggregate leaning per channel

### QStash (Background Jobs)

- **Client**: `@upstash/qstash`
- **Scheduled Jobs**:
  - Video enrichment: every 15 minutes
  - Content classification: every 15 minutes (runs after enrichment)
- **Job Endpoints**: Next.js API routes (`/api/jobs/enrich`, `/api/jobs/classify`) protected by QStash signature verification

### CI Pipeline (GitHub Actions)

```yaml
name: CI
on: [pull_request]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: npm ci
      - run: npm run lint
      - run: npm run type-check
      - run: npm test
```

## Data Model

See Prisma schema above. Key design decisions:
- **UUID primary keys** for all tables (no sequential IDs that leak information)
- **Browser model replaces User** -- anonymous browser-generated UUIDs, no auth needed for PoC
- **Seeded demographic profiles** -- `is_seed: true` flag distinguishes research accounts from future real users
- **Cascading deletes** from Browser to DemographicProfile and FeedSnapshot
- **Video table is shared** across all browsers -- a video exists once, referenced by many FeedItems
- **JSONB for raw_data** -- flexible schema for evolving feed capture format

## API Design

No API routes in this epic. API routes are defined in Epics 3 and 4.

## Task Breakdown

| Task | Description | File Scope | Worker Type | Dependencies |
|------|-------------|-----------|-------------|-------------|
| T1.1 | Initialize Next.js project | `package.json`, `next.config.ts`, `tsconfig.json`, `tailwind.config.ts`, `src/app/layout.tsx`, `src/app/page.tsx` | backend-solutions-engineer | None |
| T1.2 | Provision Neon PostgreSQL | `prisma/schema.prisma`, `.env.local`, `.env.example` | backend-solutions-engineer | T1.1 |
| T1.3 | Configure Prisma ORM + run initial migration | `prisma/schema.prisma`, `prisma/migrations/*`, `src/lib/db.ts` | backend-solutions-engineer | T1.2 |
| T1.4 | Set up Upstash Redis | `src/lib/redis.ts`, `src/lib/rate-limit.ts` | backend-solutions-engineer | T1.1 |
| T1.5 | Configure Vercel deployment | `vercel.json` (if needed), env vars in Vercel dashboard | backend-solutions-engineer | T1.3 |
| T1.6 | Set up CI pipeline | `.github/workflows/ci.yml` | backend-solutions-engineer | T1.1 |
| T1.7 | Configure QStash | `src/lib/qstash.ts`, `src/app/api/jobs/` | backend-solutions-engineer | T1.4 |

## Testing Strategy

- **Unit tests**: Prisma client instantiation, Redis connection, rate limiter logic
- **Integration tests**: Database migration applies cleanly, CI pipeline runs successfully
- **Smoke test**: Deployed application returns 200 on root path

## Implementation Status

| Task | Status | Last Updated |
|------|--------|-------------|
| T1.1 | Not Started | 2026-03-26 |
| T1.2 | Not Started | 2026-03-26 |
| T1.3 | Not Started | 2026-03-26 |
| T1.4 | Not Started | 2026-03-26 |
| T1.5 | Not Started | 2026-03-26 |
| T1.6 | Not Started | 2026-03-26 |
| T1.7 | Not Started | 2026-03-26 |
