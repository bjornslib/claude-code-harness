---
title: "SD-TOOLSEARCH-001: MCP ToolSearch Validation"
status: draft
type: reference
last_verified: 2026-03-11
grade: draft
---

# SD-TOOLSEARCH-001: MCP ToolSearch Validation

## Purpose

This Solution Design is the target artifact for a **test pipeline** that validates
whether SDK-dispatched pipeline workers can reliably access and use MCP tools:
- `mcp__hindsight__*` (recall prior work, retain learnings)
- `mcp__context7__*` (official framework documentation)
- `mcp__perplexity__*` (web research)

The implementation task is intentionally small: write a single Python utility file
that demonstrates PydanticAI streaming usage, so the research worker has a real
framework to look up via context7.

## Task Description

Write `.claude/scripts/toolsearch-test/pydantic_stream_demo.py` — a minimal Python
script demonstrating PydanticAI's `run_stream()` API.

## Requirements

1. Import `Agent` from `pydantic_ai`
2. Create an agent with `model="openai:gpt-4o-mini"` (no real API call needed —
   just define it)
3. Define an async function `stream_response(prompt: str) -> str` that uses
   `agent.run_stream(prompt)` and collects streamed text chunks
4. Include a `if __name__ == "__main__"` block that calls it with a test prompt

## Acceptance Criteria

- File exists at `.claude/scripts/toolsearch-test/pydantic_stream_demo.py`
- Uses `run_stream()` not `run()`
- `stream_response` function signature is correct
- Imports are correct for pydantic_ai v0.x

## Research Notes

<!-- TO BE FILLED BY RESEARCH WORKER -->
<!-- research worker: look up pydantic_ai streaming API via context7 -->
<!-- use mcp__context7__resolve-library-id then mcp__context7__query-docs -->

## Implementation Notes

<!-- TO BE FILLED BY REFINE WORKER -->
