@journey @prd-prefect-dispatch-001 @J1
Feature: J1 — Task Creation to PostCallProcessor Completion

  End-to-end journey: a background task is created, Prefect flow dispatches
  the call, voice agent completes the call, and PostCallProcessor runs —
  all within the Prefect flow lifecycle, not through the scheduler.

  Background:
    Given the Prefect worker is running on voice-pool
    And PREFECT_DISPATCH_MODE is set to "local_mock"
    And the Redis consumer group for post_call_ready exists
    And the database is accessible at DATABASE_URL

  @smoke
  Scenario: Full pipeline — task to PostCallProcessor
    # Layer 1: Database — task creation
    When a new background_task is created with status "pending" and action_type "call_attempt"
    Then the task has a prefect_flow_run_id set (via create_prefect_flow_run)

    # Layer 2: Prefect — flow execution
    And the Prefect flow run transitions from SCHEDULED to RUNNING
    And the flow executes dispatch_livekit_call (mocked in local_mock mode)

    # Layer 3: Redis — event transport
    And the voice agent publishes a post_call_ready event to Redis Stream
    And wait_for_stream_event catches the event within 60 seconds

    # Layer 4: Processing — PostCallProcessor
    And process_post_call runs with the transcript
    And process_call_result writes the outcome to background_tasks

    # Business outcome
    Then the task status is no longer "call_scheduled"
    And verification_results on the case is NOT empty
    And the Prefect flow run reaches COMPLETED state

  @smoke
  Scenario: Catch-up poller recovers orphaned task
    # Layer 1: Database — orphaned task
    Given a background_task with status "call_scheduled" and updated_at 45 minutes ago
    And an S3 transcript exists at "customers/{customer_id}/calls/scheduler-{id}-*/transcript.json"

    # Layer 2: Prefect — catch-up execution
    When the catch-up poller flow runs
    Then it detects the orphaned task

    # Layer 3: S3 — transcript retrieval
    And it performs an S3 prefix listing for the transcript
    And the transcript is downloaded successfully

    # Layer 4: Processing — PostCallProcessor
    And PostCallProcessor is invoked with the downloaded transcript
    And the task transitions from "call_scheduled" to a final status

    # Business outcome
    Then the task is no longer stuck
    And verification_results on the case is populated
