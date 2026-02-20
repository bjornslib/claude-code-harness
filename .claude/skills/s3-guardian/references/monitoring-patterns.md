---
title: "Monitoring Patterns"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# Monitoring Patterns Reference

Commands, signal detection, intervention protocols, and red flags for continuous tmux monitoring of S3 operators.

---

## 1. tmux Capture Commands

### Basic Output Capture

```bash
# Capture visible pane content (what you would see on screen)
tmux capture-pane -t "s3-{initiative}" -p

# Capture with scrollback history (last 100 lines)
tmux capture-pane -t "s3-{initiative}" -p -S -100

# Capture with extended scrollback (last 500 lines — for deep investigation)
tmux capture-pane -t "s3-{initiative}" -p -S -500

# Capture only the last N lines (tail equivalent)
tmux capture-pane -t "s3-{initiative}" -p -S -100 | tail -20
```

### Targeted Signal Detection

```bash
# Check for task completion signals
tmux capture-pane -t "s3-{initiative}" -p -S -100 | grep -iE "complete|done|finished|merged"

# Check for error signals
tmux capture-pane -t "s3-{initiative}" -p -S -100 | grep -iE "error|failed|exception|traceback"

# Check for blocking signals (AskUserQuestion, permission dialogs)
tmux capture-pane -t "s3-{initiative}" -p -S -50 | grep -iE "AskUser|permission|approve|reject|y/n|yes/no"

# Check for orchestrator spawning activity
tmux capture-pane -t "s3-{initiative}" -p -S -100 | grep -iE "orch-|tmux|worktree|spawn"

# Check for context exhaustion signals
tmux capture-pane -t "s3-{initiative}" -p -S -50 | grep -iE "compact|context|token|limit"

# Check for worker activity
tmux capture-pane -t "s3-{initiative}" -p -S -100 | grep -iE "Task\(|teammate|worker|subagent"

# Check for shutdown or idle signals
tmux capture-pane -t "s3-{initiative}" -p -S -50 | grep -iE "shutdown|idle|sleep|waiting|stop"
```

### Session Health Check

```bash
# Verify session exists
tmux has-session -t "s3-{initiative}" 2>/dev/null && echo "ALIVE" || echo "DEAD"

# List all system3 sessions
tmux list-sessions 2>/dev/null | grep "^s3-"

# Check session dimensions (in case of rendering issues)
tmux display-message -t "s3-{initiative}" -p "#{pane_width}x#{pane_height}"
```

---

## 2. Key Signals and Their Meaning

### Positive Signals (Operator is Making Progress)

| Signal Pattern | Meaning | Guardian Action |
|---------------|---------|-----------------|
| `Task(subagent_type=` | Operator is spawning workers | Continue monitoring |
| `bd ready` / `bd list` | Operator is checking work queue | Continue monitoring |
| `git commit` / `git push` | Code is being committed | Note for later validation |
| `cs-promise --meet` | Operator is claiming AC completion | Note claim for independent verification |
| `MONITOR_COMPLETE` | Validation monitor reports all tasks done | Prepare for Phase 4 validation |
| `All tests pass` / `pytest` | Test suite is running | Note results for cross-reference |

### Negative Signals (Potential Problems)

| Signal Pattern | Meaning | Guardian Action |
|---------------|---------|-----------------|
| `AskUserQuestion` | Operator or worker is blocked on a dialog | Intervene: navigate and confirm |
| `permission` / `approve` | Permission dialog blocking progress | Intervene: approve via Down/Enter |
| `Error` / `Exception` (3+ times) | Repeated failure | Assess: is it the same error? Send guidance |
| `stuck` / `blocked` | Operator self-reports being stuck | Send guidance or corrective instruction |
| `TODO` / `FIXME` markers growing | Deferred work accumulating | Flag for validation, may lower scores |
| No output for 5+ minutes | Session may be idle or crashed | Investigate: capture full pane |
| `context` / `compact` / `90%` | Context window filling up | Expect auto-compact, verify recovery |
| `CLAUDECODE` error | Nested session error | Session needs restart with `unset CLAUDECODE` |

### Completion Signals (Operator Claims Done)

| Signal Pattern | Meaning | Guardian Action |
|---------------|---------|-----------------|
| `All epics complete` | Operator claims initiative is done | Begin Phase 4 validation |
| `cs-verify --check` passing | Completion promise criteria met | Verify independently |
| `MONITOR_COMPLETE: Task #N validated` | Validation monitor confirms task done | Cross-reference with rubric |
| Operator outputs final summary | Session is wrapping up | Capture summary, begin validation |

---

## 3. AskUserQuestion Intervention

AskUserQuestion dialogs are the most common blocking issue. They appear when:
- A worker finishes its task and asks for next steps
- The stop gate judge asks if the session should continue
- A tool needs permission approval
- An orchestrator asks for strategic direction

### Intervention Protocol

```bash
# Step 1: Identify what is being asked
tmux capture-pane -t "s3-{initiative}" -p -S -20

# Step 2: Determine appropriate response
# For permission dialogs (most common):
tmux send-keys -t "s3-{initiative}" Down    # Navigate to approve/yes
tmux send-keys -t "s3-{initiative}" Enter   # Confirm

# For "continue working?" dialogs:
tmux send-keys -t "s3-{initiative}" Enter   # Accept default (usually "yes")

# For strategic questions that need real input:
tmux send-keys -t "s3-{initiative}" "Focus on the PRD scope. Complete the current epic before starting new work."
sleep 2
tmux send-keys -t "s3-{initiative}" Enter
```

### Common Dialog Patterns

| Dialog Pattern | Response |
|---------------|----------|
| `[Y/n]` | Enter (accept default yes) |
| Permission to use tool X | Down, Enter (approve) |
| "Should I continue?" | Enter (yes) |
| "Which option?" with choices | Read choices, select most aligned with PRD scope |
| "Should I stop?" | Depends on progress — assess first |

### Important Caveats

- `tmux send-keys` sends keystrokes but CANNOT interact with Claude Code's built-in permission dialogs at the SDK level. Some dialogs require killing the session.
- After sending keys, wait 2-3 seconds and re-check the pane to verify the dialog was resolved.
- If the same dialog reappears after intervention, the session may be in a loop. Consider killing and restarting.

---

## 4. Red Flags to Watch For

### Scope Creep Indicators

```bash
# Check for work outside PRD scope
tmux capture-pane -t "s3-{initiative}" -p -S -200 | grep -iE "also|bonus|extra|while we're at it|might as well"

# Check for refactoring tangents
tmux capture-pane -t "s3-{initiative}" -p -S -200 | grep -iE "refactor|cleanup|reorganize|restructure"
```

**When to intervene**: If the operator spends more than 10 minutes on work not referenced in the PRD, send a correction:

```bash
tmux send-keys -t "s3-{initiative}" "GUARDIAN NOTICE: Focus on PRD scope. Current work appears outside scope. Return to {next_prd_task}."
sleep 2
tmux send-keys -t "s3-{initiative}" Enter
```

### Repeated Error Patterns

Track error occurrences across monitoring cycles. Maintain a mental count:

| Error Count | Action |
|-------------|--------|
| 1 | Note it, continue monitoring |
| 2 | Check if same error — may be a retry in progress |
| 3 | Assess: is the operator stuck in a loop? |
| 4+ | Intervene with guidance or restart suggestion |

### Time-Based Red Flags

| Duration | Expected Progress | Red Flag If |
|----------|------------------|-------------|
| 0-15 min | PRD reading, task parsing | Still configuring environment |
| 15-45 min | First workers spawned, implementation starting | No workers spawned yet |
| 45-90 min | Multiple features implemented, tests running | Only 1 feature done |
| 90-120 min | Most features complete, validation beginning | Less than 50% done |
| 120+ min | Should be wrapping up or very close | Major features still pending |

### TODO/FIXME Accumulation

```bash
# Count TODO markers in the implementation repo
git -C /path/to/impl-repo grep -c "TODO\|FIXME\|HACK\|XXX" -- "*.py" "*.ts" "*.js" 2>/dev/null
```

A growing TODO count suggests the operator is deferring work rather than completing it. Each TODO reduces the maximum achievable score for the relevant feature.

---

## 5. When to Intervene vs When to Wait

### Always Intervene

- AskUserQuestion/permission dialog blocking progress
- Session has crashed (tmux session dead but work incomplete)
- Operator is clearly working on wrong PRD or wrong repo
- Critical error that prevents all forward progress

### Usually Wait

- Operator is retrying an error (give 2-3 attempts)
- Context is compacting (wait for recovery, usually 30-60 seconds)
- Workers are running in background (operator may appear idle)
- Operator is reading/investigating before acting

### Never Intervene

- Operator's coding style differs from preference (implementation detail)
- Operator chose a different technical approach than expected (as long as it meets PRD)
- Operator is running tests (even if they fail — let the cycle complete)
- Operator is communicating with workers via native teams

---

## 6. Context Percentage Monitoring

Claude Code sessions have finite context windows. When context fills up, auto-compact triggers.

### Thresholds

| Context % | Status | Guardian Concern |
|-----------|--------|-----------------|
| 0-60% | Healthy | None |
| 60-80% | Filling | Normal for active sessions |
| 80-90% | High | Expect auto-compact soon |
| 90%+ | Critical | Auto-compact should trigger. If it doesn't, session may stall |

### Detecting Context Issues

```bash
# Look for context warnings in output
tmux capture-pane -t "s3-{initiative}" -p -S -50 | grep -iE "context|compact|token|limit|truncat"

# If auto-compact triggered, verify recovery
sleep 60  # Wait for compact to complete
tmux capture-pane -t "s3-{initiative}" -p -S -20  # Check for resumed activity
```

### Post-Compact Verification

After an auto-compact event:
1. Wait 30-60 seconds for the compact to complete
2. Check that the operator resumes work (not stuck in a confused state)
3. Verify the output style is still active (compact can sometimes reset context)
4. If the operator seems confused about its mission, send a brief reminder

---

## 7. Multi-Session Monitoring

When monitoring multiple S3 operators in parallel:

### Round-Robin Pattern

```bash
# Monitor session A
tmux capture-pane -t "s3-initiative-a" -p -S -50
sleep 2

# Monitor session B
tmux capture-pane -t "s3-initiative-b" -p -S -50
sleep 2

# Monitor session C
tmux capture-pane -t "s3-initiative-c" -p -S -50
sleep 2

# Repeat cycle
```

### Priority-Based Monitoring

Check sessions in priority order:
1. Sessions with known issues (errors, blocks) — check every cycle
2. Sessions in active implementation — check every 2 cycles
3. Sessions in investigation/planning — check every 4 cycles
4. Sessions waiting for workers — check every 6 cycles

### Cross-Session Awareness

Watch for:
- Two operators modifying the same files (merge conflict risk)
- One operator's output referencing another's work (scope boundary violation)
- Shared resource contention (database, API rate limits)

---

**Reference Version**: 0.1.0
**Parent Skill**: s3-guardian
