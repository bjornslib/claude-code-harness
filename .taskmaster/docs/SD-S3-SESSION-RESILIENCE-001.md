---
sd_id: SD-S3-SESSION-RESILIENCE-001
prd_id: PRD-S3-SESSION-RESILIENCE-001
title: "Solution Design: Session Resilience & Merge Coordination"
status: draft
created: 2026-02-26
version: 0.1.0
author: solution-architect
---

# SD-S3-SESSION-RESILIENCE-001: Session Resilience & Merge Coordination

## Table of Contents

1. [Business Context](#1-business-context)
2. [Technical Architecture](#2-technical-architecture)
3. [Component Interaction Diagrams](#3-component-interaction-diagrams)
4. [Functional Decomposition](#4-functional-decomposition)
5. [Integration Points](#5-integration-points)
6. [Acceptance Criteria per Feature](#6-acceptance-criteria-per-feature)
7. [Risk Analysis](#7-risk-analysis)
8. [File Scope](#8-file-scope)

---

## 1. Business Context

### 1.1 Why Session Resilience Matters

The Guardian Architecture currently operates as a 4-layer pipeline execution system:

```
Layer 0: launch_guardian.py   — Terminal / System 3 bridge
Layer 1: guardian_agent.py    — SDK guardian driving pipeline execution
Layer 2: runner_agent.py      — SDK runner monitoring per-orchestrator tmux session
Layer 3: spawn_orchestrator.py — tmux-hosted Claude Code orchestrator
```

Three failure modes erode reliability at Layer 3:

**Crash-Induced Work Loss.** When an orchestrator tmux session dies (context exhaustion, OOM, network drop), `guardian_agent.py` already handles `ORCHESTRATOR_CRASHED` signals by re-spawning via `spawn_runner.py`. However, the new session receives only the original `--acceptance` text and `--prd` reference — it starts from scratch, re-reads the PRD, re-investigates files already examined, and potentially redoes hours of analysis. The existing `completion-promise` system records goals but not mid-session work state.

**No Single Source of Agent Truth.** The guardian tracks retries per node in an in-memory `dict` (see `build_system_prompt` in `guardian_agent.py`: "Track retries per node in memory"). System 3 must run `tmux ls` and cross-reference DOT pipeline state manually to answer "which agents are alive right now?" There is no persistent, machine-readable liveness record.

**Merge Conflict Cascades.** When multiple orchestrators complete work in parallel worktrees and each signals `VALIDATION_PASSED`, the current pipeline flow transitions nodes to `validated` and then... stops. There is no merge coordination. Manual merging in arbitrary order causes cascading rebase conflicts that require human intervention, negating the automation benefit.

**Silent Context Exhaustion.** The existing `PreCompact` hook in `.claude/settings.json` reloads MCP skills after context compression fires, but by the time `PreCompact` is triggered, the orchestrator is already under context pressure. There is no proactive detection before the cliff, no graceful handoff signal, and no pre-crash checkpoint.

### 1.2 Mapping to PRD Goals G1–G4

| Goal | Problem Addressed | Epics |
|------|-------------------|-------|
| G1: Zero work lost on session crash | Crash-induced work loss | Epic 1 (prerequisite), Epic 2 (hook files) |
| G2: Single source of truth for agent liveness | No agent registry | Epic 1 (identity registry) |
| G3: No merge conflicts from parallel orchestrators | Merge conflict cascades | Epic 1 (prerequisite), Epic 3 (merge queue) |
| G4: Graceful context cycling (stretch) | Silent context exhaustion | Epic 1 + 2 (prerequisites), Epic 4 |

### 1.3 Design Principle: Infrastructure Over Instructions

The prior approach (PRD-S3-GASTOWN-001) proposed injecting GUPP awareness into output style Markdown files so orchestrators would "remember" to write hook files. This was evaluated and rejected: LLM instructions are probabilistic, context-dependent, and silently skippable. The architecture chosen here enforces every behavior programmatically:

- `spawn_orchestrator.py` creates the identity file and hook file before the tmux session exists. The orchestrator cannot skip it.
- `runner_agent.py` updates the hook on phase transitions by writing to a file the orchestrator never touches.
- The merge queue is owned by the guardian process, not any orchestrator. Orchestrators signal `MERGE_READY` and move on; they cannot merge directly.
- Context cycling is triggered by runner observations, not by the orchestrator's self-awareness.

---

## 2. Technical Architecture

### 2.1 New Module Overview

Four new Python modules are introduced, each with a single responsibility:

| Module | Location | Responsibility |
|--------|----------|----------------|
| `identity_registry.py` | `.claude/scripts/attractor/` | CRUD for agent identity files in `.claude/state/identities/` |
| `hook_manager.py` | `.claude/scripts/attractor/` | CRUD for work-state hook files in `.claude/state/hooks/` |
| `merge_queue.py` | `.claude/scripts/attractor/` | Ordered merge queue in `.claude/state/merge-queue.json`; rebase/test/merge orchestration |
| `context_monitor.py` | `.claude/scripts/attractor/` | Context exhaustion symptom detection (Epic 4 stretch) |

These modules are pure Python with no external dependencies beyond the standard library and `signal_protocol.py`. They do not import from `guardian_agent.py` or `runner_agent.py` to prevent circular imports — those agents import the modules, not vice versa.

### 2.2 State Directory Layout

```
.claude/state/
├── identities/                     # Epic 1: one file per agent
│   ├── orchestrator-impl_auth.json
│   ├── runner-impl_auth.json
│   └── ...
├── hooks/                          # Epic 2: one file per orchestrator identity
│   ├── impl_auth.json
│   └── ...
└── merge-queue.json                # Epic 3: ordered list of pending merges
```

The `.claude/state/` directory is already git-ignored (confirmed in `.claude/.gitignore`). All state files survive process crashes on the same machine but are not persisted across machines. Cross-machine persistence is provided by the DOT pipeline checkpoints and git history.

### 2.3 Data Models

#### 2.3.1 Identity File Schema

File: `.claude/state/identities/{role}-{name}.json`

```json
{
  "schema_version": "1.0",
  "identity_name": "impl_auth",
  "role": "orchestrator",
  "session_id": "orch-impl_auth",
  "pid": 12345,
  "tmux_session": "orch-impl_auth",
  "node_id": "impl_auth",
  "pipeline_id": "PRD-AUTH-001",
  "bead_id": "AUTH-123",
  "worktree_path": "/path/to/repo/.claude/worktrees/impl_auth",
  "hook_path": ".claude/state/hooks/impl_auth.json",
  "created_at": "2026-02-26T10:00:00Z",
  "last_seen": "2026-02-26T10:05:00Z",
  "status": "active",
  "predecessor_id": null,
  "respawn_count": 0,
  "target_dir": "/path/to/target/repo"
}
```

**Status values:** `active` | `stale` | `crashed` | `terminated` | `merged`

The `predecessor_id` field contains the `identity_name` of the crashed session this one is resuming from, or `null` for first-launch sessions. The `hook_path` is relative to the `target_dir` so it is machine-portable.

#### 2.3.2 Hook File Schema

File: `.claude/state/hooks/{identity_name}.json`

```json
{
  "schema_version": "1.0",
  "identity_name": "impl_auth",
  "node_id": "impl_auth",
  "pipeline_id": "PRD-AUTH-001",
  "bead_id": "AUTH-123",
  "current_phase": "implementation",
  "work_summary": "Completed auth module skeleton; working on JWT token validation in auth/jwt.py",
  "last_checkpoint_at": "2026-02-26T10:04:30Z",
  "files_modified": [
    "src/auth/__init__.py",
    "src/auth/jwt.py",
    "tests/test_auth.py"
  ],
  "tests_status": "passing",
  "phase_history": [
    {"phase": "investigation", "entered_at": "2026-02-26T10:00:00Z", "exited_at": "2026-02-26T10:02:00Z"},
    {"phase": "planning", "entered_at": "2026-02-26T10:02:00Z", "exited_at": "2026-02-26T10:03:00Z"},
    {"phase": "implementation", "entered_at": "2026-02-26T10:03:00Z", "exited_at": null}
  ],
  "resumption_instructions": "Resume implementation of JWT token validation. auth/__init__.py and auth/jwt.py are scaffolded. Next: implement validate_token() in jwt.py then run tests.",
  "hook_status": "active"
}
```

**Phase values:** `investigation` | `planning` | `implementation` | `testing` | `completion`

**Hook status values:** `active` | `merged` | `abandoned`

The `resumption_instructions` field is populated by the runner on each phase transition update. It is a plain-English paragraph (not structured) so it can be injected directly into the wisdom prompt without transformation.

#### 2.3.3 Merge Queue Entry Schema

File: `.claude/state/merge-queue.json`

```json
{
  "schema_version": "1.0",
  "queue": [
    {
      "identity_name": "impl_auth",
      "branch": "worktree-impl_auth",
      "worktree_path": "/path/to/repo/.claude/worktrees/impl_auth",
      "pr_number": 42,
      "pipeline_id": "PRD-AUTH-001",
      "bead_id": "AUTH-123",
      "node_id": "impl_auth",
      "requested_at": "2026-02-26T10:10:00Z",
      "status": "pending",
      "merge_attempts": 0,
      "last_error": null
    }
  ],
  "processing": null,
  "last_updated": "2026-02-26T10:10:00Z"
}
```

**Queue entry status values:** `pending` | `processing` | `merged` | `conflict` | `failed`

The `processing` field at the top level holds the `identity_name` of the entry currently being processed, or `null` if the queue is idle. This prevents concurrent processing attempts.

### 2.4 Signal Protocol Extensions

Seven new signal types extend the existing `signal_protocol.py` constants. The existing signal naming convention `{timestamp}-{source}-{target}-{signal_type}.json` is preserved.

#### New Signal Type Definitions

**Epic 1 — Identity Signals:**

```
AGENT_REGISTERED    source=spawn  target=guardian  payload={identity_name, node_id, tmux_session}
AGENT_CRASHED       source=runner target=guardian  payload={identity_name, last_seen, last_output}
AGENT_TERMINATED    source=runner target=guardian  payload={identity_name, exit_reason}
```

**Epic 2 — Hook Signals:**

```
HOOK_UPDATED        source=runner target=guardian  payload={identity_name, phase, work_summary, hook_path}
```

**Epic 3 — Merge Signals:**

```
MERGE_READY         source=runner target=guardian  payload={identity_name, branch, pr_number, node_id}
MERGE_CONFLICT      source=guardian target=runner  payload={identity_name, conflicting_files, resolution_hints}
MERGE_COMPLETE      source=guardian target=runner  payload={identity_name, merged_at, commit_hash}
```

**Epic 4 — Context Signals:**

```
CONTEXT_WARNING     source=runner target=guardian  payload={identity_name, urgency, symptoms_detected}
HANDOFF_REQUESTED   source=guardian target=runner  payload={identity_name, reason, deadline_seconds}
HANDOFF_COMPLETE    source=runner target=guardian  payload={identity_name, hook_path, final_commit}
```

The signal payload schemas are validated at write time by a new `validate_payload(signal_type, payload)` function in `signal_protocol.py`. Unknown signal types raise `ValueError` immediately rather than writing a malformed signal file.

### 2.5 CLI Subcommand Additions

Two new top-level subcommands are added to `cli.py`:

```
python3 cli.py agents [--json] [--stale-only] [--status <status>]
python3 cli.py merge-queue list|add|process|status [--json]
```

These delegate to `agents_cmd.py` and `merge_queue_cmd.py` thin wrapper modules in the attractor directory, following the same dispatch pattern as the existing subcommands (`from agents_cmd import main as agents_main`).

---

## 3. Component Interaction Diagrams

### 3.1 Module Dependency Graph

```
launch_guardian.py
        │
        └── guardian_agent.py
                │
                ├── identity_registry.py  (Epic 1)
                ├── hook_manager.py       (Epic 2, reads on crash)
                ├── merge_queue.py        (Epic 3)
                ├── signal_protocol.py    (existing)
                └── spawn_orchestrator.py (spawns orchestrators)
                        │
                        ├── identity_registry.py  (creates identity + hook)
                        └── hook_manager.py       (creates initial hook)

runner_agent.py
        │
        ├── identity_registry.py  (updates last_seen)
        ├── hook_manager.py       (updates phase on transition)
        ├── signal_protocol.py    (writes HOOK_UPDATED, MERGE_READY, etc.)
        └── context_monitor.py    (Epic 4: detects exhaustion symptoms)

cli.py
        ├── agents_cmd.py         → identity_registry.list_all()
        └── merge_queue_cmd.py    → merge_queue.list_queue()
```

### 3.2 Sequence Diagram: Normal Spawn with Identity Registration

```
spawn_orchestrator.py                identity_registry.py    hook_manager.py     tmux
        │                                    │                    │               │
        │  create_identity(node_id, ...)      │                    │               │
        │────────────────────────────────────►│                    │               │
        │  identity_path                      │                    │               │
        │◄────────────────────────────────────│                    │               │
        │                                     │                    │               │
        │  create_hook(identity_name, ...)                         │               │
        │─────────────────────────────────────────────────────────►│               │
        │  hook_path                                               │               │
        │◄─────────────────────────────────────────────────────────│               │
        │                                     │                    │               │
        │  write_signal(AGENT_REGISTERED)     │                    │               │
        │────────────────── signal_protocol ──────────────────────►│               │
        │                                     │                    │               │
        │  tmux new-session + ccorch command  │                    │               │
        │────────────────────────────────────────────────────────────────────────►│
        │  {"status": "ok", "session": ...}                        │               │
        │◄────────────────────────────────────────────────────────────────────────│
```

### 3.3 Sequence Diagram: Crash Recovery Flow

```
runner_agent.py        signal_protocol.py    guardian_agent.py    identity_registry.py    hook_manager.py    spawn_orchestrator.py
        │                      │                    │                      │                    │                    │
        │  check_orchestrator_alive() → False        │                      │                    │                    │
        │                      │                    │                      │                    │                    │
        │  write_signal(AGENT_CRASHED,              │                      │                    │                    │
        │    {identity_name, last_output})           │                      │                    │                    │
        │─────────────────────►│                    │                      │                    │                    │
        │                      │  signal file       │                      │                    │                    │
        │                      │───────────────────►│                      │                    │                    │
        │                      │                    │ mark_crashed(name)   │                    │                    │
        │                      │                    │─────────────────────►│                    │                    │
        │                      │                    │                      │                    │                    │
        │                      │                    │ read_hook(name)                           │                    │
        │                      │                    │──────────────────────────────────────────►│                    │
        │                      │                    │ {phase, work_summary, resumption_instructions}                │
        │                      │                    │◄──────────────────────────────────────────│                    │
        │                      │                    │                      │                    │                    │
        │                      │                    │ spawn_orchestrator(node, prd,             │                    │
        │                      │                    │   predecessor_id=name,                    │                    │
        │                      │                    │   wisdom_prompt=resumption_block)          │                    │
        │                      │                    │────────────────────────────────────────────────────────────►│
        │                      │                    │ {"status": "ok", "session": ...}           │                    │
        │                      │                    │◄────────────────────────────────────────────────────────────│
```

### 3.4 Sequence Diagram: Merge Queue Processing

```
runner_agent.py    signal_protocol.py    guardian_agent.py    merge_queue.py    git/gh
        │                  │                    │                   │              │
        │  [VALIDATION_PASSED received]         │                   │              │
        │                  │                    │                   │              │
        │  write_signal(MERGE_READY,            │                   │              │
        │    {branch, pr_number, node_id})       │                   │              │
        │─────────────────►│                    │                   │              │
        │                  │  signal file        │                   │              │
        │                  │───────────────────►│                   │              │
        │                  │                    │ enqueue(entry)     │              │
        │                  │                    │──────────────────►│              │
        │                  │                    │                   │              │
        │                  │                    │ process_next()    │              │
        │                  │                    │──────────────────►│              │
        │                  │                    │                   │ git rebase main
        │                  │                    │                   │─────────────►│
        │                  │                    │                   │ conflict?     │
        │                  │                    │                   │◄─────────────│
        │                  │                    │                   │              │
        │                  │                    │  [if conflict]     │              │
        │                  │                    │  write_signal(MERGE_CONFLICT,    │
        │                  │                    │    {files, hints})               │
        │                  │                    │──────────────────────────────────────────► (to runner)
        │                  │                    │                   │              │
        │                  │                    │  [if clean]        │              │
        │                  │                    │                   │ gh pr merge --squash
        │                  │                    │                   │─────────────►│
        │                  │                    │                   │ merged ✓      │
        │                  │                    │  write_signal(MERGE_COMPLETE,    │
        │                  │                    │    {commit_hash, merged_at})     │
        │                  │                    │──────────────────────────────────────────► (to runner)
```

### 3.5 Sequence Diagram: Proactive Context Cycling (Epic 4)

```
runner_agent.py    context_monitor.py    signal_protocol.py    guardian_agent.py    spawn_orchestrator.py
        │                  │                    │                    │                    │
        │  [monitoring loop iteration]          │                    │                    │
        │  detect_symptoms(tmux_output)         │                    │                    │
        │─────────────────►│                    │                    │                    │
        │  {urgency, symptoms}                  │                    │                    │
        │◄─────────────────│                    │                    │                    │
        │                  │                    │                    │                    │
        │  [if urgency=high]                    │                    │                    │
        │  write_signal(CONTEXT_WARNING,        │                    │                    │
        │    {urgency="high", symptoms})        │                    │                    │
        │────────────────────────────────────►  │                    │                    │
        │                  │                    │  signal file        │                    │
        │                  │                    │──────────────────►│                    │
        │                  │                    │                    │                    │
        │                  │                    │  write_signal(HANDOFF_REQUESTED,        │
        │                  │                    │    {deadline=60s}) │                    │
        │                  │                    │◄──────────────────│                    │
        │  HANDOFF_REQUESTED received           │                    │                    │
        │  send_to_orchestrator("GUARDIAN: Save and exit cleanly")   │                    │
        │                  │                    │                    │                    │
        │  [wait for HOOK_UPDATED or 60s timeout]                    │                    │
        │  write_signal(HOOK_UPDATED,           │                    │                    │
        │    {phase, work_summary})             │                    │                    │
        │────────────────────────────────────►  │                    │                    │
        │                  │                    │──────────────────►│                    │
        │                  │                    │                    │ kill tmux session   │
        │                  │                    │                    │ spawn_orchestrator( │
        │                  │                    │                    │   predecessor_id,   │
        │                  │                    │                    │   hook_context)     │
        │                  │                    │                    │───────────────────►│
```

---

## 4. Functional Decomposition

### 4.1 Epic 1: `identity_registry.py` (New File)

**Location:** `.claude/scripts/attractor/identity_registry.py`

All functions use atomic write (temp + rename) for file mutations. The `state_dir` parameter defaults to `.claude/state/identities/` resolved from the git root using the same `_find_git_root` pattern already in `signal_protocol.py`.

#### `create_identity(node_id, role, tmux_session, pipeline_id, bead_id, worktree_path, hook_path, target_dir, predecessor_id=None, state_dir=None) -> str`

- **Purpose:** Write a new identity JSON file to `state_dir/{role}-{node_id}.json`.
- **Inputs:** All identity schema fields. `predecessor_id` is `None` for first-launch sessions.
- **Outputs:** Absolute path to the written identity file.
- **Called by:** `spawn_orchestrator.py` immediately before `tmux new-session`.
- **Dependencies:** `_atomic_write()` (internal helper), `_resolve_state_dir()`.

#### `update_liveness(identity_name, role="orchestrator", state_dir=None) -> None`

- **Purpose:** Update `last_seen` field to current UTC timestamp. Called on a 60s cycle.
- **Inputs:** `identity_name` (e.g., `"impl_auth"`), optional `role` to form file path.
- **Outputs:** None. No-ops silently if the identity file does not exist (prevents runner crash on missing state).
- **Called by:** `runner_agent.py` monitoring loop every 60 seconds.
- **Dependencies:** `_atomic_write()`, `read_identity()`.

#### `mark_crashed(identity_name, state_dir=None) -> None`

- **Purpose:** Set `status` to `"crashed"` on the identity file.
- **Inputs:** `identity_name`.
- **Outputs:** None.
- **Called by:** `guardian_agent.py` when handling `AGENT_CRASHED` or `ORCHESTRATOR_CRASHED` signal.
- **Dependencies:** `_atomic_write()`, `read_identity()`.

#### `mark_terminated(identity_name, state_dir=None) -> None`

- **Purpose:** Set `status` to `"terminated"` on a clean exit.
- **Inputs:** `identity_name`.
- **Outputs:** None.
- **Called by:** `runner_agent.py` when `VALIDATION_PASSED` is received and runner exits normally.
- **Dependencies:** `_atomic_write()`, `read_identity()`.

#### `read_identity(identity_name, role="orchestrator", state_dir=None) -> dict`

- **Purpose:** Parse and return identity JSON. Raises `FileNotFoundError` if missing.
- **Inputs:** `identity_name`, `role`.
- **Outputs:** Parsed dict.
- **Called by:** `update_liveness`, `mark_crashed`, `mark_terminated`, `guardian_agent.py`, `cli.py agents`.

#### `list_all(state_dir=None) -> list[dict]`

- **Purpose:** Return all identity dicts in `state_dir`, sorted by `created_at` descending.
- **Inputs:** Optional `state_dir` override.
- **Outputs:** List of parsed identity dicts.
- **Called by:** `guardian_agent.py` stale-scan loop, `agents_cmd.py` CLI handler.

#### `find_stale(threshold_seconds=300, state_dir=None) -> list[dict]`

- **Purpose:** Return identities where `status == "active"` and `last_seen` is more than `threshold_seconds` ago.
- **Inputs:** `threshold_seconds` (default 300 = 5 minutes), `state_dir`.
- **Outputs:** List of stale identity dicts.
- **Called by:** `guardian_agent.py` monitoring cycle.

#### `_atomic_write(path, data) -> None` (private)

- **Purpose:** Write `data` dict as JSON to `path` using temp file + `os.rename` pattern.
- **Inputs:** `path` (final destination), `data` dict.
- **Outputs:** None. Calls `fh.flush()` and `os.fsync()` before rename (same pattern as `signal_protocol.write_signal`).

#### `_resolve_state_dir(state_dir) -> str` (private)

- **Purpose:** Resolve state directory using env var `IDENTITY_STATE_DIR`, then git root walk, then `~/.claude/state/identities/` fallback. Mirrors `_default_signals_dir()` in `signal_protocol.py`.

---

### 4.2 Epic 1: `spawn_orchestrator.py` Changes

**Location:** `.claude/scripts/attractor/spawn_orchestrator.py` (modify existing)

#### `main()` — add identity registration before tmux creation

After argument parsing and session name resolution, before `subprocess.run(tmux_cmd, ...)`:

```python
from identity_registry import create_identity
from hook_manager import create_hook
from signal_protocol import write_signal

identity_path = create_identity(
    node_id=args.node,
    role="orchestrator",
    tmux_session=session_name,
    pipeline_id=args.prd,
    bead_id=getattr(args, "bead_id", None) or "",
    worktree_path=os.path.join(work_dir, ".claude", "worktrees", args.node),
    hook_path=os.path.join(".claude", "state", "hooks", f"{args.node}.json"),
    target_dir=work_dir,
    predecessor_id=getattr(args, "predecessor_id", None),
)
hook_path = create_hook(
    identity_name=args.node,
    node_id=args.node,
    pipeline_id=args.prd,
    bead_id=getattr(args, "bead_id", None) or "",
)
write_signal("spawn", "guardian", "AGENT_REGISTERED",
    {"identity_name": args.node, "node_id": args.node, "tmux_session": session_name})
```

#### `respawn_orchestrator()` — add predecessor_id and wisdom_prompt support

Two new keyword parameters:
- `predecessor_id: str | None = None` — passed to `create_identity`.
- `wisdom_prompt: str | None = None` — if provided, replaces `prompt` parameter with the hook-enriched resumption text.

The wisdom prompt is constructed by `guardian_agent.py` and passed through `spawn_runner.py` → `spawn_orchestrator.py` as `--predecessor-id` and `--wisdom-prompt` CLI flags.

New CLI arguments added to `argparse`:
```
--predecessor-id  str  Identity name of the crashed session being resumed
--bead-id         str  Beads issue identifier (already planned, wiring here)
--wisdom-prompt   str  Hook-derived resumption instructions (multi-line, JSON-encoded)
```

---

### 4.3 Epic 1: `runner_agent.py` Changes

**Location:** `.claude/scripts/attractor/runner_agent.py` (modify existing)

#### `build_system_prompt()` — add liveness update instruction

Add one entry to the "Tools Available" section:

```
- python {scripts_dir}/update_liveness.py --identity {node_id}  # Update last_seen (every 60s)
```

Add one item to "Monitoring Loop" step 7 (after sleep):

```
7b. Update liveness: python {scripts_dir}/update_liveness.py --identity {node_id}
```

This delegates the liveness update to a thin CLI wrapper `update_liveness.py` (see Section 4.4) so the runner's Bash tool handles it without requiring `runner_agent.py` to directly import `identity_registry.py`.

#### After receiving `VALIDATION_PASSED`

Add `mark_terminated` call via new `terminate_identity.py` CLI wrapper before exiting.

---

### 4.4 Epic 1: CLI Wrappers (New Thin Scripts)

These are standalone scripts invoked by runner/guardian via Bash tool. They import `identity_registry.py` and exit with code 0 on success, 1 on error.

**`update_liveness.py`**: `--identity <name>` → calls `identity_registry.update_liveness()`.

**`terminate_identity.py`**: `--identity <name>` → calls `identity_registry.mark_terminated()`.

**`agents_cmd.py`**: Handles `cli.py agents` subcommand.
- `list_all()` → table output or `--json`.
- `--stale-only` → `find_stale()`.
- `--status <status>` → filter by status.
- `--json` → machine-readable output.

---

### 4.5 Epic 1: `guardian_agent.py` Changes

**Location:** `.claude/scripts/attractor/guardian_agent.py` (modify existing)

#### `build_system_prompt()` — add identity scan instruction

Add to Phase 3 signal handling, after `ORCHESTRATOR_CRASHED` block:

```
STALE_IDENTITY_SCAN (periodic, every monitoring cycle):
   - Scan for stale identities:
     python3 {scripts_dir}/cli.py agents --stale-only --json
   - For each stale identity with status "active":
     * Verify tmux session is actually dead: python3 {scripts_dir}/check_orchestrator_alive.py --session <tmux_session>
     * If dead and stale: mark crashed and decide whether to re-spawn based on retry count
```

---

### 4.6 Epic 2: `hook_manager.py` (New File)

**Location:** `.claude/scripts/attractor/hook_manager.py`

#### `create_hook(identity_name, node_id, pipeline_id, bead_id, state_dir=None) -> str`

- **Purpose:** Write initial hook file with `current_phase="investigation"` and empty `files_modified`.
- **Inputs:** Identity fields for cross-reference.
- **Outputs:** Absolute path to the written hook file.
- **Called by:** `spawn_orchestrator.py` immediately after `create_identity`.
- **Dependencies:** `_atomic_write()`.

#### `read_hook(identity_name, state_dir=None) -> dict`

- **Purpose:** Parse and return hook JSON. Raises `FileNotFoundError` if missing.
- **Called by:** `guardian_agent.py` on crash detection (to read resumption context).

#### `update_phase(identity_name, phase, work_summary, files_modified=None, tests_status=None, state_dir=None) -> None`

- **Purpose:** Atomically update `current_phase`, `work_summary`, `last_checkpoint_at`, and optionally `files_modified` and `tests_status`. Appends to `phase_history`.
- **Inputs:** `phase` must be one of the valid phase values. `files_modified` is a list of relative file paths.
- **Outputs:** None.
- **Called by:** `runner_agent.py` when phase transition is detected via tmux output analysis.
- **Dependencies:** `_atomic_write()`, `read_hook()`.

#### `update_resumption_instructions(identity_name, instructions, state_dir=None) -> None`

- **Purpose:** Update only the `resumption_instructions` field without touching phase or summary.
- **Called by:** `runner_agent.py` when it receives a significant git commit from the orchestrator (new files committed → runner updates the file list and instructions).

#### `mark_merged(identity_name, state_dir=None) -> None`

- **Purpose:** Set `hook_status` to `"merged"` after successful merge.
- **Called by:** `merge_queue.py` after `gh pr merge` succeeds.

#### Phase Detection in `runner_agent.py`

The runner uses tmux output analysis (already its core capability) to detect phase transitions. The following heuristics are added to `build_system_prompt()`:

```
## Hook Update Triggers (call python {scripts_dir}/update_hook_phase.py --identity {node_id} --phase <p> --summary "<s>")

Phase transition indicators:
- "investigation" → "planning": Orchestrator outputs "Now planning" / creates task list / "Here is my plan"
- "planning" → "implementation": Orchestrator starts editing files / delegates first implementation task
- "implementation" → "testing": Orchestrator runs tests / delegates to tdd-test-engineer
- "testing" → "completion": All tests pass / orchestrator outputs completion summary / git commit made

Update the hook within 30 seconds of detecting a phase transition.
```

A new thin CLI wrapper `update_hook_phase.py` is introduced:
- `--identity <name>` `--phase <phase>` `--summary <text>` `--files <json_list>` → calls `hook_manager.update_phase()`.

#### `build_system_prompt()` in `guardian_agent.py` — crash resumption

The `ORCHESTRATOR_CRASHED` handling block is extended:

```
ORCHESTRATOR_CRASHED:
   - [existing: check retry count]
   - [NEW] Read hook file: python3 {scripts_dir}/read_hook.py --identity <node_id>
   - [NEW] If hook exists, build wisdom prompt including:
     "You are a continuation of {predecessor_id}. Resume from phase: {phase}.
      Last known work: {work_summary}. Resumption instructions: {resumption_instructions}"
   - [existing: re-spawn runner] but pass --predecessor-id and --wisdom-prompt
```

A new thin CLI script `read_hook.py` returns hook JSON:
- `--identity <name>` `--json` → reads and prints hook file.

---

### 4.7 Epic 2: `signal_protocol.py` Changes

**Location:** `.claude/scripts/attractor/signal_protocol.py` (modify existing)

Add a `VALID_SIGNAL_TYPES` constant set and a `validate_payload(signal_type, payload)` function:

```python
VALID_SIGNAL_TYPES = {
    # Existing
    "NEEDS_REVIEW", "NEEDS_INPUT", "VIOLATION", "ORCHESTRATOR_STUCK",
    "ORCHESTRATOR_CRASHED", "NODE_COMPLETE", "VALIDATION_PASSED",
    "VALIDATION_FAILED", "INPUT_RESPONSE", "KILL_ORCHESTRATOR",
    "GUIDANCE", "VALIDATION_COMPLETE",
    # Epic 1
    "AGENT_REGISTERED", "AGENT_CRASHED", "AGENT_TERMINATED",
    # Epic 2
    "HOOK_UPDATED",
    # Epic 3
    "MERGE_READY", "MERGE_CONFLICT", "MERGE_COMPLETE",
    # Epic 4
    "CONTEXT_WARNING", "HANDOFF_REQUESTED", "HANDOFF_COMPLETE",
}
```

No changes to the existing `write_signal`, `read_signal`, `list_signals`, or `wait_for_signal` functions — they remain signature-compatible. The `VALID_SIGNAL_TYPES` set is purely informational (used by tests and documentation generation).

---

### 4.8 Epic 3: `merge_queue.py` (New File)

**Location:** `.claude/scripts/attractor/merge_queue.py`

#### `enqueue(identity_name, branch, worktree_path, pr_number, pipeline_id, bead_id, node_id, state_dir=None) -> int`

- **Purpose:** Append a new `pending` entry to `merge-queue.json`. Returns the queue position (1-indexed).
- **Inputs:** All merge queue entry fields.
- **Outputs:** Queue position integer.
- **Called by:** `guardian_agent.py` when `MERGE_READY` signal is received.
- **Race condition protection:** Uses a file-level lock (`fcntl.flock` or a `.lock` sentinel file on macOS) since multiple guardians could enqueue simultaneously.

#### `dequeue_next(state_dir=None) -> dict | None`

- **Purpose:** Atomically move the first `pending` entry to `processing` status. Returns the entry dict or `None` if queue is empty or already processing.
- **Implementation detail:** Sets `processing` at the top level of the JSON to the identity_name, preventing a second call from claiming the same entry before the first finishes.
- **Called by:** `merge_queue.process_next()` internal.

#### `process_next(repo_root, state_dir=None) -> dict`

- **Purpose:** Dequeue the next entry, run `rebase_and_test`, then either call `merge_branch` or escalate.
- **Inputs:** `repo_root` — the git repository root for subprocess calls.
- **Outputs:** Dict with `status` (`"merged"` | `"conflict"` | `"empty"` | `"error"`) and details.
- **Called by:** `guardian_agent.py` after enqueue (and again after conflict resolution `MERGE_READY` re-signal).

#### `rebase_and_test(entry, repo_root) -> dict`

- **Purpose:** Run `git fetch origin && git rebase origin/main` in the entry's worktree. If clean, run `pytest --co -q` (collection-only fast check) then full test suite. Returns `{"status": "clean" | "conflict", "conflicting_files": [], "test_result": ...}`.
- **Called by:** `process_next()`.
- **Important:** Uses `subprocess.run` with `cwd=entry["worktree_path"]`. All git operations are on the worktree branch, not main.

#### `merge_branch(entry, repo_root) -> dict`

- **Purpose:** Run `gh pr merge {pr_number} --squash --auto` if PR number exists, otherwise `git push origin {branch} && git checkout main && git merge --squash {branch}`. Returns `{"status": "merged", "commit_hash": ...}`.
- **Called by:** `process_next()` after clean rebase.
- **Post-merge:** Calls `mark_entry_merged(entry)` and `hook_manager.mark_merged(identity_name)`.

#### `mark_entry_merged(entry, state_dir=None) -> None`

- **Purpose:** Update the queue entry status to `"merged"` and clear `processing`.

#### `list_queue(state_dir=None) -> list[dict]`

- **Purpose:** Return all queue entries (all statuses), sorted by `requested_at`.
- **Called by:** `merge_queue_cmd.py` for `cli.py merge-queue list`.

#### `get_queue_status(state_dir=None) -> dict`

- **Purpose:** Return summary: `{pending_count, processing, merged_count, conflict_count}`.
- **Called by:** `merge_queue_cmd.py` for `cli.py merge-queue status`.

---

### 4.9 Epic 3: `guardian_agent.py` Changes (Merge Queue)

The `build_system_prompt()` function gains a new signal type section:

```
MERGE_READY (orchestrator completed and branch is ready to merge):
   - Enqueue the merge request:
     python3 {scripts_dir}/merge_queue_cmd.py add --identity <id> --branch <branch> \
       --pr <pr_number> --node <node_id>
   - Process the queue (sequential, blocks until done):
     python3 {scripts_dir}/merge_queue_cmd.py process --repo-root {target_dir}
   - If result is "merged":
     * Send MERGE_COMPLETE signal to runner
     * Transition node to "merged" in DOT pipeline
   - If result is "conflict":
     * Send MERGE_CONFLICT signal to runner with conflicting file list
     * Wait for new MERGE_READY after orchestrator resolves conflicts
   - If result is "empty":
     * No action needed
```

Orchestrators are explicitly instructed to NOT merge directly — they signal `MERGE_READY` after the runner signals `VALIDATION_PASSED` on their behalf.

---

### 4.10 Epic 4: `context_monitor.py` (New File)

**Location:** `.claude/scripts/attractor/context_monitor.py`

This module is consumed by `runner_agent.py`'s monitoring loop via a thin CLI wrapper `check_context.py`.

#### `detect_symptoms(tmux_output_lines, baseline_latency_ms=None) -> dict`

- **Purpose:** Analyze tmux output lines for context exhaustion symptoms.
- **Inputs:** List of recent output lines; optional baseline response latency for comparison.
- **Outputs:** `{"urgency": "none"|"low"|"medium"|"high", "symptoms": list[str]}`.
- **Symptom patterns (all text-based, no regex magic):**
  - Urgency `low`: Line contains "context" AND ("compress" OR "limit")
  - Urgency `medium`: `PreCompact` hook firing (visible as system message in tmux)
  - Urgency `high`: Multiple PreCompact events in same session, or orchestrator outputs "I'm running out of context"
- **Called by:** `check_context.py` CLI wrapper.

#### `build_wisdom_prompt_block(hook_data, predecessor_id) -> str`

- **Purpose:** Format hook data into a plain-English resumption block for injection into the wisdom prompt.
- **Inputs:** Hook dict from `hook_manager.read_hook()`, predecessor identity name.
- **Outputs:** Multi-line string suitable for appending to spawn_orchestrator wisdom prompt.
- **Example output:**
  ```
  CONTEXT CONTINUITY NOTICE:
  You are a continuation of session '{predecessor_id}'.
  Resume from phase: {current_phase}.
  Last known work: {work_summary}
  Resumption instructions: {resumption_instructions}
  Files modified so far: {files_modified}
  Tests status at last checkpoint: {tests_status}
  ```
- **Called by:** `guardian_agent.py` crash handler and context cycling handler.

---

## 5. Integration Points

### 5.1 `guardian_agent.py` System Prompt Changes

The `build_system_prompt()` function is extended in three places:

**In "Tools Available" section:**
```
### Identity & Hook Tools
- python3 {scripts_dir}/cli.py agents --stale-only --json         # Scan for dead agents
- python3 {scripts_dir}/read_hook.py --identity <name> --json     # Read crash state
- python3 {scripts_dir}/merge_queue_cmd.py list --json            # View merge queue
- python3 {scripts_dir}/merge_queue_cmd.py process --repo-root {target_dir}  # Process next merge
```

**In "Phase 3: Wait and Handle Signals":**
- Extend `ORCHESTRATOR_CRASHED` block with hook-read and wisdom-prompt re-spawn logic.
- Add new `MERGE_READY`, `CONTEXT_WARNING`, `HOOK_UPDATED` signal type handlers.

**After Phase 4 "Check Pipeline Progress":**
- Add periodic stale identity scan instruction (every monitoring cycle, before re-checking ready nodes).

The `build_system_prompt()` function signature does not change — all new context is injected from parameters already available (`scripts_dir`, `target_dir`).

### 5.2 `runner_agent.py` Monitoring Loop Changes

The `build_system_prompt()` function gains additions in three areas:

**In "Tools Available" section:**
```
- python3 {scripts_dir}/update_liveness.py --identity {node_id}   # Heartbeat (every 60s)
- python3 {scripts_dir}/update_hook_phase.py --identity {node_id} --phase <p> --summary "<s>"  # Phase update
- python3 {scripts_dir}/check_context.py --identity {node_id} --lines 200  # Context symptoms
- python3 {scripts_dir}/terminate_identity.py --identity {node_id}  # Clean exit
```

**In "Monitoring Loop":**
- Step 7b: `update_liveness.py` call every 60s (piggyback on existing check_interval sleep).
- Step 4b: After phase transition detected, call `update_hook_phase.py`.
- Step 4c: After each capture, call `check_context.py` and handle CONTEXT_WARNING signal if urgency >= medium.

**In "After Signaling" / "Completion" section:**
- On `VALIDATION_PASSED`: call `terminate_identity.py` before exiting.
- On `VALIDATION_PASSED` (Epic 3): write `MERGE_READY` signal before exiting.

### 5.3 `spawn_orchestrator.py` Pre-spawn and Post-spawn Hooks

**Pre-spawn (before `tmux new-session`):**
1. Call `identity_registry.create_identity(...)` — writes identity file.
2. Call `hook_manager.create_hook(...)` — writes initial hook file.
3. Write `AGENT_REGISTERED` signal.

**Post-spawn (after confirming session alive):**
- No additional changes. The existing `_tmux_send(session_name, prompt)` call is extended to include `wisdom_prompt` content if `--wisdom-prompt` flag is set.

**New CLI flags for re-spawn scenario:**
```
--predecessor-id <identity_name>    Link this session to a crashed predecessor
--wisdom-prompt <json_encoded_str>  Hook-derived resumption instructions to inject
```

When `--predecessor-id` is set, `create_identity()` receives `predecessor_id=args.predecessor_id`. The `wisdom_prompt` is appended to the initial tmux prompt after `/output-style orchestrator` with a 2-second pause.

### 5.4 `cli.py` Subcommand Registration

Two new branches in the `main()` dispatch function:

```python
elif command == "agents":
    from agents_cmd import main as agents_main
    agents_main()
elif command in ("merge-queue", "merge_queue"):
    from merge_queue_cmd import main as merge_queue_main
    merge_queue_main()
```

The docstring at the top of `cli.py` gains two new usage lines:
```
python3 cli.py agents [--json] [--stale-only] [--status <status>]
python3 cli.py merge-queue list|add|process|status [--json] [--repo-root <path>]
```

And two lines in the `Subcommands:` help block:
```
agents        List all registered agents with liveness status
merge-queue   Inspect and process the sequential merge queue
```

---

## 6. Acceptance Criteria per Feature

### 6.1 Epic 1: Agent Identity Registry

**AC-1.1: Identity file created at spawn time.**
- Test: Call `spawn_orchestrator.py --node test_node --prd PRD-TEST-001 --repo-root /tmp/test --dry-run` and verify that `.claude/state/identities/orchestrator-test_node.json` exists with correct `status: "active"` and non-null `created_at`.
- File: `.claude/scripts/attractor/tests/test_identity_registry.py`

**AC-1.2: `last_seen` updates every 60s.**
- Test: Call `update_liveness.py --identity test_node`, read identity file, verify `last_seen` changed within the last 5 seconds.
- File: `.claude/scripts/attractor/tests/test_identity_registry.py`

**AC-1.3: Stale identity detected within one monitoring cycle.**
- Test: Create identity file with `last_seen` set to 6 minutes ago, call `find_stale(threshold_seconds=300)`, verify the identity appears in results.
- File: `.claude/scripts/attractor/tests/test_identity_registry.py`

**AC-1.4: Re-spawned orchestrator has `predecessor_id`.**
- Test: Call `spawn_orchestrator.py --predecessor-id old_session_name`, verify new identity file has `predecessor_id: "old_session_name"`.
- File: `.claude/scripts/attractor/tests/test_spawn_orchestrator.py`

**AC-1.5: `cli.py agents --json` returns machine-readable output.**
- Test: Create two identity files, call `cli.py agents --json`, parse output as JSON array, verify both identities appear with expected fields.
- File: `.claude/scripts/attractor/tests/test_cli.py`

### 6.2 Epic 2: Persistent Work State Hook Files

**AC-2.1: Hook file created at spawn time with initial node scope.**
- Test: After `spawn_orchestrator.py` completes (dry-run equivalent), verify `.claude/state/hooks/{node_id}.json` exists with `current_phase: "investigation"` and correct `node_id`, `pipeline_id`.
- File: `.claude/scripts/attractor/tests/test_hook_manager.py`

**AC-2.2: Hook `work_phase` updates within 30s of orchestrator phase transition.**
- Test (integration): In a tmux session, simulate orchestrator output containing "Here is my plan". Runner detects transition and calls `update_hook_phase.py`. Verify hook file shows `current_phase: "planning"` within 30 seconds.
- File: `.claude/scripts/attractor/tests/test_hook_manager_integration.py`

**AC-2.3: Re-spawned session wisdom prompt includes hook context.**
- Test: Write a hook file with `current_phase: "implementation"` and `work_summary: "Working on JWT"`. Call `spawn_orchestrator.py --predecessor-id old_id --wisdom-prompt <encoded>`. Capture the tmux send-keys call and verify it contains "Resume from phase: implementation" and "Working on JWT".
- File: `.claude/scripts/attractor/tests/test_spawn_orchestrator.py`

**AC-2.4: Re-spawned session skips already-completed phases.**
- Test: Verify the wisdom prompt block contains `resumption_instructions` from the hook, which explicitly names the last incomplete step.
- File: `.claude/scripts/attractor/tests/test_context_monitor.py` (`build_wisdom_prompt_block` unit test)

**AC-2.5: Hook file is never corrupted under concurrent writes.**
- Test: Spawn 5 concurrent threads each calling `update_phase` with different phases. After all complete, verify the hook file is valid JSON and `current_phase` is one of the valid phase values.
- File: `.claude/scripts/attractor/tests/test_hook_manager.py`

### 6.3 Epic 3: Sequential Merge Queue

**AC-3.1: Two simultaneous `MERGE_READY` signals processed sequentially.**
- Test: Call `enqueue()` twice in rapid succession. Call `process_next()` in a loop. Verify only one entry has status `"processing"` at any point, and both end up `"merged"` in sequence.
- File: `.claude/scripts/attractor/tests/test_merge_queue.py`

**AC-3.2: Clean merge path: branch rebased, tests pass, merged, branch deleted.**
- Test (with git repo fixture): Create two worktrees with non-conflicting changes. Enqueue both. Process queue. Verify both branches merged to main with no conflict, worktree branches deleted.
- File: `.claude/scripts/attractor/tests/test_merge_queue_integration.py`

**AC-3.3: Conflict path: conflicting files identified and escalated.**
- Test (with git repo fixture): Create two worktrees modifying the same file. Enqueue second after first merges. Process second. Verify `MERGE_CONFLICT` signal written with correct `conflicting_files` list.
- File: `.claude/scripts/attractor/tests/test_merge_queue_integration.py`

**AC-3.4: `cli.py merge-queue list` shows queue state with ordering.**
- Test: Enqueue 3 entries at different timestamps. Call `cli.py merge-queue list --json`. Verify returned array has 3 entries sorted by `requested_at`.
- File: `.claude/scripts/attractor/tests/test_cli.py`

**AC-3.5: Zero direct merges to main.**
- Test (contract test): Verify `spawn_orchestrator.py`'s wisdom prompt does NOT contain the string "merge" or "gh pr merge". Verify `runner_agent.py` system prompt does NOT contain direct merge instructions.
- File: `.claude/scripts/attractor/tests/test_spawn_orchestrator.py`, `test_runner_agent.py`

### 6.4 Epic 4: Proactive Context Cycling

**AC-4.1: Runner detects PreCompact event and signals CONTEXT_WARNING.**
- Test: Call `detect_symptoms()` with output lines containing a PreCompact system message. Verify returned `urgency == "medium"` and `"PreCompact" in symptoms`.
- File: `.claude/scripts/attractor/tests/test_context_monitor.py`

**AC-4.2: Graceful handoff completes within 90s.**
- Test (integration, stubbed): Stub orchestrator to respond to "Save and exit" within 10s. Verify handoff sequence: HANDOFF_REQUESTED sent → hook updated → session killed → re-spawn called with hook context. Total wall time < 90s.
- File: `.claude/scripts/attractor/tests/test_context_monitor_integration.py`

**AC-4.3: Re-spawned session resumes from correct phase.**
- Test: Write hook with `current_phase: "testing"`. Trigger re-spawn with hook context. Verify wisdom prompt contains `"Resume from phase: testing"`.
- File: `.claude/scripts/attractor/tests/test_context_monitor.py`

**AC-4.4: Force-kill at 60s timeout.**
- Test: Stub orchestrator that never responds to "Save and exit". Verify that after 60s, `tmux kill-session` is called for the target session.
- File: `.claude/scripts/attractor/tests/test_runner_agent.py`

**AC-4.5: No data loss — all files committed before handoff.**
- Test (contract): Verify that the `HANDOFF_COMPLETE` signal is only sent by the runner after `HOOK_UPDATED` is received, which implies the orchestrator committed work.
- File: `.claude/scripts/attractor/tests/test_runner_agent.py`

---

## 7. Risk Analysis

### 7.1 Atomic Write Failure Modes

**Risk:** A crash between the `os.write()` and `os.rename()` calls in `_atomic_write()` leaves a `.tmp` file but no final file. The directory scan in `identity_registry.list_all()` sees no file rather than a corrupt one.

**Mitigation:**
- The `_atomic_write()` function calls `fh.flush()` and `os.fsync(fh.fileno())` before `os.rename()`, matching the pattern in `signal_protocol.write_signal`. This is the same approach already validated in production.
- On startup (e.g., in `guardian_agent.py` initialization), a cleanup pass removes any `.tmp` files older than 60 seconds: `[os.remove(f) for f in glob("*.tmp") if age(f) > 60]`.
- No consumer function ever reads `.tmp` files — `list_all()` only reads `.json` files.

**Risk:** On macOS (HFS+), `os.rename()` is atomic for files on the same volume. Across volumes it is not. The `.claude/state/` directory and its parent are always on the same volume (both are under the git repo root), so this is not a concern.

### 7.2 Race Conditions in Identity Registry

**Risk:** Two processes (e.g., guardian_agent and a manually-invoked CLI command) call `update_liveness()` simultaneously. The `read_identity()` → modify → `_atomic_write()` sequence is not inherently atomic.

**Mitigation:**
- `update_liveness()` only modifies the `last_seen` field. The last writer wins, and both writers are writing approximately the same timestamp. There is no data loss scenario — a 1-second-old `last_seen` vs a current one has no operational difference.
- For `mark_crashed()` and `mark_terminated()`, the guardian and runner are the sole callers respectively, and they operate in a handoff sequence (runner signals AGENT_CRASHED → guardian calls mark_crashed), so simultaneous calls are not expected in practice.
- If simultaneous mutation is ever needed, a `.lock` sentinel file approach (create `.lock`, check existence, remove `.lock`) will be added. This is intentionally deferred to avoid premature complexity.

**Risk:** `find_stale()` reports a false positive because the runner is temporarily slow to update `last_seen` (e.g., the runner is itself under load).

**Mitigation:**
- The 5-minute threshold (300s) is chosen to be conservative: the runner updates every 60s, so even 4 consecutive missed updates still keep `last_seen` within 4 minutes. Only a genuinely dead session would exceed 5 minutes.
- Guardian performs a 3-strike confirmation before treating a stale identity as crashed: "if stale and tmux session dead → crashed; if stale but tmux session alive → not yet crashed, log warning."
- This is documented in `find_stale()` docstring and the guardian system prompt.

### 7.3 Merge Queue Deadlock Scenarios

**Risk:** The `processing` field in `merge-queue.json` is set to an identity_name, but the guardian process dies while processing. On restart, the queue is stuck with `processing != null` and `dequeue_next()` returns `None` forever.

**Mitigation:**
- `dequeue_next()` checks the age of the `processing` entry. If the entry has been in `processing` status for more than 15 minutes (configurable), it resets `processing` to `null` and re-queues the entry as `pending`. This is a self-healing mechanism.
- `cli.py merge-queue status --json` shows the current `processing` identity and elapsed time, allowing manual intervention via `cli.py merge-queue reset --force`.

**Risk:** `rebase_and_test()` blocks indefinitely on a hanging test suite.

**Mitigation:**
- All `subprocess.run()` calls in `merge_queue.py` use `timeout=300` (5 minutes). A `subprocess.TimeoutExpired` exception is caught and the queue entry status is set to `"failed"` with `last_error="test_timeout"`. The guardian then signals `MERGE_CONFLICT` with the error included in `resolution_hints`.

**Risk:** Two guardian instances (e.g., parallel pipelines) both attempt to call `process_next()` simultaneously.

**Mitigation:**
- The `processing` field in `merge-queue.json` acts as a distributed semaphore. `dequeue_next()` only proceeds if `processing is null`. The atomic write ensures that only one writer can successfully set `processing` before the other reads the updated state.
- In the unlikely event of a TOCTOU gap (both see `processing=null` simultaneously), the last writer wins. The first writer's entry will be "stolen" and re-queued by the self-healing mechanism above.

### 7.4 Context Exhaustion Symptom Reliability

**Risk:** The PreCompact hook produces different output strings across Claude Code versions, causing `detect_symptoms()` to miss the event.

**Mitigation:**
- Multiple symptom sources are checked independently (not a single regex). If any one triggers, the urgency level is set. The system degrades gracefully: missing the PreCompact event means the context cycling is slower, not that it fails entirely.
- The pattern matching uses substring checks (`"context" in line and "compress" in line`) rather than exact matches, making it robust to minor formatting changes.

**Risk:** The orchestrator ignores the "Save and exit" instruction and continues working, leading to forced kill at 60s.

**Mitigation:**
- This is by design: the 60s timeout force-kill is the safety net. The forced kill is no worse than the current hard-crash scenario. The hook file contains the last checkpoint before the force-kill, so re-spawn still recovers more state than a cold start.

---

## 8. File Scope

### 8.1 New Files to Create

| File | Purpose | Estimated Lines |
|------|---------|-----------------|
| `.claude/scripts/attractor/identity_registry.py` | Identity CRUD: create, read, update_liveness, mark_crashed, mark_terminated, list_all, find_stale | ~220 |
| `.claude/scripts/attractor/hook_manager.py` | Hook CRUD: create, read, update_phase, update_resumption_instructions, mark_merged | ~180 |
| `.claude/scripts/attractor/merge_queue.py` | Queue management: enqueue, dequeue_next, process_next, rebase_and_test, merge_branch, mark_entry_merged, list_queue, get_queue_status | ~280 |
| `.claude/scripts/attractor/context_monitor.py` | Symptom detection: detect_symptoms, build_wisdom_prompt_block | ~120 |
| `.claude/scripts/attractor/update_liveness.py` | Thin CLI: calls identity_registry.update_liveness | ~30 |
| `.claude/scripts/attractor/terminate_identity.py` | Thin CLI: calls identity_registry.mark_terminated | ~30 |
| `.claude/scripts/attractor/update_hook_phase.py` | Thin CLI: calls hook_manager.update_phase | ~40 |
| `.claude/scripts/attractor/read_hook.py` | Thin CLI: reads and prints hook JSON | ~25 |
| `.claude/scripts/attractor/check_context.py` | Thin CLI: calls context_monitor.detect_symptoms on tmux capture | ~45 |
| `.claude/scripts/attractor/agents_cmd.py` | CLI subcommand handler for `cli.py agents` | ~80 |
| `.claude/scripts/attractor/merge_queue_cmd.py` | CLI subcommand handler for `cli.py merge-queue` | ~100 |
| `.claude/scripts/attractor/tests/test_identity_registry.py` | Unit tests for identity_registry.py | ~200 |
| `.claude/scripts/attractor/tests/test_hook_manager.py` | Unit tests for hook_manager.py | ~180 |
| `.claude/scripts/attractor/tests/test_merge_queue.py` | Unit tests for merge_queue.py | ~220 |
| `.claude/scripts/attractor/tests/test_context_monitor.py` | Unit tests for context_monitor.py | ~120 |
| `.claude/scripts/attractor/tests/test_hook_manager_integration.py` | Integration tests for phase detection | ~80 |
| `.claude/scripts/attractor/tests/test_merge_queue_integration.py` | Integration tests with git repo fixture | ~150 |
| `.claude/scripts/attractor/tests/test_context_monitor_integration.py` | Integration tests for handoff sequence | ~100 |

**Total new lines: approximately 2,200**

### 8.2 Existing Files to Modify

| File | Changes | Estimated Delta |
|------|---------|-----------------|
| `.claude/scripts/attractor/spawn_orchestrator.py` | Import identity_registry + hook_manager; call create_identity + create_hook + write_signal before tmux session; add --predecessor-id, --bead-id, --wisdom-prompt CLI args; extend respawn_orchestrator | +60 lines |
| `.claude/scripts/attractor/runner_agent.py` | Extend build_system_prompt with liveness update, hook update, context check, merge_ready instructions; add terminate_identity call on VALIDATION_PASSED | +40 lines |
| `.claude/scripts/attractor/guardian_agent.py` | Extend build_system_prompt with stale scan, hook read on crash, merge queue processing, CONTEXT_WARNING handling | +80 lines |
| `.claude/scripts/attractor/signal_protocol.py` | Add VALID_SIGNAL_TYPES set and validate_payload function | +30 lines |
| `.claude/scripts/attractor/cli.py` | Add agents and merge-queue dispatch branches; update docstring and help text | +15 lines |
| `.claude/scripts/attractor/tests/test_spawn_orchestrator.py` | Add tests for identity creation, predecessor_id, wisdom_prompt | +60 lines |
| `.claude/scripts/attractor/tests/test_runner_agent.py` | Add tests for liveness updates, hook phase updates, MERGE_READY signal | +60 lines |
| `.claude/scripts/attractor/tests/test_guardian_agent.py` | Add tests for stale scan, crash recovery with hook, merge queue handling | +80 lines |
| `.claude/scripts/attractor/tests/test_cli.py` | Add tests for agents and merge-queue subcommands | +60 lines |
| `.claude/scripts/attractor/tests/test_signal_protocol.py` | Add tests for VALID_SIGNAL_TYPES and validate_payload | +30 lines |

**Total modified lines: approximately +515 lines net additions**

### 8.3 State Directories to Create

These are created at runtime by the modules on first use (via `os.makedirs(exist_ok=True)`):

```
.claude/state/identities/     — created by identity_registry._resolve_state_dir
.claude/state/hooks/          — created by hook_manager._resolve_state_dir
```

The `.claude/state/merge-queue.json` file is created by `merge_queue.enqueue()` on first call if it does not exist.

### 8.4 Implementation Order Summary

Following the dependency chain from the PRD:

**Phase 1 (Epic 1, P0) — 2-3 days:**
1. `identity_registry.py` with full CRUD
2. `update_liveness.py`, `terminate_identity.py` CLI wrappers
3. `agents_cmd.py` and `cli.py agents` subcommand
4. `spawn_orchestrator.py` changes (create_identity + create_hook call stubs)
5. `runner_agent.py` liveness update instruction
6. `guardian_agent.py` stale scan instruction
7. Tests: `test_identity_registry.py`, `test_cli.py` (agents portion)

**Phase 2 (Epic 2, P0) — 2-3 days:**
1. `hook_manager.py` with full CRUD
2. `update_hook_phase.py`, `read_hook.py` CLI wrappers
3. `spawn_orchestrator.py` create_hook integration
4. `runner_agent.py` phase transition detection instruction
5. `guardian_agent.py` crash recovery with hook read + wisdom prompt
6. `signal_protocol.py` HOOK_UPDATED signal type
7. Tests: `test_hook_manager.py`, `test_hook_manager_integration.py`, `test_spawn_orchestrator.py` additions

**Phase 3 (Epic 3, P1) — 3-4 days, can start after Epic 1 complete:**
1. `merge_queue.py` with enqueue, dequeue, process_next, rebase_and_test, merge_branch
2. `merge_queue_cmd.py` and `cli.py merge-queue` subcommand
3. `guardian_agent.py` MERGE_READY signal handling
4. `runner_agent.py` MERGE_READY signal emission after VALIDATION_PASSED
5. `signal_protocol.py` MERGE_READY, MERGE_CONFLICT, MERGE_COMPLETE signal types
6. Tests: `test_merge_queue.py`, `test_merge_queue_integration.py`, `test_cli.py` additions

**Phase 4 (Epic 4, P1 stretch) — 3-4 days, after Epics 1+2:**
1. `context_monitor.py` with detect_symptoms and build_wisdom_prompt_block
2. `check_context.py` CLI wrapper
3. `runner_agent.py` context check in monitoring loop
4. `guardian_agent.py` CONTEXT_WARNING, HANDOFF_REQUESTED handling
5. `signal_protocol.py` context signal types
6. Tests: `test_context_monitor.py`, `test_context_monitor_integration.py`, `test_runner_agent.py` additions

---

*End of SD-S3-SESSION-RESILIENCE-001 v0.1.0*
