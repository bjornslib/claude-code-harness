# Hindsight Integration for System 3

System 3's memory is implemented via **Hindsight MCP** with a **dual-bank architecture**. This document defines the architecture, query patterns, process supervision, and storage conventions.

---

## Hindsight Architecture

Based on [arXiv:2512.12818](https://arxiv.org/abs/2512.12818) - "Hindsight: Agent Memory That Works Like Human Memory"

### Four Memory Networks (Per Bank)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     HINDSIGHT MEMORY STRUCTURE                      │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐│
│  │    WORLD    │  │ EXPERIENCE  │  │ OBSERVATION │  │   OPINION   ││
│  │             │  │             │  │             │  │             ││
│  │  Objective  │  │   Agent's   │  │ Synthesized │  │ Subjective  ││
│  │   facts     │  │  biography  │  │  summaries  │  │  beliefs    ││
│  │             │  │  (GEO chains)│  │  (patterns) │  │ +confidence ││
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘│
│         │                │                │                │       │
│         └────────────────┴────────┬───────┴────────────────┘       │
│                                   │                                 │
│                    ┌──────────────┴──────────────┐                 │
│                    │      KNOWLEDGE GRAPH        │                 │
│                    │                             │                 │
│                    │  Links memories via:        │                 │
│                    │  • Shared entities          │                 │
│                    │  • Temporal proximity       │                 │
│                    │  • Cause-effect relations   │                 │
│                    └─────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Three Core Operations

| Operation | What Happens | Use Case |
|-----------|-------------|----------|
| **RETAIN** | LLM extracts facts, entities, relationships; builds graph | Storing learnings |
| **RECALL** | Vector + keyword + graph + temporal search | Direct lookups |
| **REFLECT** | LLM reasons over memories; forms new observations | Synthesis, **process supervision** |

---

## Dual-Bank Architecture

System 3 uses **two memory banks** for different purposes:

```
┌─────────────────────────────────┐    ┌─────────────────────────────────┐
│   PRIVATE BANK                  │    │   SHARED BANK                   │
│   system3-orchestrator           │    │   claude-code-agencheck         │
│                                 │    │                                 │
│   WHO: Only System 3            │    │   WHO: All Claude Code sessions │
│                                 │    │                                 │
│   PURPOSE:                      │    │   PURPOSE:                      │
│   • Meta-orchestration wisdom   │    │   • Project knowledge           │
│   • Capability tracking         │    │   • Development patterns        │
│   • Strategic patterns          │    │   • Architecture decisions      │
│   • Cross-session learning      │    │   • Bug lessons                 │
│                                 │    │   • Deployment patterns         │
│   CONTEXTS:                     │    │                                 │
│   ├── system3-patterns          │    │   CONTEXTS:                     │
│   ├── system3-anti-patterns     │    │   ├── project                   │
│   ├── system3-capabilities      │    │   ├── patterns                  │
│   ├── system3-narrative         │    │   ├── architecture              │
│   └── system3-active-goals      │    │   ├── bugs                      │
│                                 │    │   └── deployment                │
└─────────────────────────────────┘    └─────────────────────────────────┘
```

### Why Two Banks?

| Concern | Private Bank | Shared Bank |
|---------|-------------|-------------|
| **Isolation** | System 3's meta-cognition is private | Project knowledge is shared |
| **Noise Reduction** | Workers don't pollute meta-patterns | Workers contribute project patterns |
| **Security** | Capability assessments stay private | General patterns are shareable |
| **Performance** | Smaller, focused bank for meta-queries | Larger bank for project queries |

---

## Configuration

### MCP Configuration for System 3

```json
// .mcp.json (for System 3 uber-orchestrator)
{
  "mcpServers": {
    "hindsight-system3": {
      "url": "http://localhost:8888/mcp/system3-orchestrator/mcp"
    },
    "hindsight-shared": {
      "url": "http://localhost:8888/mcp/claude-code-agencheck/mcp"
    }
  }
}
```

### MCP Configuration for Orchestrators/Workers

```json
// .mcp.json (for spawned orchestrators and workers)
{
  "mcpServers": {
    "hindsight": {
      "url": "http://localhost:8888/mcp/claude-code-agencheck/mcp"
    }
  }
}
```

---

## Process Supervision via Reflect

**Key Insight**: `reflect(budget="high")` IS the Guardian LLM for process supervision.

### How It Works

Hindsight's `reflect` operation:
1. Retrieves relevant memories from the knowledge graph
2. **Launches an LLM** to reason over those memories
3. Forms new observations and opinions
4. Returns synthesized understanding

By asking rigorous validation questions, we use `reflect` as a process supervisor.

### Validation Pattern

```python
async def validate_reasoning_path(pattern: Pattern, outcome: Outcome) -> ValidationResult:
    """Use Hindsight reflect as Guardian LLM for process supervision."""

    validation = await mcp__hindsight__reflect(
        query=f"""
        PROCESS SUPERVISION: Validate this reasoning path

        ## Context
        Domain: {pattern.domain}
        Task Type: {pattern.task_type}
        Description: {pattern.context_description}

        ## Decisions Made (chronological)
        {format_decisions(pattern.decisions)}

        ## Outcome
        Success: {outcome.success}
        Quality Score: {outcome.quality_score}
        Duration: {outcome.duration}
        Side Effects: {outcome.side_effects}

        ## Validation Questions

        1. **Logical Necessity**: Was each decision logically required to achieve the goal?
           - Identify any unnecessary steps
           - Identify any missing steps

        2. **Generalizability**: Would this reasoning path work in similar contexts?
           - What contexts does this apply to?
           - What contexts would it fail in?

        3. **Luck vs Skill**: Was success due to sound reasoning or circumstantial luck?
           - Were there fragile assumptions?
           - Were there environmental dependencies?

        4. **Failure Modes**: What could cause this pattern to fail?
           - Edge cases not covered
           - Assumptions that might not hold

        ## Required Response Format

        VERDICT: VALID or INVALID
        CONFIDENCE: 0.0 to 1.0
        GENERALIZABILITY: [list of applicable contexts]
        FAILURE_MODES: [list of potential failures]
        EXPLANATION: [detailed reasoning]
        """,
        budget="high",  # Deep reasoning for validation
        bank_id="system3-orchestrator"
    )

    return parse_validation_result(validation)
```

### When to Apply Process Supervision

| Trigger | Action |
|---------|--------|
| Orchestrator session completes | Validate before storing patterns |
| Pattern used successfully | Increment confidence |
| Pattern fails | Re-validate, possibly demote to anti-pattern |
| Idle-time consolidation | Review recent patterns |
| Merging similar patterns | Validate merged pattern |

---

## Query Patterns

### Session Startup (Dual-Bank)

```python
async def system3_startup():
    # 1. Query private bank for meta-wisdom
    meta_wisdom = await mcp__hindsight__reflect(
        query="""
        What are my orchestration patterns, anti-patterns, and capability assessments?
        What work is currently in progress?
        What did I learn from recent sessions?
        What are my capability gaps?
        """,
        budget="mid",
        bank_id="system3-orchestrator"
    )

    # 2. Query shared bank for project context
    project_context = await mcp__hindsight__reflect(
        query="""
        What is the current project state?
        What patterns apply to active work?
        Any recent architectural decisions or bug lessons?
        What tasks are pending?
        """,
        budget="mid",
        bank_id="claude-code-agencheck"
    )

    return synthesize_context(meta_wisdom, project_context)
```

### Before Spawning Orchestrator

```python
async def prepare_wisdom_injection(initiative: str, domain: str):
    # 1. Get meta-orchestration patterns (private)
    meta_patterns = await mcp__hindsight__reflect(
        query=f"""
        What orchestration patterns apply to {initiative}?
        What anti-patterns should be avoided?
        What is my capability level for {domain}?
        """,
        budget="mid",
        bank_id="system3-orchestrator"
    )

    # 2. Get domain-specific patterns (shared)
    domain_patterns = await mcp__hindsight__reflect(
        query=f"""
        What development patterns apply to {domain}?
        What architectural decisions are relevant?
        What bugs/lessons apply here?
        """,
        budget="mid",
        bank_id="claude-code-agencheck"
    )

    return format_wisdom_injection(meta_patterns, domain_patterns)
```

### Post-Session Storage

```python
async def store_session_learnings(session: Session, outcome: Outcome):
    # 1. Apply process supervision
    validation = await validate_reasoning_path(session.patterns, outcome)

    # 2. Store to private bank (meta-learnings)
    if validation.verdict == "VALID" and validation.confidence > 0.7:
        await mcp__hindsight__retain(
            content=format_validated_pattern(session, validation),
            context="system3-patterns",
            bank_id="system3-orchestrator"
        )
    else:
        await mcp__hindsight__retain(
            content=format_anti_pattern(session, validation),
            context="system3-anti-patterns",
            bank_id="system3-orchestrator"
        )

    # 3. Store GEO chain (narrative memory)
    await mcp__hindsight__retain(
        content=format_geo_chain(session, outcome),
        context="system3-narrative",
        bank_id="system3-orchestrator"
    )

    # 4. Update capability assessment
    await mcp__hindsight__retain(
        content=format_capability_update(session.domain, outcome),
        context="system3-capabilities",
        bank_id="system3-orchestrator"
    )

    # 5. Store project learnings to shared bank (if applicable)
    if session.has_project_learnings:
        await mcp__hindsight__retain(
            content=format_project_pattern(session),
            context="patterns",
            bank_id="claude-code-agencheck"
        )
```

---

## Memory Format Templates

### Validated Pattern (Private Bank)

```markdown
## Pattern: {name}

**Validated**: {timestamp}
**Process Supervision Confidence**: {confidence}

### Context
- Domain: {domain}
- Task Type: {task_type}
- Applicability: {generalizability_contexts}

### Pattern Description
{description}

### Decision Sequence
1. {step_1}
2. {step_2}
...

### Evidence
- Sessions: {session_count}
- Success Rate: {success_rate}%
- Average Duration: {avg_duration}

### Failure Modes (from validation)
{failure_modes}

### When NOT to Use
{inapplicable_contexts}
```

### Anti-Pattern (Private Bank)

```markdown
## Anti-Pattern: {name}

**Recorded**: {timestamp}
**Process Supervision Verdict**: INVALID ({confidence})

### Context Where It Failed
- Domain: {domain}
- Task Type: {task_type}
- Specific Situation: {situation}

### What Happened
{description}

### Decision Sequence (AVOID)
1. {step_1}
2. {step_2}
...

### Why It Failed
{root_cause}

### Prevention
{prevention_strategy}

### Alternative Approaches
1. {alternative_1}
2. {alternative_2}
```

### GEO Chain (Private Bank)

```markdown
## Goal-Experience-Outcome: {chain_id}

**Session**: {session_id}
**Timestamp**: {timestamp}

### Goal
{goal_description}

**Success Criteria**:
- {criterion_1}
- {criterion_2}

### Experiences (Chronological)
1. **{timestamp_1}**: {action_1}
   - Observation: {observation_1}
   - Worker: {worker_if_any}

2. **{timestamp_2}**: {action_2}
   - Observation: {observation_2}

...

### Outcome
- **Success**: {True/False}
- **Quality Score**: {0.0-1.0}
- **Duration**: {duration}
- **Side Effects**: {side_effects}

### Lessons Learned
1. {lesson_1}
2. {lesson_2}

### Capability Impact
- Domain: {domain}
- Confidence Delta: {delta:+.2f}
```

### Capability Update (Private Bank)

```markdown
## Capability Update: {timestamp}

### Domain: {domain}

**Previous**: {old_confidence}
**Current**: {new_confidence}
**Delta**: {delta:+.2f}

### Evidence
- Session: {session_id}
- Outcome: {success/failure}
- Quality: {quality_score}

### Notes
{contextual_notes}

### Learning Target (if gap detected)
{learning_target_if_any}
```

---

## Memory Consolidation (Idle Time)

During idle periods, consolidate memories:

```python
async def consolidate_memories():
    # 1. Find similar patterns to merge
    patterns = await mcp__hindsight__recall(
        query="system3-patterns",
        bank_id="system3-orchestrator"
    )

    clusters = cluster_similar_patterns(patterns)
    for cluster in clusters:
        if len(cluster) >= 3:
            # Merge and re-validate
            merged = merge_patterns(cluster)
            validation = await validate_reasoning_path(merged, aggregate_outcomes(cluster))

            if validation.confidence > 0.8:
                await mcp__hindsight__retain(
                    content=format_merged_pattern(merged, validation),
                    context="system3-patterns",
                    bank_id="system3-orchestrator"
                )

    # 2. Synthesize capability report
    capability_synthesis = await mcp__hindsight__reflect(
        query="""
        Synthesize current capability levels:
        - Strongest capabilities (confidence > 0.8)
        - Weakest capabilities (confidence < 0.5)
        - Recent improvements
        - Recent degradations
        - Recommended learning targets
        """,
        budget="high",
        bank_id="system3-orchestrator"
    )

    await mcp__hindsight__retain(
        content=capability_synthesis,
        context="system3-capabilities",
        bank_id="system3-orchestrator",
        document_id=f"capability-report-{date.today()}"
    )
```

---

## Query Budget Guidelines

| Budget | Cost | Depth | Use Cases |
|--------|------|-------|-----------|
| `low` | $ | Shallow | Quick fact checks, simple recalls |
| `mid` | $$ | Standard | Startup synthesis, pattern retrieval |
| `high` | $$$ | Deep | **Process supervision**, validation, complex synthesis |

**Rule of Thumb**:
- Default to `mid`
- Use `high` only for process supervision and critical decisions
- Use `low` for quick checks during active work

---

## Information Flow Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SYSTEM 3 MEMORY FLOW                            │
└─────────────────────────────────────────────────────────────────────┘

SESSION START
    │
    ├── reflect(private, mid) ───► Meta-wisdom
    ├── reflect(shared, mid) ────► Project context
    │
    ▼
ACTIVE WORK / IDLE / SPAWN ORCHESTRATOR
    │
    ├── recall(shared) ──────────► Quick lookups
    ├── reflect(shared, mid) ────► Domain patterns
    │
    ▼
SESSION END
    │
    ├── reflect(private, high) ──► Process Supervision
    │       │
    │       ├── VALID + high confidence
    │       │       │
    │       │       └── retain(private) ──► system3-patterns
    │       │
    │       └── INVALID or low confidence
    │               │
    │               └── retain(private) ──► system3-anti-patterns
    │
    ├── retain(private) ─────────► system3-narrative (GEO chain)
    ├── retain(private) ─────────► system3-capabilities
    ├── retain(private) ─────────► system3-active-goals
    │
    └── retain(shared) ──────────► patterns (if project learnings)
```

---

## Quick Reference

### Bank Selection

| Query Type | Bank | Rationale |
|------------|------|-----------|
| Meta-orchestration patterns | Private | System 3 exclusive |
| Capability assessments | Private | Self-model is private |
| Active goals / next steps | Private | Strategic planning |
| Project patterns | Shared | All sessions benefit |
| Architecture decisions | Shared | Project knowledge |
| Bug lessons | Shared | Everyone should know |

### Context Selection

| What to Store | Bank | Context |
|---------------|------|---------|
| Validated orchestration pattern | Private | `system3-patterns` |
| Failed orchestration approach | Private | `system3-anti-patterns` |
| Capability update | Private | `system3-capabilities` |
| Session narrative (GEO chain) | Private | `system3-narrative` |
| Next session goals | Private | `system3-active-goals` |
| Development pattern | Shared | `patterns` |
| Architecture decision | Shared | `architecture` |
| Bug lesson | Shared | `bugs` |

---

**Version**: 2.0 (Dual-Bank + Process Supervision)
**Based On**:
- Hindsight paper (arXiv:2512.12818)
- Sophia paper (arXiv:2512.18202)
**Integration**: Hindsight MCP (dual-bank configuration)
