---
title: "SD: Runner JSONL Event Emitter"
status: active
type: architecture
last_verified: 2026-03-04
grade: reference
---

# Solution Design: Runner JSONL Event Emitter

## Problem

`runner_agent.py` communicates progress to the guardian only via signal files
(polling-based, latency of 30s+ per cycle). Meanwhile, `spawn_runner.py` sends
runner stdout to a log file and detaches immediately — no streaming visibility.

## Design

Add a lightweight JSONL emitter to `runner_agent.py` so that any consumer reading
its stdout (log file tail, or future PIPE-based guardian) gets real-time structured
events.

### Event Schema

Every line is valid JSON with a `type` field and `ts` (ISO-8601 UTC):

```jsonl
{"type":"runner/started","ts":"...","node":"impl_task","prd":"PRD-001","mode":"headless"}
{"type":"runner/state_change","ts":"...","from":"INIT","to":"MONITOR"}
{"type":"runner/cycle_start","ts":"...","cycle":1,"max_cycles":10}
{"type":"runner/node_dispatching","ts":"...","node":"impl_task","worker_mode":"headless"}
{"type":"runner/worker_event","ts":"...","node":"impl_task","event":{"type":"assistant",...}}
{"type":"runner/node_complete","ts":"...","node":"impl_task","exit_code":0,"duration_s":13.2}
{"type":"runner/node_failed","ts":"...","node":"impl_task","exit_code":1,"error":"timeout"}
{"type":"runner/cycle_end","ts":"...","cycle":1,"status":"IN_PROGRESS"}
{"type":"runner/completed","ts":"...","node":"impl_task","final_mode":"COMPLETE"}
```

### Implementation Scope

1. **`runner_agent.py` — `emit_event()` helper** (new function)
   - `json.dumps()` + `print()` + `flush=True`
   - Called at key state transitions in `RunnerStateMachine.run()` and `_do_monitor_mode()`

2. **`runner_agent.py` — `on_event` callback for headless workers**
   - When RunnerStateMachine dispatches headless workers via `spawn_orchestrator.py`,
     forward the `on_event` JSONL events as `runner/worker_event` lines

3. **`spawn_runner.py` — no changes needed**
   - Already redirects stdout to log file — JSONL lines appear there automatically
   - Guardian can `tail -f` or parse the log file for real-time events

### What This Does NOT Change

- Signal protocol remains the authoritative inter-process contract
- `spawn_runner.py` remains fire-and-forget
- Legacy tmux monitoring path is untouched (only state machine path emits JSONL)
- No new dependencies

### Files Modified

| File | Change |
|------|--------|
| `runner_agent.py` | Add `emit_event()`, call it at state transitions |
| `tests/test_runner_agent.py` | Test JSONL emission from state machine |
