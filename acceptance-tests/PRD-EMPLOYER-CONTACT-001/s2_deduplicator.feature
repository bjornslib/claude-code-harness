Feature: Contact Deduplication via DSPy ChainOfThought
  As a contact enrichment pipeline
  I want to merge duplicate contacts detected across multiple sources
  So that the final contact list contains no redundant entries

  # Scoring: 1.0 = exact match to expected output
  #          0.7 = correct structure, minor deviations (e.g. merged but wrong canonical field chosen)
  #          0.5 = partially correct (some merges done, some duplicates remain)
  #          0.0 = no deduplication performed, or wrong merges made

  Background:
    Given the deduplicator module is initialised
    And it uses DSPy ChainOfThought (not regex or rule-based matching)

  @code-analysis
  Scenario: DSPy ChainOfThought is used — not regex matching
    Given the deduplicator source code is inspected
    Then the deduplicator should import dspy
    And the deduplicator should define or use a ChainOfThought module
    And there should be no standalone regex patterns used as the primary deduplication logic
    And the deduplication decision should be produced by calling a dspy module

  @mock
  Scenario: Merge duplicate contacts from two sources — same person, different formats
    Given a contact list from source A:
      | name           | phone        | email                        |
      | Samantha Bradshaw | 0733585342 | bciqldservice@khl.com.au    |
    And a contact list from source B:
      | name           | phone          | email                        |
      | S. Bradshaw    | 07 3358 5342   | bciqldservice@khl.com.au    |
    When the deduplicator processes both lists
    Then the result should contain exactly 1 contact
    And the merged contact should have name "Samantha Bradshaw" (preferring the more complete form)
    And the merged contact should retain the email "bciqldservice@khl.com.au"
    And the merged contact should retain a phone number equivalent to "07 3358 5342"

  @mock
  Scenario: Keep distinct contacts that are similar but genuinely different people
    Given a contact list containing:
      | name          | email                       | phone       |
      | Adam Mariani  | adam.mariani@vanguard.com.au | 1800018753 |
      | Alana Zielinski | alana.zielinski@vanguard.com.au | 1800018753 |
    When the deduplicator processes the list
    Then the result should contain exactly 2 contacts
    And "Adam Mariani" should remain as a separate contact
    And "Alana Zielinski" should remain as a separate contact
    And shared fields like phone should be preserved on both records independently

  @mock
  Scenario: Merge customer-provided contact with a discovered contact for the same person
    Given a customer-provided contact:
      | field              | value                    |
      | name               | Alex Xu                  |
      | email              | Alex.Xu@sice.com.au      |
      | is_customer_provided | true                   |
    And a discovered contact from Perplexity:
      | field              | value                    |
      | name               | Alex Xu                  |
      | phone              | 0382566900               |
      | source_url         | https://sice.com.au/team |
      | is_customer_provided | false                  |
    When the deduplicator merges the two contact lists
    Then the result should contain exactly 1 contact for "Alex Xu"
    And the merged contact should have is_customer_provided = true
    And the merged contact should carry the customer-provided email "Alex.Xu@sice.com.au"
    And the merged contact should carry the discovered phone "0382566900"
    And the merged contact should retain the source_url from the discovered record

  @mock
  Scenario: Preserve all distinct contacts when no duplicates exist
    Given a contact list containing 3 contacts with no overlapping name, email, or phone
    When the deduplicator processes the list
    Then the result should contain exactly 3 contacts
    And no contacts should be modified or merged

  @mock
  Scenario: Handle empty input gracefully
    Given an empty contact list
    When the deduplicator processes the list
    Then the result should be an empty list
    And no exception should be raised
