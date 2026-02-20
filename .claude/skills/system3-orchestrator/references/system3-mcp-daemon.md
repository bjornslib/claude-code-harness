---
title: "System3 Mcp Daemon"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# System 3 MCP Daemon Design

Architecture and implementation plan for System 3 as a persistent MCP-accessible process.

---

## Overview

System 3 runs as a persistent Python daemon that exposes MCP tools for other Claude Code sessions to communicate with. This enables inter-agent coordination where Claude Code sessions can query the meta-orchestrator for wisdom, spawn orchestrators, and report outcomes.

```
┌─────────────────────────────────────────────────────┐
│         SYSTEM 3 MCP DAEMON (Python process)        │
│         Running on: localhost:8889/mcp              │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─ Claude Agent SDK Core ──────────────────────┐   │
│  │ - ClaudeSDKClient for reflective thinking    │   │
│  │ - Uses system3-meta-orchestrator output style│   │
│  │ - Automatic context compaction               │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─ Hindsight Integration ──────────────────────┐   │
│  │ - Private bank: claude-code-system3          │   │
│  │ - Shared bank: claude-code-agencheck         │   │
│  │ - Process supervision via reflect(high)      │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─ MCP Tool Registry ───────────────────────────┐   │
│  │ - system3_reflect                             │   │
│  │ - system3_spawn_orchestrator                  │   │
│  │ - system3_status                              │   │
│  │ - system3_inject_guidance                     │   │
│  │ - system3_report_outcome                      │   │
│  │ - system3_capability_check                    │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─ Idle Work Engine ────────────────────────────┐   │
│  │ - Continuous reflection cycle (30s intervals) │   │
│  │ - Pattern consolidation & validation          │   │
│  │ - Capability assessment updates               │   │
│  │ - Orchestrator health monitoring              │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘
         ↑                    ↑                    ↑
         │                    │                    │
    Claude Code         Claude Code         Spawned
    Session A          Session B          Orchestrators
```

---

## Architecture

### Two-Agent Pattern (Anthropic Proven)

Following Anthropic's "Effective Harnesses for Long-Running Agents" pattern:

```
SYSTEM 3 (Manager - Long-lived)
    │
    ├── Maintains meta-state across all sessions
    ├── Reflects on patterns and capabilities
    ├── Validates reasoning paths
    └── Guides spawned orchestrators
        │
        ├─→ ORCHESTRATOR A (Executor - Short-lived)
        │   └── Implements work in worktree
        │   └── Reports progress via MCP
        │
        ├─→ ORCHESTRATOR B (Executor - Short-lived)
        │   └── Implements work in worktree
        │   └── Reports progress via MCP
        │
        └─→ ORCHESTRATOR N...
```

### Transport: Streamable HTTP

Modern MCP standard (SSE deprecated March 2025):
- Runs on dedicated port (e.g., 8889)
- Supports long-running operations
- Multiple clients can connect simultaneously
- Stateless requests, stateful server

---

## MCP Tool Definitions

### 1. system3_reflect

Query System 3 for wisdom using reflective thinking.

```python
@app.tool()
async def system3_reflect(
    query: str,
    context: str = "",
    budget: Literal["low", "mid", "high"] = "mid"
) -> dict:
    """
    Query System 3 meta-orchestrator for wisdom.

    Args:
        query: Question or topic to reflect on
        context: Optional context (current work, initiative name)
        budget: Reflection depth (low=fast, high=thorough)

    Returns:
        {
            "reflection": "...",
            "patterns": [...],
            "anti_patterns": [...],
            "capability_notes": "...",
            "confidence": 0.85
        }
    """
```

### 2. system3_spawn_orchestrator

Spawn a new orchestrator in a worktree with wisdom injection.

```python
@app.tool()
async def system3_spawn_orchestrator(
    initiative: str,
    domain: str,
    goal: str,
    context: str = ""
) -> dict:
    """
    Spawn a new orchestrator in an isolated worktree.

    Args:
        initiative: Name for the initiative (used for worktree)
        domain: Domain of work (auth, api, ui, etc.)
        goal: High-level goal description
        context: Optional additional context

    Returns:
        {
            "session_name": "orch-{initiative}",
            "worktree": "trees/{initiative}/agencheck",
            "wisdom_injected": "...",
            "status": "spawned"
        }
    """
```

### 3. system3_status

Get status of all orchestrators and System 3 health.

```python
@app.tool()
async def system3_status() -> dict:
    """
    Get System 3 and orchestrator status.

    Returns:
        {
            "system3": {
                "uptime": "2h 15m",
                "last_reflection": "2025-12-29T10:30:00Z",
                "patterns_validated": 47,
                "capabilities_updated": 12
            },
            "orchestrators": [
                {
                    "name": "orch-auth-epic",
                    "status": "active|blocked|complete",
                    "progress": "3/5 tasks",
                    "last_update": "5m ago"
                }
            ]
        }
    """
```

### 4. system3_inject_guidance

Send guidance to a running orchestrator.

```python
@app.tool()
async def system3_inject_guidance(
    initiative: str,
    message: str,
    priority: Literal["normal", "urgent"] = "normal"
) -> dict:
    """
    Inject guidance into a running orchestrator.

    Args:
        initiative: Target orchestrator name
        message: Guidance message to send
        priority: Message priority

    Returns:
        {
            "delivered": True,
            "session": "orch-{initiative}",
            "timestamp": "..."
        }
    """
```

### 5. system3_report_outcome

Report orchestrator outcome for learning.

```python
@app.tool()
async def system3_report_outcome(
    initiative: str,
    outcome: Literal["success", "partial", "failure"],
    reasoning_path: str,
    learnings: list[str],
    blockers: list[str] = []
) -> dict:
    """
    Report orchestrator completion for System 3 learning.

    Args:
        initiative: Orchestrator that completed
        outcome: Final outcome status
        reasoning_path: Key decisions and rationale
        learnings: What was learned
        blockers: Any blockers encountered

    Returns:
        {
            "validated": True|False,
            "pattern_stored": "anti-pattern"|"pattern"|None,
            "capability_updated": True|False,
            "confidence": 0.82
        }
    """
```

### 6. system3_capability_check

Check System 3's self-assessed capabilities.

```python
@app.tool()
async def system3_capability_check(
    capability: str = "",
    domain: str = ""
) -> dict:
    """
    Check System 3 capability assessment.

    Args:
        capability: Specific capability to check (or all if empty)
        domain: Domain filter

    Returns:
        {
            "capabilities": [
                {
                    "name": "authentication_implementation",
                    "confidence": 0.85,
                    "evidence": "3 successful initiatives",
                    "last_updated": "..."
                }
            ]
        }
    """
```

---

## Implementation Structure

### Directory Layout

```
system3-daemon/
├── pyproject.toml         # Dependencies: fastmcp, anthropic-sdk, httpx
├── system3/
│   ├── __init__.py
│   ├── main.py            # FastMCP app entry point
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── reflect.py     # system3_reflect implementation
│   │   ├── spawn.py       # system3_spawn_orchestrator
│   │   ├── status.py      # system3_status
│   │   ├── guidance.py    # system3_inject_guidance
│   │   ├── outcome.py     # system3_report_outcome
│   │   └── capability.py  # system3_capability_check
│   ├── hindsight/
│   │   ├── __init__.py
│   │   └── client.py      # Hindsight MCP client wrapper
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   └── manager.py     # Orchestrator lifecycle management
│   ├── idle/
│   │   ├── __init__.py
│   │   └── engine.py      # Idle work loop
│   └── config.py          # Configuration (ports, banks, etc.)
├── tests/
│   └── ...
└── README.md
```

### Core Components

#### 1. Main Entry Point

```python
# system3/main.py
from fastmcp import FastMCP
from system3.tools import reflect, spawn, status, guidance, outcome, capability
from system3.idle.engine import IdleEngine
import asyncio

app = FastMCP("system3-daemon", version="1.0.0")

# Register all tools
app.include_router(reflect.router)
app.include_router(spawn.router)
app.include_router(status.router)
app.include_router(guidance.router)
app.include_router(outcome.router)
app.include_router(capability.router)

@app.on_startup
async def startup():
    # Initialize Hindsight connections
    await hindsight.connect()

    # Start idle work engine
    idle_engine = IdleEngine()
    asyncio.create_task(idle_engine.run())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8889)
```

#### 2. Hindsight Client

```python
# system3/hindsight/client.py
import httpx

class HindsightClient:
    def __init__(self):
        self.private_bank = "claude-code-system3"
        self.shared_bank = "claude-code-agencheck"
        self.base_url = "http://localhost:8888/mcp"

    async def reflect(self, query: str, budget: str = "mid", bank: str = "private") -> dict:
        bank_id = self.private_bank if bank == "private" else self.shared_bank
        # Call Hindsight MCP reflect tool
        ...

    async def retain(self, content: str, context: str, bank: str = "private") -> dict:
        bank_id = self.private_bank if bank == "private" else self.shared_bank
        # Call Hindsight MCP retain tool
        ...

    async def recall(self, query: str, bank: str = "private") -> dict:
        # Call Hindsight MCP recall tool
        ...
```

#### 3. Idle Work Engine

```python
# system3/idle/engine.py
import asyncio
from datetime import datetime, timedelta

class IdleEngine:
    def __init__(self, interval_seconds: int = 30):
        self.interval = interval_seconds
        self.last_activity = datetime.now()
        self.running = True

    async def run(self):
        while self.running:
            await asyncio.sleep(self.interval)

            # Check if we've been idle
            if self._is_idle():
                await self._do_idle_work()

    def _is_idle(self) -> bool:
        return datetime.now() - self.last_activity > timedelta(seconds=60)

    async def _do_idle_work(self):
        # Priority stack:
        # 1. Cross-bank reflection
        await self._cross_bank_reflection()

        # 2. Pattern consolidation
        await self._consolidate_patterns()

        # 3. Capability assessment
        await self._update_capabilities()

        # 4. Orchestrator health check
        await self._check_orchestrators()

    async def _cross_bank_reflection(self):
        # Reflect on patterns from both banks
        ...

    async def _consolidate_patterns(self):
        # Merge similar patterns, prune stale ones
        ...

    async def _update_capabilities(self):
        # Update capability confidence based on outcomes
        ...

    async def _check_orchestrators(self):
        # Poll active orchestrators for health
        ...
```

---

## Claude Code Integration

### MCP Configuration

Add to Claude Code settings:

```json
// .claude/settings/mcp.json
{
  "mcpServers": {
    "system3": {
      "url": "http://localhost:8889/mcp",
      "description": "System 3 meta-orchestrator daemon"
    },
    "hindsight-shared": {
      "url": "http://localhost:8888/mcp/claude-code-agencheck/mcp",
      "description": "Shared Hindsight memory bank"
    }
  }
}
```

### Usage from Claude Code

```python
# Query System 3 for wisdom
wisdom = mcp__system3__reflect(
    query="What patterns apply to authentication features?",
    context="Starting new auth epic",
    budget="mid"
)

# Spawn orchestrator via System 3
result = mcp__system3__spawn_orchestrator(
    initiative="auth-epic-3",
    domain="authentication",
    goal="Implement OAuth2 with Google and GitHub"
)

# Report outcome when done
mcp__system3__report_outcome(
    initiative="auth-epic-3",
    outcome="success",
    reasoning_path="Used test-first approach, isolated token handling",
    learnings=["OAuth state requires server-side storage"]
)
```

---

## Startup Sequence

```bash
# 1. Start Hindsight (if not running)
hindsight serve --port 8888

# 2. Start System 3 daemon
cd system3-daemon
uvicorn system3.main:app --host localhost --port 8889

# 3. Verify connectivity
curl http://localhost:8889/health

# 4. Test MCP
curl -X POST http://localhost:8889/mcp \
  -H "Content-Type: application/json" \
  -d '{"tool": "system3_status", "arguments": {}}'
```

---

## Process Supervision Integration

System 3 validates reasoning paths before storing patterns:

```python
async def validate_and_store(self, outcome_data: dict) -> dict:
    # Query Hindsight with high budget for validation
    validation = await self.hindsight.reflect(
        query=f"""
        PROCESS SUPERVISION: Validate reasoning path

        Initiative: {outcome_data['initiative']}
        Outcome: {outcome_data['outcome']}
        Reasoning: {outcome_data['reasoning_path']}

        VALIDATION CRITERIA:
        1. Was the goal clearly defined?
        2. Were steps logically sequenced?
        3. Were decisions justified?
        4. Were risks considered?
        5. Was outcome verified?

        VERDICT: VALID or INVALID
        CONFIDENCE: 0.0 to 1.0
        """,
        budget="high",
        bank="private"
    )

    # Parse validation result
    if "VALID" in validation and self._extract_confidence(validation) > 0.7:
        await self.hindsight.retain(
            content=self._format_pattern(outcome_data, validation),
            context="system3-patterns",
            bank="private"
        )
        return {"validated": True, "pattern_stored": "pattern"}
    else:
        await self.hindsight.retain(
            content=self._format_anti_pattern(outcome_data, validation),
            context="system3-anti-patterns",
            bank="private"
        )
        return {"validated": False, "pattern_stored": "anti-pattern"}
```

---

## Dependencies

```toml
# pyproject.toml
[project]
name = "system3-daemon"
version = "1.0.0"
dependencies = [
    "fastmcp>=0.5.0",
    "anthropic>=0.40.0",
    "httpx>=0.27.0",
    "uvicorn>=0.30.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]
```

---

## Next Steps

1. **Create project scaffold**: Initialize Python project with FastMCP
2. **Implement Hindsight client**: Wrap existing MCP calls
3. **Implement tools**: Start with reflect and spawn
4. **Add idle engine**: Background reflection loop
5. **Test integration**: Verify Claude Code can call tools
6. **Iterate**: Add remaining tools and refine

---

## References

- [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [MCP Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [Anthropic Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
