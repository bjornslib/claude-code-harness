# Orchestrator Architecture V2: Task-Based Delegation

## Overview

This document outlines architectural changes to improve orchestrator reliability through:
1. **Task-based delegation** instead of tmux sessions
2. **System3 involvement** in PRD writing with acceptance tests
3. **Continuous validation monitoring** via validation-agent
4. **Decision-time guidance integration** for stuck detection

## Current State (V1)

```
System3
    └── Spawns Orchestrator (in tmux or worktree)
            └── Spawns Workers (via tmux sessions)
                    └── Workers implement features
                            └── Report back manually
```

**Problems with V1:**
- tmux sessions are fragile (can disconnect, lose context)
- No structured reporting from workers to orchestrators
- No continuous validation - only at task closure
- System3 not involved in PRD quality assurance
- Acceptance tests written after implementation (too late)

## Proposed State (V2)

```
System3
    ├── Writes PRD with acceptance tests upfront
    │       └── acceptance-tests-writing skill generates tests from PRD
    │
    ├── Spawns Orchestrator via Task(subagent_type="orchestrator")
    │       ├── Delegates to workers via Task(subagent_type="*-expert")
    │       │       └── Workers return structured results
    │       │
    │       ├── Uses validation-agent --mode=monitor continuously
    │       │       └── Gets progress reports every N tool calls
    │       │
    │       └── Decision-time guidance detects stuck patterns
    │               └── Triggers System3 consultation when needed
    │
    └── Monitors via validation-agent --mode=monitor
            └── Can intervene if orchestrator is stuck
```

---

## Change 1: Task-Based Delegation (No tmux)

### Current Pattern (tmux)
```python
# Orchestrator spawns worker via tmux
Bash("tmux new-session -d -s worker-auth")
Bash("tmux send-keys -t worker-auth 'claude' Enter")
Bash("tmux send-keys -t worker-auth 'Implement auth feature...' Enter")
# ... later check via tmux capture-pane
```

### New Pattern (Task agents)
```python
# Orchestrator spawns worker via Task tool
result = Task(
    subagent_type="backend-solutions-engineer",
    prompt="""
    ## Task: Implement Authentication Feature

    **Context**: {context from orchestrator}

    **Requirements**:
    1. Create auth endpoints in /api/auth/
    2. Implement JWT token handling
    3. Add rate limiting

    **Acceptance Criteria**:
    - POST /api/auth/login returns JWT
    - Token expires after 1 hour
    - Rate limit: 5 attempts per minute

    **Report back with**:
    - Files modified
    - Tests written/passed
    - Any blockers encountered
    """,
    description="Implement auth feature"
)

# Result returned directly to orchestrator
print(f"Worker completed: {result}")
```

### Benefits
- **Structured results**: Workers return directly to orchestrator
- **No state management**: No tmux session tracking
- **Parallel execution**: Multiple Task calls can run concurrently
- **Context preservation**: Each worker gets clean context
- **Automatic retry**: Claude Code handles worker failures

### Implementation Steps
1. Update `orchestrator.md` output-style to use Task instead of tmux
2. Remove tmux-related helpers from orchestrator skill
3. Add worker result parsing utilities
4. Update delegation checklist to use Task pattern

---

## Change 2: System3 PRD Writing with Acceptance Tests

### Current Flow
```
User Request → System3 → (optional PRD) → Orchestrator → Implementation → Tests
```

### New Flow
```
User Request → System3 PRD Workshop → PRD + Acceptance Tests → Orchestrator → Implementation
                    │
                    ├── Structured PRD template
                    ├── Acceptance criteria for each feature
                    └── acceptance-tests-writing generates test stubs
```

### PRD Workshop Process

```python
# System3 initiates PRD workshop
def create_prd_with_tests(user_request: str):
    # Step 1: Draft PRD structure
    prd_draft = Task(
        subagent_type="solution-design-architect",
        prompt=f"""
        Create PRD for: {user_request}

        Include:
        - Epic breakdown
        - Features per epic
        - Acceptance criteria (testable)
        - Technical constraints
        """,
        description="Draft PRD structure"
    )

    # Step 2: Generate acceptance tests from PRD
    Task(
        subagent_type="tdd-test-engineer",
        prompt=f"""
        Read the PRD: {prd_path}

        For each feature's acceptance criteria, generate:
        1. Test file stub in acceptance-tests/{prd_id}/
        2. Test cases (can be empty bodies)
        3. Expected assertions

        Use the acceptance-tests-writing skill.
        """,
        description="Generate acceptance test stubs"
    )

    # Step 3: System3 reviews and approves
    return review_prd_and_tests(prd_draft)
```

### Acceptance Tests Directory Structure
```
acceptance-tests/
├── PRD-AUTH-001/
│   ├── test_login.py
│   ├── test_token_refresh.py
│   └── test_rate_limiting.py
├── PRD-PAYMENT-002/
│   ├── test_checkout.py
│   └── test_refunds.py
└── README.md
```

### Implementation Steps
1. Create `system3-prd-workshop` skill
2. Integrate `acceptance-tests-writing` skill into PRD workflow
3. Update System3 output-style to include PRD validation
4. Add PRD quality gates before orchestrator spawn

---

## Change 3: Validation Agent Monitoring Mode

### Current Modes
- `--mode=unit`: Fast technical checks with mocks
- `--mode=e2e`: PRD acceptance criteria validation

### New Mode: `--mode=monitor`
```bash
# Continuous monitoring of orchestrator progress
validation-agent --mode=monitor \
    --session-id=orch-auth-123 \
    --interval=30 \
    --task-list-id=session-abc
```

### Monitor Mode Behavior

```python
class ValidationMonitor:
    """Continuous validation monitoring for orchestrator sessions."""

    def __init__(self, session_id: str, task_list_id: str):
        self.session_id = session_id
        self.task_list_id = task_list_id
        self.goal_validator = GoalValidator()
        self.error_tracker = ErrorTracker()

    def check_progress(self) -> MonitorReport:
        """Check current progress and return status report."""

        # Load tasks from .claude/tasks/{task_list_id}
        tasks = self.goal_validator.load_tasks()
        task_pct, incomplete = self.goal_validator.get_task_completion_pct()

        # Check error patterns
        errors = self.error_tracker.get_recent_errors()
        is_stuck = len(errors) >= 4

        # Load completion state
        state = self.goal_validator.load_completion_state()

        return MonitorReport(
            session_id=self.session_id,
            completion_pct=task_pct,
            tasks_total=len(tasks),
            tasks_complete=len([t for t in tasks if t.is_complete]),
            is_stuck=is_stuck,
            recent_errors=len(errors),
            should_intervene=is_stuck and task_pct < 50,
            recommendations=self._generate_recommendations(is_stuck, task_pct, incomplete)
        )

    def _generate_recommendations(self, is_stuck, pct, incomplete) -> list[str]:
        if is_stuck and pct < 30:
            return ["Orchestrator appears stuck early. Consider System3 consultation."]
        if is_stuck and pct >= 50:
            return ["Making progress but hitting errors. Review recent failures."]
        if pct < 100 and not is_stuck:
            return [f"On track. {len(incomplete)} tasks remaining."]
        return ["Validation passed."]
```

### Monitor Report Format
```json
{
    "session_id": "orch-auth-123",
    "timestamp": "2026-01-24T12:00:00Z",
    "completion_pct": 45.0,
    "tasks": {
        "total": 8,
        "completed": 3,
        "in_progress": 2,
        "pending": 3
    },
    "health": {
        "is_stuck": false,
        "recent_errors": 2,
        "doom_loop_detected": false
    },
    "should_intervene": false,
    "recommendations": ["On track. 5 tasks remaining."]
}
```

### Implementation Steps
1. Add `--mode=monitor` to validation-agent
2. Create `MonitorReport` dataclass
3. Add interval-based polling option
4. Create System3 → validation-agent integration

---

## Change 4: System3 Active Monitoring

### System3 Monitoring Loop

```python
# In system3-meta-orchestrator output-style

async def monitor_orchestrator(orch_session_id: str, task_list_id: str):
    """System3 monitors orchestrator progress actively."""

    while True:
        # Check progress via validation-agent
        report = Task(
            subagent_type="validation-agent",
            prompt=f"--mode=monitor --session-id={orch_session_id} --task-list-id={task_list_id}",
            description="Check orchestrator progress"
        )

        if report.should_intervene:
            # Send guidance to orchestrator
            guidance = generate_guidance(report)
            Bash(f"mb-send {orch_session_id} '{json.dumps(guidance)}'")

        if report.completion_pct >= 100:
            # Orchestrator completed - run final validation
            break

        # Wait before next check
        await sleep(60)  # Check every minute
```

### Intervention Triggers
1. **Stuck detection**: 4+ errors with < 50% progress
2. **Doom loop**: Same file edited 3+ times without progress
3. **Worker failures**: 2+ workers failed on same task
4. **Timeout**: No progress for 10+ minutes

### Guidance Messages
```python
INTERVENTION_MESSAGES = {
    "stuck_early": """
## System3 Guidance: You Appear Stuck

I've detected multiple errors with limited progress ({pct}% complete).

**Consider**:
1. Re-read the original requirements
2. Try a different approach
3. Break the current task into smaller steps

**Original goal**: {original_prompt}
""",
    "worker_failures": """
## System3 Guidance: Worker Failures Detected

{failure_count} worker(s) have failed on task {task_id}.

**Options**:
1. Assign to a different worker type
2. Simplify the task scope
3. Check if prerequisites are missing

Send me a status update with: mb-send system3 '{"type": "status_update", ...}'
""",
}
```

### Implementation Steps
1. Add monitoring loop to System3 output-style
2. Create intervention message templates
3. Add `--background` option for validation-agent monitor mode
4. Integrate with message bus for bidirectional communication

---

## Change 5: PRD → Acceptance Tests Integration

### Skill: acceptance-tests-writing

The skill generates test stubs directly from PRD acceptance criteria:

```python
# Usage in PRD workshop
Task(
    subagent_type="tdd-test-engineer",
    prompt="""
    Use the acceptance-tests-writing skill to generate tests from PRD.

    PRD: .taskmaster/docs/{prd_name}.md

    For each acceptance criterion in the PRD:
    1. Create a test file in acceptance-tests/{prd_id}/
    2. Write test function stubs with descriptive names
    3. Add TODO comments for implementation
    4. Include assertion placeholders

    Output directory: acceptance-tests/{prd_id}/
    """,
    description="Generate acceptance tests from PRD"
)
```

### Generated Test Structure
```python
# acceptance-tests/PRD-AUTH-001/test_login.py
"""
Acceptance tests for: User Authentication Login
PRD: PRD-AUTH-001
Feature: F1.1 - User Login

Generated from acceptance criteria in PRD.
"""

import pytest


class TestUserLogin:
    """Tests for user login functionality."""

    def test_valid_credentials_return_jwt(self):
        """
        AC: POST /api/auth/login with valid credentials returns JWT token

        TODO: Implement test
        """
        # Arrange
        # Act
        # Assert
        pytest.skip("Not implemented - acceptance test stub")

    def test_invalid_credentials_return_401(self):
        """
        AC: POST /api/auth/login with invalid credentials returns 401

        TODO: Implement test
        """
        pytest.skip("Not implemented - acceptance test stub")

    def test_token_expires_after_one_hour(self):
        """
        AC: JWT token expires after 1 hour

        TODO: Implement test
        """
        pytest.skip("Not implemented - acceptance test stub")
```

### Validation Agent E2E Mode Uses These Tests
```bash
# When validating feature completion
validation-agent --mode=e2e --prd=PRD-AUTH-001

# Runs: pytest acceptance-tests/PRD-AUTH-001/ -v
# Reports which acceptance criteria pass/fail
```

---

## Implementation Order

### Phase 1: Foundation (This PR)
1. ✅ Decision-time guidance system
2. ✅ GoalValidator with task loading
3. ✅ Stop-gate integration
4. ⬜ Update orchestrator output-style for Task delegation

### Phase 2: Validation Monitoring
5. ⬜ Add `--mode=monitor` to validation-agent
6. ⬜ Create MonitorReport format
7. ⬜ Add System3 monitoring loop

### Phase 3: PRD Workshop
8. ⬜ Create system3-prd-workshop skill
9. ⬜ Integrate acceptance-tests-writing into PRD flow
10. ⬜ Add PRD quality gates

### Phase 4: Full Integration
11. ⬜ Update System3 output-style with new workflow
12. ⬜ Remove tmux dependencies from orchestrator
13. ⬜ End-to-end testing of new architecture

---

## Environment Variables Summary

| Variable | Purpose | Set By |
|----------|---------|--------|
| `CLAUDE_SESSION_ID` | Session identifier, `orch-*` = orchestrator | Launch scripts |
| `CLAUDE_CODE_TASK_LIST_ID` | Points to task list in `.claude/tasks/` | System3 |
| `CLAUDE_SESSION_DIR` | Session isolation directory | Launch scripts |
| `CLAUDE_ENFORCE_PROMISE` | Enable promise checking | System3 |
| `CLAUDE_MAX_ITERATIONS` | Circuit breaker limit | Config |

---

## Migration Path

### For Existing Orchestrators
1. Orchestrators can still use tmux (backward compatible)
2. New `use_task_delegation: true` flag in orchestrator skill
3. Gradual migration over multiple sessions

### For System3
1. PRD workshop is optional initially
2. Can adopt incrementally per project
3. Monitoring mode opt-in via `CLAUDE_ENABLE_MONITORING`

---

*This architecture evolves the harness from fragile tmux-based orchestration to robust Task-based delegation with continuous validation.*
