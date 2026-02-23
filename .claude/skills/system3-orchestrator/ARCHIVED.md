# ARCHIVED: system3-orchestrator Skill

**Archived**: 2026-02-24
**Reason**: Guardian-direct orchestrator spawning model adopted

---

## What Was Here

This skill taught **System 3** (the meta-orchestrator session) how to:
- Spawn orchestrators in tmux worktrees
- Inject Hindsight wisdom into orchestrator prompts
- Monitor orchestrators via tmux capture-pane
- Run validation cycles (oversight team, DOT pipeline transitions)

## Why It Was Archived

The original model had an extra layer:
```
Guardian → [tmux] System 3 (this skill) → [tmux] Orchestrators → Workers (native teams)
```

That middle layer (System 3 meta-orchestrator) added complexity without adding value.
The guardian can spawn and monitor orchestrators directly.

The new model:
```
Guardian → [tmux] Orchestrators → Workers (native teams)
```

## Where the Content Went

| Content | New Location |
|---------|-------------|
| tmux spawn sequence (4 critical patterns) | `s3-guardian/SKILL.md` Phase 2 |
| Wisdom injection from Hindsight | `s3-guardian/SKILL.md` Phase 2 |
| DOT pipeline dispatch (pending → active) | `s3-guardian/SKILL.md` Phase 2 |
| Communication hierarchy (guardian → orch) | `s3-guardian/SKILL.md` Phase 3 |
| Post-completion validation | `s3-guardian/SKILL.md` Phase 4 |

## Reference Files Still Valid

The following files remain valid supplementary material for guardian Phase 2/3:
- `references/tmux-commands.md` — tmux command patterns
- `references/spawn-workflow.md` — detailed spawn workflow
- `references/monitoring-commands.md` — monitoring commands and model selection
- `references/oversight-team.md` — oversight team spawn patterns

## How to Migrate

**Old invocation** (in system3-meta-orchestrator output style sessions):
```python
Skill("system3-orchestrator")  # DEPRECATED
```

**New invocation** (in guardian sessions):
```python
Skill("s3-guardian")  # Phase 2 contains the spawn workflow
```
