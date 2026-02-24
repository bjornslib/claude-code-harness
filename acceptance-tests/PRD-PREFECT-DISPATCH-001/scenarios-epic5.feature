@epic5 @scheduler-deprecation @prd-prefect-dispatch-001
Feature: Scheduler Deprecation

  Once Epics 1-4 are validated, the scheduler service is completely removed.
  Redis Stream becomes the sole event transport. No scheduler references remain.

  # Confidence Scoring Guide:
  # 0.0 — Scheduler still exists and is running
  # 0.5 — Scheduler directory deleted but references remain or pg_notify fallback still active
  # 1.0 — Clean removal: directory deleted, no references, pg_notify fallback removed, CI passes

  Scenario: scheduler directory deleted from codebase
    Given the agencheck-support-agent directory
    When the scheduler/ subdirectory is checked
    Then it does not exist
    # Evidence: ls scheduler/ returns "No such file or directory"
    # Red flag: scheduler/ still exists, even if "deprecated" comments added

  Scenario: No imports or references to scheduler_service remain
    Given the entire agencheck codebase
    When searched for "scheduler_service" or "from scheduler" imports
    Then zero active references are found
    # Evidence: grep -r "scheduler_service\|from scheduler" returns no results in .py files
    # Red flag: Import references in __init__.py, start_services.sh, or docker-compose

  Scenario: pg_notify fallback removed from voice agent
    Given agent.py's send_post_call_notify function
    When the function is examined
    Then only Redis Stream (send_post_call_to_stream) is used
    And pg_notify code path is removed
    # Evidence: No pg_notify or asyncpg.connect in send_post_call_notify
    # Red flag: pg_notify code still present even if commented out

  Scenario: Prefect worker health checks replace scheduler health
    Given the infrastructure configuration (docker-compose, Railway)
    When the scheduler service definition is checked
    Then it has been removed from docker-compose.prefect.yaml
    And Prefect worker health checks are the active monitoring mechanism
    # Evidence: No scheduler service in docker-compose, voice-pool worker has health check
    # Red flag: Scheduler service still defined in docker-compose even if not started

  Scenario: CI passes with no import errors
    Given the full test suite
    When all tests are executed after scheduler removal
    Then no ImportError or ModuleNotFoundError for scheduler modules
    And all previously-passing tests still pass
    # Evidence: pytest runs clean with no scheduler-related failures
    # Red flag: Tests importing scheduler fixtures or mocking scheduler functions fail

  Scenario: No tasks stuck after scheduler removal
    Given the production environment with scheduler removed
    When monitored for 24 hours post-removal
    Then no tasks are stuck at pending for more than 15 minutes
    And no tasks are stuck at call_scheduled for more than 30 minutes
    # Evidence: DB query shows zero orphaned tasks in monitoring window
    # Red flag: Tasks accumulating at pending or call_scheduled without processing
