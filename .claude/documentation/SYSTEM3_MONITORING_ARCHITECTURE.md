---
title: "System3_Monitoring_Architecture"
status: active
type: architecture
last_verified: 2026-02-19
grade: reference
---

# System3 Monitoring Architecture

## Key Finding

**Only completing subagents can wake the main thread.** External scripts, file changes, and task list updates do NOT trigger notifications to idle Claude sessions.

This shapes the entire monitoring design: **monitors must be subagents that complete when attention is needed.**

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SYSTEM 3 (Main Thread)                            │
│                                                                             │
│  Responsibilities:                                                          │
│  - Strategic planning, PRD management                                       │
│  - Launch orchestrators via tmux                                            │
│  - Receive wake-ups from monitors                                           │
│  - Provide guidance when orchestrators are blocked                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐     │
│   │  Validation      │    │  Orchestrator    │    │  Orchestrator    │     │
│   │  Monitor         │    │  Monitor         │    │  Monitor         │     │
│   │  (background)    │    │  PRD-AUTH-001    │    │  PRD-DASH-002    │     │
│   │                  │    │  (background)    │    │  (background)    │     │
│   │  Watches:        │    │                  │    │                  │     │
│   │  ~/.claude/tasks │    │  Watches:        │    │  Watches:        │     │
│   │                  │    │  tmux:orch-auth  │    │  tmux:orch-dash  │     │
│   └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘     │
│            │                       │                       │                │
│            │ WAKE on:              │ WAKE on:              │ WAKE on:       │
│            │ - task completed      │ - blocked state       │ - blocked      │
│            │ - validation failed   │ - needs guidance      │ - needs input  │
│            │                       │ - worker failed       │ - error loop   │
│            ▼                       ▼                       ▼                │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    SYSTEM 3 WAKE HANDLER                            │  │
│   │  On wake: Analyze situation → Provide guidance OR re-launch monitor │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Monitor Types

### 1. Validation Monitor (Background)

**Purpose**: Watch task list for completed tasks, run validation, wake System3 on issues.

```python
# Pseudo-code for validation monitor behavior
while iterations < MAX_ITERATIONS:
    changes = poll_task_list()

    for task in changes.newly_completed:
        result = run_validation(task)

        if result.failed:
            # COMPLETE immediately to wake System3
            return WakeUp(
                reason="validation_failed",
                task_id=task.id,
                errors=result.errors,
                suggested_action="Review and provide guidance to orchestrator"
            )

    if no_changes_for(5_minutes):
        # Heartbeat - complete to let System3 know we're alive
        return Heartbeat(status="no_issues", tasks_validated=count)

    sleep(10)

# Max iterations reached - complete with summary
return Summary(tasks_validated=total, issues_found=issues)
```

**Launch command**:
```
Task(
    subagent_type="validation-test-agent",
    prompt="--monitor --list-id PRD-AUTH-001 --max-iterations 30",
    run_in_background=True,
    model="sonnet"  # Sonnet required - Haiku lacks exit discipline  # Fast, cheap for monitoring
)
```

### 2. Orchestrator Monitor (Background)

**Purpose**: Watch a tmux orchestrator session for blocked states, errors, or need for guidance.

```python
# Pseudo-code for orchestrator monitor behavior
while iterations < MAX_ITERATIONS:
    # Check tmux session output
    output = capture_tmux_pane(session_name)

    # Analyze for concerning patterns
    if contains_error_loop(output, threshold=3):
        return WakeUp(
            reason="error_loop_detected",
            session=session_name,
            recent_output=output[-500:],
            suggested_action="Orchestrator stuck in error loop, needs guidance"
        )

    if contains_blocking_question(output):
        return WakeUp(
            reason="awaiting_input",
            session=session_name,
            question=extract_question(output),
            suggested_action="Orchestrator needs user decision"
        )

    if worker_failed(output):
        return WakeUp(
            reason="worker_failed",
            session=session_name,
            failure_details=extract_failure(output),
            suggested_action="Worker task failed, orchestrator may need new approach"
        )

    if session_idle_for(10_minutes):
        return WakeUp(
            reason="session_idle",
            session=session_name,
            suggested_action="Orchestrator appears stuck or completed"
        )

    sleep(10)

return Heartbeat(status="orchestrator_running", session=session_name)
```

**Launch command**:
```
Task(
    subagent_type="general-purpose",
    prompt=ORCHESTRATOR_MONITOR_PROMPT.format(
        session_name="orch-auth-feature",
        prd_id="PRD-AUTH-001"
    ),
    run_in_background=True,
    model="sonnet"  # Sonnet required - Haiku lacks exit discipline
)
```

---

## Blocking vs Background Decision

| Scenario | Mode | Rationale |
|----------|------|-----------|
| System3 working on single PRD | **Blocking** | Full attention, immediate response |
| System3 managing multiple PRDs | **Background** | Can't block on one orchestrator |
| Validation of completed task | **Background** | Fire and forget, wake on issues |
| Critical production issue | **Blocking** | Needs immediate attention |

### Implementation Pattern

```python
# In System3 orchestrator skill

def launch_orchestrator_with_monitor(prd_id: str, epic_name: str):
    """Launch orchestrator and its monitor."""

    # 1. Launch the orchestrator in tmux
    session_name = f"orch-{epic_name}"
    launch_tmux_orchestrator(session_name, prd_id)

    # 2. Determine monitor mode
    active_prds = get_active_prd_count()

    if active_prds == 1:
        # Single PRD - can use blocking monitor
        # System3 will wait for monitor to complete
        monitor_mode = "blocking"
    else:
        # Multiple PRDs - use background
        monitor_mode = "background"

    # 3. Launch monitor
    Task(
        subagent_type="general-purpose",
        prompt=ORCHESTRATOR_MONITOR_PROMPT.format(
            session_name=session_name,
            prd_id=prd_id
        ),
        run_in_background=(monitor_mode == "background"),
        model="sonnet"  # Sonnet required - Haiku lacks exit discipline
    )

    return session_name
```

---

## Wake-Up Response Protocol

When System3 receives a wake-up from a monitor:

```
┌─────────────────────────────────────────────────────────────────┐
│  WAKE-UP RECEIVED                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. ANALYZE the wake reason                                     │
│     - validation_failed → Review test results                   │
│     - error_loop → Check orchestrator context                   │
│     - awaiting_input → Read the question                        │
│     - worker_failed → Assess failure scope                      │
│     - session_idle → Check if work complete                     │
│                                                                 │
│  2. DECIDE action                                               │
│     - Provide guidance via tmux injection                       │
│     - Inject into tmux session                                  │
│     - Mark task for manual review                               │
│     - Close task as failed                                      │
│     - Re-scope and create new tasks                             │
│                                                                 │
│  3. RE-LAUNCH monitor                                           │
│     - After providing guidance, restart the monitor             │
│     - Monitor will watch for resolution                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Integration with Existing Systems

### Task List ID Convention

```
CLAUDE_CODE_TASK_LIST_ID = PRD-{category}-{number}

Examples:
- PRD-AUTH-001  → Authentication feature
- PRD-DASH-002  → Dashboard feature
- PRD-API-003   → API integration
```

### Monitor State Files

```
~/.claude/tasks/{TASK_LIST_ID}/           # Task files
/tmp/.task-monitor-{TASK_LIST_ID}.json    # Monitor state (change detection)
/tmp/.orch-monitor-{session_name}.json    # Orchestrator monitor state
```

---

## Implementation Checklist

- [ ] Create `orchestrator-monitor` agent template in `.claude/agents/`
- [ ] Create `validation-monitor` agent template
- [ ] Update System3 skill to launch monitors with orchestrators
- [ ] Add monitor re-launch logic to wake-up handler
- [ ] Implement tmux output analysis patterns (error loop, blocking question, idle)
- [x] Use Sonnet for monitors (Haiku lacks exit discipline - see test 2026-01-25)
- [ ] Create heartbeat/timeout handling for long-running monitors

---

## Cost Considerations

| Monitor Type | Model | Est. Cost/Hour | Justification |
|--------------|-------|----------------|---------------|
| Validation | Sonnet | ~$0.15 | Exit discipline required - Haiku gets distracted |
| Orchestrator | Sonnet | ~$0.15 | Pattern matching + reliable completion |
| System3 | Opus | ~$0.50 | Complex reasoning when woken |

**Why Sonnet over Haiku for monitors?**

Testing (2026-01-25) showed Haiku validated correctly but failed to RETURN:
- ✅ Detected task completion
- ✅ Ran validation tests (5 passed)
- ❌ Kept adding documentation instead of exiting
- ❌ Had to be manually killed

Sonnet's higher cost is justified by reliable exit behavior.

**Key insight**: Monitors use cheap Haiku, System3 only uses Opus when actually needed.
