# GasCity/Gastown Architecture Research — 2026-04-03

**Status**: Research complete. Awaiting user decision on next steps.
**Hindsight**: Server unreachable — retain to both banks when available.

## What Are They?

- **Gastown** (Steve Yegge, github.com/gastownhall/gastown): Enterprise multi-agent AI orchestration framework. Go-based. Core concepts: Mayor (coordinator), Witness (lifecycle), Polecats (ephemeral workers), Convoys (batched work), Refinery (merge queue).
- **GasCity** (github.com/gastownhall/gascity): Extracted SDK from Gastown. 5 irreducible primitives: Agent Protocol, Bead Store, Event Bus, Config, Prompt Templates. 4 derived mechanisms: Messaging, Formulas/Molecules, Dispatch (Sling), Health Patrol.

## Key Architecture Patterns

1. **Pull-based work discovery**: Agents poll `bd ready --assignee` or `bd ready --label=pool:<name>`. No push dispatcher.
2. **Controller reconciliation loop**: 30s tick, 4-state machine (not-running/healthy/orphan/drifted), fsnotify config reload.
3. **Pool agents**: Dynamic scaling based on `check` command results. Work-stealing from shared pools.
4. **Formulas/Molecules**: Reusable workflow templates instantiated at runtime. Wisps (ephemeral) auto-GC via TTL.
5. **Convoy auto-closure**: Parent beads auto-close when all children resolve.
6. **Health Patrol**: Erlang/OTP-style supervision — crash loop quarantine, drift detection (SHA-256), idle timeout.
7. **Messaging-as-beads**: Inter-agent mail uses same bead store. Threading via labels.
8. **GUPP principle**: "Get Usage, Process Placed" — agents execute immediately without confirmation.

## Complementarity with CoBuilder

### GasCity Excels At (CoBuilder Lacks)

| Capability | GasCity Pattern | CoBuilder Gap |
|------------|----------------|---------------|
| Work allocation | Pull-based discovery + pool routing + orders (cron/event) | Push-only via dispatch_worker.py |
| Agent health | Erlang/OTP supervision, crash loop quarantine, drift detection | gate_watch.py filesystem polling, no crash recovery |
| Dynamic scaling | Pool agents scale up/down based on check commands | Fixed worker assignment per DOT node |
| Inter-agent messaging | Beads-based mail + nudge notifications | Signal files (machine) + GChat (human), no agent-to-agent |
| Reusable workflows | Formulas (.formula.toml) → runtime molecules (ephemeral wisps) | Jinja2 DOT templates require explicit instantiation |
| Config hot-reload | fsnotify watches city.toml | Requires pipeline restart |

### CoBuilder Excels At (GasCity Lacks)

| Capability | CoBuilder Pattern | GasCity Gap |
|------------|-------------------|------------|
| Deterministic execution | DOT DAG with topological ordering + dependency edges | No pipeline graph — work allocated individually |
| Stepped quality gates | research → refine → codergen → wait.cobuilder → wait.human | Post-hoc validation only, no structural enforcement |
| Blind acceptance testing | Tests stored where workers can't see them, scored against hidden rubric | No information asymmetry by design |
| Pipeline observability | 18 event types, JSONL + Logfire + SignalBridge triple-backend, TUI viewer | Append-only event log, simpler |
| Checkpoint/resume | Snapshot pipeline state, resume from any checkpoint | Bead status persists but no coordinated graph resume |
| Graph templates | Jinja2 templates for sequential-validated, hub-spoke, cobuilder-lifecycle | No structural workflow templates |

### Shared Foundation: Beads

Both systems use beads (`bd`) as the fundamental work unit. This is the natural integration point — not a coincidence but convergent design.

## Proposed Integration Architecture

```
CoBuilder Guardian (S1) — Deterministic ordering + quality gates
    │
    │ Transitions DOT node to "active" → creates bead with pool label
    ▼
GasCity Controller (S2) — Work allocation + agent health
    │
    │ Detects work via pool check → starts/scales pool agent
    ▼
Pool Agent (S3) — Claims bead, executes, signals completion
    │
    │ Writes signal file (CoBuilder) + bd close (GasCity)
    ▼
Pipeline Runner — Detects signal → transitions node → next in DAG
```

**Key change**: pipeline_runner.py creates labeled beads instead of calling dispatch_worker.py directly. GasCity controller manages agent lifecycle (start, health, crash recovery, idle timeout). CoBuilder retains DAG ordering and gate validation.

## Relation to Claw-Code Initiative

PRD-CLAWCODE-COBUILDER-001 designed a two-way integration (CoBuilder ↔ claw-code). GasCity introduces a more composable three-way architecture:

- **CoBuilder**: Pipeline orchestration (ordering, gates, validation)
- **GasCity**: Agent runtime management (allocation, health, scaling)
- **claw-code/Claude SDK**: Execution runtime (LLM interaction)

## Recommended Next Steps

### Phase 1: Deep Research
- Clone GasCity repo, study Go source: controller.go, sling.go, patrol.go, store.go
- Map CoBuilder dispatch_worker.py → GasCity dispatch path
- Identify minimal viable integration surface

### Phase 2: Business Spec
- Write BS for "GasCity Integration" with 3 epics:
  1. Controller adoption — replace gate_watch.py with GasCity reconciliation
  2. Pool-based dispatch — pipeline runner creates labeled beads
  3. Health patrol — crash recovery and idle timeout for pipeline workers

### Phase 3: Prototype
- Install GasCity alongside CoBuilder harness
- Create city.toml managing CoBuilder workers as pool agents
- Run single DOT pipeline through hybrid path

### Phase 4: Convergence
- CoBuilder templates generate GasCity formulas
- Guardian validates using convoy status + signal protocol
- Unified observability: GasCity events → CoBuilder event bus
