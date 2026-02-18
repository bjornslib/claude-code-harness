# Oversight Team Management Reference

Detailed reference for System 3's independent validation team.

---

## On-Demand Validator Pattern (PRD-S3-AUTONOMY-001 F4.1)

For targeted, single-task validations, System 3 spawns lightweight `s3-validator` teammates on-demand rather than maintaining a full oversight team.

### Quick Reference

```python
# Single on-demand validation
Task(
    subagent_type="validation-test-agent",
    team_name="s3-live",
    name=f"s3-validator-{task_id}",
    model="sonnet",
    prompt=f"""You are s3-validator-{task_id}. Validate task {task_id} against:
    {acceptance_criteria}
    Report via SendMessage to team-lead, then exit."""
)
```

### When to Use On-Demand vs Full Oversight Team

| Use On-Demand Validator | Use Full Oversight Team |
|------------------------|------------------------|
| Single task completed, need quick verification | Orchestrator reports ALL work complete |
| Incremental validation during execution | Final comprehensive check before closing epic |
| Specific acceptance criterion check | Multi-specialist verification needed |
| Browser-only or code-only validation | Investigation + audit + testing + collation |

### Parallel On-Demand Validators

Spawn multiple validators simultaneously for independent tasks:

```python
# Each validator runs independently, reports separately
for task in completed_tasks:
    Task(
        subagent_type="validation-test-agent",
        team_name="s3-live",
        name=f"s3-validator-{task.id}",
        model="sonnet",
        prompt=f"Validate {task.id}: {task.criteria}. Report to team-lead."
    )
# Correlate results by task_id in each validator's SendMessage
```

### Validator Lifecycle

1. **Spawn**: System 3 creates Task with team_name + unique name
2. **Receive**: Validator reads criteria from initial prompt
3. **Validate**: Runs tests, checks files, browser automation as needed
4. **Report**: Sends structured results via SendMessage to team-lead
5. **Exit**: Validator exits gracefully (no idle waiting)

---

## Worker Spawn Commands

### s3-investigator (Read-Only Codebase Verification)

```python
Task(
    subagent_type="Explore",
    team_name="s3-live",
    name="s3-investigator",
    model="sonnet",
    prompt="""You are s3-investigator in the System 3 oversight team.
    Your role: INDEPENDENTLY verify that code changes match what the orchestrator claims.

    When assigned a task via TaskList:
    1. Read the task description and PRD reference
    2. Use Glob/Grep/Read to verify files were actually modified
    3. Check that test files exist for the implementation
    4. Verify imports, function signatures, and integration points
    5. Report findings via SendMessage to team-lead

    You are READ-ONLY. You do not edit any files.
    You report FACTS, not opinions: "File X was modified", "No test file found for Y".

    After completing a task:
    - TaskUpdate(taskId=..., status="completed")
    - SendMessage(type="message", recipient="team-lead", content="Investigation complete: ...")
    - Check TaskList for more work
    """
)
```

### s3-prd-auditor (PRD Coverage Analysis)

```python
Task(
    subagent_type="solution-design-architect",
    team_name="s3-live",
    name="s3-prd-auditor",
    model="sonnet",
    prompt="""You are s3-prd-auditor in the System 3 oversight team.
    Your role: Verify that PRD requirements are actually addressed by the implementation.

    When assigned a task via TaskList:
    1. Read the PRD document referenced in the task
    2. Read acceptance test YAMLs if they exist
    3. Read the implementation code
    4. Produce a coverage matrix: PRD requirement -> implementation file -> test coverage
    5. Flag any gaps: requirements not implemented, tests not covering requirements
    6. Report findings via SendMessage to team-lead

    Be STRICT. If a PRD says "must handle error X" and there's no error handling, flag it.
    If a PRD says "must support Y" and Y is mocked/stubbed, flag it.

    After completing a task:
    - TaskUpdate(taskId=..., status="completed")
    - SendMessage(type="message", recipient="team-lead", content="PRD audit complete: ...")
    - Check TaskList for more work
    """
)
```

### s3-validator (Real E2E Testing)

```python
Task(
    subagent_type="validation-test-agent",
    team_name="s3-live",
    name="s3-validator",
    model="sonnet",
    prompt="""You are s3-validator in the System 3 oversight team.
    Your role: Run REAL E2E tests against REAL services. NO MOCKS.

    When assigned a task via TaskList:
    1. Check that required services are running (verify ports respond)
    2. Run acceptance tests: --mode=e2e --prd=PRD-XXX --task_id=<id>
    3. For browser tests: use chrome-devtools MCP (real browser, real clicks)
    4. For API tests: use curl/HTTP (real endpoints, real data)
    5. Capture evidence: screenshots, API responses, console logs
    6. Produce validation report with pass/fail per acceptance criterion
    7. Report findings via SendMessage to team-lead

    CRITICAL RULES:
    - If services aren't running, report FAIL. Don't mock.
    - If acceptance tests don't exist, report FAIL. Don't skip.
    - If tests use mocks/stubs for external services, report FAIL.
    - Only YOU are authorized to run `bd close` after all checks pass.

    After completing a task:
    - TaskUpdate(taskId=..., status="completed")
    - SendMessage(type="message", recipient="team-lead", content="Validation complete: ...")
    - Check TaskList for more work
    """
)
```

### s3-evidence-clerk (Report Collation)

```python
Task(
    subagent_type="general-purpose",
    team_name="s3-live",
    name="s3-evidence-clerk",
    model="haiku",
    prompt="""You are s3-evidence-clerk in the System 3 oversight team.
    Your role: Collate reports from investigator, auditor, and validator into a structured closure report.

    When assigned a task via TaskList:
    1. Read the reports/messages from other oversight workers
    2. Create structured closure report with:
       - Investigation summary (what code actually changed)
       - PRD coverage matrix (what's covered, what's missing)
       - Validation results (which tests passed/failed)
       - Evidence inventory (screenshots, API responses captured)
       - Overall verdict: PASS or FAIL with reasons
    3. Write report to .claude/evidence/{task-id}/closure-report.md
    4. Report summary via SendMessage to team-lead

    After completing a task:
    - TaskUpdate(taskId=..., status="completed")
    - SendMessage(type="message", recipient="team-lead", content="Closure report ready: ...")
    - Check TaskList for more work
    """
)
```

## Task Assignment Patterns

### Dispatching Validation Work

When System 3 detects `impl_complete`:

```python
# 1. Update status
Bash("bd update <id> --status=s3_validating")

# 2. Create investigation task
TaskCreate(
    subject=f"Investigate {task_id}: verify code changes",
    description=f"""Verify code changes for {task_id}.
    PRD: {prd_ref}
    Claimed changes: {orchestrator_report}
    Check: files modified, tests exist, imports correct""",
    activeForm=f"Investigating {task_id}"
)
SendMessage(type="message", recipient="s3-investigator",
    content=f"Investigation task available for {task_id}",
    summary="Investigation request")

# 3. Create PRD audit task
TaskCreate(
    subject=f"Audit PRD coverage for {task_id}",
    description=f"""Check PRD coverage for {task_id}.
    PRD path: {prd_path}
    Implementation files: {file_list}
    Acceptance tests: {at_path}""",
    activeForm=f"Auditing PRD coverage for {task_id}"
)
SendMessage(type="message", recipient="s3-prd-auditor",
    content=f"PRD audit task available for {task_id}",
    summary="PRD audit request")

# 4. Create E2E validation task
TaskCreate(
    subject=f"E2E validate {task_id}",
    description=f"""Run E2E acceptance tests for {task_id}.
    --mode=e2e --prd={prd_ref} --task_id={task_id}
    Services required: {service_ports}
    Evidence dir: .claude/evidence/{task_id}/""",
    activeForm=f"E2E validating {task_id}"
)
SendMessage(type="message", recipient="s3-validator",
    content=f"E2E validation task available for {task_id}",
    summary="E2E validation request")
```

### Collecting Results and Decision

```python
# After all 3 workers report back via SendMessage:
# Create evidence collation task
TaskCreate(
    subject=f"Collate evidence for {task_id}",
    description=f"""Collate reports for {task_id}.
    Investigation: {investigator_report}
    PRD audit: {auditor_report}
    Validation: {validator_report}
    Write to: .claude/evidence/{task_id}/closure-report.md""",
    activeForm=f"Collating evidence for {task_id}"
)
SendMessage(type="message", recipient="s3-evidence-clerk",
    content=f"Evidence collation task available for {task_id}",
    summary="Collation request")

# After clerk reports:
if all_passed:
    Bash(f"bd close {task_id} --reason 'S3 validated: all checks pass'")
    Bash(f"mb-send orch-{{name}} s3_validated '{{\"task_id\": \"{task_id}\"}}'")
else:
    Bash(f"bd update {task_id} --status=in_progress")
    Bash(f"mb-send orch-{{name}} s3_rejected '{{\"task_id\": \"{task_id}\", \"issues\": \"{failure_summary}\"}}'")
```

## Worker Lifecycle

1. **Spawn**: During System 3 PREFLIGHT, after creating oversight team
2. **Idle**: Workers wait for tasks to appear in TaskList
3. **Active**: Workers claim and complete validation tasks
4. **Continuous**: Workers check TaskList after each task for more work
5. **Shutdown**: When initiative is complete, System 3 sends shutdown requests

## Evidence Directory Structure

```
.claude/evidence/
├── .gitkeep
├── {task-id-1}/
│   ├── closure-report.md          # Evidence clerk output
│   ├── investigation-report.md    # Investigator findings
│   ├── prd-coverage-matrix.md     # Auditor coverage analysis
│   ├── validation-results.md      # Validator test results
│   └── screenshots/               # E2E evidence
│       ├── test-1-pass.png
│       └── test-2-fail.png
└── {task-id-2}/
    └── ...
```
