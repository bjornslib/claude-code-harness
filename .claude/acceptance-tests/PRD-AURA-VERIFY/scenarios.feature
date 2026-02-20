# PRD-AURA-VERIFY: Aura Call Form - Create Verification Task
# Blind acceptance tests for guardian validation
# These tests are stored in claude-harness-setup, NOT in the implementation repo

Feature: F1 - Employer Details Card
  The /aura-call page should have an 'Employer Details' card section
  matching the existing Candidate Details styling pattern.

  @employer_details_card_renders
  Scenario: Employer Details card is visible on /aura-call page
    Given the user navigates to /aura-call
    When the page loads
    Then an "Employer Details" card section is visible
    And the card has a Building2 or similar icon in the header
    And the card uses white background with border (matching Candidate Details)
    And the card uses uppercase tracking-wider header text

    # Confidence Scoring Guide:
    # 1.0 — Card exists with correct styling, icon, header text "EMPLOYER DETAILS"
    # 0.7 — Card exists but styling doesn't exactly match Candidate Details pattern
    # 0.5 — Employer fields exist but not in a dedicated card section
    # 0.3 — Some employer fields present but scattered, no card grouping
    # 0.0 — No employer details section exists

    # Evidence to check:
    # - Browse to /aura-call in Chrome, visually inspect
    # - Check VoiceInterface.tsx or page.tsx for employer card JSX
    # - Verify className matches: bg-white border border-gray-200 rounded-xl p-6

    # Red flags:
    # - Employer fields mixed into Candidate Details card
    # - No visual separation between candidate and employer info
    # - Missing header/icon

  @employer_details_fields_present
  Scenario: Employer Details card contains all required fields
    Given the user is on the /aura-call page
    When the Employer Details card is visible
    Then the following fields are present:
      | Field                  | Type   | Required |
      | Company Name           | text   | yes      |
      | Website                | url    | no       |
      | Country                | text   | yes      |
      | City                   | text   | no       |
      | Contact Person Name    | text   | yes      |
      | Contact Person Phone   | tel    | yes      |

    # Confidence Scoring Guide:
    # 1.0 — All 6 fields present with correct types and labels
    # 0.8 — 5 of 6 fields present
    # 0.6 — 4 of 6 fields present (must include Company Name + Phone)
    # 0.3 — Fewer than 4 fields or missing Company Name/Phone
    # 0.0 — No employer fields at all

    # Evidence to check:
    # - Read the component source for input elements
    # - Browse to /aura-call and check each field exists
    # - Verify field labels and placeholder text

  @contact_person_name_moved
  Scenario: Contact Person Name is moved into Employer Details
    Given the user is on the /aura-call page
    When viewing the form layout
    Then "Contact Person Name" is inside the Employer Details card
    And "Contact Person Name" is NOT in its previous location (call configuration area)

    # Confidence Scoring Guide:
    # 1.0 — Contact Person Name is in Employer Details, removed from old location
    # 0.7 — Contact Person Name appears in Employer Details but also remains in old spot
    # 0.3 — Contact Person Name still only in old location
    # 0.0 — Contact Person Name field is missing entirely

    # Evidence to check:
    # - Search for contactPersonName state usage in JSX
    # - Verify the field renders within the employer card div
    # - Verify it does NOT render in the call configuration section

Feature: F2 - Create Task Button + API Integration
  Replace the 'Make Call' button with 'Create Task' that calls POST /api/v1/verify.

  @create_task_button_exists
  Scenario: Create Task button replaces Make Call
    Given the user is on the /aura-call page
    When the form is filled with valid data
    Then a "Create Task" button is visible (or "Submit Verification" or similar)
    And the button is prominent (primary color, full width or centered)
    And the old "Make Call" / "Start Call" button is replaced or has alternative mode

    # Confidence Scoring Guide:
    # 1.0 — Create Task button exists, styled prominently, replaces Make Call for this mode
    # 0.7 — Button exists but coexists with Make Call (dual-mode is OK if clearly separated)
    # 0.5 — Button exists but not well styled or hard to find
    # 0.3 — Submit mechanism exists but is not a visible button (e.g., auto-submit)
    # 0.0 — No Create Task button; only Make Call remains

    # Evidence to check:
    # - Browse to /aura-call, look for button text
    # - Read page.tsx or VoiceInterface.tsx for button JSX
    # - Check onClick handler references /verify API

  @create_task_calls_verify_api
  Scenario: Create Task button calls POST /api/v1/verify
    Given the form is filled with:
      | Field              | Value                          |
      | First Name         | Marcus                         |
      | Last Name          | Rivera                         |
      | Company Name       | DataStream Analytics Pty Ltd   |
      | Country            | Australia                      |
      | Contact Phone      | +61404236990                   |
      | Check Type         | work_history                   |
    When the user clicks "Create Task"
    Then a POST request is sent to /api/v1/verify (or proxied endpoint)
    And the request body contains:
      | Path                      | Value                        |
      | candidate.first_name      | Marcus                       |
      | candidate.last_name       | Rivera                       |
      | employer.company_name     | DataStream Analytics Pty Ltd |
      | phone_numbers[0]          | +61404236990                 |
      | check_type                | work_history                 |
    And the response status is 201

    # Confidence Scoring Guide:
    # 1.0 — POST /verify called with correct payload structure, 201 response
    # 0.7 — API called but payload structure slightly different (e.g., flat vs nested)
    # 0.5 — API called but wrong endpoint or wrong method
    # 0.3 — Some API integration exists but doesn't match /verify schema
    # 0.0 — No API call made from Create Task button

    # Evidence to check:
    # - Network tab in Chrome showing POST request
    # - Read the onClick handler code
    # - Check the API route handler (may proxy to localhost:8001)
    # - Verify payload matches /api/v1/verify expected schema

    # Red flags:
    # - Calling /api/livekit/token instead of /verify
    # - Missing required fields in payload
    # - Frontend-only mock (no actual backend call)

  @create_task_shows_success
  Scenario: Success feedback after task creation
    Given the form is filled with valid data
    When the user clicks "Create Task"
    And the API returns 201
    Then a success message is displayed (toast, banner, or inline)
    And the task_id from the response is shown to the user

    # Confidence Scoring Guide:
    # 1.0 — Clear success message with task_id displayed
    # 0.7 — Success message without task_id
    # 0.5 — Page navigates or changes state but no explicit success message
    # 0.3 — Console log only, no visual feedback
    # 0.0 — No feedback at all after submission

  @create_task_handles_errors
  Scenario: Error handling for failed task creation
    Given the form is filled with invalid data (e.g., missing required fields)
    When the user clicks "Create Task"
    Then appropriate error messages are shown
    And the form does not clear on error
    And the user can correct and retry

    # Confidence Scoring Guide:
    # 1.0 — Clear error messages, form preserved, retry works
    # 0.7 — Error shown but generic (not field-specific)
    # 0.5 — Error caught but only in console
    # 0.3 — Error crashes the page or shows unhandled exception
    # 0.0 — No error handling at all

Feature: F3 - Full E2E: Form -> API -> Prefect Flow
  Complete chain from browser form to Prefect flow execution.

  @e2e_form_to_prefect_flow
  Scenario: Submitting form creates Prefect flow that dispatches call
    Given Docker services are running (app-server, prefect-worker, prefect-server, redis, postgres)
    And the user navigates to /aura-call in Chrome
    When the user fills the form with:
      | Field              | Value                          |
      | First Name         | Marcus                         |
      | Last Name          | Rivera                         |
      | Company Name       | DataStream Analytics Pty Ltd   |
      | Country            | Australia                      |
      | City               | Melbourne                      |
      | Contact Phone      | +61404236990                   |
    And clicks "Create Task"
    Then the API returns 201 with a task_id
    And within 30 seconds, a Prefect flow run is created with state RUNNING or COMPLETED
    And the flow run contains task_runs: prepare_call (COMPLETED), dispatch_livekit_call (COMPLETED or RUNNING)
    And the background_tasks table has prefect_flow_run_id populated

    # Confidence Scoring Guide:
    # 1.0 — Full chain works: form -> 201 -> Prefect flow -> tasks executing -> DB updated
    # 0.8 — Flow created but some tasks fail (e.g., dispatch fails due to no voice agent)
    # 0.6 — API returns 201 and flow is SCHEDULED but not yet RUNNING
    # 0.4 — API returns 201 but no Prefect flow is created (bridge not triggered)
    # 0.2 — API returns error or form submission fails
    # 0.0 — Nothing works

    # Evidence to check:
    # - Chrome screenshot showing form filled + success message
    # - API response body with task_id
    # - Prefect API: curl -s -X POST http://localhost:4200/api/flow_runs/filter
    # - DB: SELECT prefect_flow_run_id FROM background_tasks WHERE case_id = <new>
    # - Docker logs: docker compose logs app-server --tail 20

    # Red flags:
    # - Form calls /api/livekit/token instead of /verify
    # - Bridge not triggered (flow created manually or not at all)
    # - background_tasks missing prefect metadata

Feature: F4 - Data Mapping (Form Fields -> API Payload)
  Ensure form fields correctly map to /verify API schema.

  @data_mapping_candidate
  Scenario: Candidate fields map correctly
    Given form data with First Name="Alice", Last Name="Johnson"
    When submitted to /verify API
    Then payload contains candidate.first_name="Alice" and candidate.last_name="Johnson"

    # Confidence Scoring Guide:
    # 1.0 — All candidate fields correctly nested under 'candidate' key
    # 0.5 — Fields present but flat (not nested under candidate)
    # 0.0 — Candidate fields missing from payload

  @data_mapping_employer
  Scenario: Employer fields map correctly
    Given form data with Company Name="Acme Corp", Country="Australia", City="Sydney"
    When submitted to /verify API
    Then payload contains employer.company_name="Acme Corp"

    # Confidence Scoring Guide:
    # 1.0 — Employer fields correctly nested under 'employer' key
    # 0.5 — Fields present but under wrong key
    # 0.0 — Employer fields missing

  @data_mapping_phone_numbers
  Scenario: Contact phone maps to phone_numbers array
    Given form data with Contact Phone="+61404236990"
    When submitted to /verify API
    Then payload contains phone_numbers=["+61404236990"] as an array

    # Confidence Scoring Guide:
    # 1.0 — Phone number in phone_numbers array format
    # 0.5 — Phone number present but as string not array
    # 0.0 — Phone number missing from payload

Feature: F5 - UI Polish + Validation
  Form validation and responsive design.

  @form_validation_required_fields
  Scenario: Required fields are validated before submission
    Given the user is on /aura-call with empty form
    When clicking "Create Task" without filling required fields
    Then required fields are highlighted (border color change or error text)
    And submission is prevented

    # Confidence Scoring Guide:
    # 1.0 — Visual validation on required fields, submission blocked
    # 0.5 — Submission blocked but no visual indicators
    # 0.3 — Validation exists but allows empty submission
    # 0.0 — No validation at all

  @responsive_layout
  Scenario: Form is responsive on mobile and desktop
    Given the user views /aura-call on desktop (1280px+)
    Then Employer Details card shows fields in 2-column grid
    When the viewport is resized to mobile (< 768px)
    Then fields stack to single column

    # Confidence Scoring Guide:
    # 1.0 — Responsive grid (2-col desktop, 1-col mobile) matching Candidate Details
    # 0.7 — Responsive but different breakpoints or column count
    # 0.5 — Desktop layout works but mobile is broken
    # 0.0 — No responsive behavior
