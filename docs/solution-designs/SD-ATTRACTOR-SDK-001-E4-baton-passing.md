# SD-ATTRACTOR-SDK-001-E4: Guardian Baton-Passing, Independent Validation & Seance Context Recovery

**PRD**: GAP-PRD-ATTRACTOR-SDK-001
**Epic**: 4 — Guardian Baton-Passing, Independent Validation & Seance Context Recovery
**Priority**: P1
**Depends on**: Epic 1, Epic 2
**Design Influence**: [Gastown Seance Pattern](../references/gastown-comparison.md#priority-2-seance--context-recovery-on-retry)

---

## 1. Problem

The Attractor spec's `ManagerLoopHandler` (Section 4.11) defines a supervisor pattern where the manager (guardian) orchestrates observe/steer/wait cycles over a child pipeline. Currently, the guardian's interaction with the runner is limited to:
1. Spawn runner
2. Wait for signal (600s timeout)
3. Handle signal (validate or retry)

There is no structured "baton-passing" where the guardian validates a node, then relaunches the runner to continue with the next node.

Additionally, validation is currently done by the guardian's own LLM reasoning — essentially self-grading. The Attractor spec and guardian disposition (skeptical curiosity) demand **independent validation**: a separate worker that reviews implementation without knowledge of the implementer's self-assessment.

## 2. Design

### 2.1 Baton-Passing Concept

The "baton" is the DOT graph state. After a codergen node completes:

```
Worker completes → Runner detects completion (SDK events)
  → Runner transitions codergen node: active → impl_complete
  → Runner spawns INDEPENDENT VALIDATION WORKER
  → Validation worker reviews: git diff, test results, acceptance criteria
  → Validation worker reports: PASS or FAIL with evidence
  → If PASS: Runner transitions node: impl_complete → validated
  →   Runner writes NODE_VALIDATED signal for guardian
  → If FAIL: Runner collects Seance context, spawns remediation worker
  →   Runner re-enters MONITOR mode for remediation worker
  → Guardian reads NODE_VALIDATED signal (pull-based polling)
  → Guardian checks for next ready node
  → If next node exists: Guardian spawns new runner (passes baton)
  → If pipeline complete: Guardian signals PIPELINE_COMPLETE
```

**Key changes from v1**: (1) Validation is done by an **independent worker**, not the guardian's own reasoning — eliminates self-reporting bias. (2) The **runner** owns the full node lifecycle (impl_complete → validation → validated), not the guardian. The guardian only handles cross-node decisions.

This pattern implements the `ManagerLoopHandler` observe/steer/wait cycle from Attractor Spec Section 4.11:
- **Observe**: Guardian observes runner/worker status and outcomes via signals and git log
- **Steer**: Guardian sends remediation guidance (via `--additional-context`) in the re-spawn phase
- **Wait**: Signal-based polling for NODE_COMPLETE signal via `wait_for_signal.py`

The independent validation worker extends beyond the base spec, aligning with StrongDM Level 4 practice: "validation replaces code review." The spec's `ManagerLoopHandler` provides the structural skeleton; independent validation is the discipline layer on top.

### 2.2 Validate Node Pattern

In the DOT file, validate nodes should be explicit:

```dot
codergen_g12 -> validate_g12 [label="impl_complete"]
validate_g12 -> exit_ok [label="validated", condition="outcome=success"]
validate_g12 -> codergen_g12 [label="retry", condition="outcome=fail"]

validate_g12 [
    shape=hexagon,
    handler="wait.human",
    worker_type="tdd-test-engineer",
    label="Validate G12 Implementation",
    acceptance="AC-G12.1: topic changed; AC-G12.2: handler confirmed"
]
```

The guardian handles `wait.human` nodes by spawning an independent validation worker (acting as the "human reviewer").

### 2.3 Independent Validation Worker

The validation worker is a specialist spawned via `worker_backend.py` with a different persona. It implements the CodergenBackend interface (Spec Section 4.5): the `worker_type` attribute on the DOT node determines which specialist LLM backend handles the validation node. Read-only tool restriction (no Edit/Write) enforces "blind review" discipline, preventing the validator from modifying code and introducing conflicts. This follows the holdout scenario pattern: the validator is independent and never sees the implementation worker's self-assessment.

```python
# In worker_backend.py, add validation persona:
WORKER_PERSONAS["validation-reviewer"] = {
    "role": "Independent code reviewer and test validator",
    "focus": "Code review, test execution, acceptance criteria verification",
    "tools": "Read, Bash, Grep, Glob",  # NO Edit/Write — reviewer doesn't fix, only reports
}
```

The validation worker receives:
1. **Acceptance criteria** from the DOT node
2. **Git diff** of implementation changes (via `git diff` of the codergen node's commits)
3. **Test results** (run tests independently)
4. **NOT the implementation worker's self-assessment** — this is blind validation

The validation worker's system prompt:

```python
def build_validation_prompt(
    node_id: str,
    acceptance: str,
    target_dir: str,
    impl_node_id: str,
) -> str:
    return f"""\
You are an independent code reviewer validating pipeline node '{node_id}'.

## Your Role
You are a VALIDATOR. You do NOT implement or fix code.
- You READ code, RUN tests, and ANALYZE git diffs
- You NEVER use Edit or Write tools
- You report your findings objectively

## What You're Validating
- Implementation node: {impl_node_id}
- Acceptance criteria: {acceptance}
- Target directory: {target_dir}

## Validation Steps
1. Run `git log --oneline -10` to see recent commits
2. Run `git diff HEAD~N` to review the implementation changes
3. Run any relevant test commands
4. Check each acceptance criterion independently

## Report Format
VERDICT: <PASS|FAIL>
CRITERIA_MET: <comma-separated list of met criteria>
CRITERIA_FAILED: <comma-separated list of failed criteria>
EVIDENCE: <summary of what you found>
RECOMMENDATION: <if FAIL, what needs to be fixed>
"""
```

### 2.4 Runner Validation Phase (Phase C)

The **runner** (not the guardian) handles the validation lifecycle after worker completion. This is implemented as Phase C of the runner's execution:

```python
# In RunnerStateMachine, after worker completes (Phase B detects COMPLETED):

# Phase C: Validation
# 1. Transition codergen node to impl_complete
transition_node(dot_path, node_id, "impl_complete")
checkpoint_save(dot_path)

# 2. Spawn independent validation worker
validation_result = await spawn_worker_sdk(
    node_id=f"validate_{node_id}",
    worker_type="validation-reviewer",
    task_prompt=build_validation_prompt(
        node_id=node_id,
        acceptance=acceptance_criteria,
        target_dir=target_dir,
        impl_node_id=node_id,
    ),
    target_dir=target_dir,
)

# 3. Parse validation result
if "VERDICT: PASS" in validation_result.result:
    transition_node(dot_path, node_id, "validated")
    checkpoint_save(dot_path)
    write_signal(signals_dir, "complete", {
        "status": "NODE_VALIDATED",
        "node_id": node_id,
        "ts": time.time(),
    })
else:
    # Collect Seance context and spawn remediation worker
    seance_context = collect_predecessor_context(
        node_id=node_id,
        signals_dir=signals_dir,
        worktree_path=target_dir,
        last_error=validation_result.result,
    )
    # Re-enter Phase A (SPAWN) with remediation context
    # Runner stays alive and loops back to monitoring
```

**Guardian's role is simplified**: The guardian only reads NODE_VALIDATED signals and decides which node to dispatch next. It does NOT perform validation or transition nodes within a single node's lifecycle.

### 2.5 Guardian System Prompt Update

The guardian's prompt is simplified — it only handles cross-node orchestration:

```
### Phase 2c: Wait for Runner Validation Result
For each dispatched runner:
1. Poll for NODE_VALIDATED or NODE_FAILED signal in {signals_dir}/{node_id}/complete.json
2. If NODE_VALIDATED:
   → Node is already transitioned (runner did it)
   → Save checkpoint
   → Check for next ready node (--filter=pending --deps-met)
3. If NODE_FAILED (after runner exhausted retries):
   → Log failure to Hindsight
   → Continue with next ready node (if any)
   → Report pipeline status
```

### 2.6 Seance Context Recovery (Adopted from Gastown)

When a codergen node fails and needs retry, the fresh worker must not start blind. The **Seance pattern** collects predecessor context before re-spawning:

```python
def collect_predecessor_context(
    node_id: str,
    signals_dir: str,
    worktree_path: str,
    last_error: str | None = None,
) -> str:
    """Collect context from a failed predecessor for Seance-style recovery.

    Prevents the retry worker from making contradictory decisions by providing:
    1. Git commits from the failed attempt (what was implemented)
    2. Worker's mid-work notes (why decisions were made)
    3. Validation feedback (what failed)
    4. Error details (how it crashed)
    """
    context_parts = []

    # 1. Git commits from predecessor
    try:
        result = subprocess.run(
            ["git", "-C", worktree_path, "log", "--oneline", "-20"],
            capture_output=True, text=True, timeout=10,
        )
        if result.stdout.strip():
            context_parts.append(
                f"## Predecessor Git Commits\n```\n{result.stdout.strip()}\n```"
            )
    except Exception:
        pass

    # 2. Worker notes (Seance recovery artifact from E3 signals)
    notes_path = os.path.join(signals_dir, node_id, "notes.json")
    if os.path.exists(notes_path):
        with open(notes_path) as f:
            notes = json.load(f)
        observations = notes.get("observations", [])
        if observations:
            context_parts.append(
                "## Predecessor Observations\n" +
                "\n".join(f"- {obs}" for obs in observations)
            )

    # 3. Validation feedback (if retry triggered by validation failure)
    complete_path = os.path.join(signals_dir, node_id, "complete.json")
    if os.path.exists(complete_path):
        with open(complete_path) as f:
            completion = json.load(f)
        if completion.get("status") == "VALIDATION_FAILED":
            context_parts.append(
                f"## Validation Feedback\n{completion.get('feedback', 'No details')}"
            )

    # 4. Error details
    if last_error:
        context_parts.append(f"## Error from Previous Attempt\n{last_error}")

    if not context_parts:
        return ""

    return (
        "# SEANCE CONTEXT RECOVERY\n"
        "The following context was collected from a failed predecessor attempt.\n"
        "Use this to avoid contradictory decisions and continue from where the predecessor left off.\n\n"
        + "\n\n".join(context_parts)
    )
```

### 2.7 Runner Remediation Flow

When validation fails, the **runner** handles remediation directly (not the guardian):

```python
# In RunnerStateMachine Phase C, on validation failure:
if retry_count < max_retries:
    seance_context = collect_predecessor_context(
        node_id=node_id,
        signals_dir=signals_dir,
        worktree_path=target_dir,
        last_error=validation_result.result,
    )
    # Transition node back to active for retry
    transition_node(dot_path, node_id, "active")
    checkpoint_save(dot_path)

    # Re-spawn implementation worker with Seance context
    await spawn_worker_sdk(
        node_id=node_id,
        worker_type=worker_type,
        task_prompt=original_task_prompt,
        target_dir=target_dir,
        additional_context=seance_context,  # Seance: predecessor's context
    )
    # Re-enter Phase B (MONITOR) for the remediation worker
    retry_count += 1
else:
    # Max retries exhausted — signal guardian with failure
    write_signal(signals_dir, "complete", {
        "status": "NODE_FAILED",
        "node_id": node_id,
        "ts": time.time(),
        "retries": retry_count,
        "last_error": validation_result.result,
    })
```

The `additional_context` parameter in `spawn_worker_sdk()` (E1) accepts Seance context. It is injected into the task prompt (not the system prompt) so it doesn't break prompt caching.

### 3. Testing

- **Unit test**: Validation worker prompt includes acceptance criteria and excludes Edit/Write
- **Unit test**: Guardian system prompt includes validate node handling with independent worker
- **Integration test**: codergen → NODE_COMPLETE → guardian spawns validation worker → PASS → validated
- **Integration test**: codergen → NODE_COMPLETE → validation worker → FAIL → remediation worker → re-validates
- **E2E test**: Full pipeline: start → codergen → validate (independent) → exit_ok

### 4. Files Changed

| File | Change |
|------|--------|
| `worker_backend.py` | Add `validation-reviewer` persona, `build_validation_prompt()` |
| `guardian_agent.py` | Update `build_system_prompt()` with Phase 2c: independent validation |
| `spawn_runner.py` | Add `--additional-context` flag for remediation |
| `runner_agent.py` | Pass additional_context to worker_backend |
| `tests/test_baton_passing.py` | **NEW** — integration tests |

### 5. Implementation Constraints

1. **Acceptance criteria quality is the critical bottleneck.** The validation node's acceptance criteria must be precise and unambiguous — a vague criterion ("it works") produces inconsistent verdicts. Write criteria as verifiable conditions ("AC-G12.1: `git log` shows a commit modifying `runner_agent.py`; AC-G12.2: `pytest tests/test_runner.py` exits 0").

2. **Edge-case reliability.** Validation workers may miss novel failure modes not anticipated at spec-writing time. Mitigation: acceptance criteria should be exhaustive, not minimal. Include negative checks ("no tmux references in sdk-mode paths") alongside positive checks.

3. **Instrumentation is required for effective blind review.** The validation worker serves a role analogous to StrongDM's Digital Twin Universe — objective validation separated from implementation. Like DTU, it is only as effective as the instrumentation it receives: git diff, test output, and file-based metrics must all be available. If the git diff is empty (no commits from the worker), the validator will produce an unreliable verdict.

4. **Subprocess coordination is stable.** Signal-based coordination using files, PIDs, and git logs is a validated pattern across community Attractor implementations (including streamweave-attractor in Rust). No known gotchas specific to this pattern for baton-passing or subprocess spawning.

5. **No breaking changes in Attractor spec.** The specification is stable with no versioning changes documented. All patterns here align directly with Spec Sections 4.5 (CodergenBackend) and 4.11 (ManagerLoopHandler).

### 6. Open Questions

1. **Should validation also use validation-test-agent?** For PRD-level acceptance criteria, `validation-test-agent --mode=e2e` provides more structured scoring than a raw validation worker. For technical checks (tests pass, code compiles), a `tdd-test-engineer` worker is sufficient.
   - **Recommendation**: Use `tdd-test-engineer` for technical validation at codergen nodes. Use `validation-test-agent` for pipeline-level E2E validation (separate from per-node validation).

2. **What if the validation worker crashes?** Same as implementation worker crash — signal guardian with WORKER_CRASHED. Guardian can retry the validation (spawn a new validation worker) rather than re-implementing.
   - **Recommendation**: Guardian retries validation up to 2 times before marking the validate node as failed.

3. **Validation worker timeout?** Validation should be faster than implementation — it only reads and runs tests.
   - **Recommendation**: 60-turn limit for validation workers (vs 100 for implementation workers). 5-minute timeout.
