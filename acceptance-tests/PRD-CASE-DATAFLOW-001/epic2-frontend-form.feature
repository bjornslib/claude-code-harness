Feature: E2 — Frontend Form shadcn Component Upgrade
  As a verification operator
  I want a form with proper date pickers, country selection, and complete employment options
  So that my data is always valid and complete

  Background:
    Given the New Verification form at "/checks-dashboard/new"
    And shadcn components Calendar, Popover, and Command are installed

  # === M8: DatePicker component ===

  Scenario: Start date uses shadcn DatePicker
    When I inspect the startDate form field
    Then it should render a DatePicker component (Popover + Calendar)
    And NOT a raw HTML <input type="date">

  Scenario: End date uses shadcn DatePicker
    When I inspect the endDate form field
    Then it should render a DatePicker component (Popover + Calendar)
    And NOT a raw HTML <input type="date">

  Scenario: DatePicker produces YYYY-MM-DD format
    When I select March 19, 2026 in the start date DatePicker
    Then the form value should be "2026-03-19"

  # === M7: Date format validation ===

  Scenario: Zod schema rejects invalid date format
    When I programmatically set startDate to "invalid"
    And I submit the form
    Then a validation error should appear for startDate
    And the error message should mention date format

  # === Country Combobox ===

  Scenario: Country field uses shadcn Combobox
    When I inspect the employerCountry form field
    Then it should render a Combobox component (Command + Popover)
    And NOT a raw HTML <input>

  Scenario: Country Combobox includes key markets
    When I open the country Combobox
    Then the options should include "Australia", "Singapore", "United States", "United Kingdom"

  # === M2: Employment Type enum alignment ===

  Scenario: Employment Type Select has all backend enum values
    When I open the Employment Type Select dropdown
    Then the options should be exactly:
      | Value       | Label      |
      | full_time   | Full-time  |
      | part_time   | Part-time  |
      | contractor  | Contractor |
      | casual      | Casual     |
    And NOT contain "contract" (the old incorrect value)

  # === Employment Arrangement (new field) ===

  Scenario: Employment Arrangement Select is present
    When I inspect the form
    Then there should be an "Employment Arrangement" Select field
    With options: "Direct Employment", "Via Agency", "Subcontractor"

  Scenario: Agency Name appears when arrangement is agency
    Given Employment Arrangement is set to "agency"
    Then an "Agency Name" input field should be visible

  Scenario: Agency Name appears when arrangement is subcontractor
    Given Employment Arrangement is set to "subcontractor"
    Then an "Agency Name" input field should be visible

  Scenario: Agency Name is hidden when arrangement is direct
    Given Employment Arrangement is set to "direct"
    Then an "Agency Name" input field should NOT be visible

  Scenario: Agency Name is required when arrangement is agency
    Given Employment Arrangement is set to "agency"
    And Agency Name is empty
    When I submit the form
    Then a validation error should appear for agencyName

  # === Verify Fields alignment ===

  Scenario: Verify Fields checkboxes include all backend options
    When I inspect the Additional Verification Points section
    Then the checkboxes should include:
      | Key                  | Label                |
      | salary               | Salary               |
      | supervisor           | Supervisor           |
      | employment_type      | Employment Type      |
      | rehire_eligibility   | Rehire Eligibility   |
      | reason_for_leaving   | Reason for Leaving   |

  # === Form submission produces correct payload ===

  Scenario: Form payload includes employmentArrangement and agencyName
    Given I fill out the form completely with arrangement="agency" and agencyName="Hays"
    When I submit the form
    Then the POST payload to /api/verify should include:
      | Field                  | Value    |
      | employmentArrangement  | agency   |
      | agencyName             | Hays     |
