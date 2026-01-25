# Product Requirements Document Template

Use this template to generate a PRD from a design image. This document is structured for extension via Claude Code.

---

```yaml
# ============================================================
# PRD FRONTMATTER (REQUIRED)
# ============================================================
# This YAML block MUST be the first content after the title.
# The prd_id is the canonical identifier used throughout the system:
#   - CLAUDE_CODE_TASK_LIST_ID environment variable
#   - acceptance-tests/PRD-XXX/ directory
#   - Task Master task grouping
#   - Hindsight memory context
#
# Format: PRD-{CATEGORY}-{DESCRIPTOR}
# Examples:
#   - PRD-AUTH-001        (numbered series)
#   - PRD-LIVE-FORM-UI    (descriptive)
#   - PRD-VOICE-AGENT-MVP (major feature)
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
**Status:** Draft for Extension

---

## 1. Executive Summary

{2-3 paragraphs covering:}
- What feature/product this document describes
- The core problem it solves
- High-level approach to the solution

### 1.1 Problem Statement

{Specific problem description including:}
- Who is affected
- What the current pain points are
- Why existing solutions fall short
- What users need

### 1.2 Solution Overview

{High-level description of the solution:}
- Key capabilities
- Core workflow
- Expected outcomes

---

## 2. Goals and Success Metrics

### 2.1 Business Goals

| Goal | Description | Target |
|------|-------------|--------|
| {Goal 1} | {Description} | {Measurable target} |
| {Goal 2} | {Description} | {Measurable target} |
| {Goal 3} | {Description} | {Measurable target} |

### 2.2 User Goals

| User Type | Primary Goal | Secondary Goal |
|-----------|--------------|----------------|
| {User 1} | {Goal} | {Goal} |
| {User 2} | {Goal} | {Goal} |
| {User 3} | {Goal} | {Goal} |

### 2.3 Success Metrics

| Metric | Current Baseline | Target | Measurement Method |
|--------|------------------|--------|-------------------|
| {Metric 1} | {Current or N/A} | {Target value} | {How measured} |
| {Metric 2} | {Current or N/A} | {Target value} | {How measured} |
| {Metric 3} | {Current or N/A} | {Target value} | {How measured} |

---

## 3. User Stories

### 3.1 Must Have (P0)

| ID | User Story | Acceptance Criteria |
|----|------------|---------------------|
| US-001 | As a {user type}, I want to {action} so that {benefit} | - {Criterion 1}<br>- {Criterion 2}<br>- {Criterion 3} |
| US-002 | As a {user type}, I want to {action} so that {benefit} | - {Criterion 1}<br>- {Criterion 2} |
| US-003 | As a {user type}, I want to {action} so that {benefit} | - {Criterion 1}<br>- {Criterion 2} |

### 3.2 Should Have (P1)

| ID | User Story | Acceptance Criteria |
|----|------------|---------------------|
| US-010 | As a {user type}, I want to {action} so that {benefit} | - {Criterion 1}<br>- {Criterion 2} |
| US-011 | As a {user type}, I want to {action} so that {benefit} | - {Criterion 1}<br>- {Criterion 2} |

### 3.3 Could Have (P2)

| ID | User Story | Acceptance Criteria |
|----|------------|---------------------|
| US-020 | As a {user type}, I want to {action} so that {benefit} | - {Criterion 1} |
| US-021 | As a {user type}, I want to {action} so that {benefit} | - {Criterion 1} |

---

## 4. Functional Requirements

### 4.1 {Feature Area 1}

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-001 | System shall {requirement} | P0 |
| FR-002 | System shall {requirement} | P0 |
| FR-003 | System shall {requirement} | P1 |

### 4.2 {Feature Area 2}

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-010 | System shall {requirement} | P0 |
| FR-011 | System shall {requirement} | P0 |
| FR-012 | System shall {requirement} | P1 |

### 4.3 {Feature Area 3}

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-020 | System shall {requirement} | P0 |
| FR-021 | System shall {requirement} | P1 |
| FR-022 | System shall {requirement} | P2 |

{Add more feature areas as needed}

---

## 5. Non-Functional Requirements

### 5.1 Performance

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-001 | {Component} shall load within {time} | < {X}s |
| NFR-002 | {Action} shall complete within {time} | < {X}ms |
| NFR-003 | {Operation} shall support {volume} | {X} per second |

### 5.2 Reliability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-010 | {Feature} shall have uptime of | 99.9% |
| NFR-011 | Data shall be backed up | Every {X} hours |
| NFR-012 | Recovery shall complete within | < {X} minutes |

### 5.3 Scalability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-020 | System shall support {volume} | {X} users/items |
| NFR-021 | System shall handle {growth} | {X}% monthly growth |

### 5.4 Security

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-030 | Data shall be encrypted at rest | {Standard, e.g., AES-256} |
| NFR-031 | Data shall be encrypted in transit | {Standard, e.g., TLS 1.3} |
| NFR-032 | Access shall require {authentication} | {Method} |
| NFR-033 | Actions shall be logged for audit | {Scope} |

### 5.5 Accessibility

| ID | Requirement | Standard |
|----|-------------|----------|
| NFR-040 | Interface shall be keyboard navigable | WCAG 2.1 AA |
| NFR-041 | Interface shall support screen readers | WCAG 2.1 AA |
| NFR-042 | Touch targets shall be minimum 44×44px | WCAG 2.1 AAA |
| NFR-043 | Colour shall not be sole information indicator | WCAG 2.1 AA |

---

## 6. Technical Architecture

### 6.1 Data Model

```
{EntityName}
├── id: {type}
├── {field}: {type}
├── {field}: {type}
├── {relationship}: {type}
├── createdAt: timestamp
└── updatedAt: timestamp

{RelatedEntity}
├── id: {type}
├── {parentId}: {type} (FK to {Parent})
├── {field}: {type}
└── {field}: {type}
```

### 6.2 API Endpoints

```
GET    /api/v1/{resource}           # List all
GET    /api/v1/{resource}/:id       # Get one
POST   /api/v1/{resource}           # Create
PUT    /api/v1/{resource}/:id       # Update
DELETE /api/v1/{resource}/:id       # Delete

POST   /api/v1/{resource}/:id/{action}  # Special action
GET    /api/v1/{resource}/:id/{sub}     # Sub-resource
```

### 6.3 Technology Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| Frontend | {Framework, e.g., Next.js 15 + React 19} | {Rationale} |
| UI Components | {Library, e.g., shadcn/ui + Tailwind} | {Rationale} |
| State Management | {Library, e.g., Zustand / TanStack Query} | {Rationale} |
| Backend | {Framework, e.g., Python FastAPI} | {Rationale} |
| Database | {Database, e.g., PostgreSQL} | {Rationale} |
| Caching | {Technology, e.g., Redis} | {Rationale} |

---

## 7. Dependencies

### 7.1 Internal Dependencies

| Dependency | Description | Owner | Risk |
|------------|-------------|-------|------|
| {Dependency 1} | {What it provides} | {Team/Person} | {Low/Medium/High} |
| {Dependency 2} | {What it provides} | {Team/Person} | {Low/Medium/High} |

### 7.2 External Dependencies

| Dependency | Description | Fallback |
|------------|-------------|----------|
| {Service/API} | {What it provides} | {Alternative if unavailable} |
| {Library} | {What it provides} | {Alternative if deprecated} |

---

## 8. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| {Risk 1} | {Low/Medium/High} | {Low/Medium/High} | {How to prevent/reduce} |
| {Risk 2} | {Low/Medium/High} | {Low/Medium/High} | {How to prevent/reduce} |
| {Risk 3} | {Low/Medium/High} | {Low/Medium/High} | {How to prevent/reduce} |

---

## 9. Open Questions

| ID | Question | Owner | Due Date | Resolution |
|----|----------|-------|----------|------------|
| OQ-001 | {Question needing decision} | {Person} | {Date} | {Answer when resolved} |
| OQ-002 | {Question needing decision} | {Person} | {Date} | |
| OQ-003 | {Question needing decision} | {Person} | {Date} | |

---

## 10. Implementation Phases

### Phase 1: {Phase Name} (MVP)

- {Feature/capability 1}
- {Feature/capability 2}
- {Feature/capability 3}

**Target:** {Timeline or milestone}

### Phase 2: {Phase Name}

- {Feature/capability 1}
- {Feature/capability 2}

**Target:** {Timeline or milestone}

### Phase 3: {Phase Name}

- {Feature/capability 1}
- {Feature/capability 2}

**Target:** {Timeline or milestone}

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| {Term 1} | {Definition} |
| {Term 2} | {Definition} |
| {Term 3} | {Definition} |

---

## Appendix B: Reference Materials

- Interaction Design Specification: [{filename}]
- UI Mockups: [{filename or link}]
- Technical Architecture: [{document or link}]
- User Research: [{document or link}]

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | {Date} | {Author} | Initial draft |

---

## PRD Generation Guidelines

When generating a PRD from a design image:

### Must Include

1. **All visible features** as functional requirements
2. **Data entities** implied by the UI
3. **User actions** as user stories
4. **Visual states** as requirements (loading, error, empty)
5. **Accessibility** requirements for all interactive elements

### Derive From Design

- **Buttons/actions** → User stories + functional requirements
- **Forms/inputs** → Data model fields + validation requirements
- **Lists/tables** → API endpoints + scalability requirements
- **Status indicators** → State management requirements
- **Navigation** → Information architecture + routes

### Priority Assignment

- **P0 (Must Have):** Core functionality visible in design
- **P1 (Should Have):** Secondary features, error handling, edge cases
- **P2 (Could Have):** Enhancements, optimisations, future features

### Open Questions to Generate

- Decisions implied but not resolved in design
- Edge cases not shown
- Integration points with unclear scope
- Performance targets not specified
