---
title: "ConversationRuntime as CoBuilder Dispatch Adapter — Technical Spec"
description: "Abstract pipeline_runner.py worker dispatch behind an adapter interface, enabling claw-code's ConversationRuntime as an alternative to claude_code_sdk"
version: "1.0.0"
last-updated: 2026-04-02
status: draft
type: sd
grade: draft
prd_id: PRD-CLAWCODE-COBUILDER-001
---

# SD-CLAWCODE-COBUILDER-SDK-001: ConversationRuntime as Dispatch Adapter

**Epic**: 2 — Claw-Code ConversationRuntime as Dispatch Adapter (Phase 2 — Rust)
**PRD**: PRD-CLAWCODE-COBUILDER-001
**Depends On**: Epic 1 (SD-CLAWCODE-COBUILDER-TOOL-001), claw-code Rust branch merged to main

## 1. Overview

CoBuilder's `pipeline_runner.py` currently dispatches workers exclusively via `claude_code_sdk` (the `_dispatch_via_sdk()` method at line 2215). This SD introduces a `DispatchAdapter` abstraction that:

1. Extracts the existing SDK dispatch into a `ClaudeSDKAdapter` (zero behavioral change)
2. Defines a new `ClawCodeAdapter` that dispatches workers via claw-code's `ConversationRuntime`
3. Makes the adapter selectable per-node via `providers.yaml` or per-pipeline via CLI flag

This enables provider-agnostic worker dispatch — the same DOT pipeline can run workers on Claude SDK, claw-code's runtime, or future adapters.

## 2. Prerequisites

- **Hard dependency**: Claw-code Rust branch merged to main (provides `ConversationRuntime<C, T>`)
- Epic 1 completed (CoBuilder tools registered in claw-code)
- `pip install claw-code` or equivalent importable package
- Python bindings for claw-code's Rust runtime (via PyO3 or subprocess bridge)

## 3. Architecture

### 3.1 Current State (What We're Refactoring)

```
pipeline_runner.py
    _dispatch_via_sdk()          # L2215 — tightly coupled to claude_code_sdk
        ClaudeCodeOptions(...)   # Build options
        ClaudeSDKClient(...)     # Create client
        client.query(prompt)     # Send prompt
        client.receive_response  # Stream response
        → write signal file      # On completion
```

### 3.2 Target State

```
pipeline_runner.py
    DispatchAdapter.dispatch()   # Abstract interface
        |
        +-- ClaudeSDKAdapter     # Wraps existing _dispatch_via_sdk() exactly
        |       Uses claude_code_sdk.ClaudeSDKClient
        |
        +-- ClawCodeAdapter      # NEW — uses claw-code ConversationRuntime
        |       Maps tools → ToolExecutor
        |       Maps hooks → HookRunner
        |       Writes signal files on completion
        |
        +-- (future adapters)    # e.g., OpenAI Codex, Gemini, local LLMs
```

### 3.3 DispatchAdapter Interface

```python
# cobuilder/engine/adapters/__init__.py

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

@dataclass(frozen=True)
class DispatchConfig:
    """Configuration for a worker dispatch."""
    node_id: str
    worker_type: str
    prompt: str
    handler: str
    system_prompt: str
    allowed_tools: list[str]
    model: str
    cwd: str
    env: dict[str, str]
    signal_dir: Path
    max_turns: int = 300
    hooks: dict[str, Any] | None = None

@dataclass(frozen=True)
class DispatchMessage:
    """A message from a dispatched worker."""
    type: str  # "text", "tool_use", "tool_result", "usage", "stop"
    content: str
    metadata: dict[str, Any] | None = None

class DispatchAdapter(ABC):
    """Abstract interface for worker dispatch backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable adapter name."""
        ...

    @abstractmethod
    async def dispatch(self, config: DispatchConfig) -> AsyncIterator[DispatchMessage]:
        """Dispatch a worker and stream response messages.

        Yields DispatchMessage instances as the worker runs.
        The final message should have type="stop".

        The adapter is responsible for:
        - Starting the worker process/runtime
        - Streaming responses
        - NOT writing signal files (that's the runner's job for failure signals;
          the worker writes success signals)
        """
        ...

    @abstractmethod
    async def cancel(self) -> None:
        """Cancel the running dispatch."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this adapter's dependencies are installed."""
        ...
```

### 3.4 ClaudeSDKAdapter

Wraps the existing `_dispatch_via_sdk()` logic with **zero behavioral change**:

```python
# cobuilder/engine/adapters/claude_sdk_adapter.py

class ClaudeSDKAdapter(DispatchAdapter):
    name = "claude-sdk"

    def is_available(self) -> bool:
        try:
            import claude_code_sdk  # type: ignore
            return True
        except ImportError:
            return False

    async def dispatch(self, config: DispatchConfig) -> AsyncIterator[DispatchMessage]:
        import claude_code_sdk

        options = claude_code_sdk.ClaudeCodeOptions(
            system_prompt=config.system_prompt,
            allowed_tools=config.allowed_tools,
            permission_mode="bypassPermissions",
            model=config.model,
            max_turns=config.max_turns,
            cwd=config.cwd,
            env=config.env,
            hooks=config.hooks,
        )

        async with claude_code_sdk.ClaudeSDKClient(options=options) as client:
            await client.connect()
            await client.query(config.prompt)
            async for msg in client.receive_response():
                msg_type = type(msg).__name__
                if hasattr(msg, "content") and msg_type == "AssistantMessage":
                    for block in (msg.content if isinstance(msg.content, list) else []):
                        if hasattr(block, "text"):
                            yield DispatchMessage(type="text", content=block.text)
                        elif hasattr(block, "name"):
                            yield DispatchMessage(
                                type="tool_use",
                                content=block.name,
                                metadata={"id": block.id, "input": block.input},
                            )
                elif msg_type == "ResultMessage":
                    yield DispatchMessage(
                        type="stop",
                        content=getattr(msg, "text", ""),
                        metadata={"cost_usd": getattr(msg, "cost_usd", None)},
                    )

    async def cancel(self) -> None:
        # ClaudeSDKClient handles cancellation via context manager
        pass
```

### 3.5 ClawCodeAdapter

Maps CoBuilder's dispatch model to claw-code's `ConversationRuntime`:

```python
# cobuilder/engine/adapters/clawcode_adapter.py

class ClawCodeAdapter(DispatchAdapter):
    name = "clawcode"

    def is_available(self) -> bool:
        try:
            from claw_code.runtime import ConversationRuntime  # type: ignore
            return True
        except ImportError:
            return False

    async def dispatch(self, config: DispatchConfig) -> AsyncIterator[DispatchMessage]:
        from claw_code.runtime import ConversationRuntime, Session
        from claw_code.api import AnthropicClient  # or provider-agnostic client
        from claw_code.hooks import HookRunner, HookConfig

        # Map CoBuilder tools → claw-code ToolExecutor
        tool_executor = self._build_tool_executor(config.allowed_tools, config.cwd)

        # Map CoBuilder hooks → claw-code HookRunner
        hook_runner = self._build_hook_runner(config)

        # Build API client with model/key from config
        api_client = AnthropicClient(
            model=config.model,
            api_key=config.env.get("ANTHROPIC_API_KEY", ""),
            base_url=config.env.get("ANTHROPIC_BASE_URL"),
        )

        # Create runtime
        runtime = ConversationRuntime(
            session=Session.new(),
            api_client=api_client,
            tool_executor=tool_executor,
            permission_policy=PermissionPolicy.bypass_all(),
            system_prompt=[config.system_prompt],
        )

        # Run turn loop
        for turn in range(config.max_turns):
            prompt = config.prompt if turn == 0 else None
            if prompt is None:
                break

            summary = runtime.run_turn(prompt)

            # Yield assistant messages
            for msg in summary.assistant_messages:
                for block in msg.blocks:
                    if block.type == "text":
                        yield DispatchMessage(type="text", content=block.text)
                    elif block.type == "tool_use":
                        yield DispatchMessage(
                            type="tool_use", content=block.name,
                            metadata={"id": block.id, "input": block.input},
                        )

            # Yield tool results
            for msg in summary.tool_results:
                for block in msg.blocks:
                    yield DispatchMessage(
                        type="tool_result", content=block.output,
                        metadata={"tool_name": block.tool_name, "is_error": block.is_error},
                    )

            # Check for stop
            if not summary.tool_results:
                break

        yield DispatchMessage(type="stop", content="", metadata={
            "usage": {"turns": runtime.usage().turns()},
        })

    def _build_tool_executor(self, allowed_tools: list[str], cwd: str) -> "StaticToolExecutor":
        """Map CoBuilder allowed_tools list to claw-code ToolExecutor."""
        from claw_code.runtime import StaticToolExecutor

        executor = StaticToolExecutor()

        # Register standard tools that map to claw-code builtins
        tool_mapping = {
            "Bash": lambda input: _run_bash(input, cwd),
            "Read": lambda input: _read_file(input, cwd),
            "Write": lambda input: _write_file(input, cwd),
            "Edit": lambda input: _edit_file(input, cwd),
            "Glob": lambda input: _glob_search(input, cwd),
            "Grep": lambda input: _grep_search(input, cwd),
        }

        for tool_name in allowed_tools:
            if tool_name in tool_mapping:
                executor.register(tool_name, tool_mapping[tool_name])

        return executor

    def _build_hook_runner(self, config: DispatchConfig) -> "HookRunner":
        """Map CoBuilder hooks config to claw-code HookRunner."""
        from claw_code.hooks import HookRunner, HookConfig

        if not config.hooks:
            return HookRunner.default()

        # CoBuilder hooks use the same exit code protocol as claw-code:
        # 0 = allow, 2 = deny, other = warn
        # Direct mapping is possible
        pre_hooks = []
        post_hooks = []
        for matcher in config.hooks.get("pre_tool_use", []):
            pre_hooks.append(matcher.get("command", ""))
        for matcher in config.hooks.get("post_tool_use", []):
            post_hooks.append(matcher.get("command", ""))

        return HookRunner(HookConfig(pre_tool_use=pre_hooks, post_tool_use=post_hooks))
```

**Note**: The exact import paths (`claw_code.runtime`, `claw_code.api`, etc.) are speculative — they depend on how claw-code packages its Rust runtime for Python consumption (likely PyO3 bindings). The adapter will need adjustment when the actual package structure is known.

### 3.6 Adapter Selection

Selection via `providers.yaml` profile or CLI flag:

```yaml
# providers.yaml — add dispatch_adapter field to profiles
profiles:
  anthropic-smart:
    model: claude-sonnet-4-5-20250514
    api_key: $ANTHROPIC_API_KEY
    dispatch_adapter: claude-sdk  # default

  clawcode-local:
    model: claude-sonnet-4-5-20250514
    api_key: $ANTHROPIC_API_KEY
    dispatch_adapter: clawcode  # use claw-code runtime

  clawcode-glm5:
    model: glm-5
    api_key: $DASHSCOPE_API_KEY
    base_url: https://coding-intl.dashscope.aliyuncs.com/apps/anthropic
    dispatch_adapter: clawcode
```

Per-node selection in DOT:
```dot
impl_auth [
    shape=box
    handler="codergen"
    llm_profile="clawcode-local"  # Uses ClawCodeAdapter
    worker_type="backend-solutions-engineer"
];
```

CLI override:
```bash
python3 pipeline_runner.py --dot-file pipeline.dot --adapter clawcode
```

### 3.7 Integration into pipeline_runner.py

```python
# In PipelineRunner.__init__()
self._adapter_registry: dict[str, type[DispatchAdapter]] = {
    "claude-sdk": ClaudeSDKAdapter,
    "clawcode": ClawCodeAdapter,
}
self._default_adapter = os.environ.get("PIPELINE_DISPATCH_ADAPTER", "claude-sdk")

# In _dispatch_via_sdk() — rename to _dispatch_worker()
def _dispatch_worker(self, node_id: str, worker_type: str, prompt: str, ...):
    adapter_name = llm_config.dispatch_adapter or self._default_adapter
    adapter_cls = self._adapter_registry.get(adapter_name)
    if adapter_cls is None:
        log.error("Unknown dispatch adapter: %s", adapter_name)
        return

    adapter = adapter_cls()
    if not adapter.is_available():
        log.error("Adapter %s not available (missing dependencies)", adapter_name)
        return

    config = DispatchConfig(
        node_id=node_id, worker_type=worker_type, prompt=prompt,
        handler=handler, system_prompt=self._build_system_prompt(worker_type),
        allowed_tools=self._get_allowed_tools(handler),
        model=worker_model, cwd=effective_dir, env=clean_env,
        signal_dir=self.signal_dir, max_turns=_max_turns,
        hooks=_create_signal_stop_hook(self.signal_dir, node_id),
    )

    async def _run():
        messages = []
        async for msg in adapter.dispatch(config):
            messages.append(msg)
            # Existing logging/monitoring logic
        return messages

    asyncio.run(_run())
```

## 4. File Changes

### New Files (in cobuilder-harness)

| File | Purpose |
|------|---------|
| `cobuilder/engine/adapters/__init__.py` | Package init, adapter registry |
| `cobuilder/engine/adapters/base.py` | `DispatchAdapter` ABC, `DispatchConfig`, `DispatchMessage` |
| `cobuilder/engine/adapters/claude_sdk_adapter.py` | Existing SDK dispatch wrapped in adapter |
| `cobuilder/engine/adapters/clawcode_adapter.py` | Claw-code ConversationRuntime adapter |
| `tests/engine/adapters/test_claude_sdk_adapter.py` | Regression tests |
| `tests/engine/adapters/test_clawcode_adapter.py` | ClawCode adapter tests |
| `tests/engine/adapters/test_dispatch_config.py` | Config construction tests |

### Modified Files

| File | Change |
|------|--------|
| `cobuilder/engine/pipeline_runner.py` | Replace `_dispatch_via_sdk()` with `_dispatch_worker()` using adapter registry |
| `cobuilder/engine/providers.py` | Add `dispatch_adapter` field to `ResolvedLLMConfig` |
| `cobuilder/engine/providers.yaml` | Add `dispatch_adapter` to profile schema |

## 5. Migration Path

### Phase 2a: Extract adapter (no new functionality)

1. Create `adapters/` package with `DispatchAdapter` ABC
2. Extract `_dispatch_via_sdk()` into `ClaudeSDKAdapter` with zero behavioral change
3. Wire `pipeline_runner.py` to use adapter registry
4. Run all existing tests — must pass unchanged

### Phase 2b: Implement ClawCodeAdapter

1. Implement `ClawCodeAdapter` with tool mapping and hook bridge
2. Add `dispatch_adapter` field to `providers.yaml` profiles
3. Test with a simple 3-node pipeline using claw-code runtime
4. Validate signal file compatibility

### Phase 2c: Provider-agnostic validation

1. Run same pipeline through both adapters, compare signal output
2. Verify hooks fire correctly in both paths
3. Performance benchmarking (startup time, memory, throughput)

## 6. Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Claw-code Python bindings don't exist | Fallback: subprocess bridge to `claw` binary |
| Tool mapping is incomplete | Start with core 6 tools (Bash, Read, Write, Edit, Glob, Grep); expand iteratively |
| Async model mismatch (claw-code is sync) | Wrap sync calls in `asyncio.to_thread()` |
| Breaking changes when claw-code updates | Pin to specific claw-code version; adapter handles version detection |

## 7. Open Design Questions

1. **Python bindings or subprocess?** Does claw-code plan to publish PyO3 bindings, or should we shell out to the `claw` binary?
2. **Session persistence**: Should the ClawCodeAdapter persist sessions between pipeline nodes, or start fresh per node?
3. **Streaming**: claw-code's `run_turn()` is synchronous and returns a `TurnSummary`. Should we run it in a thread and yield messages periodically, or wait for a streaming API?

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| DispatchAdapter ABC | Not Started | Blocked on Epic 1 |
| ClaudeSDKAdapter | Not Started | Extraction from existing code |
| ClawCodeAdapter | Not Started | Blocked on Rust merge |
| providers.yaml schema | Not Started | |
| pipeline_runner.py refactor | Not Started | |
| Tests | Not Started | |
