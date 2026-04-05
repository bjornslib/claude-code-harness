Feature: Contact Classification and Prioritisation via DSPy Predict
  As a contact enrichment pipeline
  I want to classify each contact and sort the final list by priority tier
  So that placement teams always see the highest-value contacts first

  # Scoring: 1.0 = exact match to expected output (correct tier, correct order)
  #          0.7 = correct classification, minor ordering errors
  #          0.5 = most contacts classified correctly, tier ordering wrong
  #          0.0 = no classification applied, or all contacts in wrong tier

  Background:
    Given the classifier module is initialised
    And it uses DSPy Predict (not pure Python if/else rules)

  @code-analysis
  Scenario: DSPy Predict is used — not hardcoded rules
    Given the classifier source code is inspected
    Then the classifier should import dspy
    And the classifier should define or use a Predict module for classification
    And the primary classification decision should not be a series of hardcoded if/elif statements
    And the module should accept a contact dict and return a tier label

  @code-analysis
  Scenario: Classification tiers are defined and cover all expected categories
    Given the classifier source code is inspected
    Then the classifier should define at minimum these tier labels:
      | tier              |
      | general           |
      | named_poc         |
      | validated_poc     |
    And the priority ordering should be: validated_poc > named_poc > general

  @mock
  Scenario: Classify a named manager as named_poc
    Given a contact:
      | field  | value          |
      | name   | Jaime Macdonald |
      | title  | Manager        |
      | email  | sarah.harris@hydroil.com.au |
    When the classifier processes the contact
    Then the contact should be assigned tier "named_poc"

  @mock
  Scenario: Classify a generic department address as general
    Given a contact:
      | field       | value                     |
      | name        |                           |
      | department  | Customer Service          |
      | email       | service@somecompany.com.au |
    When the classifier processes the contact
    Then the contact should be assigned tier "general"

  @mock
  Scenario: Customer-provided contacts rank highest within their tier
    Given a contact list containing:
      | name             | tier      | is_customer_provided |
      | David Linke      | named_poc | true                 |
      | Generic Enquiries | general  | false                |
      | Some Recruiter   | named_poc | false                |
    When the classifier prioritises the list
    Then "David Linke" (customer-provided named_poc) should rank above "Some Recruiter" (discovered named_poc)
    And "David Linke" should appear first in the output list

  @mock
  Scenario: Small employer CEO classified as named_poc
    Given an employer with estimated employee count less than 50
    And a contact:
      | field | value            |
      | name  | Samantha Bradshaw |
      | title | CEO              |
    When the classifier processes the contact
    Then the contact should be assigned tier "named_poc"

  @mock
  Scenario: Full prioritisation sort across all 7 tiers
    Given a mixed contact list:
      | name               | tier          | is_customer_provided | confidence_score |
      | Alex Xu            | validated_poc | false                | 0.9              |
      | Adam Mariani       | named_poc     | true                 | 0.8              |
      | Alana Zielinski    | named_poc     | false                | 0.75             |
      | Sales Team         | general       | false                | 0.4              |
    When the classifier prioritises the list
    Then the output order should be:
      | position | name            |
      | 1        | Alex Xu         |
      | 2        | Adam Mariani    |
      | 3        | Alana Zielinski |
      | 4        | Sales Team      |
    And validated_poc contacts should always precede named_poc contacts
    And named_poc contacts should always precede general contacts

  @mock
  Scenario: Return a PrioritizedContactList structure
    Given a list of classified contacts
    When the classifier returns the final result
    Then the result type should be PrioritizedContactList (or equivalent named model)
    And the result should expose the ranked list of contacts as an iterable
    And each contact in the result should retain its tier label and confidence_score
