---
title: "Adr 001 Output Style Reliability"
status: active
type: architecture
last_verified: 2026-02-19
grade: reference
---

# ADR-001: Output Style Reliability for Critical Content

## Status
Accepted

## Date
2026-01-12

## Context

The project uses a 3-level agent hierarchy (System 3 → Orchestrator → Worker) with two mechanisms for providing context:

1. **Output Styles** (`.claude/output-styles/`) - Loaded automatically at session start
2. **Skills** (`.claude/skills/`) - Must be explicitly invoked via Skill tool

We needed to determine where to place critical operational content that agents must follow to work correctly.

## Decision

**Critical content belongs in output styles; optional/reference content can live in skills.**

### Reliability Analysis

| Mechanism | Load Guarantee | Risk | Use For |
|-----------|----------------|------|---------|
| Output Style | 100% (automatic) | None | Critical patterns, core workflows, mandatory protocols |
| Skill | ~85% (requires invocation) | Agent may forget to invoke | Reference material, detailed guides, optional enhancements |

### Content Classification

**Output Style Content (Critical)**:
- Core workflow patterns (4-phase pattern, PREFLIGHT)
- Mandatory protocols (validation-test-agent enforcement, tmux Enter pattern)
- Session lifecycle (registration, handoff checklists)
- Memory integration patterns (Hindsight operations)

**Skill Content (Reference)**:
- Detailed implementation guides
- Extended reference tables
- Optional enhancement procedures
- Archive/legacy documentation

### Key Metrics

Based on analysis of the system3-meta-orchestrator.md output style:
- **~85% critical content** - Must be in output style for reliability
- **~15% optional content** - Can be extracted to skills with references

## Consequences

### Positive
- Critical patterns are always available to agents
- No risk of agents "forgetting" to invoke essential skills
- Single source of truth for core workflows
- Predictable agent behavior

### Negative
- Output styles are larger files (1800+ lines for system3-meta-orchestrator)
- Content duplication risk if not carefully managed
- Requires discipline to categorize content correctly

### Mitigations
- Cross-references from output styles to skills for related content
- Progressive disclosure: output style has pattern, skill has details
- Regular audits to identify misplaced content

## Alternatives Considered

### Option A: Everything in Skills
Rejected because skills must be explicitly invoked. Critical patterns would be missed if agents forget.

### Option B: Everything in Output Styles
Rejected because output styles would become too large and include optional content agents may not need.

### Option C: Hybrid with Cross-References (Selected)
Output styles contain critical content with references to skills for optional details. Best balance of reliability and maintainability.

## Related Documents

- `.claude/CLAUDE.md` - Agent hierarchy diagram
- `.claude/output-styles/system3-meta-orchestrator.md` - System 3 critical content
- `.claude/output-styles/orchestrator.md` - Orchestrator critical content
- `.claude/skills/system3-orchestrator/` - System 3 optional reference
- `.claude/skills/orchestrator-multiagent/` - Orchestrator implementation guides
