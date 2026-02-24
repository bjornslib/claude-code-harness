@epic4 @catch-up-poller @prd-prefect-dispatch-001
Feature: Catch-Up Poller for Orphaned call_scheduled Tasks

  The catch-up poller must detect tasks stuck at call_scheduled status
  where the call completed but PostCallProcessor never ran, and recover
  them by checking S3 for transcripts and running PostCallProcessor.

  # Confidence Scoring Guide:
  # 0.0 — No catch-up mechanism exists for call_scheduled tasks
  # 0.5 — Query exists but S3 check or PostCallProcessor invocation is missing/broken
  # 1.0 — Full pipeline: detect → S3 prefix list → download → PostCallProcessor → status update

  Scenario: Detect call_scheduled tasks older than threshold
    Given a background_task with status "call_scheduled"
    And updated_at is more than 30 minutes ago
    When the catch-up poller runs
    Then the task is included in the catch-up candidate set
    # Evidence: SQL query uses "WHERE status = 'call_scheduled' AND updated_at < NOW() - INTERVAL '30 minutes'"
    # Red flag: Query only checks status='pending' (existing catch_up_poller.py behavior)

  Scenario: S3 transcript found triggers PostCallProcessor
    Given a call_scheduled task with customer_id=32 and room_name "scheduler-107-166a7bf7"
    And an S3 object exists at "customers/32/calls/scheduler-107-166a7bf7/transcript.json"
    When the catch-up poller processes this task
    Then the transcript is downloaded from S3
    And PostCallProcessor is invoked with the transcript content
    And the task status transitions to a final state
    # Evidence: S3 prefix listing at "customers/{customer_id}/calls/scheduler-{task_id}-*/"
    # Red flag: Uses exact key lookup instead of prefix listing (misses wildcard segment)

  Scenario: No S3 transcript logs WARNING and retries later
    Given a call_scheduled task with no S3 transcript at the expected path
    When the catch-up poller processes this task
    Then a WARNING log is emitted with the task ID and age
    And the task status remains "call_scheduled" for future retry
    And no PostCallProcessor invocation occurs
    # Evidence: Logger.warning with task_id, catch_up_attempted_at metadata updated
    # Red flag: Task silently skipped or moved to failed without transcript

  Scenario: Idempotency guard prevents double processing
    Given a call_scheduled task that is being processed by the catch-up poller
    And another process transitions the task to "completed" during processing
    When PostCallProcessor would be invoked
    Then the idempotency guard re-checks task status
    And processing is skipped because status is no longer "call_scheduled"
    # Evidence: Re-query of task status immediately before PostCallProcessor invocation
    # Red flag: No re-check, or FOR UPDATE SKIP LOCKED not used on the initial query

  Scenario: FOR UPDATE SKIP LOCKED prevents concurrent processing
    Given two catch-up poller instances running concurrently
    And both detect the same call_scheduled task
    When both attempt to process the task
    Then only one succeeds due to FOR UPDATE SKIP LOCKED
    And the other skips the task without error
    # Evidence: SQL query includes FOR UPDATE SKIP LOCKED clause

  Scenario: Catch-up poller registered as scheduled Prefect deployment
    Given the catch-up poller is deployed
    Then it is registered as a Prefect deployment running every 15 minutes
    And it runs on the voice-pool work pool
    # Evidence: register_deployments.py includes catch-up schedule, cron="*/15 * * * *"
    # Red flag: Runs as a standalone script or cron job outside Prefect

  Scenario: Recovery of existing 34 stuck tasks
    Given 34 tasks are currently stuck at call_scheduled status
    When the catch-up poller runs for the first time after deployment
    Then tasks with S3 transcripts are recovered via PostCallProcessor
    And tasks without transcripts are logged at WARNING
    And the total stuck count decreases significantly
    # Evidence: Manual verification that recovered task count > 0
    # Red flag: Zero tasks recovered on first run
