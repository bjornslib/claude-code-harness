# PRD Template (Business-Focused)

> **Purpose**: This template captures WHAT to build and WHY. It is the business
> artifact owned by System 3 / the operator. Technical implementation details
> belong in the Solution Design (SD) document — not here.
>
> **Who reads this**: System 3 (strategic validation), operators (business sign-off)
> **Who does NOT read this**: Task Master, orchestrators, workers (they read the SD)
>
> **Naming**: `PRD-{CATEGORY}-{DESCRIPTOR}` (e.g., PRD-AUTH-001, PRD-DASH-002)
> **Location**: `.taskmaster/docs/PRD-{ID}.md`

---

```yaml
# ============================================================
# PRD FRONTMATTER (REQUIRED)
# ============================================================
prd_id: PRD-{CATEGORY}-{DESCRIPTOR}
title: "{Feature Name}"
product: "{Product Name}"
version: "0.1"
status: draft
created: "{YYYY-MM-DD}"
author: "{Author/Team}"
```

# PRD-{CATEGORY}-{DESCRIPTOR}: {Feature Name}

**Product:** {Product Name}
**Version:** 0.1 (Initial Draft)
**Date:** {Current Date}
**Author:** {Author/Team}
**Status:** Draft

---

## 1. Problem Statement

[Describe the core problem. Be concrete about user pain points. Why does this
need to exist? What happens if we don't build it?]

## 2. Goals & Success Metrics

[What does success look like? Quantifiable outcomes where possible.]

| Goal | Success Metric | Target |
|------|---------------|--------|
| {Goal 1} | {How we measure it} | {Target value} |
| {Goal 2} | {How we measure it} | {Target value} |

## 3. Target Users

[Define personas, their workflows, and what they're trying to achieve.]

| Persona | Role | Key Need |
|---------|------|----------|
| {Persona 1} | {Role description} | {What they need from this feature} |

## 4. User Stories

[Describe the user experience. What can users do after this ships?]

### US-1: {Story Title}
**As a** {persona}, **I want** {capability}, **so that** {value/benefit}.
**Priority**: P0/P1/P2

### US-2: {Story Title}
**As a** {persona}, **I want** {capability}, **so that** {value/benefit}.
**Priority**: P0/P1/P2

## 5. Functional Requirements

[WHAT the system must do. No implementation details — just capabilities.]

| ID | Requirement | Priority | User Story |
|----|-------------|----------|------------|
| FR-001 | {The system shall...} | P0 | US-1 |
| FR-002 | {The system shall...} | P1 | US-2 |

## 6. Non-Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-001 | {Performance: ...} | P1 |
| NFR-002 | {Security: ...} | P0 |

## 7. Architectural Decisions (High-Level Only)

> **Boundary rule**: This section records WHICH options were chosen — not HOW
> they are implemented. No schemas, no API specs, no sequence diagrams.
> Those belong in the Solution Design document.

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | {e.g., PostgreSQL} | {Why this choice} |
| Framework | {e.g., FastAPI + React} | {Why this choice} |
| Hosting | {e.g., Railway} | {Why this choice} |
| Auth approach | {e.g., JWT with refresh tokens} | {Why this choice} |

## 8. Epics (High-Level Breakdown)

[Break the work into business-meaningful chunks. Each epic will get its own
Solution Design document with full technical detail.]

### Epic 1: {Epic Name}
{One-paragraph description of what this epic delivers to the user.}

### Epic 2: {Epic Name}
{One-paragraph description of what this epic delivers to the user.}

### Epic 3: {Epic Name}
{One-paragraph description of what this epic delivers to the user.}

## 9. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| {Risk description} | High/Med/Low | High/Med/Low | {How to address} |

## 10. Non-Goals

[Explicitly state what this PRD does NOT cover. Prevents scope creep.]

- {Non-goal 1}
- {Non-goal 2}

## 11. Dependencies

| Dependency | Status | Impact |
|------------|--------|--------|
| {External system, library, or prior work} | {Status} | {What happens if unavailable} |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | {date} | {author} | Initial draft |
