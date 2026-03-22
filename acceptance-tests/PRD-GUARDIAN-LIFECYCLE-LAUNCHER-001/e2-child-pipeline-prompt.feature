Feature: E2 — System Prompt Child Pipeline Creation
  Guardian system prompt teaches template instantiation for PLAN nodes

  Scenario: Template instantiation instructions in prompt
    Given guardian.py exists
    When I read the system prompt from build_system_prompt()
    Then it contains "template instantiate" or "instantiate_template"
    And it contains instructions for generating a child pipeline DOT
    # Scoring: 0.0 if no template instructions, 1.0 if complete

  Scenario: Plan JSON format specified
    Given guardian.py exists
    When I read the system prompt
    Then it contains "plan.json" format specification
    And the format includes: dot_path, template, tasks fields
    # Scoring: 0.0 if no format, 1.0 if complete spec

  Scenario: Refined BS reading pattern
    Given guardian.py exists
    When I read the system prompt
    Then it contains instructions to read "state/{id}-refined.md"
    And it contains instructions to break BS into implementation tasks
    # Scoring: 0.0 if no pattern, 1.0 if complete
