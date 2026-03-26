---
title: "BubbleLens Phase 1 - Data Foundation & Infrastructure"
description: "Chrome extension, authentication, feed ingestion, and cloud infrastructure for the BubbleLens platform"
version: "1.0.0"
last-updated: 2026-03-26
status: draft
type: prd
grade: authoritative
prd_id: PRD-BUBBLELENS-P1-001
---

# PRD-BUBBLELENS-P1-001: BubbleLens Phase 1 - Data Foundation & Infrastructure

## Overview

Phase 1 establishes the complete data collection pipeline for BubbleLens: a Chrome extension that captures YouTube homepage recommendations, user authentication with demographic profiling, and a backend API that ingests, normalizes, and stores feed data. At the end of Phase 1, users can install the extension, create an account, fill out their demographic profile, and capture their YouTube feed -- building the dataset that powers Phase 2's "Walk in Their Shoes" feature.

**Parent PRD**: PRD-BUBBLELENS-001
**Depends On**: Nothing (greenfield)
**Blocks**: PRD-BUBBLELENS-P2-001 (Phase 2 requires feed data to exist)

## Goals

### Goal 1: Reliable Feed Capture
The Chrome extension captures 95%+ of visible YouTube homepage video recommendations accurately and sends them to the backend within 3 seconds.

### Goal 2: Frictionless Onboarding
Users can sign up, install the extension, and complete their demographic profile in under 5 minutes. All demographic fields are optional with clear privacy explanations.

### Goal 3: Scalable Data Ingestion
The backend reliably ingests, validates, and stores feed captures with rate limiting and error handling, ready to support thousands of concurrent users.

### Goal 4: Privacy-First Architecture
No PII is linked to feed data. Demographic profiles are anonymized. Users can delete all their data at any time. GDPR-compliant from day one.

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
    Given Prisma schema with all core tables defined
    When I run prisma migrate deploy
    Then all tables (users, demographic_profiles, feed_snapshots, feed_items, videos, comparisons) are created
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
- T1.3: Configure Prisma ORM with initial schema migration (all 6 core tables)
- T1.4: Set up Upstash Redis for rate limiting and session cache
- T1.5: Configure Vercel deployment with environment variables
- T1.6: Set up GitHub Actions CI pipeline (lint, type-check, test)
- T1.7: Configure Upstash QStash for background job scheduling

---

## Epic 2: Chrome Extension - Feed Capture

### Description
Build a Manifest V3 Chrome extension that injects a content script on YouTube pages, parses the homepage video grid, and sends structured feed data to the BubbleLens API.

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
    And the response confirms successful storage

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

  Scenario: Extension requires authentication
    Given I am not logged into BubbleLens
    When I open the extension popup
    Then I see a "Sign in to BubbleLens" prompt with a link to the web app
    And the "Capture Feed" button is disabled
```

### Task Breakdown
- T2.1: Set up Manifest V3 extension project structure (manifest.json, service worker, content script, popup)
- T2.2: Implement content script DOM parser for `ytd-rich-item-renderer` with fallback selectors
- T2.3: Build popup UI with "Capture Feed" button, status display, and capture count
- T2.4: Implement message passing between content script, popup, and service worker
- T2.5: Add offline capture storage using chrome.storage API
- T2.6: Implement sync mechanism with retry logic for pending captures
- T2.7: Add authentication state check (validate Clerk session token)
- T2.8: Package extension for Chrome Web Store submission

---

## Epic 3: User Authentication & Onboarding Survey

### Description
Implement Clerk-based authentication with Google OAuth and a demographic onboarding survey where all fields are optional and privacy-first.

### Acceptance Criteria

```gherkin
Feature: User Authentication

  Scenario: Email signup
    Given I am on the BubbleLens signup page
    When I enter my email and password
    Then a Clerk account is created
    And I am redirected to the onboarding survey

  Scenario: Google OAuth signup
    Given I am on the BubbleLens signup page
    When I click "Sign in with Google"
    Then I complete Google OAuth flow
    And a Clerk account is created linked to my Google account

  Scenario: Returning user login
    Given I have an existing BubbleLens account
    When I log in with my credentials
    Then I am redirected to the dashboard (not onboarding)

Feature: Demographic Onboarding Survey

  Scenario: Survey presentation
    Given I have just signed up
    When I land on the onboarding survey page
    Then I see a privacy explanation at the top
    And I see 7 demographic fields, each marked as optional
    And each field has a "Prefer not to say" option

  Scenario: Survey fields
    Given I am on the onboarding survey
    Then I see the following fields:
      | Field | Type | Options |
      | Political leaning | 5-point scale | Strong Left, Left, Center, Right, Strong Right, Prefer not to say |
      | Country/Region | Dropdown | Major countries + regions |
      | Age range | Radio | 18-24, 25-34, 35-44, 45-54, 55+, Prefer not to say |
      | Primary interests | Multi-select | Politics, Tech, Entertainment, Sports, Education, News, Science, Music, Gaming, Other |
      | Ethnicity | Multi-select, optional | Common categories + Prefer not to say |
      | Gender | Radio, optional | Male, Female, Non-binary, Other, Prefer not to say |
      | Sexual orientation | Radio, optional | Straight, Gay, Lesbian, Bisexual, Other, Prefer not to say |

  Scenario: Skip survey entirely
    Given I am on the onboarding survey
    When I click "Skip for now"
    Then I am redirected to the dashboard
    And no demographic profile is created
    And I can fill it out later from settings

  Scenario: Anonymous storage
    Given I submit the onboarding survey
    Then my responses are stored with my anonymous user UUID only
    And no PII (name, email) is stored in the demographic_profiles table

  Scenario: Profile management
    Given I have a demographic profile
    When I go to Settings > My Profile
    Then I can update any field
    And I can delete my entire profile
    And deletion is immediate and permanent
```

### Task Breakdown
- T3.1: Integrate Clerk SDK with Next.js App Router (middleware, providers, sign-in/sign-up pages)
- T3.2: Configure Google OAuth provider in Clerk dashboard
- T3.3: Build onboarding survey page with all 7 demographic fields
- T3.4: Implement survey submission API route (`POST /api/profile`)
- T3.5: Build profile management page (view, update, delete)
- T3.6: Add privacy policy page and data handling explanation
- T3.7: Implement user data deletion endpoint (`DELETE /api/profile`)
- T3.8: Add onboarding flow routing (new users -> survey, returning users -> dashboard)

---

## Epic 4: Feed Ingestion API & Storage

### Description
Build the API layer that receives feed captures from the Chrome extension, validates them, normalizes them into the database, and provides rate limiting.

### Acceptance Criteria

```gherkin
Feature: Feed Ingestion API

  Scenario: Successful feed ingestion
    Given I am authenticated
    And I send a valid feed capture JSON to POST /api/feeds
    When the API processes the request
    Then a feed_snapshot record is created with timestamp and feed_type
    And each video in the feed creates a feed_items record with video_id, position, and context
    And the response returns 201 with the snapshot ID

  Scenario: Payload validation
    Given I send a malformed feed capture (missing video_id)
    When the API processes the request
    Then it returns 400 with a descriptive error message
    And no records are created in the database

  Scenario: Rate limiting
    Given I have already submitted 10 feed captures in the past hour
    When I submit another capture
    Then the API returns 429 Too Many Requests
    And includes a Retry-After header

  Scenario: Authentication required
    Given I am not authenticated
    When I send a feed capture to POST /api/feeds
    Then the API returns 401 Unauthorized

  Scenario: Duplicate video handling
    Given a feed capture contains a video_id already in the videos table
    When the feed is ingested
    Then the feed_items record references the existing video
    And no duplicate video record is created

  Scenario: Feed retrieval
    Given I have captured 5 feeds
    When I call GET /api/feeds
    Then I receive my feed snapshots ordered by most recent
    And each snapshot includes a video count
```

### Task Breakdown
- T4.1: Build `POST /api/feeds` route handler with Clerk JWT validation
- T4.2: Implement request payload validation (Zod schema)
- T4.3: Implement feed snapshot creation and feed item normalization (Prisma transaction)
- T4.4: Set up Upstash Redis rate limiting middleware (10 captures/user/hour)
- T4.5: Build `GET /api/feeds` endpoint for listing user's feed snapshots
- T4.6: Build `GET /api/feeds/[id]` endpoint for retrieving a specific feed with items
- T4.7: Add error handling and logging for ingestion failures
- T4.8: Write integration tests for all API endpoints

---

## Non-Functional Requirements

### Performance
- Feed capture (extension) completes in <3 seconds
- API response time <500ms for feed ingestion
- API response time <200ms for feed retrieval

### Security
- All API routes require Clerk JWT authentication
- Rate limiting on all mutation endpoints
- Input validation on all API routes (Zod schemas)
- CORS configured for extension and web app domains only
- No PII in database tables beyond Clerk user ID reference

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
| Epic 3: Auth & Onboarding | Not Started | 2026-03-26 |
| Epic 4: Feed Ingestion API | Not Started | 2026-03-26 |
