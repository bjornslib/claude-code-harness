# CLAUDE.md

Claude Code harness for multi-agent AI orchestration. Contains configuration, skills, hooks, and the CoBuilder pipeline engine.

## Agent Hierarchy

| Level | Name | Launch | Purpose |
|-------|------|--------|---------|
| 1 | CoBuilder | `cccb` | Strategic planning, business validation |
| 1.5 | Pilot | `cobuilder-lifecycle` template | Autonomous research-to-validate loop |
| 2 | Orchestrator | `launchorchestrator [epic]` | Feature coordination, worker delegation |
| 3 | Workers | `Task(subagent_type="...", team_name="...")` | Implementation, testing, focused execution |
| -- | Pipeline | `python3 cobuilder/engine/pipeline_runner.py --dot-file <path>` | Zero-LLM-cost DAG state machine |

Additional commands:
- Resume pipeline: `pipeline_runner.py --dot-file <path> --resume`
- Event-driven pilot: `python3 cobuilder/engine/guardian.py --dot <path> --pipeline-id <id> --target-dir <dir> --event-driven`
- Gate watcher: `python3 cobuilder/engine/gate_watch.py --signal-dir <dir> --dot-file <path>`

**Key Principle**: Higher levels coordinate; lower levels implement. Orchestrators NEVER Edit/Write — they delegate to workers.

## Directory Index

| Directory | Purpose | Deeper Docs |
|-----------|---------|-------------|
| `cobuilder/engine/` | Pipeline runner, handlers, CLI, checkpoint, signal protocol, event bus | [`cobuilder/CLAUDE.md`](cobuilder/CLAUDE.md) |
| `cobuilder/repomap/` | ZeroRepo — codebase intelligence via graph + embeddings | [`cobuilder/CLAUDE.md`](cobuilder/CLAUDE.md) |
| `.cobuilder/templates/` | Jinja2 DOT pipeline templates (6 templates) | [`.cobuilder/templates/CLAUDE.md`](.cobuilder/templates/CLAUDE.md) |
| `.claude/output-styles/` | Auto-loaded agent behaviors (cobuilder-guardian, orchestrator) | |
| `.claude/skills/` | 40+ explicitly invoked skills | See Critical Skills below |
| `.claude/hooks/` | Lifecycle handlers (session-start, delegation, stop-gate, pre-compact) | |
| `.claude/scripts/` | CLI utilities: `completion-state/` (cs-*), `doc-gardener/` (lint) | |
| `.claude/agents/` | Agent-specific instructions | [`.claude/agents/CLAUDE.md`](.claude/agents/CLAUDE.md) |
| `docs/prds/` | Business Specs (PRDs) | |
| `docs/sds/` | Technical Specs (Solution Designs) | |
| `tools/` | Go CLI: `tmux-nav` (TUI navigator), `pipeline-watch` (event viewer) | |
| `.pipelines/` | Runtime pipeline state — DOT files, checkpoints, signals (git-ignored) | |

## Key Patterns

- **Investigation vs Implementation**: Orchestrators Read/Grep/Glob to investigate. ALL code changes delegated to workers via Agent Teams.
- **Agent selection by directory**: `*/frontend/*` -> `frontend-dev-expert` | `*/agent/*` or backend -> `backend-solutions-engineer` | test files -> `tdd-test-engineer` | design docs -> `solution-architect`
- **Validation**: All task closures go through `validation-test-agent` — direct `bd close` is blocked. Writing NEW tests -> `tdd-test-engineer`; checking existing work -> `validation-test-agent`.
- **Acceptance tests**: Blind tests live in `acceptance-tests/PRD-{ID}/`, never in the implementation repo. Workers cannot see the rubric.

## Critical Skills

| Skill | Invoke | When to Use |
|-------|--------|-------------|
| `cobuilder-guardian` | `Skill("cobuilder-guardian")` | Independent validation of orchestrator work |
| `research-first` | `Skill("research-first")` | Structured research before implementation |
| `acceptance-test-writer` | `Skill("acceptance-test-writer")` | Generate blind Gherkin tests from BS |
| `acceptance-test-runner` | `Skill("acceptance-test-runner")` | Execute stored acceptance tests |
| `completion-promise` | `Skill("completion-promise")` | Track session promises (cs-* CLI) |
| `worktree-manager-skill` | `Skill("worktree-manager-skill")` | Manage git worktrees for isolation |
| `railway-deploy` | `Skill("railway-deploy")` | Deploy to Railway |
| `mcp-skills/*` | See `.claude/skills/mcp-skills/SKILL.md` | MCP server wrappers (90%+ context savings) |

## Testing

```bash
pytest .claude/tests/hooks/              # Hook tests
pytest .claude/tests/completion-state/   # Completion state tests
pytest tests/engine/ -v                  # Pipeline engine tests
pytest cobuilder/engine/conditions/tests/ -v  # Conditions integration tests
```

## Documentation Standards

All markdown in `.claude/` and `docs/` must include YAML frontmatter and follow naming conventions enforced by doc-gardener. Run `python3 .claude/scripts/doc-gardener/lint.py` to check, or `python3 .claude/scripts/doc-gardener/gardener.py --execute` to auto-fix. Config: `.claude/scripts/doc-gardener/docs-gardener.config.json`. Emergency bypass: `DOC_GARDENER_SKIP=1 git push`.

## Pipeline Observability

Every pipeline emits structured events (18 types) to JSONL, Logfire, and SignalBridge backends simultaneously. Stream events with:

```bash
python3 cobuilder/engine/cli.py watch <pipeline.dot>          # Follow pipeline events
python3 cobuilder/engine/cli.py watch events.jsonl --filter "agent.*"  # Agent activity only
pipeline-watch                                                  # TUI viewer (Go, in tools/)
```

Full details in [`cobuilder/CLAUDE.md`](cobuilder/CLAUDE.md).

## Core Systems

- **Output Styles** (auto-loaded, 100% reliable) vs **Skills** (~85%, explicit `Skill()` invoke). Output styles for critical patterns; skills for reference material.
- **Task Master**: `/project:tm/init/quick`, `/project:tm/parse-prd <file>`, `/project:tm/next`, `/project:tm/list`. Full guide: `.claude/TM_COMMANDS_GUIDE.md`.
- **MCP Servers** (`.mcp.json`): sequential-thinking, task-master-ai, context7, perplexity, brave-search, serena, hindsight, beads. Wrappers: `.claude/skills/mcp-skills/`.
- **Hooks** (`settings.json`): SessionStart (mode detection), UserPromptSubmit (delegation reminder), Stop (completion validation), PreCompact (memory flush).

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `CLAUDE_SESSION_ID` | Unique session identifier |
| `CLAUDE_OUTPUT_STYLE` | Active output style |
| `ANTHROPIC_API_KEY` | API authentication |
| `DASHSCOPE_API_KEY` | DashScope API key (GLM-5/Qwen3) |
| `PIPELINE_SIGNAL_DIR` | Override signal file directory |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | Enable native Agent Teams (`1`) |

## Important Notes

- **API Keys**: `.mcp.json` contains API keys for development only. Never commit to production.
- **Orchestrator Rules**: Investigation allowed; implementation forbidden. Always delegate code changes to workers.
- **Beads**: Default task tracker. `bd ready` for available work, `bd create` before coding, `bd sync` at session end.
- **Hindsight**: Must call `mcp__hindsight__retain` before session end — enforced by stop hook.
