# Worker Delegation

Patterns for delegating implementation to tmux workers.

**Part of**: [Multi-Agent Orchestrator Skill](SKILL.md)

---

## Table of Contents
- [Core Principle](#core-principle)
- [Worker Types](#worker-types)
- [tmux Delegation Pattern](#tmux-delegation-pattern)
- [Worker Assignment Template](#worker-assignment-template)
- [Monitoring with Haiku](#monitoring-with-haiku)
- [Browser Testing Workers](#browser-testing-workers)
- [Worker Feedback](#worker-feedback)

---

## 🚨 3-Tier Hierarchy (CRITICAL)

Understanding the hierarchy prevents delegation violations:

| Tier | Role | Spawns | Implements |
|------|------|--------|------------|
| **TIER 1: System 3** | Meta-orchestrator | Orchestrators via tmux | ❌ Never |
| **TIER 2: Orchestrator** | Coordinator | Workers via tmux + Haiku monitors | ❌ Never |
| **TIER 3: Worker** | Implementer | ❌ Does NOT spawn sub-workers | ✅ Directly |

**The Key Insight**: Workers are the END of the chain. They implement directly using Edit/Write tools. Workers do NOT spawn their own sub-workers or sub-agents for implementation.

```
System 3 ──tmux──► Orchestrator ──tmux──► Worker ──Edit/Write──► Code
                                              │
                                              └──► (Task for validation ONLY, not implementation)
```

**Common Violation**: Workers spawning sub-agents for every coding step. This creates a 4-tier system and confuses responsibility. Workers ARE specialists - they implement directly.

---

## Core Principle

**Orchestrator = Coordinator. Worker = Implementer.**

Never use `Task(subagent_type=specialist)` directly - always delegate via tmux.

```bash
# WRONG - Direct sub-agent usage
Task(subagent_type="frontend-dev-expert", prompt="Implement...")

# RIGHT - Worker via tmux
tmux new-session -d -s worker-F001
tmux send-keys -t worker-F001 "launchcc"
tmux send-keys -t worker-F001 Enter
```

**Why `launchcc`?** The alias includes `--dangerously-skip-permissions` so workers edit files autonomously.

**Allowed exceptions**: `Task(subagent_type="Explore")` for investigation, `Task(model="haiku")` for monitoring.

---

## Worker Types

| Type | Via tmux | Use For |
|------|----------|---------|
| Frontend | `frontend-dev-expert` | React, Next.js, UI, TypeScript |
| Backend | `backend-solutions-engineer` | Python, FastAPI, PydanticAI, MCP |
| Browser Testing | `haiku` + chrome-devtools | E2E validation, browser automation |
| General | `general-purpose` | Scripts, docs, everything else |

### Quick Decision Rule

**Using Beads**: Worker type is stored in bead metadata:
```bash
bd show <bd-id>  # View metadata including worker_type
```

**If worker_type not specified**, determine from scope:
- Scope includes `*-frontend/*` -> `frontend-dev-expert`
- Scope includes `*-agent/*` or `*-backend/*` -> `backend-solutions-engineer`
- Otherwise -> `general-purpose`

---

## tmux Delegation Pattern

### Critical: tmux Enter Pattern

**Enter MUST be a separate `send-keys` command!**

```bash
# WRONG - Enter gets silently ignored (no error, just doesn't work)
tmux send-keys -t worker "command" Enter

# CORRECT - Enter as separate command
tmux send-keys -t worker "command"
tmux send-keys -t worker Enter
```

This affects 100% of worker delegation workflows.

### Step-by-Step Launch Procedure

#### Step 1: Create tmux Session

```bash
# Create detached tmux session for worker
tmux new-session -d -s worker-F001 -c /path/to/project

# Verify session created
tmux list-sessions | grep worker-F001
```

#### Step 2: Prepare Worker Prompt

```bash
# Write assignment to temporary file
cat > /tmp/worker-F001-prompt.txt << 'EOF'
You are a focused worker executing feature F001.

[Paste full Worker Assignment Template here]
EOF

# Verify prompt file
cat /tmp/worker-F001-prompt.txt
```

#### Step 3: Launch Claude Code Interactively

```bash
# Launch Claude Code in INTERACTIVE mode (no -p flag!)
tmux send-keys -t worker-F001 "claude --dangerously-skip-permissions --model claude-opus-4-5-20251101"
tmux send-keys -t worker-F001 Enter

# Wait for Claude to start
sleep 3

# Paste the assignment prompt
tmux send-keys -t worker-F001 "$(cat /tmp/worker-F001-prompt.txt)"
tmux send-keys -t worker-F001 Enter
```

**Why `--dangerously-skip-permissions`**: Workers need to act autonomously. Orchestrator has already verified scope constraints.

**Why NOT use `-p` flag**: Worker needs to be interactive for follow-up questions and feedback.

#### Step 4: Verify Worker Started

```bash
# Check worker output after 10 seconds
sleep 10
tmux capture-pane -t worker-F001 -p | tail -30

# Look for: "I'll help you implement...", "Let me start by...", Tool usage messages
```

### Launch Checklist

- [ ] tmux session created with correct name
- [ ] Worker assignment written to temp file
- [ ] Claude Code launched in INTERACTIVE mode (no `-p`)
- [ ] `--dangerously-skip-permissions` flag used
- [ ] Opus 4.5 model specified
- [ ] Assignment prompt pasted into session
- [ ] Worker output shows it's processing

---

## Worker Assignment Template

### Beads Format (RECOMMENDED)

```markdown
## Task Assignment: bd-xxxx

### Mandatory: Serena Mode Activation
Set mode before starting work:
mcp__serena__switch_modes(["editing", "interactive"])

### Checkpoint Protocol (NEVER SKIP)
1. After gathering context (3+ files/symbols):
   `mcp__serena__think_about_collected_information()`

2. Every 5 tool calls during implementation:
   `mcp__serena__think_about_task_adherence()`

3. BEFORE reporting completion (MANDATORY):
   `mcp__serena__think_about_whether_you_are_done()`

---

**Bead ID**: bd-xxxx
**Description**: [Task title from Beads]
**Priority**: P0/P1/P2/P3

**Validation Steps**:
1. [Step 1 from bead metadata]
2. [Step 2 from bead metadata]
3. [Step 3 from bead metadata]

**Scope** (ONLY these files):
- [file1.ts]
- [file2.py]

**Validation Type**: [browser/api/unit]

**Dependencies Verified**: [List parent beads that are closed]

**Your Role**:
- You are TIER 2 in the 3-tier hierarchy (Worker)
- Complete this ONE SMALL TASK - implement it DIRECTLY yourself
- Do NOT spawn sub-agents for implementation - you ARE the implementer
- ONLY modify files in scope list
- Use superpowers:test-driven-development
- Use superpowers:verification-before-completion before claiming done

**Implementation Approach**:
- Write the code yourself using Edit/Write tools
- Write the tests yourself using Edit/Write tools
- You are a specialist agent (frontend-dev-expert, backend-solutions-engineer, etc.)
- Sub-agents are ONLY for validation checks AFTER implementation, not during
- If you need research help, use Task(model="haiku") for quick lookups only

**When Done**:
1. Run all validation steps from above
2. Verify all tests pass
3. MANDATORY CHECKPOINT: `mcp__serena__think_about_whether_you_are_done()`
4. Report: "Task bd-xxxx COMPLETE" or "Task bd-xxxx BLOCKED: [details]"
5. Do NOT run `bd close` - orchestrator handles status updates
6. Commit with message: "feat(bd-xxxx): [description]"

**CRITICAL Constraints**:
- Do NOT modify files outside scope
- Do NOT leave TODO/FIXME comments
- Do NOT use "I think" or "probably" - verify everything
- Do NOT run `bd close` or update bead status
```

### Assignment Checklist

Before launching worker, verify assignment includes:

- [ ] Feature ID and exact description
- [ ] Complete validation steps list
- [ ] Explicit scope (file paths)
- [ ] Validation type specified
- [ ] Dependencies verified as passing
- [ ] Role explanation (TIER 2 = direct implementer)
- [ ] Implementation approach (worker implements directly, not via sub-agents)
- [ ] Completion criteria
- [ ] Critical constraints listed

---

## Monitoring with Haiku

### Haiku Monitor Sub-Agent (RECOMMENDED)

**Use a Haiku sub-agent to monitor workers - saves orchestrator context!**

```python
# Background monitor with TaskOutput retrieval
monitor_task = Task(
    subagent_type="general-purpose",
    model="haiku",
    run_in_background=True,  # MANDATORY - without this, orchestrator blocks!
    prompt="""
Monitor the tmux worker session 'worker-F001' until completion or blockers.

Instructions:
1. Check session every 30 seconds:
   tmux capture-pane -t worker-F001 -p | tail -50

2. Look for signals:
   - 'COMPLETE' - Worker finished successfully
   - 'BLOCKED' - Worker needs help
   - 'PASS' / 'FAIL' - Test results
   - 'Error' - Something went wrong

3. Continue monitoring silently until you detect:
   - COMPLETE signal -> Report: 'COMPLETE: [summary of what was done]'
   - BLOCKED signal -> Report: 'BLOCKED: [reason and what help is needed]'
   - No output for 5+ minutes -> Report: 'STALLED: Worker may be stuck'

4. ONLY report back when one of these conditions is met
5. Do NOT report intermediate progress - only final status
""")

# Capture agent_id for later retrieval
agent_id = monitor_task.agent_id

# Wait for monitor result (orchestrator waits efficiently via TaskOutput)
result = TaskOutput(task_id=agent_id, block=True, timeout=600000)  # 10 min max
```

**Why Haiku Monitors**:
- Orchestrator context is precious - don't waste it on polling
- Haiku is cheap and fast for simple monitoring tasks
- Monitor runs in background while orchestrator does other work
- Only reports when action is needed

### Monitor Checklist

- [ ] One Haiku monitor per worker
- [ ] Monitor checks every 30 seconds
- [ ] Monitor looks for completion signals
- [ ] Monitor reports only final status (not intermediate)
- [ ] Monitor includes error details if BLOCKED
- [ ] `run_in_background=True` is specified (MANDATORY)
- [ ] `TaskOutput` is used to retrieve results

### Monitoring Signals

| Signal in Output | Meaning | Action |
|------------------|---------|--------|
| "COMPLETE" | Worker finished successfully | Retrieve output, validate, close bead |
| "BLOCKED" | Worker needs help | Read blocker reason, provide solution |
| "FAIL" after test run | Tests failed | Review failure, provide fix or retry |
| "PASS" after test run | Tests passed | Good sign, wait for validation |
| No output for 5+ minutes | Worker stalled | Check if stuck, provide hint or restart |
| "Error:" or "Exception:" | Runtime error | Review error, provide fix or retry |
| Files outside scope | Scope violation | Reject immediately, fresh retry |

---

## Browser Testing Workers

### Overview

Browser testing workers enable actual E2E validation using chrome-devtools MCP tools for real browser automation, not just unit tests.

**Pattern**: Orchestrator -> Worker (via tmux) -> chrome-devtools MCP -> Execution Report -> Orchestrator Review

### When to Use

**Use browser testing workers when**:
- Feature requires validation of actual browser behavior
- Testing UI interactions, animations, scroll behavior
- Validating accessibility (keyboard navigation, ARIA)
- Performance testing (load times, interaction responsiveness)
- Visual regression testing (screenshots, layout)

**Don't use for**:
- Pure logic testing (use unit tests)
- API endpoint testing (use curl/HTTP requests)
- Backend validation (use pytest)

### Markdown-Based Test Specification Workflow

```
1. TEST SPECIFICATION (Markdown)
   Location: __tests__/e2e/specs/J{N}-{journey-name}.md
   Template: __tests__/e2e/specs/TEMPLATE.md
   Format: Given/When/Then with MCP chrome-devtools steps
                                 |
                                 v
2. WORKER EXECUTION (via tmux)
   - Orchestrator launches Worker in tmux session
   - Worker reads the test spec Markdown file
   - Worker executes tests using chrome-devtools MCP tools
   - Worker captures screenshots as evidence
                                 |
                                 v
3. EXECUTION REPORT (Markdown)
   Location: __tests__/e2e/results/J{N}/J{N}_EXECUTION_REPORT.md
   Contents: Pass/Fail per test, evidence manifest, issues found
                                 |
                                 v
4. ORCHESTRATOR REVIEW
   - Reviews execution report for anomalies
   - Sense-checks results against expected behavior
   - Re-executes any tests that seem incorrect
   - Approves or requests fixes
```

### Key Files

| File | Purpose |
|------|---------|
| `__tests__/e2e/specs/TEMPLATE.md` | Standard format for test specifications |
| `__tests__/e2e/specs/J{N}-*.md` | Journey-specific test specs |
| `__tests__/e2e/results/EXECUTION_REPORT_TEMPLATE.md` | Standard format for execution reports |
| `__tests__/e2e/results/J{N}/J{N}_EXECUTION_REPORT.md` | Filled-out execution report |
| `__tests__/e2e/results/J{N}/*.png` | Screenshot evidence |

### Browser Testing Worker Launch Pattern

```python
Task({
    subagent_type: "general-purpose",
    model: "haiku",
    description: "Launch browser-testing worker for F084",
    prompt: """MISSION: Set up E2E testing worker with chrome-devtools

FEATURE: F084 - [Feature description]

PHASES:
1. Setup: Create tmux session and launch Claude Code worker
2. Assignment: Send testing checklist to worker
3. Monitor: Track progress and report results

EXECUTION:

## Phase 1: Setup Worker Session

SESSION="e2e-worker-f084"
tmux new-session -d -s $SESSION
tmux send-keys -t $SESSION "claude --model claude-haiku-4-5-20250514"
tmux send-keys -t $SESSION Enter
sleep 5

## Phase 2: Send Testing Assignment

[Include testing checklist with chrome-devtools commands]

## Phase 3: Monitor Progress

[Monitor loop checking for completion signals]

SUCCESS CRITERIA:
- chrome-devtools connected successfully
- Worker received testing assignment
- All test steps executed
- Results reported with pass/fail status"""
})
```

### Worker Testing Assignment Template

```markdown
FEATURE: [ID] - [Description]

TARGET: http://localhost:[port]/[path]

TESTING CHECKLIST:
- [ ] [Action 1] ([chrome-devtools command])
- [ ] [Action 2] ([chrome-devtools command])
- [ ] [Action 3] ([chrome-devtools command])

VALIDATION CRITERIA:
- [Criterion 1]
- [Criterion 2]
- [Criterion 3]

EXPECTED BEHAVIOR:
- [Behavior 1]
- [Behavior 2]

REPORT FORMAT:
- Pass/Fail per item
- Screenshots of key states
- Console log analysis
- Overall assessment
```

### Connection Validation

**Check tmux capture-pane for**:

| Indicator | State | Action |
|-----------|-------|--------|
| "connected" in MCP status | Connected | Proceed |
| "chrome-devtools" checkmark | Connected | Proceed |
| "failed" or "error" | Failed | Check MCP config |
| `Context left: X%` where X<15 | Low context | May need /clear |

### Troubleshooting

**chrome-devtools Won't Connect**:
1. Check `.mcp.json` has chrome-devtools configured
2. Verify Chrome DevTools MCP server is installed
3. Check for port conflicts
4. Try manual attach: `tmux attach-session -t session`

**Worker Stuck in Loop**:
1. Attach to session: `tmux attach-session -t session`
2. Send C-c to interrupt
3. Provide clarifying guidance
4. If unrecoverable: `tmux kill-session -t session`

**Tests Pass But Feature Broken** (Hollow Test Problem):
- Worker may be testing mocked/stubbed behavior
- DOM elements present but non-functional
- Update assignment to use production endpoints
- Add real data validation
- Test actual user workflows

---

## Worker Feedback

### When to Intervene

| Trigger | Timing | Action |
|---------|--------|--------|
| Worker reports BLOCKED | Immediate | Read blocker, provide solution |
| No output for 10+ minutes | After 10 min | Check status, provide hint |
| Files outside scope modified | Immediate | Reject, provide correction |
| Repeated errors on same step | After 2-3 attempts | Provide alternative or decompose |
| Worker asks question | Immediate | Answer via send-keys |

### Providing Feedback via tmux

```bash
# Short message
tmux send-keys -t worker-F001 "Your feedback here"
tmux send-keys -t worker-F001 Enter

# Multi-line message
tmux send-keys -t worker-F001 "$(cat <<'EOF'
Your feedback here.
Can be multiple lines.
EOF
)"
tmux send-keys -t worker-F001 Enter
```

### Example Interventions

**Worker blocked on missing dependency**:
```bash
tmux send-keys -t worker-F001 "$(cat <<'EOF'
The backend endpoint you need doesn't exist yet.
For now, create a mock that returns sample data.
We'll implement the real endpoint in the next feature.
EOF
)"
tmux send-keys -t worker-F001 Enter
```

**Worker exceeded scope**:
```bash
tmux send-keys -t worker-F001 "$(cat <<'EOF'
STOP - You modified files outside your scope.
Your scope is ONLY:
- agencheck-support-frontend/components/ChatInterface.tsx

Please revert changes to other files and stay within scope.
EOF
)"
tmux send-keys -t worker-F001 Enter
```

### Feedback Best Practices

**DO**:
- Be specific and actionable
- Reference existing code patterns when possible
- Provide examples or file paths
- Acknowledge what worker got right

**DON'T**:
- Be vague ("just make it work")
- Solve the whole problem (let worker figure it out)
- Provide conflicting instructions
- Ignore repeated blockers (decompose instead)

### Retrieving Worker Output

```bash
# Capture full session output
tmux capture-pane -t worker-F001 -p -S - > /tmp/worker-F001-output.txt

# View output
cat /tmp/worker-F001-output.txt

# Extract: What was implemented, tests run, validation performed, warnings
```

### 🚨 MANDATORY: Cleanup After Worker Completes

**CRITICAL**: Always kill worker tmux sessions after they complete. Failure to do so results in session buildup that consumes system resources.

```bash
# 1. Kill the specific worker session
tmux kill-session -t worker-F001

# 2. Verify session terminated
tmux list-sessions | grep worker-F001
# Should return nothing

# 3. Clean up temp files
rm -f /tmp/worker-F001-*.txt
```

**Batch cleanup for multiple completed workers:**

```bash
# List all worker sessions
tmux list-sessions 2>/dev/null | grep "^worker-" | awk -F: '{print $1}'

# Kill all worker sessions matching a pattern (e.g., completed initiative)
for session in $(tmux list-sessions 2>/dev/null | grep "worker-dspy-" | awk -F: '{print $1}'); do
    tmux kill-session -t "$session" 2>/dev/null && echo "Killed: $session"
done

# Verify cleanup - should show only active workers
tmux list-sessions 2>/dev/null | grep worker- | wc -l
```

**When to cleanup:**
- ✅ After worker reports COMPLETE
- ✅ After worker reports BLOCKED (and you've captured output)
- ✅ Before starting a new initiative (clean slate)
- ✅ At session end (cleanup all your workers)

**Include in orchestrator's Session End protocol:**
```bash
# Kill all worker sessions for this initiative
for session in $(tmux list-sessions 2>/dev/null | grep "worker-" | awk -F: '{print $1}'); do
    tmux kill-session -t "$session" 2>/dev/null && echo "Cleaned up: $session"
done
```

---

## Red Flags

| Signal | Action |
|--------|--------|
| Modified files outside scope | Reject - Fresh retry |
| TODO/FIXME in output | Reject - Fresh retry |
| Validation fails | Reject - Fresh retry |
| Exceeds 2 hours | Stop - Re-decompose |
| "I think" or "probably" | Warn - Verify everything |
| Didn't run validation steps | Reject - Must validate |

---

## Related Documents

- **[SKILL.md](SKILL.md)** - Main orchestrator skill
- **[WORKFLOWS.md](WORKFLOWS.md)** - Feature decomposition, autonomous mode
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Recovery patterns
- **[BEADS_INTEGRATION.md](BEADS_INTEGRATION.md)** - Task state management

---

**Document Version**: 1.0
**Last Updated**: 2026-01-07
**Consolidated From**: WORKER_DELEGATION_GUIDE.md, BROWSER_TESTING_WORKERS.md
