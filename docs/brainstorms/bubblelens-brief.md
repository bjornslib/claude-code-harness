---
title: "Brainstorm Brief: BubbleLens - Filter Bubble Analyzer"
description: "Brainstorm brief for BubbleLens initiative - Filter bubble analyzer for YouTube"
version: "1.0.0"
last-updated: 2026-03-26
status: active
type: research
date: 2026-03-26
participants: Bjorn Schliebitz (Human) + Claude (AI)
initiative_id: INIT-BUBBLELENS-001
---

# Brainstorm Brief: BubbleLens - Filter Bubble Analyzer for YouTube

**Date**: 2026-03-26
**Participants**: Bjorn Schliebitz (Faie Group) + Claude (AI)
**Initiative ID**: INIT-BUBBLELENS-001
**Inspiration**: Diary of a CEO podcast with Geoffrey Hinton -- discussion on platform-driven confirmation bias

---

## Problem Statement

YouTube, Meta, TikTok, and other platforms use recommendation algorithms that optimize for engagement, not perspective diversity. The result is filter bubbles -- users are served content that reinforces their existing beliefs, demographics, and interests while systematically hiding opposing viewpoints.

There is no consumer-facing tool that lets a user see what their filter bubble looks like, compare their feed to someone with different demographics or beliefs, or understand why they see what they see.

This is experienced daily by billions of users, with measurable societal impacts on political polarization, cultural echo chambers, and information asymmetry.

---

## Target Users & Impact

| User Type | Pain Point | Expected Benefit |
|-----------|-----------|-----------------|
| Curious individuals | Unaware of their own filter bubble; no way to see what "the other side" sees | Self-awareness of algorithmic bias; empathy through perspective-taking |
| Journalists & researchers | No scalable tool to audit YouTube recommendations across demographics | Quantifiable data on algorithmic bias; publishable research insights |
| Educators & digital literacy advocates | Difficult to demonstrate filter bubbles to students | Interactive, tangible demonstration of how algorithms shape worldview |
| Policy makers & regulators | Lack of evidence for algorithmic transparency legislation | Data-driven evidence of recommendation bias patterns |

---

## Proposed Approach

### Selected: Chrome Extension + Next.js Dashboard with "Walk in Their Shoes" Persona Simulation

A browser extension captures users' YouTube homepage recommendations. A Next.js web application analyzes feeds, classifies content along political/topic/diversity axes, and enables users to simulate what someone with entirely different attributes (political leaning, sexual orientation, ethnicity, geography, age) would see on their YouTube homepage.

**Why this approach**:
- Chrome extension is the only reliable way to capture personalized YouTube recommendations (no public API for recommendations)
- Next.js provides SSR for marketing/SEO pages + React for interactive dashboard -- single deployable unit
- Persona simulation ("Walk in Their Shoes") is the differentiating feature that no competitor offers
- Starting YouTube-only keeps scope manageable; architecture designed for multi-platform expansion

### Rejected Alternatives

| Alternative | Why Rejected |
|------------|-------------|
| Mobile app (React Native) | Higher barrier to entry; Chrome extension captures data where users already consume content; mobile can be Phase 3+ |
| YouTube API-only approach | YouTube Data API does not expose personalized recommendations -- only public video metadata. Extension is required for feed capture |
| Centralized scraping service | Legal risk (ToS violation); cannot capture personalized feeds without user's browser context |
| Browser-only (no backend) | Cannot aggregate across users for demographic comparisons; no persistence for trend analysis |

---

## Open Questions Resolved

| Question | Resolution |
|----------|-----------|
| How to capture YouTube recommendations without API? | Chrome extension parses DOM elements (`ytd-rich-item-renderer` for homepage, `ytd-compact-video-renderer` for sidebar) |
| Is DOM scraping via extension legal? | Grey area but defensible -- extension reads data already rendered for the authenticated user (analogous to screen reader). hiQ v. LinkedIn precedent supports this |
| How to classify video political leaning? | Multi-signal approach: AI classification of title/description/transcript + channel-level historical classification + community correction |
| What's the MVP feature to launch with? | "Walk in Their Shoes" -- users select a persona (e.g., democrat + gay + urban) and see a simulated feed based on aggregated data from users matching that profile |
| How to get initial data without users? | Seed with research accounts representing diverse demographic profiles; partner with digital literacy organizations for early adopters |

---

## Success Criteria (Proto-Acceptance)

These will become formal acceptance criteria in the PRD:

1. **Feed capture works reliably** -- Chrome extension captures 95%+ of visible YouTube homepage video recommendations within 3 seconds
2. **Persona simulation is meaningful** -- "Walk in Their Shoes" shows demonstrably different feeds for personas with different political/demographic attributes (>30% content divergence)
3. **Data privacy is respected** -- All demographic data is opt-in, anonymized, and deletable; no PII stored alongside feed data
4. **Users complete onboarding** -- 60%+ of users who install the extension complete the demographic survey
5. **Classification accuracy** -- AI political leaning classification achieves >75% agreement with human annotators on a test set

---

## Constraints Discovered

- **YouTube DOM instability** -- YouTube frequently changes its DOM structure; extension must be resilient to changes and easy to update
- **Cold start problem** -- Persona simulation requires aggregated data from multiple users per demographic group; minimum ~50 users per persona combination for meaningful simulation
- **Google OAuth verification** -- Production deployment with >100 users requires Google OAuth app verification (4-8 week timeline)
- **GDPR/Privacy** -- EU users require full GDPR compliance; Australian Privacy Act for AU users
- **API rate limits** -- YouTube Data API v3 has quota limits (10,000 units/day default); video enrichment must be batched and cached

---

## Next Step

Create master PRD at `docs/prds/PRD-BUBBLELENS-001.md`, then decompose into phase-specific PRDs targeting MVP launch with the "Walk in Their Shoes" feature.
