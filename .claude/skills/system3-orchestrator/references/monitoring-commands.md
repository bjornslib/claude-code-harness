# Monitoring Commands Reference

> Extracted from `system3-meta-orchestrator.md` to reduce output style context size.
> This is lookup/reference material for monitoring spawned orchestrators.

---

## Step 1: Launch Background Validation-Agents (one per orchestrator)

```python
# For each orchestrator, spawn a background Sonnet monitor for deep validation
orchestrator_sessions = ["orch-live-form-ui", "orch-employer-data-model"]

for orch_session in orchestrator_sessions:
    Task(
        subagent_type="validation-test-agent",
        model="sonnet",  # Sonnet has exit discipline; Haiku doesn't
        run_in_background=True,  # Non-blocking
        description=f"Background monitor: {orch_session}",
        prompt=f"--mode=monitor --session-id={orch_session} --task-list-id=PRD-XXX"
    )
```

## Step 2: Launch ONE Blocking Haiku Watcher (monitors ALL orchestrators)

```python
# This keeps System 3 alive and reports when ANY orchestrator needs attention
orchestrator_sessions = ["orch-live-form-ui", "orch-employer-data-model"]
session_list = ", ".join(orchestrator_sessions)

Task(
    subagent_type="general-purpose",
    model="haiku",
    run_in_background=False,  # BLOCKING - keeps System 3 alive
    description="Blocking watcher for all orchestrators",
    prompt=f'''You are monitoring these orchestrators: {session_list}

## Your Mission
Poll all orchestrators periodically. Report back to System 3 IMMEDIATELY when ANY orchestrator:
1. **COMPLETE**: Signals work is done
2. **BLOCKED**: Stuck on same issue for >10 minutes
3. **NEEDS_INPUT**: Waiting for user/System3 guidance
4. **OFF_COURSE**: Modifying files outside scope or repeating actions
5. **ERROR**: Same error repeated 3+ times

## Monitoring Commands
Check each orchestrator every 30-60 seconds:

```bash
# Capture recent output (use session name for each orchestrator)
tmux capture-pane -t "ORCHESTRATOR_NAME" -p -S -100 2>/dev/null | tail -80
```

Also check beads progress:
```bash
bd list --status=in_progress
bd list --status=closed | tail -5
```

## What "COMPLETE" Looks Like

An orchestrator is DONE when you see these signs in the tmux output:

1. **Final work report** — The orchestrator summarizes what it accomplished (files changed, tasks completed, commits made). This is typically a structured summary near the end of output.
2. **Code committed and pushed** — You see `git commit` and `git push` commands with successful output (no errors).
3. **Stop hook passed** — The orchestrator's session is winding down. You may see stop hook output or the Claude Code session exiting.
4. **Claude Code exited** — The tmux pane shows a bash `$` prompt instead of Claude's `>` prompt, meaning Claude Code has exited.
5. **tmux session gone** — `tmux has-session -t ORCHESTRATOR_NAME 2>/dev/null` returns non-zero (session no longer exists).

**Any ONE of signs 4 or 5 is definitive** — report COMPLETE immediately.
**Signs 1+2 together are strong evidence** — report COMPLETE.
**Sign 1 alone** — wait one more poll cycle to confirm, then report COMPLETE.

## Progress Indicators (Good Signs — Orchestrator Still Working)
- Tasks being closed (`bd close`)
- Files being edited matching scope
- Tests being run
- Commits being made
- Workers being spawned or receiving results

## Red Flags (Report Immediately)
- "I'm stuck", "blocked", "need help", "waiting for"
- Same file edited >5 times without commit
- No activity for >10 minutes
- Repeated errors in output
- Questions directed at user without response

## Report Format
When ANY orchestrator needs attention:
```
STATUS: [COMPLETE|BLOCKED|NEEDS_INPUT|OFF_COURSE|ERROR]
ORCHESTRATOR: [which one]
SUMMARY: [What happened]
LAST_ACTIVITY: [What it was doing]
RECOMMENDED_ACTION: [What System 3 should do]
```

## Important
- Report as soon as ONE orchestrator needs attention (don't wait for all)
- Include which specific orchestrator needs help
- System 3 will send guidance and may relaunch you to continue watching

Begin monitoring now.
'''
)
```

## Why This Pattern Works

| Component | Role | Model | Blocking? |
|-----------|------|-------|-----------|
| validation-test-agent monitors | Deep validation, complex checks, exit discipline | Sonnet | No (background) |
| Haiku watcher | Fast polling, session keep-alive, first-to-report | Haiku | Yes (blocking) |

**Benefits:**
- System 3 stays alive (blocking Haiku watcher)
- Scalable to N orchestrators (one watcher monitors all)
- Immediate intervention when any orchestrator needs help
- Deep validation runs in parallel (Sonnet monitors with proper exit discipline)

## Model Selection for Monitors

| Monitor Type | Model | Reason |
|--------------|-------|--------|
| validation-test-agent --mode=monitor | **Sonnet** | Exit discipline required - Haiku keeps working instead of returning |
| Blocking watcher | **Haiku** | Simple polling task, fast and cheap, exit discipline not critical |

**Why not Haiku for validation-test-agent?** Testing (2026-01-25) showed:
- Haiku validated correctly (5 tests passed)
- Haiku failed to EXIT - kept writing documentation
- Sonnet returned promptly: "MONITOR_COMPLETE: Task #15 validated"

## tmux Monitoring Techniques

```bash
# View recent output without attaching
tmux capture-pane -t orch-epic4 -p | tail -30

# Attach to see full terminal (detach with Ctrl+B, D)
tmux attach-session -t orch-epic4

# List all orchestrator sessions
tmux list-sessions | grep "^orch-"
```

## MANDATORY: Review Final Report Before Cleanup

**When a monitor reports an orchestrator is COMPLETE, do NOT kill the session immediately.** First, capture and review the orchestrator's final output to understand what was actually accomplished.

### Step 1: Capture the Orchestrator's Final Report

```bash
# Capture the last 150 lines — this contains the orchestrator's final summary,
# git commits, push output, and any completion messages
tmux capture-pane -t orch-[initiative] -p -S -200 2>/dev/null | tail -150
```

**Read this output.** Look for:
- What tasks were completed and what files were changed
- Whether code was committed and pushed (and to which branch)
- Any warnings, skipped items, or known issues the orchestrator flagged
- The orchestrator's own summary of what it accomplished

This is how you verify the monitor's COMPLETE status is real and understand the scope of delivered work.

### Step 2: Cleanup

Only AFTER reviewing the final report:

```bash
# Kill the orchestrator's tmux session
tmux kill-session -t orch-[initiative] 2>/dev/null && echo "Cleaned up: orch-[initiative]"

# Verify cleanup
remaining=$(tmux list-sessions 2>/dev/null | grep -c "^orch-" || echo "0")
echo "Remaining orchestrator sessions: $remaining"
```

**Note**: Workers are now native teammates managed by the team lead (orchestrator). Shut down workers via `SendMessage(type="shutdown_request")` and clean up teams via `Teammate(operation="cleanup")` before killing the orchestrator tmux session.

**Why review first**: Killing the tmux session destroys the orchestrator's output. If you kill first, you lose visibility into what was done, any issues flagged, and whether the work actually matches expectations.

### Cleanup Triggers

| Event | Action |
|-------|--------|
| Orchestrator COMPLETE | Kill `orch-*` tmux session |
| Orchestrator BLOCKED (abandoned) | Kill `orch-*` tmux session |
| System 3 session end | Kill ALL remaining `orch-*` sessions |
