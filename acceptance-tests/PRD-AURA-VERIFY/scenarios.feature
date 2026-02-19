# PRD-AURA-VERIFY: Aura Call Form Extension — Create Task & Employer Details
#
# These scenarios are stored in the config repo (claude-harness-setup),
# NOT in the implementation repo. Operators and workers never see the
# scoring rubric. The guardian reads actual code and scores independently.
#
# Scoring: 0.0 = not implemented, 0.5 = partially done, 1.0 = fully correct
# Accept threshold: >= 0.60 weighted total
# Reject threshold: < 0.40 weighted total

# =============================================================================
# F1: Employer Details Card — New UI Section (weight: 0.30, CRITICAL)
# =============================================================================

@F1 @critical
Feature: Employer Details Card

  Background:
    Given the /aura-call page is loaded in the browser
    And the VoiceInterface component is rendered

  Scenario: S1.1 — Employer Details card exists as a distinct section
    # WHAT TO CHECK:
    #   VoiceInterface.tsx contains a new card section with header "Employer Details"
    #   The card uses the same CSS pattern as "Candidate Details":
    #     <div className="bg-white border border-gray-200 rounded-xl p-6">
    #   The card has an icon + uppercase tracking-wider header
    #
    # CONFIDENCE GUIDE:
    #   1.0 — Card exists with exact CSS class pattern, icon, and "Employer Details" header
    #   0.7 — Card exists but uses different CSS classes or missing icon
    #   0.3 — Fields exist but not grouped in a card structure
    #   0.0 — No employer card section found
    #
    # EVIDENCE TO CHECK:
    #   - grep for "Employer Details" in VoiceInterface.tsx
    #   - grep for "bg-white border border-gray-200 rounded-xl p-6" — should appear at least twice
    #   - Browser DOM: look for a second card matching the Candidate Details pattern
    #
    # RED FLAGS:
    #   - Employer fields still inside Candidate Details card
    #   - Card uses completely different styling than Candidate Details
    #   - "Employer Details" header exists but is not an h3 with uppercase tracking-wider

    Then I should see a card section with header "Employer Details"
    And it should use className "bg-white border border-gray-200 rounded-xl p-6"
    And it should have an icon element (e.g., Building2 or Briefcase from lucide-react)
    And the header should be an h3 with classes "text-sm font-semibold text-gray-800 uppercase tracking-wider"

  Scenario: S1.2 — Employer Details card contains all required fields
    # WHAT TO CHECK:
    #   The Employer Details card contains exactly these fields:
    #     1. Company Name (was employerName, migrated from Candidate Details)
    #     2. Website (was employerWebsite, migrated from Candidate Details)
    #     3. Country (NEW field)
    #     4. City (NEW field)
    #     5. Contact Person Name (migrated from standalone call config row)
    #     6. Contact Phone Number (NEW field)
    #
    # CONFIDENCE GUIDE:
    #   1.0 — All 6 fields present in the Employer Details card with proper labels
    #   0.8 — 5 of 6 fields present
    #   0.5 — 3-4 fields present, some still in old locations
    #   0.2 — Only 1-2 fields present or fields not in a card
    #   0.0 — No employer-specific fields found
    #
    # EVIDENCE TO CHECK:
    #   - Browser: navigate to /aura-call, look for 6 input fields in Employer Details card
    #   - Code: check VoiceInterface.tsx for input elements inside the Employer Details card section
    #   - State: check page.tsx for state variables (employerCountry, employerCity, contactPhone or similar)
    #
    # RED FLAGS:
    #   - Fields exist in state but no corresponding UI inputs
    #   - Placeholder text missing or generic
    #   - Field names don't match the payload expected by POST /api/v1/verify

    Then the Employer Details card should contain an input for "Company Name"
    And the Employer Details card should contain an input for "Website"
    And the Employer Details card should contain an input for "Country"
    And the Employer Details card should contain an input for "City"
    And the Employer Details card should contain an input for "Contact Person Name"
    And the Employer Details card should contain an input for "Contact Phone Number"

  Scenario: S1.3 — New fields have state management in page.tsx
    # WHAT TO CHECK:
    #   page.tsx declares state for the new fields (country, city, contactPhone)
    #   and passes them as props to VoiceInterface
    #
    # CONFIDENCE GUIDE:
    #   1.0 — useState declarations for all 3 new fields + props passed to VoiceInterface
    #   0.5 — State exists but props not wired, or some fields missing
    #   0.0 — No new state declarations
    #
    # EVIDENCE TO CHECK:
    #   - grep page.tsx for useState.*country, useState.*city, useState.*contactPhone
    #   - grep page.tsx for the VoiceInterface JSX props (should include new fields)
    #   - Check VoiceInterface component props interface for new fields

    Then page.tsx should have useState for employerCountry or country
    And page.tsx should have useState for employerCity or city
    And page.tsx should have useState for contactPhone or contactPhoneNumber
    And VoiceInterface should receive these as props


# =============================================================================
# F2: Create Task Button — POST /api/v1/verify Integration (weight: 0.30, CRITICAL)
# =============================================================================

@F2 @critical
Feature: Create Task Button

  Background:
    Given the /aura-call page is loaded
    And the user has filled in candidate and employer details

  Scenario: S2.1 — Button text changed from "Make Call" to "Create Task"
    # WHAT TO CHECK:
    #   The main action button now reads "Create Task" instead of "Make Call"
    #   The phone mode text may also need updating (was "Start Phone Call")
    #
    # CONFIDENCE GUIDE:
    #   1.0 — Button text is "Create Task", no trace of "Make Call" in the button
    #   0.5 — Button text changed but "Make Call" still appears elsewhere in code
    #   0.0 — Button still says "Make Call"
    #
    # EVIDENCE TO CHECK:
    #   - grep VoiceInterface.tsx for "Make Call" — should NOT appear in button text
    #   - grep VoiceInterface.tsx for "Create Task" — should appear in button text
    #   - Browser: visually confirm button text
    #
    # RED FLAGS:
    #   - "Make Call" still in code but conditionally hidden
    #   - "Create Task" added but "Make Call" still the default

    Then the primary action button should display "Create Task"
    And the text "Make Call" should not appear as button text in VoiceInterface.tsx

  Scenario: S2.2 — Button click calls POST /api/v1/verify
    # WHAT TO CHECK:
    #   Clicking "Create Task" triggers a fetch/axios call to POST /api/v1/verify
    #   The request body contains all candidate and employer fields
    #   The request goes to the backend API (not a page navigation)
    #
    # CONFIDENCE GUIDE:
    #   1.0 — Button click triggers POST /api/v1/verify with complete payload
    #   0.7 — POST request made but to a different endpoint or missing fields
    #   0.3 — Code exists for POST but button still triggers old behavior
    #   0.0 — No POST /api/v1/verify integration found
    #
    # EVIDENCE TO CHECK:
    #   - grep for "/api/v1/verify" in VoiceInterface.tsx or page.tsx
    #   - Read the handler function for the button click
    #   - Browser: click button, check Network tab for POST request
    #   - Inspect request payload in Network tab
    #
    # RED FLAGS:
    #   - POST goes to /api/outbound-call instead of /api/v1/verify
    #   - Button navigates to /verify-call/ instead of making a POST
    #   - Handler function is defined but not connected to button onClick

    When I click the "Create Task" button
    Then a POST request should be sent to "/api/v1/verify"
    And the request body should contain candidateFirstName
    And the request body should contain candidateLastName
    And the request body should contain employerName or company_name
    And the request body should contain employerWebsite or website
    And the request body should contain country
    And the request body should contain city
    And the request body should contain contactPersonName or contact_person_name
    And the request body should contain contactPhone or contact_phone

  Scenario: S2.3 — Success response shows confirmation
    # WHAT TO CHECK:
    #   After a successful POST /api/v1/verify response (200/201),
    #   the user sees a success indicator (toast, message, status text)
    #
    # CONFIDENCE GUIDE:
    #   1.0 — Clear success message/toast shown with task details
    #   0.5 — Some feedback shown but generic or unclear
    #   0.2 — Console.log only, no user-visible feedback
    #   0.0 — No success handling found
    #
    # EVIDENCE TO CHECK:
    #   - Read the POST handler's .then() or try/catch success branch
    #   - Browser: fill form, click Create Task, observe UI response
    #   - Look for toast/notification/state update on success

    Then a success message should be displayed to the user
    And the message should indicate the task was created

  Scenario: S2.4 — Error response displays error to user
    # WHAT TO CHECK:
    #   If POST /api/v1/verify returns an error (4xx, 5xx, network failure),
    #   the user sees an error message (not a blank screen or console-only error)
    #
    # CONFIDENCE GUIDE:
    #   1.0 — Error message displayed in UI with actionable information
    #   0.5 — Generic error shown ("Something went wrong")
    #   0.2 — Error caught but only logged to console
    #   0.0 — No error handling — unhandled promise rejection
    #
    # EVIDENCE TO CHECK:
    #   - Read the POST handler's .catch() or try/catch error branch
    #   - Look for error state variable and corresponding UI element
    #   - Browser: simulate error (invalid data) and observe response

    Then an error message should be displayed to the user
    And the error should be caught (no unhandled promise rejection)

  Scenario: S2.5 — Loading state shown during API call
    # WHAT TO CHECK:
    #   While the POST request is in flight, the button shows a loading state
    #   (disabled, spinner, or text change like "Creating...")
    #
    # CONFIDENCE GUIDE:
    #   1.0 — Button disabled + visual loading indicator during request
    #   0.5 — Button disabled but no visual indicator
    #   0.2 — Loading state exists in code but not wired to button
    #   0.0 — No loading state handling
    #
    # EVIDENCE TO CHECK:
    #   - Look for isLoading/isSubmitting state variable
    #   - Check if button has disabled={isLoading} or similar
    #   - Browser: click Create Task, observe button state during request

    Then the "Create Task" button should show a loading state during the API call
    And the button should be disabled while the request is in flight


# =============================================================================
# F3: Field Migration — Employer Fields Moved Correctly (weight: 0.15, IMPORTANT)
# =============================================================================

@F3
Feature: Field Migration

  Scenario: S3.1 — Employer fields removed from Candidate Details card
    # WHAT TO CHECK:
    #   The Candidate Details card in VoiceInterface.tsx no longer contains
    #   employerName or employerWebsite inputs. These must be in the
    #   Employer Details card instead.
    #
    # CONFIDENCE GUIDE:
    #   1.0 — employerName and employerWebsite are exclusively in Employer Details card
    #   0.5 — Fields appear in both cards (duplicated)
    #   0.0 — Fields still only in Candidate Details card
    #
    # EVIDENCE TO CHECK:
    #   - Read the Candidate Details card section — should NOT contain employer fields
    #   - Read the Employer Details card section — SHOULD contain employer fields
    #   - Browser: visually verify field locations
    #
    # RED FLAGS:
    #   - employerName input appears twice in VoiceInterface.tsx
    #   - Fields removed from Candidate Details but not added to Employer Details

    Then the Candidate Details card should NOT contain "Employer Name" or "employerName" input
    And the Candidate Details card should NOT contain "Website" input for employer
    And the Employer Details card SHOULD contain these fields

  Scenario: S3.2 — Contact Person Name moved from config row to Employer Details
    # WHAT TO CHECK:
    #   contactPersonName was previously a standalone field in the call
    #   configuration row (around lines 526-538 of original VoiceInterface.tsx).
    #   It must now be inside the Employer Details card.
    #
    # CONFIDENCE GUIDE:
    #   1.0 — contactPersonName exclusively in Employer Details card, removed from config row
    #   0.5 — Field in Employer Details but also still in config row (duplicated)
    #   0.0 — Field still only in the config row
    #
    # EVIDENCE TO CHECK:
    #   - grep for contactPersonName in VoiceInterface.tsx — should be in Employer card section
    #   - Check that the old location (call config row) no longer has this field
    #   - Browser: verify contact person name appears under Employer Details

    Then contactPersonName should be inside the Employer Details card
    And contactPersonName should NOT be in the call configuration row

  Scenario: S3.3 — Candidate Details card retains only candidate-specific fields
    # WHAT TO CHECK:
    #   After migration, the Candidate Details card should contain only:
    #   - First Name, Middle Name, Last Name
    #   - Position/Role, Start Date, End Date
    #   (No employer fields remain)
    #
    # CONFIDENCE GUIDE:
    #   1.0 — Only candidate-specific fields remain, clean separation
    #   0.7 — Mostly clean but one stray field remains
    #   0.3 — Multiple employer fields still in Candidate Details
    #   0.0 — No migration occurred
    #
    # EVIDENCE TO CHECK:
    #   - Read the Candidate Details card section completely
    #   - List all input fields within that card boundary
    #   - Verify none relate to employer information

    Then the Candidate Details card should contain firstName, middleName, lastName
    And the Candidate Details card should contain position, startDate, endDate
    And the Candidate Details card should NOT contain any employer-related fields


# =============================================================================
# F4: Form Validation and Error Handling (weight: 0.10, IMPORTANT)
# =============================================================================

@F4
Feature: Form Validation and Error Handling

  Scenario: S4.1 — Required fields are validated before submission
    # WHAT TO CHECK:
    #   The "Create Task" button should not submit if required fields are empty.
    #   At minimum, company name and contact phone should be required.
    #
    # CONFIDENCE GUIDE:
    #   1.0 — Clear validation with inline error messages for required fields
    #   0.5 — Button disabled when fields empty, but no error messages
    #   0.2 — Validation exists but only for some fields
    #   0.0 — No client-side validation — all fields optional
    #
    # EVIDENCE TO CHECK:
    #   - Look for validation logic before the POST call
    #   - Check for required attributes on input elements
    #   - Browser: try submitting with empty fields

    Then required fields (at minimum company name, contact phone) should be validated
    And the form should prevent submission when required fields are empty

  Scenario: S4.2 — API errors are displayed in the UI
    # WHAT TO CHECK:
    #   If POST /api/v1/verify returns 400/422/500, the user sees an error.
    #   Not just console.error, but a visible UI element.
    #
    # CONFIDENCE GUIDE:
    #   1.0 — Error state stored and rendered as visible UI element
    #   0.5 — Error caught and generic message shown
    #   0.2 — Error caught but only in console
    #   0.0 — No error handling

    Then API errors should be displayed as visible UI elements
    And the user should see actionable error information


# =============================================================================
# F5: Visual Consistency and Responsiveness (weight: 0.10, IMPORTANT)
# =============================================================================

@F5
Feature: Visual Consistency

  Scenario: S5.1 — Employer Details card matches Candidate Details styling
    # WHAT TO CHECK:
    #   Both cards use identical structural CSS:
    #   - Outer div: bg-white border border-gray-200 rounded-xl p-6
    #   - Header: flex items-center gap-2 mb-4
    #   - h3: text-sm font-semibold text-gray-800 uppercase tracking-wider
    #   - Input fields use same styling pattern
    #
    # CONFIDENCE GUIDE:
    #   1.0 — Pixel-perfect CSS match between both cards
    #   0.7 — Same general structure, minor differences (different icon size, etc.)
    #   0.3 — Visually similar but noticeably different styling
    #   0.0 — Completely different card styling
    #
    # EVIDENCE TO CHECK:
    #   - Compare CSS classes between both card sections in code
    #   - Browser: visually compare both cards side by side
    #   - Check icon sizing and header typography match

    Then the Employer Details card should use className "bg-white border border-gray-200 rounded-xl p-6"
    And the card header should use the same flex + uppercase pattern as Candidate Details
    And input fields should use the same styling pattern

  Scenario: S5.2 — Card ordering is logical
    # WHAT TO CHECK:
    #   Cards appear in a logical order on the page:
    #   1. Candidate Details
    #   2. Employer Details
    #   3. Additional Verification Points (existing)
    #   The new card should be between Candidate and Verification Points.
    #
    # CONFIDENCE GUIDE:
    #   1.0 — Employer Details card between Candidate Details and Verification Points
    #   0.5 — Employer Details card exists but in unexpected position
    #   0.0 — No distinct card section

    Then the Employer Details card should appear after the Candidate Details card
    And the Employer Details card should appear before the Additional Verification Points card


# =============================================================================
# F6: Browser Automation Validation (weight: 0.05, NICE_TO_HAVE)
# =============================================================================

@F6
Feature: Browser Automation Validation

  Scenario: S6.1 — Full form submission via Claude in Chrome
    # WHAT TO CHECK:
    #   An operator using Claude in Chrome can:
    #   1. Navigate to /aura-call (localhost:3000/aura-call or similar)
    #   2. Fill in all Candidate Details fields
    #   3. Fill in all Employer Details fields
    #   4. Click "Create Task"
    #   5. See the POST /api/v1/verify request in Network tab
    #   6. See a success or meaningful error response
    #
    # CONFIDENCE GUIDE:
    #   1.0 — Full workflow completes end-to-end via browser automation
    #   0.5 — Form fills but POST fails or returns error
    #   0.2 — Page loads but form interaction fails
    #   0.0 — Not tested via browser automation
    #
    # EVIDENCE TO CHECK:
    #   - Screenshot of filled form
    #   - Network request log showing POST /api/v1/verify
    #   - Response body from the POST request
    #
    # NOTE: This scenario may not be scoreable until the full stack is running.
    # Score as N/A (excluded from weighted total) if stack is not available.

    When the operator navigates to /aura-call
    And fills in Candidate Details (first name, last name, etc.)
    And fills in Employer Details (company, website, country, city, contact name, phone)
    And clicks "Create Task"
    Then a POST request to /api/v1/verify should appear in the network tab
    And the response should indicate task creation success or a clear error
