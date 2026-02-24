@epic3 @pg-notify @listen-reconnect @prd-prefect-dispatch-001
Feature: pg_notify LISTEN Reconnection and Heartbeat

  The scheduler's PostgreSQL LISTEN connection must be resilient to drops.
  A heartbeat detects dead connections and auto-reconnect restores the listener.

  # Confidence Scoring Guide:
  # 0.0 — No heartbeat or reconnection logic exists
  # 0.5 — Heartbeat exists but reconnection fails or has no backoff
  # 1.0 — Full resilience: heartbeat + auto-reconnect + backoff + logging + health status

  Scenario: Heartbeat detects dead LISTEN connection
    Given the scheduler has an active LISTEN connection
    When the connection drops silently
    Then the heartbeat SELECT 1 query fails within 60 seconds
    And the connection is marked as dead
    # Evidence: _heartbeat_listener coroutine running every 30s, SELECT 1 query
    # Red flag: No heartbeat coroutine, or interval > 60s

  Scenario: Auto-reconnect with exponential backoff
    Given the LISTEN connection has been detected as dead
    When reconnection is attempted
    Then exponential backoff is used starting at 1s up to max 60s
    And LISTEN is re-established on both channels (interpretation_ready, post_call_ready)
    # Evidence: Backoff factor=2, start=1s, max=60s in reconnection loop
    # Red flag: Fixed retry interval or no max backoff cap

  Scenario: Reconnection events logged at WARNING
    Given a LISTEN connection drop and reconnection attempt
    When the reconnection succeeds
    Then a WARNING log includes connection metadata (attempt count, elapsed time)
    And a successful reconnect is logged at INFO level
    # Evidence: logger.warning with attempt count, logger.info on success
    # Red flag: Reconnection events not logged or logged at DEBUG only

  Scenario: No silent event loss during brief disconnection
    Given the LISTEN connection drops for 5 seconds
    And a pg_notify event is sent during the disconnect
    When the connection is re-established
    Then events sent during the gap are not silently lost
    # Note: pg_notify is inherently fire-and-forget; events during disconnect ARE lost.
    # The catch-up poller (Epic 4) is the safety net for this gap.
    # Score 1.0 if: reconnection is fast AND catch-up poller covers the gap
    # Score 0.5 if: reconnection works but no catch-up acknowledgment
    # Red flag: Reconnection takes > 5 minutes or no catch-up safety net

  Scenario: Health check reflects LISTEN status
    Given the scheduler health check endpoint
    When the LISTEN connection is active
    Then the health response includes listener_active: true
    When the LISTEN connection is dead and reconnecting
    Then the health response includes listener_active: false
    # Evidence: Health endpoint at port 8001 includes listener status field
    # Red flag: Health check does not reflect LISTEN state
