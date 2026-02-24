@epic2 @email-dispatch @prd-prefect-dispatch-001
Feature: Verify and Harden Email Dispatch via Prefect

  Email dispatch must be exclusively owned by email_outreach_flow.
  The scheduler must have zero active email dispatch code paths.

  # Confidence Scoring Guide:
  # 0.0 — Scheduler still has active email dispatch paths
  # 0.5 — Audit done but integration test missing or email flow not verified
  # 1.0 — Audit clean + email_outreach_flow verified + orchestrator routing confirmed

  Scenario: Scheduler has no active email dispatch paths
    Given the scheduler_service.py codebase
    When audited for SMTP, sendgrid, email, or outreach references
    Then zero active email dispatch code paths are found
    # Evidence: grep -r for sendgrid|smtp|email_outreach in scheduler/ shows no active dispatch
    # Red flag: Active email sending code exists in scheduler even if behind a feature flag

  Scenario: verification_orchestrator_flow routes to email correctly
    Given the verification_orchestrator_flow
    When voice verification fails or is not applicable
    Then it creates a Prefect flow run for email_outreach_flow
    And does NOT dispatch email inline
    # Evidence: Flow creates email_outreach_flow run via Prefect client, not direct sendgrid call
    # Red flag: Inline SendGrid call in orchestrator flow

  Scenario: email_outreach_flow applies business hours scheduling
    Given an email outreach task
    When the flow run is created
    Then business hours scheduling is applied via calculate_next_business_hour
    # Evidence: email_outreach_flow or its bridge uses calculate_next_business_hour
    # Red flag: Emails sent immediately regardless of business hours

  Scenario: End-to-end voice to email fallback
    Given a task where voice verification fails after max retries
    When verification_orchestrator_flow handles the fallback
    Then an email_outreach_flow run is created
    And the email flow reaches completion (in mock mode)
    # Evidence: Integration test showing voice failure → email fallback → completion
    # Red flag: No integration test covering the fallback path
