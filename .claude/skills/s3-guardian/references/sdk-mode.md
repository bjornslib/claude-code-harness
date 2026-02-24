# SDK Mode: Automated Pipeline Execution

## Overview

SDK mode replaces Phase 2 (manual tmux spawning) and Phase 3 (tmux polling) with an automated 4-layer Agent SDK chain. The Guardian launches a Headless Guardian subprocess which autonomously manages the entire pipeline.

## Architecture

```
Layer 0: Terminal Guardian (this session)
    └── launch_guardian.py
        └── Layer 1: Headless Guardian (guardian_agent.py, Agent SDK)
            └── Layer 2: Runner (runner_agent.py, Agent SDK)
                └── Layer 3: Orchestrator (tmux + ccorch, interactive)
                    └── Workers (native Agent Teams)
```

## How Signal Files Work

The 4-layer chain communicates via JSON signal files on disk. Each layer writes signals to a shared directory and polls for responses. The Terminal Guardian (Layer 0 — this session) needs to understand this flow to know what to look for.

### Signal Directory

All signal files live in `.claude/attractor/signals/` (or `$ATTRACTOR_SIGNALS_DIR` if set):

```
.claude/attractor/signals/
├── 20260224T120000Z-runner-guardian-NEEDS_REVIEW.json     ← Runner asking Guardian for help
├── 20260224T120030Z-guardian-runner-VALIDATION_PASSED.json ← Guardian responding
├── 20260224T123000Z-guardian-terminal-ESCALATE.json       ← Guardian escalating to YOU
└── processed/                                              ← Consumed signals moved here
```

### Signal File Format

Every signal is a JSON file with this schema:

```json
{
    "source": "runner",
    "target": "guardian",
    "signal_type": "NEEDS_REVIEW",
    "timestamp": "20260224T120000Z",
    "payload": {
        "node_id": "impl_auth",
        "evidence_path": ".claude/evidence/impl_auth/",
        "summary": "All tests pass, ready for review"
    }
}
```

### File Naming Convention

`{timestamp}-{source}-{target}-{signal_type}.json`

This lets you find relevant signals with simple glob patterns:
- All signals FOR you: `ls .claude/attractor/signals/*-terminal-*.json`
- All signals FROM the guardian: `ls .claude/attractor/signals/*-guardian-*.json`

### What the Terminal Guardian Watches For

As Layer 0, you only need to watch for signals with `target: "terminal"`. There are three:

| Signal | Written By | Meaning | Your Action |
|--------|-----------|---------|-------------|
| `PIPELINE_COMPLETE` | Guardian (via `escalate_to_terminal.py`) | All pipeline nodes validated/failed | Proceed to Phase 4 validation |
| `ESCALATION` | Guardian (via `escalate_to_terminal.py`) | Guardian hit a problem it cannot resolve | Read payload, decide: retry, manual fix, or forward to user |
| `GUARDIAN_ERROR` | Guardian (crash detection) | Guardian subprocess died | Check DOT status, re-launch from checkpoint |

### How Signals Flow During Normal Execution

```
1. Guardian reads DOT → finds pending node → spawns Runner
2. Runner spawns Orchestrator in tmux → monitors tmux output
3. Orchestrator completes work → Runner detects completion
4. Runner writes: signal_guardian.py NODE_COMPLETE --node impl_auth
   → Creates .claude/attractor/signals/...-runner-guardian-NODE_COMPLETE.json
5. Guardian reads signal (via wait_for_signal.py --target guardian)
   → Validates the work
6. Guardian writes: respond_to_runner.py VALIDATION_PASSED --node impl_auth
   → Creates .claude/attractor/signals/...-guardian-runner-VALIDATION_PASSED.json
7. Guardian transitions DOT node to "validated"
8. Repeat for next node...
9. When all nodes terminal:
   Guardian writes: escalate_to_terminal.py --pipeline PRD-{ID} --issue "PIPELINE_COMPLETE: all nodes validated"
   → Creates .claude/attractor/signals/...-guardian-terminal-ESCALATE.json
10. Terminal Guardian (you) reads this signal → proceeds to Phase 4
```

### Processed Signals

After a signal is read, it is moved to `signals/processed/`. This prevents re-reading. If you need to inspect old signals for debugging:

```bash
ls .claude/attractor/signals/processed/
```

---

## Phase 2-SDK: Pipeline Execution

### Prerequisites

- `claude-code-sdk >= 0.0.25` installed
- `ANTHROPIC_API_KEY` set
- DOT pipeline exists with bead IDs mapped
- Implementation repo accessible

### Launch Single Pipeline

```bash
# Dry-run (verify config, no API calls)
python3 /path/to/impl-repo/.claude/scripts/attractor/launch_guardian.py \
    --dry-run \
    --dot /path/to/pipeline.dot \
    --pipeline-id PRD-{ID} \
    --project-root /path/to/impl-repo

# Real execution
python3 /path/to/impl-repo/.claude/scripts/attractor/launch_guardian.py \
    --dot /path/to/pipeline.dot \
    --pipeline-id PRD-{ID} \
    --project-root /path/to/impl-repo \
    --model claude-sonnet-4-6 \
    --max-turns 200 \
    --signal-timeout 600 \
    --max-retries 3
```

### Launch Multiple Pipelines (Parallel)

```python
from launch_guardian import launch_multiple_guardians

results = await launch_multiple_guardians([
    {"dot_path": "auth.dot", "project_root": "/impl", "pipeline_id": "PRD-AUTH-001"},
    {"dot_path": "dash.dot", "project_root": "/impl", "pipeline_id": "PRD-DASH-002"},
])
```

### What Happens Internally

The chain handles all orchestrator lifecycle management automatically:

1. **Headless Guardian** (Layer 1) reads the DOT pipeline
2. For each ready codergen node, spawn a **Runner** (Layer 2)
3. Runner spawns an **Orchestrator** (Layer 3) in tmux
4. Runner monitors orchestrator output via LLM interpretation
5. Runner signals Guardian at decision points
6. Guardian makes decisions (validate, retry, escalate to Layer 0)
7. Guardian transitions pipeline nodes and saves checkpoints
8. When all nodes are terminal, signal Layer 0 with `PIPELINE_COMPLETE`

### Signal Flow

Layers communicate via JSON signal files in `.claude/attractor/signals/{pipeline_id}/`:

| Direction | Signal Types |
|-----------|-------------|
| Runner to Guardian | `NEEDS_REVIEW`, `NEEDS_INPUT`, `VIOLATION`, `ORCHESTRATOR_STUCK`, `ORCHESTRATOR_CRASHED`, `NODE_COMPLETE` |
| Guardian to Runner | `VALIDATION_PASSED`, `VALIDATION_FAILED`, `INPUT_RESPONSE`, `KILL_ORCHESTRATOR`, `GUIDANCE` |
| Guardian to Terminal | `PIPELINE_COMPLETE`, `ESCALATION`, `GUARDIAN_ERROR` |

---

## Phase 3-SDK: Signal Monitoring

### Signal Watcher (Blocking Haiku Subagent)

After launching the Guardian, spawn a blocking Haiku subagent to watch for terminal-targeted signals. This is more efficient than polling in the main thread — the subagent runs cheaply and returns when a signal arrives, waking the Terminal Guardian.

```python
SIGNALS_DIR = f"{IMPL_REPO}/.claude/attractor/signals"

result = Task(
    subagent_type="general-purpose",
    model="haiku",
    run_in_background=False,  # BLOCKING — Terminal Guardian waits
    description="Watch for Guardian signals",
    prompt=f"""
You are a signal file watcher. Your ONLY job: poll for terminal-targeted
signals and return them.

Signals directory: {SIGNALS_DIR}

## Polling Loop

Every 10 seconds, run:

```bash
ls {SIGNALS_DIR}/*-terminal-*.json 2>/dev/null
```

## Rules
- If a file matches: read it with the Read tool, parse the JSON
- Return EXACTLY one of:
  - "SIGNAL_RECEIVED: PIPELINE_COMPLETE: <payload summary>"
  - "SIGNAL_RECEIVED: ESCALATION: <issue text>"
  - "SIGNAL_RECEIVED: GUARDIAN_ERROR: <error text>"
- If no files match: sleep 10s, try again
- Max 360 attempts (1 hour). If timeout:
  - Return "SIGNAL_TIMEOUT: No signal in 1 hour"
- Do NOT do anything else. No exploration, no investigation.
- Return as soon as you have a result. EXIT IMMEDIATELY.
"""
)
```

**Handling the result:**

| Result | Meaning | Action |
|--------|---------|--------|
| `SIGNAL_RECEIVED: PIPELINE_COMPLETE` | All nodes terminal | Proceed to Phase 4 |
| `SIGNAL_RECEIVED: ESCALATION` | Guardian needs help | Parse payload, decide: retry, manual fix, or forward to user |
| `SIGNAL_RECEIVED: GUARDIAN_ERROR` | Guardian crashed | Check DOT status, re-launch from checkpoint |
| `SIGNAL_TIMEOUT` | Guardian may be stuck | Check `cli.py status pipeline.dot --summary`, re-launch or fall back to tmux mode |

**Re-launch pattern (cyclic wake-up):**

After handling any signal except PIPELINE_COMPLETE, re-spawn the signal watcher:

```
Terminal Guardian                Signal Watcher (Haiku)        Guardian (Layer 1)
      │                              │                              │
      │── spawn watcher ────────────►│                              │
      │   (blocking)                 │◄── poll signals dir ─────── │
      │                              │    no match, sleep 10s       │
      │                              │◄── poll again ──────────────│
      │                              │    FOUND: *-terminal-*.json  │
      │◄── SIGNAL_RECEIVED ─────────│    (agent exits)             │
      │                              │                              │
      │── handle signal              │                              │
      │── re-spawn watcher ─────────►│  (cycle repeats)            │
```

### Crash Recovery

Pipeline state survives Guardian crashes (stored in DOT + checkpoints):

1. Check state: `cli.py status pipeline.dot --json`
2. Re-launch Guardian — resumes from last checkpoint
3. Already-validated nodes are skipped

### Falling Back to tmux Mode

If the SDK chain gets stuck on specific nodes:

1. Check unfinished nodes: `cli.py status pipeline.dot --filter=pending`
2. Kill the Guardian subprocess
3. Manually spawn orchestrators for remaining nodes using Phase 2 (tmux mode) patterns
4. Continue with Phase 3 (tmux mode) monitoring

---

## CLI Reference

| Script | Purpose | Layer |
|--------|---------|-------|
| `launch_guardian.py` | Terminal to Guardian bridge | 0 to 1 |
| `guardian_agent.py` | Pipeline execution engine | 1 |
| `runner_agent.py` | Orchestrator monitor | 2 |
| `signal_protocol.py` | Signal file I/O | All |
| `wait_for_signal.py` | Blocking signal wait | All |
| `signal_guardian.py` | Runner to Guardian signal | 2 to 1 |
| `respond_to_runner.py` | Guardian to Runner response | 1 to 2 |
| `escalate_to_terminal.py` | Guardian to Terminal escalation | 1 to 0 |

---

## Signal Protocol Session Scoping

Signal files are stored in a flat directory by default. For concurrent Guardian executions, set `ATTRACTOR_SIGNALS_DIR` to a pipeline-specific path to prevent cross-talk. Single-pipeline usage (the common case) works without any special configuration.

---

## Detailed CLI Reference

For exact argparse flags, output JSON schemas, and signal routing for all 15 SDK mode scripts, see `references/sdk-cli-tools.md`.
