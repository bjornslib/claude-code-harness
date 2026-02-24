@epic1 @call-dispatch @prd-prefect-dispatch-001
Feature: Move Call Dispatch Into Prefect Flow

  All voice call dispatch must go through the Prefect voice_verification_flow
  pipeline. The scheduler must no longer dispatch calls directly. The flow's
  wait_for_stream_event consumer must be active when the call completes.

  # Confidence Scoring Guide:
  # 0.0 — Scheduler still dispatches calls directly, no change
  # 0.5 — Dispatch moved to Prefect but consumer timing not fixed, or tests broken
  # 1.0 — Full pipeline working: flow dispatches, consumer catches event, PostCallProcessor runs

  Scenario: Scheduler no longer dispatches calls directly
    Given the scheduler_service.py poll_cycle method
    When a pending task is found
    Then dispatch_to_voice_agent() is NOT called
    And only create_prefect_flow_run() is invoked
    # Evidence: No call to dispatch_to_voice_agent or dispatch_work_history_call in poll_cycle/claim_and_process_task
    # Red flag: dispatch_to_voice_agent still called conditionally or as fallback

  Scenario: voice_verification_flow dispatches the call
    Given a Prefect flow run for voice_verification_flow
    When the flow starts at the scheduled business hour
    Then dispatch_livekit_call task initiates the SIP call
    And wait_for_stream_event starts listening AFTER dispatch within the same execution
    # Evidence: Flow task ordering: prepare_call → dispatch_livekit_call → wait_for_stream_event
    # Red flag: dispatch and wait tasks run in separate flow runs or with a gap

  Scenario: Business hours scheduling preserved
    Given a task created at 7 PM AEDT (outside business hours)
    When create_prefect_flow_run is called
    Then the flow run is scheduled for 9 AM AEDT next business day
    And calculate_next_business_hour logic is unchanged
    # Evidence: prefect_bridge.py still calls calculate_next_business_hour
    # Red flag: Business hours logic modified or bypassed

  Scenario: wait_for_stream_event catches post-call event
    Given the flow has dispatched a call via dispatch_livekit_call
    And the voice agent publishes a post_call_ready event to Redis Stream
    When wait_for_stream_event polls the stream
    Then the event is caught and processing continues to process_post_call
    # Evidence: wait_for_stream_event returns the stream message with task_id matching dispatch
    # Red flag: Timeout without receiving event in mock or local testing

  Scenario: local_mock mode end-to-end completion
    Given PREFECT_DISPATCH_MODE=local_mock
    When a test task is created and the flow runs
    Then the full pipeline completes: prepare → dispatch → wait → process → result
    And no errors are logged
    # Evidence: Flow run in Prefect UI shows COMPLETED state
    # Red flag: Flow stuck at PENDING or FAILED

  Scenario: Existing tests pass without modification
    Given the existing unit and integration test suites
    When all tests are executed
    Then all previously-passing tests still pass
    # Evidence: pytest output shows same pass count as before changes
    # Red flag: Test failures in voice_verification or scheduler test modules

  Scenario: Redis consumer group exists before flow starts
    Given the voice-pool Prefect worker
    When the worker starts or a flow run begins
    Then the Redis consumer group for post_call_ready stream exists
    # Evidence: ensure_consumer_group call in flow startup or worker init
    # Red flag: XREADGROUP fails with "NOGROUP" error
