# .claude Configuration Directory

This directory contains Claude Code configuration for the agencheck project.

## Agent Hierarchy

This project uses a 3-level agent hierarchy for complex multi-feature development:

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
│  Role: Feature coordination, worker delegation, tmux management     │
├─────────────────────────────────────────────────────────────────────┤
│  LEVEL 3: WORKERS (via tmux)                                        │
│  Specialists: frontend-dev-expert, backend-solutions-engineer,      │
│               tdd-test-engineer, solution-architect                 │
│  Role: Implementation, testing, focused execution                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Launch Commands

| Level | Command | Purpose |
|-------|---------|---------|
| System 3 | `ccsystem3` | Launch meta-orchestrator with completion promises |
| Orchestrator | `launchorchestrator [epic-name]` | Launch in isolated worktree |
| Worker | `launchcc` (in tmux session) | Launch Claude Code for implementation |

### Key Principle

**Higher levels coordinate; lower levels implement.**
- System 3 sets goals and validates business outcomes
- Orchestrators break down work and delegate to workers
- Workers execute focused tasks and report completion

## Directory Structure

| Path | Purpose |
|------|---------|
| `output-styles/` | Output style definitions (system3-meta-orchestrator.md, orchestrator.md) |
| `skills/` | Skill implementations (system3-orchestrator/, orchestrator-multiagent/) |
| `hooks/` | Pre/post tool hooks for automation |
| `documentation/` | Architecture docs, changelogs |
| `completion-state/` | Session completion tracking |
| `scripts/` | CLI utilities (message-bus, completion state) |

## Related Documentation

- Main CLAUDE.md: `/agencheck/CLAUDE.md` (project instructions)
- Output Styles: `.claude/output-styles/`
- Skills: `.claude/skills/`
- Architecture: `.claude/documentation/`
