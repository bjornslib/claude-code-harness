# PRD-S3-GASTOWN-001: Gas Town Pattern Integration for Multi-Agent Resilience

## Overview

Adopt proven architectural patterns from Gas Town (Steve Yegge's Go-based multi-agent orchestrator, ~10k GitHub stars, released 2026-01-01) into the claude-harness-setup framework. This is NOT an installation of Gas Town itself — it is a selective integration of Gas Town's battle-tested patterns (GUPP persistence, crash-recovery identity, Deacon patrol cycles, Refinery merge queues, context cycling) into our existing 3-level hierarchy, output styles, and skills.

**PRD ID**: PRD-S3-GASTOWN-001
**Status**: Draft
**Priority**: P0–P2 (tiered by epic)
**Owner**: System 3 Meta-Orchestrator
**Target Repository**: claude-harness-setup (deployed to all targets)
**Date**: 2026-02-23

## Background

### Why Gas Town Matters to Us

Gas Town solves the same problems we face: context window exhaustion, session crashes losing state, unmanageable parallel agents, and merge conflict pileup. Its core patterns — persistent identity, git-backed state, supervisor hierarchies, and merge queues — are "architecturally sound and based on proven Erlang patterns" (Steve Klabnik). DoltHub's Tim Sehn called the Mayor interface "compelling" despite closing all generated PRs.

The system is expensive ($100/hour for heavy usage) and complex, but the architectural patterns it pioneered are directionally correct and map cleanly onto our existing infrastructure:

| Gas Town Concept | Our Equivalent | Gap This PRD Closes |
|------------------|----------------|---------------------|
| GUPP (universal work hook) | Completion promises | Promises don't survive crashes; no "hook" pinning |
| Mayor | System 3 Meta-Orchestrator | No single conversational interface abstraction |
| Polecats | Workers (native teams) | No crash-recovery identity; no ephemeral worktree isolation |
| Witness | s3-heartbeat | No recovery strategies — detects stalls but can't fix them |
| Refinery | Manual merge by orchestrator | No dedicated merge queue; conflict pileup risk |
| Deacon + DYFJ | Stop gate + hooks | No proactive "Do Your Job" patrol cycle |
| `gt prime` | SessionStart hooks | No role-based CWD detection; no identity inheritance |
| `gt handoff` | Session handoffs (manual) | No automated context cycling before exhaustion |
| `gt seance` | `/resume` | No structured predecessor communication protocol |
| Wisps | (nothing) | No ephemeral beads concept |
| Convoys | Attractor DOT pipelines | Need tighter convoy-to-pipeline mapping |
| Crew | (nothing) | No long-lived named agents for interactive work |
| Town Mail | Message bus (mb-*) | Already functional; minor enhancements needed |

### Three Workstreams

1. **Workstream A: Crash-Resilient Identity & GUPP** (P0) — Hook-based persistence, crash recovery, identity inheritance
2. **Workstream B: Operational Supervisors** (P1) — Deacon patrol, Witness recovery, Refinery merge queue, context cycling
3. **Workstream C: Ergonomics & Extensibility** (P2) — Wisps, Crew agents, dashboard, multi-runtime presets

### Design Principles

1. **Adopt patterns, not code.** Gas Town is 189k lines of Go. We extract the architectural ideas and implement them in our existing Python/Bash/Markdown skill framework.
2. **Layer on existing infrastructure.** Beads, message bus, attractor DOT, completion promises, tmux management — all stay. Gas Town patterns augment; they don't replace.
3. **Progressive complexity.** P0 makes the system crash-resilient. P1 adds operational intelligence. P2 adds ergonomic polish. Each tier is independently valuable.
4. **Erlang-inspired supervision.** Like Gas Town's borrowing from Erlang supervisor trees, our hierarchy becomes self-healing: every agent monitors its children; every crash triggers re-spawn with identity preservation.

---

## Workstream A: Crash-Resilient Identity & GUPP (P0)

### Epic 1: GUPP Hook Enforcement — "If There Is Work on Your Hook, YOU MUST RUN IT"

**Priority**: P0
**Rationale**: GUPP (Gas Town Universal Propulsion Principle) is the single most important pattern in Gas Town. Every agent has a persistent "hook" — a pinned work item that survives session crashes and restarts. When a session resumes, the hook tells it exactly what to do. Without this, crashed sessions lose their work state and the hierarchy stalls.

#### Problem

Currently, completion promises track what a session committed to, but they don't survive crashes gracefully. When a session dies:
- The next session doesn't know what the previous one was working on
- No "hook" file exists to pin the current work item
- The stop gate checks promises but doesn't enforce active work resumption
- Orchestrators that crash leave their workers orphaned with no recovery signal

#### Requirements

- **R1.1**: Create a GUPP hook file format at `.claude/state/hooks/{session-id}.json` containing: `{role, identity, current_bead, work_summary, last_checkpoint, created_at, updated_at}`
- **R1.2**: SessionStart hook (`session-start-orchestrator-detector.py`) reads the hook file for the current CWD/role and injects work context into the session
- **R1.3**: Every tool call that advances work updates the hook file atomically (via PostToolUse hook)
- **R1.4**: Stop gate refuses to allow exit if hook has unfinished work unless explicitly released
- **R1.5**: Hook file is git-tracked in `.claude/state/hooks/` so it persists across machine restarts
- **R1.6**: System 3 output style includes GUPP enforcement: "Check your hook before doing anything else"
- **R1.7**: Orchestrator output style includes GUPP compliance: "Update your hook after every work advancement"

#### Acceptance Criteria

- AC-1.1: A hook file is created at session start for every System 3 and orchestrator session
- AC-1.2: Hook file contains current bead ID, work summary, and last checkpoint timestamp
- AC-1.3: When a session crashes and restarts in the same CWD, the new session reads the hook and resumes work within 30 seconds
- AC-1.4: Stop gate blocks exit when hook has `current_bead` set and work is incomplete
- AC-1.5: Hook file updates atomically on every `bd update`, `bd close`, or `TaskUpdate` call

#### Files to Modify

| File | Change |
|------|--------|
| `.claude/hooks/session-start-orchestrator-detector.py` | Add hook file reading + work context injection |
| `.claude/hooks/unified-stop-gate.sh` | Add GUPP hook check before allowing exit |
| `.claude/output-styles/system3-meta-orchestrator.md` | Add "GUPP Hook Protocol" section after Immediate Session Initialization |
| `.claude/output-styles/orchestrator.md` | Add "GUPP Compliance" to Core Principles |
| `.claude/skills/system3-orchestrator/SKILL.md` | Add hook creation to PREFLIGHT and hook update to SPAWN WORKFLOW |
| `.claude/skills/orchestrator-multiagent/PREFLIGHT.md` | Add hook creation step |
| NEW: `.claude/scripts/gupp-hook.py` | GUPP hook CRUD operations (create, read, update, release) |
| NEW: `.claude/hooks/gupp-hook-update.py` | PostToolUse hook to update hook on work-advancing tool calls |

---

### Epic 2: Crash-Recovery Identity — Session Dies, Identity Lives

**Priority**: P0
**Rationale**: Gas Town's core insight is that "sessions are cattle; identities are persistent." When a Polecat session crashes, a new session picks up the same identity and continues from the hook. Our sessions currently don't have persistent identities — they rely on env vars that die with the process.

#### Problem

When an orchestrator session crashes (context exhaustion, OOM, network failure):
- The tmux session may still exist but the Claude Code process is dead
- The next `ccorch` launch gets a fresh session with no memory of the previous identity
- Workers spawned by the dead orchestrator are orphaned
- System 3's monitors report the session as "missing" but have no recovery path
- The Deacon patrol (s3-heartbeat) detects the crash but cannot re-establish identity

#### Requirements

- **R2.1**: Create identity files at `.claude/state/identities/{role}-{name}.json` containing: `{role, name, initiative, session_id, hook_path, worktree_path, created_at, last_seen, status}`
- **R2.2**: Identity files persist across session restarts (git-tracked)
- **R2.3**: `spawn-orchestrator.sh` creates an identity file before launching the session and updates `session_id` on each restart
- **R2.4**: SessionStart hook performs CWD-based role detection (Gas Town's `gt prime` pattern): if CWD is under `trees/{name}/`, inject orchestrator identity for `{name}`
- **R2.5**: When System 3 detects a dead orchestrator session, it re-spawns with the same identity file, inheriting hook state and worker team
- **R2.6**: Add `gt seance` equivalent: a structured protocol where a new session reads the predecessor's hook, transcript summary (from `.claude/progress/`), and identity file to reconstruct context
- **R2.7**: Identity file `last_seen` is updated every 60 seconds by the agent's own heartbeat cycle (for liveness detection)

#### Acceptance Criteria

- AC-2.1: Identity file created for every orchestrator session at spawn time
- AC-2.2: After killing a tmux session and re-running `spawn-orchestrator.sh` with the same initiative name, the new session reads the previous identity and hook, logging "Resuming identity: orch-{name}"
- AC-2.3: Workers from the previous session are still accessible if the team persists, or re-created with the same names
- AC-2.4: CWD-based role detection correctly identifies role for paths under `trees/`, `mayor/`, `crew/`, `polecats/` (Gas Town convention compatibility)
- AC-2.5: System 3 can detect stale identities (last_seen > 5 minutes) and trigger re-spawn

#### Files to Modify

| File | Change |
|------|--------|
| `.claude/hooks/session-start-orchestrator-detector.py` | Add CWD-based role detection and identity file reading |
| `.claude/scripts/spawn-orchestrator.sh` | Create/update identity file during spawn |
| `.claude/skills/system3-orchestrator/SKILL.md` | Add "Crash-Recovery Protocol" section with seance workflow |
| `.claude/output-styles/system3-meta-orchestrator.md` | Add identity management to "Oversight Team Management" section |
| NEW: `.claude/scripts/identity-manager.py` | Identity CRUD, liveness check, stale detection |
| NEW: `.claude/scripts/seance.py` | Structured predecessor context reconstruction |

---

### Epic 3: System 3 Output Style — GUPP & Identity Awareness

**Priority**: P0
**Rationale**: The system3-meta-orchestrator.md output style is loaded 100% of the time (per ADR-001). It must encode GUPP enforcement and crash-recovery identity as mandatory protocols, not optional skill references.

#### Problem

The current output style has no awareness of:
- Hook-based work persistence
- Crash recovery for orchestrators it spawns
- Identity inheritance across sessions
- Proactive hook checking at session start

#### Requirements

- **R3.1**: Add "GUPP Hook Protocol" section after "Immediate Session Initialization" in system3-meta-orchestrator.md
- **R3.2**: Section must instruct System 3 to: (a) check own hook at session start, (b) create hook if none exists, (c) update hook after every orchestrator spawn/completion
- **R3.3**: Add "Identity Registry" section to "Oversight Team Management" — System 3 must track all active identities and detect stale ones
- **R3.4**: Add "Crash Recovery Cycle" to "Monitoring Checklist" — when an identity goes stale, trigger seance + re-spawn
- **R3.5**: Modify "Post-Compaction Recovery" to include GUPP hook verification alongside team health check
- **R3.6**: Add GUPP-aware idle mode: when idle, check all hooks for stale work before memory consolidation

#### Acceptance Criteria

- AC-3.1: New System 3 session reads its own hook within the first 5 actions
- AC-3.2: Output style contains explicit GUPP enforcement language: "If there is work on your hook, YOU MUST RUN IT"
- AC-3.3: Identity registry section shows how to list, check, and recover stale identities
- AC-3.4: Post-compaction recovery section includes GUPP hook check as step 1 (before team health)

#### Files to Modify

| File | Change |
|------|--------|
| `.claude/output-styles/system3-meta-orchestrator.md` | Add GUPP Hook Protocol, Identity Registry, Crash Recovery Cycle sections; update Post-Compaction Recovery and Idle Mode |

---

### Epic 4: Orchestrator Output Style — GUPP Compliance & Self-Monitoring

**Priority**: P0
**Rationale**: Orchestrators must be GUPP-compliant so they maintain hooks that survive crashes, and self-monitoring so they detect their own context exhaustion before it causes a hard crash.

#### Problem

The current orchestrator output style (orchestrator.md) has no concept of:
- Maintaining a persistent hook for crash recovery
- Monitoring its own context window usage
- Triggering a graceful handoff before context exhaustion
- Self-reporting liveness to System 3

#### Requirements

- **R4.1**: Add "GUPP Compliance" as Core Principle #6 in orchestrator.md
- **R4.2**: Add "Hook Maintenance" section: orchestrators must update their hook after every `bd update`, worker completion, or phase transition
- **R4.3**: Add "Context Window Awareness" section: orchestrators should monitor their own context usage and trigger handoff at 80% capacity
- **R4.4**: Add "Liveness Heartbeat" section: orchestrators must update their identity file `last_seen` every 60 seconds (via a lightweight background agent or tool call side-effect)
- **R4.5**: Add "Graceful Handoff" protocol: save state to hook, notify System 3, end session; System 3 re-spawns with inherited identity

#### Acceptance Criteria

- AC-4.1: Orchestrator output style contains GUPP as an explicit core principle
- AC-4.2: Orchestrator updates hook file after every phase transition (preparation → assignment → completion → validation)
- AC-4.3: Orchestrator triggers graceful handoff before context exhaustion (no more hard crashes from full context)
- AC-4.4: System 3 can verify orchestrator liveness via identity file timestamps

#### Files to Modify

| File | Change |
|------|--------|
| `.claude/output-styles/orchestrator.md` | Add GUPP Compliance principle, Hook Maintenance, Context Window Awareness, Liveness Heartbeat, Graceful Handoff sections |

---

## Workstream B: Operational Supervisors (P1)

### Epic 5: Deacon Patrol Cycle — Proactive "Do Your Job" Signals

**Priority**: P1
**Rationale**: Gas Town's Deacon is a daemon that sends "Do Your Job" (DYFJ) signals propagating downward through the hierarchy every few minutes. Our s3-heartbeat scans for problems but doesn't actively nudge agents. The Deacon pattern turns passive monitoring into proactive supervision.

#### Problem

Currently, s3-heartbeat detects actionable situations (stale beads, crashed sessions, idle orchestrators) and reports findings to System 3 via SendMessage. But:
- System 3 must manually decide what to do with each finding
- There's no automatic "nudge" to idle agents
- Orchestrators that are waiting politely for user input (but should be working) go un-nudged
- The heartbeat has no authority to trigger DYFJ signals itself

#### Requirements

- **R5.1**: Upgrade s3-heartbeat SKILL.md with a "DYFJ Signal" action type: when detecting an idle agent, inject a nudge via `tmux send-keys`
- **R5.2**: DYFJ signals propagate: System 3 heartbeat nudges orchestrators; orchestrators nudge their workers (via SendMessage)
- **R5.3**: DYFJ signal content is role-aware: orchestrators get "Check bd ready, resume your hook"; workers get "Check TaskList for unclaimed work"
- **R5.4**: DYFJ cadence: every 300s (5 minutes) for orchestrators, every 600s (10 minutes) for System 3 (existing cycle)
- **R5.5**: DYFJ signals are logged to `.claude/state/dyfj-log.jsonl` for audit
- **R5.6**: s3-heartbeat gets a new scan target: "DYFJ compliance" — check if nudged agents actually responded within 120s

#### Acceptance Criteria

- AC-5.1: s3-heartbeat sends DYFJ nudges to idle orchestrator tmux sessions
- AC-5.2: Nudged orchestrators resume work within 2 minutes of receiving DYFJ
- AC-5.3: DYFJ log shows timestamped nudge-and-response pairs
- AC-5.4: System 3 output style references DYFJ as part of the monitoring protocol

#### Files to Modify

| File | Change |
|------|--------|
| `.claude/skills/s3-heartbeat/SKILL.md` | Add DYFJ Signal action type, propagation rules, compliance checking |
| `.claude/output-styles/system3-meta-orchestrator.md` | Add DYFJ patrol to Monitoring Checklist section |
| `.claude/skills/system3-orchestrator/SKILL.md` | Add DYFJ signal handling to Monitoring section |
| NEW: `.claude/scripts/dyfj-nudge.sh` | Inject DYFJ signal into tmux session with role-aware content |
| NEW: `.claude/state/dyfj-log.jsonl` | Audit log for DYFJ signals and responses |

---

### Epic 6: Witness Recovery Strategies — From Detection to Repair

**Priority**: P1
**Rationale**: Gas Town's Witness doesn't just detect problems — it actively helps stuck agents recover. Our s3-heartbeat detects stalls but leaves recovery to System 3. Adding Witness-style recovery strategies makes the system self-healing at the orchestrator level.

#### Problem

When s3-heartbeat detects a stuck orchestrator:
1. It reports to System 3 via SendMessage
2. System 3 must manually investigate and intervene
3. This adds latency (System 3 may be busy with other work)
4. Common recovery actions are predictable and automatable

#### Requirements

- **R6.1**: Define a recovery strategy catalog in `.claude/state/recovery-strategies.json` mapping stall patterns to automated actions
- **R6.2**: Strategies include: (a) DYFJ nudge, (b) seance restart (kill + re-spawn with identity), (c) context cycling (graceful handoff + re-spawn), (d) worker re-spawn (if workers are dead), (e) escalate to System 3 (if no automated fix)
- **R6.3**: s3-heartbeat attempts strategy (a) first, then (b), then (c), escalating only if all automated strategies fail
- **R6.4**: Each recovery attempt is logged with outcome (success/failure/escalated)
- **R6.5**: System 3 output style documents recovery strategy precedence and escalation rules
- **R6.6**: s3-guardian skill adds recovery verification: after automated recovery, guardian independently checks whether the agent actually resumed

#### Acceptance Criteria

- AC-6.1: s3-heartbeat autonomously recovers a stalled orchestrator via DYFJ nudge without System 3 intervention
- AC-6.2: If DYFJ fails, s3-heartbeat performs seance restart (kill tmux + re-spawn with identity) within 3 minutes
- AC-6.3: Recovery log shows escalation chain: nudge → seance → context-cycle → escalate
- AC-6.4: System 3 only receives escalation for truly unrecoverable situations
- AC-6.5: s3-guardian validates recovery success independently

#### Files to Modify

| File | Change |
|------|--------|
| `.claude/skills/s3-heartbeat/SKILL.md` | Add recovery strategy catalog, escalation chain, automated actions |
| `.claude/output-styles/system3-meta-orchestrator.md` | Add recovery strategy precedence to Monitoring section |
| `.claude/skills/s3-guardian/SKILL.md` | Add recovery verification to Phase 3 Monitoring |
| NEW: `.claude/state/recovery-strategies.json` | Stall pattern → recovery action mapping |
| NEW: `.claude/scripts/witness-recover.sh` | Execute recovery strategies (nudge, seance, context-cycle) |

---

### Epic 7: Refinery Merge Queue — One Merge at a Time

**Priority**: P1
**Rationale**: Gas Town's Refinery manages a merge queue: completed work is merged to main one change at a time, with conflict escalation. Currently, orchestrators merge directly, which causes conflict pileup when multiple orchestrators complete simultaneously.

#### Problem

When multiple orchestrators complete work in parallel:
- Each pushes to its own branch and creates a PR
- Merges happen in arbitrary order, causing cascading conflicts
- No single entity owns the merge sequence
- Failed merges require manual intervention from System 3

#### Requirements

- **R7.1**: Create a merge queue protocol in `.claude/scripts/refinery/merge-queue.py` that accepts merge requests and processes them sequentially
- **R7.2**: Orchestrators signal `merge_ready` (new beads status) instead of merging directly
- **R7.3**: System 3 output style delegates merge coordination to the Refinery pattern: "When orchestrators signal merge_ready, process merges sequentially"
- **R7.4**: Merge queue handles: (a) rebase onto latest main, (b) run tests, (c) merge if green, (d) escalate conflicts to System 3 if rebase fails
- **R7.5**: Beads lifecycle gets new status: `merge_ready` (after `impl_complete` validation) and `merged` (after successful merge)
- **R7.6**: Orchestrator output style removes direct merge instructions; replaces with "Signal merge_ready and continue to next task"
- **R7.7**: s3-guardian adds merge verification: confirm that merged code matches what was validated

#### Acceptance Criteria

- AC-7.1: Merge queue processes two simultaneous merge requests sequentially without conflicts
- AC-7.2: Failed rebase escalates to System 3 with specific conflict files identified
- AC-7.3: Beads lifecycle includes `merge_ready` → `merged` transitions
- AC-7.4: No orchestrator directly merges to main; all merges go through the queue
- AC-7.5: s3-guardian verifies post-merge code matches pre-merge validation

#### Files to Modify

| File | Change |
|------|--------|
| `.claude/output-styles/system3-meta-orchestrator.md` | Add "Refinery Merge Queue" section to Oversight Team Management |
| `.claude/output-styles/orchestrator.md` | Replace direct merge instructions with merge_ready signaling |
| `.claude/skills/orchestrator-multiagent/SKILL.md` | Update Implementation Complete Handoff to include merge_ready |
| `.claude/skills/orchestrator-multiagent/WORKFLOWS.md` | Update Progression phase to signal merge_ready instead of direct merge |
| `.claude/skills/s3-guardian/SKILL.md` | Add merge verification to Phase 4 validation |
| `.claude/skills/system3-orchestrator/SKILL.md` | Add Refinery to POST-COMPLETION CHECKLIST |
| NEW: `.claude/scripts/refinery/merge-queue.py` | Sequential merge queue with rebase, test, merge, escalate |
| NEW: `.claude/scripts/refinery/merge-request.sh` | CLI to submit a merge request to the queue |

---

### Epic 8: Context Cycling — Automated Handoff Before Exhaustion

**Priority**: P1
**Rationale**: Gas Town's `gt handoff` provides graceful session restarts when context windows fill up. Currently our agents crash when context is exhausted, losing in-progress work. Automated context cycling prevents this.

#### Problem

When a session's context window fills:
- The session crashes or becomes unresponsive
- In-progress work may not be committed
- The hook file may be stale (last updated several tool calls ago)
- System 3 must detect the crash and manually re-spawn

#### Requirements

- **R8.1**: Add context window monitoring to orchestrator output style: check `context_usage` percentage at every phase transition
- **R8.2**: At 75% context capacity, orchestrator triggers a "pre-handoff checkpoint": update hook, commit work, notify System 3
- **R8.3**: At 85% context capacity, orchestrator triggers graceful handoff: save full state to hook, send `handoff_requested` to System 3 via message bus, then stop
- **R8.4**: System 3 detects `handoff_requested`, runs seance protocol, re-spawns orchestrator with inherited identity
- **R8.5**: Post-compaction recovery in System 3 output style checks for pending handoff requests
- **R8.6**: s3-heartbeat adds "context exhaustion warning" scan: if an orchestrator's context is > 70%, send a preemptive alert

#### Acceptance Criteria

- AC-8.1: Orchestrator triggers pre-handoff checkpoint at 75% context capacity
- AC-8.2: Orchestrator performs graceful handoff at 85% — no data loss
- AC-8.3: System 3 re-spawns handed-off orchestrator within 60 seconds with full identity/hook inheritance
- AC-8.4: New session resumes work from the exact bead the previous session was working on
- AC-8.5: No more hard crashes from context exhaustion (all exits are graceful)

#### Files to Modify

| File | Change |
|------|--------|
| `.claude/output-styles/orchestrator.md` | Add context cycling protocol (75% checkpoint, 85% handoff) |
| `.claude/output-styles/system3-meta-orchestrator.md` | Add handoff detection to Post-Compaction Recovery and Monitoring |
| `.claude/skills/system3-orchestrator/SKILL.md` | Add handoff re-spawn to MONITORING CHECKLIST |
| `.claude/skills/s3-heartbeat/SKILL.md` | Add context exhaustion warning scan target |

---

## Workstream C: Ergonomics & Extensibility (P2)

### Epic 9: Ephemeral Wisps — Transient Coordination Beads

**Priority**: P2
**Rationale**: Gas Town's Wisps are ephemeral beads that exist only in the database, never written to Git, and are "burned" after use. This prevents coordination metadata from polluting the repository. Currently all our beads are git-tracked, which clutters history with transient orchestration state.

#### Problem

Orchestration-only beads (coordination signals, temporary work assignments, nudge acknowledgments) get committed to git alongside real work beads, cluttering the repository history and making `git log` noisy.

#### Requirements

- **R9.1**: Add a `--wisp` flag to `bd create` that creates beads in SQLite only (no JSONL git file)
- **R9.2**: Wisps have a TTL (default 24 hours) after which they are automatically purged
- **R9.3**: Wisps are visible in `bd list --include-wisps` but excluded by default from `bd list` and `bd ready`
- **R9.4**: Orchestrator output style uses wisps for: DYFJ acknowledgments, merge queue tickets, handoff coordination
- **R9.5**: s3-heartbeat purges expired wisps as part of its scan cycle

#### Acceptance Criteria

- AC-9.1: `bd create --wisp "Coordination signal"` creates a bead visible in SQLite but not in git
- AC-9.2: After 24 hours, wisp is automatically purged by heartbeat scan
- AC-9.3: `git log` shows no trace of wisp creation or deletion
- AC-9.4: `bd list` excludes wisps; `bd list --include-wisps` shows them

#### Files to Modify

| File | Change |
|------|--------|
| `.claude/output-styles/orchestrator.md` | Document wisp usage for transient coordination |
| `.claude/skills/orchestrator-multiagent/SKILL.md` | Add wisp examples for DYFJ ack, merge queue tickets |
| `.claude/skills/s3-heartbeat/SKILL.md` | Add wisp purge to scan cycle |
| EXTERNAL: Beads (`bd`) | Requires upstream wisp support (or wrapper script) |

---

### Epic 10: Crew Agents — Long-Lived Named Agents for Interactive Work

**Priority**: P2
**Rationale**: Gas Town's Crew are long-lived named agents for interactive work that report to the Overseer (human), not the Witness. They're useful for exploratory research, debugging, and ad-hoc tasks that don't fit the ephemeral Polecat (worker) pattern.

#### Problem

All our workers are ephemeral — spawned for a task, then decommissioned. There's no concept of a persistent named agent that the human can interact with directly for exploratory work, while still being part of the orchestration hierarchy.

#### Requirements

- **R10.1**: Add "Crew" concept to System 3 output style: long-lived named agents spawned by System 3 that report directly to the human (Overseer)
- **R10.2**: Crew agents have persistent identity files (like orchestrators) but no hook obligation — they work on-demand
- **R10.3**: Crew agents are spawned via `gt crew add {name}` equivalent: `./scripts/spawn-crew.sh {name} {initiative}`
- **R10.4**: Crew agents get their own git worktree (like Gas Town's `crew/{name}/rig/`)
- **R10.5**: System 3 tracks crew agents in the identity registry but does not manage their work — human directs them
- **R10.6**: Crew agents can read from the shared message bus but only the human or System 3 can assign them work

#### Acceptance Criteria

- AC-10.1: `spawn-crew.sh debug-helper auth` creates a named Crew agent with its own worktree
- AC-10.2: Crew agent persists across sessions with identity file
- AC-10.3: System 3 identity registry shows crew agents with role=crew
- AC-10.4: Crew agent is not nudged by DYFJ (exempt from patrol)

#### Files to Modify

| File | Change |
|------|--------|
| `.claude/output-styles/system3-meta-orchestrator.md` | Add Crew section to Oversight Team Management |
| `.claude/skills/system3-orchestrator/SKILL.md` | Add Crew spawn workflow |
| NEW: `.claude/scripts/spawn-crew.sh` | Crew agent spawn with worktree and identity |

---

### Epic 11: Real-Time Dashboard — Web-Based Monitoring

**Priority**: P2
**Rationale**: Gas Town provides a web dashboard with 13 interactive panels using htmx and SSE. Our monitoring relies on tmux capture-pane and message bus polling. A lightweight web dashboard would give the human real-time visibility without attaching to tmux sessions.

#### Problem

Monitoring multiple orchestrators requires attaching to individual tmux sessions or relying on System 3's filtered reports. There's no at-a-glance view of the entire hierarchy.

#### Requirements

- **R11.1**: Create a lightweight dashboard server (Python + htmx + SSE) at `.claude/scripts/dashboard/`
- **R11.2**: Dashboard reads from: identity registry, hook files, beads status, DYFJ log, merge queue, message bus
- **R11.3**: Panels include: Agent Registry (roles, status, last_seen), Pipeline Status (attractor DOT visualization), Merge Queue, Message Bus (recent messages), DYFJ Patrol Log
- **R11.4**: Dashboard is read-only — no write operations from the UI
- **R11.5**: Accessible via `gt dashboard` equivalent: `python .claude/scripts/dashboard/server.py --port 8899`
- **R11.6**: Auto-refreshes via SSE (no polling from browser)

#### Acceptance Criteria

- AC-11.1: Dashboard shows all active agents with liveness status (green/yellow/red)
- AC-11.2: Pipeline visualization renders the attractor DOT graph with node statuses
- AC-11.3: Dashboard updates within 5 seconds of state changes (via SSE)
- AC-11.4: Accessible at `http://localhost:8899` while agents are running

#### Files to Modify

| File | Change |
|------|--------|
| NEW: `.claude/scripts/dashboard/server.py` | htmx + SSE dashboard server |
| NEW: `.claude/scripts/dashboard/templates/index.html` | Dashboard UI template |
| NEW: `.claude/scripts/dashboard/static/` | CSS/JS assets |

---

### Epic 12: Multi-Runtime Presets — Beyond Claude Code

**Priority**: P2
**Rationale**: Gas Town supports multiple LLM runtimes (Claude Code, Gemini CLI, Codex, Cursor, etc.) via configurable presets. Our harness is Claude Code-only. Adding preset support future-proofs the architecture for multi-model orchestration.

#### Problem

All our agents run on Claude Code. As alternative runtimes mature (Codex, Gemini CLI, Cursor agents), we have no mechanism to spawn workers on different runtimes based on task type or cost optimization.

#### Requirements

- **R12.1**: Create a runtime preset registry at `.claude/state/runtime-presets.json` mapping runtime names to launch commands and hook compatibility
- **R12.2**: Orchestrator spawn workflow accepts `--runtime` flag (default: `claude`)
- **R12.3**: Presets include: `claude` (default), `codex` (OpenAI Codex), `gemini` (Gemini CLI), `cursor` (Cursor agent)
- **R12.4**: Each preset specifies: `launch_command`, `hook_support` (boolean), `gupp_compatible` (boolean), `config_file_fallback` (for runtimes that don't support `.claude/`)
- **R12.5**: System 3 output style documents multi-runtime capability but recommends Claude Code as default
- **R12.6**: Workers spawned on non-Claude runtimes get GUPP hooks via file-based fallback (not session hooks)

#### Acceptance Criteria

- AC-12.1: `runtime-presets.json` contains at least 3 runtime configurations
- AC-12.2: `spawn-orchestrator.sh --runtime gemini` launches a Gemini CLI session with compatible hooks
- AC-12.3: Non-Claude runtimes can read GUPP hook files and resume work
- AC-12.4: System 3 can mix runtimes across orchestrators (e.g., Claude for backend, Codex for frontend)

#### Files to Modify

| File | Change |
|------|--------|
| `.claude/skills/system3-orchestrator/SKILL.md` | Add --runtime flag to spawn workflow |
| `.claude/output-styles/system3-meta-orchestrator.md` | Document multi-runtime capability |
| `.claude/scripts/spawn-orchestrator.sh` | Add --runtime parameter with preset loading |
| NEW: `.claude/state/runtime-presets.json` | Runtime preset registry |

---

## Cross-Cutting Concerns

### Beads Status Lifecycle Update

The full lifecycle with Gas Town patterns incorporated:

```
open → in_progress → impl_complete → [S3 validates] → merge_ready → [Refinery merges] → merged → closed
                         ↑                                    ↑                                    │
                         └──── s3_rejected ───────────────────┘                                    │
                         └──── merge_conflict ────────────────────────────────────────┘            │
                                                                                                   │
                         └────────────────────────────────────────────────────────────────────────┘
```

New statuses: `merge_ready`, `merged`, `merge_conflict`

### s3-guardian Updates Summary

The s3-guardian skill receives updates across multiple epics:

| Epic | Guardian Change |
|------|----------------|
| Epic 2 (Identity) | Verify crash-recovery identity inheritance |
| Epic 5 (Deacon) | Monitor DYFJ compliance |
| Epic 6 (Witness) | Validate automated recovery success |
| Epic 7 (Refinery) | Verify post-merge code matches validation |
| Epic 8 (Context Cycling) | Verify graceful handoff preserves state |

### Skill Version Bumps

| Skill | Current Version | Target Version |
|-------|----------------|----------------|
| system3-orchestrator | 3.5.0 | 4.0.0 |
| orchestrator-multiagent | (unversioned) | 1.0.0 |
| s3-guardian | 0.1.0 | 0.2.0 |
| s3-heartbeat | (unversioned) | 1.0.0 |

### Output Style Change Summary

**system3-meta-orchestrator.md additions:**
1. GUPP Hook Protocol (after Immediate Session Initialization)
2. Identity Registry (in Oversight Team Management)
3. Crash Recovery Cycle (in Monitoring Checklist)
4. DYFJ Patrol (in Monitoring Checklist)
5. Refinery Merge Queue (in Oversight Team Management)
6. Crew Agents (in Oversight Team Management)
7. Context Cycling detection (in Post-Compaction Recovery)
8. Multi-Runtime notes (reference only)

**orchestrator.md additions:**
1. GUPP Compliance (Core Principle #6)
2. Hook Maintenance (new section)
3. Context Window Awareness (new section)
4. Liveness Heartbeat (new section)
5. Graceful Handoff (new section)
6. merge_ready signaling (replaces direct merge)
7. Wisp usage (transient coordination)

---

## Implementation Order

```
Phase 1 (P0): Crash-Resilient Foundation
├── Epic 1: GUPP Hook Enforcement
├── Epic 2: Crash-Recovery Identity
├── Epic 3: System 3 Output Style Updates
└── Epic 4: Orchestrator Output Style Updates

Phase 2 (P1): Operational Intelligence
├── Epic 5: Deacon Patrol Cycle
├── Epic 6: Witness Recovery Strategies
├── Epic 7: Refinery Merge Queue
└── Epic 8: Context Cycling

Phase 3 (P2): Ergonomics & Extensibility
├── Epic 9: Ephemeral Wisps
├── Epic 10: Crew Agents
├── Epic 11: Real-Time Dashboard
└── Epic 12: Multi-Runtime Presets
```

### Dependencies

```
Epic 1 (GUPP) ──► Epic 2 (Identity) ──► Epic 3 (S3 Output) ──► Epic 4 (Orch Output)
                                              │
Epic 5 (Deacon) ◄────────────────────────────┘
Epic 6 (Witness) ◄── Epic 5 (Deacon) + Epic 2 (Identity)
Epic 7 (Refinery) ◄── Epic 4 (Orch Output)
Epic 8 (Context Cycling) ◄── Epic 1 (GUPP) + Epic 2 (Identity)
Epic 9 (Wisps) ◄── Epic 5 (Deacon) [optional]
Epic 10 (Crew) ◄── Epic 2 (Identity)
Epic 11 (Dashboard) ◄── Epic 1 (GUPP) + Epic 2 (Identity)
Epic 12 (Multi-Runtime) ◄── Epic 1 (GUPP)
```

---

## Success Metrics

| Metric | Current | Target (Post-P0) | Target (Post-P1) |
|--------|---------|-------------------|-------------------|
| Session crash recovery time | Manual (5-15 min) | Automatic (<60s) | Automatic (<30s) with self-healing |
| Work lost per crash | Variable (0-100%) | 0% (hook-preserved) | 0% (hook + identity preserved) |
| Merge conflicts from parallel work | Frequent | Frequent | Rare (sequential merge queue) |
| Stalled agent detection time | 10-30 min (heartbeat) | 5-10 min | <5 min (DYFJ patrol) |
| Stalled agent recovery | Manual (System 3) | Manual with identity | Automatic (Witness strategies) |
| Human monitoring overhead | High (tmux attach) | Medium (identity registry) | Low (dashboard + DYFJ) |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hook file corruption during crash | Work state lost | Atomic writes via temp file + rename; git-backed persistence |
| DYFJ nudge spam (agent in legitimate wait) | Wasted tokens, confusion | Role-aware nudge content; respect "waiting for worker" state |
| Refinery merge queue bottleneck | Slow throughput | Queue processes merges in <60s; parallel test execution |
| Identity file conflicts (two sessions claim same identity) | Split-brain | Lock file + PID check; only one session per identity |
| Context cycling loses in-progress reasoning | Quality degradation | Checkpoint at 75% (before handoff threshold); seance reconstructs context |
| Dashboard security (exposed port) | Unauthorized access | Localhost-only binding; read-only; optional auth token |

---

## References

- [Gas Town Repository](https://github.com/steveyegge/gastown) — ~10k stars, 189k LOC Go
- [Beads Issue Tracker](https://github.com/steveyegge/beads) — Git-backed persistent state
- [Revenge of the Junior Developer](https://steveyegge.substack.com) — Yegge's prediction of agent orchestrators (March 2025)
- [PRD-S3-ATTRACTOR-001](PRD-S3-ATTRACTOR-001.md) — Existing attractor DOT graph orchestration
- [PRD-S3-AUTONOMY-001](PRD-S3-AUTONOMY-001.md) — S3 autonomy and s3-live team
- [PRD-S3-DOT-LIFECYCLE-001](PRD-S3-DOT-LIFECYCLE-001.md) — DOT lifecycle gaps

---

**Version**: 0.1.0 (Draft)
**Author**: System 3 Meta-Orchestrator
**Created**: 2026-02-23
**Last Updated**: 2026-02-23
