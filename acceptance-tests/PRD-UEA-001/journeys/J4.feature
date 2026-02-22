# Journey J4: Retry Sequence Uses Dynamic Intervals + Writes Audit Trail
#
# CROSS-LAYER: Prefect Flow → Service (dynamic intervals) → PostgreSQL (audit)
#              → Template Service → Channel Dispatch → Follow-up Scheduling
# BUSINESS OUTCOME: When a voice verification attempt fails, the system schedules
#   the next retry using the interval from the DB-backed check_steps (not hardcoded
#   VOICEMAIL_BACKOFF_HOURS), records the attempt in background_tasks with sequence
#   metadata, and eventually dispatches email follow-up using text file templates.
#
# EXECUTION ENVIRONMENT:
#   Backend:  Docker app-server (feature branch) on http://localhost:8000
#   Database: Docker app-postgres on port 5434 (migration 035 applied)
#   Prefect:  Docker prefect-server on port 4200 (PREFECT_DISPATCH_MODE=local_mock)
#   Tests:    curl for API calls, docker exec psql for DB queries, code grep for source verification
#
# BLIND: This test is invisible to the S3 operator and its workers.

@journey @prd-uea-001 @J4 @prefect @db @audit
Feature: J4 — Dynamic retry intervals, audit trail, and follow-up scheduling

  Background:
    Given the backend API Docker container is running at http://localhost:8000 (feature branch)
    And PostgreSQL Docker container has migration 035 applied
    And an active work_history sequence exists for customer_id=1 with:
      | step               | max_attempts | retry_intervals   |
      | voice-verification | 5            | [2, 4, 24, 48]    |
      | email-outreach     | 3            | [24, 72, 120]     |
      | human-review       | 1            | []                |
    And PREFECT_DISPATCH_MODE=local_mock is set
    And a work_history verification case exists for customer_id=1 (case_id=X)

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 1: Dynamic retry intervals from DB config
  # ─────────────────────────────────────────────────────────────────

  @prefect @smoke
  Scenario: Failed voice attempt schedules retry using DB-backed interval, not hardcoded
    # LAYER 1: Prefect — First voice attempt fails
    When the verification_orchestrator_flow dispatches voice-verification for case_id=X
    And the voice attempt returns status=no_answer (attempt 1)

    # LAYER 2: Service — Retry scheduled with DB interval
    Then a retry task is created in background_tasks
    And the retry is scheduled for +2 hours from now (retry_intervals[0]=2, from DB config)
    And NOT +2 hours from VOICEMAIL_BACKOFF_HOURS (which is the same value but sourced differently)

    # LAYER 3: Verify the interval source
    When the source code of verification_orchestrator.py is examined
    Then retry intervals are read from the resolved check_steps (not DEFAULT_RETRY_CONFIG)
    And the indexing logic uses: interval = retry_intervals[min(attempt-1, len(retry_intervals)-1)]

    # LAYER 4: Second failure uses second interval
    When attempt 2 also returns no_answer
    Then the next retry is scheduled for +4 hours (retry_intervals[1]=4)

    When attempt 3 returns no_answer
    Then the next retry is scheduled for +24 hours (retry_intervals[2]=24)

    # Evidence Required:
    #   - grep verification_orchestrator.py for "retry_intervals" from check_steps
    #   - grep for "VOICEMAIL_BACKOFF_HOURS" — should be removed or only system fallback
    #   - SQL: SELECT scheduled_time, attempt_timestamp FROM background_tasks ORDER BY created_at
    #   - Interval between consecutive tasks matches DB config
    #
    # Confidence Scoring:
    #   0.0 — Still using hardcoded VOICEMAIL_BACKOFF_HOURS = [2, 4, 24, 48]
    #   0.3 — Code references retry_intervals but never uses them in scheduling
    #   0.5 — First retry uses DB interval but subsequent ones fall back to hardcoded
    #   0.7 — All retries use DB intervals with correct index calculation
    #   1.0 — Complete: dynamic intervals, correct indexing, overflow handling (use last interval),
    #          VOICEMAIL_BACKOFF_HOURS removed or fallback-only

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 2: Audit trail — every attempt recorded with sequence metadata
  # ─────────────────────────────────────────────────────────────────

  @db
  Scenario: Each task in background_tasks has sequence_id, sequence_version, attempt_timestamp
    Given 3 voice verification attempts have been made for case_id=X
    When the background_tasks table is queried for case_id=X
    Then at least 3 task records exist (original + 2 retries)
    And EVERY record has:
      | field             | value                                 |
      | sequence_id       | UUID matching active sequence for c=1  |
      | sequence_version  | integer >= 1                          |
      | attempt_timestamp | TIMESTAMPTZ, NOT NULL                 |
    And the sequence_id FK is valid (references background_check_sequence.id)
    And attempt_timestamps are monotonically increasing

    # LAYER: Code — Verify create_retry_task passes sequence metadata
    When the source code of utils/background_task_helpers.py is examined
    Then create_retry_task() accepts sequence_id, sequence_version, and attempt_timestamp parameters
    And all call sites in Prefect flows pass these parameters

    # Evidence Required:
    #   - SQL: SELECT sequence_id, sequence_version, attempt_timestamp FROM background_tasks WHERE case_id=X
    #   - grep background_task_helpers.py for "sequence_id" in create_retry_task signature
    #   - grep Prefect flow files for create_retry_task calls — all must include sequence params
    #
    # Confidence Scoring:
    #   0.0 — background_tasks has no new columns (migration not applied)
    #   0.2 — Columns exist but are always NULL (code never sets them)
    #   0.4 — Some code paths set sequence_id but not all (e.g., voice sets it, email doesn't)
    #   0.6 — All paths set sequence_id and sequence_version. attempt_timestamp sometimes NULL
    #   0.8 — All fields populated on every task. FK valid. Timestamps increasing
    #   1.0 — Complete audit trail: all fields populated, FK valid, indexed,
    #          queryable for audit purposes, all call sites pass metadata

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 3: Channel baton passing — voice exhausted → email dispatch
  # ─────────────────────────────────────────────────────────────────

  @prefect
  Scenario: After voice max_attempts exhausted, flow moves to email-outreach channel
    Given voice-verification has been attempted 5 times (max_attempts=5) for case_id=X
    And all 5 attempts returned no_answer/voicemail_left
    When the verification_orchestrator_flow advances to the next check_step
    Then the next channel dispatched is "email-outreach" (step 2 from check_steps)
    And the email attempt uses the template from prefect_flows/templates/work_history/email_first_contact.txt
    And the template variables are populated:
      | variable          | source                      |
      | {employer_name}   | case.employer_name           |
      | {candidate_name}  | case.candidate_name          |
      | {case_id}         | case.id                      |
      | {callback_number} | system config                |

    # Evidence Required:
    #   - verification_orchestrator.py: loop over check_steps with channel progression
    #   - channel_dispatch.py: email channel dispatches using template_service
    #   - prefect_flows/templates/work_history/email_first_contact.txt exists with variables
    #   - services/template_service.py: load_template() and render_template() functions
    #
    # Confidence Scoring:
    #   0.0 — No channel progression — only voice, never moves to email
    #   0.3 — Code references email-outreach but channel_dispatch doesn't handle it
    #   0.5 — Email dispatched but without templates (hardcoded body text)
    #   0.7 — Email uses templates, variables populated. Template service works
    #   1.0 — Complete: channel progression from DB config, template loading,
    #          variable rendering, email dispatched with correct content

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 4: Follow-up scheduler respects case status
  # ─────────────────────────────────────────────────────────────────

  @prefect @db
  Scenario: Follow-up tasks stop when case is completed or cancelled
    Given email-outreach attempt 1 has been made for case_id=X
    And a follow-up task is scheduled for +24 hours
    When the case status is changed to "completed" (employer responded)
    Then the followup_scheduler checks case status before executing
    And the scheduled follow-up is NOT dispatched (case is no longer active)

    # LAYER: Code verification
    When the source code of followup_scheduler.py is examined
    Then it contains a case status check before scheduling retries
    And it skips scheduling if case status is in ["completed", "cancelled", "closed"]

    # Evidence Required:
    #   - prefect_flows/flows/tasks/followup_scheduler.py exists
    #   - grep for "case.*status" check in the scheduler
    #   - grep for "completed" or "cancelled" in status guard
    #   - The scheduler is imported and called from verification_orchestrator.py
    #
    # Confidence Scoring:
    #   0.0 — followup_scheduler.py doesn't exist
    #   0.3 — File exists but is a stub (pass/TODO)
    #   0.5 — Scheduler works but doesn't check case status (retries continue after completion)
    #   0.7 — Case status checked, retries stop on completion. Imported in orchestrator
    #   1.0 — Complete: status guard for completed/cancelled/closed, imported and called
    #          from verification_orchestrator, tested with status transitions

  # ─────────────────────────────────────────────────────────────────
  # SCENARIO 5: Sequence metadata propagates through channel dispatch
  # ─────────────────────────────────────────────────────────────────

  @prefect @db
  Scenario: sequence_id and sequence_version flow from orchestrator through dispatch to voice flow
    When verification_orchestrator_flow dispatches voice_verification_flow for case_id=X
    Then the dispatch call includes sequence_id and sequence_version parameters

    When channel_dispatch.py routes to voice_verification_flow
    Then it passes sequence_id and sequence_version to the voice flow function

    When voice_verification_flow creates a retry task via create_retry_task
    Then it includes sequence_id, sequence_version, and attempt_timestamp

    # Evidence Required:
    #   - grep verification_orchestrator.py for "sequence_id" being passed to dispatch
    #   - grep channel_dispatch.py for "sequence_id" being passed to voice_verification_flow
    #   - grep voice_verification.py for "sequence_id" in create_retry_task call
    #   - End-to-end: orchestrator → dispatch → voice → background_tasks record
    #
    # Confidence Scoring:
    #   0.0 — sequence_id not passed from orchestrator to any downstream
    #   0.3 — Passed from orchestrator to dispatch but not to voice flow
    #   0.5 — Passed to voice flow but not included in create_retry_task call
    #   0.7 — Full chain: orchestrator → dispatch → voice → create_retry_task with metadata
    #   1.0 — Complete: metadata flows through ALL paths (voice, email, human-review),
    #          every create_retry_task call includes all 3 audit fields
