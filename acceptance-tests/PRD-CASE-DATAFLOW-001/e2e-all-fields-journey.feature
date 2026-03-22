Feature: PRD-CASE-DATAFLOW-001 All Fields Journey -- Submit, Verify, Confirm with ALL optional fields
  As an AgenCheck operator
  I want to submit a work history check with ALL possible verification fields enabled
  So that the entire pipeline handles every field type correctly end-to-end

  Background:
    Given the feature branch "feature/PRD-CASE-DATAFLOW-001" is active
    And the backend server is running (Docker app-server on port 8001)
    And the frontend dev server is running locally on port 5002
    And PostgreSQL localhost:5434 is available
    And Prefect worker is running (PREFECT_DISPATCH_MODE must be live, never mock)
    And LiveKit worker is running locally via uv (LIVEKIT_AGENT_NAME=check-agent-local)

  # === Pre-requisites ===

  Scenario: Browser automation and authentication ready
    When I load "https://www.linkedin.com" in Claude-in-Chrome
    Then the page should load successfully
    When I navigate to the AgenCheck dashboard
    Then I should be logged in (or AskUserQuestion to log in via Clerk)

  # === Step 1: Frontend Form Submission with ALL fields ===

  Scenario: Submit new case with ALL verification fields enabled
    Given I am logged into the AgenCheck dashboard
    When I navigate to "/checks-dashboard/new"
    Then I should see the new case form

    When I fill in the candidate details:
      | Field              | Value                          |
      | First Name         | Maximilian                     |
      | Middle Name        | James                          |
      | Last Name          | AllFields                      |
      | Position           | VP of Engineering              |
      | Start Date         | 2019-06-15                     |
      | End Date           | 2024-09-30                     |
      | Employment Type    | full_time                      |
      | Employment Arrange | agency                         |
      | Agency Name        | TechStaff Solutions            |

    And I fill in the employer details:
      | Field              | Value                          |
      | Employer Name      | AllFields Corp International   |
      | Website            | allfields-corp.com.au          |
      | Country            | Australia                      |
      | City               | Melbourne                      |

    And I add the primary contact:
      | Field              | Value                          |
      | Contact Name       | Sarah Chen                     |
      | Contact Email      | bjorn@agencheck.com            |
      | Contact Phone      | +61404236990                   |

    And I enable ALL additional verification points:
      | Verification Point   | Enabled |
      | Salary               | true    |
      | Supervisor           | true    |
      | Employment Type      | true    |
      | Rehire Eligibility   | true    |
      | Reason for Leaving   | true    |

    And I fill in the salary details:
      | Field              | Value   |
      | Salary Currency    | AUD     |
      | Salary Amount      | 185000  |

    And I submit the form
    Then I should be redirected to "/checks-dashboard?checkCreated=1"

  # === Step 2: Database Validation — ALL fields stored ===

  Scenario: All database records created with ALL fields
    Given a case was submitted via the frontend form
    Then a new row should exist in "verification_subjects" with:
      | first_name  | Maximilian |
      | last_name   | AllFields  |
    And a new row should exist in "cases" with:
      | case_type                | employment    |
      | status                   | pending       |
    And cases.verification_metadata JSONB should contain:
      | employer.employer_company_name | AllFields Corp International |
      | employer.country_code          | AU                           |
      | employment.position_title      | VP of Engineering            |
      | employment.salary_amount       | 185000                       |
      | employment.salary_currency     | AUD                          |
      | employment.start_date          | 2019-06-15                   |
      | employment.end_date            | 2024-09-30                   |
      | employment.employment_type     | full_time                    |
      | employment.employment_arrangement | agency                    |
      | verify_fields.salary              | true                     |
      | verify_fields.employment_type     | true                     |
      | verify_fields.eligibility_for_rehire | true                  |
    And a new row should exist in "background_tasks" with:
      | task_type     | work_history       |
      | status        | started            |
      | action_type   | email_attempt      |
    And a new row should exist in "university_contacts" with:
      | entity_type    | employer                     |
      | employer_name  | AllFields Corp International |
      | phone          | +61404236990                 |
      | email          | bjorn@agencheck.com          |

  # === Step 3: SLA and Prefect ===

  Scenario: SLA and Prefect flow created correctly
    Given the background_task was created
    Then background_tasks.sla_due_at should be ~48 hours from created_at
    And background_tasks.prefect_flow_run_id should be a valid UUID
    And background_tasks.prefect_deployment_name should be "verification-orchestrator/verification-orchestrator"
    And background_tasks.current_sequence_step should be 1

  # === Step 4: Verifier Opens /verify-check — ALL fields displayed ===

  Scenario: Verifier sees ALL verification fields on /verify-check page
    Given the verifier opens the /verify-check/<task_id> link in a browser
    Then the page should load with candidate info:
      | Candidate Name | Maximilian AllFields         |
      | Company        | AllFields Corp International |
      | Position       | VP of Engineering            |

    And the verification form should show ALL these fields for confirmation:
      | Field Name             | Claimed Value     | Type     |
      | was_employed           | (Yes/No question) | yesno    |
      | start_date             | 2019-06-15        | date     |
      | end_date               | 2024-09-30        | date     |
      | position_title         | VP of Engineering | text     |
      | employment_type        | full_time         | select   |
      | salary                 | AUD 185,000       | currency |
      | supervisor_name        | (inquiry field)   | text     |
      | eligibility_for_rehire | (Yes/No/Refused)  | yesno    |
      | reason_for_leaving     | (inquiry field)   | text     |

    And a LiveKit chat agent (check-agent-local) should be connected
    And the chat session should show "ACTIVE"

  # === Step 5: Chat interaction before form fill ===

  Scenario: Verifier chats with agent about the candidate
    When the verifier types "Yes, Max worked here. He was a great VP of Engineering."
    Then the agent should respond acknowledging the verification
    And the SSE listener should emit a DELTA update for was_employed="yes"

  # === Step 6: Verifier confirms and fills ALL fields ===

  Scenario: Verifier fills in all verification fields
    # Base fields — confirm claimed values
    When the verifier clicks "Yes" for was_employed
    And confirms start_date as "2019-06-15" (using DatePicker)
    And confirms end_date as "2024-09-30" (using DatePicker)
    And confirms position_title as "VP of Engineering"
    And confirms employment_type as "full_time" (using Select dropdown)
    And confirms salary as "AUD 185000" (using currency Select + amount Input)

    # Optional fields — these are INQUIRY type (verifier provides new info)
    And enters supervisor_name as "Dr. Angela Martinez"
    And selects eligibility_for_rehire as "Yes"
    And enters reason_for_leaving as "Relocated to Singapore for family reasons"

    # Submit
    And enters verifier name as "Sarah Chen"
    And submits the verification form
    Then the page should redirect to "/verify-call/thank-you"
    And the page should show "Submission complete"

  # === Step 7: sub_threads stored ===

  Scenario: LiveKit sub_threads correctly linked
    Given the verification form was submitted
    Then a new row should exist in "sub_threads" with:
      | background_task_id | <task_uuid> |
    And sub_threads.message_count should be >= 2 (agent greeting + verifier message)
    And sub_threads.all_messages JSONB should contain the chat exchange

  # === Step 8: PostCheckProcessor — ALL fields in outcome ===

  Scenario: PostCheckProcessor stores ALL field outcomes
    Given the FORM_SUBMITTED event was processed
    Then cases.status should be "completed"
    And cases.verification_results JSONB should contain:
      | was_employed       | true     |
      | employment_status  | verified |
      | confidence         | >= 0.8   |
    And verification_results.verifier should contain:
      | name | Sarah Chen |
    And verification_results.verified_data should contain ALL these fields:
      | field                    | claimed            | verified                                    | match |
      | start_date               | 2019-06-15         | 2019-06-15                                  | true  |
      | end_date                 | 2024-09-30         | 2024-09-30                                  | true  |
      | position_title           | VP of Engineering  | VP of Engineering                           | true  |
      | employment_type          | full_time          | full_time                                   | true  |
      | salary_amount            | 185000             | 185000                                      | true  |
      | salary_currency          | AUD                | AUD                                         | true  |
      | supervisor_name          | (none claimed)     | Dr. Angela Martinez                         | N/A   |
      | eligibility_for_rehire   | (none claimed)     | yes                                         | N/A   |
      | reason_for_leaving       | (none claimed)     | Relocated to Singapore for family reasons   | N/A   |
    And background_tasks.status should be "completed"

  # === Step 9: Verify field type rendering ===

  Scenario: shadcn components render correctly for each field type
    When reviewing the /verify-check page:
    Then start_date should use a DatePicker component (Popover + Calendar)
    And end_date should use a DatePicker component
    And employment_type should use a Select dropdown with options:
      | Full-time  |
      | Part-time  |
      | Contractor |
      | Casual     |
    And salary should show as Currency Select (AUD) + Amount Input (185000) on one line
    And eligibility_for_rehire should show Yes / No / "Refused to answer" buttons
    And supervisor_name should be a text input (inquiry field)
    And reason_for_leaving should be a text input (inquiry field)
