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
│  │  ├── scripts/          ← CLI utilities                     │  │
│  │  └── settings.json     ← Base configuration                │  │
│  │                                                             │  │
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

## Three-Level Agent Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│  LEVEL 1: System 3 (Meta-Orchestrator)                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • Strategic planning and OKR tracking                    │  │
│  │  • Spawns orchestrators for epics/initiatives             │  │
│  │  • Business outcome validation                            │  │
│  │  • Independent validation coordinator                     │  │
│  │                                                            │  │
│  │  Output Style: system3-meta-orchestrator.md               │  │
│  │  Skills: system3-orchestrator/, completion-promise        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              │ spawns & coordinates              │
│                              ▼                                   │
├─────────────────────────────────────────────────────────────────┤
│  LEVEL 2: Orchestrators                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • Feature coordination and task breakdown                │  │
│  │  • Investigate: Read/Grep/Glob                            │  │
│  │  • Delegate: Launch workers via tmux                      │  │
│  │  • Monitor: Track worker progress                         │  │
│  │  • NEVER: Edit/Write/MultiEdit directly                   │  │
│  │                                                            │  │
│  │  Output Style: orchestrator.md                            │  │
│  │  Skills: orchestrator-multiagent/                         │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              │ delegates via tmux                │
│                              ▼                                   │
├─────────────────────────────────────────────────────────────────┤
│  LEVEL 3: Workers (Specialists)                                 │
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

## Core Systems Integration

```
┌──────────────────────────────────────────────────────────────────┐
│  Task Master (PRD → Task Decomposition)                          │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  1. Parse PRD ─→ Generate tasks                            │  │
│  │  2. Analyze complexity ─→ Expand tasks                     │  │
│  │  3. Track status ─→ Next task recommendation              │  │
│  │  4. Sync to Beads ─→ Issue tracking                        │  │
│  │                                                             │  │
│  │  Commands: /project:tm/*                                   │  │
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

Stop (Before session end)
    │
    ├─→ Validate completion promise
    ├─→ Check open tasks
    ├─→ Confirm user intent to stop
    └─→ Allow/block stop based on state

Notification (On notifications)
    │
    └─→ Forward to webhook for external alerting
```

## Skills System (20+ Capabilities)

```
Orchestration:
├── system3-orchestrator      ─→ Strategic planning
├── orchestrator-multiagent   ─→ Worker delegation
├── completion-promise        ─→ Session goal tracking
Development:
├── frontend-design           ─→ React/UI patterns
├── backend-solutions         ─→ Python/API patterns
├── tdd-test-engineer         ─→ Test-driven development
└── solution-architect        ─→ Architecture design

Workflows:
├── research-first            ─→ Context7 + Perplexity
├── explore-first-navigation  ─→ Codebase exploration
├── design-to-code            ─→ Figma → React
└── codebase-quality          ─→ Code review automation

Utilities:
├── worktree-manager          ─→ Git worktree management
├── setup-harness             ─→ Symlink automation
├── mcp-skills                ─→ MCP server wrappers
└── using-tmux                ─→ Interactive command patterns
```

## Workflow Example: New Feature Implementation

```
1. User defines feature in PRD
        ↓
2. System 3 receives request
        ↓
3. System 3 parses PRD with Task Master
        PRD ─→ tasks.json ─→ Beads issues
        ↓
4. System 3 spawns Orchestrator for epic
        worktree creation
        ↓
5. Orchestrator investigates
        Read/Grep/Glob to understand codebase
        Analyzes dependencies
        Creates task structure
        ↓
6. Orchestrator delegates to Workers via tmux
        ┌──────────────┬──────────────┬──────────────┐
        │ Frontend     │ Backend      │ TDD Engineer │
        │ Worker       │ Worker       │              │
        │              │              │              │
        │ Implements   │ Implements   │ Writes tests │
        │ UI           │ API          │ Validates    │
        └──────────────┴──────────────┴──────────────┘
        ↓
7. Workers report completion to Orchestrator
        ↓
8. Orchestrator validates with validation-agent
        Unit tests + API tests + E2E browser tests
        ↓
9. Orchestrator reports to System 3
        ↓
10. System 3 validates business outcomes
        Feature complete! ✓
```

## File Structure in Projects

```
your-project/
├── .claude/                    ─→ Symlink to ~/claude-harness/.claude
│   ├── output-styles/          ← Auto-loaded from harness
│   ├── skills/                 ← All skills available
│   ├── hooks/                  ← Lifecycle automation
│   ├── scripts/                ← CLI utilities
│   └── settings.json           ← Base configuration
│
├── .mcp.json                   ─→ Symlink or copy from harness
│
├── .claude/settings.local.json ─→ Project-specific overrides
│                                  (created by you, gitignored)
│
├── .claude-local/              ─→ Project-specific additions
│   └── skills/                    (optional, for custom skills)
│
└── your-code/                  ─→ Your actual application code
```

## Update Propagation

```
Central Harness Update:
─────────────────────────

cd ~/claude-harness
git pull
    │
    └─→ Updates .claude/ directory
            │
            ├─→ Project A sees update immediately (symlink)
            ├─→ Project B sees update immediately (symlink)
            ├─→ Project C sees update immediately (symlink)
            └─→ Project N sees update immediately (symlink)

No manual copying needed!
All projects automatically get improvements.
```

## Security Model

```
┌─────────────────────────────────────┐
│  Central Harness (Version Control)  │
│  ✓ Skills, hooks, documentation     │
│  ✓ Base settings.json               │
│  ✓ .mcp.json.example (template)     │
│  ✗ .mcp.json (gitignored)           │ ← Your API keys, not committed
│  ✗ settings.local.json (gitignored) │ ← User preferences
│  ✗ Runtime state (gitignored)       │ ← Session-specific data
└─────────────────────────────────────┘

API Keys Workflow:
──────────────────
1. Clone harness
2. cp .mcp.json.example .mcp.json
3. Add your API keys to .mcp.json
4. .mcp.json is gitignored ✓
5. Symlink or copy to projects
```

## Benefits Summary

| Aspect | Without Harness | With Harness |
|--------|----------------|--------------|
| Configuration | Copy to each project | Symlink once |
| Updates | Manual copying | `git pull` → all projects |
| Consistency | Drift over time | Always synchronized |
| Team sharing | Manual distribution | `git clone` → ready |
| Version control | Per-project chaos | Single source of truth |
| Maintenance | N projects × updates | 1 harness × updates |

---

**Architecture Version**: 1.0.0
**Last Updated**: January 23, 2026
