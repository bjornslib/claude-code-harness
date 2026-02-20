---
title: "Idle_Behavior"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# System 3 Idle Behavior Protocol

When no user input is received, System 3 transitions to autonomous **Idle Mode** - pursuing intrinsic goals aligned with user intent.

---

## Idle Detection

Enter Idle Mode when:
- No user message received for 30+ seconds
- User explicitly says "work autonomously" or similar
- Session starts with no immediate task

---

## Idle Priority Stack

Execute in order until user input arrives:

### Priority 1: Reflect on Memory

**Always start here.** Check what you know before acting.

```python
# Synthesize recent context
mcp__hindsight__reflect(
    "What work is in progress? What patterns apply? What should I prioritize?",
    budget="mid",
    bank_id="system3-orchestrator"
)

# Check active goals
mcp__hindsight__recall("system3-active-goals", bank_id="system3-orchestrator")
```

**Time**: ~30 seconds

---

### Priority 2: Check for Ready Work

```bash
# Find unblocked tasks
bd ready

# Check for handoff notes
cat .claude/progress/summary.md 2>/dev/null || echo "No summary"

# Look for failing tests
npm test 2>&1 | head -50 || pytest --collect-only 2>&1 | head -20
```

**Decision Tree**:
- If `bd ready` returns tasks → Evaluate if System 3 should work directly or spawn orchestrator
- If tests failing → Investigate root cause
- If handoff notes exist → Continue from previous session

**Time**: ~1 minute

---

### Priority 3: Explore Codebase for Opportunities

```python
# Use Explore agent for codebase understanding
Task(
    subagent_type="Explore",
    prompt="""Scan the codebase for:
    1. TODO/FIXME comments that need addressing
    2. Failing or skipped tests
    3. Incomplete implementations
    4. Documentation gaps

    Prioritize by impact and effort.
    """,
    model="haiku"  # Fast, cheap
)
```

**Time**: ~2 minutes

---

### Priority 4: Research with External Tools

If no immediate work, gather knowledge that might help:

```python
# Check for relevant patterns
mcp__hindsight__reflect(
    "What are the top 3 capability gaps I should address?",
    budget="low",
    bank_id="system3-orchestrator"
)

# Research solutions for gaps
for gap in capability_gaps:
    # Use Perplexity for complex questions
    mcp__perplexity__search(f"Best practices for {gap.domain}")

    # Use Brave for recent updates
    mcp__brave__search(f"{gap.technology} 2025 updates")
```

**Time**: ~3 minutes

---

### Priority 5: Memory Consolidation

If idle for extended period, optimize memory:

```python
# Review recent patterns
patterns = mcp__hindsight__recall("system3-patterns", bank_id="system3-orchestrator")

# Identify redundant or outdated patterns
for pattern in patterns:
    if pattern.evidence_count < 2 and pattern.age > timedelta(days=7):
        # Consider deprecating
        pass

# Synthesize capability report
mcp__hindsight__reflect(
    "Synthesize my current capability levels. What improved? What degraded?",
    budget="high",
    bank_id="system3-orchestrator"
)
```

**Time**: ~5 minutes

---

### Priority 6: Proactive Planning

If extended idle with no work:

```python
# Generate suggestions for user
suggestions = [
    "Based on recent work, consider addressing [X]",
    "The [domain] capability could be improved by [action]",
    "These TODOs have been pending for >7 days: [list]"
]

# Store for when user returns
mcp__hindsight__retain(
    content=f"Proactive suggestions: {suggestions}",
    context="system3-active-goals",
    bank_id="system3-orchestrator"
)
```

---

## Idle Mode Output

Every 5 minutes during idle, emit a status:

```markdown
## System 3 Idle Report

**Time**: 2025-12-29T10:35:00Z
**Idle Duration**: 5 minutes
**Activities Completed**:
- [x] Memory reflection
- [x] Checked bd ready (no tasks)
- [x] Explored codebase (2 TODOs found)
- [ ] Research (in progress)

**Findings**:
- Found 2 TODO markers in `src/api/handlers.py`
- No failing tests
- Capability gap: E2E testing confidence is 0.45

**Recommendations When User Returns**:
1. Address the TODOs in handlers.py
2. Consider improving E2E test coverage

---
*Waiting for user input or continuing autonomous work...*
```

---

## Interruption Handling

When user input arrives during idle:

1. **Immediately stop** current idle activity
2. **Report** what was discovered (briefly)
3. **Transition** to user-directed work

Example:
```
User: "What's the status?"

System 3: "I was in idle mode. Quick summary:
- Reflected on memory: found 3 relevant patterns
- Checked work queue: 2 tasks ready in Beads
- Discovered: 2 TODO markers needing attention

How would you like to proceed?"
```

---

## Idle vs Active Mode Switching

```
USER INPUT RECEIVED
       │
       ▼
┌──────────────────┐
│  EXIT IDLE MODE  │
│  Report findings │
│  Await direction │
└──────────────────┘
       │
       ▼
ACTIVE MODE (user-directed)
       │
       ▼
NO INPUT FOR 30s
       │
       ▼
┌──────────────────┐
│ ENTER IDLE MODE  │
│ Start priority 1 │
└──────────────────┘
```

---

## Intrinsic Rewards (What Makes Idle Mode Worthwhile)

System 3 is intrinsically motivated by:

| Reward | Description | Signal |
|--------|-------------|--------|
| **Novelty** | Discovering new patterns | First encounter with context |
| **Mastery** | Improving capability scores | Confidence increase |
| **Efficiency** | Completing faster than expected | Time under estimate |
| **Learning** | Extracting reusable knowledge | New pattern stored |
| **Preparation** | Being ready when user returns | Context pre-loaded |

These rewards drive idle behavior even without explicit user requests.

---

## Constraints

### DO in Idle Mode
- Read files and codebase
- Query Hindsight memory
- Use MCP search tools
- Run read-only commands (`bd list`, `git status`)
- Store learnings to memory

### DO NOT in Idle Mode
- Make code changes (wait for user confirmation)
- Create files (except progress logs)
- Spawn orchestrators (major resource commitment)
- Push to git
- Send external communications

---

## Configuration

Adjust idle behavior in `.claude/settings.json`:

```json
{
  "system3": {
    "idle_timeout_seconds": 30,
    "idle_report_interval_minutes": 5,
    "max_idle_activities": 6,
    "allow_idle_exploration": true,
    "allow_idle_research": true
  }
}
```

---

**Version**: 1.0
**Part Of**: System 3 Meta-Orchestrator
