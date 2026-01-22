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
tmux send-keys -t "orch-[name]" "launchcc" Enter
sleep 5
tmux send-keys -t "orch-[name]" "$(cat /tmp/wisdom-${INITIATIVE}.md)" Enter
```

**🚨 CRITICAL**: The wisdom file (`/tmp/wisdom-${INITIATIVE}.md`) MUST include instruction to invoke `Skill("orchestrator-multiagent")` as the orchestrator's FIRST action. Example:

```markdown
## FIRST ACTION REQUIRED
Before doing ANYTHING else, invoke: Skill("orchestrator-multiagent")
This loads worker coordination patterns essential for proper delegation.
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

## Starting Point
1. Invoke: Skill("orchestrator-multiagent")
2. Run PREFLIGHT checklist
3. Find first task: bd ready
4. Log progress to .claude/progress/orch-${INITIATIVE}-log.md
EOF

# Step 4: Launch
./scripts/spawn-orchestrator.sh $INITIATIVE /tmp/wisdom-${INITIATIVE}.md

# Step 5: Verify
sleep 10
tmux capture-pane -t orch-$INITIATIVE -p | tail -5
```
