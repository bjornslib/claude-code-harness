# Research: Orchestrator Per-Step Task Creation

**PRD**: PRD-SEQ-PROGRESSION-001 (Epic E), PRD-DASHBOARD-AUDIT-001 (Epic A prerequisite)
**Date**: 2026-03-11
**Researcher**: Research Worker
**Status**: Complete

---

## Executive Summary

This research analyzes the current `verification_orchestrator.py` implementation to understand the root cause of the audit trail gap where sequence steps 2+ use the wrong `task_id` for dispatches. The findings confirm the Solution Design `SD-SEQ-PERSTEP-TASKS-001` is correct: each sequence step requires its own `background_tasks` row created **before** dispatch, not after step completion.

### Key Finding

The orchestrator currently uses a single `task_id` for all steps in a sequence (the original step 1 task). This causes:
1. Dashboard queries return only step 1 data
2. Email/SMS verification links reference the wrong step's task
3. Audit trail is fragmented across steps

### Required Fix

Add `create_step_task()` function in `utils/background_task_helpers.py` that creates a new `background_tasks` row for each step at the **start** of that step's dispatch. The orchestrator loop must then:
1. Create a step-specific task ID before each step's dispatch
2. Use that task ID for all dispatches in that step
3. Chain tasks via `previous_task_id`/`next_task_id`

---

## Current Implementation Analysis

### File: `prefect_flows/flows/verification_orchestrator.py`

#### Current Step Loop (Lines 426-531)

```python
async def verification_orchestrator_flow(...):
    # ...

    # Step 3a: Step-based iteration (when sequence steps are available)
    if steps:
        for i, step in enumerate(steps):
            channel_enum = _channel_type_to_enum(step.channel_type)
            step_label = f"{step.step_name}({channel_enum.value})"

            # Dispatch using ORIGINAL task_id (WRONG for steps 2+)
            result = await dispatch_channel_verification(
                channel=channel_enum,
                case_id=case_id,
                customer_id=customer_id,
                task_id=task_id,  # Same task_id for all steps!
                # ...
            )

            # Sleep before the next step
            if i < len(steps) - 1 and step.delay_hours > 0:
                await asyncio.sleep(delay_secs)

                # Check if case was resolved while we slept
                resolved = await _check_case_resolved(case_id, task_id)
                # ...
```

**Problem**: `task_id` parameter is passed to the flow and never updates across steps.

#### Current `dispatch_channel_verification` Call

The `dispatch_channel_verification` function (imported from `channel_dispatch`) receives the same `task_id` for all steps:

```python
result = await dispatch_channel_verification(
    channel=channel_enum,
    case_id=case_id,
    customer_id=customer_id,
    task_id=task_id,  # Never changes: always step 1's task_id
    task_uuid=task_uuid,
    check_type=check_type,
    retry_config=retry_config,
    sequence_id=sequence_id,
    sequence_version=sequence_version,
    context=context,
    attempt=i,
)
```

#### `_check_case_resolved` Validation (Lines 269-305)

This helper already rechecks the case status after sleep, confirming that external resolution is possible:

```python
async def _check_case_resolved(case_id: int, task_id: int) -> str | None:
    """Check if case or background_task has been resolved while we slept."""
    terminal_statuses = {"completed", "verified", "success", "cancelled"}

    row = await pool.fetchrow("""
        SELECT bt.status AS task_status, c.status AS case_status
        FROM background_tasks bt
        JOIN cases c ON c.id = bt.case_id
        WHERE bt.id = $1 AND c.id = $2
    """, task_id, case_id)
    # Returns terminal status if resolved
```

**This confirms the guard pattern already exists in the codebase** and can be used to check if a case is resolved before creating a step 2 task.

---

## Related Code Patterns

### `utils/background_task_helpers.py` - `create_retry_task()` (Lines 162-280)

This function already implements the **task chaining** pattern we need:

```python
async def create_retry_task(
    original_task_id: int,
    scheduled_time: datetime,
    timezone_str: str = "UTC",
    context_data_override: Optional[Dict[str, Any]] = None,
    sequence_id: Optional[str] = None,
    sequence_version: Optional[int] = None,
) -> Optional[int]:
    """Create a retry task linked to the original task."""
    # ... fetch original task details ...

    # INSERT new retry task with previous_task_id = original_task_id
    new_task_id = await conn.fetchval("""
        INSERT INTO background_tasks (
            task_id, customer_id, case_id, user_id, task_type,
            status, retry_count, max_retries, context_data,
            scheduled_time, timezone, action_type, previous_task_id,
            sequence_id, sequence_version, attempt_timestamp
        ) VALUES (
            $1, $2, $3, $4, $5,
            'pending', $6, $7, $8,
            $9, $10, $11, $12,
            $13, $14, NOW()
        )
        RETURNING id
    """, ...)

    # Update original task's next_task_id
    await conn.execute("""
        UPDATE background_tasks
        SET next_task_id = $1
        WHERE id = $2
    """, new_task_id, original_task_id)

    return new_task_id
```

**Key insights for per-step task creation**:
- The chaining pattern (`previous_task_id` -> `next_task_id`) is already working
- Task metadata storage via `context_data` JSONB is already in place
- Transactional INSERT + UPDATE ensures atomic task chain creation

### `prefect_flows/flows/tasks/process_result.py` - Retry Scheduling (Lines 220-270)

When a call result is retryable, a new task is created **within the same step**:

```python
if should_retry:
    retry_task_id = await pool.fetchval(
        """
        INSERT INTO background_tasks (
            task_id, customer_id, case_id,
            task_type, status, action_type,
            context_data, scheduled_time, max_retries,
            retry_count, previous_task_id
        ) VALUES (
            $1, $2, $3,
            'verification', 'pending', 'call_attempt',
            $4, $5, $6,
            $7, $8
        )
        RETURNING id
        """,
        str(_uuid.uuid4()),
        customer_id,
        case_id,
        retry_context,
        scheduled_for,
        MAX_CALL_RETRIES,
        (attempt_count or 0) + 1,
        task_id,  # Chain to current task
    )

    # Link the original task to the retry
    await pool.execute(
        "UPDATE background_tasks SET next_task_id = $1 WHERE id = $2",
        retry_task_id, task_id,
    )
```

**This shows the retry pattern already exists**, but it's for **within-step retries** (same `current_sequence_step`). Per-step task creation is for **cross-step advancement** (incrementing `current_sequence_step`).

### `prefect_flows/flows/tasks/followup_scheduler.py` - Step Exhaustion Handler

The `schedule_followup_task()` function handles step exhaustion and creates follow-up tasks:

```python
async def schedule_followup_task(
    case_id: int,
    customer_id: int,
    original_task_id: int,
    step: dict,
    attempt_number: int,
    sequence_id: str | None = None,
    sequence_version: int | None = None,
    context: dict | None = None,
) -> int | None:
    """Schedule the next follow-up task based on step configuration."""
    # 1. Check case status — do NOT schedule if completed/cancelled
    case_status = await _get_case_status(case_id)
    if case_status in ("completed", "cancelled", "manual_review"):
        logger.info("Case %d is %s — skipping follow-up", case_id, case_status)
        return None

    # 2. Check max attempts
    max_attempts = step.get("max_attempts", 1)
    if attempt_number >= max_attempts:
        logger.info("Max attempts (%d) reached for case %d", max_attempts, case_id)
        return None

    # 3. Calculate delay from retry_intervals
    retry_intervals = step.get("retry_intervals", [])
    # ...

    # 4. Create the follow-up task using create_retry_task
    task_id = await create_retry_task(
        original_task_id=original_task_id,
        scheduled_time=scheduled_for,
        timezone_str="UTC",
        context_data_override={...},
        sequence_id=sequence_id,
        sequence_version=sequence_version,
    )
```

**This is called when a step is exhausted**, not when a step begins. Per-step task creation must happen **before** any dispatch attempt.

---

## Database Schema Analysis

### `background_tasks` Table Columns (All Already Present)

| Column | Type | Current Usage | Per-Step Usage |
|--------|------|---------------|----------------|
| `id` | INT PK | Current task ID | New step gets new ID |
| `case_id` | INT FK | Set at case submission | Same for all steps |
| `customer_id` | INT | Set at case submission | Same for all steps |
| `action_type` | VARCHAR | `call_attempt`, `email_attempt`, etc. | `call_attempt`, `email_attempt`, etc. |
| `status` | VARCHAR | `pending`, `in_progress`, `completed`, `failed` | `in_progress` at step start |
| `result_status` | ENUM | `no_answer`, `voicemail_left`, `verified`, etc. | `NULL` at step start (not yet attempted) |
| `retry_count` | INT | Tracks within-step retries | `0` for new step |
| `max_retries` | INT | `1` for new step (no retries yet) | From step configuration |
| `context_data` | JSONB | Step metadata | `{"step_name": "first_call", "channel_type": "voice"}` |
| `previous_task_id` | INT FK | **Never used** | **Set to prior step's task** |
| `next_task_id` | INT FK | **Never used** | **Set by next step to link chain** |
| `current_sequence_step` | INT | Always `1` | **Set to step_order (1, 2, 3, ...)** |
| `sequence_id` | VARCHAR | Populated | From resolved sequence |
| `sequence_version` | INT | Populated | From resolved sequence |
| `check_type_config_id` | INT FK | Always populated | From case configuration |
| `scheduled_time` | TIMESTAMPTZ | Retry scheduling | `NULL` (immediate dispatch) |
| `attempt_timestamp` | TIMESTAMPTZ | Populated | `NOW()` at step start |
| `started_at` | TIMESTAMPTZ | Populated when processing | `NOW()` when step begins |
| `completed_at` | TIMESTAMPTZ | Populated on completion | `NULL` at step start |

**Conclusion**: No schema changes required. All needed columns already exist.

---

## Current Flow vs. Target Flow Comparison

### Current Flow (Broken)

```
API creates case -> background_tasks row #1 (task_id=101, step=1)
    ↓
verification_orchestrator_flow(task_id=101)
    ↓
Step 1: dispatch_voice(task_id=101)
    → process_result → completed? → exit
    → retryable? → create_retry_task(task_id=102, previous=101)
    → exhausted? → asyncio.sleep(delay) → [NO NEW TASK CREATED]
    ↓
Step 2: dispatch_email(task_id=101) ← WRONG! Uses step 1's task
    → process_result → exhausted? → asyncio.sleep(delay) → [NO NEW TASK CREATED]
    ↓
Step 3: dispatch_email(task_id=101) ← WRONG! Uses step 1's task

Background tasks visible in dashboard:
- task_id=101, step=1, action=call_attempt, status=completed
  (Steps 2+ not visible!)
```

### Target Flow (Fixed)

```
API creates case -> background_tasks row #1 (task_id=101, step=1)
    ↓
verification_orchestrator_flow(task_id=101)
    ↓
Step 1: [task already exists for step 1]
    dispatch_voice(task_id=101)
    → process_result → completed? → exit
    → retryable? → create_retry_task(task_id=102, previous=101)
    → exhausted? → asyncio.sleep(delay)
    ↓
Step 2 guard: case still not done? → YES
    create_step_task(step=2) → task_id=103
    dispatch_email(task_id=103) ← CORRECT!
    → process_result → exhausted? → asyncio.sleep(delay)
    ↓
Step 3 guard: case still not done? → YES
    create_step_task(step=3) → task_id=104
    escalate(task_id=104) ← CORRECT!

Background tasks visible in dashboard:
- task_id=101, step=1, action=call_attempt, status=completed
- task_id=103, step=2, action=email_attempt, status=in_progress
- task_id=104, step=3, action=email_attempt, status=pending
```

---

## Key Differences: `create_step_task()` vs `advance_sequence()`

The Solution Design mentions `advance_sequence()` from SD-SEQ-PROGRESSION-001. Based on my research, this function **does not exist yet** in the codebase. The required function is a **pre-dispatch task creation** helper.

### `create_step_task()` (Required)

| Aspect | Details |
|--------|---------|
| **When called** | Before dispatching a step's first attempt |
| **Initial status** | `in_progress` (will start dispatching now) |
| **Scheduled time** | `NULL` (immediate dispatch, no delay) |
| **Result status** | `NULL` (no result yet) |
| **Purpose** | Audit trail for the step being started |
| **Task chaining** | Sets `previous_task_id` on last step's task |

### `advance_sequence()` (Future - for catch-up/recovery)

| Aspect | Details |
|--------|---------|
| **When called** | After step completes/fails (recovery path) |
| **Initial status** | `pending` (scheduled for later) |
| **Scheduled time** | `NOW() + delay_hours` (may be in future) |
| **Result status** | `NULL` |
| **Purpose** | Cross-step advancement when orchestrator is offline |
| **Task chaining** | Sets `previous_task_id` on last step's task |

---

## Integration Points

### 1. `utils/background_task_helpers.py` - Add `create_step_task()`

```python
async def create_step_task(
    case_id: int,
    customer_id: int,
    step: dict,
    sequence_id: int,
    sequence_version: int,
    check_type_config_id: int,
    previous_task_id: int | None,
    db_pool,
) -> int:
    """Create a background_tasks row for a step that is about to begin.

    Called BEFORE dispatching the step's channel (voice/email/SMS).
    The returned task_id MUST be used for all dispatches in this step.
    """
    # Map channel_type to action_type
    channel_to_action = {
        'voice': 'call_attempt',
        'email': 'email_attempt',
        'sms': 'sms_attempt',
        'whatsapp': 'whatsapp_attempt',
    }
    action_type = channel_to_action.get(step['channel_type'], 'call_attempt')

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            # INSERT the new step task
            new_task_id = await conn.fetchval("""
                INSERT INTO background_tasks (
                    case_id,
                    customer_id,
                    action_type,
                    status,
                    current_sequence_step,
                    sequence_id,
                    sequence_version,
                    check_type_config_id,
                    previous_task_id,
                    retry_count,
                    max_retries,
                    context_data,
                    created_at,
                    attempt_timestamp
                ) VALUES (
                    $1, $2, $3, 'in_progress', $4, $5, $6, $7, $8,
                    0, $9, $10::jsonb, NOW(), NOW()
                )
                RETURNING id
            """,
                case_id,
                customer_id,
                action_type,
                step['step_order'],
                sequence_id,
                sequence_version,
                check_type_config_id,
                previous_task_id,
                step['max_attempts'],
                json.dumps({
                    "step_name": step['step_name'],
                    "channel_type": step['channel_type'],
                }),
            )

            # Chain: update previous task's next_task_id
            if previous_task_id is not None:
                await conn.execute("""
                    UPDATE background_tasks
                    SET next_task_id = $1
                    WHERE id = $2
                """, new_task_id, previous_task_id)

    return new_task_id
```

### 2. `prefect_flows/flows/verification_orchestrator.py` - Update Step Loop

The step loop needs to:
1. Track `current_task_id` (starts with original `task_id` for step 1)
2. Track `previous_task_id` (None for step 1, updated after each step)
3. Call `create_step_task()` before step 2+ dispatch
4. Use `current_task_id` for all dispatches

---

## Edge Cases to Handle

### Case Resolved During Delay

After `asyncio.sleep(delay_hours)`, the case may be resolved externally:

```python
# Re-check after sleep
case_status = await get_case_status(case_id, db_pool)
if case_status in TERMINAL_CASE_STATUSES:
    # Do NOT create step 2 task — case is done
    logger.info(f"Case {case_id} resolved during delay, stopping")
    return {"status": "resolved_during_delay", "stopped_at_step": i + 1}
```

### Idempotency on Orchestrator Restart

If the orchestrator crashes and restarts, it might try to create a step 2 task when one already exists:

```python
# Check if step task already exists
existing = await db_pool.fetchval("""
    SELECT id FROM background_tasks
    WHERE case_id = $1 AND current_sequence_step = $2
    LIMIT 1
""", case_id, step['step_order'])

if existing:
    current_task_id = existing  # Reuse existing task
else:
    current_task_id = await create_step_task(...)
```

### Email Template Task ID

ElectTemplates include a verification link: `/verify/{task_id}`. If the wrong task_id is used:
- Result recorded against wrong step
- Step 2 task stuck in `in_progress`
- Chain broken for step 3

**Solution**: Always use the `current_task_id` for dispatches in that step.

---

## Testing Strategy

### Unit Tests

1. **`create_step_task()` creates correct row**: Verify all columns set correctly
2. **Task chain integrity**: After creating step 2 task, verify step 1 task's `next_task_id` updated
3. **Guard prevents task creation for terminal cases**: If `cases.status = 'completed'`, no new task created
4. **Idempotency**: Calling `create_step_task()` twice for same step returns existing task_id

### Integration Tests

1. **Full 3-step sequence**: Submit case -> step 1 exhausted -> step 2 task created -> step 2 dispatched -> step 2 exhausted -> step 3 task created
2. **Dashboard query returns all steps**: After steps 1+2 complete, DB query returns 2+ rows with distinct `current_sequence_step` values
3. **Email verification link uses correct task_id**: Step 2 email contains `/verify/{step2_task_id}`, not `/verify/{step1_task_id}`
4. **External resolution during delay**: Start step 1, sleep for step 2 delay, resolve case externally during sleep -> verify no step 2 task created

---

## Files to Modify

| File | Change | Priority |
|------|--------|----------|
| `utils/background_task_helpers.py` | Add `create_step_task()` function | P0 |
| `prefect_flows/flows/verification_orchestrator.py` | Replace in-memory step loop with per-step task creation + guard | P0 |
| `prefect_flows/flows/tasks/process_result.py` | Ensure `task_id` in results refers to current step's task | P0 |
| `prefect_flows/flows/email_dispatch.py` | Verify email template uses received `task_id` (not hardcoded) | P1 |
| `prefect_flows/flows/voice_verification.py` | Verify voice dispatch uses received `task_id` | P1 |
| `prefect_flows/flows/tasks/followup_scheduler.py` | Update `schedule_followup_task()` to use per-step task pattern | P1 |

---

## Acceptance Criteria

- [ ] After each step in a 3-step sequence, a new `background_tasks` row exists with the correct `current_sequence_step`
- [ ] `previous_task_id`/`next_task_id` chain is intact across all step tasks
- [ ] Voice calls in step 1 use step 1's task_id; emails in step 2 use step 2's task_id
- [ ] If a case is resolved externally during the delay between steps, no new task is created
- [ ] Dashboard API query (`SELECT * FROM background_tasks WHERE case_id = ?`) returns one entry per step with correct step_order
- [ ] Email verification links (`/verify/{task_id}`) reference the current step's task, not a previous step's task
- [ ] No duplicate step tasks created on orchestrator restart (idempotency guard)

---

## References

1. **PRD-SEQ-PROGRESSION-001**: Sequence advancement logic
2. **PRD-DASHBOARD-AUDIT-001**: Dashboard timeline display
3. **SD-SEQ-PERSTEP-TASKS-001**: Full solution design with technical details
4. **File**: `prefect_flows/flows/verification_orchestrator.py` (lines 426-531)
5. **File**: `utils/background_task_helpers.py` (lines 162-280)
6. **File**: `prefect_flows/flows/tasks/followup_scheduler.py` (lines 23-106)
7. **File**: `prefect_flows/flows/tasks/process_result.py` (lines 220-270)

---

**Research Complete** - Findings confirm the Solution Design's approach is correct and aligns with existing code patterns in the codebase.
