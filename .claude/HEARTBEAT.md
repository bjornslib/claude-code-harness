# Heartbeat Check Instructions

Configuration for the S3 Communicator heartbeat cycle.
Empty this file to disable all checks (HEARTBEAT_OK early return).

## Active Hours
- Start: 8
- End: 22
- Weekend: false

## Beads Status Check

Check for actionable work in the beads issue tracker.

### Commands
- `bd ready` — Find unblocked tasks ready for work
- `bd list --status=in_progress` — Check for stalled in-progress tasks

### Actionable Conditions
- P0 or P1 tasks appear in `bd ready`
- Any task has been `in_progress` for more than 2 hours without activity
- New tasks created since last heartbeat cycle

### Report Format
```
BEADS_STATUS: {ready_count} ready, {in_progress_count} in progress
ACTIONABLE: [yes/no] — [reason if yes]
```

## Orchestrator Health Check

Monitor tmux sessions running orchestrators.

### Commands
- `tmux list-sessions 2>/dev/null | grep "^orch-"` — List orchestrator sessions
- Check message bus status if available

### Actionable Conditions
- An orchestrator session has crashed (tmux session gone but bead still in_progress)
- An orchestrator has been idle for more than 30 minutes
- Message bus shows undelivered messages

### Report Format
```
ORCHESTRATOR_HEALTH: {active_count} sessions, {healthy_count} healthy
ACTIONABLE: [yes/no] — [reason if yes]
```

## Git Status Check

Check for uncommitted work across worktrees.

### Commands
- `git worktree list` — List all worktrees
- `git status --porcelain` — Check each worktree for dirty state

### Actionable Conditions
- Uncommitted changes older than 1 hour
- Unmerged branches with completed work
- Stale worktrees (no commits in 24+ hours)

### Report Format
```
GIT_STATUS: {clean_count}/{total_count} worktrees clean
ACTIONABLE: [yes/no] — [reason if yes]
```

## Hindsight Goals Check

Check for active goals and unresolved questions.

### Commands
- Recall active goals and priorities from Hindsight
- Check for unresolved questions from recent sessions

### Actionable Conditions
- Active goals with no recent progress
- Unresolved questions pending for 24+ hours

### Report Format
```
HINDSIGHT_GOALS: {active_count} goals, {unresolved_count} unresolved
ACTIONABLE: [yes/no] — [reason if yes]
```

## Google Chat Messages (Epic 2)

Check for unread user messages (requires google-chat-bridge MCP).

### Commands
- Get new messages from Google Chat bridge (if available)
- Check for pending ASK_USER responses

### Actionable Conditions
- Unread messages from user
- Response to pending question received

### Report Format
```
GOOGLE_CHAT: {unread_count} unread messages
ACTIONABLE: [yes/no] — [reason if yes]
```

## Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| heartbeat_interval | 600 | Seconds between cycles |
| active_hours_start | 08:00 | Start of active monitoring (local time) |
| active_hours_end | 22:00 | End of active monitoring (local time) |
| stale_threshold_hours | 2 | Hours before in_progress task considered stalled |
| idle_threshold_minutes | 30 | Minutes before orchestrator considered idle |
| cost_alert_threshold | 20000 | Token threshold for cost alerts per cycle |
