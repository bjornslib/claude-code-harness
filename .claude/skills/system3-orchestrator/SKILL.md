---
name: system3-orchestrator
description: This skill should be used when spawning orchestrators, launching new initiatives, starting parallel work, creating orchestrators in worktrees, or managing System 3 orchestration. Provides complete preflight checklists and spawn workflows for nested orchestrator management with Hindsight wisdom injection.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Task, SlashCommand
version: 3.2.0
---

# System 3 Orchestrator Skill

Spawn orchestrator Claude Code sessions in isolated worktrees. Named after Russian nesting dolls: System 3 contains orchestrators, which contain workers.

```
System 3 (Uber-Orchestrator)
    ├── Orchestrator A (worktree: trees/auth)
    ├── Orchestrator B (worktree: trees/dashboard)
    └── Orchestrator C (worktree: trees/api-v2)
```

---

## 🚨 WHEN YOU MUST USE THIS SKILL

**Invoke this skill for ANY implementation work. No exceptions.**

### Triggers That REQUIRE This Skill

| User Request | Action |
|--------------|--------|
| "Fix the bug in..." | → Invoke this skill, spawn orchestrator |
| "Add a feature to..." | → Invoke this skill, spawn orchestrator |
| "Refactor the..." | → Invoke this skill, spawn orchestrator |
| "Update the code to..." | → Invoke this skill, spawn orchestrator |
| "Fix deprecation warnings" | → Invoke this skill, spawn orchestrator |
| "Implement..." | → Invoke this skill, spawn orchestrator |
| ANY task requiring Edit/Write | → Invoke this skill, spawn orchestrator |

### The Test

**Ask yourself: "Will this result in code being edited or written?"**

- **YES** → You MUST invoke this skill and spawn an orchestrator
- **NO** → You may proceed directly (research, planning, memory operations)

### Common Rationalizations to REJECT

| Rationalization | Why It's Wrong |
|-----------------|----------------|
| "It's just a small fix" | Size is irrelevant - pattern matters |
| "It's straightforward" | Complexity is irrelevant - pattern matters |
| "Only 2-3 files" | File count is irrelevant - pattern matters |
| "I'll delegate to backend-solutions-engineer" | WRONG - delegate to ORCHESTRATOR who delegates |
| "Let me research first" | Research is fine, but the moment you'd Edit/Write → orchestrator |

### What System 3 Does vs What Orchestrators Do

| System 3 (You) | Orchestrators |
|----------------|---------------|
| Spawn orchestrators | Spawn workers |
| Monitor progress | Coordinate implementation |
| Inject wisdom | Execute Edit/Write |
| Guide strategy | Run tests |
| Validate outcomes | Handle beads |

---

## PREFLIGHT CHECKLIST (Do This First)

Before spawning ANY orchestrator, complete this checklist:

### [ ] 1. Extract Goals from PRD

```python
# Read the PRD
prd_content = Read(f".taskmaster/docs/{initiative}-prd.md")

# Retain goals to Hindsight
mcp__hindsight__retain(
    content=f"""
    ## Active Initiative: {initiative}
    ### Goals: [extract from PRD]
    ### Acceptance Criteria: [extract from PRD]
    ### Scope Boundaries: [IN/OUT from PRD]
    """,
    context="system3-prd-tracking"
)
```

**Detailed workflow**: See [references/prd-extraction.md](references/prd-extraction.md)

### [ ] 2. Initialize Completion Promise

**Note**: `CLAUDE_SESSION_ID` is auto-set by `ccsystem3`. No manual initialization needed.

```bash
# Create promise from PRD or goal (session ID already set!)
cs-promise --create "Complete [initiative] with [acceptance criteria]"

# Start the promise
cs-promise --start <promise-id>
```

**For tmux-spawned orchestrators**: You must set `CLAUDE_SESSION_ID` manually before launching (see spawn sequence below).

**Detailed workflow**: See [references/completion-promise.md](references/completion-promise.md)

### [ ] 3. Gather Wisdom from Hindsight

```python
# Meta-orchestration patterns (private bank)
meta_patterns = mcp__hindsight__reflect(
    f"What orchestration patterns apply to {initiative}?",
    budget="mid",
    bank_id="system3-orchestrator"
)

# Domain-specific patterns (shared bank)
domain_patterns = mcp__hindsight__reflect(
    f"What development patterns apply to {domain}?",
    budget="mid",
    bank_id="claude-code-agencheck"
)
```

### [ ] 4. Check Business Outcome Linkage

```bash
# What Business Epic does this serve?
bd list --tag=bo --status=open

# What Key Results will this advance?
bd show <bo-id>
```

**Detailed workflow**: See [references/okr-tracking.md](references/okr-tracking.md)

### [ ] 5. Create Oversight Team

```python
TeamCreate(team_name=f"s3-{initiative}-oversight", description=f"S3 independent validation for {initiative}")
```

Spawn specialist workers into the team. See [references/oversight-team.md](references/oversight-team.md) for exact spawn commands and prompts.

### [ ] 6. Define Validation Expectations

Determine which validation levels apply:
- [ ] Unit tests required?
- [ ] API tests required?
- [ ] E2E browser tests required?

**Detailed workflow**: See [references/validation-workflow.md](references/validation-workflow.md)

---

## SPAWN WORKFLOW

### Option A: Use Spawn Script (Recommended)

```bash
# 1. Create worktree (if needed)
/create_worktree [initiative-name]

# 2. Create wisdom injection file
cat > /tmp/wisdom-${INITIATIVE}.md << 'EOF'
[Include FIRST ACTIONS template + gathered wisdom]
EOF

# 3. Launch
./scripts/spawn-orchestrator.sh [initiative-name] /tmp/wisdom-${INITIATIVE}.md
```

The script automatically:
- Creates `.claude` and `.beads` symlinks
- Sets `CLAUDE_SESSION_DIR`, `CLAUDE_SESSION_ID`, and `CLAUDE_CODE_TASK_LIST_ID`
- Launches Claude Code with proper tmux patterns
- Updates orchestrator registry

### Option B: Manual tmux Commands

```bash
# 1. Symlink shared resources
ln -s $(pwd)/.claude trees/[name]/agencheck/.claude
ln -s $(dirname $(pwd))/.beads trees/[name]/.beads

# 2. Create tmux session
tmux new-session -d -s "orch-[name]"

# 3. Navigate to worktree
tmux send-keys -t "orch-[name]" "cd trees/[name]/agencheck"
tmux send-keys -t "orch-[name]" Enter

# 4. CRITICAL: Set env vars BEFORE launching Claude
tmux send-keys -t "orch-[name]" "export CLAUDE_SESSION_DIR=[initiative]-$(date +%Y%m%d)"
tmux send-keys -t "orch-[name]" Enter
tmux send-keys -t "orch-[name]" "export CLAUDE_SESSION_ID=orch-[name]"
tmux send-keys -t "orch-[name]" Enter
tmux send-keys -t "orch-[name]" "export CLAUDE_CODE_TASK_LIST_ID=PRD-[prd-name]"
tmux send-keys -t "orch-[name]" Enter
tmux send-keys -t "orch-[name]" "export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1"
tmux send-keys -t "orch-[name]" Enter

# 5. Launch Claude Code with ccorch (Enter MUST be separate!)
tmux send-keys -t "orch-[name]" "ccorch"
tmux send-keys -t "orch-[name]" Enter

# 6. Wait for initialization
sleep 5

# 7. CRITICAL: Select orchestrator output style via direct command
#    This MUST happen BEFORE the wisdom injection prompt.
#    The orchestrator starts in "default" output style - it won't reliably
#    follow output-style instructions embedded in text. System 3 must
#    physically select it via the /output-style slash command.
#
#    IMPORTANT: Text and Enter MUST be separate send-keys calls (Pattern 1).
#    Do NOT include a linebreak in the text — send the command text first,
#    then Enter separately.
tmux send-keys -t "orch-[name]" "/output-style orchestrator"
tmux send-keys -t "orch-[name]" Enter
sleep 3  # Wait for output style to load

# 8. Send initialization prompt (orchestrator output style is now active)
tmux send-keys -t "orch-[name]" "$(cat /tmp/wisdom-${INITIATIVE}.md)"
sleep 2  # CRITICAL: Large pastes need time for bracketed paste processing
tmux send-keys -t "orch-[name]" Enter
```

**tmux command reference**: See [references/tmux-commands.md](references/tmux-commands.md)

---

## INITIALIZATION TEMPLATE

Include this in your wisdom injection file:

```markdown
You are an orchestrator for initiative: [INITIATIVE_NAME]

## FIRST ACTIONS (Do Not Skip)

> **Note**: Your output style was already set to "orchestrator" by System 3 during spawn.
> You do NOT need to run `/output-style` — it is already active.

### 1. Invoke Skill (MANDATORY)
Before ANYTHING else: `Skill("orchestrator-multiagent")`

### 2. Register with Message Bus
```bash
.claude/scripts/message-bus/mb-register \
    "${CLAUDE_SESSION_ID}" \
    "orch-[name]" \
    "[description]" \
    --initiative="[name]"
```

### 3. Spawn Background Monitor
```python
Task(
    subagent_type="general-purpose",
    model="haiku",
    run_in_background=True,
    description="Message queue monitor",
    prompt="[Monitor template from message-bus skill]"
)
```

### 4. Create Worker Team (NEW)
```python
Teammate(
    operation="spawnTeam",
    team_name="{initiative}-workers",
    description="Workers for {initiative}"
)
```

### 5. Check for Messages
```bash
.claude/scripts/message-bus/mb-recv --peek
```

## System 3 Wisdom Injection
[Include patterns from Hindsight here]

## Your Mission
[Initiative description and goals]

## Acceptance Criteria
[From PRD or completion promise]

## Validation Requirements
[Which of 3 levels: Unit, API, E2E]

## Starting Point
1. Follow PREFLIGHT checklist from orchestrator-multiagent skill
2. Use `bd ready` to find first task
3. Report progress to `.claude/progress/orch-[name]-log.md`
4. Send completion messages to System 3 via `mb-send`
```

---

## VALIDATION MONITOR INTEGRATION (NEW)

When spawning an orchestrator, launch a validation-test-agent monitor to enable wake-up notifications.

### Set Task List ID in Spawn Sequence

Add to tmux spawn commands (BEFORE launching Claude Code):

```bash
tmux send-keys -t "orch-[name]" "export CLAUDE_CODE_TASK_LIST_ID=PRD-[prd-name]"
tmux send-keys -t "orch-[name]" Enter
```

### Launch Monitor (Cyclic Pattern)

After orchestrator is running, launch a validation monitor:

```python
def launch_monitor(name, prd_name):
    """Launch validation monitor - must be re-called after each wake-up."""
    return Task(
        subagent_type="validation-test-agent",
        model="haiku",
        run_in_background=True,
        description=f"Monitor orch-{name}",
        prompt=f"--mode=monitor --session-id=orch-{name} --task-list-id=PRD-{prd_name} --max-iterations=30"
    )

# Initial launch after spawning orchestrator
launch_monitor(name, prd_name)
```

### Handle Wake-Up Notifications

When monitor COMPLETES, System3 receives `<task-notification>`:

```python
if "MONITOR_STUCK" in result:
    # Send guidance to orchestrator
    Bash(f"mb-send orch-{name} guidance '...'")
    # RE-LAUNCH monitor to continue watching
    launch_monitor(name, prd_name)

elif "MONITOR_COMPLETE" in result:
    # All tasks done - trigger final validation
    Task(subagent_type="validation-test-agent",
         prompt=f"--mode=e2e --prd=PRD-{prd_name} ...")

elif "MONITOR_HEALTHY" in result:
    # Heartbeat - orchestrator working fine
    # RE-LAUNCH monitor to continue cycle
    launch_monitor(name, prd_name)
```

**Key Insight**: Monitors COMPLETE to wake System3. The cyclic pattern (launch → check → complete → re-launch) provides continuous monitoring.

### Also Start Oversight Team

After orchestrator is running:
1. Create oversight team: `TeamCreate(team_name=f"s3-{initiative}-oversight")`
2. Spawn 4 oversight workers (see [references/oversight-team.md](references/oversight-team.md))
3. Oversight team runs independently -- validates `impl_complete` tasks

---

## MONITORING CHECKLIST

**🚨 CRITICAL**: Always monitor orchestrators using background Haiku agents. Never block the main thread waiting for orchestrator status.

### Mandatory Background Monitoring Pattern

Spawn a Haiku 4.5 background agent to monitor. It reports back ONLY when intervention is needed:

```python
Task(
    subagent_type="general-purpose",
    model="haiku",  # Uses Haiku 4.5 - fast and cheap
    run_in_background=True,  # MANDATORY - never monitor in main thread
    description=f"Monitor orch-{name}",
    prompt=f"""
Monitor tmux session 'orch-{name}' and report back ONLY if:
1. Orchestrator is BLOCKED and needs intervention
2. Orchestrator has COMPLETED all work
3. There is an ERROR requiring attention

Check command:
```bash
tmux capture-pane -t orch-{name} -p | tail -50
```

If orchestrator is actively working (not blocked): Confirm running, do NOT report full output.
If session doesn't exist: Report that.

Be concise - only return actionable information.
"""
)
```

**Why background agents?** System 3 can continue other work while orchestrators run. Only interrupt when intervention is actually needed.

### Quick Manual Status Check (for debugging)

```bash
# List all orchestrator sessions
tmux list-sessions | grep "^orch-"

# View recent output (manual check only)
tmux capture-pane -t "orch-[name]" -p | tail -20
```

### Intervention via Message Bus

```bash
# Send guidance (preferred)
.claude/scripts/message-bus/mb-send "orch-[name]" guidance '{
    "subject": "Priority Change",
    "body": "Focus on API endpoints first"
}'

# Urgent message
.claude/scripts/message-bus/mb-send "orch-[name]" urgent '{
    "subject": "Stop Work",
    "body": "Regression detected"
}' --urgent

# Broadcast to all
.claude/scripts/message-bus/mb-send --broadcast announcement '{
    "subject": "Policy Update",
    "body": "All commits require passing tests"
}'
```

### Direct tmux Intervention (Fallback)

```bash
# Inject message
tmux send-keys -t "orch-[name]" "[guidance]"
tmux send-keys -t "orch-[name]" Enter

# Interrupt and rescue
tmux send-keys -t "orch-[name]" C-c
tmux send-keys -t "orch-[name]" "[rescue instructions]"
tmux send-keys -t "orch-[name]" Enter
```

### First-to-Finish Blocking Monitor (Multi-Orchestrator)

When running multiple orchestrators in parallel and you want to wait for ANY one to complete, use the **shared TaskList** for coordination.

#### Step 1: Create Tracking Tasks (Before Spawning Monitors)

```python
# Create tracking tasks for each orchestrator
TaskCreate(
    subject="Monitor orch-live-form-ui",
    description="Tracking task for validation-test-agent monitoring orch-live-form-ui",
    activeForm="Monitoring orch-live-form-ui"
)
# Returns task ID, e.g., #16

TaskCreate(
    subject="Monitor orch-employer-data-model",
    description="Tracking task for validation-test-agent monitoring orch-employer-data-model",
    activeForm="Monitoring orch-employer-data-model"
)
# Returns task ID, e.g., #17
```

#### Step 2: Instruct Validation-Agents to Update Tasks

Include in monitor prompt:

```python
Task(
    subagent_type="validation-test-agent",
    model="sonnet",
    run_in_background=True,
    description="Monitor orch-live-form-ui",
    prompt=f"""
    --mode=monitor --session-id=orch-live-form-ui --task-list-id=PRD-LIVE-FORM-UI

    CRITICAL: When you complete (for ANY reason), update the tracking task:
    TaskUpdate(taskId="{monitor_task_id}", status="completed")

    This allows System 3 to detect your completion via TaskList.
    """
)
```

#### Step 3: Blocking Watcher Polls TaskList

```python
Task(
    subagent_type="general-purpose",
    model="haiku",  # Haiku is fine for simple polling
    run_in_background=False,  # BLOCKING - System 3 waits here
    description="Wait for first monitor to complete",
    prompt="""
## Mission
Poll TaskList until ANY validation-test-agent monitor task completes.

## Tracking Tasks
| Task ID | Orchestrator |
|---------|--------------|
| #16 | orch-live-form-ui |
| #17 | orch-employer-data-model |

## Polling Loop (every 10 seconds)

1. Call TaskList to get all tasks
2. Check tasks #16 and #17 for status="completed"
3. If ANY is completed → return immediately with details
4. If none completed → sleep 10 seconds, repeat

## Return Format
```
FIRST_COMPLETE: #16
Orchestrator: orch-live-form-ui
Remaining: #17 (orch-employer-data-model) still in_progress
```

## Timeout
Max iterations: 720 (2 hours at 10s intervals). On timeout:
```
MONITOR_TIMEOUT: No monitors completed in 2 hours
```
"""
)
```

#### Why This Pattern Works

1. **Shared TaskList** - All subagents share `CLAUDE_CODE_TASK_LIST_ID`
2. **Real-time updates** - TaskUpdate propagates immediately
3. **Simple polling** - Haiku can do this (just TaskList + sleep)
4. **No external dependencies** - No tmux/beads polling needed
5. **Built-in coordination** - Uses Claude Code's native task system

**When to use blocking vs background:**
| Scenario | Pattern |
|----------|---------|
| System 3 has other work to do | Background monitors only |
| System 3 should wait for results | Blocking watcher + background monitors |
| Need to validate work incrementally | Background with cyclic re-launch |
| Racing multiple approaches | Blocking watcher + background monitors |

---

## POST-COMPLETION CHECKLIST

When an orchestrator completes:

### [ ] 0. 🚨 MANDATORY: Independent Validation via Oversight Agent Team

**This step is NON-NEGOTIABLE. Do NOT skip to step 1.**

Reading tmux output or orchestrator self-reports is NOT validation. System 3 must verify independently using an Agent Team (NOT standalone subagents).

```python
# Step 0a: Check for impl_complete tasks
# bd list --status=impl_complete

# Step 0b: Create oversight team (Agent Team, NOT standalone subagents)
TeamCreate(team_name=f"s3-{initiative}-oversight", description=f"S3 final validation for {initiative}")

# Step 0c: Spawn workers INTO the team
Task(
    subagent_type="tdd-test-engineer",
    team_name=f"s3-{initiative}-oversight",
    name="s3-test-runner",
    model="sonnet",
    prompt=f"""You are s3-test-runner in the System 3 oversight team.
    Run tests INDEPENDENTLY against real services. Do NOT trust orchestrator reports.

    1. Find and run the test suite for {initiative}
    2. Verify services are actually running (check ports)
    3. Report pass/fail with evidence via SendMessage to team-lead
    """
)

Task(
    subagent_type="Explore",
    team_name=f"s3-{initiative}-oversight",
    name="s3-investigator",
    model="sonnet",
    prompt=f"""You are s3-investigator in the System 3 oversight team.
    Verify that code changes match what the orchestrator claimed.

    1. Check git diff for actual file changes
    2. Verify test files exist for implementations
    3. Report findings via SendMessage to team-lead
    """
)

# Step 0d: Wait for team results (DO NOT proceed until both report back)
# Results arrive via SendMessage — do not proceed to step 1 until received

# Step 0e: Shutdown oversight team after validation
SendMessage(type="shutdown_request", recipient="s3-test-runner", content="Validation complete")
SendMessage(type="shutdown_request", recipient="s3-investigator", content="Validation complete")
```

**If validation fails**: Do NOT proceed to cleanup. Send rejection to orchestrator and restart the cycle.
**If validation passes**: Continue to step 1.

### [ ] 1. Collect Outcomes

```python
progress_log = Read(f"trees/{initiative}/.claude/progress/orch-{initiative}-log.md")
```

### [ ] 2. Apply Process Supervision

```python
validation = mcp__hindsight__reflect(
    f"""
    PROCESS SUPERVISION: Validate orchestrator reasoning

    INITIATIVE: {initiative}
    REASONING PATH: {progress_log}

    VERDICT: VALID or INVALID
    CONFIDENCE: 0.0 to 1.0
    """,
    budget="high",
    bank_id="system3-orchestrator"
)
```

### [ ] 3. Store Learnings

```python
# Valid pattern
mcp__hindsight__retain(
    content=f"Validated pattern: {pattern_summary}",
    context="system3-patterns",
    bank_id="system3-orchestrator"
)

# Or anti-pattern
mcp__hindsight__retain(
    content=f"Anti-pattern: {failure_description}",
    context="system3-anti-patterns",
    bank_id="system3-orchestrator"
)
```

### [ ] 4. Check Key Results

```python
# Did this advance any Key Results?
for kr in get_key_results_for(business_epic):
    if can_verify_now(kr):
        Task(subagent_type="validation-test-agent",
             prompt=f"--mode=e2e --prd={prd_id} --task_id={kr.id}")
```

### [ ] 5. Merge Work

```bash
cd trees/[name]/agencheck
git push -u origin [branch-name]
gh pr create --title "[initiative] Implementation" --body "..."
```

### [ ] 6. Cleanup Team

```python
# Shut down all workers
SendMessage(type="broadcast", content="All tasks complete. Shutting down team.")
# Then for each worker:
SendMessage(type="shutdown_request", recipient="worker-name", content="Task complete")
# Finally:
Teammate(operation="cleanup")
```

### [ ] 7. Cleanup Worktree

```bash
# Update registry (automatic if using terminate script)
./scripts/terminate-orchestrator.sh [initiative-name]

# Or remove worktree
/remove_worktree [initiative-name]
```

**Detailed workflow**: See [references/post-orchestration.md](references/post-orchestration.md)

---

## PARALLEL ORCHESTRATORS

### Coordination Rules

1. **No Overlapping Files** - Clear file ownership per orchestrator
2. **Independent Epics** - No dependent tasks across orchestrators
3. **Shared Knowledge** - All learnings go to central Hindsight bank
4. **Regular Sync** - Check for conflicts before merging

### Registry

Maintain active orchestrators in `.claude/state/active-orchestrators.json`:

```json
{
  "orchestrators": [{
    "name": "orch-auth",
    "initiative": "auth",
    "worktree": "trees/auth/agencheck",
    "status": "active",
    "started_at": "2025-12-29T10:00:00Z"
  }]
}
```

---

## QUICK REFERENCE

### Scripts

| Script | Purpose |
|--------|---------|
| `./scripts/spawn-orchestrator.sh` | Spawn new orchestrator |
| `./scripts/status-orchestrators.sh` | Check all status |
| `./scripts/terminate-orchestrator.sh` | Graceful termination |
| `./scripts/inject-guidance.sh` | Send message |

### Commands

| Action | Command |
|--------|---------|
| List orchestrators | `tmux list-sessions \| grep orch-` |
| Attach to session | `tmux attach -t orch-[name]` |
| View output | `tmux capture-pane -t orch-[name] -p` |
| Create worktree | `/create_worktree [name]` |
| Remove worktree | `/remove_worktree [name]` |

### Reference Files

| File | Content |
|------|---------|
| [completion-promise.md](references/completion-promise.md) | Session state tracking, cs-* scripts |
| [prd-extraction.md](references/prd-extraction.md) | Goal extraction workflow |
| [validation-workflow.md](references/validation-workflow.md) | 3-level validation, validation-test-agent |
| [okr-tracking.md](references/okr-tracking.md) | Business Epic / Key Result tracking |
| [spawn-workflow.md](references/spawn-workflow.md) | Complete spawn process |
| [tmux-commands.md](references/tmux-commands.md) | tmux command reference |
| [post-orchestration.md](references/post-orchestration.md) | Post-completion workflow |
| [troubleshooting.md](references/troubleshooting.md) | Common issues and solutions |
| [oversight-team.md](references/oversight-team.md) | S3 oversight team spawn commands and patterns |

---

**Version**: 3.3.0
**Dependencies**: worktree-manager-skill, orchestrator-multiagent, tmux, Hindsight MCP
**Theory**: Sophia (arXiv:2512.18202), Hindsight (arXiv:2512.12818)

**v3.3.0 Changes**:
- Added PREFLIGHT step 5: Create Oversight Team (renumbered step 5 -> 6)
- Added "Also Start Oversight Team" to spawn workflow
- Added POST-COMPLETION step 0: Run Final Validation on impl_complete tasks
- New reference: oversight-team.md (4 specialist worker spawn commands)
- Custom beads status lifecycle: open -> in_progress -> impl_complete -> s3_validating -> closed

**v3.2.0 Changes**:
- Added `CLAUDE_CODE_TASK_LIST_ID` inline in spawn sequence (step 4)
- Added "First-to-Finish Blocking Monitor" pattern using shared TaskList
- Validation-agents update tracking tasks on completion (TaskUpdate)
- Blocking watcher polls TaskList (not tmux/beads) for simplicity
- Uses Claude Code's native task system for cross-subagent coordination

**v3.1.0 Changes**:
- **BREAKING**: Use `ccorch` instead of `launchcc` for spawning orchestrators
- Monitoring must use background Haiku 4.5 agents (never main thread)
- Enhanced monitoring pattern with specific reporting criteria
- Added explicit "Why background agents?" explanation

**v3.0.0 Changes**:
- Restructured as preflight checklist format
- Added 4 new reference files: completion-promise.md, prd-extraction.md, validation-workflow.md, okr-tracking.md
- Updated spawn-orchestrator.sh with CLAUDE_SESSION_DIR and CLAUDE_SESSION_ID
- Added validation expectations to preflight
- Added OKR linkage check to preflight
- Enhanced initialization template with message bus integration
