# SD-S3-RESILIENCE-GAPS-001: Session Resilience SDK Integration

**Status**: Active
**PRD**: PRD-S3-RESILIENCE-GAPS-001
**Date**: 2026-02-27
**Type**: Solution Design

---

## 1. Business Context

The session-resilience modules (identity_registry, hook_manager, merge_queue) are merged to main with 132 passing tests but are not wired into the actual SDK execution chain. This SD specifies exact code changes to integrate them so the 4-layer guardian/runner/orchestrator pipeline runs with full session resilience.

## 2. Technical Architecture

### Current State

```
launch_guardian.py (Layer 0)
    ├── NO identity registration
    ├── Delegates to guardian_agent.py (Layer 1) via SDK
    │
    guardian_agent.py (Layer 1)
    │   ├── identity_registry: create/terminate/crash ✅
    │   ├── hook_manager: NOT USED ❌
    │   ├── merge_queue: import side-effect only, prompt-text instructions ❌
    │   └── Instructs Claude to run spawn_runner.py
    │
    spawn_runner.py → PLACEHOLDER (writes JSON, exits) ❌
    │
    runner_agent.py (Layer 2)
    │   ├── identity_registry: create/terminate/crash ✅
    │   ├── hook_manager: create only, never updates ❌
    │   └── Instructs Claude to run spawn_orchestrator.py
    │
    spawn_orchestrator.py (Layer 3)
        ├── identity_registry: create ✅
        ├── hook_manager: create only ❌
        └── Creates tmux orchestrator session
```

### Target State

```
launch_guardian.py (Layer 0)
    ├── identity_registry.create_identity(role="launch") ✅
    ├── Delegates to guardian_agent.py (Layer 1) via SDK
    │
    guardian_agent.py (Layer 1)
    │   ├── identity_registry: create/terminate/crash ✅ (existing)
    │   ├── hook_manager: update_phase("validating"/"merged") on signal receipt ✅
    │   ├── merge_queue: process_next() called directly on MERGE_READY ✅
    │   ├── signal_protocol: write MERGE_COMPLETE/MERGE_FAILED after merge ✅
    │   └── Instructs Claude to run spawn_runner.py (real launcher)
    │
    spawn_runner.py → subprocess.Popen(runner_agent.py) ✅
    │
    runner_agent.py (Layer 2)
    │   ├── identity_registry: create/terminate/crash ✅ (existing)
    │   ├── hook_manager: update_phase at transitions ✅
    │   │   - "executing" when orch starts
    │   │   - "impl_complete" when orch signals done
    │   └── Instructs Claude to run spawn_orchestrator.py
    │
    spawn_orchestrator.py (Layer 3)
        ├── identity_registry: create ✅ (existing)
        ├── hook_manager: create + respawn reads existing hook ✅
        └── build_wisdom_prompt_block() on respawn ✅
```

## 3. Dependency Order

```
Epic 1 (CLI modes) ──┐
                      ├──► Epic 5 (E2E test)
Epic 2 (hook lifecycle) ──┤
                           │
Epic 3 (merge signals) ────┤
                           │
Epic 4 (spawn_runner) ─────┘
```

Epics 1-4 are independent of each other. Epic 5 depends on all four.

## 4. Functional Decomposition

### Epic 1: Identity Registry CLI Mode

**File**: `identity_registry.py`

Add at bottom of file:

```python
if __name__ == "__main__":
    import argparse, json, sys

    parser = argparse.ArgumentParser(description="Identity Registry CLI")
    sub = parser.add_subparsers(dest="command")

    # --update-liveness
    up = sub.add_parser("update-liveness")
    up.add_argument("role")
    up.add_argument("name")

    # --find-stale
    fs = sub.add_parser("find-stale")
    fs.add_argument("--timeout", type=int, default=300)

    # --list
    ls = sub.add_parser("list")
    ls.add_argument("--json", action="store_true")
    ls.add_argument("--stale-only", type=int, metavar="TIMEOUT_SECONDS")

    # --mark-crashed / --mark-terminated
    mc = sub.add_parser("mark-crashed")
    mc.add_argument("role")
    mc.add_argument("name")

    mt = sub.add_parser("mark-terminated")
    mt.add_argument("role")
    mt.add_argument("name")

    args = parser.parse_args()
    # ... dispatch to existing functions
```

**File**: `hook_manager.py` — same pattern, add CLI block with `update-phase`, `read`, `update-resumption`.

**File**: `agents_cmd.py` — add `--json` flag to `list` subcommand, add `--stale-only` filter.

### Epic 2: Hook Manager Lifecycle Integration

**File**: `runner_agent.py`

In `build_system_prompt()`, add instructions for Claude to call hook phase transitions:

```python
# After existing liveness section (~L204), add:
HOOK_LIFECYCLE = f"""
## Hook Phase Tracking
Update work phase at each lifecycle transition:
```bash
python3 {{scripts_dir}}/hook_manager.py update-phase runner {{node_id}} executing
```
When orchestrator signals NODE_COMPLETE:
```bash
python3 {{scripts_dir}}/hook_manager.py update-phase runner {{node_id}} impl_complete
```
"""
```

**File**: `guardian_agent.py`

In `build_system_prompt()`, add hook phase instructions:

```python
HOOK_LIFECYCLE = f"""
## Hook Phase Tracking
When starting validation:
```bash
python3 {{scripts_dir}}/hook_manager.py update-phase guardian {{pipeline_id}} validating
```
After successful merge:
```bash
python3 {{scripts_dir}}/hook_manager.py update-phase guardian {{pipeline_id}} merged
```
"""
```

**File**: `spawn_orchestrator.py`

In `respawn_orchestrator()`, read existing hook and inject wisdom:

```python
from hook_manager import read_hook, build_wisdom_prompt_block

existing_hook = read_hook("orchestrator", node_id)
if existing_hook:
    wisdom_block = build_wisdom_prompt_block(existing_hook)
    prompt = f"{wisdom_block}\n\n{prompt}"
```

**File**: `hook_manager.py`

Add new function:

```python
def build_wisdom_prompt_block(hook: dict) -> str:
    """Generate skip instructions from hook state for respawned orchestrator."""
    phase = hook.get("phase", "planning")
    instructions = hook.get("resumption_instructions", "")
    last_node = hook.get("last_committed_node", "")

    lines = [f"## RESUMPTION CONTEXT (from previous session)"]
    lines.append(f"Previous phase reached: {phase}")
    if last_node:
        lines.append(f"Last committed node: {last_node}")
    if phase in ("executing", "impl_complete", "validating"):
        lines.append(f"SKIP planning phase — go directly to {phase}")
    if instructions:
        lines.append(f"Resumption notes: {instructions}")
    return "\n".join(lines)
```

### Epic 3: Merge Queue Signal Integration

**File**: `guardian_agent.py`

In `build_system_prompt()`, replace the prompt-text merge queue section with direct Python integration instructions:

```python
MERGE_QUEUE_SECTION = f"""
## Merge Queue Integration
When you receive a MERGE_READY signal from a runner:
1. Call merge_queue.process_next() via Python:
```bash
python3 -c "
import sys; sys.path.insert(0, '{scripts_dir}')
from merge_queue import process_next
from signal_protocol import write_signal
result = process_next()
if result['success']:
    write_signal('guardian', 'runner', 'MERGE_COMPLETE', {{'node_id': result['entry']['node_id']}}, '{scripts_dir}/../pipelines/signals')
else:
    write_signal('guardian', 'runner', 'MERGE_FAILED', {{'node_id': result['entry']['node_id'], 'error': result['error']}}, '{scripts_dir}/../pipelines/signals')
print(result)
"
```
"""
```

**File**: `merge_queue_cmd.py` (NEW)

CLI subcommand for `cli.py merge-queue`:

```python
def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action")

    sub.add_parser("list")  # show queue state

    eq = sub.add_parser("enqueue")
    eq.add_argument("node_id")
    eq.add_argument("branch")
    eq.add_argument("--repo-root")

    sub.add_parser("process")  # process next entry

    args = parser.parse_args()
    # dispatch to merge_queue functions
```

**File**: `cli.py` — add `merge-queue` dispatch.

### Epic 4: spawn_runner.py Real Implementation

Replace placeholder with:

```python
def main():
    args = parse_args()

    # 1. Register identity
    identity = identity_registry.create_identity(
        role="runner", name=args.node_id,
        session_id=f"runner-{args.node_id}",
        worktree=args.target_dir
    )

    # 2. Create hook
    hook_manager.create_hook(
        role="runner", name=args.node_id, phase="planning"
    )

    # 3. Build runner command
    runner_script = os.path.join(os.path.dirname(__file__), "runner_agent.py")
    cmd = [
        sys.executable, runner_script,
        "--node", args.node_id,
        "--prd", args.prd_ref,
        "--session", f"orch-{args.node_id}",
        "--target-dir", args.target_dir,
    ]

    # 4. Launch with cleaned env
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    proc = subprocess.Popen(
        cmd, env=env, cwd=args.target_dir,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    # 5. Write state file with PID
    state = {
        "runner_pid": proc.pid,
        "node_id": args.node_id,
        "identity_file": f".claude/state/identities/runner-{args.node_id}.json",
        "hook_file": f".claude/state/hooks/runner-{args.node_id}.json",
        "started_at": datetime.utcnow().isoformat() + "Z",
    }
    # Write to runner-state/ directory
```

### Epic 5: E2E Integration Test

**File**: `tests/test_e2e_resilience.py` (NEW)

```python
@pytest.fixture
def mini_pipeline(tmp_path):
    """Create a minimal 2-node DOT pipeline for testing."""
    dot = tmp_path / "test.dot"
    dot.write_text('''
    digraph pipeline {
        graph [prd_ref="PRD-TEST-001"];
        start [shape=circle; label="START"];
        impl_test [shape=box; handler=codergen; label="Test Task";
                   status=pending; bead_id="TEST-001"];
        exit_ok [shape=doublecircle; label="EXIT-OK"];
        start -> impl_test [label="begin"];
        impl_test -> exit_ok [label="pass"];
    }
    ''')
    return dot

class TestE2EResilience:
    def test_identity_created_for_all_layers(self, mini_pipeline, tmp_path):
        """Verify identity files appear for guardian, runner, orchestrator."""

    def test_hook_phases_transition(self, mini_pipeline, tmp_path):
        """Verify hook phases: planning -> executing -> impl_complete."""

    def test_merge_queue_signal_chain(self, mini_pipeline, tmp_path):
        """Verify MERGE_READY -> process_next() -> MERGE_COMPLETE signal chain."""

    def test_liveness_heartbeat_updates(self, mini_pipeline, tmp_path):
        """Verify heartbeat timestamps update during execution."""

    def test_identity_registry_cli(self, tmp_path):
        """Verify CLI commands work: update-liveness, find-stale, list --json."""

    def test_hook_manager_cli(self, tmp_path):
        """Verify CLI commands work: update-phase, read."""

    def test_full_chain_dry_run(self, mini_pipeline, tmp_path):
        """Full chain: launch_guardian -> guardian -> runner -> orchestrator.
        Uses mocked SDK to avoid real Claude API calls."""
```

## 5. File Scope

| File | Epic | Change Type | Lines |
|------|------|-------------|-------|
| `identity_registry.py` | 1 | Modify (add CLI) | +60 |
| `hook_manager.py` | 1, 2 | Modify (add CLI + `build_wisdom_prompt_block`) | +80 |
| `agents_cmd.py` | 1 | Modify (add --json, --stale-only) | +15 |
| `runner_agent.py` | 2 | Modify (hook phase instructions in prompt) | +20 |
| `guardian_agent.py` | 2, 3 | Modify (hook phase + merge queue integration) | +40 |
| `spawn_orchestrator.py` | 2 | Modify (respawn wisdom from hook) | +20 |
| `merge_queue.py` | 3 | No change (signal emission in guardian, not here) | 0 |
| `spawn_runner.py` | 4 | Rewrite (placeholder -> real launcher) | +80 (net) |
| `cli.py` | 3 | Modify (add merge-queue dispatch) | +5 |
| `merge_queue_cmd.py` | 3 | New | +80 |
| `launch_guardian.py` | 2 | Modify (add identity registration) | +10 |
| `tests/test_e2e_resilience.py` | 5 | New | +200 |
| **Total** | | | ~+610 |

## 6. Acceptance Criteria per Feature

### Epic 1
- F1.1: `python3 identity_registry.py update-liveness runner impl_auth` exits 0 and updates heartbeat
- F1.2: `python3 identity_registry.py find-stale --timeout 300` returns JSON array of stale agents
- F1.3: `python3 identity_registry.py list --json` returns all identities as JSON
- F1.4: `python3 hook_manager.py update-phase runner impl_auth executing` exits 0 and updates phase
- F1.5: `python3 hook_manager.py read runner impl_auth` prints hook JSON

### Epic 2
- F2.1: Runner system prompt includes hook phase update instructions
- F2.2: Guardian system prompt includes hook phase update instructions
- F2.3: `build_wisdom_prompt_block()` returns skip instructions for phase >= executing
- F2.4: `respawn_orchestrator()` reads existing hook and injects wisdom

### Epic 3
- F3.1: Guardian system prompt includes direct Python merge_queue.process_next() call
- F3.2: On MERGE_READY, guardian writes MERGE_COMPLETE or MERGE_FAILED signal
- F3.3: `cli.py merge-queue list` shows queue state
- F3.4: `cli.py merge-queue enqueue <node> <branch>` adds to queue
- F3.5: `cli.py merge-queue process` processes next entry

### Epic 4
- F4.1: `spawn_runner.py --node impl_auth --prd PRD-TEST-001 --target-dir /path` launches runner_agent.py
- F4.2: Runner identity registered before subprocess launch
- F4.3: Runner hook created before subprocess launch
- F4.4: Runner PID tracked in state file

### Epic 5
- F5.1: `pytest test_e2e_resilience.py` passes with 7+ test cases
- F5.2: Identity files verified for guardian, runner, orchestrator
- F5.3: Hook phase transitions verified
- F5.4: Signal chain verified (MERGE_READY -> MERGE_COMPLETE)
- F5.5: All 132 existing tests still pass (regression gate)

## 7. Risks

- **SDK version sensitivity**: `claude_code_sdk` API may change; test with current installed version
- **tmux in CI**: E2E test requires tmux; may need `@pytest.mark.skipif` for CI environments
- **Race conditions**: Signal file writes must be atomic (already solved by signal_protocol pattern)

## 8. Implementation Notes

- All file writes MUST use the existing atomic tmp+rename pattern from signal_protocol.py
- CLI blocks should use `sys.exit(0)` on success, `sys.exit(1)` on failure
- Tests should clean up `.claude/state/` directories in fixtures
- The E2E test can mock the Claude SDK `query()` call to avoid API costs while testing infrastructure
