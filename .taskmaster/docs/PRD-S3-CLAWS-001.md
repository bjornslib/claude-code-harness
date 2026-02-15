# PRD-S3-CLAWS-001: System 3 "With Claws" — Proactive Autonomous Operation

**Status**: DRAFT
**Author**: System 3 Meta-Orchestrator
**Date**: 2026-02-15
**Version**: 1.0
**Branch**: `system3-with-claws`
**Research**: `research-openclaw.md` (extended architecture analysis)

---

## 1. Problem Statement

Our System 3 meta-orchestrator is powerful but **fundamentally reactive** — it only works when a human types `ccsystem3` in a terminal. Between sessions, it is inert. It cannot:

- **Proactively check** if orchestrators are stuck, beads need attention, or work is ready
- **Communicate asynchronously** — the only interface is the terminal where it was launched
- **Preserve knowledge** across context compressions — PreCompact hook exists but doesn't trigger Hindsight
- **Learn systematically** from interactions — Hindsight retain happens ad-hoc, not structurally
- **Recover intelligently** from failures — orchestrator crashes get blanket retries, not classified recovery
- **Run background tasks** — no scheduling for briefings, health checks, or periodic reflections

OpenClaw's architecture (191k+ GitHub stars, fastest-growing AI agent framework) solves every one of these problems through four patterns: **Heartbeat** (proactive wake cycles), **Channel Adapters** (multi-platform communication), **Pre-compaction Memory Flush** (automatic knowledge preservation), and **Session Management** (context hygiene and concurrency control).

**The opportunity**: Adopt OpenClaw's proven patterns within our existing claude-harness-setup framework, transforming System 3 from a reactive tool into a proactive partner that monitors, communicates, learns, and improves autonomously.

---

## 2. Strategic Context

### 2.1 What We Already Have (Preserving These)

| Capability | Current State | Verdict |
|-----------|--------------|---------|
| Hindsight Memory (dual-bank) | 4 memory networks, knowledge graph, reflect/retain/recall | **Keep + Extend** |
| Output Styles | 100% load guarantee, behavioral configuration | **Keep** |
| Native Agent Teams | Orchestrator → Worker delegation | **Keep** |
| Worktree Isolation | Git worktrees for code isolation | **Keep** |
| Beads Issue Tracking | P0-P4 priorities, tags, dependencies | **Keep** |
| Validation Pipeline | Unit → E2E → PRD acceptance | **Keep** |
| Stop Gate | 6-step validation before session ends | **Keep** |
| Completion Promises | UUID-based session goal tracking | **Keep** |
| Message Bus | SQLite queue + signal files | **Replace with Channel Adapters** |
| tmux Monitoring | capture-pane polling | **Enhance with Heartbeat** |

### 2.2 What OpenClaw Teaches Us (New Capabilities)

| OpenClaw Pattern | Gap in System 3 | Proposed Solution |
|-----------------|-----------------|-------------------|
| Heartbeat (30-min wake cycle) | Reactive-only operation | **Epic 1**: Python heartbeat daemon with APScheduler |
| Channel Adapters (15+ platforms) | Terminal-only interaction | **Epic 2**: Google Chat MCP adapter |
| Pre-compaction Memory Flush | Knowledge lost on context compression | **Epic 3**: Automatic Hindsight retain in PreCompact hook |
| Session Transcript Indexing | Past sessions not searchable | **Epic 3**: Index session narratives in Hindsight |
| Error Classification | Blanket orchestrator retries | **Epic 4**: Classified failure types with targeted recovery |
| Adaptive Model Routing | Fixed model per role | **Epic 4**: Opus → Sonnet → Haiku based on task complexity |
| HEARTBEAT.md instructions | No proactive check configuration | **Epic 1**: Configurable heartbeat instructions |
| Command Queue Lanes | Heartbeat blocks user interaction | **Epic 1**: Separate lanes for proactive vs. interactive |
| Daily Session Logs | Ad-hoc memory retention | **Epic 3**: Structured daily logs with periodic distillation |
| USER.md (operator profile) | Scattered user preferences | **Epic 5**: Structured user preference learning |
| IDENTITY.md (self-model) | No capability self-tracking | **Epic 5**: Self-model with confidence levels |

### 2.3 Design Principles

1. **Existing systems first** — Extend Hindsight, hooks, and output styles rather than building new infrastructure
2. **Google Chat as primary async channel** — Not terminal replacement, but complement
3. **Cost-conscious** — Route heartbeat checks to Haiku; reserve Opus for strategic decisions
4. **Incremental adoption** — Each epic is independently valuable; no big-bang migration
5. **Security by default** — Google Chat restricted to workspace owner; no public endpoints

---

## 3. Epic Breakdown

### Epic 1: Heartbeat Daemon — Proactive Wake Cycles

**Goal**: Transform System 3 from reactive to proactive. A Haiku teammate keeps the Operator alive between work cycles, gathers context, relays user feedback, and wakes the Operator when action is needed.

#### Features

**F1.1: System 3 Communicator (Native Agent Team Teammate)**
- **Not a separate session** — a Haiku teammate within the System 3 Operator's own team
- Spawned by System 3 Operator as a background teammate:
  ```python
  TeamCreate(team_name="s3-live")
  Task(
      subagent_type="general-purpose",
      model="haiku",
      run_in_background=True,
      team_name="s3-live",
      name="s3-communicator",
      prompt="[Communicator skill: .claude/skills/system3-orchestrator/communicator/]"
  )
  ```
- Inherits ALL MCP tools from parent session (Hindsight, beads, future Google Chat MCP)
- Runs a heartbeat loop: sleep 600s (10 min) → check → sleep → check (configurable)
- Active hours configuration (default: 8 AM – 10 PM user local time)
- When actionable work found → `SendMessage(type="message", recipient="team-lead", ...)` → wakes Operator
- Cost: Haiku model + HEARTBEAT_OK early return = minimal token spend per cycle
- Skill definition: `.claude/skills/system3-orchestrator/communicator/SKILL.md`

**F1.2: HEARTBEAT.md Configuration**
- New file: `.claude/HEARTBEAT.md`
- Defines what to check on each wake cycle:
  - Beads status (`bd ready`, `bd list --status=in_progress`)
  - Orchestrator health (tmux session status)
  - Git status (uncommitted changes, PR reviews pending)
  - Hindsight active goals (`recall` from private bank)
  - Google Chat unread messages (Epic 2 dependency)
- Agent reads this file on each heartbeat and decides action

**F1.3: Cost-Optimized Model Routing**
- Heartbeat checks route to Haiku (fast, cheap)
- If actionable work found → escalate to Sonnet for planning
- If strategic decision needed → escalate to Opus
- `HEARTBEAT_OK` silent return when nothing is actionable (save tokens)
- Token usage tracking per heartbeat cycle

**F1.4: Cron Jobs for Scheduled Tasks**
- Morning briefing (7 AM, isolated session): summarize overnight beads changes, PR status, pending work
- End-of-day summary (6 PM, main session): log day's accomplishments, set next-day priorities
- Weekly reflection (Monday 8 AM, isolated session): `reflect(budget="high")` on private bank, consolidate patterns
- Job persistence: survive daemon restarts
- Configurable via `.claude/cron.json`

**F1.5: Command Queue Lanes**
- Separate lanes for heartbeat vs. user-initiated commands
- Heartbeat never blocks interactive commands
- Queue management: if heartbeat is running when user sends command, queue heartbeat completion and prioritize user

**F1.6: Operator Wake-Up (Communicator → SendMessage)**
- When Communicator (Haiku) detects work requiring the Operator's attention:
  - Beads with P0-P1 priority ready
  - User responds to option questions via Google Chat
  - Orchestrator failure requiring intervention
- Communicator sends structured message to team lead:
  ```python
  SendMessage(
      type="message",
      recipient="team-lead",
      content="WORK_FOUND: [context brief with beads state, user response, Hindsight recall]",
      summary="P0 work detected — beads ready"
  )
  ```
- Message appears as new conversation turn → wakes idle Operator
- Operator processes the context brief and takes action
- No new tmux session needed — Operator is the SAME session, just woken from idle

**F1.8: User Intermediary (Communicator as Async Bridge)**
- Instead of System 3 using AskUserQuestion (requires terminal), it delegates to Communicator:
  ```python
  # System 3 Operator needs user input:
  SendMessage(
      type="message",
      recipient="s3-communicator",
      content="ASK_USER: [question with 2-4 options, context, rationale]"
  )
  # System 3 goes idle, waiting for Communicator's reply
  ```
- Communicator receives the question → sends to Google Chat (Epic 2)
- User responds via Google Chat (from phone, laptop, anywhere)
- Communicator receives response → relays back to Operator:
  ```python
  SendMessage(
      type="message",
      recipient="team-lead",
      content="USER_RESPONSE: [user's answer with any additional context they provided]"
  )
  ```
- This makes the Communicator the **async intermediary** between System 3 and the user
- System 3 never blocks on terminal input — it goes idle and gets woken when the user responds
- Fallback: if Google Chat not configured, Communicator writes to `.claude/user-input-queue/` and polls

**F1.7: Session Start Recall (Post-Compaction Recovery)**
- New SessionStart hook (or enhancement of existing)
- On EVERY session start (including post-compaction restart):
  1. Recall from Hindsight: "What was I working on? What did I store before compaction?"
  2. Restore active goals, in-progress decisions, key context
  3. Check completion promises: any pending promises from previous session?
- Creates a complete memory cycle:
  ```
  PreCompact → retain to Hindsight → [context compressed] → SessionStart → recall from Hindsight
  ```
- Ensures knowledge is NEVER truly lost — preserved in Hindsight and recalled on restart
- Different from dual-bank startup (which queries general patterns); this specifically targets continuity of interrupted work

**F1.9: Stop Gate Communicator Check**
- New checker in `unified_stop_gate/communicator_checker.py`
- When System 3 Operator tries to stop:
  1. Check `~/.claude/teams/s3-live/config.json` for active Communicator member
  2. If Communicator exists and is active → exit 2 (BLOCK): "Communicator running — waiting for heartbeat"
  3. If no Communicator → exit 0 (PASS): allow stop
- This keeps the Operator alive while the Communicator monitors for work
- Communicator's SendMessage will eventually wake the Operator or signal clean exit

#### Acceptance Criteria (Epic 1)

- [ ] AC-1.1: Communicator spawns as Haiku teammate in `s3-live` team and runs heartbeat loop with 10-min sleep intervals
- [ ] AC-1.2: HEARTBEAT.md is read on each cycle; empty file causes early return with `HEARTBEAT_OK`
- [ ] AC-1.3: Heartbeat checks beads, tmux sessions, and git status; reports actionable items
- [ ] AC-1.4: Morning briefing runs at 7 AM in isolated session with summarized output
- [ ] AC-1.5: Token cost per heartbeat cycle is < 5000 tokens (Haiku, non-actionable cycle)
- [ ] AC-1.6: Communicator SendMessage wakes idle System 3 Operator (validated by PoC test)
- [ ] AC-1.7: Communicator detects P0 bead and wakes System 3 Operator with context brief
- [ ] AC-1.8: After context compaction, Session Start Recall restores active goals from Hindsight within 30 seconds
- [ ] AC-1.9: System 3 sends option question via Communicator; user responds via Google Chat; response relayed back to Operator
- [ ] AC-1.10: Stop gate blocks Operator exit while Communicator teammate is active in `~/.claude/teams/s3-live/`

---

### Epic 2: Google Chat Channel Adapter — Asynchronous Communication

**Goal**: Break the terminal dependency. System 3 can send and receive messages via Google Chat, enabling asynchronous interaction from any device.

#### Features

**F2.1: Google Chat MCP Server**
- New MCP server: `google-chat-bridge`
- Implements Google Chat API (Workspace API or webhook-based)
- Tools: `send_message`, `get_new_messages`, `mark_read`, `send_task_completion`, `get_stats`
- Configured in `.mcp.json` with service account credentials
- Runs as stdio MCP server

**F2.2: Inbound Message Routing**
- Google Chat webhook receives user messages
- Routes to System 3 session (if running) or queues for next heartbeat
- Message format: `{sender, text, timestamp, thread_id}`
- Thread-based conversation grouping
- Rate limiting to prevent abuse

**F2.3: Outbound Message Formatting**
- Progress updates: orchestrator status, task completions, beads changes
- Structured cards: task summaries with action buttons
- Markdown rendering for Google Chat format
- Chunking for long messages (Google Chat limit: 4096 characters)
- Media support: screenshots from validation, code snippets

**F2.4: Proactive Notifications**
- Heartbeat findings → Google Chat message (if actionable)
- Orchestrator completion → Google Chat notification with summary
- Blocked work → Google Chat alert asking for input
- Morning briefing → Google Chat delivery
- End-of-day summary → Google Chat delivery

**F2.5: Command Reception**
- User sends commands via Google Chat → System 3 receives and processes
- Supported commands: `status`, `bd ready`, `start [initiative]`, `approve`, `reject`
- Natural language understanding: "What's the status?" → run status check
- Response delivery back to same Google Chat thread

#### Acceptance Criteria (Epic 2)

- [ ] AC-2.1: MCP server starts and connects to Google Chat API
- [ ] AC-2.2: System 3 can send a message to a configured Google Chat space
- [ ] AC-2.3: User message in Google Chat is received and processed by System 3
- [ ] AC-2.4: Heartbeat findings are delivered to Google Chat within 5 minutes
- [ ] AC-2.5: Orchestrator completion triggers automatic Google Chat notification
- [ ] AC-2.6: User can send `status` in Google Chat and receive current beads/orchestrator status

---

### Epic 3: Enhanced Hindsight Integration — Systematic Learning

**Goal**: Transform ad-hoc memory retention into a systematic learning pipeline that captures, distills, and applies knowledge from every interaction.

#### Features

**F3.1: Pre-compaction Memory Flush**
- Enhance existing PreCompact hook to trigger Hindsight `retain()`
- Before context compression: save durable information to both banks
- Content to save: active goals, in-progress decisions, unresolved questions, key findings
- `NO_REPLY` pattern: if nothing to save, skip silently
- One flush per compaction cycle (tracked in session state)

**F3.2: Post-Session Narrative Logging**
- After each System 3 session: auto-generate session narrative
- Store as GEO chain (Goal → Experience → Outcome) in experience network
- Include: what was attempted, what succeeded, what failed, key decisions
- Link to beads IDs and orchestrator session IDs for traceability
- Searchable via `recall()` in future sessions

**F3.3: Daily Session Log Distillation**
- Cron job (end-of-day): review all session narratives from today
- `reflect(budget="mid")` to synthesize patterns across sessions
- Promote validated patterns to observation network
- Flag potential anti-patterns for review
- Update capability assessments based on session outcomes

**F3.4: Structured User Preference Learning**
- New Hindsight context: `user-preferences`
- Automatically retain: communication preferences, work hours, tool preferences, domain expertise
- Respect explicit "remember this" and "forget this" instructions
- Apply preferences in session initialization (wisdom injection)
- Store in project bank for team-wide consistency

**F3.5: Session Transcript Indexing**
- Index past session transcripts in Hindsight for searchable history
- Chunk transcripts (~400 tokens, 80-token overlap per OpenClaw pattern)
- Enable: "What did I do last Tuesday?" or "How did we solve the auth bug?"
- Privacy: only index main session transcripts, not worker sessions

#### Acceptance Criteria (Epic 3)

- [ ] AC-3.1: PreCompact hook triggers `retain()` with session context before compression
- [ ] AC-3.2: Post-session narrative is automatically generated and stored as GEO chain
- [ ] AC-3.3: Daily distillation cron synthesizes patterns from day's sessions
- [ ] AC-3.4: User preference "remember always use Sonnet for workers" is retained and applied in next session
- [ ] AC-3.5: Query "What did I work on yesterday?" returns relevant session transcripts from Hindsight

---

### Epic 4: Error Classification and Adaptive Resilience

**Goal**: Replace blanket orchestrator retries with intelligent failure classification and targeted recovery, reducing wasted compute and improving success rates.

#### Features

**F4.1: Failure Classification System**
- Classify orchestrator failures into categories:
  - `auth` — API key issues, credential expiry → rotate credentials
  - `resource` — context overflow, OOM, rate limits → downgrade model, reduce scope
  - `logic` — wrong approach, scope creep, infinite loops → fresh retry with different prompt
  - `scope` — exceeded time/token budget → decompose task further
  - `external` — Chrome extension missing, service down → wait and retry, or skip
- Store classification in beads metadata for pattern analysis

**F4.2: Targeted Recovery Strategies**
- Auth errors → rotate API key profile (per OpenClaw's auth profile rotation)
- Resource errors → downgrade model (Opus → Sonnet → Haiku), reduce context
- Logic errors → fresh retry with enhanced wisdom injection (anti-patterns from Hindsight)
- Scope errors → decompose task into smaller subtasks, retry each
- External errors → notify user via Google Chat, pause until resolved

**F4.3: Adaptive Model Routing**
- Default model per role: System 3 = Opus, Orchestrator = Sonnet, Worker = Haiku
- Adaptive upgrade: if Haiku worker fails on complex task → retry with Sonnet
- Adaptive downgrade: if Opus heartbeat is too expensive → route to Haiku
- Cost tracking per model per role for optimization

**F4.4: Failure Pattern Learning**
- After each failure + recovery: retain to Hindsight with classification
- `reflect(budget="mid")` on failure patterns weekly
- Build predictive model: "tasks involving X tend to fail with Y, pre-apply Z"
- Surface recurring failures to user as improvement suggestions

#### Acceptance Criteria (Epic 4)

- [ ] AC-4.1: Orchestrator failure is classified into one of 5 categories within 30 seconds
- [ ] AC-4.2: Auth errors trigger credential rotation without user intervention
- [ ] AC-4.3: Resource errors trigger model downgrade and successful retry
- [ ] AC-4.4: Failure classification is stored in Hindsight and queryable
- [ ] AC-4.5: Weekly reflection identifies top 3 recurring failure patterns

---

### Epic 5: Self-Model and Context Hygiene

**Goal**: Give System 3 an accurate model of its own capabilities, user preferences, and session health, enabling better autonomous decision-making.

#### Features

**F5.1: Capability Self-Model**
- Structured tracking of System 3's capabilities:
  - Backend orchestration: confidence level, success rate, common pitfalls
  - Frontend orchestration: confidence level, Chrome dependency status
  - PRD writing: quality metrics from user feedback
  - Research: tool preferences (Perplexity vs Brave vs context7)
- Updated after each session based on outcomes
- Used in autonomous goal selection: prefer tasks in high-confidence domains

**F5.2: Operator Profile (USER.md equivalent)**
- Structured file: `.claude/USER.md`
- Content: work hours, communication preferences, domain expertise, tool preferences
- Auto-populated from Hindsight observations
- Loaded in system prompt on session start
- Respects explicit user instructions ("I prefer morning briefings", "Never auto-commit")

**F5.3: Session Health Monitoring**
- Track context window usage in real-time
- Trigger pre-compaction flush at configurable threshold (default: 80% of window)
- Track token spending per session with alerts at configurable thresholds
- Session duration monitoring: suggest breaks or session rotation after 2 hours
- Stale context detection: flag when conversation history is too old to be useful

**F5.4: Identity and Disposition**
- `.claude/IDENTITY.md` — System 3's self-description and behavioral guidelines
- Disposition traits: confidence level, risk tolerance, communication style
- Evolves based on user feedback and session outcomes
- Used by Hindsight `reflect()` to calibrate responses

#### Acceptance Criteria (Epic 5)

- [ ] AC-5.1: Capability self-model is updated after each session with success/failure metrics
- [ ] AC-5.2: USER.md is loaded on session start and preferences are applied
- [ ] AC-5.3: Pre-compaction flush triggers at 80% context window usage
- [ ] AC-5.4: Session token spending is tracked and alert fires at configured threshold

---

## 4. Dependency Graph

```
Epic 1 (Communicator + Heartbeat) ──────────────────┐
    │                                             │
    ├── F1.1 Communicator Teammate Core           │
    ├── F1.2 HEARTBEAT.md (depends on F1.1)       │
    ├── F1.3 Cost Routing (depends on F1.1)       │
    ├── F1.4 Cron Jobs (depends on F1.1)          │
    ├── F1.5 Command Lanes (depends on F1.1)      │
    ├── F1.6 Operator Wake-Up (depends on F1.1)   │
    ├── F1.8 User Intermediary                    │
    │       (depends on F1.1 AND Epic 2)          │
    └── F1.9 Stop Gate Check (depends on F1.1)    │
                                                   │
Epic 2 (Google Chat) ────────────────────────────┤
    │                                             │
    ├── F2.1 MCP Server                           │
    ├── F2.2 Inbound Routing (depends on F2.1)    │
    ├── F2.3 Outbound Formatting (depends on F2.1)│
    ├── F2.4 Proactive Notifications              │
    │       (depends on F2.3 AND Epic 1)          │
    └── F2.5 Command Reception                    │
            (depends on F2.2)                     │
                                                   │
Epic 3 (Hindsight) ──────────────────────────────┤
    │                                             │
    ├── F3.1 Pre-compaction Flush (independent)   │
    ├── F3.2 Session Narratives (independent)     │
    ├── F3.3 Daily Distillation                   │
    │       (depends on F3.2 AND Epic 1 F1.4)     │
    ├── F3.4 User Preference Learning             │
    │       (independent)                          │
    └── F3.5 Transcript Indexing                  │
            (depends on F3.2)                      │
                                                   │
Epic 4 (Error Classification) ───────────────────┤
    │                                             │
    ├── F4.1 Failure Classification (independent) │
    ├── F4.2 Recovery Strategies                  │
    │       (depends on F4.1)                      │
    ├── F4.3 Adaptive Model Routing               │
    │       (depends on F4.1)                      │
    └── F4.4 Failure Pattern Learning             │
            (depends on F4.1 AND Epic 3 F3.2)     │
                                                   │
Epic 5 (Self-Model) ─────────────────────────────┘
    │
    ├── F5.1 Capability Self-Model
    │       (depends on Epic 3 F3.2)
    ├── F5.2 Operator Profile (independent)
    ├── F5.3 Session Health (independent)
    └── F5.4 Identity/Disposition
            (depends on F5.1)
```

**Parallel execution opportunities**:
- Epic 1 (Heartbeat) and Epic 2 (Google Chat) can run in parallel — they converge at F2.4
- Epic 3 (Hindsight) features F3.1, F3.2, F3.4 are all independent — start immediately
- Epic 4 (Error Classification) F4.1 is independent — start immediately
- Epic 5 F5.2 and F5.3 are independent — start immediately

**Critical path**: F1.1 → F1.4 → F3.3 (heartbeat daemon enables cron jobs, which enable daily distillation)

---

## 5. Implementation Approach

### Phase 1: Quick Wins (Week 1)
*Independent features that provide immediate value:*

- **F3.1**: Pre-compaction Memory Flush — single hook enhancement, highest ROI
- **F5.2**: USER.md — create file, load in session start hook
- **F5.3**: Session Health Monitoring — enhance statusline analyzer
- **F4.1**: Failure Classification — add error categorization to orchestrator monitoring

### Phase 2: Core Infrastructure (Weeks 2-3)
*Build the daemon and communication layer:*

- **F1.1**: Heartbeat Daemon Core — Python daemon with APScheduler
- **F1.2**: HEARTBEAT.md Configuration — define default check instructions
- **F2.1**: Google Chat MCP Server — webhook-based bridge
- **F2.3**: Outbound Message Formatting — structured messages to Google Chat

### Phase 3: Integration (Weeks 3-4)
*Connect the pieces:*

- **F1.3**: Cost-Optimized Model Routing
- **F1.4**: Cron Jobs (morning briefing, end-of-day summary)
- **F2.2**: Inbound Message Routing — receive commands from Google Chat
- **F2.4**: Proactive Notifications — heartbeat → Google Chat
- **F3.2**: Post-Session Narrative Logging

### Phase 4: Learning Loop (Weeks 4-5)
*Close the learning cycle:*

- **F3.3**: Daily Session Log Distillation
- **F3.4**: User Preference Learning
- **F4.2-F4.4**: Recovery strategies, adaptive routing, failure learning
- **F5.1**: Capability Self-Model
- **F5.4**: Identity and Disposition

### Phase 5: Polish and Refinement (Week 6)
- **F1.5**: Command Queue Lanes
- **F2.5**: Natural language command reception
- **F3.5**: Session Transcript Indexing
- End-to-end integration testing
- Cost optimization and token budget tuning

---

## 6. Technical Decisions

### 6.1 Why Native Agent Team Teammate (Not Separate Session or Python Daemon)?

OpenClaw uses a Node.js Gateway. Our first draft proposed a Python daemon, then a separate Claude Code Haiku tmux session. The final insight: **the Communicator is a native Agent Team teammate within the System 3 Operator's own session**.

**Three design iterations and why the final one wins:**

| Approach | Problem |
|----------|---------|
| Python daemon (APScheduler) | No native MCP access. New infrastructure to manage. |
| Separate Haiku tmux session | `--output-style` is not a CLI flag. Can't set agent behavior. Two independent sessions can't wake each other. |
| **Native teammate (chosen)** | Inherits MCP. SendMessage wakes team lead. Stop gate keeps session alive. Zero new infrastructure. |

**Why native teammate is superior:**
- **Inherits ALL MCP tools** — Hindsight, beads, Google Chat MCP available without configuration
- **SendMessage wakes team lead** — tested pattern: "Idle agents wake up from peer messages"
- **Stop gate integration** — new `communicator_checker.py` blocks Operator exit while Communicator is active
- **User intermediary** — relays option questions to Google Chat, user responds asynchronously, relays back
- **No new infrastructure** — no separate session, no process management, no coordination protocol
- **Same security context** — runs within the Operator's permission scope

**The Communicator ↔ Operator interaction:**
```
System 3 Operator (Opus, team lead of s3-live)
    │
    ├── Does strategic work (orchestrators, validation, etc.)
    │
    ├── Needs user input → SendMessage to s3-communicator: "ASK_USER: [options]"
    │   → Communicator → Google Chat → User responds → Communicator → SendMessage → Operator wakes
    │
    ├── Exhausts work → goes idle
    │   → Stop gate: "Communicator active — blocking exit"
    │   → Communicator heartbeat loop continues checking
    │
    └── Communicator finds work → SendMessage: "WORK_FOUND: [context]"
        → Operator wakes, processes work, cycle repeats
```

**Why not just run Opus all the time?** Cost. Opus idle costs tokens on every wake-up. The teammate model means Haiku does the cheap monitoring; Opus only runs when there's real work. Haiku heartbeat cost: ~$0.003/cycle. At 48 cycles/day: ~$0.15/day for the Communicator.

### 6.2 Why MCP Server for Google Chat (Not Direct API)?

- **Composable** — any MCP-compatible agent can use it
- **Configurable** — add/remove in `.mcp.json`
- **Isolated** — runs as separate process, crashes don't affect System 3
- **Standard interface** — tools are self-documenting via MCP schema
- **Future-proof** — swap Google Chat for Slack/Discord by swapping MCP server

### 6.3 Why Extend Hindsight (Not Build New Memory)?

- **Already running** — HTTP server on localhost:8888
- **4 memory networks** — World, Experience, Observation, Opinion already model what we need
- **Knowledge graph** — entity linking, temporal proximity, causal relationships
- **Reflect** — LLM-powered synthesis already acts as our "Guardian LLM"
- **Dual-bank** — private + project isolation already exists
- **What's missing**: automatic retention triggers, session transcript indexing, daily distillation

### 6.4 Why Not Run OpenClaw Directly?

- **191k lines of TypeScript** — massive surface area for security and maintenance
- **Full gateway architecture** — overkill for single-user, single-channel use case
- **ClawHub dependency risk** — skills registry has proven security vulnerabilities
- **Our stack is Python** — introducing Node.js gateway adds infrastructure complexity
- **We need the patterns, not the platform** — heartbeat, channel adapter, memory flush are architectural concepts, not coupled implementations

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Google Chat API rate limits | Medium | Low | Batch notifications, respect quotas |
| Heartbeat cost overrun | Medium | Medium | Haiku-first routing, `HEARTBEAT_OK` early return, token budget alerts |
| Hindsight server instability | Low | High | Health check in heartbeat, auto-restart, fallback to file-based logging |
| Context window exhaustion during long heartbeat | Low | Medium | Isolated sessions for complex checks, strict token budgets |
| Google Chat webhook security | Medium | High | Verify webhook signatures, restrict to workspace owner |
| Daemon process management | Medium | Low | Systemd/launchd service, health monitoring, auto-restart |

---

## 8. Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Time to discover actionable work | Manual check (~minutes) | < 30 minutes (heartbeat interval) | Heartbeat → action latency |
| Knowledge preserved across sessions | Ad-hoc (~50% of insights) | > 90% of durable insights retained | Hindsight recall accuracy |
| User response time (async) | Terminal-bound (must be at computer) | < 5 min via Google Chat | Message delivery latency |
| Orchestrator failure recovery | Blanket retry (~60% success) | Classified retry (~85% success) | Recovery success rate by category |
| Cost per heartbeat cycle (non-actionable) | N/A | < $0.01 (Haiku) | Token cost tracking |
| Session narrative coverage | ~20% of sessions | > 90% of sessions | Auto-generated narratives / total sessions |

---

## 9. Open Questions

1. **Google Chat authentication**: Service account (simpler, system-level) vs. OAuth (user-level, more secure)? Recommend: Service account for MVP, OAuth for multi-user.

2. **Heartbeat during active sessions**: Should the daemon pause heartbeats while a full System 3 session is running (to avoid interference), or run them in a separate lane? Recommend: Separate lane with lower priority.

3. **Transcript indexing scope**: Index all sessions including orchestrator/worker sessions, or only main System 3 sessions? Recommend: Main sessions only for MVP, expand later.

4. **Daemon hosting**: Run as macOS launchd service, or as a persistent tmux session, or as a Docker container? Recommend: launchd for reliability, tmux as fallback.

5. **Cost budget**: What's the acceptable monthly cost for proactive operation? OpenClaw users report $70-150/month for heavy use. With Haiku routing, we should target < $30/month.

---

## 10. Glossary

| Term | Definition |
|------|-----------|
| **Heartbeat** | Periodic wake cycle where the agent checks for actionable work without user prompting |
| **Channel Adapter** | Plugin that translates between a messaging platform's API and System 3's internal message format |
| **Pre-compaction Flush** | Automatic memory retention triggered before context window compression |
| **Command Queue Lane** | Separate execution queue preventing heartbeat and user commands from blocking each other |
| **GEO Chain** | Goal → Experience → Outcome narrative structure for episodic memory |
| **HEARTBEAT_OK** | Silent return signal indicating nothing actionable was found during a heartbeat check |
| **Active Hours** | Configurable time window during which heartbeats are enabled (cost optimization) |

---

**Version History**:
- v1.2 (2026-02-15): Communicator as native Agent Team teammate (not separate session). Added F1.8 (User Intermediary), F1.9 (Stop Gate Check). Updated AC-1.6 through AC-1.10. Rewrote section 6.1.
- v1.1 (2026-02-15): Added F1.6 (Operator Launcher), F1.7 (Session Start Recall). Changed from Python daemon to Claude Code Haiku session.
- v1.0 (2026-02-15): Initial draft based on OpenClaw architecture research
