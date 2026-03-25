Feature: PRD-CASE-DATAFLOW-001 Backend Integration
  As a platform engineer
  I want canonical types validated end-to-end
  So that field mismatches are caught before production

  Background:
    Given the feature branch "feature/PRD-CASE-DATAFLOW-001" is checked out
    And the local PostgreSQL is running at localhost:5434
    And migration 053 has been applied

  Scenario: Canonical models pass all unit tests
    When I run "pytest tests/test_work_history_models.py -v"
    Then all 29 tests should pass

  Scenario: Generated TypeScript types compile
    When I run "npx tsc --noEmit lib/types/work-history.generated.ts" in agencheck-support-frontend
    Then exit code should be 0

  Scenario: Frontend builds with new shadcn components
    When I run "npm run build" in agencheck-support-frontend
    Then the build should succeed

  Scenario: API accepts canonical schema
    Given the backend is running
    When I POST /api/v1/verify with valid VerificationRequest:
      | candidate.first_name          | John              |
      | candidate.last_name           | Smith             |
      | employer.employer_company_name| Acme Corp         |
      | employer.country_code         | AU                |
      | employer.phone_numbers        | ["+61404236990"]  |
      | employment.start_date         | 2020-01-15        |
      | employment.position_title     | Software Engineer |
      | employment.salary_amount      | 85000             |
      | employment.salary_currency    | AUD               |
      | verify_fields.salary          | true              |
    Then the response should be 200/201 with a task_id UUID

  Scenario: Optional employer_website_url does not cause 500
    When I POST /api/v1/verify without employer_website_url
    Then the response should NOT be 500

  Scenario: Auto-derive salary_currency from country_code
    When I POST with salary_amount="85000" but no salary_currency
    And employer.country_code="AU"
    Then salary_currency in stored metadata should be "AUD"

  Scenario: JSONB verification_metadata stores canonical structure
    Given a case was created via the API
    When I query cases.verification_metadata for that case_id
    Then it should contain employer.country_code="AU"
    And employer.contacts should be a JSON array
    And employment.salary_amount="85000"
    And employment.salary_currency="AUD"
    And there should be NO hr_contact_name or hr_email fields

  Scenario: Invalid country code rejected
    When I POST with employer.country_code="XX"
    Then response should be 422 with country_code error

  Scenario: Invalid currency rejected
    When I POST with employment.salary_currency="ZZZ"
    Then response should be 422 with currency error

  Scenario: PostCheckProcessor import works
    When I run "python -c 'from helpers.post_call_processor import PostCheckProcessor'"
    Then the import succeeds

  Scenario: Backward-compatible PostCallProcessor alias works
    When I run "python -c 'from helpers.post_call_processor import PostCallProcessor'"
    Then the import succeeds
