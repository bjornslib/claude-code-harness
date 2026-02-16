# System 3 Meta-Orchestrator (System 3 Pattern)

> **Level 3 Reflective Thinking** - A self-aware coordination system that launches, monitors, and guides orchestrator agents.

Based on the [Sophia: A Persistent Agent Framework](https://arxiv.org/abs/2512.18202) paper's System 3 concept.

---

## Quick Start

### 1. Use the Output Style
```bash
claude --output-style system3-meta-orchestrator
```

### 2. Or Invoke the Skill
```
Skill("system3-orchestrator", args="spawn my-initiative")
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SYSTEM 3 (You are here)                  │
│                                                             │
│  Reflects on memory → Forms goals → Spawns orchestrators    │
│  Monitors progress → Stores learnings → Self-improves       │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
         ┌─────────────────┐   ┌─────────────────┐
         │ Orchestrator A  │   │ Orchestrator B  │
         │ (worktree A)    │   │ (worktree B)    │
         │                 │   │                 │
         │ 4-Phase Pattern │   │ 4-Phase Pattern │
         └────────┬────────┘   └────────┬────────┘
                  │                     │
            ┌─────┴─────┐         ┌─────┴─────┐
            ▼           ▼         ▼           ▼
         [Workers]   [Workers]  [Workers]   [Workers]
```

---

## Key Concepts

### System 3 Pattern
Like Russian nesting dolls: System 3 contains orchestrators, which contain workers.

### Wisdom Injection
Before spawning an orchestrator, System 3 retrieves learned patterns from Hindsight and injects them into the orchestrator's context.

### Idle Mode
When no user input is received, System 3 proactively:
- Reflects on memory
- Explores for work
- Researches with MCP tools
- Consolidates learnings

### Mandatory Worktrees
All orchestrators run in isolated git worktrees for safe parallel development.

---

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Main skill definition for spawning orchestrators |
| `IDLE_BEHAVIOR.md` | Protocol for autonomous idle-time work |
| `HINDSIGHT_INTEGRATION.md` | Memory storage and retrieval patterns |
| `README.md` | This file |

### Output Style

| File | Purpose |
|------|---------|
| `../.claude/output-styles/system3-meta-orchestrator.md` | System 3 personality/behavior |

---

## Usage Examples

### Spawn an Orchestrator
```
Skill("system3-orchestrator", args="spawn authentication-epic")
```

### Check Status
```
Skill("system3-orchestrator", args="status")
```

### Terminate
```
Skill("system3-orchestrator", args="terminate authentication-epic")
```

---

## Hindsight Contexts

| Context | What's Stored |
|---------|--------------|
| `system3-patterns` | Validated successful patterns |
| `system3-anti-patterns` | Failed approaches to avoid |
| `system3-capabilities` | Capability confidence levels |
| `system3-narrative` | Goal-Experience-Outcome chains |
| `system3-active-goals` | Current work and next steps |

---

## Dependencies

- `orchestrator-multiagent` skill (for spawned orchestrators)
- `worktree-manager-skill` (for isolation)
- Hindsight MCP (for memory)
- tmux (for session management)

---

## Theory: Sophia's System 3

From [arXiv:2512.18202](https://arxiv.org/abs/2512.18202):

> System 3 presides over the agent's narrative identity and long-horizon adaptation... grafting a continuous self-improvement loop onto any LLM-centric System 1/2 stack.

Four synergistic mechanisms:
1. **Process-Supervised Thought Search** - Validates reasoning paths
2. **Narrative Memory** - Maintains identity via GEO chains
3. **Self-Model** - Tracks capabilities and gaps
4. **Hybrid Rewards** - Balances external and intrinsic motivation

---

## Version History

- **v1.0** (MVP) - Initial implementation with output-style, system3-orchestrator skill (formerly matryoshka), idle behavior, and Hindsight integration

---

**Author**: System 3 Meta-Orchestrator Team
**License**: Same as parent project
