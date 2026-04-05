Feature: Employer Contact Research via Perplexity API
  As a contact enrichment pipeline
  I want to discover employer contact details using Perplexity search
  So that placement teams have actionable phone/email contacts for each employer

  # Scoring: 1.0 = exact match to expected output
  #          0.7 = correct structure, minor deviations (e.g. alternate phone format)
  #          0.5 = partially correct (some contacts found, missing key fields)
  #          0.0 = missing or wrong (no contacts returned, wrong employer matched)

  Background:
    Given the Perplexity API is reachable
    And the researcher module is initialised with a valid API key

  @api-required
  Scenario: Discover contacts for a small regional employer (name + country only)
    Given employer input:
      | field   | value         |
      | name    | Kresta Blinds |
      | country | AUS           |
    When the researcher runs contact discovery
    Then the result should contain at least 1 contact
    And at least one contact should have a phone number matching "07 3358 5342" or similar Queensland format
    And at least one contact should have an email address ending in "@khl.com.au" or the domain "khl.com.au"
    And each returned contact should have a confidence_score between 0.0 and 1.0
    And each returned contact should have a non-empty source_url

  @api-required
  Scenario: Discover contacts for a large national employer (name + country only)
    Given employer input:
      | field   | value                        |
      | name    | Vanguard Investments Australia |
      | country | AUS                          |
    When the researcher runs contact discovery
    Then the result should contain at least 2 contacts
    And at least one contact should have a phone or email associated with Vanguard Australia
    And the result should include at least one contact with a title or department indication
    And each returned contact should have a confidence_score between 0.0 and 1.0

  @api-required
  Scenario: Enrich partial data — phone already known, discover email and manager
    Given employer input:
      | field   | value     |
      | name    | SICE ANZ  |
      | country | AUS       |
      | phone   | 0382566900 |
    When the researcher runs contact discovery
    Then the result should contain at least 1 contact
    And at least one contact should have an email address containing "sice.com.au"
    And the researcher should not duplicate the provided phone as a new discovery
    And each returned contact should carry a source_url pointing to a live or archived web page

  @api-required
  Scenario: Discover contacts for a niche SME employer
    Given employer input:
      | field   | value                  |
      | name    | Premier Proline Pty Ltd |
      | country | AUS                    |
    When the researcher runs contact discovery
    Then the result may contain 0 or more contacts
    And if contacts are returned, each should have at least one of: phone, email, name
    And if contacts are returned, each should have a confidence_score > 0.0
    And the call should complete without raising an exception

  @api-required
  Scenario: Handle zero-results gracefully for an obscure or fictional employer
    Given employer input:
      | field   | value                              |
      | name    | Zzymox Industrial Fictitious Pty Ltd |
      | country | AUS                                |
    When the researcher runs contact discovery
    Then the result should be an empty list or a list with confidence_score = 0.0
    And no exception should be raised
    And the response should indicate zero results clearly (not a fabricated contact)

  @api-required
  Scenario: Confidence scores reflect source quality
    Given employer input:
      | field   | value                        |
      | name    | Medatech Australia           |
      | country | AUS                          |
    When the researcher runs contact discovery
    Then contacts sourced from the employer's own domain should have confidence_score >= 0.7
    And contacts sourced from third-party directories should have confidence_score between 0.3 and 0.9
    And no contact should have a confidence_score outside the range 0.0 to 1.0
    And each contact source_url should be a valid URL string
