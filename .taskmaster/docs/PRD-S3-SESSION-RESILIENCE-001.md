---
prd_id: PRD-S3-SESSION-RESILIENCE-001
title: "Session Resilience & Merge Coordination"
status: draft
created: 2026-02-26
priority: P0-P1
owner: System 3 Guardian
target_repository: claude-harness-setup
supersedes: PRD-S3-GASTOWN-001 (partially — viable patterns only)
---

# PRD-S3-SESSION-RESILIENCE-001: Session Resilience & Merge Coordination

## 1. Background & Motivation

### Origin: Gastown Pattern Evaluation

PRD-S3-GASTOWN-001 proposed 12 epics to adopt patterns from Steve Yegge's Gas Town multi-agent orchestrator. A subsequent evaluation (2026-02-26) found that the AgentSDK guardian/runner architecture built between 2026-02-23 and 2026-02-25 had organically implemented ~40% of those patterns at the infrastructure level:

- **Runner agent** = Deacon per-orchestrator patrol (Epic 5)
- **Signal protocol** = Witness recovery escalation chain (Epic 6)
- **Programmatic enforcement** > LLM instruction (Epics 3, 4)

9 of 12 epics were assessed as obsolete, already addressed, or low-priority. This PRD repackages the **3 remaining viable patterns** plus 1 prerequisite, built natively on the existing signal_protocol.py + guardian/runner SDK infrastructure.

### The Problems That Remain

1. **No crash-safe work state.** When an orchestrator session crashes (context exhaustion, OOM, network failure), the next session starts fresh. Completion promises exist but aren't crash-atomic. The guardian can re-spawn via `spawn_orchestrator.py`, but the new session has no memory of what the crashed session was doing or how far it got.

2. **No central agent registry.** The guardian and runner know about their own orchestrator, but there's no single source of truth for "which agents are alive right now?" System 3 must manually `tmux ls` and cross-reference with DOT pipeline state.

3. **Merge conflict pileup.** When multiple orchestrators finish work in parallel worktrees, they each create PRs. Merges happen in arbitrary order, causing cascading rebase conflicts. No entity owns the merge sequence.

4. **Silent context exhaustion.** Sessions crash hard when context fills. There's no proactive detection, no graceful handoff, and no pre-crash checkpoint. Work in the final few tool calls before the crash is lost.

### Design Principle: Infrastructure Over Instructions

The Gastown PRD proposed adding GUPP awareness to output styles (Markdown read by LLMs). The evaluation found that programmatic enforcement via Python scripts is architecturally superior — signals can't be ignored, hook files can't be forgotten, and merge queues can't be bypassed. This PRD follows that principle: every feature is implemented as infrastructure that the guardian/runner invoke, not as instructions that orchestrators might follow.

## 2. Goals

| ID | Goal | Success Metric |
|----|------|----------------|
| G1 | Zero work lost on session crash | Crashed sessions resume from last checkpoint within 60s |
| G2 | Single source of truth for agent liveness | `cli.py agents` shows all active/stale agents with <10s latency |
| G3 | No merge conflicts from parallel orchestrators | Sequential merge queue processes N merges with 0 manual conflict resolution |
| G4 | Graceful context cycling (stretch) | 0 hard crashes from context exhaustion; all exits via handoff signal |

## 3. User Stories

- As the **guardian**, I want to re-spawn a crashed orchestrator with its previous work context, so that no progress is lost.
- As **System 3**, I want to see all active agents and their liveness status at a glance, so I can detect stale sessions without manual tmux inspection.
- As an **orchestrator**, I want my completed work to merge cleanly without conflicts from parallel orchestrators, so that validated code reaches main without manual intervention.
- As the **runner**, I want to detect when my orchestrator is approaching context exhaustion, so I can trigger a graceful handoff before a hard crash.

## 4. Non-Goals

- **Multi-runtime support** (Codex, Gemini CLI) — premature; revisit when demand exists
- **Web dashboard** — `cli.py dashboard` text output is sufficient
- **Ephemeral wisps** — requires upstream beads changes; not blocking
- **Crew agents** — nice-to-have; not addressing a pain point currently
- **Output style modifications for GUPP** — infrastructure enforcement is preferred

---

## Epic 1: Agent Identity Registry (P0 — Prerequisite)

**Rationale**: Every subsequent epic needs a central registry to answer "who is alive?" The identity registry is the foundation for crash recovery (which identity to restore), merge queue (which identities have merge requests), and context cycling (which identity is approaching exhaustion).

### Problem

No central registry exists. The guardian knows its runner, the runner knows its orchestrator, but:
- `tmux ls` is the only way to see all sessions
- Dead sessions leave no trace (no deregistration)
- Re-spawned sessions get new IDs with no link to predecessors
- DOT pipeline node→session mapping is implicit (node_id embedded in tmux session name)

### Requirements

- **R1.1**: Create identity registry at `.claude/state/identities/{role}-{name}.json`
- **R1.2**: Identity file schema: `{role, name, session_id, pid, tmux_session, node_id, bead_id, worktree_path, hook_path, created_at, last_seen, status, predecessor_id}`
- **R1.3**: `spawn_orchestrator.py` creates identity file before launching tmux session
- **R1.4**: `runner_agent.py` updates its orchestrator's `last_seen` every 60s (piggyback on existing monitoring loop)
- **R1.5**: `guardian_agent.py` updates its own `last_seen` and scans for stale identities (>5min since last_seen)
- **R1.6**: `cli.py agents` subcommand lists all identities with liveness status (green/yellow/red)
- **R1.7**: On clean session exit, identity status set to `terminated`; on crash detection, set to `crashed`
- **R1.8**: Re-spawned session inherits `predecessor_id` linking to the crashed identity

### Acceptance Criteria

- AC-1.1: Identity file created for every orchestrator at spawn time, queryable via `cli.py agents`
- AC-1.2: `last_seen` updates every 60s while orchestrator is alive
- AC-1.3: Stale identity (>5min) detected by guardian within one monitoring cycle
- AC-1.4: Re-spawned orchestrator has `predecessor_id` pointing to crashed identity
- AC-1.5: `cli.py agents --json` returns machine-readable registry for automation

### Files to Modify

| File | Change |
|------|--------|
| `.claude/scripts/attractor/spawn_orchestrator.py` | Create identity file before tmux session |
| `.claude/scripts/attractor/runner_agent.py` | Update `last_seen` in monitoring loop |
| `.claude/scripts/attractor/guardian_agent.py` | Scan for stale identities |
| `.claude/scripts/attractor/cli.py` | Add `agents` subcommand |
| NEW: `.claude/scripts/attractor/identity_registry.py` | Identity CRUD: create, read, update_liveness, mark_crashed, mark_terminated, list_all, find_stale |

### Integration Points

- **Signal protocol**: New signal types `AGENT_REGISTERED`, `AGENT_CRASHED`, `AGENT_TERMINATED`
- **DOT pipeline**: Node `session` attribute populated from identity registry
- **Guardian system prompt**: Include identity scan in monitoring cycle

---

## Epic 2: Persistent Work State — GUPP-Inspired Hook Files (P0)

**Rationale**: Gas Town's single most important insight: "If there is work on your hook, YOU MUST RUN IT." A hook file is a crash-persistent JSON document that records the current work item, checkpoint, and resumption instructions. When a session dies and is re-spawned, the hook tells it exactly where to resume.

### Problem

When an orchestrator crashes mid-task:
- The completion promise file may exist but doesn't capture in-progress state
- The DOT pipeline shows the node as `active` but not what step within that node
- The signal protocol has no "last known good state" for the crashed session
- The guardian re-spawns the orchestrator, but the new session starts from scratch — re-reading the PRD, re-investigating files already examined, potentially re-doing work

### Requirements

- **R2.1**: Hook file at `.claude/state/hooks/{identity-name}.json` with schema: `{identity_name, current_bead, current_node, work_phase, work_summary, last_checkpoint_at, files_modified, tests_status, resumption_instructions}`
- **R2.2**: `spawn_orchestrator.py` creates initial hook file with node scope from DOT pipeline
- **R2.3**: `runner_agent.py` updates the hook whenever it detects a phase transition in the orchestrator (via tmux capture analysis): investigation → planning → implementation → testing → completion
- **R2.4**: Signal protocol extended: `HOOK_UPDATED` signal from runner to guardian carries the hook state
- **R2.5**: When guardian detects crashed identity (Epic 1), it reads the hook file and includes resumption context in the re-spawn wisdom prompt
- **R2.6**: Hook files use atomic write (temp file + rename) to prevent corruption from mid-write crashes
- **R2.7**: Hook files are NOT git-tracked (they're in `.claude/state/` which is gitignored) — they survive within a machine session but not across machines. The identity registry + DOT pipeline provide cross-machine state.

### Acceptance Criteria

- AC-2.1: Hook file created at spawn time with initial node scope
- AC-2.2: Hook `work_phase` updates within 30s of orchestrator phase transition
- AC-2.3: After killing an orchestrator tmux session, re-spawning with the same identity produces a wisdom prompt that includes "Resume from phase: {phase}, last working on: {summary}"
- AC-2.4: Re-spawned orchestrator skips already-completed investigation and goes directly to the last known phase
- AC-2.5: Hook file is never corrupted (atomic write verified by concurrent kill test)

### Files to Modify

| File | Change |
|------|--------|
| `.claude/scripts/attractor/spawn_orchestrator.py` | Create initial hook file from DOT node context |
| `.claude/scripts/attractor/runner_agent.py` | Detect phase transitions, update hook, signal HOOK_UPDATED |
| `.claude/scripts/attractor/guardian_agent.py` | Read hook on crash detection, inject into re-spawn wisdom |
| `.claude/scripts/attractor/signal_protocol.py` | Add HOOK_UPDATED signal type |
| NEW: `.claude/scripts/attractor/hook_manager.py` | Hook CRUD: create, read, update_phase, update_checkpoint, atomic_write |

### Integration Points

- **Identity registry** (Epic 1): Hook path stored in identity file; hook linked to identity
- **Signal protocol**: HOOK_UPDATED carries compressed hook state
- **Spawn orchestrator**: Wisdom prompt template includes hook resumption block
- **DOT pipeline**: Hook references current node_id; pipeline transition triggers hook update

---

## Epic 3: Sequential Merge Queue — Refinery-Inspired (P1)

**Rationale**: When 3 orchestrators complete work in parallel worktrees and all signal `merge_ready`, merging in arbitrary order causes cascading rebase conflicts. The Refinery pattern processes merges sequentially: rebase → test → merge → next.

### Problem

Current workflow: orchestrator completes → creates PR → guardian validates → merge (manually or via gh pr merge). With parallel orchestrators:
- Orchestrator A merges first (clean)
- Orchestrator B's branch now conflicts with main (A's changes)
- Orchestrator C conflicts with both A and B
- Manual resolution needed for B and C

### Requirements

- **R3.1**: Merge queue file at `.claude/state/merge-queue.json` — ordered list of `{identity_name, branch, worktree_path, pr_number, bead_id, node_id, requested_at, status}`
- **R3.2**: New signal type `MERGE_READY` from runner to guardian (after orchestrator signals impl_complete and guardian validates)
- **R3.3**: Guardian processes queue sequentially: (a) checkout branch, (b) rebase onto main, (c) run tests, (d) if green → merge + delete branch, (e) if red → signal `MERGE_CONFLICT` back to runner with conflict file list
- **R3.4**: `cli.py merge-queue` subcommand: `list` (show queue), `add` (enqueue), `process` (process next), `status` (current state)
- **R3.5**: Orchestrators do NOT merge directly — they signal `MERGE_READY` and move to next node (or exit if no more nodes)
- **R3.6**: Conflict escalation: guardian sends `MERGE_CONFLICT` signal to runner → runner instructs orchestrator to resolve conflicts → orchestrator re-signals `MERGE_READY` after resolution

### Acceptance Criteria

- AC-3.1: Two simultaneous `MERGE_READY` signals are processed sequentially — second waits for first
- AC-3.2: Clean merge: branch rebased, tests pass, merged to main, branch deleted
- AC-3.3: Conflict merge: specific conflicting files identified, escalated to orchestrator via runner signal
- AC-3.4: `cli.py merge-queue list` shows queue state with ordering
- AC-3.5: Zero direct merges to main — all go through queue

### Files to Modify

| File | Change |
|------|--------|
| `.claude/scripts/attractor/guardian_agent.py` | Process merge queue after validation; handle MERGE_READY signals |
| `.claude/scripts/attractor/runner_agent.py` | Send MERGE_READY after impl_complete validation; relay MERGE_CONFLICT |
| `.claude/scripts/attractor/signal_protocol.py` | Add MERGE_READY, MERGE_CONFLICT, MERGE_COMPLETE signal types |
| `.claude/scripts/attractor/cli.py` | Add `merge-queue` subcommand |
| `.claude/scripts/attractor/spawn_orchestrator.py` | Remove any direct merge instructions from wisdom template |
| NEW: `.claude/scripts/attractor/merge_queue.py` | Queue management: enqueue, dequeue, process_next, rebase_and_test, merge_or_escalate |

### Integration Points

- **Identity registry** (Epic 1): Queue entries reference identity_name
- **Hook files** (Epic 2): After merge, hook status set to `merged`
- **Signal protocol**: 3 new signal types for merge lifecycle
- **DOT pipeline**: Node transitions from `impl_complete` → `validated` → (merge_queue) → `merged`

---

## Epic 4: Proactive Context Cycling (P1 — Stretch)

**Rationale**: Context exhaustion is the #1 cause of unrecoverable orchestrator crashes. Currently the PreCompact hook fires (reloading MCP skills) but there's no proactive detection or graceful handoff. With Epics 1 and 2 in place, context cycling becomes feasible: save state to hook → signal guardian → exit cleanly → guardian re-spawns with hook context.

### Problem

- Claude Code doesn't expose context usage % via API
- The only signal is PreCompact (context compression starting) — by then it may be too late
- Hard crashes lose the last N tool calls before context fills
- The runner can observe symptoms (slower responses, compaction events) but has no channel to trigger proactive handoff

### Requirements

- **R4.1**: Runner detects context exhaustion symptoms: (a) PreCompact hook fires (visible in tmux as system message), (b) response latency increases >3x baseline, (c) orchestrator outputs "context" warnings
- **R4.2**: On symptom detection, runner signals `CONTEXT_WARNING` to guardian with estimated urgency (low/medium/high)
- **R4.3**: Guardian decides: `low` → continue monitoring, `medium` → send "checkpoint now" guidance to orchestrator via runner, `high` → trigger immediate handoff
- **R4.4**: Handoff sequence: runner sends "GUARDIAN: Save your work and exit cleanly" → orchestrator commits work + updates hook → runner confirms via `HOOK_UPDATED` signal → guardian kills tmux session → guardian re-spawns with hook context
- **R4.5**: If orchestrator doesn't exit cleanly within 60s of handoff request, runner signals `ORCHESTRATOR_STUCK` and guardian force-kills
- **R4.6**: Re-spawned session includes in wisdom: "You are a continuation of {predecessor_id}. Resume from: {hook.work_summary}. Phase: {hook.work_phase}."

### Acceptance Criteria

- AC-4.1: Runner detects PreCompact event in tmux output and signals CONTEXT_WARNING
- AC-4.2: Graceful handoff completes: orchestrator saves hook → exits → re-spawns with hook context within 90s
- AC-4.3: Re-spawned session resumes from correct phase (verified by examining its first 5 tool calls)
- AC-4.4: Force-kill triggered if graceful handoff times out at 60s
- AC-4.5: No data loss: all files modified before handoff are committed

### Files to Modify

| File | Change |
|------|--------|
| `.claude/scripts/attractor/runner_agent.py` | Detect context exhaustion symptoms; send CONTEXT_WARNING; manage handoff sequence |
| `.claude/scripts/attractor/guardian_agent.py` | Handle CONTEXT_WARNING; decide urgency response; trigger re-spawn after handoff |
| `.claude/scripts/attractor/signal_protocol.py` | Add CONTEXT_WARNING, HANDOFF_REQUESTED, HANDOFF_COMPLETE signal types |
| `.claude/scripts/attractor/spawn_orchestrator.py` | Support re-spawn with predecessor context from hook file |

### Dependencies

- **Epic 1** (Identity Registry): Predecessor linking for re-spawned sessions
- **Epic 2** (Hook Files): Crash-safe state that the handoff saves to and re-spawn reads from

---

## 5. Implementation Order & Dependencies

```
Epic 1 (Identity Registry) ──► Epic 2 (Hook Files) ──► Epic 4 (Context Cycling)
                                       │
                                       └──► Epic 3 (Merge Queue)
```

Epic 1 is prerequisite for all others. Epics 2 and 3 can be parallelized after Epic 1. Epic 4 depends on both 1 and 2.

**Recommended phasing:**
- **Phase 1** (P0): Epic 1 (Identity Registry) — 2-3 days
- **Phase 2** (P0): Epic 2 (Hook Files) — 2-3 days (after Epic 1)
- **Phase 3** (P1): Epic 3 (Merge Queue) — 3-4 days (can overlap with Epic 2)
- **Phase 4** (P1 stretch): Epic 4 (Context Cycling) — 3-4 days (after Epics 1+2)

## 6. Success Metrics

| Metric | Current | Target (Post-Epic 2) | Target (Post-Epic 4) |
|--------|---------|-------------------|--------------------|
| Work lost per crash | Variable (0-100%) | 0% (hook-preserved) | 0% (hook + proactive handoff) |
| Crash recovery time | Manual (5-15 min) | Automatic (<60s) | Automatic (<90s with context cycling) |
| Merge conflicts from parallel work | Frequent | Frequent | Rare (sequential queue) |
| Agent liveness detection | Manual tmux ls | <10s via `cli.py agents` | <10s |
| Context exhaustion crashes | Frequent | Frequent | 0 (proactive cycling) |

## 7. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hook file corruption during crash | Work state lost | Atomic writes (temp + rename); periodic backups |
| Identity stale-detection false positives | Unnecessary re-spawns | 5-minute threshold with 3-strike confirmation |
| Merge queue bottleneck | Slow throughput | Process merges in <60s; parallel test execution |
| Context exhaustion symptoms unreliable | Late detection | Multiple symptom sources; conservative thresholds |
| Runner overhead from frequent hook updates | Slower monitoring | Batch updates; update only on phase transitions |

## 8. References

- PRD-S3-GASTOWN-001 (superseded — evaluation found 9/12 epics obsolete)
- `.claude/scripts/attractor/signal_protocol.py` — existing IPC infrastructure
- `.claude/scripts/attractor/guardian_agent.py` — existing SDK guardian
- `.claude/scripts/attractor/runner_agent.py` — existing SDK runner
- `.claude/scripts/attractor/spawn_orchestrator.py` — existing tmux spawning
- `.claude/scripts/attractor/cli.py` — existing pipeline CLI

---

**Version**: 0.1.0 (Draft)
**Author**: System 3 Guardian
**Created**: 2026-02-26
