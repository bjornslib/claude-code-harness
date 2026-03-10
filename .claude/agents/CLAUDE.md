---
title: "Project Guidelines for AI Workers"
status: active
type: guide
last_verified: 2026-03-10
grade: authoritative
---

# Project Guidelines for AI Workers

## Repository Purpose
This is a Claude Code harness setup repository that provides a complete configuration framework for multi-agent AI orchestration using Claude Code. It contains no application code—only configuration, skills, hooks, and orchestration tools.

## Key Patterns

### Investigation vs Implementation Boundary
- **Orchestrators**: Use Read/Grep/Glob to investigate, analyze, plan, and create task structures
- **Workers**: Implement features using Edit/Write
- **Never use Edit/Write directly for implementation in orchestrator mode**

### 4-Phase Orchestration Pattern
1. **Ideation** - Brainstorm, research, parallel-solutioning
2. **Planning** - PRD → Task Master → Beads hierarchy
3. **Execution** - Delegate to workers, monitor progress
4. **Validation** - 3-level testing (Unit + API + E2E)

### Validation Agent Enforcement
All task closures must go through validation-agent with --mode=implementation.

## Environment Variables
- `CLAUDE_SESSION_ID`: Unique session identifier
- `CLAUDE_OUTPUT_STYLE`: Active output style (system3/orchestrator)
- `CLAUDE_PROJECT_DIR`: Project root directory
- `ANTHROPIC_API_KEY`: API authentication
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`: Enable native Agent Teams (1)
- `CLAUDE_CODE_TASK_LIST_ID`: Shared task list ID for team coordination

## Critical MCP Tools Patterns
Use ToolSearch to discover available tools before using them. MCP tools are deferred and their schemas are not in the agent's context until loaded via ToolSearch.