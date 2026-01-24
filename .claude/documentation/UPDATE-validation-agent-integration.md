# Update Plan: validation-agent Integration

**Date**: 2026-01-24
**Status**: COMPLETED
**Related**: SOLUTION-DESIGN-acceptance-testing.md

## Context

We've created two new skills for acceptance testing:
- `acceptance-test-writer` - Generates YAML test scripts from PRD
- `acceptance-test-runner` - Executes tests and generates evidence reports

The `validation-agent` has been updated to route to these skills:
- `--mode=unit` - Fast technical checks (mocks OK)
- `--mode=e2e --prd=PRD-XXX` - Full acceptance validation (real data)

## Problem

The system3 and orchestrator output styles/skills need to be updated to:
1. Use the new mode names (`unit`/`e2e` instead of `implementation`/`business`)
2. Always pass `--prd=PRD-XXX` for E2E validation
3. Never call acceptance-test skills directly - always through validation-agent
4. Fix WORKFLOWS.md which incorrectly shows direct `bd close`

## Files to Update

| File | Changes |
|------|---------|
| `orchestrator-multiagent/WORKFLOWS.md` | Replace `bd close` with validation-agent delegation |
| `orchestrator-multiagent/SKILL.md` | Update examples to new modes |
| `orchestrator-multiagent/VALIDATION.md` | Update to reference new modes |
| `output-styles/orchestrator.md` | Update TASK CLOSURE GATE |
| `output-styles/system3-meta-orchestrator.md` | Update validation sections |
| `system3-orchestrator/references/validation-workflow.md` | Update mode references |

## Key Patterns

### Old Pattern (REMOVE)
```python
Task(subagent_type="validation-agent",
     prompt="--mode=implementation --task_id=X")

Task(subagent_type="validation-agent",
     prompt="--mode=business --epic-id=X")
```

### New Pattern (USE)
```python
# Fast unit check
Task(subagent_type="validation-agent",
     prompt="--mode=unit --task_id=TASK-123")

# Full E2E with PRD acceptance tests
Task(subagent_type="validation-agent",
     prompt="--mode=e2e --task_id=TASK-123 --prd=PRD-AUTH-001")
```

### Direct Skill Invocation (WRONG)
```python
# ❌ NEVER call skills directly
Skill("acceptance-test-runner", args="--prd=X")
Skill("acceptance-test-writer", args="--prd=X")
```

### Through validation-agent (CORRECT)
```python
# ✅ Always route through validation-agent
Task(subagent_type="validation-agent",
     prompt="--mode=e2e --task_id=X --prd=PRD-XXX")
# validation-agent will invoke acceptance-test-runner internally
```

## Iron Law #2

Add to system3-meta-orchestrator.md:

> **THE IRON LAW #2: Closure = validation-agent**
>
> ANY task/epic closure MUST go through validation-agent as the single entry point.
> - Orchestrator tasks: `--mode=unit` or `--mode=e2e --prd=X`
> - System 3 epics/KRs: `--mode=e2e --prd=X`

## Validation Chain

```
Worker completes
    ↓
Orchestrator runs: validation-agent --mode=unit (fast check)
    ↓
If pass: validation-agent --mode=e2e --prd=PRD-XXX (acceptance tests)
    ↓
validation-agent invokes acceptance-test-runner skill
    ↓
If all criteria pass: validation-agent closes task with evidence
If any fail: Report to orchestrator for remediation
```

## Completion Checklist

- [x] WORKFLOWS.md - Replace bd close with validation-agent
- [x] SKILL.md - Update examples
- [x] VALIDATION.md - Update modes
- [x] orchestrator.md - Update TASK CLOSURE GATE
- [x] system3-meta-orchestrator.md - Update validation + add Iron Law #2
- [x] validation-workflow.md - Update mode references

**Status**: COMPLETED (2026-01-24)
