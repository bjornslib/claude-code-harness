---
title: "Troubleshooting"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# Troubleshooting Reference

Common issues and solutions for orchestrator management.

---

## Session Issues

### Session Won't Start

**Symptom**: `tmux new-session` fails or hangs

**Causes & Solutions**:

| Cause | Solution |
|-------|----------|
| tmux not installed | `apt install tmux` or `brew install tmux` |
| Session name collision | Use unique name: `tmux new-session -d -s "orch-$(date +%s)"` |
| tmux server crashed | `tmux kill-server && tmux` |
| Terminal too small | Increase terminal size |

### Can't Attach to Session

**Symptom**: `tmux attach -t orch-[name]` fails

**Diagnosis**:
```bash
# List all sessions
tmux list-sessions

# Check if session exists
tmux has-session -t "orch-[name]" && echo "EXISTS" || echo "NOT FOUND"
```

**Solutions**:
- Session doesn't exist: Check spelling, list sessions
- Permission denied: Check tmux socket permissions
- Already attached: Use `tmux attach -t orch-[name] -d` to detach others

### Session Hangs/Unresponsive

**Symptom**: Commands sent but no response

**Diagnosis**:
```bash
# Capture output
tmux capture-pane -t "orch-[name]" -p | tail -10

# Check if Claude is running
tmux capture-pane -t "orch-[name]" -p | grep -i "claude\|thinking\|processing"
```

**Solutions**:
```bash
# Send interrupt
tmux send-keys -t "orch-[name]" C-c
sleep 2

# Try to recover
tmux send-keys -t "orch-[name]" "Continue from where you left off" Enter

# If still stuck, force restart
tmux kill-session -t "orch-[name]"
# Then respawn
```

---

## Claude Code Issues

### Claude Code Not Launching

**Symptom**: `launchcc` command not found or fails

**Diagnosis**:
```bash
# Check if alias exists
which launchcc
type launchcc

# Check in worktree
cd trees/[name]/agencheck
which launchcc
```

**Solutions**:
- Alias not set: Add to `.bashrc` or use full path
- Wrong directory: Ensure you're in the worktree
- API key missing: Check `ANTHROPIC_API_KEY` environment variable

### Claude Code Exits Unexpectedly

**Symptom**: Claude session ends without completing

**Diagnosis**:
```bash
# Check exit code
tmux capture-pane -t "orch-[name]" -p -S -100 | grep -i "exit\|error\|crash"
```

**Common Causes**:
- Rate limiting: Wait and retry
- Network issues: Check connectivity
- Token limit: Long sessions may need restart
- Memory: Check system resources

### Wisdom Injection Not Working

**Symptom**: Orchestrator doesn't acknowledge wisdom

**Diagnosis**:
```bash
# Check if message was sent
tmux capture-pane -t "orch-[name]" -p | grep -i "wisdom\|pattern\|injection"
```

**Solutions**:
- Wait longer before sending: Increase sleep time
- Message too long: Break into smaller chunks
- Special characters: Escape or use heredoc

---

## Worktree Issues

### Worktree Doesn't Exist

**Symptom**: Spawn fails with "worktree not found"

**Solution**:
```bash
# Create worktree first
/create_worktree [initiative-name]

# Verify
ls trees/[name]/agencheck
```

### Git Conflicts in Worktree

**Symptom**: Git operations fail

**Diagnosis**:
```bash
cd trees/[name]/agencheck
git status
git log --oneline -5
```

**Solutions**:
```bash
# Pull latest changes
git pull origin main --rebase

# If conflicts, resolve them
git add .
git rebase --continue

# Or abort and start fresh
git rebase --abort
git reset --hard origin/main
```

### Worktree Locked

**Symptom**: "index.lock exists" or similar

**Solution**:
```bash
cd trees/[name]/agencheck
rm -f .git/index.lock
rm -f .git/HEAD.lock
```

---

## Hindsight Issues

### MCP Connection Failed

**Symptom**: `mcp__hindsight__*` calls fail

**Diagnosis**:
```bash
# Check if Hindsight server is running
curl http://localhost:8888/health

# Check MCP configuration
cat .claude/settings/mcp.json
```

**Solutions**:
- Start Hindsight server
- Check port configuration
- Verify bank_id is correct

### Wrong Bank ID

**Symptom**: Queries return unexpected or no results

**Verification**:
```python
# System 3 bank
mcp__hindsight__reflect("test query", bank_id="system3-orchestrator")

# Shared bank
mcp__hindsight__reflect("test query", bank_id="claude-code-agencheck")
```

**Solution**: Check bank_id spelling and existence

### Slow Reflections

**Symptom**: `reflect()` takes too long

**Solutions**:
- Reduce budget: Use "low" or "mid" instead of "high"
- Simplify query: Shorter, more focused questions
- Check Hindsight logs for performance issues

---

## Monitoring Issues

### Status Script Shows Stale Data

**Symptom**: Reported times are incorrect

**Causes**:
- Progress log not being updated
- File timestamp issues
- Orchestrator stuck

**Solution**: Check orchestrator is actually running and logging

### Can't See Output

**Symptom**: `capture-pane` returns empty or minimal content

**Solutions**:
```bash
# Increase capture range
tmux capture-pane -t "orch-[name]" -p -S -1000

# Full history
tmux capture-pane -t "orch-[name]" -p -S -

# Check scrollback settings
tmux show-options -g history-limit
```

---

## Registry Issues

### Registry Corrupted

**Symptom**: jq commands fail, invalid JSON

**Diagnosis**:
```bash
jq '.' .claude/state/active-orchestrators.json
```

**Solution**:
```bash
# Backup and recreate
mv .claude/state/active-orchestrators.json .claude/state/active-orchestrators.json.bak

# Create fresh registry
echo '{"orchestrators": []}' > .claude/state/active-orchestrators.json

# Rebuild from running sessions
for session in $(tmux list-sessions -F "#{session_name}" | grep "^orch-"); do
    # Add to registry...
done
```

### Registry Out of Sync

**Symptom**: Registry shows sessions that don't exist (or vice versa)

**Solution**: Sync registry with actual tmux sessions
```bash
# Get actual sessions
ACTUAL=$(tmux list-sessions -F "#{session_name}" | grep "^orch-" | sort)

# Get registry sessions
REGISTRY=$(jq -r '.orchestrators[].name' .claude/state/active-orchestrators.json | sort)

# Compare
diff <(echo "$ACTUAL") <(echo "$REGISTRY")
```

---

## Emergency Recovery

### Kill All Orchestrators

```bash
# Nuclear option - kill all orchestrator sessions
tmux list-sessions -F "#{session_name}" | grep "^orch-" | xargs -I {} tmux kill-session -t {}

# Clear registry
echo '{"orchestrators": []}' > .claude/state/active-orchestrators.json
```

### Reset Everything

```bash
#!/bin/bash
# WARNING: This kills all orchestrators and removes worktrees

echo "This will kill all orchestrators and remove worktrees. Continue? (y/N)"
read confirm
if [ "$confirm" != "y" ]; then exit 1; fi

# Kill all orchestrator sessions
tmux list-sessions -F "#{session_name}" | grep "^orch-" | xargs -I {} tmux kill-session -t {} 2>/dev/null

# Clear registry
echo '{"orchestrators": []}' > .claude/state/active-orchestrators.json

# Remove worktrees (be careful!)
for worktree in trees/*/agencheck; do
    name=$(basename $(dirname $worktree))
    echo "Removing worktree: $name"
    /remove_worktree $name
done

echo "Reset complete."
```

---

## Getting Help

### Collect Debug Info

When reporting issues, gather:

```bash
# System info
uname -a
tmux -V
which launchcc

# Session info
tmux list-sessions
cat .claude/state/active-orchestrators.json

# Recent logs
ls -la trees/*/agencheck/.claude/progress/

# Hindsight status
curl http://localhost:8888/health
```

### Log Locations

| Log | Location |
|-----|----------|
| Orchestrator progress | `trees/[name]/.claude/progress/orch-[name]-log.md` |
| Session output | `tmux capture-pane -t orch-[name] -p` |
| Registry | `.claude/state/active-orchestrators.json` |
| Hindsight | (depends on Hindsight config) |
