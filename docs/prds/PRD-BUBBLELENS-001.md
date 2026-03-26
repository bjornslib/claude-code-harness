---
title: "BubbleLens - Filter Bubble Analyzer for YouTube"
description: "Platform that captures YouTube recommendations, classifies content bias, and enables Walk in Their Shoes persona simulation"
version: "1.0.0"
last-updated: 2026-03-26
status: draft
type: prd
grade: authoritative
prd_id: PRD-BUBBLELENS-001
---

# PRD-BUBBLELENS-001: BubbleLens - Filter Bubble Analyzer for YouTube

## Overview

BubbleLens is a consumer-facing tool that lets users see, understand, and compare their YouTube filter bubble with people who have different demographic and belief profiles. The core differentiating feature -- "Walk in Their Shoes" -- allows a user to select a persona (e.g., "democrat, gay, urban, 25-34") and see a simulated YouTube feed based on aggregated data from real users matching that profile.

**Author**: Bjorn Schliebitz, Faie Group
**Inspiration**: Diary of a CEO podcast with Geoffrey Hinton -- platform algorithms optimize for engagement, not perspective diversity.

## Goals

### Goal 1: Enable Feed Transparency
Users can see exactly what YouTube recommends to them, captured reliably from their actual homepage, with topic and bias classification overlaid.

### Goal 2: Enable Perspective-Taking ("Walk in Their Shoes")
Users can simulate what someone with entirely different attributes would see on YouTube. This is the MVP launch feature and primary differentiator.

### Goal 3: Collect Demographically-Tagged Feed Data
Build an anonymized dataset of YouTube recommendations tagged by user demographics, enabling both the persona simulation feature and future research use cases.

### Goal 4: Respect User Privacy
All demographic data is opt-in, anonymized, and deletable. No PII is linked to feed data. GDPR and Australian Privacy Act compliant from day one.

---

## MVP Phasing Strategy

The product is divided into two phases to reach MVP launch:

| Phase | Name | Focus | Outcome |
|-------|------|-------|---------|
| **Phase 1** | Data Foundation | Extension + Auth + Feed Ingestion + Storage | Users can capture their YouTube feed and submit demographic profile |
| **Phase 2** | Walk in Their Shoes MVP | Classification + Persona Engine + Dashboard | Users can simulate feeds for different personas and see their own feed analyzed |

Post-MVP phases (not in scope for this PRD):
- Phase 3: Bubble Score, weekly digests, comparison engine
- Phase 4: Multi-platform expansion (TikTok, Instagram, X)
- Phase 5: Research API and institutional licensing

---

## Phase 1: Data Foundation & Infrastructure

### Epic 1: Project Scaffolding & DevOps

Set up the Next.js application, cloud PostgreSQL database, and deployment pipeline.

**Acceptance Criteria:**
- AC-1.1: Next.js 14+ App Router project with TypeScript is deployed to Vercel
- AC-1.2: Neon PostgreSQL database is provisioned with connection pooling enabled
- AC-1.3: Prisma ORM is configured with initial schema migrations
- AC-1.4: CI/CD pipeline runs lint, type-check, and tests on every PR
- AC-1.5: Environment configuration supports development, staging, and production

### Epic 2: Chrome Extension - Feed Capture

Build a Manifest V3 Chrome extension that captures YouTube homepage video recommendations and sends them to the backend.

**Acceptance Criteria:**
- AC-2.1: Extension injects content script on `youtube.com` pages
- AC-2.2: Content script parses `ytd-rich-item-renderer` elements and extracts video ID, title, channel name, thumbnail URL, and position
- AC-2.3: Extension popup shows "Capture Feed" button; clicking it triggers a capture and displays count of videos found
- AC-2.4: Captured feed data is sent to the backend API as structured JSON within 3 seconds
- AC-2.5: Extension handles YouTube DOM changes gracefully with fallback selectors
- AC-2.6: Extension stores captures locally when offline and syncs when connection is restored

### Epic 3: User Authentication & Onboarding Survey

Implement user signup/login with Clerk and a demographic onboarding survey.

**Acceptance Criteria:**
- AC-3.1: Users can sign up and log in via Clerk (email + Google OAuth)
- AC-3.2: Onboarding survey presents 7 optional demographic fields: political leaning (5-point scale), country/region, age range, primary interests (multi-select), ethnicity (multi-select, optional), gender (optional), sexual orientation (optional)
- AC-3.3: All survey fields display "Prefer not to say" option
- AC-3.4: Survey responses are stored with anonymous user IDs only -- no PII linkage
- AC-3.5: Users can update or delete their demographic profile at any time
- AC-3.6: Privacy policy and data handling explanation are shown before survey

### Epic 4: Feed Ingestion API & Storage

Build the API routes to receive feed captures from the extension and store them in the database.

**Acceptance Criteria:**
- AC-4.1: `POST /api/feeds` endpoint accepts feed capture JSON from the extension
- AC-4.2: Feed snapshots are stored in `feed_snapshots` table with timestamp and feed type
- AC-4.3: Individual videos are normalized into `feed_items` table with position and context
- AC-4.4: API validates payload structure and rejects malformed data with descriptive errors
- AC-4.5: Rate limiting prevents abuse (max 10 captures per user per hour)
- AC-4.6: API requires authenticated session (Clerk JWT validation)

---

## Phase 2: Walk in Their Shoes MVP

### Epic 5: Video Metadata Enrichment Pipeline

Enrich captured video IDs with metadata from the YouTube Data API v3.

**Acceptance Criteria:**
- AC-5.1: Background job processes new video IDs from `feed_items` and calls YouTube Data API v3
- AC-5.2: Video metadata stored in `videos` table: title, description, tags, category, channel info, view/like counts, published date, duration
- AC-5.3: API quota usage is tracked and stays within daily limits (10,000 units/day default)
- AC-5.4: Videos already enriched are skipped (deduplication by `video_id`)
- AC-5.5: Enrichment job runs on a schedule (QStash cron) and processes in batches of 50

### Epic 6: Content Classification Pipeline

Classify enriched videos along political, topic, and diversity axes using AI.

**Acceptance Criteria:**
- AC-6.1: Each video receives a political leaning classification: Left, Center-Left, Center, Center-Right, Right
- AC-6.2: Each video receives topic tags (more granular than YouTube's 15 categories)
- AC-6.3: Each video receives a sentiment score (positive/negative/neutral)
- AC-6.4: Classification uses title, description, tags, and (when available) transcript
- AC-6.5: Classification achieves >75% agreement with human annotators on a 200-video test set
- AC-6.6: Classification runs as a background job, processing newly enriched videos

### Epic 7: Persona Engine - "Walk in Their Shoes" Simulation

Build the core differentiating feature: users select a demographic persona and see a simulated feed.

**Acceptance Criteria:**
- AC-7.1: User can select persona attributes via interactive controls: political leaning, sexual orientation, gender, ethnicity, age range, country/region
- AC-7.2: System aggregates feed data from real users matching the selected persona attributes
- AC-7.3: Simulated feed displays 20-40 videos with title, channel, thumbnail, and classification overlay (political leaning badge, topic tags)
- AC-7.4: If insufficient data exists for a persona combination (<10 matching users), system displays a "Not enough data yet" message with an invitation to contribute
- AC-7.5: User can compare their own feed side-by-side with the simulated persona feed
- AC-7.6: Comparison highlights content overlap (videos appearing in both feeds) and divergence (unique to each)

### Epic 8: Dashboard & Visualization

Build the user-facing dashboard displaying feed analysis, persona simulation, and comparisons.

**Acceptance Criteria:**
- AC-8.1: Dashboard displays user's most recent captured feed with classification overlays
- AC-8.2: Topic distribution visualization shows breakdown of feed content by category (pie or radar chart)
- AC-8.3: Political leaning distribution shows left-to-right spectrum of feed content
- AC-8.4: "Walk in Their Shoes" panel is prominently featured with persona selector controls
- AC-8.5: Side-by-side comparison view shows user's feed vs. simulated persona feed
- AC-8.6: Dashboard is responsive and works on desktop (primary) and tablet viewports
- AC-8.7: All visualizations load within 2 seconds on a standard broadband connection

---

## Data Model (Core Tables)

```sql
-- Users (anonymous profiles)
users: id (UUID PK), clerk_id (TEXT UNIQUE), created_at (TIMESTAMPTZ)

-- Demographic profiles (all fields optional)
demographic_profiles: user_id (UUID PK FK), political_leaning (SMALLINT 1-5),
  country (TEXT), region (TEXT), age_range (TEXT), gender (TEXT),
  sexual_orientation (TEXT), ethnicity (TEXT[]), interests (TEXT[]),
  updated_at (TIMESTAMPTZ)

-- Feed snapshots
feed_snapshots: id (UUID PK), user_id (UUID FK), captured_at (TIMESTAMPTZ),
  feed_type (TEXT), raw_data (JSONB)

-- Individual feed items (normalized)
feed_items: id (UUID PK), snapshot_id (UUID FK), video_id (TEXT),
  position (INTEGER), context (TEXT)

-- Video metadata (enriched)
videos: video_id (TEXT PK), title (TEXT), channel_id (TEXT),
  channel_name (TEXT), category_id (INTEGER), description (TEXT),
  tags (TEXT[]), view_count (BIGINT), like_count (BIGINT),
  published_at (TIMESTAMPTZ), duration_seconds (INTEGER),
  political_leaning (SMALLINT), topics (TEXT[]), sentiment (REAL),
  enriched_at (TIMESTAMPTZ), classified_at (TIMESTAMPTZ)

-- Comparison results (cached)
comparisons: id (UUID PK), persona_a (JSONB), persona_b (JSONB),
  overlap_score (REAL), topic_divergence (JSONB),
  political_divergence (JSONB), computed_at (TIMESTAMPTZ)
```

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | Next.js 14+ (App Router) + React + TypeScript | SSR for marketing; React for interactive dashboard |
| UI Components | shadcn/ui + Tailwind CSS | Fast, accessible, professional |
| Data Visualization | Recharts + D3.js | Recharts for standard charts; D3 for custom bubble visualizations |
| Auth | Clerk + Google OAuth | Clerk for auth management; Google OAuth for optional YouTube linking |
| Backend/API | Next.js API Routes (Route Handlers) | Single deployable unit; extract later if needed |
| Database | Neon PostgreSQL (serverless) | Scales to zero; branching for dev/staging; connection pooling |
| ORM | Prisma | Type-safe queries; excellent Next.js integration |
| Cache/Queue | Upstash Redis + QStash | Serverless Redis for caching; QStash for background jobs |
| Browser Extension | Chrome Extension (Manifest V3) | Content scripts for DOM parsing; service worker for background sync |
| Hosting | Vercel | Natural fit for Next.js; edge functions; blob storage |
| Analytics | PostHog | Privacy-friendly; self-hostable |

---

## Legal & Compliance

- **YouTube ToS**: Extension reads data already rendered for the user (screen-reader analogy). hiQ v. LinkedIn precedent supports this. Position as research/transparency tool.
- **GDPR**: All demographic data opt-in, anonymized, deletable on request. No PII linked to feed data.
- **Australian Privacy Act**: Compliant with opt-in consent model.
- **Google OAuth Verification**: Required for >100 users. Timeline: 4-8 weeks. Needs privacy policy, ToS, domain verification.

---

## Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| YouTube blocks extension or sends C&D | High | Partner with academic institutions; frame as research; maintain backup collection methods |
| Low user adoption (cold start) | High | Seed with research accounts; partner with digital literacy orgs; PR/media strategy |
| Privacy backlash | Medium | Privacy-by-design; anonymous-first; transparent data practices |
| Google rejects OAuth verification | Medium | Minimize requested scopes; strong privacy policy; consider operating without OAuth initially |
| Classification accuracy | Medium | Multi-signal approach; community correction; transparent methodology |
| YouTube DOM changes break extension | Medium | Resilient selectors with fallbacks; automated DOM structure monitoring; rapid update pipeline |

---

## Implementation Status

| Epic | Status | Last Updated |
|------|--------|-------------|
| Epic 1: Project Scaffolding | Not Started | 2026-03-26 |
| Epic 2: Chrome Extension | Not Started | 2026-03-26 |
| Epic 3: Auth & Onboarding | Not Started | 2026-03-26 |
| Epic 4: Feed Ingestion API | Not Started | 2026-03-26 |
| Epic 5: Video Metadata Enrichment | Not Started | 2026-03-26 |
| Epic 6: Content Classification | Not Started | 2026-03-26 |
| Epic 7: Persona Engine | Not Started | 2026-03-26 |
| Epic 8: Dashboard & Visualization | Not Started | 2026-03-26 |
