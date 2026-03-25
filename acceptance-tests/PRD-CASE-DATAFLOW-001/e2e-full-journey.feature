Feature: PRD-CASE-DATAFLOW-001 Full Journey -- Submit, Verify, Confirm
  As an AgenCheck operator
  I want to submit a work history check and complete it through the verification form
  So that the entire pipeline from frontend to outcome is validated

  Background:
    Given the feature branch "feature/PRD-CASE-DATAFLOW-001" is active
    And the backend server is running
    And the frontend dev server is running
    And PostgreSQL localhost:5434 is available
    And Prefect worker is running (PREFECT_DISPATCH_MODE must be live, never mock)
    And LiveKit server Docker container has REDIS_URL pointing to local Prefect Redis

  # === Pre-requisites ===

  Scenario: Browser automation is functional
    When I load "https://www.linkedin.com" in Claude-in-Chrome
    Then the page should load successfully
    And I should see LinkedIn content

  Scenario: User is logged into AgenCheck dashboard
    When I navigate to the AgenCheck dashboard URL
    Then I should see the Clerk login page or the dashboard
    # Manual step: User logs in via AskUserQuestion if not already authenticated

  # === Step 1: Frontend Form Submission ===

  Scenario: Submit new case from Dashboard
    Given I am logged into the AgenCheck dashboard
    When I navigate to "/checks-dashboard"
    And I click the "+ New Case" button
    Then I should see the new case form at "/checks-dashboard/new"

    When I fill in the form with:
      | Field              | Value                          |
      | First Name         | Test                           |
      | Last Name          | Candidate                      |
      | Position           | Senior Developer               |
      | Start Date         | 2021-03-01                     |
      | End Date           | 2024-12-31                     |
      | Employment Type    | full_time                      |
      | Employer Name      | TestCorp Pty Ltd               |
      | Employer Country   | Australia                      |
      | Contact Email      | bjorn@agencheck.com            |
      | Contact Phone      | +61404236990                   |
      | Contact Name       | Bjorn Verifier                 |
      | Location           | australia                      |
      | Phone Type         | direct_contact                 |
      | Salary checkbox    | checked                        |
      | Salary Amount      | 120000                         |
    And I submit the form
    Then I should be redirected to "/checks-dashboard?checkCreated=1"

  # === Step 2: Database Validation ===

  Scenario: All database records created correctly
    Given a case was submitted via the frontend form
    Then a new row should exist in "verification_subjects" with:
      | first_name | Test      |
      | last_name  | Candidate |
    And a new row should exist in "cases" with:
      | case_type                | employment    |
      | status                   | pending       |
      | verification_subject_id  | <subject_id>  |
    And cases.verification_metadata JSONB should contain:
      | employer.employer_company_name | TestCorp Pty Ltd |
      | employer.country_code          | AU               |
      | employment.position_title      | Senior Developer |
      | employment.salary_amount       | 120000           |
      | employment.salary_currency     | AUD              |
      | employment.start_date          | 2021-03-01       |
      | employment.end_date            | 2024-12-31       |
      | verify_fields.salary           | true             |
    And a new row should exist in "background_tasks" with:
      | task_type     | work_history       |
      | status        | started            |
      | case_id       | <case_id>          |
      | action_type   | email_attempt      |
    And background_tasks.context_data JSONB should contain candidate and employer details
    And a new row should exist in "university_contacts" with:
      | entity_type    | employer           |
      | employer_name  | TestCorp Pty Ltd   |
      | phone          | +61404236990       |
      | email          | bjorn@agencheck.com|

  # === Step 3: SLA and Sequence Resolution ===
  # Note: work_history SLA = 48 hours. Sequence has multi-channel steps:
  # Step 1: initial_email (0h delay) + initial_call (0h)
  # Step 2: email_reminder (0.08h) + first_retry voice (2h)
  # Step 3: second_retry voice (4h) + email_reminder_2 (0.08h)
  # Step 4: final_attempt voice (24h)

  Scenario: SLA correctly resolved for work_history check
    Given the background_task was created
    Then background_tasks.sla_due_at should be ~48 hours from created_at
    And background_tasks.check_type_config_id should reference check_types.name="work_history"
    And background_tasks.sequence_id should reference a valid background_check_sequence
    And background_tasks.sequence_version should be >= 1
    And background_tasks.current_sequence_step should be 1
    And background_tasks.action_type should be "email_attempt"

  # === Step 4: Prefect Workflow Created ===

  Scenario: Prefect flow run created with correct parameters
    Given the SLA was resolved
    Then background_tasks.prefect_flow_run_id should be a valid UUID
    And background_tasks.prefect_deployment_name should be "verification-orchestrator/verification-orchestrator"
    And background_tasks.prefect_scheduled_start should be approximately now (email = immediate)

  # === Step 5: Email Sent to Verifier ===

  Scenario: Verification email dispatched
    Given the Prefect worker has executed the flow
    Then a row should exist in "verification_tokens" with:
      | case_id   | <case_id>  |
      | status    | active     |
    And a row should exist in "email_events" with:
      | case_id     | <case_id>           |
      | to_email    | bjorn@agencheck.com |
      | event_type  | sent                |
    And the email should contain a /verify?token=<jwt> link

  # === Step 6: Verifier Opens Link and Fills Form ===

  Scenario: Verifier confirms all fields via /verify-check
    Given bjorn@agencheck.com received the verification email
    When the verifier opens the /verify-check/<task_id> link in a browser
    Then the page should load with:
      | Candidate Name | Test Candidate   |
      | Company        | TestCorp Pty Ltd |
      | Position       | Senior Developer |
      | Start Date     | 2021-03-01       |
      | End Date       | 2024-12-31       |
      | Salary         | 120000 AUD       |
    And the verify_fields checkboxes should show salary as selected
    And a LiveKit chat agent should be connected

    When the verifier enters chat message "I can confirm this person worked here"
    Then the chat agent should respond acknowledging the verification

    When the verifier fills in was_employed=true
    And confirms all verification fields as matching
    And enters verifier name as "John Doe"
    And submits the verification form
    Then a FORM_SUBMITTED event should be published via LiveKit

  # === Step 7: sub_threads Stored with background_task_id ===

  Scenario: LiveKit sub_threads correctly linked to background_task
    Given the verification form was submitted
    Then a new row should exist in "sub_threads" with:
      | background_task_id | <task_uuid>  |
      | role               | agent        |
    And sub_threads.thread_id should reference a valid thread
    And sub_threads.all_messages JSONB should contain the chat exchange
    And sub_threads.background_task_id should match the background_tasks.task_id UUID

  # === Step 8: PostCheckProcessor Interprets Outcome ===

  Scenario: PostCheckProcessor correctly validates the outcome
    Given the FORM_SUBMITTED event was processed
    Then cases.verification_results JSONB should contain:
      | was_employed       | true                    |
      | employment_status  | verified                |
      | confidence         | >= 0.8                  |
    And verification_results.verified_data should contain:
      | field          | match |
      | position_title | true  |
      | start_date     | true  |
      | end_date       | true  |
      | salary         | true  |
    And verification_results.verifier should contain:
      | name | John Doe |
    And background_tasks.status should be "completed"
    And cases.status should be "completed" or "verified"
