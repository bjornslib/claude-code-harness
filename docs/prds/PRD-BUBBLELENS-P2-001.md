---
title: "BubbleLens Phase 2 - Walk in Their Shoes MVP"
description: "Video classification, persona simulation engine, and dashboard for the BubbleLens Walk in Their Shoes launch feature"
version: "1.0.0"
last-updated: 2026-03-26
status: draft
type: prd
grade: authoritative
prd_id: PRD-BUBBLELENS-P2-001
---

# PRD-BUBBLELENS-P2-001: BubbleLens Phase 2 - Walk in Their Shoes MVP

## Overview

Phase 2 transforms the raw feed data collected in Phase 1 into the user-facing "Walk in Their Shoes" experience. It adds three capabilities: (1) video metadata enrichment via YouTube Data API, (2) AI-powered content classification along political, topic, and sentiment axes, and (3) the persona simulation engine that aggregates feeds by demographic profile to let users see what someone with different attributes would see on YouTube.

This is the launch phase. At its completion, BubbleLens has a usable product: users can capture their feed, see it analyzed, select a persona (e.g., "democrat, gay, 25-34, urban"), and view a simulated feed with side-by-side comparison.

**Parent PRD**: PRD-BUBBLELENS-001
**Depends On**: PRD-BUBBLELENS-P1-001 (requires feed data, auth, and infrastructure)
**Blocks**: Phase 3 (Bubble Score, comparisons, digests)

## Goals

### Goal 1: Classify Content Accurately
Every captured video is classified along political leaning, topic, and sentiment axes with >75% agreement with human annotators.

### Goal 2: Enable "Walk in Their Shoes"
Users can select any combination of demographic attributes and see a simulated YouTube feed based on aggregated data from real users matching that profile. This is the moment users understand their filter bubble.

### Goal 3: Visualize the Bubble
Users see their own feed analyzed with topic distribution charts, political leaning spectrum, and classification overlays -- making the invisible bubble visible.

---

## Epic 5: Video Metadata Enrichment Pipeline

### Description
Build a background job pipeline that takes video IDs from captured feeds and enriches them with metadata from the YouTube Data API v3 (title, description, tags, channel info, view/like counts, published date, duration).

### Acceptance Criteria

```gherkin
Feature: Video Metadata Enrichment

  Scenario: New videos are enriched automatically
    Given a feed capture contains 30 video IDs
    And 10 of those videos are not yet in the videos table
    When the enrichment job runs
    Then it calls YouTube Data API for the 10 new videos only
    And stores title, description, tags, category_id, channel_id, channel_name, view_count, like_count, published_at, and duration_seconds

  Scenario: API quota management
    Given the daily YouTube API quota is 10,000 units
    And a videos.list call costs 1 unit per video (batched in groups of 50)
    When the enrichment job runs
    Then it tracks cumulative quota usage for the day
    And stops processing if remaining quota drops below 500 units
    And logs a warning for monitoring

  Scenario: Enrichment deduplication
    Given a video_id already exists in the videos table with enriched_at set
    When the enrichment job encounters this video_id
    Then it skips the video
    And does not make an API call for it

  Scenario: Scheduled execution
    Given the enrichment job is configured as a QStash cron
    When the scheduled time arrives
    Then the job processes all un-enriched videos in batches of 50
    And completes within the API quota limits

  Scenario: API error handling
    Given the YouTube API returns a 403 (quota exceeded) or 500 error
    When the enrichment job encounters the error
    Then it stops the current batch
    And retries with exponential backoff (max 3 retries)
    And logs the error for monitoring
```

### Task Breakdown
- T5.1: Create YouTube Data API v3 client with API key configuration
- T5.2: Implement batch video metadata fetcher (videos.list endpoint, 50 per batch)
- T5.3: Build enrichment job that queries un-enriched video IDs and processes in batches
- T5.4: Implement API quota tracking (daily counter in Redis)
- T5.5: Configure QStash cron job to trigger enrichment every 15 minutes
- T5.6: Add error handling with exponential backoff and logging
- T5.7: Build admin endpoint to view enrichment job status and quota usage
- T5.8: Write tests for enrichment pipeline with mocked YouTube API responses

---

## Epic 6: Content Classification Pipeline

### Description
Classify enriched videos along political leaning (Left to Right), topic category, and sentiment using LLM-based classification. This enables the persona simulation and feed analysis features.

### Acceptance Criteria

```gherkin
Feature: Content Classification

  Scenario: Political leaning classification
    Given a video with title, description, and tags
    When the classification pipeline processes it
    Then it assigns one of: Left, Center-Left, Center, Center-Right, Right
    And stores the result in the videos.political_leaning column

  Scenario: Topic classification
    Given a video with title, description, and tags
    When the classification pipeline processes it
    Then it assigns 1-3 topic tags from a predefined taxonomy
    And stores the tags in the videos.topics column
    And topics are more granular than YouTube's 15 categories (minimum 40 categories)

  Scenario: Sentiment classification
    Given a video with title and description
    When the classification pipeline processes it
    Then it assigns a sentiment score: -1.0 (very negative) to 1.0 (very positive)
    And stores the score in the videos.sentiment column

  Scenario: Classification uses multiple signals
    Given a video with title "Why Democrats Are Wrong About Everything"
    And description containing partisan political arguments
    And channel historically classified as Right-leaning
    When the classification pipeline processes it
    Then it considers title, description, tags, and channel history
    And assigns Right or Center-Right with high confidence

  Scenario: Classification accuracy validation
    Given a test set of 200 manually labeled videos
    When the classifier runs on the test set
    Then political leaning classification agrees with human labels >75% of the time
    And topic classification agrees >80% of the time

  Scenario: Batch classification processing
    Given 100 newly enriched videos exist without classification
    When the classification job runs
    Then it processes all 100 videos
    And stores classification results
    And sets classified_at timestamp for each video
```

### Task Breakdown
- T6.1: Design classification taxonomy (political leaning scale, 40+ topic categories, sentiment scale)
- T6.2: Build LLM classification prompt for political leaning, topics, and sentiment
- T6.3: Implement classification pipeline that processes enriched, unclassified videos
- T6.4: Create channel-level classification cache (aggregate of video classifications per channel)
- T6.5: Build classification background job (QStash cron, processes in batches of 20)
- T6.6: Create 200-video test set with human annotations for accuracy validation
- T6.7: Implement accuracy measurement script that compares classifier output to test set
- T6.8: Add classification confidence scores to enable future community correction

---

## Epic 7: Persona Engine - "Walk in Their Shoes" Simulation

### Description
The core differentiating feature. Users select demographic attributes (political leaning, sexual orientation, gender, ethnicity, age, geography) to create a persona, and the system shows them a simulated YouTube feed based on aggregated data from real users matching that profile.

### Acceptance Criteria

```gherkin
Feature: Persona Selection

  Scenario: User selects persona attributes
    Given I am on the "Walk in Their Shoes" page
    When I see the persona selector
    Then I can choose values for:
      | Attribute | Input Type | Options |
      | Political leaning | Slider/radio | Strong Left, Left, Center, Right, Strong Right |
      | Sexual orientation | Radio | Straight, Gay, Lesbian, Bisexual, Any |
      | Gender | Radio | Male, Female, Non-binary, Any |
      | Age range | Radio | 18-24, 25-34, 35-44, 45-54, 55+, Any |
      | Country/Region | Dropdown | Major countries, Any |
      | Ethnicity | Multi-select | Common categories, Any |
    And "Any" is the default for all attributes

  Scenario: Quick persona presets
    Given I am on the persona selector
    Then I see preset buttons for common comparisons:
      | Preset | Attributes |
      | "Conservative American" | Right, Straight, Male, 45-54, USA |
      | "Progressive European" | Left, Any, Any, 25-34, Europe |
      | "Young Urban LGBTQ+" | Left, Gay/Lesbian/Bisexual, Any, 18-24, Any |
    And clicking a preset fills in the attributes

Feature: Feed Simulation

  Scenario: Simulated feed generation
    Given I have selected persona attributes (Democrat + Gay + 25-34)
    And at least 10 real users match those attributes (with wildcards)
    When I click "See Their Feed"
    Then the system aggregates feed data from matching users
    And displays 20-40 videos ranked by frequency of appearance across matching feeds
    And each video shows: title, channel, thumbnail, political leaning badge, topic tags

  Scenario: Insufficient data
    Given I have selected persona attributes
    And fewer than 10 real users match those attributes
    When I click "See Their Feed"
    Then I see a "Not enough data yet" message
    And an explanation that more users with this profile are needed
    And an invitation to share BubbleLens to help build the dataset

  Scenario: Simulation performance
    Given valid persona attributes with sufficient data
    When I click "See Their Feed"
    Then the simulated feed loads within 3 seconds
    And the UI shows a loading skeleton while processing

Feature: Side-by-Side Comparison

  Scenario: Compare my feed with persona feed
    Given I have captured at least one feed
    And I have generated a simulated persona feed
    When I click "Compare Side by Side"
    Then I see my feed on the left and the persona feed on the right
    And videos appearing in both feeds are highlighted as "overlap"
    And the overlap percentage is displayed (e.g., "12% content overlap")

  Scenario: Comparison highlights divergence
    Given a side-by-side comparison is displayed
    Then videos unique to my feed show a "Only in your feed" badge
    And videos unique to the persona feed show a "Only in their feed" badge
    And topic distribution differences are shown below the feeds
```

### Task Breakdown
- T7.1: Build persona selector component with attribute controls and "Any" defaults
- T7.2: Create preset persona definitions and quick-select buttons
- T7.3: Implement persona matching query (find users whose demographic_profiles match selected attributes, with wildcard handling for "Any")
- T7.4: Build feed aggregation algorithm (rank videos by frequency across matching users' feeds, weighted by recency)
- T7.5: Create `GET /api/persona/simulate` endpoint that accepts persona attributes and returns simulated feed
- T7.6: Implement comparison engine that computes overlap and divergence between two feeds
- T7.7: Build simulated feed display component with classification overlays
- T7.8: Build side-by-side comparison view with overlap highlighting
- T7.9: Add caching layer (Redis) for persona simulation results (cache by attribute hash, TTL 1 hour)
- T7.10: Handle insufficient data case with messaging and sharing prompt

---

## Epic 8: Dashboard & Visualization

### Description
Build the user-facing dashboard that displays the user's captured feed with analysis overlays, topic/political distributions, and the "Walk in Their Shoes" feature prominently.

### Acceptance Criteria

```gherkin
Feature: Feed Analysis Dashboard

  Scenario: Dashboard displays latest feed
    Given I have captured at least one feed
    When I visit the dashboard
    Then I see my most recent feed displayed as a grid of video cards
    And each card shows: thumbnail, title, channel name, political leaning badge (color-coded), and topic tags

  Scenario: Topic distribution chart
    Given my latest feed has been classified
    When I view the topic distribution section
    Then I see a radar or pie chart showing the percentage breakdown by topic category
    And hovering over a segment shows the exact percentage and video count

  Scenario: Political leaning spectrum
    Given my latest feed has been classified
    When I view the political leaning section
    Then I see a horizontal bar chart showing Left to Right distribution
    And the chart clearly shows where the majority of my content falls
    And the colors match: Left (blue), Center (gray), Right (red) with gradients

  Scenario: Walk in Their Shoes prominent placement
    Given I am on the dashboard
    Then the "Walk in Their Shoes" panel is visible above the fold
    And it includes a brief explanation: "See what YouTube recommends to someone with different life experiences"
    And clicking it navigates to the persona selector

  Scenario: Empty state
    Given I have not captured any feeds yet
    When I visit the dashboard
    Then I see an onboarding prompt to install the Chrome extension
    And a "How it works" explanation with 3 steps
    And a direct link to the Chrome Web Store listing

  Scenario: Responsive layout
    Given I am viewing the dashboard
    When I resize the browser to tablet width (768px)
    Then the layout adjusts to a single-column view
    And all charts remain readable and interactive
    And the "Walk in Their Shoes" panel remains accessible

  Scenario: Performance
    Given a dashboard with 30 classified videos and charts
    When the page loads
    Then all content and visualizations are interactive within 2 seconds
    And chart animations are smooth (60fps)
```

### Task Breakdown
- T8.1: Build dashboard layout with responsive grid (desktop: 3-column, tablet: 1-column)
- T8.2: Create video card component with thumbnail, metadata, and classification overlays
- T8.3: Build topic distribution chart using Recharts (radar or pie chart with hover details)
- T8.4: Build political leaning spectrum chart using Recharts (horizontal stacked bar)
- T8.5: Create "Walk in Their Shoes" prominent CTA panel with explanation text
- T8.6: Build empty state component with extension install prompt and "How it works"
- T8.7: Implement dashboard data fetching with SWR/React Query (latest feed + classification data)
- T8.8: Build feed history selector (dropdown to switch between past captures)
- T8.9: Optimize performance: lazy load images, skeleton loading states, code splitting
- T8.10: Write component tests for all dashboard sections

---

## Non-Functional Requirements

### Performance
- Simulated feed generation: <3 seconds
- Dashboard initial load: <2 seconds
- Chart interactions: 60fps
- API response for persona simulation: <2 seconds (cache hit), <5 seconds (cache miss)

### Accuracy
- Political leaning classification: >75% agreement with human annotators
- Topic classification: >80% agreement with human annotators
- Persona simulation relevance: simulated feed content divergence >30% from average user's feed when persona attributes differ significantly

### Scalability
- Classification pipeline handles 10,000 videos/day
- Persona simulation supports 100 concurrent requests
- Redis caching reduces repeated simulation queries by 80%

### Privacy
- Persona simulation never reveals individual user data -- only aggregated results
- Minimum 10 matching users required before simulation results are shown
- No way to reverse-engineer individual feeds from aggregated simulation

---

## Implementation Status

| Epic | Status | Last Updated |
|------|--------|-------------|
| Epic 5: Video Metadata Enrichment | Not Started | 2026-03-26 |
| Epic 6: Content Classification | Not Started | 2026-03-26 |
| Epic 7: Persona Engine | Not Started | 2026-03-26 |
| Epic 8: Dashboard & Visualization | Not Started | 2026-03-26 |
