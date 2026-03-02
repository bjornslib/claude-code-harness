---
title: "Composio Agent-Orchestrator vs Claude Code Harness: Architecture Comparison"
status: active
type: architecture
last_verified: 2026-03-02
grade: reference
---

# Composio Agent-Orchestrator vs Claude Code Harness

A comparative analysis of [ComposioHQ/agent-orchestrator](https://github.com/ComposioHQ/agent-orchestrator) and our 3-level Claude Code harness (System 3 / Orchestrator / Workers).

---

## 1. Project Overviews

### Composio Agent-Orchestrator

A TypeScript-based system for managing **fleets of AI coding agents** working in parallel on codebases. Each agent operates in its own git worktree with an isolated branch and PR. Agents autonomously fix CI failures, address review comments, and open PRs — humans supervise from a centralized dashboard.

**Core value proposition**: `ao spawn my-project 123` → agent picks up GitHub issue #123, creates a worktree, writes code, opens a PR, handles CI failures and review comments, and notifies you when it's done or stuck.

- **Language**: TypeScript (monorepo via pnpm)
- **Architecture**: 8-slot plugin system with swappable implementations
- **Default agents**: Claude Code, Codex, Aider
- **Default runtime**: tmux (alternatives: Docker, Kubernetes)
- **Dashboard**: Web UI on port 3000 + CLI (`ao status`)
- **Tests**: 3,288 test cases
- **License**: MIT

### Our Claude Code Harness

A configuration-only framework implementing a **3-level agent hierarchy** with independent validation, built entirely on Claude Code's native capabilities (output styles, skills, hooks, Agent Teams).

**Core value proposition**: A meta-cognitive orchestration stack where System 3 sets strategic goals and creates blind acceptance tests, Orchestrators coordinate workers through native Agent Teams, and Workers implement — with independent validation ensuring no level can self-report success.

- **Language**: Configuration (YAML, Markdown, Python/Bash scripts, JSON)
- **Architecture**: 3-tier hierarchy with strict separation of concerns
- **Agent runtime**: Claude Code only (native Agent Teams or ephemeral `Task()`)
- **Isolation**: Git worktrees (via tmux for orchestrators), session directories for state
- **Validation**: Independent blind acceptance tests + validation-test-agent
- **License**: Proprietary / Internal

---

## 2. Architecture Comparison

### Composio: Flat Plugin Architecture

```
┌─────────────────────────────────────────────┐
│              Dashboard / CLI                 │
├─────────────────────────────────────────────┤
│         LifecycleManager (state machine)     │
│         Reaction Engine (CI, reviews)        │
├─────────────────────────────────────────────┤
│         SessionManager (CRUD)                │
├────┬────┬────┬────┬────┬────┬────┬──────────┤
│ Rt │ Ag │ Ws │ Tr │SCM │ No │ Te │ Lf       │
│    │    │    │    │    │    │    │           │
│tmux│CC  │wt  │GH  │GH  │dsk │it2│ core     │
│dock│cdx │cln │lin │    │slk │web│           │
│k8s │aidr│    │    │    │whk │   │           │
└────┴────┴────┴────┴────┴────┴────┴──────────┘
     (8 pluggable slots, each swappable)
```

- **Flat hierarchy**: All agents are peers, managed by a single LifecycleManager
- **State machine**: `spawning → working → pr_open → ci_failed → ... → merged → done`
- **Reactions**: Configurable auto-responses (retry CI N times, forward reviews, escalate)
- **Human = guardian**: Humans supervise via dashboard; agents are autonomous runners

### Ours: 3-Level Cognitive Hierarchy

```
┌─────────────────────────────────────────────────────┐
│  SYSTEM 3 (Meta-Orchestrator)                        │
│  • Dual-bank memory (Hindsight)                      │
│  • Blind acceptance tests (independent rubric)       │
│  • DOT pipeline navigation                           │
│  • Validation-test-agent for closure                 │
├─────────────────────────────────────────────────────┤
│  ORCHESTRATOR (Team Lead)                            │
│  • Investigation-only (Read/Grep/Glob)               │
│  • Delegates via Native Agent Teams                  │
│  • Beads + TaskList coordination                     │
│  • Never edits code directly                         │
├─────────────────────────────────────────────────────┤
│  WORKERS (Specialists)                               │
│  • frontend-dev-expert, backend-solutions-engineer   │
│  • tdd-test-engineer, solution-architect             │
│  • Direct Edit/Write, TDD red-green-refactor         │
│  • Scope enforcement, Serena checkpoints             │
└─────────────────────────────────────────────────────┘
```

- **Hierarchical**: Strategic → Coordination → Implementation
- **Independent validation**: Acceptance tests live outside implementation repo
- **Meta-cognition**: System 3 reflects on its own reasoning via Hindsight
- **Strict boundaries**: Orchestrators cannot edit; workers cannot coordinate

---

## 3. Feature-by-Feature Comparison

| Feature | Composio | Ours |
|---------|----------|------|
| **Agent diversity** | Claude Code, Codex, Aider (pluggable) | Claude Code only |
| **Runtime isolation** | tmux, Docker, K8s (pluggable) | tmux + worktrees |
| **Issue tracking** | GitHub, Linear (pluggable) | Beads + Task Master |
| **CI feedback loop** | Automatic: detect failure → send logs → agent retries | Manual: worker runs tests, reports back |
| **Review feedback loop** | Automatic: detect review → forward comments → agent addresses | Manual: orchestrator reads reviews, creates tasks |
| **PR lifecycle** | Full: create → CI → review → merge (automated) | Partial: workers commit, orchestrator/S3 manages PRs |
| **Dashboard** | Web UI + CLI (`ao status`) | CLI only (statusline analyzer) |
| **State machine** | Formal 16-state FSM with transitions | Implicit via task status + bead lifecycle |
| **Plugin system** | 8 typed slots, any can be swapped | Skills (invokable) + Output Styles (automatic) |
| **Multi-agent coordination** | Flat: all agents independent | Hierarchical: 3 tiers with delegation |
| **Validation** | CI checks + human review | Independent blind tests + validation-test-agent |
| **Memory** | None (stateless between sessions) | Hindsight dual-bank (private + project) |
| **Strategic planning** | None (issue-driven) | System 3 PRDs, DOT pipelines, OKR tracking |
| **Self-reporting bias prevention** | None (agents report their own status) | Core design: blind rubric, independent validator |
| **Parallel agents** | Yes — multiple agents on different issues | Yes — multiple orchestrators in worktrees |
| **Session recovery** | `ao session restore` for crashed agents | Completion promises + stop gates |
| **Notifications** | Desktop, Slack, webhook (pluggable) | Google Chat hooks |
| **Configuration** | YAML (`agent-orchestrator.yaml`) | JSON + Markdown (settings.json, output-styles, skills) |
| **Test suite** | 3,288 tests (TypeScript) | Hook tests + completion state tests (Python) |
| **Codebase** | ~15k+ LoC TypeScript application | ~0 app code (configuration + scripts only) |

---

## 4. What Composio Has That We Don't

### 4.1 Automated CI/Review Feedback Loops

Composio's **reaction system** is its killer feature. When CI fails or a reviewer requests changes:

```yaml
reactions:
  ci_failed:
    auto: true
    action: send-to-agent
    maxRetries: 2
  changes_requested:
    auto: true
    action: send-to-agent
    escalateAfterMinutes: 30
  approved_and_green:
    auto: false
    action: notify
```

The system detects the event, gathers context (CI logs, review comments), and routes it back to the working agent automatically. Our harness requires manual orchestrator intervention for each iteration.

**Gap**: We have no equivalent automated event-reaction pipeline for CI and code reviews.

### 4.2 Agent Agnosticism

Composio can orchestrate Claude Code, Codex, or Aider — even mixing agents in the same fleet. Each agent plugin implements a common interface (`getLaunchCommand`, `detectActivity`, `getSessionInfo`).

**Gap**: We are locked to Claude Code. While this gives us deeper integration (Agent Teams, output styles), it means we can't leverage cheaper/faster models via alternative coding agents for simpler tasks.

### 4.3 Formal State Machine

Composio's LifecycleManager implements a proper 16-state FSM:

```
spawning → working → pr_open → ci_failed → working → pr_open →
review_pending → changes_requested → working → approved → mergeable → merged → done
```

With well-defined transitions, guards, and timeout-based escalation. Our state tracking is distributed across beads, TaskList, DOT pipelines, and completion promises — powerful but less formally defined.

**Gap**: No single state machine governs the lifecycle of a task from spawn to merge.

### 4.4 Web Dashboard

A real-time web UI showing all sessions, their states, PRs, CI status, and activity. Our equivalent is a CLI statusline analyzer and manual `ao status`-style checks.

**Gap**: No visual dashboard for monitoring multiple parallel agents.

### 4.5 Session Management CLI

Clean, discoverable CLI surface:

```bash
ao spawn project 123    # Start agent on issue
ao status               # Fleet overview
ao send session "msg"   # Send instruction to running agent
ao session restore X    # Recover crashed session
ao session kill X       # Terminate session
```

**Gap**: Our launch commands (`ccsystem3`, `launchorchestrator`) are functional but less polished and less discoverable.

### 4.6 Container-Based Isolation

Docker and Kubernetes runtime plugins allow true sandboxing — not just filesystem isolation (worktrees) but full process/network isolation.

**Gap**: Our worktree isolation prevents file conflicts but doesn't provide security boundaries between agents.

### 4.7 Comprehensive Test Suite

3,288 tests covering the full TypeScript stack. Our test coverage is limited to hooks and completion state scripts.

**Gap**: Far less automated testing of our orchestration logic itself.

---

## 5. What We Have That Composio Doesn't

### 5.1 Independent Validation (Anti-Self-Reporting Bias)

Our most significant architectural advantage. System 3 creates **blind acceptance tests stored outside the implementation repository** before the orchestrator even starts working. The orchestrator and workers never see the scoring rubric.

```
System 3 → writes Gherkin + executable tests → acceptance-tests/PRD-{ID}/
Orchestrator + Workers → implement the feature (never see tests)
validation-test-agent → runs blind tests → scores on 0.0-1.0 gradient
```

Composio agents self-report status. CI checks validate correctness but not completeness against business requirements.

**Our edge**: Structural prevention of the "it works on my machine" / "all tests pass" self-deception pattern.

### 5.2 Strategic Meta-Cognition (System 3)

No equivalent in Composio. System 3 provides:

- **PRD-driven planning**: Breaks business goals into epics → tasks → acceptance criteria
- **DOT pipeline navigation**: Tracks execution state as a directed graph
- **Dual-bank memory**: Private meta-wisdom + project-specific knowledge via Hindsight
- **Reflective reasoning**: `reflect(budget="high")` for deep strategic analysis
- **OKR tracking**: Connects implementation to business outcomes

Composio is issue-driven — it executes what's in the issue tracker. It doesn't reason about *why* an issue matters or *whether* the implementation actually satisfies the business need.

**Our edge**: Can autonomously plan multi-epic initiatives, not just execute pre-defined issues.

### 5.3 Hierarchical Separation of Concerns

The strict 3-level boundary (S3 validates, Orchestrators coordinate, Workers implement) prevents common failure modes:

- Workers can't skip validation by marking their own work done
- Orchestrators can't implement shortcuts instead of delegating
- System 3 can't blindly trust orchestrator completion reports

Composio's flat model means every agent is equally trusted and equally autonomous.

**Our edge**: Built-in checks and balances between cognitive layers.

### 5.4 Long-Term Memory

Hindsight memory banks persist learnings across sessions:

```python
mcp__hindsight__retain()   # Store architectural decisions, failure patterns
mcp__hindsight__recall()   # Retrieve context for new sessions
mcp__hindsight__reflect()  # Synthesize across memories
```

Composio agents are stateless — each spawn starts fresh with only the issue context.

**Our edge**: Organizational learning that improves decision-making over time.

### 5.5 Completion Promises & Stop Gates

Session-level goal tracking with acceptance criteria that must be met before a session can end:

```bash
cs-promise --create "User auth feature" --ac "AC-1: Login works" --ac "AC-2: Tokens expire"
# ... work happens ...
cs-verify --check  # Stop hook blocks if criteria unmet
```

Composio tracks session states but doesn't enforce that business goals are actually satisfied before marking "done."

**Our edge**: Structural guarantee that sessions don't silently drop incomplete work.

### 5.6 Scope Enforcement for Workers

Workers are constrained to modify only files listed in their task's scope field. Deviations require explicit scope expansion requests to the orchestrator.

```python
# Worker discovers it needs to modify an out-of-scope file
SendMessage(type="message", recipient="team-lead",
    content="SCOPE_EXPANSION_REQUEST: Need to modify auth.py for ...")
```

Composio agents have full repo access within their worktree.

**Our edge**: Prevents workers from making uncontrolled changes across the codebase.

### 5.7 Progressive Context Disclosure

Our MCP skills wrapper system provides 90%+ context savings:

```
Idle: ~150 tokens (registry only)
Using 1 skill: ~5k tokens (just that skill's docs)
Native MCP: 40-100k tokens (all servers loaded)
```

Composio doesn't have an equivalent context management concern since it runs agents as separate processes.

**Our edge**: Efficient use of limited context windows in LLM-based orchestration.

### 5.8 Configurable Output Styles with Guaranteed Loading

Output styles load automatically at 100% reliability (unlike skills at ~85%). This means critical behavioral constraints — like "orchestrators never edit code" — are structurally enforced, not dependent on skill invocation.

**Our edge**: Behavioral guarantees baked into the agent's identity, not just instructions.

---

## 6. Philosophical Differences

| Dimension | Composio | Ours |
|-----------|----------|------|
| **Trust model** | Trust agents; humans verify | Trust no layer; independent validation |
| **Planning** | External (issue tracker) | Internal (System 3 creates PRDs and plans) |
| **Agent identity** | Interchangeable workers | Specialized roles with enforced boundaries |
| **Feedback** | Automated event-reaction | Cognitive hierarchy with delegation |
| **Goal definition** | Issue description | PRD → Acceptance Criteria → Blind Tests |
| **Completion criteria** | CI green + review approved | Blind acceptance test score ≥ threshold |
| **Memory** | Stateless | Persistent dual-bank |
| **Extensibility** | Plugin interfaces (TypeScript) | Skills + Output Styles (Markdown + scripts) |

---

## 7. Summary: Strengths and Weaknesses

### Composio Strengths
1. Production-grade DevOps integration (CI/CD feedback loops)
2. Agent-agnostic — can orchestrate any coding agent
3. Clean, well-tested TypeScript codebase (3,288 tests)
4. Formal state machine with clear lifecycle transitions
5. Web dashboard for fleet monitoring
6. Container isolation options (Docker, K8s)
7. Low barrier to entry (`ao spawn project 123`)

### Composio Weaknesses
1. No validation beyond CI — agents self-report quality
2. Flat hierarchy — no separation between planning/coordination/implementation
3. Stateless — no learning across sessions
4. Issue-driven only — can't autonomously plan multi-epic initiatives
5. No scope enforcement — agents can modify anything in their worktree
6. No completion guarantees beyond state machine transitions

### Our Strengths
1. Independent validation eliminates self-reporting bias
2. 3-level hierarchy with enforced separation of concerns
3. Strategic meta-cognition (System 3 plans, reasons, reflects)
4. Long-term memory (Hindsight) for organizational learning
5. Completion promises prevent silent work abandonment
6. Scope enforcement prevents uncontrolled changes
7. Progressive context management (MCP skills wrapper)
8. Zero application code — pure configuration, portable across projects

### Our Weaknesses
1. No automated CI/review feedback loops
2. Locked to Claude Code (no agent diversity)
3. No web dashboard for visual monitoring
4. No formal state machine — distributed state across multiple systems
5. Limited test coverage of orchestration logic itself
6. Higher complexity / steeper learning curve
7. No container-based security isolation
8. Less polished CLI surface

---

## 8. Recommendations

### What We Should Consider Adopting from Composio

1. **Automated CI feedback routing**: Implement a reaction system that detects CI failures and routes logs + context back to the responsible worker automatically, rather than requiring orchestrator intervention.

2. **Formal lifecycle state machine**: Define a single FSM for task/session lifecycle that unifies beads, TaskList status, DOT pipeline state, and completion promises into one coherent model.

3. **Web dashboard**: Even a minimal status page would dramatically improve multi-orchestrator monitoring.

4. **Session management CLI**: Consolidate our launch scripts into a unified `ao`-style CLI with discoverable commands.

### What Composio Could Learn from Us

1. **Independent validation**: Adding blind acceptance tests that agents never see would catch quality issues CI misses.

2. **Hierarchical delegation**: Separating planning from implementation would reduce the "agent goes off the rails" problem.

3. **Long-term memory**: Retaining learnings across sessions would improve agent effectiveness over time.

4. **Completion guarantees**: Stop gates that enforce acceptance criteria would prevent premature "done" status.
