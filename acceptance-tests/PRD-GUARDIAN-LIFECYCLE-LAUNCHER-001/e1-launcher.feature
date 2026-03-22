Feature: E1 — Lifecycle Launcher Function
  Guardian can auto-launch a lifecycle pipeline from a PRD path

  Scenario: --lifecycle flag exists
    When I run "python3 cobuilder/engine/guardian.py --help"
    Then the output contains "--lifecycle"
    # Scoring: 0.0 if missing, 1.0 if present

  Scenario: Initiative ID derived from PRD filename
    Given a PRD at "docs/prds/PRD-AUTH-001.md"
    When I run "python3 cobuilder/engine/guardian.py --lifecycle docs/prds/PRD-AUTH-001.md --dry-run"
    Then the output JSON contains initiative_id = "AUTH-001"
    # Scoring: 0.0 if wrong derivation, 1.0 if correct

  Scenario: Template instantiation produces valid DOT
    Given a PRD at "docs/prds/PRD-GUARDIAN-LIFECYCLE-LAUNCHER-001.md"
    When I run "python3 cobuilder/engine/guardian.py --lifecycle docs/prds/PRD-GUARDIAN-LIFECYCLE-LAUNCHER-001.md --dry-run"
    Then the output JSON contains dot_path pointing to a valid .dot file
    And "python3 cobuilder/engine/cli.py validate <dot_path>" passes
    # Scoring: 0.0 if invalid DOT, 1.0 if valid

  Scenario: Placeholder state files created
    Given a PRD at "docs/prds/PRD-GUARDIAN-LIFECYCLE-LAUNCHER-001.md"
    When I run "python3 cobuilder/engine/guardian.py --lifecycle docs/prds/PRD-GUARDIAN-LIFECYCLE-LAUNCHER-001.md --dry-run"
    Then state/GUARDIAN-LIFECYCLE-LAUNCHER-001-research.json exists
    And state/GUARDIAN-LIFECYCLE-LAUNCHER-001-refined.md exists
    # Scoring: 0.0 if missing, 1.0 if both exist

  Scenario: Dry-run returns config without launching
    When I run "python3 cobuilder/engine/guardian.py --lifecycle <prd_path> --dry-run"
    Then exit code is 0
    And output is valid JSON with keys: dry_run, initiative_id, prd_path, dot_path, pipeline_id, model
    # Scoring: 0.0 if error, 1.0 if valid config JSON
