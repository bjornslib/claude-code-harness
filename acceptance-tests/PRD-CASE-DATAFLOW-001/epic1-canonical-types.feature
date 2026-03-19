Feature: E1 — Canonical Type Definitions & Contract
  As a platform engineer
  I want a single source of truth for all work history verification types
  So that field name mismatches are caught at build time

  Background:
    Given the Pydantic models in "models/work_history.py" are the canonical types
    And the TypeScript types in "lib/types/work-history.generated.ts" mirror them

  # === M1: VerifyFields rehire_eligibility alias ===

  Scenario: VerifyFields accepts eligibility_for_rehire (canonical name)
    When I create a VerifyFields instance with eligibility_for_rehire=True
    Then the model should be valid
    And eligibility_for_rehire should be True

  Scenario: VerifyFields accepts rehire_eligibility (frontend compat alias)
    When I create a VerifyFields instance with rehire_eligibility=True
    Then the model should be valid
    And eligibility_for_rehire should be True

  Scenario: VerifyFields serializes to canonical name
    Given a VerifyFields instance created with rehire_eligibility=True
    When I call model_dump()
    Then the key should be "eligibility_for_rehire" not "rehire_eligibility"

  # === M3: EmployerInfo contact field aliases ===

  Scenario: EmployerInfo accepts hr_contact_name (canonical name)
    When I create an EmployerInfo with hr_contact_name="Jane Doe"
    Then the model should be valid
    And hr_contact_name should be "Jane Doe"

  Scenario: EmployerInfo accepts contact_name (frontend compat alias)
    When I create an EmployerInfo with contact_name="Jane Doe"
    Then the model should be valid
    And hr_contact_name should be "Jane Doe"

  Scenario: EmployerInfo accepts hr_email (canonical name)
    When I create an EmployerInfo with hr_email="hr@company.com"
    Then the model should be valid
    And hr_email should be "hr@company.com"

  Scenario: EmployerInfo accepts contact_email (frontend compat alias)
    When I create an EmployerInfo with contact_email="hr@company.com"
    Then the model should be valid
    And hr_email should be "hr@company.com"

  # === M6: was_employed logic ===

  Scenario: was_employed is True for VERIFIED status
    Given a VerificationOutcome with employment_status="verified"
    Then was_employed should be True

  Scenario: was_employed is True for PARTIAL_VERIFICATION status
    Given a VerificationOutcome with employment_status="partial_verification"
    Then was_employed should be True

  Scenario: was_employed is False for FAILED_VERIFICATION status
    Given a VerificationOutcome with employment_status="failed_verification"
    Then was_employed should be False

  Scenario: was_employed derivation does not reference currently_employed
    Given the outcome_converter module
    When I search for the string "currently_employed" in was_employed logic
    Then it should only appear in the legacy mapping, not in the comparison set

  # === M5: Single VerifiedField type ===

  Scenario: VerifiedField is Pydantic BaseModel
    Given the VerifiedField class from models/work_history.py
    Then it should be a subclass of pydantic.BaseModel
    And it should have fields: claimed, verified, match

  Scenario: Outcome converter produces Pydantic VerifiedField from dataclass
    Given a PostCallResult with dataclass VerifiedField objects
    When I run postcall_result_to_outcome()
    Then all VerifiedField objects in the result should be Pydantic BaseModel instances

  # === TypeScript type generation ===

  Scenario: TypeScript types file exists and matches Pydantic
    Given the generate_ts_types.py script has been run
    Then "lib/types/work-history.generated.ts" should exist
    And it should contain interfaces: VerifyFields, EmployerInfo, EmploymentClaim
    And VerifyFields interface should contain "eligibility_for_rehire" not "rehire_eligibility"

  Scenario: TypeScript types compile without errors
    Given "lib/types/work-history.generated.ts" exists
    When I run the TypeScript compiler on the file
    Then there should be zero compilation errors
