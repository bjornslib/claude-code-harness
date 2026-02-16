# PRD-NATIVE-TEAMS-001: Harness Evolution for Claude Code Native Agent Teams

**Status**: DRAFT (Open Questions Resolved)
**Author**: System 3 Meta-Orchestrator
**Date**: 2026-02-06
**Version**: 1.1

---

## 1. Problem Statement

Our Claude Code harness implements a sophisticated 3-level agent hierarchy (System 3 -> Orchestrator -> Worker) using custom infrastructure:

- **tmux-based session spawning** for orchestrators (brittle: Enter must be separate command, `ccorch` vs `launchcc` confusion, session detection failures)
- **SQLite message bus** with signal files and background polling monitors (complex: 7 CLI scripts, PostToolUse hook, background Haiku agents)
- **Manual orchestrator registry** (`active-orchestrators.json`)
- **Custom shutdown protocol** via message bus
- **tmux capture-pane monitoring** for orchestrator health checks

Claude Code has now released **native Agent Teams** (experimental), which provide built-in equivalents for several of these custom systems:

| Custom Infrastructure | Native Equivalent | Status |
|----------------------|-------------------|--------|
| tmux session spawning | `Teammate` tool + team creation | Experimental |
| SQLite message bus | Native `SendMessage` with auto-delivery | Experimental |
| Orchestrator registry | `~/.claude/teams/{name}/config.json` | Experimental |
| tmux monitoring | Split-pane display mode / idle notifications | Experimental |
| "No Edit/Write" enforcement | Delegate mode (Shift+Tab) | Experimental |
| Shutdown protocol | Native `shutdown_request`/`shutdown_response` | Experimental |

**The opportunity**: Replace our most brittle infrastructure (tmux spawning, message bus, monitoring) with native primitives while preserving our unique semantic layers (Hindsight memory, validation pipeline, beads tracking, stop gate, OKR tracking).

---

## 2. Strategic Context

### 2.1 What Native Agent Teams Provide

From the official Claude Code documentation:

1. **Team Architecture**: Lead session creates team, spawns teammates, coordinates work
2. **Shared Task List**: `~/.claude/tasks/{team-name}/` with pending/in_progress/completed states, dependency tracking, file-locking for race-free claiming
3. **Direct Messaging**: Teammates message each other (DM) or broadcast. Auto-delivery - no polling needed
4. **Idle Notifications**: Automatic notification when teammate finishes
5. **Plan Mode**: Require teammates to plan before implementing; lead approves/rejects
6. **Delegate Mode**: Restrict lead to coordination-only tools (no Edit/Write)
7. **Display Modes**: In-process (same terminal) or split-pane (tmux/iTerm2)
8. **Shutdown Protocol**: Graceful shutdown with approve/reject
9. **Context Isolation**: Each teammate gets own context window, loads CLAUDE.md/MCP/skills

### 2.2 What Our Harness Uniquely Provides (NOT in Native Teams)

| Capability | Purpose | Native Equivalent |
|-----------|---------|-------------------|
| **Hindsight Memory** (dual-bank) | Cross-session wisdom, pattern validation | None |
| **Validation-Agent** pipeline | Unit -> E2E -> PRD acceptance testing | None |
| **Beads Issue Tracking** | Rich metadata: priorities (P0-P4), tags, epics, KRs, comments | Basic task list only |
| **Stop Gate Pipeline** | 6-step validation before session ends | None |
| **Completion Promises** | UUID-based session goal tracking | None |
| **Worktree Isolation** | Git worktrees for code isolation | None (shared directory) |
| **OKR-Driven Development** | Business Epic -> Key Results -> Enabler Epics | None |
| **Process Supervision** | Hindsight reflect for pattern validation | None |
| **Wisdom Injection** | Inject learned patterns into spawned agents | None |
| **Output Styles** | Behavioral configuration for agent roles | None |

### 2.3 Known Limitations of Native Agent Teams

From the documentation:

1. **Experimental** - "disabled by default" with "known limitations around session resumption, task coordination, and shutdown behavior"
2. **No session resumption** - `/resume` and `/rewind` do not restore teammates
3. **Task status lag** - "teammates sometimes fail to mark tasks as completed"
4. **Shutdown can be slow** - teammates finish current tool call before stopping
5. **One team per session** - can't manage multiple teams simultaneously
6. **No nested teams** - "teammates cannot spawn their own teams"
7. **Higher token cost** - each teammate is a separate Claude instance
8. **Permissions set at spawn** - can't set per-teammate permissions at creation time

---

## 3. Proposed Architecture: Hybrid Model

### 3.1 Architecture Diagram (Revised v1.1)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LEVEL 1: SYSTEM 3 (Meta-Orchestrator) — OUTSIDE all native teams           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Hindsight Memory  │ Completion Promises │ OKR Tracking │ Stop Gate  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  Spawns orchestrators via tmux (proven System 3 → Orch pattern)             │
│  Monitors via tmux capture-pane + iTerm2 split-pane                         │
│  KEEPS: Autonomous steering, Hindsight, beads, stop gate, promises          │
│  System 3 is NOT a team member — it steers independently                    │
│                                                                             │
│  ┌──── tmux spawn ────────────────────────────────────────────────────┐    │
│  ▼                                                                    │    │
├──┼────────────────────────────────────────────────────────────────────┼────┤
│  │  LEVEL 2: ORCHESTRATOR AS NATIVE TEAM LEAD (delegate mode)        │    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │ Delegate Mode (HARD no Edit/Write) │ Beads │ Validation    │   │    │
│  │  └─────────────────────────────────────────────────────────────┘   │    │
│  │                                                                    │    │
│  │  NEW: Creates native team, manages workers as teammates            │    │
│  │  NEW: Delegate mode = hard enforcement (tools removed, not just    │    │
│  │       documented). Output style shifts to quality-of-coordination  │    │
│  │  NEW: Native SendMessage for worker communication (auto-delivery)  │    │
│  │  NEW: Shared task list for worker coordination (race-free claiming)│    │
│  │  NEW: Plan approval for high-risk worker tasks                     │    │
│  │  KEEPS: Beads for rich tracking, validation-agent pipeline         │    │
│  │                                                                    │    │
│  │  ┌──── native teammate spawn ─────────────────────────────────┐   │    │
│  │  ▼                                                             │   │    │
├──┼──┼─────────────────────────────────────────────────────────────┼───┼────┤
│  │  │  LEVEL 3: WORKERS AS NATIVE TEAMMATES                      │   │    │
│  │  │  ┌─────────────────────────────────────────────────────┐   │   │    │
│  │  │  │ frontend │ backend │ tdd-test │ solution-architect  │   │   │    │
│  │  │  └─────────────────────────────────────────────────────┘   │   │    │
│  │  │                                                             │   │    │
│  │  │  NEW: Full native teammates (not Task subagents)            │   │    │
│  │  │  NEW: Direct peer messaging (workers talk to each other!)   │   │    │
│  │  │  NEW: Self-claim tasks from shared task list                │   │    │
│  │  │  NEW: iTerm2 split-pane visibility for all workers          │   │    │
│  │  │  ACCEPTS: Higher token cost for better coordination         │   │    │
│  │  └─────────────────────────────────────────────────────────────┘   │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Key Architectural Decisions (Revised v1.1)

**Decision 1: System 3 stays OUTSIDE native teams.**
System 3 is an autonomous meta-orchestrator with completion promises, Hindsight memory, stop gate enforcement, and OKR tracking. Native agent teams don't provide autonomous steering — the team lead requires user interaction. By keeping System 3 outside, it retains the ability to manage orchestrators independently after the user defines a session promise.

**Decision 2: Orchestrator becomes native team LEAD.**
The orchestrator, spawned by System 3 via tmux (proven pattern), creates a native team and manages workers as teammates. It gains delegate mode (hard Edit/Write enforcement), native messaging (auto-delivery), shared task list (race-free claiming), and plan approval. The wisdom injection from System 3 becomes the spawn prompt — exactly what native teams call it.

**Decision 3: Workers become native teammates (not Task subagents).**
Workers gain direct peer messaging (frontend can talk to backend directly), self-claiming from the shared task list, and visibility via iTerm2 split-pane. The token cost increase (~2-3x per worker) is accepted for superior coordination, especially for cross-layer work (frontend + backend + tests).

**Decision 4: iTerm2 for split-pane display.**
Use iTerm2 with `it2 CLI` for split-pane worker visibility, not raw tmux panes. Requires enabling Python API in iTerm2 settings.

| Boundary | Current | Proposed | Rationale |
|----------|---------|----------|-----------|
| S3 <-> Orchestrator | tmux + SQLite message bus | **tmux spawn (unchanged)** | System 3 must stay outside teams for autonomous steering |
| Orchestrator <-> Worker | Task subagents | **Native teammates** | Peer messaging, self-claiming, split-pane visibility |

### 3.3 Why This Architecture (Not the v1.0 Proposal)

The v1.0 PRD proposed making orchestrators into teammates of System 3. This was rejected because:

1. **System 3 autonomy**: Agent teams require a user-interactive lead. System 3 is designed to steer *without* user input after receiving a session promise. Making it a team lead would constrain its autonomous behavior.
2. **Native teams are best at Orch<->Worker**: The biggest coordination challenges (peer messaging, file conflicts, task racing) exist between workers, not between System 3 and orchestrators.
3. **tmux is proven for S3<->Orch**: The System 3 to orchestrator spawning via tmux is well-understood and reliable. The native team benefits (auto-delivery messaging) are most valuable at the worker level where coordination is intensive.
4. **Anthropic also chose tmux**: The native split-pane mode uses tmux/iTerm2 under the hood, validating our architectural instinct.

---

## 4. Epics

### Epic 1: Enable Agent Teams + Compatibility Testing

**Priority**: P1
**Goal**: Safely enable native agent teams without disrupting existing workflows

**Tasks**:
1. Add `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` to `.claude/settings.json` env section
2. Test basic team creation with research/review tasks
3. Verify existing harness (hooks, skills, output styles) loads correctly for teammates
4. Measure token usage for team-based vs current approach
5. Document any incompatibilities with our hooks system

**Acceptance Criteria**:
- [ ] Agent teams enabled and functional
- [ ] Confirmed teammates don't need custom hooks (native team system manages lifecycle)
- [ ] Agent ID format documented: `{name}@{team-name}` from `~/.claude/teams/{name}/config.json`
- [ ] CLAUDE.md loads correctly for all teammates (confirmed per docs, verify empirically)
- [ ] Token usage comparison documented (baseline vs native teams)
- [ ] iTerm2 `it2 CLI` installed and Python API enabled

---

### Epic 2: Message Bus Migration (SQLite -> Native Messaging)

**Priority**: P1
**Goal**: Replace custom SQLite message bus with native auto-delivery messaging

**Current State**:
- 7 CLI scripts (`mb-init`, `mb-send`, `mb-recv`, `mb-register`, `mb-unregister`, `mb-list`, `mb-status`)
- SQLite database (`.claude/message-bus/queue.db`)
- Signal directory (`.claude/message-bus/signals/`)
- PostToolUse hook (`message-bus-signal-check.py`)
- Background Haiku monitor agents for polling

**Target State**:
- Use native `SendMessage` tool for all inter-agent communication
- Messages delivered automatically (no polling, no signal files)
- Audit trail maintained via Hindsight retention (not SQLite)

**Tasks**:
1. Map current message types to native equivalents:
   - `guidance` -> native `message` type
   - `completion` -> native `message` type
   - `broadcast` -> native `broadcast` type
   - `urgent` -> native `message` (with priority in content)
   - `query` -> native `message` type
2. Update System 3 output style to use `SendMessage` instead of `mb-send`
3. Update orchestrator output style to use `SendMessage` instead of `mb-send`/`mb-recv`
4. Remove or deprecate PostToolUse `message-bus-signal-check.py` hook
5. Remove or deprecate background monitor agent spawning for message polling
6. Retain message bus scripts as fallback for non-team scenarios

**Acceptance Criteria**:
- [ ] System 3 communicates with orchestrators via native `SendMessage`
- [ ] Orchestrators receive messages automatically (no polling)
- [ ] PostToolUse message hook disabled for team sessions
- [ ] Background polling monitors no longer spawned for team sessions
- [ ] Fallback to SQLite bus available for non-team scenarios

---

### Epic 3: Orchestrator as Native Team Lead

**Priority**: P1
**Goal**: Orchestrator creates native team and manages workers as teammates

**Current State**:
- System 3 spawns orchestrator via tmux (proven, stays unchanged)
- Orchestrator delegates to workers via Task subagents
- Workers return results but cannot message each other
- No peer coordination between workers

**Target State**:
- System 3 continues to spawn orchestrator via tmux (unchanged)
- Orchestrator, once spawned, creates a native team
- Workers are spawned as native teammates within that team
- Workers can message each other directly (frontend <-> backend coordination)
- Workers self-claim tasks from shared task list
- iTerm2 split-pane shows all worker activity

**Tasks**:
1. Update orchestrator output style:
   - Add native team creation as first action after skill loading
   - Add `Teammate(operation="spawnTeam")` pattern
   - Add worker spawning via `Task(team_name=..., name=...)`
   - Document peer messaging patterns for workers
2. Update orchestrator-multiagent skill:
   - Replace Task subagent worker patterns with native teammate patterns
   - Add shared task list coordination patterns
   - Add plan approval patterns for high-risk worker tasks
   - Add shutdown/cleanup workflow
3. Update System 3 spawn workflow (wisdom injection):
   - Include team creation instructions in spawn prompt
   - Set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in tmux env
   - Include `teammateMode: "tmux"` guidance for iTerm2 split-pane
4. Map environment variables:
   - `CLAUDE_SESSION_DIR` -> set before tmux launch (unchanged)
   - `CLAUDE_SESSION_ID` -> set before tmux launch (unchanged)
   - `CLAUDE_CODE_TASK_LIST_ID` -> becomes the team task list name
5. Test that System 3 can still monitor orchestrator via tmux capture-pane
   while orchestrator manages its own team internally

**Acceptance Criteria**:
- [ ] Orchestrator creates native team upon starting
- [ ] Workers spawned as native teammates with delegate mode for lead
- [ ] Workers can message each other directly (verified with cross-layer task)
- [ ] Workers self-claim tasks from shared task list
- [ ] System 3 can still monitor orchestrator via tmux
- [ ] iTerm2 split-pane shows worker activity within orchestrator session

---

### Epic 4: Orchestrator as Delegate-Mode Teammate

**Priority**: P2
**Goal**: Orchestrators leverage native delegate mode for enforcement

**Current State**:
- Orchestrator output style enforces "no Edit/Write" via documentation
- Hooks provide secondary enforcement
- Violations possible if output style not loaded

**Target State**:
- Delegate mode provides HARD enforcement (tool restriction, not just documentation)
- Output style provides behavioral guidance on top of delegate mode
- Double enforcement: native delegate mode + output style

**Tasks**:
1. Test delegate mode behavior with our orchestrator output style
2. Ensure delegate mode doesn't block tools orchestrators need:
   - `Task` (spawning workers) - should be allowed
   - `Read/Grep/Glob` (investigation) - should be allowed
   - `SendMessage` (messaging) - should be allowed
   - `Edit/Write` - should be blocked (correct!)
3. Update orchestrator skill to reference delegate mode as primary enforcement
4. Update output style to complement (not duplicate) delegate mode

**Acceptance Criteria**:
- [ ] Orchestrators in delegate mode can still investigate (Read/Grep/Glob)
- [ ] Orchestrators in delegate mode can still spawn workers (Task)
- [ ] Orchestrators in delegate mode CANNOT Edit/Write (hard enforcement)
- [ ] Output style provides behavioral guidance complementary to delegate mode

---

### Epic 5: Plan Approval Integration

**Priority**: P2
**Goal**: Use native plan approval for worker oversight when needed

**Current State**:
- No formal plan approval mechanism for workers
- Workers implement immediately upon receiving task

**Target State**:
- Critical workers can be spawned with `plan_mode_required`
- Orchestrator reviews and approves worker plans before implementation
- Used selectively for high-risk changes (database schema, auth, etc.)

**Tasks**:
1. Identify which worker types benefit from plan approval
2. Test plan approval workflow with frontend-dev-expert and backend-solutions-engineer
3. Update orchestrator skill with plan approval patterns
4. Define criteria for when plan approval is required vs optional

**Acceptance Criteria**:
- [ ] Plan approval works for at least one worker type
- [ ] Orchestrator can approve/reject plans with feedback
- [ ] Plan approval criteria documented in orchestrator skill

---

### Epic 6: Validation-Agent as Team Participant

**Priority**: P2
**Goal**: Ensure validation-agent works seamlessly within native team context

**Current State**:
- Validation-agent spawned as Task subagent by orchestrators
- Also spawned as background monitor by System 3

**Target State**:
- Validation-agent continues as Task subagent for orchestrator-spawned validation
- System 3 can optionally spawn validation-agent as a teammate for long-running monitoring
- Native idle notifications replace custom monitor wake-up patterns

**Tasks**:
1. Test validation-agent as Task subagent within team context (should work unchanged)
2. Test validation-agent as dedicated teammate for monitoring
3. Compare: teammate monitor vs current background Sonnet monitor pattern
4. Update System 3 monitoring patterns if teammate approach is superior

**Acceptance Criteria**:
- [ ] validation-agent works as Task subagent within teams (no regression)
- [ ] Monitoring comparison documented (teammate vs background task)
- [ ] Preferred monitoring pattern decided and documented

---

### Epic 7: Display Mode and Monitoring Integration

**Priority**: P3
**Goal**: Leverage native display modes for orchestrator monitoring

**Current State**:
- `tmux capture-pane -t orch-[name] -p | tail -30` for monitoring
- Background Haiku watchers for multi-orchestrator monitoring
- Manual `tmux attach-session` for debugging

**Target State**:
- Split-pane mode provides real-time visibility into all orchestrators
- `Shift+Up/Down` for switching between orchestrators
- Direct interaction with specific orchestrators via pane selection

**Tasks**:
1. Test split-pane mode with multiple orchestrator teammates
2. Verify tmux/iTerm2 compatibility
3. Update monitoring documentation
4. Define when to use split-pane vs in-process mode

**Acceptance Criteria**:
- [ ] Split-pane mode works for 2-3 simultaneous orchestrators
- [ ] System 3 can monitor all orchestrators visually
- [ ] Direct interaction with specific orchestrator possible via pane selection

---

## 5. Non-Goals (Explicitly OUT of Scope)

| Item | Reason |
|------|--------|
| Replace beads with native task list | Beads provide richer metadata (P0-P4 priorities, tags, epics, KRs, comments) |
| Remove Hindsight memory | No native equivalent; core strategic advantage |
| Remove stop gate pipeline | No native session completion verification |
| Remove completion promises | No native goal tracking |
| Remove output styles | Behavioral configuration beyond what delegate mode provides |
| Remove worktree isolation | Native teams share directory; worktrees still needed for code isolation |
| Make System 3 a team member | System 3 must stay outside teams for autonomous steering |
| Remove OKR/business outcome tracking | No native equivalent |

---

## 6. Migration Strategy: Phased Rollout

### Phase 1: Enable and Experiment (Epics 1)
- **Risk**: Low
- **Duration**: 1-2 sessions
- **Rollback**: Disable env var
- Enable agent teams feature flag
- Test with research/review tasks (not implementation)
- Measure token usage, reliability, coordination quality
- Document incompatibilities

### Phase 2: Message Bus + Team Creation (Epics 2, 3)
- **Risk**: Medium
- **Duration**: 3-5 sessions
- **Rollback**: Revert to tmux + SQLite bus
- Replace tmux spawning with native team creation
- Replace SQLite messaging with native messaging
- Keep SQLite bus as fallback
- Run parallel: native + fallback for 2 sessions

### Phase 3: Delegate Mode + Validation (Epics 4, 5, 6)
- **Risk**: Medium
- **Duration**: 2-3 sessions
- **Rollback**: Revert delegate mode, keep output style enforcement
- Enable delegate mode for orchestrators
- Test plan approval for high-risk workers
- Validate validation-agent compatibility

### Phase 4: Display + Cleanup (Epic 7 + Deprecation)
- **Risk**: Low
- **Duration**: 1-2 sessions
- Integrate split-pane monitoring
- Deprecate (not delete) tmux-based scripts
- Update all documentation
- Final token usage comparison

---

## 7. Success Metrics

| Metric | Current Baseline | Target |
|--------|-----------------|--------|
| tmux-related spawn failures | ~15% of sessions | 0% (native spawning) |
| Message delivery latency | 3-10s (polling) | <1s (auto-delivery) |
| Lines of custom infra code | ~2000+ (message bus + tmux scripts) | ~500 (adapters only) |
| Monitoring setup complexity | 5+ agents (Haiku watchers + Sonnet monitors) | 1 (split-pane display) |
| Token cost per orchestrator session | Baseline | <30% increase acceptable |
| Quality regression | 0 | 0 (must maintain) |

---

## 8. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| "Experimental" features change/break | High | Medium | Keep fallback (tmux + SQLite), phase rollout |
| Token cost too high | Medium | Medium | Use native teams for S3<->Orch only; keep Task subagents for workers |
| No session resumption | Medium | High (confirmed) | Design for stateless teammates; Hindsight provides continuity |
| Task status lag | Medium | Medium (confirmed) | validation-agent double-checks task status before closure |
| One team per session | Medium | High (confirmed) | S3 manages one team; multiple orchestrators as teammates within it |
| No nested teams | High | High (confirmed) | Hybrid model: native teams for S3<->Orch, Task subagents for Orch<->Worker |

---

## 9. Dependencies

| Dependency | Type | Status |
|-----------|------|--------|
| Claude Code agent teams feature | External | Experimental (enabled via env var) |
| tmux/iTerm2 for split-pane mode | External | Available on macOS |
| Existing harness (hooks, skills, output styles) | Internal | Stable |
| Hindsight MCP server | Internal | Operational |
| Beads plugin | Internal | Operational |

---

## 10. Open Questions (All Resolved)

| # | Question | Resolution | Rationale |
|---|----------|------------|-----------|
| 1 | Does delegate mode allow Task tool for spawning workers? | **Yes** | System 3 creates shared task list; delegate mode allows "spawning, messaging, shutting down teammates, and managing tasks" per docs |
| 2 | Do teammates load project CLAUDE.md correctly? | **Yes, per documentation** | PDF confirms teammates "load the same project context as a regular session: CLAUDE.md, MCP servers, and skills." Verify in Epic 1 |
| 3 | Do our hooks fire correctly for teammates? | **No changes needed** | Teammates are ephemeral workers managed by native team system — they don't need our custom hooks (stop gate, message bus, orchestrator detection). The lead (orchestrator) is spawned via tmux with `CLAUDE_SESSION_ID=orch-*`, so all existing hooks work unchanged. In-process teammates share the lead's process; split-pane teammates could get an early-exit guard if needed |
| 4 | Are native team tasks the same as TaskCreate/TaskList? | **Yes, same system** | Same path pattern (`~/.claude/tasks/{team-name}/`), same states, same dependency model |
| 5 | Is iTerm2 split-pane reliable for monitoring? | **Selected iTerm2** | Use iTerm2 with `it2 CLI` and Python API enabled. Preferred over raw tmux panes |
| 6 | Token cost at scale? | **Accept higher cost** | ~2-3x per worker accepted for superior coordination (peer messaging, self-claiming). Cross-layer work (frontend + backend + tests) benefits most |

---

## Appendix A: Feature Comparison Matrix

| Feature | Our Harness | Native Teams | Winner |
|---------|-------------|-------------|--------|
| Session spawning | tmux (brittle) | Native `Teammate` tool | **Native** |
| Messaging | SQLite + polling | Auto-delivery | **Native** |
| Task coordination | Custom + beads | Shared task list | **Tie** (different strengths) |
| Delegation enforcement | Output style + hooks | Delegate mode | **Native** (hard enforcement) |
| Plan approval | Not implemented | Built-in | **Native** |
| Monitoring | tmux capture-pane | Split-pane display | **Native** |
| Shutdown | Custom message type | Built-in protocol | **Native** |
| Memory | Hindsight (dual-bank) | None | **Our Harness** |
| Validation | validation-agent pipeline | None | **Our Harness** |
| Issue tracking | Beads (rich metadata) | Basic task list | **Our Harness** |
| Session verification | Stop gate (6-step) | None | **Our Harness** |
| Goal tracking | Completion promises | None | **Our Harness** |
| Business outcomes | OKR tracking | None | **Our Harness** |
| Code isolation | Git worktrees | Shared directory | **Our Harness** |
| Multi-level hierarchy | 3 levels | 2 levels (no nesting) | **Our Harness** |
| Token efficiency | Task subagents (lower) | Full context per teammate | **Our Harness** (accepted trade-off) |
| Cross-agent messaging | Leader-mediated only | Direct peer messaging | **Native** |
| Session resumption | tmux persists | No resumption | **Our Harness** |

**Score**: Our Harness: 9 | Native: 7 | Tie: 1

**Conclusion**: Hybrid model leverages native strengths (spawning, messaging, enforcement, monitoring) while preserving our unique capabilities (memory, validation, tracking, hierarchy).

---

## Appendix B: Code Artifacts to Modify

### Files to UPDATE (adapt to native teams)

| File | Change |
|------|--------|
| `.claude/output-styles/system3-meta-orchestrator.md` | Replace tmux patterns with native team patterns |
| `.claude/skills/system3-orchestrator/SKILL.md` | Replace spawn workflow with `Teammate` tool |
| `.claude/skills/orchestrator-multiagent/SKILL.md` | Add native messaging patterns |
| `.claude/output-styles/orchestrator.md` | Reference delegate mode |
| `.claude/settings.json` | Add `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` |
| `.claude/documentation/MESSAGE_BUS_ARCHITECTURE.md` | Document hybrid (native + fallback) |

### Files to DEPRECATE (keep as fallback)

| File | Reason |
|------|--------|
| `.claude/scripts/message-bus/mb-*` | Replaced by native messaging (keep for non-team use) |
| `.claude/hooks/message-bus-signal-check.py` | Replaced by auto-delivery (keep for non-team use) |
| `.claude/state/active-orchestrators.json` | Replaced by native team config |
| `.claude/skills/system3-orchestrator/scripts/spawn-orchestrator.sh` | Replaced by native spawning |

### Files UNCHANGED

| File | Reason |
|------|--------|
| `.claude/hooks/unified-stop-gate.sh` | No native equivalent |
| `.claude/hooks/unified_stop_gate/*` | No native equivalent |
| `.claude/scripts/completion-state/*` | No native equivalent |
| `.claude/agents/validation-agent.md` | Validation pipeline preserved |
| All Hindsight integration | No native equivalent |
| All beads integration | Richer than native tasks |
