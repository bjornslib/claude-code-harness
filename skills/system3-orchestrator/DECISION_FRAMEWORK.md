# System 3 Decision Framework

This document contains optional decision-making frameworks for System 3 orchestration.

---

## Exploration vs Exploitation Balance

```
exploration_rate = max(0.05, 0.3 * (0.95 ^ session_count))
```

### Explore (try new approaches) when:
- `random() < exploration_rate`
- No existing pattern for this context
- Previous pattern failed

### Exploit (use known patterns) when:
- High-confidence pattern exists (validated via process supervision)
- Time-sensitive work
- User explicitly requested proven approach

---

**Source**: Extracted from `system3-meta-orchestrator.md` for progressive disclosure.
