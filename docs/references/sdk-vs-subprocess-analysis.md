# SDK vs Subprocess: Worker-Spawning Architecture Analysis

**Date**: 2026-03-03
**Scope**: Attractor pipeline worker spawning — Claude Agent SDK vs `subprocess.Popen(['claude', '--print', ...])`
**Status**: Decision document for Epic 1 implementation

---

## 1. Current SDK API

The Python package is `claude-agent-sdk`, installed via `pip install claude-agent-sdk`. The import path is `claude_agent_sdk`. There is **no separate `claude_code_sdk` package** — that naming was from earlier pre-release documentation.

### `query()` function

The primary entry point is an async generator function:

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(prompt="Implement the auth module", options=options):
    if isinstance(message, ResultMessage):
        print(message.result)
```

Each `query()` call is a **fresh session** — no memory of previous calls. The function yields messages as they arrive and returns when the agent loop completes.

### `ClaudeAgentOptions` — Full Dataclass

```python
@dataclass
class ClaudeAgentOptions:
    # Tool control
    tools: list[str] | ToolsPreset | None = None
    allowed_tools: list[str] = field(default_factory=list)
    disallowed_tools: list[str] = field(default_factory=list)

    # Identity / persona
    system_prompt: str | SystemPromptPreset | None = None

    # Environment isolation (CRITICAL for worker spawning)
    setting_sources: list[SettingSource] | None = None
    # SettingSource = Literal["user", "project", "local"]
    # Default (None) = load NO filesystem settings at all

    # MCP servers
    mcp_servers: dict[str, McpServerConfig] | str | Path = field(default_factory=dict)

    # Permissions
    permission_mode: PermissionMode | None = None

    # Conversation
    continue_conversation: bool = False
    resume: str | None = None
    max_turns: int | None = None

    # Model
    model: str | None = None
    fallback_model: str | None = None

    # Cost control
    max_budget_usd: float | None = None

    # Working directory
    cwd: str | Path | None = None

    # Subprocess environment
    env: dict[str, str] = field(default_factory=dict)

    # CLI path override
    cli_path: str | Path | None = None

    # Streaming
    include_partial_messages: bool = False
    output_format: OutputFormat | None = None

    # Thinking
    max_thinking_tokens: int | None = None
    betas: list[SdkBeta] = field(default_factory=list)

    # Hooks (programmatic, not filesystem hooks)
    hooks: dict[HookEvent, list[HookMatcher]] | None = None

    # Subagents
    agents: dict[str, AgentDefinition] | None = None

    # Other
    add_dirs: list[str | Path] = field(default_factory=list)
    extra_args: dict[str, str | None] = field(default_factory=dict)
    settings: str | None = None
    permission_prompt_tool_name: str | None = None
    can_use_tool: CanUseTool | None = None
    user: str | None = None
    fork_session: bool = False
    max_buffer_size: int | None = None
    stderr: Callable[[str], None] | None = None
```

### Message types emitted by `query()`

| Type | Description | Key Fields |
|------|-------------|------------|
| `AssistantMessage` | Claude's response content | `content: list[TextBlock | ToolUseBlock]` |
| `ResultMessage` | Final completion signal | `stop_reason`, `result`, `session_id` |
| `StreamEvent` | Partial token chunks (when `include_partial_messages=True`) | `event: dict` with `type`, `delta` |

`ResultMessage.stop_reason` values: `end_turn`, `max_tokens`, `stop_sequence`, `refusal`, `tool_use`, `null`.

The SDK also defines typed errors: `CLINotFoundError`, `CLIConnectionError`, `ProcessError` (with `exit_code` and `stderr`).

### `setting_sources` — The Isolation Knob

This is the most important parameter for worker spawning:

```python
# Default (None): no filesystem settings loaded at all
# Workers get ZERO inherited config: no MCP servers, no hooks, no CLAUDE.md
options = ClaudeAgentOptions()  # setting_sources=None by default

# Load only project CLAUDE.md and shared project settings
options = ClaudeAgentOptions(setting_sources=["project"])

# Load all settings like interactive Claude Code does
options = ClaudeAgentOptions(setting_sources=["user", "project", "local"])
```

When `setting_sources=None` (the default): no `~/.claude/settings.json`, no `.claude/settings.json`, no MCP servers, no filesystem hooks, no `CLAUDE.md` files are loaded. This provides **clean-room isolation** that is impossible to achieve with raw subprocess spawning.

### Subagent definitions via `agents=`

Workers can be defined and their models overridden:

```python
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Grep", "Glob", "Task"],
    agents={
        "backend-solutions-engineer": AgentDefinition(
            description="Backend implementation specialist",
            prompt="You are a senior backend engineer...",
            tools=["Read", "Write", "Edit", "Bash"],
            model="sonnet",
        )
    }
)
```

---

## 2. Subprocess Pattern — Current State

### Documented headless pattern

```bash
claude -p "your prompt" --output-format stream-json --verbose --include-partial-messages
```

The `-p` / `--print` flag activates headless mode. Output is newline-delimited JSON objects.

### Official CLI flags for headless mode

These are **officially documented** as of 2026:

| Flag | Status | Purpose |
|------|--------|---------|
| `-p` / `--print` | Documented | Activate headless/non-interactive mode |
| `--output-format text\|json\|stream-json` | Documented | Output format |
| `--include-partial-messages` | Documented | Stream partial token chunks |
| `--verbose` | Documented | Include metadata in stream |
| `--model <alias>` | Documented | Model selection (sonnet, opus, haiku) |
| `--system-prompt <text>` | Documented | Replace entire system prompt |
| `--system-prompt-file <path>` | Documented | Replace system prompt from file |
| `--append-system-prompt <text>` | Documented | Augment default system prompt |
| `--append-system-prompt-file <path>` | Documented | Augment from file |
| `--max-turns <n>` | Documented (in agents spec) | Max agentic turns before stopping |
| `--agents <json>` | Documented | Define subagents as JSON |
| `--dangerously-skip-permissions` | Documented | Bypass permission prompts |

**Note on `--system-prompt` scope**: When `--system-prompt` is used, it **replaces the entire default Claude Code system prompt** — including all Claude Code instructions. This is only appropriate if you want to run Claude as a raw LLM, not as a coding agent with file editing tools.

### Current subprocess pattern used in our codebase

From `spawn_orchestrator.py`:

```python
claude_launch_cmd = (
    f"unset CLAUDECODE && env {env_vars} "
    f"claude --chrome --model claude-sonnet-4-6"
    f" --dangerously-skip-permissions --worktree {node_id}"
)
```

This is an **interactive** session launched via tmux, not a headless subprocess. For headless worker spawning, the pattern would be:

```python
import subprocess
import json

proc = subprocess.Popen(
    [
        "claude", "-p", prompt,
        "--output-format", "stream-json",
        "--model", "claude-sonnet-4-6",
        "--dangerously-skip-permissions",
        "--max-turns", "50",
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env={**os.environ, "CLAUDECODE": ""},  # Remove CLAUDECODE
    cwd=worktree_path,
)

for line in proc.stdout:
    event = json.loads(line)
    # Parse event manually
```

### Environment variable issues with subprocess

- `CLAUDECODE=1` is set by Claude Code in interactive sessions. Subprocesses inherit it. This causes the subprocess to think it is already inside a Claude Code session, triggering the "nested session" guard. **Fix**: `unset CLAUDECODE` before spawning (confirmed in GitHub issue #573).
- `DISABLE_AUTOUPDATER=1` should also be set to prevent auto-update checks from blocking the worker.
- All user-level MCP servers from `~/.claude/settings.json` are inherited by the subprocess because they are loaded at Claude startup based on the environment.

---

## 3. Side-by-Side Comparison

| Dimension | Claude Agent SDK (`claude_agent_sdk`) | Raw Subprocess (`claude -p --output-format stream-json`) |
|-----------|---------------------------------------|----------------------------------------------------------|
| **System prompt injection** | `ClaudeAgentOptions(system_prompt="You are a backend engineer...")` — first-class parameter, does NOT strip Claude Code's built-in tools | `--system-prompt "..."` — replaces the **entire** default system prompt including all Claude Code instructions. Use `--append-system-prompt` to augment instead. |
| **Environment isolation** | `setting_sources=None` (default) — zero filesystem config loaded. No user MCP servers, no hooks, no CLAUDE.md. Explicit `env={}` for subprocess env. | Inherits ALL user config by default: `~/.claude/settings.json`, MCP servers, hooks, plugins. Must manually strip with `env={...}` override. CLAUDECODE must be unset. |
| **Token overhead** | Minimal — only programmatically specified tools and MCP servers are loaded. No inheritance from user config. | Estimated +5K tokens per spawn from inherited user config (MCP tool defs, hooks, plugins). Our harness has 5+ MCP servers and 6 hooks. |
| **Process monitoring** | No direct PID access — SDK manages the subprocess internally. Use `ResultMessage.session_id` for correlation. Error surfaces as `ProcessError(exit_code, stderr)`. | Full PID access via `proc.pid`. Can `proc.poll()`, `proc.kill()`, set `proc.timeout`. Direct `returncode` on completion. |
| **Error handling** | Typed exceptions: `CLINotFoundError`, `CLIConnectionError`, `ProcessError`. Crash surfaces through the async generator. | Must parse stderr manually. Exit code 1 on any failure. No structured error envelope from the CLI itself. |
| **Streaming events** | `AssistantMessage`, `ResultMessage`, `StreamEvent` (with `include_partial_messages=True`). Typed Python objects. | Raw newline-delimited JSON — must `json.loads()` each line and dispatch on `type` field manually. Same information, more parsing code. |
| **Model selection** | `ClaudeAgentOptions(model="claude-sonnet-4-6")` or model aliases `"sonnet"`, `"haiku"`, `"opus"` | `--model claude-sonnet-4-6` or `--model sonnet` (aliases supported) |
| **Working directory control** | `ClaudeAgentOptions(cwd="/path/to/worktree")` — first-class parameter | `subprocess.Popen(..., cwd="/path/to/worktree")` or `--add-dir` flag. Both work. |
| **Max turns/iterations limit** | `ClaudeAgentOptions(max_turns=50)` — maps to `--max-turns` internally | `--max-turns 50` directly |
| **Async support** | Native — `async for message in query(...)`. Designed for asyncio. | Manual — wrap `proc.stdout.readline()` in `asyncio.to_thread()` or use `asyncio.subprocess.create_subprocess_exec`. |
| **MCP server configuration** | `ClaudeAgentOptions(mcp_servers={"my-server": {...}})` — programmatic, no JSON file needed | Must pre-configure MCP servers in `~/.claude/settings.json` or `.claude/settings.json` on disk |
| **Hooks (PreToolUse, PostToolUse)** | `ClaudeAgentOptions(hooks={...})` — programmatic Python callables, can block/allow tool calls | Must configure via `.claude/settings.json` on disk, or override with `CLAUDE_CODE_HOOKS=` env var (undocumented) |
| **Subagent spawning** | `ClaudeAgentOptions(agents={"worker": AgentDefinition(...)})` — define worker personas and their tool access inline | Requires separate `claude -p` invocations, orchestrated manually |
| **Session resumption** | `ClaudeAgentOptions(resume="<session_id>")` — continue a previous session | No equivalent in headless mode; must re-provide context in the prompt |
| **Permission mode** | `ClaudeAgentOptions(permission_mode="acceptEdits")` or `"bypassPermissions"` | `--dangerously-skip-permissions` (bypass only, no granular control) |
| **Stability / API maturity** | SDK is in active development; `setting_sources` was added in a breaking change from v0.0.x (which loaded all settings by default). Expect minor API changes. | CLI flags are stable and versioned with Claude Code releases. |
| **Dependency** | `pip install claude-agent-sdk` — Python package dependency, pin the version | Only requires `claude` CLI on PATH. No Python dependency. |

---

## 4. Recommendation

### Use the SDK immediately for Epic 1.

The environment isolation argument alone is decisive. Here is why:

**The isolation problem with subprocess is severe in our harness.** Our `.claude/settings.json` loads:
- 5+ MCP servers (hindsight, task-master-ai, context7, perplexity, brave-search, beads, serena, logfire)
- 6 lifecycle hooks (SessionStart, UserPromptSubmit, Stop, PreCompact, Notification)
- Enabled plugins (beads, frontend-design, code-review, double-shot-latte)

Every raw subprocess spawn inherits all of this. Estimated overhead: **+5K–12K tokens per worker spawn** just from tool definitions and hook machinery. Workers that should focus on `["Read", "Write", "Edit", "Bash"]` will instead have 20+ MCP tools in their context, bloating their system prompt and increasing API costs on every turn.

With the SDK:

```python
options = ClaudeAgentOptions(
    system_prompt="You are a backend implementation engineer...",
    allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    permission_mode="bypassPermissions",
    model="claude-sonnet-4-6",
    cwd=str(worktree_path),
    max_turns=50,
    setting_sources=None,  # explicit: load nothing from filesystem
    env={
        k: v for k, v in os.environ.items()
        if k not in ("CLAUDECODE",)  # strip CLAUDECODE
    },
)
```

This gives workers a **clean-room context**: only the tools they need, no MCP server overhead, no inherited hooks that could interfere with their Stop gate behavior, and precise cost control.

**Additional SDK advantages for Epic 1:**

1. **Typed error handling**: `ProcessError(exit_code, stderr)` vs parsing raw stderr. The runner can distinguish crash vs refusal vs max_turns exceeded with zero parsing code.

2. **Native async**: The runner agent (`runner_agent.py`) is already async-capable. `async for message in query(...)` integrates cleanly without `asyncio.to_thread` gymnastics.

3. **Subagent definitions**: When workers need to spawn their own sub-workers (e.g., a backend engineer spawning a test runner), this is a first-class SDK feature, not a manual subprocess chain.

4. **No CLAUDECODE handling**: The SDK manages `CLAUDECODE` unsetting internally. This is one fewer footgun.

**The one area where subprocess wins**: direct PID access for timeout enforcement via `proc.kill()`. With the SDK, you must use `asyncio.wait_for()` around the entire `query()` call and rely on `ProcessError` for crash detection. This is acceptable — `asyncio.wait_for(asyncio.gather(...), timeout=1800)` is idiomatic Python.

---

## 5. Migration Path (if subprocess-first is chosen)

If the team decides to start with subprocess for Epic 1 and migrate later, follow this migration ladder:

### Layer 0 — Abstract the interface now (do this regardless)

Create a thin `WorkerSpawner` protocol before writing any subprocess code:

```python
from typing import Protocol, AsyncIterable

class WorkerMessage:
    stop_reason: str
    result: str | None
    session_id: str

class WorkerSpawner(Protocol):
    async def spawn(
        self,
        prompt: str,
        system_prompt: str,
        model: str,
        cwd: str,
        max_turns: int,
        allowed_tools: list[str],
    ) -> AsyncIterable[WorkerMessage]: ...
```

Any code that calls `spawn_orchestrator` should use this interface, not call subprocess directly. This makes the SDK migration a single-file swap.

### Layer 1 — Subprocess implementation (v1)

```python
class SubprocessWorkerSpawner:
    async def spawn(self, prompt, system_prompt, model, cwd, max_turns, allowed_tools):
        clean_env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE",)}
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", prompt,
            "--output-format", "stream-json",
            "--model", model,
            "--append-system-prompt", system_prompt,
            "--max-turns", str(max_turns),
            "--dangerously-skip-permissions",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=clean_env,
        )
        async for line in proc.stdout:
            event = json.loads(line)
            if event.get("type") == "result":
                yield WorkerMessage(
                    stop_reason=event.get("stop_reason", ""),
                    result=event.get("result"),
                    session_id=event.get("session_id", ""),
                )
        await proc.wait()
```

**Problems to manage in this layer**:
- MCP token overhead: pass `--no-mcp` if that flag becomes available, or use a stripped settings file via `--settings /tmp/worker-settings.json`
- Hook interference: hooks inherited from `~/.claude/settings.json` will run in the subprocess. The Stop gate (`unified-stop-gate.sh`) will execute inside every worker — this could block workers from stopping normally.
- Timeout: wrap with `asyncio.wait_for(..., timeout=1800)`

### Layer 2 — SDK implementation (v2, migration target)

```python
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

class SDKWorkerSpawner:
    async def spawn(self, prompt, system_prompt, model, cwd, max_turns, allowed_tools):
        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            permission_mode="bypassPermissions",
            model=model,
            cwd=cwd,
            max_turns=max_turns,
            setting_sources=None,  # zero filesystem inheritance
            env={k: v for k, v in os.environ.items() if k not in ("CLAUDECODE",)},
        )
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                yield WorkerMessage(
                    stop_reason=message.stop_reason,
                    result=message.result,
                    session_id=message.session_id,
                )
```

### Migration checklist

When migrating from subprocess to SDK:

- [ ] Replace `SubprocessWorkerSpawner` with `SDKWorkerSpawner` in the spawner registry
- [ ] Remove manual CLAUDECODE env stripping (SDK handles it)
- [ ] Remove manual stream-json parsing code
- [ ] Remove `--append-system-prompt` subprocess flag handling (replace with `system_prompt=` param)
- [ ] Verify `max_turns` behavior is equivalent (it is — same underlying flag)
- [ ] Update error handling from `returncode` checks to `ProcessError` exception catches
- [ ] Remove any subprocess-level hook suppression workarounds
- [ ] Verify working directory behavior via `cwd=` param (identical to subprocess `cwd=`)
- [ ] Run cost comparison: token count with SDK `setting_sources=None` vs subprocess baseline

### Estimated migration effort

If the `WorkerSpawner` protocol is in place from day one: **2–4 hours** for the swap. Without the protocol abstraction: **1–2 days** of refactoring scattered subprocess calls.

---

## 6. Risk Assessment

| Risk | Subprocess | SDK |
|------|-----------|-----|
| Inherited user config bloating workers | HIGH — requires explicit workaround | LOW — `setting_sources=None` is the default |
| CLAUDECODE nested session guard | HIGH — must manually unset | LOW — SDK handles internally |
| Stop gate running inside workers | HIGH — hook is inherited via `~/.claude/settings.json` | NONE — hooks not loaded when `setting_sources=None` |
| API stability | LOW — CLI flags are stable | MEDIUM — SDK had breaking changes in v0.0.x→v0.1.x; pin version |
| Async complexity | MEDIUM — must use `asyncio.create_subprocess_exec` | LOW — native `async for` |
| Observability (PID, kill) | LOW — direct PID access | MEDIUM — must use `asyncio.wait_for` for timeouts |
| Dependency management | NONE — only `claude` on PATH | LOW — `pip install claude-agent-sdk`, pin version |

---

## 7. Concrete Recommendation for Epic 1

**Use `claude_agent_sdk` with `setting_sources=None` for all worker spawning in Epic 1.**

The key pattern for spawning a scoped worker:

```python
import asyncio
import os
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

WORKER_SYSTEM_PROMPTS = {
    "backend-solutions-engineer": (
        "You are a senior backend engineer specializing in Python, FastAPI, and Supabase. "
        "You implement features by reading existing code, understanding patterns, "
        "then writing clean, tested implementations. "
        "You do NOT orchestrate or delegate — you implement directly."
    ),
    "frontend-dev-expert": (
        "You are a senior frontend engineer specializing in React, Next.js, TypeScript, "
        "Zustand, and Tailwind CSS. You implement UI features directly."
    ),
    "tdd-test-engineer": (
        "You are a test engineer. You write comprehensive tests using Jest and Pytest. "
        "You do NOT implement features — you write tests only."
    ),
}

WORKER_TOOLS = {
    "backend-solutions-engineer": ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "MultiEdit"],
    "frontend-dev-expert": ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "MultiEdit"],
    "tdd-test-engineer": ["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
}

async def spawn_worker(
    prompt: str,
    worker_type: str,
    worktree_path: Path,
    max_turns: int = 50,
    timeout_seconds: int = 1800,
) -> dict:
    """Spawn a headless worker via the Claude Agent SDK.

    Returns a dict with stop_reason, result, session_id, and any error.
    """
    system_prompt = WORKER_SYSTEM_PROMPTS.get(
        worker_type,
        "You are a specialist agent. Implement the requested changes directly."
    )
    allowed_tools = WORKER_TOOLS.get(worker_type, ["Read", "Write", "Edit", "Bash"])

    clean_env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE",)}

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
        permission_mode="bypassPermissions",
        model="claude-sonnet-4-6",
        cwd=str(worktree_path),
        max_turns=max_turns,
        setting_sources=None,   # Clean room: no user config, no MCP, no hooks
        env=clean_env,
    )

    result = {
        "worker_type": worker_type,
        "worktree": str(worktree_path),
        "stop_reason": None,
        "result": None,
        "session_id": None,
        "error": None,
    }

    try:
        async for message in asyncio.wait_for(
            _collect_query(prompt, options),
            timeout=timeout_seconds,
        ):
            if isinstance(message, ResultMessage):
                result["stop_reason"] = message.stop_reason
                result["result"] = getattr(message, "result", None)
                result["session_id"] = getattr(message, "session_id", None)
    except asyncio.TimeoutError:
        result["error"] = f"Worker timed out after {timeout_seconds}s"
        result["stop_reason"] = "timeout"
    except Exception as exc:
        result["error"] = str(exc)
        result["stop_reason"] = "error"

    return result


async def _collect_query(prompt: str, options: ClaudeAgentOptions):
    """Thin async generator wrapper to make query() compatible with wait_for."""
    async for message in query(prompt=prompt, options=options):
        yield message
```

This replaces the current tmux-based `_tool_spawn_orchestrator` for headless worker spawning and eliminates the `CLAUDECODE`, hook inheritance, and token overhead problems in a single change.

---

*Research sources: Anthropic Agent SDK documentation (platform.claude.com/docs/en/agent-sdk), Claude Code documentation (code.claude.com), and direct examination of `.claude/scripts/attractor/runner_tools.py` and `spawn_orchestrator.py`.*
