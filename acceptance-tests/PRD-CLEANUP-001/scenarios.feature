@prd-cleanup-001 @guardian
Feature: .claude Directory Cleanup Validation

  Background:
    Given the repository is at "claude-harness-setup"
    And the working directory is the repository root

  # ─── Epic 1: Empty / Placeholder Files ─────────────────────────────

  @E1
  Scenario: Empty test file removed
    Then the file ".claude/test" should not exist
    # Scoring: 1.0 = file absent | 0.0 = file present

  @E1
  Scenario: Empty progress directory removed
    Then the directory ".claude/progress/" should not exist
    # Scoring: 1.0 = dir absent | 0.5 = dir exists but empty | 0.0 = dir exists with content

  @E1
  Scenario: Gitkeep placeholders removed from populated directories
    Then the file ".claude/state/.gitkeep" should not exist
    And the file ".claude/evidence/.gitkeep" should not exist
    And the file ".claude/completion-state/.gitkeep" should not exist
    # Scoring: 1.0 = all 3 absent | 0.5 = 1-2 absent | 0.0 = all present

  @E1
  Scenario: Doc-gardener-skip disposition resolved
    Then either ".claude/.doc-gardener-skip" is removed
    Or it is documented as an active flag in a code comment or README
    # Scoring: 1.0 = removed OR documented | 0.0 = still present undocumented

  # ─── Epic 2: Archive Directories ────────────────────────────────────

  @E2
  Scenario: Archived s3-communicator skill removed
    Then the directory ".claude/skills/_archived/s3-communicator/" should not exist
    # Scoring: 1.0 = absent | 0.0 = present

  @E2
  Scenario: Archived hooks directory removed
    Then the directory ".claude/hooks/archive/" should not exist
    # Scoring: 1.0 = absent | 0.0 = present

  # ─── Epic 3: Build Caches ───────────────────────────────────────────

  @E3
  Scenario: No __pycache__ directories under .claude
    When I search for "__pycache__" directories under ".claude/"
    Then zero results are returned
    # Scoring: 1.0 = zero pycache dirs | 0.5 = 1-2 remain | 0.0 = 3+ remain

  @E3
  Scenario: Gitignore prevents pycache re-accumulation
    When I read ".claude/.gitignore"
    Then it contains a line matching "__pycache__"
    # Scoring: 1.0 = pattern present | 0.0 = pattern absent

  # ─── Epic 4: Orphaned Hooks ─────────────────────────────────────────

  @E4
  Scenario: Completion gate hooks removed
    Then the file ".claude/hooks/completion-gate.py" should not exist
    And the file ".claude/hooks/completion-gate.sh" should not exist
    # Scoring: 1.0 = both absent | 0.5 = one absent | 0.0 = both present
    # Red flag: If either is referenced in settings.json (false positive)

  @E4
  Scenario: All hooks in .claude/hooks/ are either in settings.json or documented
    When I list all .py and .sh files in ".claude/hooks/" (excluding archive/)
    Then every file is either:
      - Referenced in ".claude/settings.json" hooks configuration
      - Or is inside a subdirectory that is referenced (e.g., unified_stop_gate/)
      - Or has a comment header explaining its non-settings.json usage
    # Scoring: 1.0 = all accounted for | 0.5 = 1-2 orphans remain | 0.0 = 3+ orphans

  # ─── Epic 5: Project-Specific Content ───────────────────────────────

  @E5
  Scenario: AgenCheck schemas removed
    Then the file ".claude/schemas/v3.9-agent-quick-reference.md" should not exist
    And the file ".claude/schemas/v3.9-contact-schema.md" should not exist
    # Scoring: 1.0 = both absent | 0.0 = either present

  @E5
  Scenario: Old learnings directory cleaned
    Then the directory ".claude/learnings/" should not exist
    Or the directory contains only files relevant to the harness (not agencheck-specific)
    # Scoring: 1.0 = dir absent | 0.5 = dir exists but cleaned | 0.0 = old files remain

  @E5
  Scenario: Example files removed from user-input-queue
    Then the file ".claude/user-input-queue/EXAMPLE-pending.md" should not exist
    And the file ".claude/user-input-queue/EXAMPLE-response.md" should not exist
    # Scoring: 1.0 = both absent | 0.0 = either present

  # ─── Epic 6: Stale Utility Scripts ──────────────────────────────────

  @E6
  Scenario: Each utility script has confirmed references or is removed
    When I check ".claude/utils/" contents
    Then each script either:
      - Has at least one reference in .claude/tests/ or .claude/hooks/ or .claude/settings.json
      - Or has been removed
    # Scoring: 1.0 = all resolved | 0.5 = 1-2 unresolved | 0.0 = all unresolved

  # ─── Epic 7: Stale Commands ─────────────────────────────────────────

  @E7
  Scenario: Project-specific commands investigated and resolved
    Then the following commands are either confirmed useful or removed:
      | command                  |
      | o3-pro.md               |
      | use-codex-support.md    |
      | website-upgraded.md     |
      | parallel-solutioning.md |
      | check-messages.md       |
    # Scoring: 1.0 = all resolved | 0.5 = some resolved | 0.0 = none resolved

  # ─── Epic 8: Stale Runtime State ────────────────────────────────────

  @E8
  Scenario: Signal directories are empty
    When I check ".claude/message-bus/signals/"
    And I check ".claude/attractor/pipelines/signals/"
    Then both directories contain zero files (excluding .gitkeep)
    # Scoring: 1.0 = both empty | 0.5 = one empty | 0.0 = neither empty

  @E8
  Scenario: Stale attractor checkpoints consolidated
    When I count JSON checkpoint files in ".claude/attractor/pipelines/"
    Then at most 1 checkpoint file remains per pipeline (the latest)
    # Scoring: 1.0 = consolidated | 0.5 = reduced but not minimal | 0.0 = unchanged

  @E8
  Scenario: State marker directories cleaned
    When I check files in ".claude/state/gchat-forwarded-ask/"
    And ".claude/state/capability-update/"
    And ".claude/state/hindsight-flush/"
    And ".claude/state/hindsight-narrative/"
    And ".claude/state/hindsight-recall/"
    Then no files older than 7 days remain (excluding .gitkeep)
    # Scoring: 1.0 = all clean | 0.5 = some cleaned | 0.0 = none cleaned

  # ─── Epic 9: Stale Documentation ────────────────────────────────────

  @E9
  Scenario: Each documentation file confirmed current or removed
    When I review the following files in ".claude/documentation/":
      | file                                    |
      | DECISION_TIME_GUIDANCE.md               |
      | STOP_GATE_CONSOLIDATION.md              |
      | NATIVE-TEAMS-EPIC1-FINDINGS.md          |
      | ORCHESTRATOR_ARCHITECTURE_V2.md         |
      | SKILL-DEDUP-AUDIT.md                    |
      | UPDATE-validation-agent-integration.md  |
    Then each is either:
      - Confirmed still relevant and kept
      - Or removed with content verified as superseded
    # Scoring: 1.0 = all resolved | 0.5 = some resolved | 0.0 = none resolved

  @E9
  Scenario: TM_COMMANDS_GUIDE.md disposition resolved
    Then either ".claude/TM_COMMANDS_GUIDE.md" is removed (duplicated by /tm commands)
    Or it contains unique content not available via /tm commands
    # Scoring: 1.0 = removed OR justified | 0.0 = still present unjustified

  # ─── Cross-Cutting: No Regressions ──────────────────────────────────

  @regression
  Scenario: Test suite passes after cleanup
    When I run "pytest .claude/tests/ -q"
    Then the exit code is 0
    And all previously passing tests still pass
    # Scoring: 1.0 = all pass | 0.0 = any failure

  @regression
  Scenario: Git diff shows only deletions
    When I run "git diff --stat HEAD"
    Then the diff shows only file deletions and .gitignore additions
    And no existing file content has been modified (except .gitignore)
    # Scoring: 1.0 = clean diff | 0.5 = minor mods | 0.0 = unexpected changes
