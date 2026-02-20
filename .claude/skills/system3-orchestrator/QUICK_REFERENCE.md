---
title: "Quick_Reference"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# System 3 Quick Reference

This document contains quick reference tables for System 3 operations.

---

## Quick Reference

### Hindsight Operations

| Operation | Budget | Bank | Use Case |
|-----------|--------|------|----------|
| `reflect` | `high` | private | Process supervision, validation |
| `reflect` | `mid` | both | Standard synthesis, startup |
| `reflect` | `low` | either | Quick checks |
| `recall` | - | either | Direct retrieval |
| `retain` | - | appropriate | Store learnings |

### Memory Flow

```
Session Start
    │
    ├── reflect(private) → meta-wisdom
    ├── reflect(shared) → project context
    │
    ▼
Work / Idle / Spawn Orchestrator
    │
    ▼
Session End
    │
    ├── Process Supervision (reflect high)
    ├── retain(private) → meta-learnings
    ├── retain(shared) → project learnings (if any)
    └── retain(private) → next session context
```

---

**Source**: Extracted from `system3-meta-orchestrator.md` for progressive disclosure.
