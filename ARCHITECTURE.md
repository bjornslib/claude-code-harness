# Claude Code Harness Architecture

Visual guide to understanding how the harness works across multiple projects.

## The Symlink Concept

```
┌──────────────────────────────────────────────────────────────────┐
│  ~/claude-harness (Central Repository)                           │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  .claude/                                                   │  │
│  │  ├── output-styles/    ← Agent behaviors                   │  │
│  │  ├── skills/           ← 20+ capabilities                  │  │
│  │  ├── hooks/            ← Lifecycle automation              │  │
│  │  ├── scripts/          ← CLI utilities + Attractor         │  │
│  │  └── settings.json     ← Base configuration                │  │
│  │                                                             │  │
│  │  cobuilder/            ← Orchestration Python package      │  │
│  │  .mcp.json             ← Your API keys                     │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
        ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
        │  Project A    │  │  Project B    │  │  Project C    │
        │               │  │               │  │               │
        │  .claude ─────┼──│  .claude ─────┼──│  .claude ─────┼──► All point to
        │     (symlink) │  │     (symlink) │  │     (symlink) │    central harness
        │               │  │               │  │               │
        │  .mcp.json ───┼──│  .mcp.json ───┼──│  .mcp.json    │
        │     (symlink) │  │     (symlink) │  │     (copy)    │◄── Can be copied
        │               │  │               │  │               │    for custom MCP
        └───────────────┘  └───────────────┘  └───────────────┘

        Update once in           All projects get updates automatically
        central harness    ──────────────────────────────────────────►
```

## Agent Architecture (SDK Mode)

The harness uses a **Guardian-led hierarchy** in SDK mode. Layers 0 and 1 have
collapsed into a single S3 Guardian role — the terminal-based session users
interact with directly.

```
┌─────────────────────────────────────────────────────────────────┐
│  S3 GUARDIAN (User-Facing Terminal Session)                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • Strategic planning, OKR tracking, acceptance tests     │  │
│  │  • Validates business outcomes (stop hook at this layer)  │  │
│  │  • In SDK mode: spawns Runner → which spawns Orchestrator │  │
│  │  • Can also spawn another Guardian for monitoring         │  │
│  │  • UUID-based completion promises (multi-session aware)   │  │
│  │                                                            │  │
│  │  Skills: s3-guardian/, completion-promise                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              │ (SDK mode only)                   │
│                              ▼                                   │
├─────────────────────────────────────────────────────────────────┤
│  RUNNER (SDK Mode Only)                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • Manages orchestrator lifecycle and reliability         │  │
│  │  • Spawned by Guardian; does NOT run in tmux              │  │
│  │  • Provides fault-tolerant orchestrator execution         │  │
│  │  • Reports back to Guardian on completion or failure      │  │
│  │                                                            │  │
│  │  Package: cobuilder/orchestration/pipeline_runner.py      │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              │ spawns                            │
│                              ▼                                   │
├─────────────────────────────────────────────────────────────────┤
│  ORCHESTRATOR                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • Feature coordination and task breakdown                │  │
│  │  • Investigate: Read/Grep/Glob                            │  │
│  │  • Delegate to workers via native Agent Teams             │  │
│  │  • NEVER: Edit/Write/MultiEdit directly                   │  │
│  │                                                            │  │
│  │  Skills: orchestrator-multiagent/                         │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              │ delegates via native teams        │
│                              ▼                                   │
├─────────────────────────────────────────────────────────────────┤
│  WORKERS (Specialists)                                          │
│  ┌───────────────┬───────────────┬───────────────────────────┐  │
│  │ Frontend Dev  │ Backend Eng   │ TDD Test Engineer        │  │
│  │               │               │                          │  │
│  │ • React/Next  │ • Python/API  │ • Write tests first      │  │
│  │ • Zustand     │ • PydanticAI  │ • Red-Green-Refactor     │  │
│  │ • Tailwind    │ • Supabase    │ • Browser validation     │  │
│  │ • Edit/Write  │ • Edit/Write  │ • API testing            │  │
│  └───────────────┴───────────────┴───────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Guardian → Runner Reliability Pattern

In SDK mode, the Guardian does not call the Orchestrator directly. Instead it
spawns a **Runner** subagent. This indirection dramatically increases
reliability: if an orchestrator crashes or stalls, the Runner can detect the
failure and restart it without the Guardian needing to intervene.

```
Guardian
  │
  ├── SDK mode ──► Runner ──► Orchestrator ──► Workers
  │                  │
  │                  └── On failure: restarts Orchestrator automatically
  │
  └── Monitor ──► Guardian (validation subagent, runs in background)
```

## CoBuilder Package

The `cobuilder/` Python package formalises the orchestration patterns that
were previously implicit in harness scripts:

```
cobuilder/
├── orchestration/              ← Agent coordination layer
│   ├── pipeline_runner.py      ← Manages full pipeline execution (Runner)
│   ├── identity_registry.py    ← Tracks agent identities across sessions
│   ├── spawn_orchestrator.py   ← Programmatic orchestrator spawning
│   ├── runner_hooks.py         ← Hook lifecycle management
│   ├── runner_models.py        ← Data models for pipeline state
│   ├── runner_tools.py         ← Tool wrappers for orchestrators
│   └── adapters/
│       ├── native_teams.py     ← Native Agent Teams adapter
│       └── stdout.py           ← Stdout capture adapter
│
├── pipeline/                   ← Pipeline stage implementations
│   ├── generate.py             ← Code generation stage
│   ├── validate.py             ← Validation stage
│   ├── checkpoint.py           ← Save/restore pipeline state
│   ├── dashboard.py            ← Real-time progress display
│   ├── signal_protocol.py      ← Agent-to-agent signalling
│   ├── transition.py           ← State machine transitions
│   └── ...                     ← node_ops, edge_ops, annotate, etc.
│
└── repomap/                    ← Repository mapping (from zerorepo)
    └── cli/                    ← CLI commands: init, sync, status
```

## Session Resilience System

```
┌──────────────────────────────────────────────────────────────────┐
│  Attractor System (.claude/scripts/attractor/ + cobuilder/)      │
│                                                                   │
│  IdentityRegistry ─── Tracks agent identities & health          │
│         │                                                         │
│  MergeQueue ──────── Serialises concurrent code changes          │
│         │                                                         │
│  HookManager ─────── Central hook dispatch (pre/post tool)       │
│         │                                                         │
│  SignalProtocol ──── Agent-to-agent messaging                    │
│         │                                                         │
│  GuardianAgent ───── Validation subagent (monitoring mode)       │
│         │                                                         │
│  RunnerAgent ─────── Executes pipeline stages (SDK mode only)    │
└──────────────────────────────────────────────────────────────────┘

Cyclic Validation Pattern (Guardian monitors Runner/Orchestrator):
────────────────────────────────────────────────────────────────────

Guardian                 Monitor Guardian               Orchestrator
   │                           │                              │
   │  Launch monitor ─────────►│                              │
   │                           │◄── Poll task state ──────────│
   │                           │    Validate work...          │
   │◄──── COMPLETE ────────────│                              │
   │  Handle result            │                              │
   │  Re-launch monitor ──────►│  (cycle repeats)             │
```

## Core Systems Integration

```
┌──────────────────────────────────────────────────────────────────┐
│  Task Master (PRD → Task Decomposition)                          │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  1. Parse PRD ─→ Generate tasks                            │  │
│  │  2. Analyze complexity ─→ Expand tasks                     │  │
│  │  3. Track status ─→ Next task recommendation              │  │
│  │  4. Sync to Beads ─→ Issue tracking                        │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  MCP Integration (9+ Servers)                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Sequential Thinking | Task Master | Context7 (Docs)       │  │
│  │  Perplexity | Brave Search | Serena | Hindsight | Beads    │  │
│  │  Chrome DevTools | GitHub | Playwright | More...           │  │
│  │                                                             │  │
│  │  Progressive Disclosure: Load only what's needed (90%↓)    │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Hooks System (Lifecycle Automation)

```
Session Lifecycle:
─────────────────

SessionStart
    │
    ├─→ Detect orchestrator mode
    ├─→ Load MCP skills registry
    └─→ Initialize session state

UserPromptSubmit (Before each user prompt)
    │
    └─→ Remind orchestrator of delegation rules

PostToolUse (After each tool execution)
    │
    └─→ Decision-time guidance injection

PreCompact (Before context compression)
    │
    └─→ Reload MCP skills (preserve after compaction)

Stop (Before session end — enforced at Guardian layer)
    │
    ├─→ Validate completion promise (UUID-based, multi-session)
    ├─→ Check open tasks
    ├─→ Confirm user intent to stop
    └─→ Allow/block stop based on state

Notification (On notifications)
    │
    └─→ Forward to webhook for external alerting
```

## Workflow: New Feature (SDK Mode)

```
1. User defines feature in PRD
        ↓
2. Guardian receives request; writes blind acceptance tests (s3-guardian)
        ↓
3. Guardian parses PRD with Task Master
        PRD ─→ tasks.json ─→ Beads issues
        ↓
4. Guardian spawns Runner (SDK mode)
        CoBuilder: IdentityRegistry.register()
        CoBuilder: PipelineRunner.start()
        ↓
5. Runner spawns Orchestrator (with automatic restart on failure)
        ↓
6. Orchestrator investigates codebase
        Read/Grep/Glob, analyzes dependencies
        ↓
7. Orchestrator delegates to Workers (native Agent Teams)
        ┌──────────────┬──────────────┬──────────────┐
        │ Frontend     │ Backend      │ TDD Engineer │
        │ Worker       │ Worker       │              │
        │              │              │              │
        │ Implements   │ Implements   │ Writes tests │
        │ UI           │ API          │ Validates    │
        └──────────────┴──────────────┴──────────────┘
        ↓
8. Workers report completion; CoBuilder MergeQueue serialises changes
        ↓
9. Guardian Monitor validates work (background subagent, cyclic pattern)
        Unit tests + API tests + E2E browser tests
        ↓
10. Guardian validates business outcomes against acceptance tests
        Feature complete! ✓
```

## File Structure in Projects

```
your-project/
├── .claude/                    ─→ Symlink to ~/claude-harness/.claude
│   ├── output-styles/          ← Auto-loaded from harness
│   ├── skills/                 ← All skills available
│   ├── hooks/                  ← Lifecycle automation
│   ├── scripts/attractor/      ← Session resilience scripts
│   ├── scripts/                ← CLI utilities
│   └── settings.json           ← Base configuration
│
├── cobuilder/                  ─→ Orchestration Python package
│   ├── orchestration/          ← Pipeline runner, identity, spawner
│   └── pipeline/               ← Generate, validate, checkpoint
│
├── .mcp.json                   ─→ Symlink or copy from harness
├── .claude/settings.local.json ─→ Project-specific overrides
└── your-code/                  ─→ Your actual application code
```

## Benefits Summary

| Aspect | Without Harness | With Harness |
|--------|----------------|--------------|
| Configuration | Copy to each project | Symlink once |
| Updates | Manual copying | `git pull` → all projects |
| Consistency | Drift over time | Always synchronized |
| Team sharing | Manual distribution | `git clone` → ready |
| Version control | Per-project chaos | Single source of truth |
| Resilience | Single-agent, fragile | Multi-session, identity-tracked |
| Pipeline state | Implicit / lost on crash | Checkpoint & resume via CoBuilder |
| Reliability | Manual restarts | Runner auto-restarts Orchestrators |

---

**Architecture Version**: 2.0.0
**Last Updated**: February 27, 2026
