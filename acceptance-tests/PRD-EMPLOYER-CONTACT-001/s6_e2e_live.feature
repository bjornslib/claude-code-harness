Feature: End-to-End Live Test with Real Employers
  As a QA engineer validating the full pipeline against live data
  I want to run the complete research → dedup → classify → prioritise flow
  Against real Australian employers using the live Perplexity API
  So that I can confirm the system produces usable contact data in production conditions

  # Scoring: 1.0 = full pipeline runs, contacts returned, all validation fields present
  #          0.7 = pipeline runs, 1+ contacts returned, some fields missing (e.g. source_url)
  #          0.5 = pipeline runs but zero contacts found for known employers
  #          0.0 = exception raised, pipeline does not complete

  # NOTE: These tests require live Perplexity API access and network connectivity.
  # They are marked @live and @api-required. Do not run in offline/mock environments.

  Background:
    Given the full employer contact service is running
    And a valid Perplexity API key is configured in the environment
    And no mock patches are active

  @live @api-required
  Scenario: Discover at least one contact for Kresta Blinds (name + country only)
    Given employer input with no pre-existing contacts:
      | field   | value         |
      | name    | Kresta Blinds |
      | country | AUS           |
    When the full pipeline is executed against the live Perplexity API
    Then the pipeline should complete without raising an exception
    And the result should be a PrioritizedContactList
    And the result should contain at least 1 contact
    And at least one contact should have a phone number or email address present
    And at least one contact should have a confidence_score greater than 0.0
    And at least one contact should have a non-empty source_url

  @live @api-required
  Scenario: Discover multiple contacts for Vanguard Investments Australia (large known employer)
    Given employer input with no pre-existing contacts:
      | field   | value                          |
      | name    | Vanguard Investments Australia |
      | country | AUS                            |
    When the full pipeline is executed against the live Perplexity API
    Then the pipeline should complete without raising an exception
    And the result should contain at least 2 contacts
    And at least one contact should have a name, or a department label
    And at least one contact should have a phone number or email address present
    And all returned contacts should have confidence_score between 0.0 and 1.0

  @live @api-required
  Scenario: Enrich SICE ANZ using partial seed data (name + country + partial phone)
    Given employer input:
      | field   | value      |
      | name    | SICE ANZ   |
      | country | AUS        |
      | phone   | 0382566900 |
    When the full pipeline is executed against the live Perplexity API
    Then the pipeline should complete without raising an exception
    And the result should contain at least 1 contact
    And at least one contact should have an email address present
    And the result should not contain duplicate contacts for the same person
    And each contact in the result should have a unique (name + email) or (name + phone) combination

  @live @api-required
  Scenario: Full pipeline E2E — research, dedup, classify, prioritise, return structured result
    Given employer input with customer-provided contacts for "Medatech Australia":
      | field               | value                 |
      | employer_name       | Medatech Australia    |
      | country             | AUS                   |
      | customer_contact_name | David Linke         |
      | customer_contact_email | sales@medatech.com.au |
      | is_customer_provided | true                 |
    When the full pipeline is executed (research → dedup → classify → prioritise)
    Then the pipeline should complete all 4 stages without exception
    And the result type should be PrioritizedContactList
    And the result should contain the customer-provided contact "David Linke"
    And each contact in the result should have at minimum:
      | required_field  | constraint                        |
      | name OR department | at least one must be non-empty |
      | phone OR email  | at least one must be non-empty    |
      | confidence_score | greater than 0.0                 |
      | source_url      | non-empty string (URL format)     |
    And the customer-provided contact should not have a lower priority rank than discovered contacts of the same tier

  @live @api-required
  Scenario: Validate contact quality — no fabricated contacts
    Given employer input:
      | field   | value                      |
      | name    | Premier Proline Pty Ltd    |
      | country | AUS                        |
    When the full pipeline is executed against the live Perplexity API
    Then any returned contacts should have a source_url that is a valid URL
    And no contact should have a confidence_score of exactly 1.0 unless the source is the employer's own domain
    And if zero contacts are returned, the result should be an empty PrioritizedContactList (not None)
    And the pipeline should complete within 60 seconds

  @live @api-required
  Scenario: Pipeline latency is acceptable for production use
    Given employer input for 1 employer:
      | field   | value                          |
      | name    | Vanguard Investments Australia |
      | country | AUS                            |
    When the full pipeline is executed and execution time is measured
    Then the pipeline should complete within 120 seconds
    And the Perplexity API should be called at most 5 times for a single employer lookup
