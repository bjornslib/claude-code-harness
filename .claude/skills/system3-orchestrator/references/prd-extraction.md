---
title: "Prd Extraction"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# PRD-Driven Outcome Tracking Reference

Extract goals and acceptance criteria from PRDs to maintain meta-level awareness of what orchestrators are trying to achieve.

---

## Why PRD Extraction Matters

Without PRD-driven tracking:
- Orchestrators complete tasks but miss the point
- Scope creep goes undetected
- "Done" doesn't mean "achieved"
- No feedback loop for improvement

With PRD-driven tracking:
- Meta-level awareness of true objectives
- Early detection of goal drift
- Completion means actual achievement
- Continuous learning from outcomes

---

## Before Spawning: Extract and Retain Goals

### Step 1: Read the PRD

```python
prd_content = Read(f"docs/prds/{epic_name}-prd.md")
```

### Step 2: Extract Key Elements

Identify from the PRD:
- **Ultimate Goals**: What success looks like
- **Acceptance Criteria**: Specific, testable conditions
- **Scope Boundaries**: What's IN and OUT

### Step 3: Retain to Hindsight

```python
mcp__hindsight__retain(
    content=f"""
    ## Active Initiative: {initiative_name}

    ### Ultimate Goals
    - [Goal 1: What success looks like]
    - [Goal 2: What must be true when done]
    - [Goal 3: User-facing outcomes]

    ### Acceptance Criteria (from PRD)
    - [Criterion 1]
    - [Criterion 2]
    - [Criterion 3]

    ### Scope Boundaries
    - IN: [What's included]
    - OUT: [What's explicitly excluded]

    ### Orchestrator Session: {session_name}
    Started: {timestamp}
    Worktree: {worktree_path}
    """,
    context="system3-prd-tracking"
)
```

---

## During Monitoring: Compare Against Intentions

### Recall Stored Goals

```python
goals = mcp__hindsight__recall(
    query=f"What are the goals and acceptance criteria for {initiative_name}?",
    max_results=3
)
```

### Key Questions to Ask

When checking on orchestrators:
- Are they working toward the right goals?
- Are they staying within scope?
- Will completion actually satisfy acceptance criteria?

### Red Flags

| Signal | Meaning |
|--------|---------|
| Files modified outside scope | Scope creep |
| New tasks added not in PRD | Feature creep |
| Original goals not being addressed | Goal drift |
| Acceptance criteria ignored | Misaligned work |

---

## After Completion: Evaluate Outcomes

### Step 1: Reflect on Achievement

```python
outcome_reflection = mcp__hindsight__reflect(
    query=f"""
    ## Outcome Evaluation: {initiative_name}

    ### Original Goals
    [Recalled from system3-prd-tracking]

    ### What Was Actually Delivered
    [Summary of completed work]

    ### Evaluation Questions
    1. Were the stated goals actually achieved?
    2. Do the deliverables satisfy acceptance criteria?
    3. Was scope maintained or did it creep?
    4. Are there gaps between intention and execution?
    5. What lessons should inform future orchestration?

    ### Verdict
    ACHIEVED / PARTIAL / MISSED
    """,
    budget="high",
    bank_id="system3-orchestrator"
)
```

### Step 2: Store Outcome Record

```python
mcp__hindsight__retain(
    content=f"""
    ## Outcome Record: {initiative_name}

    Verdict: {verdict}
    Goals Achieved: {goals_achieved_list}
    Gaps Identified: {gaps}
    Lessons Learned: {lessons}

    Evidence:
    - Tests: {test_results}
    - Validation: {validation_summary}
    - User Feedback: {feedback if any}
    """,
    context="system3-prd-tracking"
)
```

---

## PRD Extraction Template

When reading a PRD, extract these sections:

### 1. Executive Summary / Overview
- What problem are we solving?
- Who is the user/customer?
- What's the business value?

### 2. Goals and Success Metrics
- Explicit goals stated in the PRD
- KPIs or metrics if defined
- Definition of done

### 3. Functional Requirements
- Must-have features
- Should-have features
- Nice-to-have features

### 4. Non-Functional Requirements
- Performance requirements
- Security requirements
- Scalability needs

### 5. Scope Definition
- What's explicitly IN scope
- What's explicitly OUT of scope
- Future considerations (not this iteration)

### 6. Acceptance Criteria
- Per-feature acceptance criteria
- End-to-end scenarios
- Edge cases to handle

---

## Integration with Completion Promise

PRD goals feed into the completion promise:

```bash
# 1. Extract from PRD
.claude/scripts/completion-state/cs-extract --prd "docs/prds/epic-prd.md"

# 2. Add goals from PRD
.claude/scripts/completion-state/cs-extract \
    --goal "[Goal from PRD]" \
    --criteria "[Acceptance criterion 1]" \
    --criteria "[Acceptance criterion 2]"
```

---

## Autonomous Fallback Protocol

When PRD is ambiguous but blocking progress:

1. **Log uncertainty**:
   ```python
   mcp__hindsight__retain(
       content=f"Ambiguity: [description]. Proceeding with {chosen_approach}",
       context="system3-decisions"
   )
   ```

2. **Make best judgment**: Choose most conservative/reversible option

3. **Proceed with execution**: Don't block on user clarification

4. **Report decision**: Note in progress log why this path was chosen

---

## Memory Contexts

| Context | Bank | Purpose |
|---------|------|---------|
| `system3-prd-tracking` | Private | Active initiative goals, outcome records |
| `system3-decisions` | Private | Autonomous decisions under ambiguity |
| `project` | Shared | General project context |

---

**Version**: 1.0.0
**Source**: System 3 Output Style - PRD-Driven Outcome Tracking Protocol
