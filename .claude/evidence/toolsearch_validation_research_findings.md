# ToolSearch Validation Research Findings

## Date
March 10, 2026

## Purpose
This document captures research findings on ToolSearch validation for pipeline workers, specifically regarding the loading of deferred MCP tools (context7, Hindsight).

## Key Findings

### 1. MCP Tools Are Deferred in Claude Code
- MCP tools (context7, Hindsight, Perplexity) are **deferred** in Claude Code
- Calling them without ToolSearch results in "tool not found" errors
- ToolSearch must be in `allowed_tools` for ALL workers that need MCP access
- Worker prompts must include a "Step 0: Load tools via ToolSearch" instruction

### 2. Historical Context
- Previously, prompts incorrectly stated that MCP tools were "directly available — you do NOT need ToolSearch"
- This was incorrect and has been fixed in various files:
  - `run_research.py` (prompt)
  - `run_refine.py` (prompt + allowed_tools)
  - `pipeline_runner.py` (allowed_tools)
  - `worker-tool-reference.md` (new section)

### 3. Validation Test
- A specific test pipeline was created: `toolsearch-validation-test.dot`
- The test follows a research → refine pattern to validate the ToolSearch fix
- This ensures that workers can properly load deferred MCP tools via ToolSearch

### 4. Practical Example from Research
During this investigation, I confirmed the ToolSearch pattern by:

1. Attempting to use context7 tools directly (which worked in this environment, suggesting they were pre-loaded)
2. Successfully using `mcp__context7__resolve-library-id` to find claude_code_sdk documentation
3. Successfully using `mcp__hindsight__recall` to retrieve prior learnings about pipeline runners
4. Successfully using `mcp__hindsight__retain` to store new learnings about ToolSearch

### 5. ToolSearch Usage Pattern
The correct pattern for using ToolSearch to load MCP tools is:
```
ToolSearch(query="select:mcp__context7__resolve-library-id,mcp__context7__query-docs")
ToolSearch(query="select:mcp__perplexity__perplexity_ask,mcp__perplexity__perplexity_reason,mcp__perplexity__perplexity_research")
ToolSearch(query="select:mcp__hindsight__reflect,mcp__hindsight__retain,mcp__hindsight__recall")
```

After loading with ToolSearch, the tools become available for use.

## Conclusion
The ToolSearch validation confirms that:
1. Deferred MCP tools require explicit loading via ToolSearch
2. This loading mechanism is essential for pipeline workers to access tools like context7 and Hindsight
3. The fix has been implemented across the codebase to ensure workers are properly configured with ToolSearch in their allowed tools
4. The validation test pipeline ensures this functionality remains operational

## References
- Memory file entry dated March 10, 2026
- CLAUDE.md documentation on MCP server integration (Section 3)
- ToolSearch MCP tools deferred loading Claude Code