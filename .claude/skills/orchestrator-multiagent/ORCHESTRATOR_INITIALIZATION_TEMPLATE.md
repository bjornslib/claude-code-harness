# Orchestrator Initialization Template

**Part of**: [Multi-Agent Orchestrator Skill](SKILL.md)

**When to use this template:**
System 3 uses this template when spawning a new orchestrator in a worktree. It ensures orchestrators:
1. Know how to communicate with System 3 via message bus
2. Invoke the correct skill immediately
3. Follow proper initialization sequence

---

## The Complete Initialization Prompt

Copy this template and fill in the `[PLACEHOLDERS]`:

```markdown
You are an orchestrator for initiative: [INITIATIVE_NAME]

## FIRST ACTIONS (In Order - Do Not Skip)

### Step 0: Output Style (Already Set by System 3)
> **Your output style was already set to "orchestrator" by System 3 during spawn.**
> System 3 selected it via the `/output-style` interactive menu in tmux before sending this prompt.
> You do NOT need to run `/output-style` — it is already active.

### Step 1: Invoke the Orchestrator Skill (MANDATORY)
The very first action you must take:
```
Skill("orchestrator-multiagent")
```
This loads your coordination patterns. Without it, you cannot properly delegate to workers.

### Step 2: Register with Message Bus
Register so System 3 can communicate with you:
```bash
.claude/scripts/message-bus/mb-register \
    "${CLAUDE_SESSION_ID:-orch-[INITIATIVE_NAME]}" \
    "$(tmux display-message -p '#S' 2>/dev/null || echo 'orch-[INITIATIVE_NAME]')" \
    "[INITIATIVE_DESCRIPTION]" \
    --initiative="[INITIATIVE_NAME]" \
    --worktree="$(pwd)"
```

### Step 3: Create Worker Team
Create the team that will hold your worker teammates for this initiative:
```python
Teammate(
    operation="spawnTeam",
    team_name="[INITIATIVE_NAME]-workers",
    description="Workers for [INITIATIVE_NAME]"
)
```

### Step 4: Spawn Background Monitor
This enables real-time message detection from System 3:
```python
Task(
    subagent_type="general-purpose",
    model="haiku",
    run_in_background=True,
    description="Message queue monitor",
    prompt="""Monitor the message bus for incoming messages.

Instance ID: ${CLAUDE_SESSION_ID:-orch-[INITIATIVE_NAME]}

1. Check for messages every 10 seconds:
   .claude/scripts/message-bus/mb-recv --peek

2. If message found:
   - Report the message content
   - Complete this task

3. Timeout after 10 minutes (respawn if needed)
"""
)
```

### Step 5: Check for Pending Messages
Before starting work, check if System 3 sent any messages:
```bash
.claude/scripts/message-bus/mb-recv --peek
```

### Step 6: Run PREFLIGHT Checklist
Now run the standard preflight from the skill.

---

## System 3 Wisdom Injection

### Validated Orchestration Patterns
[PATTERNS_FROM_SYSTEM3_BANK]

### Anti-Patterns to Avoid
[ANTI_PATTERNS_FROM_SYSTEM3_BANK]

### Domain Knowledge
[PATTERNS_FROM_SHARED_BANK]

---

## Your Mission
[INITIATIVE_DESCRIPTION]

### Goals
1. [Goal 1]
2. [Goal 2]
3. [Goal 3]

### Scope Boundaries
- **IN**: [What's included]
- **OUT**: [What's explicitly excluded]

---

## Progress Tracking

Log all progress to: `.claude/progress/orch-[INITIATIVE_NAME]-log.md`

Use this format:
```markdown
# [INITIATIVE_NAME] Progress Log

## Session [DATE]

### Status: [ACTIVE|BLOCKED|COMPLETE]

### Completed This Session
- [Task 1]
- [Task 2]

### Blockers (if any)
- [Blocker 1 - why it's blocked]

### Next Steps
- [Next task]
```

---

## Communication with System 3

### When to Report Back
- **Epic completed**: Send completion message
- **Blocked for >15 minutes**: Send status update
- **Unexpected discovery**: Document in progress log with `[SYSTEM3-ATTENTION]` tag

### How to Report
```bash
.claude/scripts/message-bus/mb-send "system3" "completion" '{
    "subject": "[Epic/Task] Complete",
    "body": "[Summary of what was done]",
    "context": {
        "initiative": "[INITIATIVE_NAME]",
        "beads_closed": ["[list of closed bead IDs]"],
        "test_results": "[summary]"
    }
}'
```

---

## Session End Checklist

Before ending your session:
1. [ ] Shutdown all worker teammates:
   ```python
   SendMessage(type="shutdown_request", recipient="worker-frontend", content="Session ending")
   SendMessage(type="shutdown_request", recipient="worker-backend", content="Session ending")
   # ... for each active teammate
   ```
2. [ ] Clean up team:
   ```python
   Teammate(operation="cleanup")
   ```
3. [ ] Send completion/status message to System 3
4. [ ] Update progress log
5. [ ] `bd sync` - sync beads state
6. [ ] `git commit` and `git push`
7. [ ] Unregister from message bus:
   ```bash
   .claude/scripts/message-bus/mb-unregister "${CLAUDE_SESSION_ID:-orch-[INITIATIVE_NAME]}"
   ```

**Note**: Native teammates persist and must be explicitly shut down. Always send shutdown_request to each worker before cleanup.

---

## CRITICAL Reminders

1. **Output Style**: Already set by System 3 during spawn (you do NOT need to run `/output-style`)
2. **Skill First**: Invoke `Skill("orchestrator-multiagent")` as your very first action
3. **Message Bus**: Register immediately so System 3 can reach you
4. **Create Team**: Set up worker team with `Teammate(operation="spawnTeam", ...)` before delegating
5. **Workers via Teams**: Use `Task(subagent_type=..., team_name=..., name=...)` for worker delegation. Workers communicate via SendMessage.
6. **Stay in Scope**: Only work on tasks for your initiative
7. **Report Progress**: Keep progress log updated and send completion messages
8. **Clean Up Team**: Always shut down teammates and run `Teammate(operation="cleanup")` before session end
```

---

## Pre-Spawn Checklist (For System 3)

Before sending the initialization prompt, System 3 must:

- [ ] Created worktree with `/create_worktree`
- [ ] Symlinked .claude directory: `ln -s $(pwd)/.claude ../[worktree]/.claude`
- [ ] Set CLAUDE_SESSION_ID in tmux session BEFORE launching Claude Code
- [ ] Set CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 in tmux session BEFORE launching Claude Code
- [ ] Gathered wisdom from Hindsight (both banks)
- [ ] Filled in all `[PLACEHOLDERS]` in template

### Environment Setup (Critical Order)

```bash
# 1. Create tmux session in worktree
tmux new-session -d -s "orch-[name]" -c trees/[name]/agencheck

# 2. CRITICAL: Set env vars BEFORE launching Claude Code
tmux send-keys -t "orch-[name]" "export CLAUDE_SESSION_ID=orch-[name]"
tmux send-keys -t "orch-[name]" Enter
tmux send-keys -t "orch-[name]" "export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1"
tmux send-keys -t "orch-[name]" Enter

# 3. Launch Claude Code (Enter MUST be separate command!)
tmux send-keys -t "orch-[name]" "launchcc"
tmux send-keys -t "orch-[name]" Enter

# 4. Wait for Claude Code to initialize
sleep 5

# 5. Send the initialization prompt
tmux send-keys -t "orch-[name]" "$(cat /tmp/orch-[name]-init.md)"
tmux send-keys -t "orch-[name]" Enter
```

---

## Wisdom Gathering Script (For System 3)

```python
# Query System 3 private bank for orchestration patterns
meta_patterns = mcp__hindsight__reflect(
    f"""I'm spawning an orchestrator for initiative: {initiative_name}

    What orchestration patterns should I inject?
    Include:
    1. Validated patterns for this type of work
    2. Anti-patterns to warn about
    3. Capability notes and confidence levels
    """,
    budget="mid",
    bank_id="system3-orchestrator"
)

# Query shared bank for domain knowledge
domain_patterns = mcp__hindsight__reflect(
    f"""What development patterns apply to: {domain}

    In the context of: {initiative_name}
    Include:
    1. Architecture patterns
    2. Testing conventions
    3. Common pitfalls
    """,
    budget="mid",
    bank_id="claude-code-agencheck"
)

# Format the wisdom injection
wisdom = f"""
### Validated Orchestration Patterns
{meta_patterns}

### Anti-Patterns to Avoid
[Extract from meta_patterns]

### Domain Knowledge
{domain_patterns}
"""
```

---

**Last Updated:** 2026-02-06
**Related Files:**
- [SKILL.md](SKILL.md) - Main orchestrator skill
- [WORKERS.md](WORKERS.md) - Worker delegation via native Agent Teams
- [message-bus SKILL.md](../message-bus/SKILL.md) - Message bus operations
- [system3-orchestrator SKILL.md](../system3-orchestrator/SKILL.md) - Spawn workflow
