---
title: "Fastapi Validation"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# Example: Validating FastAPI Design

## Scenario

Designing an API endpoint for work history verification that needs to handle async external calls.

## Research Query

```python
Task(
    subagent_type="general-purpose",
    model="haiku",
    description="Validate FastAPI async pattern",
    prompt="""
    Research Query: Best pattern for FastAPI endpoint that makes multiple async external API calls?

    Context: Building a verification endpoint that needs to:
    1. Call an external employer database API
    2. Call a voice agent service
    3. Store results in Supabase
    All async, with proper error handling and timeouts.

    Steps:
    1. Use mcp__context7__resolve-library-id for "fastapi"
    2. Use mcp__context7__query-docs for "async background tasks dependencies"
    3. Use mcp__perplexity-ask__perplexity_ask:
       - Should external calls be in endpoint or background task?
       - How to handle partial failures?
       - Timeout patterns for external APIs?

    Return:
    ## Recommended Pattern
    ## Code Structure
    ## Error Handling Approach
    ## Timeout Configuration
    """
)
```

## Expected Response

Pattern recommendation with BackgroundTasks vs async/await trade-offs, httpx for async HTTP, and structured error handling.
