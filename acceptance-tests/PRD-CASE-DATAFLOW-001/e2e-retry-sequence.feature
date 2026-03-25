Feature: PRD-CASE-DATAFLOW-001 Retry Sequence -- Second Email
  As an AgenCheck operator
  I want the system to send a follow-up email when the first goes unanswered
  So that verification attempts are automatically retried per the sequence config

  Background:
    Given the feature branch "feature/PRD-CASE-DATAFLOW-001" is active
    And all services are running (backend, frontend, Prefect worker, PostgreSQL)
    And Prefect is in live mode (PREFECT_DISPATCH_MODE is NOT local_mock)
    And LiveKit Docker REDIS_URL points to local Prefect Redis

  Scenario: Create case and let first email go unanswered
    Given I submit a new case via the Dashboard with:
      | Employer Name  | RetryTest Corp        |
      | Contact Email  | bjorn@agencheck.com   |
      | Contact Phone  | +61404236990          |
      | Position       | QA Engineer           |
    Then a background_task should be created with:
      | action_type            | email_attempt |
      | current_sequence_step  | 1             |
    And a verification email should be sent to bjorn@agencheck.com
    And verification_tokens should have status="active"

  Scenario: Second email triggered after first email unanswered
    Given the first background_task has status="completed" or "timeout"
    And the verification was NOT submitted (no FORM_SUBMITTED event)
    When the Prefect worker advances to the next sequence step
    Then a new background_task should be created with:
      | previous_task_id       | <original_task_id>           |
      | current_sequence_step  | 2                            |
      | action_type            | email_attempt                |
      | sequence_id            | <same_sequence_id>           |
      | sequence_version       | <same_version>               |
    And the original background_task.next_task_id should point to the new task
    And a new row should exist in "verification_tokens" for the new task
    And a second email should be sent to bjorn@agencheck.com
    And the second email should contain a new /verify?token=<new_jwt> link
    And the new background_task.prefect_flow_run_id should be a new UUID
    And the new background_task.sla_due_at should be recalculated from now + 48 hours
