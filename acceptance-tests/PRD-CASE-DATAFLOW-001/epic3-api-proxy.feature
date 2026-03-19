Feature: E3 — API Proxy Contract Alignment
  As a platform engineer
  I want the frontend proxy to map all fields to canonical backend names
  So that no data is silently lost between frontend and backend

  Background:
    Given the API proxy at "app/api/verify/route.ts"
    And the backend endpoint at "/api/v1/verify"

  # === M1: rehire_eligibility → eligibility_for_rehire ===

  Scenario: Proxy maps rehire_eligibility to eligibility_for_rehire
    Given frontend verifyFields has rehire_eligibility=true
    When the proxy builds backendVerifyFields
    Then the field name should be "eligibility_for_rehire" (not "rehire_eligibility")
    And the value should be true

  Scenario: Backend receives eligibility_for_rehire
    Given a form submission with rehire_eligibility checked
    When the proxy forwards to /api/v1/verify
    Then the backend should receive verify_fields.eligibility_for_rehire=true

  # === M3 + M9: Employer field name fixes ===

  Scenario: Proxy maps contactPersonName to hr_contact_name
    Given frontend payload has contactPersonName="Jane Doe"
    When the proxy builds the employer object
    Then the field should be "hr_contact_name" (not "contact_name")

  Scenario: Proxy maps contactEmail to hr_email
    Given frontend payload has contactEmail="hr@company.com"
    When the proxy builds the employer object
    Then the field should be "hr_email" (not "contact_email")

  Scenario: Backend receives hr_contact_name
    Given a form submission with contact person "Jane Doe"
    When the proxy forwards to /api/v1/verify
    Then the backend EmployerInfo should have hr_contact_name="Jane Doe"

  # === Employment arrangement pass-through ===

  Scenario: Proxy passes employment_arrangement to backend
    Given frontend payload has employmentArrangement="agency"
    When the proxy builds the employment object
    Then employment.employment_arrangement should be "agency"

  Scenario: Proxy passes agency_name to backend
    Given frontend payload has agencyName="Robert Half"
    When the proxy builds the employment object
    Then employment.agency_name should be "Robert Half"

  # === Date validation ===

  Scenario: Proxy validates date format before sending
    Given frontend payload has startDate="invalid-date"
    When the proxy processes the request
    Then it should return HTTP 400
    And the error should mention date format

  Scenario: Proxy accepts valid YYYY-MM-DD date
    Given frontend payload has startDate="2026-03-19"
    When the proxy processes the request
    Then the date should be forwarded without error

  # === Type imports ===

  Scenario: Proxy uses canonical TypeScript types
    When I inspect the imports in route.ts
    Then it should import types from "lib/types/work-history.generated"
    And NOT define inline FrontendVerifyFields interface

  # === Regression: standard flow still works ===

  Scenario: Standard work history submission succeeds
    Given a valid form submission with all required fields
    When the proxy forwards to /api/v1/verify
    Then the response should be HTTP 201
    And the response should contain a task_id
