---
title: "BubbleLens Phase 1 - Data Foundation & Infrastructure"
description: "Chrome extension, lightweight demographic survey, anonymous feed ingestion, and cloud infrastructure for the BubbleLens PoC"
version: "1.2.0"
last-updated: 2026-03-26
status: draft
type: prd
grade: authoritative
prd_id: PRD-BUBBLELENS-P1-001
---

# PRD-BUBBLELENS-P1-001: BubbleLens Phase 1 - Data Foundation & Infrastructure

## Overview

Phase 1 establishes the complete data collection pipeline for the BubbleLens proof of concept: a Chrome extension that captures YouTube homepage recommendations, a lightweight 3-field demographic survey triggered after first capture, and a backend API that ingests and stores everything. No user accounts -- the PoC uses anonymous browser-generated UUIDs. At the end of Phase 1, users can install the extension, capture their YouTube feed, answer 3 demographic questions, and the demographically-tagged feed data is ready for Phase 2's persona simulation.

**Parent PRD**: PRD-BUBBLELENS-001
**Depends On**: Nothing (greenfield)
**Blocks**: PRD-BUBBLELENS-P2-001 (Phase 2 requires feed data to exist)

## Goals

### Goal 1: Reliable Feed Capture
The Chrome extension captures 95%+ of visible YouTube homepage video recommendations accurately and sends them to the backend within 3 seconds.

### Goal 2: Low-Friction Demographic Collection
No signup, no login. After first capture, a 3-field survey collects political leaning, age range, and gender/orientation. All fields optional. Proves the end-to-end data pipeline with real user demographics.

### Goal 3: Scalable Data Ingestion
The backend reliably ingests, validates, and stores feed captures with rate limiting and error handling.

---

## Epic 1: Project Scaffolding & DevOps

### Description
Initialize the Next.js application, provision cloud infrastructure (Neon PostgreSQL, Upstash Redis, Vercel), configure the ORM, and establish the CI/CD pipeline.

### Acceptance Criteria

```gherkin
Feature: Project Infrastructure

  Scenario: Application deploys successfully
    Given the Next.js 14+ App Router project with TypeScript
    When I push to the main branch
    Then the application deploys to Vercel without errors
    And the deployment is accessible via HTTPS

  Scenario: Database is operational
    Given a Neon PostgreSQL database with connection pooling
    When the application connects via Prisma
    Then queries execute successfully
    And connection pooling handles concurrent serverless function connections

  Scenario: Schema migrations work
    Given Prisma schema with core tables defined
    When I run prisma migrate deploy
    Then all tables (browsers, demographic_profiles, feed_snapshots, feed_items, videos) are created
    And foreign key relationships are enforced

  Scenario: CI pipeline catches issues
    Given a pull request with code changes
    When the CI pipeline runs
    Then it executes lint, type-check, and test stages
    And blocks merge if any stage fails

  Scenario: Environment configuration
    Given development, staging, and production environments
    When I deploy to each
    Then each uses its own database branch (Neon branching)
    And environment variables are isolated
```

### Task Breakdown
- T1.1: Initialize Next.js 14+ App Router project with TypeScript, ESLint, Prettier
- T1.2: Provision Neon PostgreSQL database with dev/staging/production branches
- T1.3: Configure Prisma ORM with initial schema migration (core tables, no auth)
- T1.4: Set up Upstash Redis for rate limiting and caching
- T1.5: Configure Vercel deployment with environment variables
- T1.6: Set up GitHub Actions CI pipeline (lint, type-check, test)
- T1.7: Configure Upstash QStash for background job scheduling

---

## Epic 2: Chrome Extension - Feed Capture

### Description
Build a Manifest V3 Chrome extension that injects a content script on YouTube pages, parses the homepage video grid, and sends structured feed data to the BubbleLens API. No auth required -- the extension generates an anonymous browser UUID on first install.

### Acceptance Criteria

```gherkin
Feature: YouTube Feed Capture

  Scenario: Extension captures homepage feed
    Given I am on youtube.com homepage
    And the page has loaded with video recommendations
    When I click "Capture Feed" in the extension popup
    Then the extension extracts video ID, title, channel name, thumbnail URL, and position for each visible video
    And displays the count of captured videos in the popup

  Scenario: Captured data is sent to backend
    Given a successful feed capture with 30 videos
    When the capture completes
    Then structured JSON is sent to POST /api/feeds within 3 seconds
    And the request includes the anonymous browser UUID
    And the response confirms successful storage

  Scenario: Anonymous browser identity
    Given I install the extension for the first time
    Then the extension generates a UUID v4 and stores it in chrome.storage.local
    And all subsequent captures include this UUID
    And the UUID persists across browser sessions

  Scenario: Extension handles DOM changes
    Given YouTube has updated its DOM structure
    When the primary selector (ytd-rich-item-renderer) fails
    Then the extension falls back to alternative selectors
    And logs a warning to help developers update selectors

  Scenario: Offline capture and sync
    Given the user is offline or the API is unreachable
    When I click "Capture Feed"
    Then the capture is stored locally in chrome.storage
    And when connectivity is restored, pending captures sync automatically
```

### Task Breakdown
- T2.1: Set up Manifest V3 extension project structure (manifest.json, service worker, content script, popup)
- T2.2: Implement content script DOM parser for `ytd-rich-item-renderer` with fallback selectors
- T2.3: Build popup UI with "Capture Feed" button, status display, and capture count
- T2.4: Implement message passing between content script, popup, and service worker
- T2.5: Implement anonymous browser UUID generation and persistence (chrome.storage.local)
- T2.6: Add offline capture storage using chrome.storage API
- T2.7: Implement sync mechanism with retry logic for pending captures
- T2.8: Package extension for Chrome Web Store submission

---

## Epic 3: Feed Ingestion API & Storage

### Description
Build the API layer that receives feed captures from the Chrome extension, validates them, normalizes them into the database, and provides rate limiting. No authentication -- uses anonymous browser IDs from the extension.

### Acceptance Criteria

```gherkin
Feature: Feed Ingestion API

  Scenario: Successful feed ingestion
    Given I send a valid feed capture JSON to POST /api/feeds
    And the request includes an anonymous browser UUID
    When the API processes the request
    Then a browser record is created (or found) for the UUID
    And a feed_snapshot record is created with timestamp and feed_type
    And each video in the feed creates a feed_items record with video_id, position, and context
    And the response returns 201 with the snapshot ID

  Scenario: Payload validation
    Given I send a malformed feed capture (missing video_id)
    When the API processes the request
    Then it returns 400 with a descriptive error message
    And no records are created in the database

  Scenario: Rate limiting
    Given I have already submitted 10 feed captures from the same IP in the past hour
    When I submit another capture
    Then the API returns 429 Too Many Requests
    And includes a Retry-After header

  Scenario: Duplicate video handling
    Given a feed capture contains a video_id already in the videos table
    When the feed is ingested
    Then the feed_items record references the existing video
    And no duplicate video record is created

  Scenario: Feed retrieval
    Given I have captured 5 feeds with browser UUID "abc-123"
    When I call GET /api/feeds?browserId=abc-123
    Then I receive my feed snapshots ordered by most recent
    And each snapshot includes a video count
```

### Task Breakdown
- T3.1: Build `POST /api/feeds` route handler (no auth, accepts browser UUID)
- T3.2: Implement request payload validation (Zod schema)
- T3.3: Implement browser record upsert + feed snapshot creation + feed item normalization (Prisma transaction)
- T3.4: Set up Upstash Redis rate limiting middleware (10 captures/IP/hour)
- T3.5: Build `GET /api/feeds` endpoint for listing feed snapshots by browser ID
- T3.6: Build `GET /api/feeds/[id]` endpoint for retrieving a specific feed with items
- T3.7: Add error handling and logging for ingestion failures
- T3.8: Write integration tests for all API endpoints

## Epic 4: Lightweight Demographic Survey

### Description
A 3-field mini-survey embedded in the Chrome extension popup, triggered after the user's first successful feed capture. No login, no accounts -- responses are submitted with the same anonymous browser UUID used for feed captures. This is the critical data collection step that tags feeds with demographics, enabling the persona simulation in Phase 2.

### Acceptance Criteria

```gherkin
Feature: Post-Capture Demographic Survey

  Scenario: Survey appears after first capture
    Given I have just completed my first successful feed capture
    When the capture success screen shows in the extension popup
    Then below the success message I see a survey prompt:
      "Help us understand filter bubbles — 3 quick optional questions"
    And the survey displays 3 fields inline

  Scenario: Survey fields
    Given the survey is displayed
    Then I see the following fields:
      | Field | Type | Options |
      | Political leaning | 5-point scale | Strong Left, Left, Center, Right, Strong Right, Prefer not to say |
      | Age range | Radio | 18-24, 25-34, 35-44, 45-54, 55+, Prefer not to say |
      | Gender / Orientation | Radio | Straight Male, Straight Female, Gay/Lesbian, Bisexual, Non-binary/Other, Prefer not to say |

  Scenario: Submit survey
    Given I have selected values for one or more fields
    When I click "Submit"
    Then responses are sent to POST /api/profile with my anonymous browser UUID
    And the survey is replaced with a "Thank you" message
    And chrome.storage records that the survey is complete

  Scenario: Skip survey
    Given the survey is displayed
    When I click "Skip"
    Then the survey disappears
    And chrome.storage records that the survey was skipped
    And the survey does not appear again on future captures

  Scenario: Survey only shows once
    Given I have already completed or skipped the survey
    When I capture another feed
    Then the survey does not appear
    And instead I see a small "Update my profile" link

  Scenario: Update profile later
    Given I have previously completed or skipped the survey
    When I click "Update my profile" in the extension popup
    Then the survey form reappears pre-filled with my previous answers (if any)
    And I can update and resubmit

  Scenario: Profile API storage
    Given I submit the survey with browserId "abc-123"
    When the API processes the request
    Then a demographic_profiles record is created (or updated) linked to browser "abc-123"
    And the response returns 200 OK
```

### Task Breakdown
- T4.1: Build inline survey UI component for extension popup (3 fields + submit/skip buttons)
- T4.2: Implement survey trigger logic (show after first capture, remember completion/skip)
- T4.3: Build `POST /api/profile` route handler (accepts browser UUID + 3 survey fields)
- T4.4: Implement Zod validation schema for profile payload
- T4.5: Implement profile upsert (create or update) linked to browser record
- T4.6: Build "Update my profile" re-display flow in extension popup
- T4.7: Write integration tests for profile API endpoints
- T4.8: Write component tests for survey UI (display, submit, skip, pre-fill)

---

## Non-Functional Requirements

### Performance
- Feed capture (extension) completes in <3 seconds
- API response time <500ms for feed ingestion
- API response time <200ms for feed retrieval

### Security
- Rate limiting on all mutation endpoints (IP-based for PoC)
- Input validation on all API routes (Zod schemas)
- CORS configured for extension and web app domains only
- No PII collected or stored

### Scalability
- Neon PostgreSQL connection pooling for serverless functions
- Redis caching for frequently accessed data
- QStash for async background processing

---

## Implementation Status

| Epic | Status | Last Updated |
|------|--------|-------------|
| Epic 1: Project Scaffolding | Not Started | 2026-03-26 |
| Epic 2: Chrome Extension | Not Started | 2026-03-26 |
| Epic 3: Feed Ingestion API | Not Started | 2026-03-26 |
| Epic 4: Lightweight Demographic Survey | Not Started | 2026-03-26 |
