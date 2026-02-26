# PRD-S3-RESILIENCE-GAPS-001: Session Resilience — SDK Integration Gaps

**Status**: Active
**Author**: System 3 Guardian
**Date**: 2026-02-27
**Priority**: P1
**Dependencies**: PRD-S3-SESSION-RESILIENCE-001 (Epics 1-3 merged), PRD-S3-GUARDIAN-001 (4-layer architecture)
**prd_id**: PRD-S3-RESILIENCE-GAPS-001

---

## 1. Problem Statement

PRD-S3-SESSION-RESILIENCE-001 delivered three standalone modules — identity_registry.py, hook_manager.py, and merge_queue.py — with 132 passing unit tests. However, these modules are not yet fully wired into the SDK-based guardian/runner/orchestrator chain. Specifically:

1. **spawn_runner.py is a placeholder** — writes a JSON state file but never launches runner_agent.py
2. **identity_registry.py has no CLI mode** — system prompts tell Claude to run `python3 identity_registry.py --find-stale` but no `__main__` block exists
3. **hook_manager lifecycle is never invoked** — `create_hook()` is called on startup but `update_phase()`, `update_resumption_instructions()`, `mark_merged()` are never called
4. **merge_queue is prompt-text only** — enqueue/process_next appear in system prompt strings but the Python wrapper never calls them directly
5. **launch_guardian.py has no identity tracking** — Layer 0 crashes leave no audit trail
6. **E2E test is a skip placeholder** — `test_e2e_3layer.py` has only dry-run tests; the live test body is commented out

These gaps mean the 4-layer chain cannot be run end-to-end with session resilience features active.

## 2. Goals

1. Make the 4-layer chain runnable end-to-end with all resilience modules active
2. Enable identity tracking at all layers (0-3)
3. Enable hook phase transitions during orchestrator lifecycle
4. Enable merge queue integration at guardian level
5. Provide a working E2E test that validates the full signal chain with resilience

## 3. Non-Goals

- Epic 4 (Proactive Context Cycling) — deferred to future PRD
- Production-grade error recovery — this PRD focuses on wiring, not edge case handling
- Performance optimization — correctness first

## 4. Epic Breakdown

### Epic 1: CLI Mode for Identity Registry (F002/F005 gaps)

Add `if __name__ == "__main__"` CLI block to `identity_registry.py` with argparse subcommands:
- `--create-identity` with role, name, session-id, worktree flags
- `--update-liveness` with role, name flags
- `--find-stale` with --timeout flag
- `--mark-crashed` / `--mark-terminated` with role, name flags
- `--list` with optional `--json` and `--stale-only` flags

**Acceptance Criteria**:
- All 6 subcommands work from CLI: `python3 identity_registry.py --update-liveness runner impl_auth`
- Guardian and runner system prompts reference working CLI commands
- Existing 30 unit tests still pass + 6 new CLI tests

### Epic 2: Hook Manager Lifecycle Integration (F008/F009 gaps)

Wire `update_phase()` calls into runner_agent.py and spawn_orchestrator.py at lifecycle transitions:
- Runner calls `update_phase("executing")` when orchestrator starts working
- Runner calls `update_phase("impl_complete")` when orchestrator signals completion
- Guardian calls `update_phase("validating")` when validation begins
- Guardian calls `update_phase("merged")` after successful merge
- On respawn: `read_hook()` populates wisdom prompt with last phase and resumption instructions
- Add `build_wisdom_prompt_block()` that generates skip instructions from hook state

Also add CLI mode to `hook_manager.py` (`--update-phase`, `--read`, `--update-resumption`).

**Acceptance Criteria**:
- Hook phase transitions appear in `.claude/state/hooks/` JSON files during E2E run
- Respawned orchestrator receives skip instructions from previous hook
- Existing 35 unit tests pass + 8 new lifecycle tests

### Epic 3: Merge Queue Signal Integration (F013 gap)

Wire merge queue into the signal chain:
- Guardian calls `merge_queue.process_next()` directly (Python, not prompt-text) when receiving MERGE_READY signal
- On conflict: write `MERGE_FAILED` signal with conflict details
- On success: write `MERGE_COMPLETE` signal
- Add `merge_queue_cmd.py` CLI subcommand for `cli.py merge-queue list|enqueue|process`

**Acceptance Criteria**:
- `MERGE_READY` signal triggers `process_next()` in guardian Python code
- `MERGE_FAILED` signal written on rebase conflict
- `MERGE_COMPLETE` signal written on successful merge
- CLI `merge-queue` subcommand operational

### Epic 4: spawn_runner.py Real Implementation

Replace placeholder with actual runner_agent.py launcher:
- Use `subprocess.Popen` with cleaned environment (no CLAUDECODE)
- Register identity for runner before launch
- Create hook for runner before launch
- Return PID and runner state file path
- Handle runner crash detection (non-zero exit)

**Acceptance Criteria**:
- `spawn_runner.py --node impl_auth --prd PRD-TEST-001 --target-dir /path/to/repo` launches runner_agent.py as subprocess
- Identity file created at `.claude/state/identities/runner-impl_auth.json`
- Hook file created at `.claude/state/hooks/runner-impl_auth.json`
- Runner PID tracked in state file

### Epic 5: E2E Integration Test

Write a real E2E test that exercises the full chain:
1. Create a minimal test DOT pipeline (2 nodes: one codergen, one validation)
2. Launch guardian via launch_guardian.py
3. Guardian spawns runner via spawn_runner.py (real, not placeholder)
4. Runner spawns orchestrator via spawn_orchestrator.py
5. Verify: identity files exist for all 3 agents
6. Verify: hook files exist with correct phases
7. Verify: signal chain works (runner -> guardian -> runner)
8. Verify: merge queue processes on MERGE_READY
9. Verify: liveness heartbeats update
10. Clean up tmux sessions and state files

**Acceptance Criteria**:
- `pytest test_e2e_resilience.py -v` runs and passes in < 60 seconds
- Test creates real tmux sessions (not mocked)
- All identity, hook, signal, and merge-queue artifacts verified
- Test cleans up all state on exit (even on failure)
- All 132 existing tests still pass

## 5. Technical Approach

All implementation is in `.claude/scripts/attractor/`. No new modules — only extending existing ones.

File scope:
- `identity_registry.py` — add `__main__` CLI block (~60 lines)
- `hook_manager.py` — add `__main__` CLI block (~50 lines), add `build_wisdom_prompt_block()` (~30 lines)
- `runner_agent.py` — add `update_phase()` calls at lifecycle transitions (~15 lines)
- `guardian_agent.py` — add `merge_queue.process_next()` call on MERGE_READY signal, add `update_phase()` calls (~25 lines)
- `spawn_runner.py` — rewrite placeholder to real launcher (~80 lines)
- `spawn_orchestrator.py` — add respawn wisdom injection from hook (~20 lines)
- `merge_queue.py` — add signal emission on complete/fail (~15 lines)
- `signal_protocol.py` — no changes needed (signals already defined)
- `agents_cmd.py` — add `--json` and `--stale-only` flags (~10 lines)
- `cli.py` — add `merge-queue` dispatch (~5 lines)
- `launch_guardian.py` — add identity registration (~10 lines)
- New: `tests/test_e2e_resilience.py` — E2E integration test (~200 lines)
- New: `merge_queue_cmd.py` — CLI subcommand (~80 lines)

## 6. Success Metrics

- All 132 existing tests pass (regression gate)
- E2E test passes end-to-end
- Identity files created for all 4 layers during E2E run
- Hook phase transitions visible in state files
- Merge queue signal chain operational
