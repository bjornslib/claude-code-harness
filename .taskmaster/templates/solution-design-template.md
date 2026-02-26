# Solution Design (SD) Template

> **Purpose**: This is the primary automation input document. It contains enough
> business context for Task Master to generate meaningful tasks, AND enough
> technical detail for orchestrators to brief workers. One SD per epic.
>
> **Who reads this**: Task Master (parse-prd), orchestrators, workers, acceptance-test-writer
> **Who writes this**: solution-design-architect agent (from PRD + research)
> **Who validates this**: System 3 / operator (before passing to Task Master)
>
> **Naming**: `SD-{CATEGORY}-{NUMBER}-{epic-slug}.md`
> **Location**: `.taskmaster/docs/SD-{CATEGORY}-{NUMBER}-{epic-slug}.md`
> **Source PRD**: Always links back to the parent PRD

---

```yaml
# ============================================================
# SD FRONTMATTER (REQUIRED)
# ============================================================
sd_id: SD-{CATEGORY}-{NUMBER}-{epic-slug}
prd_ref: PRD-{CATEGORY}-{DESCRIPTOR}
epic: "{Epic Name from PRD}"
title: "{Solution Design Title}"
version: "0.1"
status: draft
created: "{YYYY-MM-DD}"
author: "{Agent or Team}"
```

# SD-{CATEGORY}-{NUMBER}-{epic-slug}: {Solution Design Title}

**Epic:** {Epic Name}
**Source PRD:** PRD-{CATEGORY}-{DESCRIPTOR}
**Date:** {Current Date}
**Author:** {solution-design-architect / Team}
**Status:** Draft

---

## 1. Business Context (Summary from PRD)

> **Why this section exists**: Task Master needs business context to generate
> tasks with meaningful descriptions. This is a brief summary (3-5 sentences)
> of the relevant goals, user impact, and success metrics from the PRD.
> Do NOT duplicate the full PRD — just enough for task descriptions to be meaningful.

**Goal**: {What this epic achieves for the user — one sentence}

**User Impact**: {Who benefits and how — one sentence}

**Success Metrics**: {How we know it worked — from PRD Section 2}
- {Metric 1}
- {Metric 2}

**Constraints**: {Non-functional requirements that affect design — from PRD Section 6}
- {Constraint 1}
- {Constraint 2}

---

## 2. Technical Architecture

### 2.1 System Components

[Major architectural pieces and their responsibilities for this epic.]

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Component A │────►│  Component B  │────►│  Component C │
│  {role}      │     │  {role}       │     │  {role}      │
└─────────────┘     └──────────────┘     └─────────────┘
```

### 2.2 Data Models

[Core data structures, schemas, database design for this epic.]

```sql
-- Example: New tables or modifications
CREATE TABLE {table_name} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    {field_name} {type} NOT NULL,
    {field_name} {type},
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 2.3 API Contracts

[Endpoints, request/response shapes, error handling.]

| Method | Endpoint | Request Body | Response | Auth |
|--------|----------|-------------|----------|------|
| POST | `/api/v1/{resource}` | `{schema}` | `{schema}` | JWT |
| GET | `/api/v1/{resource}/{id}` | — | `{schema}` | JWT |

### 2.4 Component Design (Frontend)

[If applicable: component hierarchy, state management, key interactions.]

```
PageComponent
├── HeaderSection
├── MainContent
│   ├── FeatureWidget (state: local)
│   └── DataDisplay (state: server/query)
└── ActionBar
```

---

## 3. Implementation Approach

### 3.1 Technology Choices

[Specific libraries, patterns, and approaches — the HOW.]

| Choice | Technology | Rationale |
|--------|-----------|-----------|
| ORM | {e.g., SQLAlchemy} | {Why} |
| State management | {e.g., React Query} | {Why} |
| Testing | {e.g., pytest + Playwright} | {Why} |

### 3.2 Key Design Decisions

[Technical decisions specific to this epic. Use ADR-lite format.]

**Decision 1: {Decision Title}**
- **Context**: {What drove this decision}
- **Options considered**: {Option A, Option B, Option C}
- **Chosen**: {Option B}
- **Rationale**: {Why this option}
- **Trade-offs**: {What we're giving up}

### 3.3 Integration Points

[How this epic's work connects to existing systems.]

| Integration | Type | Direction | Notes |
|-------------|------|-----------|-------|
| {Existing service} | REST API | Outbound | {Details} |
| {Database} | Direct | Read/Write | {Details} |

---

## 4. Functional Decomposition

> **Why this section exists**: Task Master uses this section to generate
> dependency-aware tasks. Structure capabilities → features → tasks with
> explicit dependencies for topological ordering.

### Capability: {Capability Name}

{Brief description of what this capability domain covers}

#### Feature: {Feature Name}
- **Description**: {One sentence}
- **Inputs**: {What it needs}
- **Outputs**: {What it produces}
- **Behavior**: {Key logic}
- **Depends on**: {Other features or capabilities — EXPLICIT}

#### Feature: {Feature Name}
- **Description**: {One sentence}
- **Inputs**: {What it needs}
- **Outputs**: {What it produces}
- **Behavior**: {Key logic}
- **Depends on**: {Other features or capabilities — EXPLICIT}

### Capability: {Capability Name}

{Brief description}

#### Feature: {Feature Name}
...

---

## 5. Dependency Graph

> **Why this section exists**: Task Master parses this to create topological
> task ordering. Be explicit about what depends on what.

### Foundation Layer (Build First)
No dependencies — these are built first.

- **{Module/Feature}**: {What it provides to downstream work}
- **{Module/Feature}**: {What it provides to downstream work}

### Layer 1: {Layer Name}
- **{Module/Feature}**: Depends on [{foundation items}]
- **{Module/Feature}**: Depends on [{foundation items}]

### Layer 2: {Layer Name}
- **{Module/Feature}**: Depends on [{Layer 1 items}]

---

## 6. Acceptance Criteria (Per Feature)

> **Why this section exists**: These criteria are used by:
> 1. Task Master — to populate task acceptance criteria
> 2. acceptance-test-writer — to generate Gherkin scenarios
> 3. Orchestrators — to brief workers on "definition of done"
> 4. Validators — to verify implementation

### Feature: {Feature Name}

**Given** {precondition}
**When** {action}
**Then** {expected outcome}
**And** {additional criteria}

### Feature: {Feature Name}

**Given** {precondition}
**When** {action}
**Then** {expected outcome}

---

## 7. Test Strategy

### Test Pyramid

| Level | Coverage | Tools | What It Tests |
|-------|----------|-------|---------------|
| Unit | {X}% | {pytest/vitest} | Business logic, utilities |
| Integration | {Y}% | {pytest + httpx} | API contracts, DB operations |
| E2E | {Z}% | {Playwright} | User journeys, cross-layer flows |

### Critical Test Scenarios

| Scenario | Type | Priority |
|----------|------|----------|
| {Happy path scenario} | E2E | P0 |
| {Error handling scenario} | Integration | P1 |
| {Edge case scenario} | Unit | P1 |

---

## 8. File Scope

> **Why this section exists**: Orchestrators use this to scope worker
> assignments. Workers ONLY touch files listed in their scope.

### New Files

| File Path | Purpose |
|-----------|---------|
| `src/{module}/{file}.py` | {What it does} |
| `src/{module}/{file}.tsx` | {What it does} |

### Modified Files

| File Path | Changes |
|-----------|---------|
| `src/{existing_file}.py` | {What changes and why} |

### Files NOT to Modify

| File Path | Reason |
|-----------|--------|
| `src/{sensitive_file}.py` | {Why it should not be touched} |

---

## 9. Risks & Technical Concerns

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| {Technical risk specific to this epic} | H/M/L | H/M/L | {Mitigation} |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | {date} | {author} | Initial design |
