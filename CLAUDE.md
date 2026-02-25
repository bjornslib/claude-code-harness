# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a **Claude Code harness setup** repository that provides a complete configuration framework for multi-agent AI orchestration using Claude Code. It contains no application code—only configuration, skills, hooks, and orchestration tools.

## Architecture

### 3-Level Agent Hierarchy

This setup implements a sophisticated multi-agent system with three distinct levels:

```
┌─────────────────────────────────────────────────────────────────────┐
│  LEVEL 1: SYSTEM 3 (Meta-Orchestrator)                              │
│  Output Style: system3-meta-orchestrator.md                         │
│  Skills: system3-orchestrator/, completion-promise                  │
│  Role: Strategic planning, OKR tracking, business validation        │
├─────────────────────────────────────────────────────────────────────┤
│  LEVEL 2: ORCHESTRATOR                                              │
│  Output Style: orchestrator.md                                      │
│  Skills: orchestrator-multiagent/                                   │
│  Role: Feature coordination, worker delegation via native teams     │
├─────────────────────────────────────────────────────────────────────┤
│  LEVEL 3: WORKERS (native teammates via Agent Teams)                │
│  Specialists: frontend-dev-expert, backend-solutions-engineer,      │
│               tdd-test-engineer, solution-architect                 │
│  Role: Implementation, testing, focused execution                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Principle**: Higher levels coordinate; lower levels implement.
- System 3 sets goals and validates business outcomes
- Orchestrators break down work and delegate to workers
- Workers execute focused tasks and report completion

### Launch Commands

| Level | Command | Purpose |
|-------|---------|---------|
| System 3 | `ccsystem3` | Launch meta-orchestrator with completion promises |
| Orchestrator | `launchorchestrator [epic-name]` | Launch in isolated worktree (via tmux) |
| Worker | `Task(subagent_type="...", team_name="...", name="...")` | Spawned as native teammate by orchestrator (team lead) |

## Directory Structure

```
.claude/
├── CLAUDE.md                     # This configuration directory documentation
├── settings.json                 # Core settings (hooks, permissions, plugins)
├── settings.local.json           # Local overrides
├── output-styles/                # Automatically loaded agent behaviors
│   ├── orchestrator.md           # Level 2 orchestrator behavior
│   └── system3-meta-orchestrator.md  # Level 1 meta-orchestrator behavior
├── skills/                       # Explicitly invoked agent skills
│   ├── orchestrator-multiagent/  # Multi-agent orchestration patterns
│   ├── system3-orchestrator/     # System 3 strategic planning
│   ├── completion-promise/       # Session completion tracking
│   ├── message-bus/              # Inter-instance messaging
│   ├── mcp-skills/              # MCP server wrappers with progressive disclosure
│   └── [20+ additional skills]
├── hooks/                        # Lifecycle event handlers
│   ├── session-start-orchestrator-detector.py
│   ├── user-prompt-orchestrator-reminder.py
│   ├── message-bus-signal-check.py
│   ├── unified-stop-gate.sh
│   └── unified_stop_gate/        # Stop gate implementation
├── scripts/                      # CLI utilities
│   ├── message-bus/              # mb-* commands for inter-instance messaging
│   └── completion-state/         # cs-* commands for session tracking
├── commands/                     # Slash commands (e.g., /check-messages)
├── documentation/                # Architecture decisions and guides
│   ├── MESSAGE_BUS_ARCHITECTURE.md
│   ├── ADR-001-output-style-reliability.md
│   └── SYSTEM3_CHANGELOG.md
├── validation/                   # Validation agent configs
├── state/                        # Runtime state tracking
├── agents/                       # Agent configurations
└── tests/                        # Hook and workflow tests
```

## Core Systems

### 1. Output Styles vs Skills

**Critical Decision** (see ADR-001): Content is split by reliability requirements.

| Mechanism | Load Guarantee | Use For |
|-----------|----------------|---------|
| **Output Styles** | 100% (automatic) | Critical patterns, mandatory protocols, core workflows |
| **Skills** | ~85% (requires invocation) | Reference material, detailed guides, optional enhancements |

**Output styles are loaded automatically at session start**. Skills must be explicitly invoked using the `Skill` tool.

### 2. Message Bus (Inter-Instance Communication)

Enables real-time coordination between Claude Code sessions (System 3 ↔ Orchestrators ↔ Workers).

**Components**:
- SQLite queue: `.claude/message-bus/queue.db`
- Signal files: `.claude/message-bus/signals/*.signal`
- CLI scripts: `.claude/scripts/message-bus/mb-*`

**Key Commands**:
```bash
mb-init                    # Initialize message bus
mb-register <id> <type>    # Register instance
mb-send <target> <msg>     # Send message
mb-recv                    # Receive pending messages
mb-list                    # List active orchestrators
mb-status                  # Queue status overview
```

**Detection Mechanisms**:
1. Background monitor agent (polls every 3s)
2. PostToolUse hook (signal file detection)
3. tmux injection (fallback for idle agents)

See `.claude/documentation/MESSAGE_BUS_ARCHITECTURE.md` for full details.

### 3. Task Master Integration

Task Master is used for task decomposition and tracking through the `/project:tm/` namespace.

**Common Commands**:
```bash
/project:tm/init/quick               # Initialize project
/project:tm/parse-prd <file>         # Generate tasks from PRD
/project:tm/next                     # Get next recommended task
/project:tm/list                     # List tasks with filters
/project:tm/set-status/to-done <id>  # Mark task complete
/project:tm/expand <id>              # Break down complex task
```

See `.claude/TM_COMMANDS_GUIDE.md` for complete command reference.

### 4. MCP Server Integration

The repository includes extensive MCP (Model Context Protocol) server integration:

**Available MCP Servers** (configured in `.mcp.json`):
- `sequential-thinking` - Multi-step reasoning
- `task-master-ai` - Task decomposition and management
- `context7` - Framework documentation lookup
- `perplexity-ask` - Web research
- `brave-search` - Web search
- `serena` - IDE assistant patterns
- `hindsight` - Long-term memory (HTTP server on localhost:8888)
- `beads_dev:beads` - Issue tracking integration

**MCP Skills Wrapper**: The `.claude/skills/mcp-skills/` directory provides progressive disclosure wrappers that reduce context usage by 90%+ compared to native MCP loading.

Available wrapped skills: `assistant-ui`, `chrome-devtools`, `github`, `livekit-docs`, `logfire`, `magicui`, `playwright`, `shadcn`, `mcp-undetected-chromedriver`

### 5. Hooks System

Automated lifecycle event handlers configured in `.claude/settings.json`:

| Hook | Purpose | Script |
|------|---------|--------|
| `SessionStart` | Detect orchestrator mode, load MCP skills | `session-start-orchestrator-detector.py`, `load-mcp-skills.sh` |
| `UserPromptSubmit` | Remind orchestrator of delegation rules | `user-prompt-orchestrator-reminder.py` |
| `PostToolUse` | Check for inter-instance messages | `message-bus-signal-check.py` |
| `Stop` | Validate completion before session ends | `unified-stop-gate.sh` |
| `PreCompact` | Reload MCP skills after context compression | `load-mcp-skills.sh` |
| `Notification` | Webhook notifications | `claude_notification_webhook.sh` |

### 6. Enabled Plugins

Configured in `.claude/settings.json`:
- `beads@beads-marketplace` - Issue tracking
- `frontend-design@claude-plugins-official` - UI design patterns
- `code-review@claude-plugins-official` - Code review automation
- `double-shot-latte@superpowers-marketplace` - Enhanced capabilities

## Key Patterns

### Investigation vs Implementation Boundary

**Orchestrators** (Level 2):
- ✅ Use Read/Grep/Glob to investigate
- ✅ Analyze, plan, and create task structures
- 🛑 NEVER use Edit/Write/MultiEdit directly
- 🛑 MUST delegate implementation to workers via native Agent Teams (`Teammate` + `TaskCreate` + `SendMessage`)

**Workers** (Level 3):
- ✅ Implement features using Edit/Write
- ✅ Run tests with tdd-test-engineer
- ✅ Report completion to orchestrator

### 4-Phase Orchestration Pattern

1. **Ideation** - Brainstorm, research, parallel-solutioning
2. **Planning** - PRD → Task Master → Beads hierarchy
3. **Execution** - Delegate to workers, monitor progress
4. **Validation** - 3-level testing (Unit + API + E2E)

### Validation Agent Enforcement

**MANDATORY**: All task closures must go through validation-agent with `--mode=implementation`:

```bash
# CORRECT: Delegate to validation-agent
Task(
    subagent_type="validation-agent",
    prompt="--mode=implementation --task_id=<id> ..."
)

# WRONG: Direct closure
bd close <task-id>  # BLOCKED
```

### Session Isolation

Each orchestrator session should have:
- Unique `CLAUDE_SESSION_ID` environment variable
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` for native team coordination
- Separate worktree (for code-based projects)
- Message bus registration
- Completion promise tracking
- Native team created via `Teammate(operation="spawnTeam")`

## Environment Variables

| Variable | Purpose | Set By |
|----------|---------|--------|
| `CLAUDE_SESSION_ID` | Unique session identifier | Launch scripts |
| `CLAUDE_OUTPUT_STYLE` | Active output style (system3/orchestrator) | Claude Code CLI |
| `CLAUDE_PROJECT_DIR` | Project root directory | Claude Code CLI |
| `ANTHROPIC_API_KEY` | API authentication | `.mcp.json` env |
| `PERPLEXITY_API_KEY` | Perplexity API key | `.mcp.json` env |
| `BRAVE_API_KEY` | Brave search API key | `.mcp.json` env |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | Enable native Agent Teams (`1`) | `.claude/settings.json` or spawn script |
| `CLAUDE_CODE_TASK_LIST_ID` | Shared task list ID for team coordination | Spawn script |

## Testing

**Hook Tests**: `.claude/tests/hooks/`
```bash
pytest .claude/tests/hooks/              # Run all hook tests
pytest .claude/tests/hooks/test_*.py     # Run specific test
```

**Completion State Tests**: `.claude/tests/completion-state/`
```bash
pytest .claude/tests/completion-state/
```

## Utilities

### Status Line Analyzer

Real-time session status display:
```bash
./.claude/statusline_analyzer.py        # Show current session status
./.claude/setup-statusline.sh           # Configure status line
```

### Sync Scripts

Task Master to Beads synchronization:
```bash
node .claude/scripts/sync-taskmaster-to-features.js
node .claude/skills/orchestrator-multiagent/scripts/sync-taskmaster-to-beads.js
```

## Configuration Files

| File | Purpose |
|------|---------|
| `.mcp.json` | MCP server configurations (root level) |
| `.claude/settings.json` | Core Claude Code settings |
| `.claude/settings.local.json` | Local overrides (not in version control) |
| `.claude/.gitignore` | Excluded files (state/, logs/, etc.) |

## Important Notes

### API Keys in Configuration

⚠️ **Security Warning**: The `.mcp.json` file in this repository contains API keys embedded in the configuration. In a production environment:
- Never commit API keys to version control
- Use environment variables or secure secret management
- Rotate keys regularly
- This harness is for development/testing only

### No Application Code

This repository contains **only Claude Code configuration and orchestration tools**. It does not include:
- Application source code
- Frontend/backend implementations
- Deployment configurations
- Production services

The harness is designed to be copied into actual project repositories that contain application code.

### Orchestrator Delegation Rules

When running as an orchestrator (Level 2):
1. **Investigation is allowed**: Read/Grep/Glob to understand problems
2. **Implementation is forbidden**: Never use Edit/Write directly
3. **Always delegate**: Use native Agent Teams (teammates) for all code changes
4. **No exceptions**: Even "simple" changes must be delegated

This separation ensures proper testing, validation, and architectural consistency.

## Documentation Standards

All markdown files in `.claude/` must follow these standards, enforced by the **doc-gardener** linter (`scripts/doc-gardener/lint.py`).

### Documentation Directory Map

Files in these directories are **linted and require frontmatter**:

| Directory | Purpose | Default Grade |
|-----------|---------|---------------|
| `skills/` | Skill implementations (SKILL.md per skill) | `authoritative` |
| `agents/` | Agent configuration definitions | `authoritative` |
| `output-styles/` | Output style behavior definitions | `authoritative` |
| `documentation/` | Architecture docs, ADRs, guides | `reference` |
| `commands/` | Slash command definitions | `reference` |

Files in these directories are **skipped** (runtime state, not documentation):

| Directory | Purpose |
|-----------|---------|
| `state/` | Runtime state tracking |
| `message-bus/` | Message queue database and signals |
| `completion-state/` | Session completion tracking |
| `evidence/` | Validation evidence artifacts |
| `progress/` | Session progress logs |
| `worker-assignments/` | Worker task assignments |
| `user-input-queue/` | Queued user input |

Also skipped: `documentation/gardening-report.md` (auto-generated).

### Frontmatter Requirements

Every `.md` file in a linted directory must have YAML frontmatter:

```yaml
---
title: "Human-Readable Title"           # REQUIRED - string
status: active                          # REQUIRED - active | draft | archived | deprecated
type: skill                             # Recommended - skill | agent | output-style | hook | command | guide | architecture | reference | config
last_verified: 2026-02-19              # Recommended - YYYY-MM-DD format
grade: authoritative                    # Recommended - authoritative | reference | archive | draft
---
```

**Required fields**: `title`, `status`. Missing frontmatter is auto-fixable (the gardener generates it from filename and context).

### Lint Check Categories

The doc-gardener checks 5 categories:

| Category | What It Checks | Severity | Auto-fixable |
|----------|---------------|----------|-------------|
| **frontmatter** | Presence + valid field values in linted directories | error | Yes (generates missing frontmatter) |
| **crosslinks** | All relative markdown links resolve to real files | error | No |
| **naming** | Directory and file naming conventions (see below) | warning | No |
| **staleness** | `last_verified` date vs current date thresholds | warning | Yes (downgrades grade) |
| **grades-sync** | Frontmatter `grade` matches `quality-grades.json` defaults | info | Yes (updates frontmatter) |

### Naming Conventions

| Item | Convention | Pattern | Examples |
|------|-----------|---------|----------|
| Directories | `kebab-case` | `^[a-z0-9]+(-[a-z0-9]+)*$` | `orchestrator-multiagent/`, `doc-gardener/` |
| Top-level docs | `UPPER-CASE.md` | Exact match set | `CLAUDE.md`, `SKILL.md`, `README.md`, `INDEX.md`, `CHANGELOG.md` |
| Regular files | `kebab-case.md` | `^[a-z0-9]+(-[a-z0-9]+)*\.md$` | `message-bus-integration.md` |
| ADR/spec prefixes | `ADR-NNN-kebab.md` | Mixed case prefix | `ADR-001-output-style-reliability.md` |
| Version-prefixed | `vN.N-kebab.md` | Version prefix | `v3.9-migration-guide.md` |
| Private files | `_underscore.md` | Leading underscore | `_internal-notes.md` |

### Staleness Thresholds

| Condition | Action |
|-----------|--------|
| `last_verified` > 90 days old | Grade should be `archive` (auto-fixed) |
| `last_verified` > 60 days old | Consider downgrading from `authoritative` (warning) |
| No `last_verified` field | Not flagged (field is optional) |

### Cross-Link Integrity

All relative markdown links (`[text](path)`) in `.claude/` must resolve to existing files. The linter:
- Strips code blocks and inline code before scanning
- Resolves paths relative to the file containing the link
- Reports unresolvable links as errors (not auto-fixable)

### Quality Grades

Documents are graded by reliability and maintenance commitment:

| Grade | Meaning | Review Cadence | Trust Level |
|-------|---------|----------------|-------------|
| `authoritative` | Source of truth, actively maintained | Continuous | High |
| `reference` | Useful context, periodically reviewed | Quarterly | Medium |
| `archive` | Historical record, not maintained | None | Low |
| `draft` | Work in progress, unverified | On completion | Unverified |

Default grades per directory are defined in `scripts/doc-gardener/quality-grades.json`.

### Doc-Gardener Commands

```bash
# Report violations (dry-run, no changes)
python3 .claude/scripts/doc-gardener/gardener.py --report

# Apply auto-fixes and generate report
python3 .claude/scripts/doc-gardener/gardener.py --execute

# Machine-readable output
python3 .claude/scripts/doc-gardener/lint.py --json

# Lint only (exit code 0=clean, 1=violations)
python3 .claude/scripts/doc-gardener/lint.py

# Bypass on push (emergency only)
DOC_GARDENER_SKIP=1 git push
```

---

## Skills Library

Skills are explicitly invoked via `Skill("skill-name")`. Use this library to know **when** to reach for each skill rather than doing the work manually. Skills contain versioned, current patterns — your memory does not.

### Orchestration & Planning

| Skill | Invoke When |
|-------|------------|
| `system3-orchestrator` | About to spawn an orchestrator into a tmux worktree |
| `orchestrator-multiagent` | Orchestrator setting up a native Agent Team and delegating to workers |
| `s3-guardian` | Independent validation of an orchestrator's claimed completion; blind acceptance tests needed |
| `s3-heartbeat` | Setting up a session-scoped keep-alive agent that scans for work on a cycle |
| `completion-promise` | Tracking session-level goals with verifiable acceptance criteria |
| `worker-focused-execution` | A worker agent needs persistent task claiming and completion reporting patterns |

### Research & Investigation

| Skill | Invoke When |
|-------|------------|
| `research-first` | Investigating an unfamiliar framework, library, or architectural pattern before briefing an orchestrator |
| `explore-first-navigation` | Need to find files, search a codebase, or understand structure before making a plan |
| `mcp-skills` | Looking up which MCP-derived skill wraps a tool (github, playwright, logfire, shadcn, magicui, livekit, etc.) |

### Validation & Quality

| Skill | Invoke When |
|-------|------------|
| `acceptance-test-writer` | Kicking off a new initiative — write blind Gherkin acceptance tests from the PRD **before** briefing the orchestrator |
| `acceptance-test-runner` | Running stored acceptance tests against a completed implementation to generate evidence |
| `codebase-quality` | Orchestrating a quality sweep (linting, dead code, security review) across the repo |

### Frontend & Design

| Skill | Invoke When |
|-------|------------|
| `frontend-design` | Designing or reviewing a frontend interface — ensures distinctive, non-generic UI patterns |
| `design-to-code` | Translating a design mockup or screenshot into production React components |
| `website-ux-audit` | Any work involving an existing website or UI — run audit before forming the design brief |
| `website-ux-design-concepts` | Generating visual mockups or HTML/CSS prototypes from audit recommendations |
| `react-best-practices` | Briefing frontend workers — reference current React/Next.js performance rules |

### Infrastructure & Deployment

| Skill | Invoke When |
|-------|------------|
| `railway-new` | Creating a new Railway project, service, or database |
| `railway-deploy` | Deploying code to Railway (`railway up`) |
| `railway-deployment` | Managing existing deployments (logs, redeploy, remove) |
| `railway-status` | Checking current Railway project health |
| `railway-environment` | Reading or editing Railway environment variables |
| `railway-database` | Adding a managed database service to a Railway project |
| `railway-domain` | Adding or removing custom domains on Railway |
| `railway-metrics` | Querying CPU/memory resource usage for a Railway service |
| `railway-service` | Checking service status or advanced service configuration |
| `railway-projects` | Listing or switching Railway projects |
| `railway-templates` | Searching and deploying from the Railway template marketplace |
| `railway-railway-docs` | Looking up Railway documentation to answer config questions accurately |
| `railway-central-station` | Searching Railway community support threads |
| `worktree-manager-skill` | Creating, switching, or cleaning up git worktrees for parallel development |

### Development Tools

| Skill | Invoke When |
|-------|------------|
| `using-tmux-for-interactive-commands` | Running interactive CLI tools (vim, git rebase -i, REPLs) that require a real terminal |
| `dspy-development` | Building or modifying DSPy modules, optimizers, or LLM pipelines |
| `setup-harness` | Deploying this harness configuration to a target project repository |
| `message-bus` | Setting up or using inter-instance messaging between Claude Code sessions |

### Skill Development

| Skill | Invoke When |
|-------|------------|
| `skill-development` | Creating a new skill or editing an existing one |
| `mcp-to-skill-converter` | Wrapping an MCP server as a progressive-disclosure Claude skill |

### Quick Decision Guide

**Before any new initiative** → `acceptance-test-writer` (blind tests first)
**Before researching a framework** → `research-first`
**Before spawning an orchestrator** → `system3-orchestrator`
**Before designing UI** → `website-ux-audit` → `website-ux-design-concepts` → `frontend-design`
**Before deploying to Railway** → `railway-status` → `railway-deploy`
**After orchestrator claims done** → `s3-guardian` or validation-test-agent
**When navigating unfamiliar code** → Serena MCP (`mcp__serena__find_symbol`, `mcp__serena__search_for_pattern`)
