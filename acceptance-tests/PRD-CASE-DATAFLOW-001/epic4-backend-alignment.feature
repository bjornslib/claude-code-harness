Feature: E4 — Backend Agent & Processor Type Alignment
  As a platform engineer
  I want both outcome paths to produce identical VerificationOutcome objects
  So that downstream consumers don't need path-specific handling

  Background:
    Given the Live Form Filler path via outcome_builder.py
    And the PostCallProcessor path via process_post_call.py
    And the canonical VerificationOutcome from models/work_history.py

  # === M6: was_employed fix ===

  Scenario: PostCallProcessor uses valid EmploymentStatusEnum values only
    When I inspect the was_employed derivation in the converter
    Then it should check against EmploymentStatusEnum.VERIFIED and PARTIAL_VERIFICATION
    And NOT reference "currently_employed" as a comparison value

  Scenario: Currently_employed maps to VERIFIED in legacy mapping
    Given the _normalize_employment_status function
    When called with "currently_employed"
    Then it should return EmploymentStatusEnum.VERIFIED

  # === M4: CandidateInfo field mapping ===

  Scenario: process_post_call maps start_date to claimed_start correctly
    Given candidate_info_data with start_date="2019-03-01"
    When building CandidateInfo for PostCallProcessor
    Then claimed_start should receive "2019-03-01"

  Scenario: process_post_call maps end_date to claimed_end correctly
    Given candidate_info_data with end_date="2021-06-15"
    When building CandidateInfo for PostCallProcessor
    Then claimed_end should receive "2021-06-15"

  # === M5: VerifiedField convergence ===

  Scenario: Outcome converter produces Pydantic VerifiedField
    Given a PostCallResult with dataclass VerifiedField(claimed="X", verified="Y", match=True)
    When I run postcall_result_to_outcome()
    Then the resulting verified_data should contain Pydantic VerifiedField instances
    And each field should have: claimed="X", verified="Y", match=True

  Scenario: Outcome converter handles dict VerifiedField
    Given a PostCallResult with dict verified_data entries
    When I run postcall_result_to_outcome()
    Then the resulting verified_data should contain Pydantic VerifiedField instances

  # === Outcome equivalence across paths ===

  Scenario: Live Form Filler outcome matches PostCallProcessor outcome schema
    Given identical verification data processed through both paths:
      | Field      | Claimed    | Verified   | Match |
      | start_date | 2019-03-01 | 2019-03-01 | true  |
      | position   | Engineer   | Engineer   | true  |
    When both outcomes are serialized with model_dump(mode="json")
    Then the JSON schemas should be identical
    And both should contain was_employed, employment_status, verified_data, verifier

  Scenario: Database writer accepts outcomes from both paths
    Given a VerificationOutcome from the Live Form Filler path
    And a VerificationOutcome from the PostCallProcessor path
    When both are passed to write_verification_to_case()
    Then both should succeed without type errors

  # === Field name validation ===

  Scenario: outcome_builder warns on unknown field names
    Given a FormSubmissionRequest with field_name="unknown_field"
    When build_verification_outcome() processes it
    Then a warning should be logged for "unknown_field"
    But the outcome should still be created (non-blocking)

  Scenario: outcome_builder accepts all known field names
    Given FormSubmissionRequest fields with names:
      | Field Name             |
      | start_date             |
      | end_date               |
      | position_title         |
      | supervisor_name        |
      | employment_type        |
      | eligibility_for_rehire |
      | reason_for_leaving     |
      | salary                 |
    When build_verification_outcome() processes them
    Then no warnings should be logged

  # === Integration: end-to-end outcome storage ===

  Scenario: Outcome stored in cases.verification_results matches canonical schema
    Given a completed verification through either path
    When I query cases.verification_results for the case
    Then the JSONB should deserialize into a valid VerificationOutcome model
    And it should contain: was_employed, employment_status, verified_data, verifier, confidence
