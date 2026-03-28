# CLAUDE.md

Claude Code harness for multi-agent AI orchestration. Contains configuration, skills, hooks, and the CoBuilder pipeline engine.

## Agent Hierarchy

```
CoBuilder (cccb)               → Strategic planning, business validation
  Orchestrator (launchorchestrator) → Feature coordination, worker delegation
    Workers (Agent Teams)         → Implementation, testing, focused execution
```

**Key Principle**: Higher levels coordinate; lower levels implement.

Launch commands:
- CoBuilder: `cccb`
- Orchestrator: `launchorchestrator [epic-name]`
- Worker: `Task(subagent_type="...", team_name="...", name="...")`
- Pipeline: `python3 cobuilder/engine/pipeline_runner.py --dot-file <path.dot>`
- Pipeline (resume): `python3 cobuilder/engine/pipeline_runner.py --dot-file <path.dot> --resume`

## Directory Index

### `cobuilder/` — Pipeline Execution Engine

Zero-LLM-cost state machine that turns DOT graph pipelines into working software. Parses directed acyclic graphs, dispatches AgentSDK workers, watches signal files, and transitions nodes through states. All intelligence lives in the workers it spawns.

| Subdirectory | Purpose |
|---|---|
| `engine/` | Core runner (`pipeline_runner.py`), pilot agent (`guardian.py`), node handlers, signal protocol, checkpoint system, CLI. Pilot is an autonomous goal-pursuing agent: SD fidelity monitoring, cross-node integration, Gherkin E2E, manifest auto-generation. See `docs/sds/SD-PILOT-AUTONOMY-001.md`. |
| `engine/handlers/` | Node implementations: `codergen` (LLM work), `research` (Context7+Perplexity), `refine` (SD rewriting), `wait_human` (gates), `manager_loop` (sub-pipelines) |
| `engine/providers.yaml` | Named LLM profiles (anthropic-fast/smart/opus, alibaba-glm5/qwen3) |
| `repomap/` | **ZeroRepo** — codebase intelligence via graph construction and embeddings for context-aware agent guidance |
| `templates/` | Jinja2 DOT pipeline templates: `sequential-validated`, `hub-spoke`, `cobuilder-lifecycle` |

### `.claude/` — Harness Configuration

| Subdirectory | Purpose |
|---|---|
| `output-styles/` | Auto-loaded agent behaviors: `cobuilder-guardian.md` (Level 1), `orchestrator.md` (Level 2) |
| `skills/` | 40+ explicitly invoked skills. Key: `cobuilder-guardian/`, `orchestrator-multiagent/`, `mcp-skills/` (MCP wrappers with 90%+ context savings) |
| `hooks/` | Lifecycle handlers: session-start detection, delegation reminders, stop-gate validation, pre-compact memory flush |
| `scripts/` | CLI utilities including `completion-state/` (cs-* session tracking), `doc-gardener/` (documentation linter) |
| `tests/` | Hook and workflow tests: `pytest .claude/tests/` |

### `docs/` — Project Documentation

| Subdirectory | Purpose |
|---|---|
| `prds/` | Product Requirement Documents (Business Specs) |
| `sds/` | Solution Design documents (Technical Specs) |

## Documentation Standards

All markdown in `.claude/` and `docs/` must follow standards enforced by **doc-gardener** (`.claude/scripts/doc-gardener/lint.py`). The linter supports target-specific schemas controlled via config files.

### Frontmatter Requirements

**`.claude/` files** (minimal schema):

```yaml
---
title: "Human-Readable Title"           # REQUIRED
status: active                          # REQUIRED - active | draft | archived | deprecated
type: skill                             # Recommended - skill | agent | output-style | hook | command | guide | architecture | reference | config
last_verified: 2026-02-19              # Recommended - YYYY-MM-DD
grade: authoritative                    # Recommended - authoritative | reference | archive | draft
---
```

**`docs/` files** (extended schema):

```yaml
---
title: "Human-Readable Title"           # REQUIRED
description: "One-line purpose summary"  # REQUIRED - non-empty, max 200 chars
version: "1.0.0"                        # REQUIRED - semver N.N.N
last-updated: 2026-03-15               # REQUIRED - YYYY-MM-DD
status: active                          # REQUIRED - active | draft | archived | deprecated
type: prd                               # REQUIRED - prd | sd | epic | specification | research | guide | reference | architecture
grade: authoritative                    # Recommended
prd_id: PRD-XXX-NNN                    # CONDITIONAL - required for PRDs
---
```

### Lint Categories

| Category | What It Checks | Auto-fixable |
|----------|---------------|-------------|
| **frontmatter** | Missing block or invalid field values | Yes |
| **crosslinks** | Relative markdown links resolve to real files | No |
| **naming** | kebab-case dirs, UPPER-CASE top-level docs, Doc-ID prefixed files | No |
| **staleness** | `last_verified` > 90 days (warning), > 60 days for authoritative (info) | Yes (downgrades grade) |
| **grades-sync** | Frontmatter `grade` matches `quality-grades.json` | Yes |
| **implementation-status** | PRD/SD/Epic/Spec docs must have `## Implementation Status` section | Yes |
| **misplaced-document** | PRD/SD content outside `docs/` is flagged | No |

### Naming Conventions

| Item | Pattern | Examples |
|------|---------|---------|
| Directories | `kebab-case` | `orchestrator-multiagent/` |
| Doc-ID dirs | `PREFIX-Name` | `SD-DOC-GARDENER-002/` |
| Top-level docs | `UPPER-CASE.md` | `CLAUDE.md`, `SKILL.md`, `README.md` |
| Regular files | `kebab-case.md` | `decision-time-guidance.md` |
| Doc-ID files | `PREFIX-name.md` | `PRD-DOC-GARDENER-002.md` |

### Quality Grades

| Grade | Meaning | Trust Level |
|-------|---------|-------------|
| `authoritative` | Source of truth, actively maintained | High |
| `reference` | Useful context, periodically reviewed | Medium |
| `archive` | Historical record, not maintained | Low |
| `draft` | Work in progress, unverified | Unverified |

### Doc-Gardener Commands

```bash
python3 .claude/scripts/doc-gardener/lint.py                    # Lint .claude/
python3 .claude/scripts/doc-gardener/lint.py --target docs/     # Lint docs/
python3 .claude/scripts/doc-gardener/gardener.py --execute      # Auto-fix + report
python3 .claude/scripts/doc-gardener/lint.py --json             # Machine-readable
DOC_GARDENER_SKIP=1 git push                                    # Emergency bypass
```

Config files: `.claude/scripts/doc-gardener/docs-gardener.config.json`, `.claude/scripts/doc-gardener/quality-grades.json`.

### `.pipelines/` — Runtime Pipeline State (git-ignored)

Active DOT files, checkpoint snapshots, signal directories, and validation evidence.

### `.cobuilder/templates/` — Template Library

Jinja2 DOT templates for pipeline instantiation.

## Key Patterns

### Investigation vs Implementation Boundary

- **Orchestrators** (Level 2): Read/Grep/Glob to investigate. NEVER Edit/Write. Delegate all implementation to workers.
- **Workers** (Level 3): Implement features, run tests, report completion.

### Agent Selection by Directory

| Directory Pattern | Agent |
|---|---|
| `*/frontend/*` | `frontend-dev-expert` |
| `*/agent/*` or backend | `backend-solutions-engineer` |
| Test files (`*.test.*`, `*.spec.*`) | `tdd-test-engineer` |
| Solution design docs | `solution-architect` |

### Validation Rules

- All task closures go through `validation-test-agent` — direct `bd close` is blocked
- Writing NEW tests → `tdd-test-engineer`; checking existing work → `validation-test-agent`

## Core Systems

### Output Styles vs Skills

| Mechanism | Load Guarantee | Use For |
|---|---|---|
| **Output Styles** | 100% (auto-loaded) | Critical patterns, mandatory protocols |
| **Skills** | ~85% (explicit invoke) | Reference material, detailed guides |

Output styles load automatically at session start. Skills require `Skill("skill-name")` invocation.

### Task Master Integration

Task decomposition and tracking: `/project:tm/init/quick`, `/project:tm/parse-prd <file>`, `/project:tm/next`, `/project:tm/list`, `/project:tm/set-status/to-done <id>`, `/project:tm/expand <id>`. See `.claude/TM_COMMANDS_GUIDE.md` for full reference.

### MCP Servers

Configured in `.mcp.json`: sequential-thinking, task-master-ai, context7, perplexity (4 tools), brave-search, serena, hindsight (localhost:8888), beads. MCP skill wrappers in `.claude/skills/mcp-skills/` reduce context by 90%+.

### Hooks System

Lifecycle event handlers in `.claude/settings.json`:

| Hook | Purpose |
|---|---|
| `SessionStart` | Detect orchestrator mode, load MCP skills |
| `UserPromptSubmit` | Remind orchestrator of delegation rules |
| `Stop` | Validate completion before session ends |
| `PreCompact` | Flush Hindsight memory before compression |

### Enabled Plugins

Configured in `.claude/settings.json`: beads, frontend-design, code-review, double-shot-latte.

## Environment Variables

| Variable | Purpose |
|---|---|
| `CLAUDE_SESSION_ID` | Unique session identifier |
| `CLAUDE_OUTPUT_STYLE` | Active output style |
| `ANTHROPIC_API_KEY` | API authentication |
| `DASHSCOPE_API_KEY` | DashScope API key (GLM-5/Qwen3) |
| `PIPELINE_SIGNAL_DIR` | Override signal file directory |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | Enable native Agent Teams (`1`) |

## Testing

```bash
pytest .claude/tests/hooks/           # Hook tests
pytest .claude/tests/completion-state/ # Completion state tests
```

## Important Notes

- **API Keys**: `.mcp.json` contains API keys for development only. Never commit to production.
- **Orchestrator Delegation Rules**: Investigation is allowed; implementation is forbidden. Always delegate code changes to workers.
- **Documentation**: See Documentation Standards section above.
