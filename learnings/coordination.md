# Coordination Patterns

Successful patterns for multi-agent orchestration.

---

## Worker Selection

### Matching Workers to Tasks

| Task Characteristics | Best Worker |
|---------------------|-------------|
| React, TypeScript, UI | `frontend-dev-expert` |
| CSS, Tailwind, styling | `frontend-dev-expert` |
| Python, FastAPI | `backend-solutions-engineer` |
| PydanticAI, agents | `backend-solutions-engineer` |
| MCP tools | `backend-solutions-engineer` |
| Scripts, docs, misc | `general-purpose` |

### When Unsure

If a task spans multiple domains:
1. Decompose further
2. Assign parts to specialized workers
3. Use general-purpose only for truly mixed work

---

## Communication Patterns

### Assignment Clarity

Good assignment includes:
- Exact feature ID and description
- All validation steps
- Complete file scope
- Dependencies confirmed passed
- Clear instructions

### Completion Verification

Before marking feature passed:
1. Worker claims completion
2. Orchestrator runs validation steps
3. Orchestrator verifies scope adherence
4. Orchestrator updates feature_list.json

---

## Session Continuity

### Handoff Protocol

Before ending session:
1. Complete or cleanly stop current feature
2. Update feature_list.json
3. Update progress/summary.md
4. Add entry to progress/log.md
5. Ensure git is clean

### Starting New Session

1. Read feature_list.json
2. Read progress/summary.md
3. Run regression check
4. Pick next ready feature

---

## Parallel Work (Future)

When multiple workers can work simultaneously:
- Only on features with NO shared dependencies
- Only on features with NO overlapping scope
- Coordinate commits carefully

---

## Learning Log

*Add coordination patterns discovered during orchestration sessions here*
