# Spawn Workflow Reference

Complete guide for spawning orchestrator sessions.

---

## Prerequisites

Before spawning:

1. **tmux installed**: `which tmux`
2. **Worktree exists**: `ls trees/[name]/agencheck`
3. **Hindsight accessible**: MCP connection active
4. **No conflicting session**: `tmux has-session -t orch-[name]` returns error

---

## Full Spawn Sequence

### 1. Create Worktree (if needed)

```bash
/create_worktree [initiative-name]
```

This creates:
- `trees/[name]/` - worktree directory
- Fresh branch for isolated work
- Copy of codebase at current HEAD

**⚠️ CRITICAL: Symlinks for Shared Resources**

Git worktrees don't inherit certain directories. Without them, essential features won't work. The spawn script auto-creates these symlinks, but for manual spawns:

```bash
# .claude - skills, hooks, output-styles (in agencheck dir)
ln -s $(pwd)/.claude trees/[name]/agencheck/.claude

# .beads - issue tracking database (in zenagent dir)
ln -s $(dirname $(pwd))/.beads trees/[name]/.beads
```

| Directory | Purpose | Location |
|-----------|---------|----------|
| `.claude` | Skills, hooks, output-styles | `trees/[name]/agencheck/.claude` |
| `.beads` | Issue tracking (bd commands) | `trees/[name]/.beads` |

### 2. Gather Wisdom from Hindsight

Query relevant patterns before launching:

```python
# Meta-orchestration wisdom (System 3 private bank)
meta_wisdom = mcp__hindsight__reflect(
    f"""
    What orchestration patterns are relevant for: {initiative}
    Consider:
    - Similar past initiatives and their outcomes
    - Anti-patterns to avoid
    - Capability considerations
    """,
    budget="mid",
    bank_id="system3-orchestrator"
)

# Domain-specific wisdom (shared bank)
domain_wisdom = mcp__hindsight__reflect(
    f"""
    What development patterns apply to: {domain}
    Consider:
    - Architecture patterns in this codebase
    - Common pitfalls and solutions
    - Testing requirements
    """,
    budget="mid",
    bank_id="claude-code-agencheck"
)
```

### 3. Compose Wisdom Injection

Create a wisdom file combining patterns:

```bash
cat > /tmp/wisdom-${INITIATIVE}.md << 'EOF'
## System 3 Wisdom Injection

### Orchestration Patterns (Validated)
[Include relevant patterns from meta_wisdom]

### Anti-Patterns (Avoid)
[Include warnings from past failures]

### Domain Knowledge
[Include relevant patterns from domain_wisdom]

### Capability Notes
[Any relevant capability observations]
EOF
```

### 4. Launch Session

```bash
# Using the spawn script
./scripts/spawn-orchestrator.sh [name] /tmp/wisdom-${INITIATIVE}.md

# OR manual tmux commands
tmux new-session -d -s "orch-[name]"
tmux send-keys -t "orch-[name]" "cd trees/[name]/agencheck" Enter

# 4b. Set task list ID (enables shared task tracking)
tmux send-keys -t "orch-[name]" "export CLAUDE_CODE_TASK_LIST_ID=PRD-[prd-name]" Enter

tmux send-keys -t "orch-[name]" "launchcc" Enter
sleep 5
tmux send-keys -t "orch-[name]" "$(cat /tmp/wisdom-${INITIATIVE}.md)" Enter
```

**🚨 CRITICAL**: The wisdom file (`/tmp/wisdom-${INITIATIVE}.md`) MUST include instruction for the orchestrator's FIRST actions (exact order). Example:

```markdown
## FIRST ACTIONS REQUIRED (EXACT ORDER)
1. IMMEDIATE: `/output-style orchestrator`
   This loads orchestrator behavior patterns and delegation rules.

2. THEN: Skill("orchestrator-multiagent")
   This loads worker coordination patterns essential for proper delegation.

Do NOT skip or reorder these steps - orchestrators without proper output style may violate protocol.
```

### 5. Update Registry

The spawn script handles this automatically, but for manual spawns:

```bash
REGISTRY=".claude/state/active-orchestrators.json"

jq --arg name "orch-$INITIATIVE" \
   --arg init "$INITIATIVE" \
   --arg wt "trees/$INITIATIVE/agencheck" \
   --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
   '.orchestrators += [{name: $name, initiative: $init, worktree: $wt, status: "active", started_at: $ts}]' \
   "$REGISTRY" > "${REGISTRY}.tmp" && mv "${REGISTRY}.tmp" "$REGISTRY"
```

### 6. Launch Validation Monitor

After orchestrator is running, System3 launches a validation monitor:

```python
Task(
    subagent_type="validation-agent",
    model="sonnet",  # ⚠️ MUST be Sonnet - Haiku lacks exit discipline
    run_in_background=True,
    description=f"Validation monitor for orch-{INITIATIVE}",
    prompt=f"--mode=monitor --session-id=orch-{INITIATIVE} --task-list-id=PRD-{PRD_NAME} --max-iterations=30"
)
```

**⚠️ Model Selection**: Use **Sonnet 4.5**, not Haiku. Testing showed Haiku gets distracted after validation and fails to return promptly. Sonnet has the discipline to detect → validate → RETURN.

The monitor will COMPLETE after validation (or ~5 minutes max) and wake System3 with status.
System3 must re-launch the monitor to continue watching.

---

## Verification Steps

After spawning, verify:

```bash
# Session exists
tmux has-session -t orch-[name] && echo "OK" || echo "FAILED"

# Claude Code responsive
tmux capture-pane -t orch-[name] -p | grep -q "Claude" && echo "OK" || echo "WAITING"

# Wisdom acknowledged (check for keyword from injection)
tmux capture-pane -t orch-[name] -p | grep -qi "pattern" && echo "OK" || echo "NOT YET"
```

---

## Troubleshooting Spawn

| Issue | Cause | Solution |
|-------|-------|----------|
| Session already exists | Name collision | Use unique initiative name or terminate existing |
| Worktree not found | Not created | Run `/create_worktree [name]` first |
| Claude Code not launching | `launchcc` not available | Check alias or use full path |
| Wisdom not sent | Session not ready | Increase sleep time before sending |

---

## Example: Complete Spawn

```bash
# Variables
INITIATIVE="auth-epic-2"
DOMAIN="authentication"

# Step 1: Create worktree
/create_worktree $INITIATIVE

# Step 2: Query Hindsight (in Python/Claude context)
meta_wisdom=$(mcp__hindsight__reflect "orchestration patterns for auth systems", budget="mid")
domain_wisdom=$(mcp__hindsight__reflect "authentication patterns in this codebase", budget="mid")

# Step 3: Create wisdom file
cat > /tmp/wisdom-${INITIATIVE}.md << EOF
You are orchestrator for: $INITIATIVE

## Wisdom Injection
$meta_wisdom

## Domain Patterns
$domain_wisdom

## Starting Point (EXACT ORDER - DO NOT SKIP)
1. FIRST: /output-style orchestrator (loads orchestrator behavior patterns)
2. THEN: Skill("orchestrator-multiagent") (loads coordination patterns)
3. Run PREFLIGHT checklist
4. Find first task: bd ready
5. Log progress to .claude/progress/orch-${INITIATIVE}-log.md
EOF

# Step 4: Launch
./scripts/spawn-orchestrator.sh $INITIATIVE /tmp/wisdom-${INITIATIVE}.md

# Step 5: Verify
sleep 10
tmux capture-pane -t orch-$INITIATIVE -p | tail -5

# Step 6: (OPTIONAL for >1 hour initiatives) Spawn blocking monitor
# This keeps System 3 session alive and enables real-time intervention
# See system3-meta-orchestrator output style for full monitor prompt template
```

---

## Long-Running Initiatives: Blocking Monitor (MANDATORY for >1 hour)

For initiatives expected to take >1 hour, System 3 MUST spawn a **blocking** Haiku monitor after the orchestrator is launched:

```python
Task(
    subagent_type="general-purpose",
    model="haiku",
    run_in_background=False,  # BLOCKING - keeps session alive
    description=f"Blocking monitor for orch-{INITIATIVE}",
    prompt=f"""Monitor orchestrator: orch-{INITIATIVE}

Report back when ANY of these occur:
1. COMPLETION: Orchestrator signals work is done
2. BLOCKED >15 min: Orchestrator stuck on same issue
3. LOOP DETECTED: Same actions repeated 3+ times without progress
4. GUIDANCE NEEDED: Orchestrator explicitly requests user input
5. SCOPE CREEP: Files modified outside declared scope
6. ERROR SPIRAL: Same error repeated 3+ times

Monitoring commands:
- tmux capture-pane -t orch-{INITIATIVE} -p | tail -80
- bd list --status=in_progress

Check every 2-3 minutes. Report using format:
STATUS: [COMPLETE|BLOCKED|LOOP|NEEDS_GUIDANCE|SCOPE_CREEP|ERROR]
ORCHESTRATOR: orch-{INITIATIVE}
SUMMARY: [What happened]
RECOMMENDED_ACTION: [What System 3 should do]
"""
)
```

**Why blocking?**
- Keeps System 3 session naturally alive (stop hook won't trigger)
- Immediate intervention when orchestrator needs guidance
- Session lifecycle matches initiative lifecycle
- No risk of missing critical blockers
