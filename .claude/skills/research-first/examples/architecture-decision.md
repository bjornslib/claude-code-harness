---
title: "Architecture Decision"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# Example: Architecture Decision Research

## Scenario

Deciding between Redis and PostgreSQL for session state in a multi-instance deployment.

## Research Query

```python
Task(
    subagent_type="general-purpose",
    model="haiku",
    description="Research session storage architecture",
    prompt="""
    Research Query: Redis vs PostgreSQL for session state in multi-instance Python app?

    Context:
    - FastAPI app running 3+ instances behind load balancer
    - Session data: ~2KB per user, 1000 concurrent users
    - Need: Fast reads, occasional writes, 24hr TTL
    - Already have: Supabase (PostgreSQL), considering adding Redis

    Use Perplexity to research:
    1. Performance comparison for this use case
    2. Operational complexity (adding Redis vs using existing Postgres)
    3. Failure modes and recovery
    4. Cost implications

    Return:
    ## Options Compared
    | Aspect | Redis | PostgreSQL |
    |--------|-------|------------|
    | Read latency | ? | ? |
    | Complexity | ? | ? |
    | Failure recovery | ? | ? |

    ## Recommendation
    [Which to use and why]

    ## Implementation Notes
    [Key considerations for chosen approach]
    """
)
```

## Expected Response

Trade-off analysis with recommendation based on existing infrastructure (likely PostgreSQL since already have Supabase, unless latency requirements are strict).
