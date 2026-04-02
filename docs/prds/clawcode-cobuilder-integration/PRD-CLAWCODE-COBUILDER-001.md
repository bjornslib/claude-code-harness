---
title: "CoBuilder Pipeline Integration into Claw-Code"
description: "Integrate CoBuilder's DOT pipeline engine into claw-code as native tools, enabling deterministic multi-agent orchestration within an open-source agent harness"
version: "1.0.0"
last-updated: 2026-04-02
status: draft
type: prd
grade: draft
prd_id: PRD-CLAWCODE-COBUILDER-001
---

# PRD-CLAWCODE-COBUILDER-001: CoBuilder Pipeline Integration into Claw-Code

## 1. Problem Statement

[Claw-code](https://github.com/ultraworkers/claw-code) is an open-source, clean-room reimplementation of the Claude Code agent harness (132K+ GitHub stars). It provides a solid agentic loop (session management, tool execution, hooks, MCP support) but **completely lacks multi-agent orchestration** — there is no mechanism for coordinating multiple workers on a complex initiative, tracking task dependencies, or running deterministic DAG-based pipelines.

CoBuilder's pipeline engine (`pipeline_runner.py`) solves exactly this problem: it parses DOT-defined directed acyclic graphs, dispatches AgentSDK workers per node, watches signal files for completion, and transitions nodes through a status chain — all at zero LLM cost for the graph traversal layer.

**The opportunity**: By integrating CoBuilder's pipeline engine into claw-code as native tools, we create the first open-source agent harness with built-in deterministic pipeline orchestration. This benefits both projects:

- **Claw-code gains**: Multi-agent orchestration, task tracking, pipeline-driven execution
- **CoBuilder gains**: A provider-agnostic frontend runtime (not locked to `claude_code_sdk`), Rust-native performance (when Rust merges), and community adoption via claw-code's 132K+ star base

## 2. Target Users

| User | Need |
|------|------|
| **Claw-code contributors** | Multi-agent orchestration without building from scratch |
| **CoBuilder users** | Alternative dispatch runtime beyond `claude_code_sdk` |
| **Agent harness researchers** | Reference implementation of deterministic DAG-based agent coordination |
| **Teams running multi-step automations** | Pipeline-driven task execution with signal-based completion tracking |

## 3. Current State Assessment

### Claw-code (main branch — Python)

The current `main` branch is a **Python porting scaffold**, not a full runtime:

- `src/tools.py` loads `tools_snapshot.json` (184 tool metadata entries) but `execute_tool()` returns stubs
- `src/runtime.py` has `PortRuntime` for prompt routing — not an actual agent conversation loop
- `src/tasks.py` has 3 hardcoded porting tasks — no `TaskTool`, `TeamTool`, or `AskUserQuestionTool`
- The Rust `dev/rust` branch has a real `ConversationRuntime<C, T>` with working hooks, sessions, and MCP, but is **not yet merged to main**

### CoBuilder Pipeline Engine

- `pipeline_runner.py`: Zero-LLM-cost Python state machine that parses DOT, dispatches workers, watches signal files
- `dispatch_worker.py`: Worker dispatch utilities, currently tightly coupled to `claude_code_sdk`
- Signal protocol: Workers write JSON to `{signal_dir}/{node_id}.json`; runner reads and transitions
- Status chain: `pending -> active -> impl_complete -> validated -> accepted`
- Provider resolution: 5-layer precedence from `providers.yaml`

### Key Gaps to Bridge

| Gap | Impact |
|-----|--------|
| claw-code has no real tool execution (Python side) | Must implement actual `execute()` for new tools |
| `pipeline_runner.py` dispatches only via `claude_code_sdk` | Must add an adapter layer for alternative runtimes |
| No shared signal protocol consumer in claw-code | Must implement signal file reading |
| claw-code repo clone-disabled (403) | Must fork or request access before implementation |

## 4. Success Criteria

1. A user can invoke `pipeline-run --dot-file pipeline.dot` from claw-code's REPL and have nodes dispatched to workers
2. Workers report completion via the existing signal file protocol
3. A `TaskTool` in claw-code wraps the beads CLI for issue tracking within pipelines
4. CoBuilder's `_dispatch_via_sdk()` can optionally dispatch via claw-code's `ConversationRuntime` instead of `claude_code_sdk`
5. All existing CoBuilder pipeline tests continue to pass (no regression)

## 5. Non-Goals

- Porting CoBuilder's full guardian/pilot pattern into claw-code (too complex for v1)
- Replacing claw-code's agentic loop (we add orchestration ON TOP of it)
- Supporting claw-code as a worker runtime before the Rust branch merges (Python stubs are insufficient)
- Contributing to claw-code's plugin execution layer (out of scope — we work within the tool system)

## 6. Constraints

- **Repo access**: claw-code's git clone returns 403. We need a fork to work in.
- **Rust merge timeline**: Epic 2 depends on the Rust `ConversationRuntime` being on main. If it doesn't merge, Epic 2 is deferred indefinitely.
- **Signal protocol compatibility**: Must maintain backward compatibility with existing CoBuilder signal files.
- **No proprietary code**: claw-code is a clean-room effort. Our contributions must not reference Claude Code internals.

## 7. Architecture Overview

```
claw-code REPL
    |
    |-- PipelineRunnerTool (NEW)
    |       |-- Invokes pipeline_runner.py --dot-file <path>
    |       |-- Reads signal files for status updates
    |       |-- Returns structured pipeline completion report
    |
    |-- PipelineCreateTool (NEW)
    |       |-- Wraps cobuilder pipeline create CLI
    |       |-- Generates DOT files from task descriptions
    |       |-- Validates topology before returning
    |
    |-- TaskTool (NEW)
    |       |-- Wraps beads CLI (bd create, bd ready, bd close)
    |       |-- Tracks work items within pipeline execution
    |       |-- Returns structured task status
    |
    pipeline_runner.py (EXISTING)
        |
        |-- DispatchAdapter (NEW interface)
        |       |-- ClaudeSDKAdapter (existing behavior, default)
        |       |-- ClawCodeAdapter (NEW — Epic 2)
        |               |-- Maps to ConversationRuntime<C, T>
        |               |-- Implements ToolExecutor trait for CoBuilder tools
        |               |-- Streams responses back as signal files
        |
        |-- Signal protocol (EXISTING, unchanged)
        |-- Checkpoint/resume (EXISTING, unchanged)
```

## 8. Epics

### Epic 1: CoBuilder Tools in Claw-Code (Phase 1 — Python)

**Goal**: Register CoBuilder's pipeline engine as real, executable tools in claw-code's Python workspace.

**Scope**:
- Implement `PipelineRunnerTool` in `src/tools.py` that shells out to `pipeline_runner.py`
- Implement `PipelineCreateTool` for DOT pipeline generation
- Implement `TaskTool` wrapping the beads CLI
- Add signal file reader for pipeline status reporting
- Integration tests covering the full tool-invoke → pipeline-run → signal-complete round-trip

**Acceptance Criteria**:
- AC-1 [code-analysis]: `PipelineRunnerTool` exists in claw-code's `src/tools.py` with real `execute()` (not stub)
- AC-2 [code-analysis]: `PipelineCreateTool` exists and generates valid DOT files (passes `cobuilder pipeline validate`)
- AC-3 [code-analysis]: `TaskTool` wraps `bd create`, `bd ready`, `bd close`, `bd show` commands
- AC-4 [api-call]: Running `python3 -m src.main exec-tool PipelineRunnerTool '{"dot_file": "test.dot"}'` invokes the pipeline
- AC-5 [unit-test]: Signal file reader correctly parses success, failed, and requeue signals
- AC-6 [code-analysis]: No references to Claude Code proprietary internals in contributed code

**Dependencies**: Fork of claw-code repo created and accessible

### Epic 2: Claw-Code ConversationRuntime as Dispatch Adapter (Phase 2 — Rust)

**Goal**: Replace `claude_code_sdk` dispatch in CoBuilder's pipeline runner with claw-code's `ConversationRuntime` as an alternative backend.

**Scope**:
- Define a `DispatchAdapter` interface in `pipeline_runner.py` abstracting worker dispatch
- Extract current `_dispatch_via_sdk()` into a `ClaudeSDKAdapter`
- Implement `ClawCodeAdapter` that maps to claw-code's `ConversationRuntime`
- Map CoBuilder tool definitions → claw-code `ToolExecutor` implementations
- Map CoBuilder hooks → claw-code `HookRunner` (exit code protocol is already compatible)
- Support provider-agnostic model selection via claw-code's API abstraction

**Acceptance Criteria**:
- AC-1 [code-analysis]: `DispatchAdapter` ABC defined with `dispatch()`, `stream_response()`, `get_status()` methods
- AC-2 [code-analysis]: `ClaudeSDKAdapter` wraps existing `_dispatch_via_sdk()` with zero behavioral change
- AC-3 [code-analysis]: `ClawCodeAdapter` instantiates claw-code's `ConversationRuntime` with proper tool/hook mapping
- AC-4 [unit-test]: Existing pipeline tests pass unchanged when using `ClaudeSDKAdapter` (regression-free)
- AC-5 [api-call]: A simple 3-node pipeline (start → codergen → finish) completes successfully via `ClawCodeAdapter`
- AC-6 [code-analysis]: Provider selection works via `providers.yaml` for both adapters
- AC-7 [unit-test]: Hook bridge correctly maps CoBuilder PreToolUse/PostToolUse to claw-code HookRunner

**Dependencies**: Claw-code Rust branch merged to main; Epic 1 completed

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Claw-code repo remains clone-disabled | Medium | Blocks all work | Contact maintainer; worst case, work from API-reconstructed fork |
| Rust branch never merges | Low-Medium | Blocks Epic 2 entirely | Epic 1 stands alone as valuable; Epic 2 is explicitly deferred |
| claw-code architecture changes significantly | Medium | Rework needed | Pin to a specific commit/tag; isolate integration behind adapter |
| Signal protocol incompatibility | Low | Data loss | Comprehensive signal parsing tests in Epic 1 |
| Community rejects contribution | Medium | Wasted effort | Open discussion issue before PR; align with project goals |

## 10. Open Questions

1. Should we contribute directly to `ultraworkers/claw-code` or maintain a fork with CoBuilder integration?
2. Is claw-code's Python workspace intended to become a real runtime, or will it remain a scaffold until Rust merges?
3. Should the `DispatchAdapter` interface live in CoBuilder or be contributed as a claw-code crate?

## Implementation Status

| Epic | Status | Notes |
|------|--------|-------|
| Epic 1: CoBuilder Tools in Claw-Code | Not Started | Blocked on repo access (fork needed) |
| Epic 2: ConversationRuntime Adapter | Not Started | Blocked on Rust merge + Epic 1 |
