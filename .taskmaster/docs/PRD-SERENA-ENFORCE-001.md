# PRD-SERENA-ENFORCE-001: Serena MCP Usage Enforcement Hooks

## Status: Draft
## Priority: P1
## Owner: System 3

---

## Problem Statement

Claude Code agents (orchestrators and workers) consistently fall back to Read/Grep/Glob for source code exploration despite extensive documentation mandating Serena MCP usage. The pattern is:

1. Serena is mentioned as "MANDATORY" in 6+ locations (output styles, skills, PREFLIGHT, CLAUDE.md)
2. Agents activate Serena at session start (when reminded)
3. During actual work, agents default to Read/Grep under cognitive load
4. Users must manually intervene ("Remember Serena?") to redirect behavior

Text-based instructions have proven insufficient. Structural enforcement via hooks is required.

## Goals

1. **G1**: Reduce unnecessary Read/Grep calls on source code files by 80%+ when Serena is active
2. **G2**: Zero performance impact on non-code file operations (PRDs, YAML, JSON, markdown)
3. **G3**: Graceful degradation when Serena is not active (no blocking, just advisory)
4. **G4**: Works across all agent levels (System 3, orchestrators, workers)

## Solution: Two-Layer Hook Approach

### Layer 1: Synchronous PreToolUse Hook (Blocking)

**File**: `.claude/hooks/serena-enforce-pretool.py`
**Matcher**: `Read|Grep`
**Behavior**: Intercepts Read/Grep calls targeting source code files

**Decision logic**:
```
IF file extension is source code (.py, .ts, .tsx, .jsx, .js, .vue, .go, .rs, .java)
  AND Serena project is active (check .serena/ exists in project dir)
  AND NOT in bypass mode (SERENA_ENFORCE_SKIP=1)
THEN
  BLOCK with message: "Serena is active. Use mcp__serena__find_symbol,
  search_for_pattern, or get_symbols_overview instead of {tool} for source code.
  Set SERENA_ENFORCE_SKIP=1 to bypass."
ELSE
  APPROVE (fast path, ~1ms)
```

**Whitelist** (always approve):
- Non-code files: `.md`, `.yaml`, `.yml`, `.json`, `.toml`, `.cfg`, `.ini`, `.env`, `.txt`, `.csv`, `.feature`, `.html`, `.css`, `.scss`, `.dot`, `.gitignore`
- Files in non-code directories: `.claude/`, `.taskmaster/`, `acceptance-tests/`, `docs/`, `documentation/`, `.beads/`
- Glob tool calls (file discovery, not code reading)
- Any file when Serena is not active

**Bypass methods**:
1. Environment variable: `SERENA_ENFORCE_SKIP=1`
2. Signal file: `.claude/.serena-enforce-skip` (project-level temporary bypass)

### Layer 2: Async PostToolUse Hook (Advisory)

**File**: `.claude/hooks/serena-enforce-posttool.py`
**Matcher**: `Read|Grep`
**Async**: `true`
**Behavior**: After any Read/Grep that was approved (non-code files), provides a gentle reminder

**Decision logic**:
```
IF the Read/Grep target was a source code file
  AND Serena project is active
THEN
  Return systemMessage: "Reminder: Serena is active for this project.
  Consider using find_symbol or search_for_pattern for code navigation."
ELSE
  No output (silent)
```

This layer catches edge cases where the PreToolUse approved a borderline file but the agent could have used Serena more effectively.

## Acceptance Criteria

### AC-1: PreToolUse blocks Read on source code when Serena active
- Read("src/auth/routes.py") is BLOCKED with Serena suggestion message
- Read("README.md") is APPROVED (non-code)
- Read(".claude/settings.json") is APPROVED (non-code directory)

### AC-2: PreToolUse blocks Grep on source code when Serena active
- Grep(pattern="def login", path="src/") is BLOCKED with Serena suggestion
- Grep(pattern="TODO", path=".taskmaster/") is APPROVED (non-code directory)

### AC-3: Fast path for non-code files
- Non-code file operations complete in <5ms overhead
- No measurable impact on PRD reading, YAML parsing, markdown operations

### AC-4: Graceful degradation without Serena
- When no `.serena/` directory exists, ALL Read/Grep calls are APPROVED
- No errors, no warnings, silent pass-through

### AC-5: Bypass mechanism works
- `SERENA_ENFORCE_SKIP=1` environment variable allows Read/Grep on code files
- `.claude/.serena-enforce-skip` signal file allows Read/Grep on code files

### AC-6: PostToolUse async advisory
- After approved Read/Grep on non-code files, advisory message delivered on next turn
- Advisory does NOT block or slow down any operations
- Advisory only fires when Serena is active

### AC-7: Glob tool NOT affected
- Glob("**/*.py") is ALWAYS approved (file discovery, not code reading)
- Hook only matches Read and Grep

### AC-8: Settings.json properly configured
- PreToolUse entry with matcher "Read|Grep", sync, timeout 10s
- PostToolUse entry with matcher "Read|Grep", async: true
- Both hooks registered and functional

## Non-Goals

- Auto-activating Serena (separate concern, handled by PREFLIGHT)
- Modifying Serena's behavior or tools
- Enforcing Serena usage for Write/Edit operations (those are implementation, not exploration)
- Blocking Read on test output files or log files

## Technical Notes

### Hook Input Format
```json
{
  "tool_name": "Read",
  "tool_input": {
    "file_path": "/Users/theb/Documents/Windsurf/zenagent2/zenagent/agencheck/src/auth/routes.py"
  }
}
```

For Grep:
```json
{
  "tool_name": "Grep",
  "tool_input": {
    "pattern": "def login",
    "path": "/Users/theb/Documents/Windsurf/zenagent2/zenagent/agencheck/src/"
  }
}
```

### Hook Output Format
```json
{"decision": "block", "reason": "Serena is active. Use find_symbol instead of Read for .py files."}
```
or
```json
{"decision": "approve"}
```

### Serena Detection
Check if `.serena/project.yml` exists relative to `CLAUDE_PROJECT_DIR`. If it exists, Serena is configured for this project.

## Risks

| Risk | Mitigation |
|------|-----------|
| Over-blocking legitimate Read calls | Comprehensive whitelist + bypass mechanism |
| Performance regression from hook overhead | Fast path (~1ms) for non-code, file extension check only |
| Breaks existing workflows | Bypass env var + signal file for escape hatch |
| False positives on code-like extensions | Conservative extension list, err toward approval |

## Implementation Estimate

- **Complexity**: Low (2 Python scripts + settings.json update)
- **Files**: 3 new files, 1 modified
- **Testing**: Unit tests for decision logic + manual E2E validation
- **Estimated effort**: 1-2 hours
