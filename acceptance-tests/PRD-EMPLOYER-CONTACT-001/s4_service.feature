Feature: Service Pipeline Orchestration
  As a consumer of the employer contact enrichment service
  I want a single service entry point that orchestrates all pipeline stages
  So that callers do not need to wire individual components together

  # Scoring: 1.0 = pipeline runs end-to-end, correct stage order, correct output
  #          0.7 = pipeline runs, minor output deviation or optional stage missing
  #          0.5 = some stages wired correctly, others missing or out of order
  #          0.0 = service does not exist, raises on call, or stage order wrong

  Background:
    Given the employer contact service is importable
    And the service exposes a callable entry point (function or class method)

  @code-analysis
  Scenario: Pipeline stage order — dedup before classify
    Given the service source code is inspected
    Then the deduplication stage should be called before the classification stage
    And the classification stage should receive the output of the deduplication stage
    And the research stage should be called before deduplication

  @code-analysis
  Scenario: All four stages are present in the service
    Given the service source code is inspected
    Then the service should call or invoke: research
    And the service should call or invoke: deduplication
    And the service should call or invoke: classification
    And the service should call or invoke: storage (repository write)

  @mock
  Scenario: Full pipeline with customer-provided contacts as seed input
    Given customer-provided contacts for "Medatech Australia":
      | name        | email                  | phone       | is_customer_provided |
      | David Linke | sales@medatech.com.au  | 0393297355  | true                 |
    When the service is called with employer name "Medatech Australia" and the above contacts
    Then the pipeline should run all stages: research, dedup, classify, store
    And the result should be a PrioritizedContactList
    And the customer-provided contact "David Linke" should appear in the result
    And "David Linke" should not be duplicated in the result

  @mock
  Scenario: Perplexity API failure falls back to customer-provided contacts only
    Given the Perplexity API is unavailable (raises an exception or returns error)
    And customer-provided contacts for "SICE ANZ":
      | name    | email               | is_customer_provided |
      | Alex Xu | Alex.Xu@sice.com.au | true                 |
    When the service is called with employer name "SICE ANZ" and the above contacts
    Then the pipeline should complete without raising an unhandled exception
    And the result should contain the customer-provided contact "Alex Xu"
    And the result should not be empty

  @mock
  Scenario: Zero discovered contacts returns result with customer contacts only
    Given the Perplexity API returns an empty result for "Premier Proline Pty Ltd"
    And customer-provided contacts:
      | name             | email                          | is_customer_provided |
      | Jaime Macdonald  | sarah.harris@hydroil.com.au    | true                 |
    When the service is called
    Then the result should contain exactly the customer-provided contact
    And the result should be a valid PrioritizedContactList (not None, not empty)
    And no exception should be raised

  @mock
  Scenario: Service with no customer contacts and no API results returns empty list gracefully
    Given the Perplexity API returns empty results
    And no customer-provided contacts are supplied
    When the service is called for any employer
    Then the result should be a PrioritizedContactList with an empty or zero-length contact list
    And no exception should be raised

  @mock
  Scenario: Service stores results to the repository after pipeline completes
    Given a successful pipeline run for "Vanguard Investments Australia"
    When the service completes
    Then the repository write method should have been called at least once
    And the stored records should include entity_type set to "employer"
    And the stored records should include the employer identifier or name
