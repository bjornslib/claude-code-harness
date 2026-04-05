Feature: Data Model Integration with Existing contacts.py
  As a maintainer of the shared data layer
  I want employer contacts to use the existing contact models
  So that the codebase does not grow a parallel model hierarchy

  # Scoring: 1.0 = uses existing models exactly as expected, no parallel models
  #          0.7 = correct base model used, minor extra fields or subclass deviations
  #          0.5 = some model reuse, but parallel models also created
  #          0.0 = entirely new parallel model hierarchy created, existing models ignored

  Background:
    Given the project codebase is accessible for static analysis

  @code-analysis
  Scenario: EmployerContact uses existing models/contacts.py — not a parallel model
    Given the file models/contacts.py exists in the codebase
    When searching for EmployerContact (or the equivalent employer contact model)
    Then EmployerContact should be defined in models/contacts.py or import from it
    And there should be no separate models/employer_contact.py or employer_contacts.py file
    And EmployerContact should inherit from or compose the base contact model

  @code-analysis
  Scenario: AdditionalContact is extended with confidence_score field
    Given the AdditionalContact model in models/contacts.py
    Then AdditionalContact should have a field named confidence_score
    And confidence_score should be typed as float
    And confidence_score should have a default value of 0.0 or be Optional[float]
    And confidence_score should have valid range constraints (0.0 to 1.0) or be documented

  @code-analysis
  Scenario: AdditionalContact is extended with is_customer_provided field
    Given the AdditionalContact model in models/contacts.py
    Then AdditionalContact should have a field named is_customer_provided
    And is_customer_provided should be typed as bool
    And is_customer_provided should default to False

  @code-analysis
  Scenario: AdditionalContact is extended with source_url field
    Given the AdditionalContact model in models/contacts.py
    Then AdditionalContact should have a field named source_url
    And source_url should be typed as Optional[str] or Optional[AnyUrl]
    And source_url should default to None

  @code-analysis
  Scenario: Repository stores employer contacts to university_contacts table
    Given the contact repository implementation
    When employer contacts are persisted
    Then the repository should write to the university_contacts table (or equivalent shared table)
    And the stored record should include entity_type set to the string "employer"
    And the stored record should not be written to a separate employer_contacts table

  @code-analysis
  Scenario: No duplicate Pydantic model definitions for contact fields
    Given all Python files in the models/ directory
    When searching for contact-related Pydantic models
    Then fields like phone, email, name should be defined once in the base model
    And employer-specific models should not redefine fields that already exist on the base
    And there should be at most one canonical definition of AdditionalContact

  @code-analysis
  Scenario: PrioritizedContactList is a typed Pydantic model
    Given the classifier or service output type
    Then PrioritizedContactList should be a Pydantic BaseModel or dataclass
    And it should contain a typed list field of contact items (e.g. contacts: list[AdditionalContact])
    And it should be importable from a single known module path
