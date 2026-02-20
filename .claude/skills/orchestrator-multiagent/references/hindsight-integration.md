---
title: "Hindsight Integration"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# Memory-Driven Decision Making (Hindsight Integration)

The orchestrator uses Hindsight as extended memory to learn from experience and avoid repeating mistakes.

**Architecture Context**: For Hindsight's role in System 3's memory-driven philosophy and dual-bank architecture, see `system3-meta-orchestrator.md` → "Dual-Bank Startup Protocol" section.

## Core Principle

**Before deciding, recall. After learning, retain. When stuck, reflect + validate.**

## Integration Points

| Decision Point | Action | Purpose |
|----------------|--------|---------|
| **Task start** | `recall` | Check for pertinent memories before beginning |
| **User feedback received** | `retain` → `reflect` → `retain` | Capture feedback, extract lesson, store pattern |
| **Rejected 2 times** (feature OR regression) | `recall` → `reflect` → Perplexity → `retain` | Full analysis with external validation |
| **Regression detected** (first time) | `recall` | Check for similar past situations |
| **Hollow test detected** | `reflect` → Perplexity → `retain` | Analyze gap, validate fix, store prevention |
| **AT epic/session closure** | `reflect` → `retain` | Synthesize patterns and store insights |

## Task Start Memory Check

**Before starting ANY task:**

```python
# Check for pertinent memories about this task type/context
mcp__hindsight__recall("What should I remember about [task type/domain]?")
```

This surfaces patterns like:
- "Always launch Haiku sub-agent to monitor workers"
- "This component has fragile dependencies on X"
- "Previous attempts failed because of Y"

## User Feedback Loop

**When the user provides feedback** (corrections, reminders, guidance):

```
USER FEEDBACK DETECTED
    │
    ▼
1. RETAIN immediately
   mcp__hindsight__retain(
       content="User reminded me to [X] when [context]",
       context="patterns"
   )
    │
    ▼
2. REFLECT on the lesson
   mcp__hindsight__reflect(
       query="Why did I forget this? What pattern should I follow?",
       budget="mid"
   )
    │
    ▼
3. RETAIN the extracted pattern
   mcp__hindsight__retain(
       content="Lesson: [extracted pattern from reflection]",
       context="patterns"
   )
```

**Example**: User keeps reminding to launch Haiku sub-agent for monitoring:
- Retain: "User reminded me to launch Haiku sub-agent to monitor worker progress"
- Reflect: "Why did I miss this? What's the pattern?"
- Retain: "Lesson: Always use run_in_background=True for parallel workers"

## Rejected 2 Times (Feature or Regression)

**When a feature is rejected twice OR regression occurs twice:**

```python
# 1. Recall similar situations
mcp__hindsight__recall("What happened when [similar feature/regression] was rejected?")

# 2. Reflect on patterns
mcp__hindsight__reflect(
    query="Why has [feature/regression] failed twice? What pattern is emerging?",
    budget="high"
)

# 3. Validate with Perplexity (MANDATORY)
mcp__perplexity-ask__perplexity_ask(
    messages=[{
        "role": "user",
        "content": "I'm seeing repeated failures with [issue]. My hypothesis is [reflection output]. Is this assessment correct? What approaches should I consider?"
    }]
)

# 4. Retain the validated lesson
mcp__hindsight__retain(
    content="Double rejection: [feature]. Root cause: [X]. Validated approach: [Y]",
    context="bugs"
)
```

## Regression Detected (First Time)

**On first regression detection:**

```python
# Recall only - check for similar past situations
mcp__hindsight__recall("What do I know about regressions in [component/area]?")
```

If recall surfaces relevant patterns, apply them. If not, proceed with standard fix.

## Hollow Test Analysis

**When tests pass but feature doesn't work:**

```python
# 1. Reflect on the gap
mcp__hindsight__reflect(
    query="Why did tests pass but feature fail? What's the mock/reality gap?",
    budget="high"
)

# 2. Validate prevention approach with Perplexity
mcp__perplexity-ask__perplexity_ask(
    messages=[{
        "role": "user",
        "content": "My tests passed but feature failed because [gap]. How should I improve my testing approach to catch this?"
    }]
)

# 3. Retain prevention pattern
mcp__hindsight__retain(
    content="Hollow test: [scenario]. Gap: [X]. Prevention: [Y]",
    context="patterns"
)
```

## AT Epic/Session Closure

**When closing an AT epic or ending a session:**

```python
# 1. Reflect on patterns that emerged
mcp__hindsight__reflect(
    query="What patterns emerged from this [epic/session]? What worked well? What should be done differently?",
    budget="high"
)

# 2. Retain the insights
mcp__hindsight__retain(
    content="[Epic/Session] insights: [key patterns and learnings]",
    context="patterns"
)
```

## The Learning Loop

```
Experience → Retain → Reflect → Retain Pattern → Recall Next Time → Apply
     ↑                                                              │
     └──────────────────────────────────────────────────────────────┘
```

This creates a continuous improvement cycle where each task benefits from all previous experience.
