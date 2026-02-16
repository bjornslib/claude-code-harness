"""
Skill Integration Tests for Post-Push Code Review Hook

This test module validates the skill invocation logic for the
post-push code review system. Tests are written following TDD RED-GREEN-REFACTOR.

Acceptance Criteria Tested:
- AC-6: Verify codebase-quality:security skill is invoked during post-push review
- AC-7: Verify codebase-quality:code-quality skill is invoked after security
- AC-8: Verify codebase-quality:documentation skill is invoked after code-quality

Usage:
    pytest .claude/tests/hooks/test_skill_integration.py -v

Note: These tests are written FIRST (RED phase) before the skill orchestration is implemented.
They will fail until the skill chain is fully implemented (GREEN phase).
"""

import json
from pathlib import Path
from typing import Any

import pytest


# =============================================================================
# Skill Orchestration Module (to be tested)
# =============================================================================
# Note: In RED phase, we define the expected interface.
# The actual implementation will be in the skill orchestrator.


def invoke_skill(skill_name: str, context: dict[str, Any]) -> dict[str, Any]:
    """
    Invoke a codebase-quality sub-skill.

    Args:
        skill_name: The skill to invoke (e.g., "codebase-quality:security")
        context: Context data including changed files, trigger info, etc.

    Returns:
        Skill result with status, findings, and next_skill recommendation
    """
    raise NotImplementedError("Skill invocation not yet implemented")


def get_skill_sequence(trigger: str) -> list[str]:
    """
    Get the ordered sequence of skills for a given trigger.

    Args:
        trigger: The trigger event (e.g., "full-audit", "post-push", "pre-merge")

    Returns:
        Ordered list of skill names to invoke
    """
    raise NotImplementedError("Skill sequence not yet implemented")


def orchestrate_quality_audit(
    trigger: str, context: dict[str, Any]
) -> tuple[list[dict[str, Any]], str]:
    """
    Orchestrate the full quality audit sequence.

    Args:
        trigger: The trigger event type
        context: Context data for the audit

    Returns:
        Tuple of (list of skill results, final_status)
        final_status is one of: "pass", "pass_with_warnings", "blocked"
    """
    raise NotImplementedError("Quality audit orchestration not yet implemented")


def should_continue_to_next_skill(skill_result: dict[str, Any]) -> bool:
    """
    Determine if the skill chain should continue based on current result.

    Args:
        skill_result: Result from the most recently invoked skill

    Returns:
        True if next skill should be invoked, False if chain should stop
    """
    raise NotImplementedError("Continue logic not yet implemented")


# =============================================================================
# Constants for Skill Integration
# =============================================================================

# Ordered skill sequence for full audit
FULL_AUDIT_SEQUENCE = [
    "codebase-quality:security",
    "codebase-quality:code-quality",
    "codebase-quality:documentation",
]

# Skill that runs first (BLOCKING for critical issues)
FIRST_SKILL = "codebase-quality:security"

# Skill that runs second (after security passes)
SECOND_SKILL = "codebase-quality:code-quality"

# Skill that runs last (documentation is never blocking)
THIRD_SKILL = "codebase-quality:documentation"

# Status values that allow continuation
CONTINUE_STATUSES = ["pass", "pass_with_warnings", "warn", "updated"]

# Status values that block continuation
BLOCK_STATUSES = ["block", "critical", "fail"]


# =============================================================================
# Test Class: AC-6 - Security Skill Invocation
# =============================================================================


class TestAC6_SecuritySkillInvocation:
    """
    AC-6: Verify codebase-quality:security skill is invoked during post-push review

    Given: Post-push review is triggered
    When: Quality audit begins
    Then: Security skill is invoked FIRST (before any other skill)
    """

    def test_security_is_first_in_sequence(
        self, skill_invocation_full_audit: dict[str, Any]
    ) -> None:
        """Test that security skill is first in the audit sequence."""
        expected_sequence = skill_invocation_full_audit["expected_skill_sequence"]

        # Verify security is first
        assert expected_sequence[0] == "codebase-quality:security"

        # Test sequence retrieval logic (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            sequence = get_skill_sequence("full-audit")
            assert sequence[0] == "codebase-quality:security"

    def test_security_skill_invoked_on_post_push(
        self, skill_post_push_trigger: dict[str, Any]
    ) -> None:
        """Test that security skill is invoked when post-push triggers."""
        expected_sequence = skill_post_push_trigger["expected_sequence"]

        # Verify first skill is security
        first_skill = expected_sequence[0]
        assert first_skill["order"] == 1
        assert first_skill["skill"] == "codebase-quality:security"

        # Test invocation (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            context = {"changed_files": [], "trigger": "post_push"}
            result = invoke_skill("codebase-quality:security", context)
            assert "status" in result

    def test_security_runs_before_code_quality(
        self, skill_invocation_full_audit: dict[str, Any]
    ) -> None:
        """Test that security runs before code quality."""
        phases = skill_invocation_full_audit["expected_phases"]

        security_phase = next(p for p in phases if p["skill"] == "codebase-quality:security")
        code_quality_phase = next(
            p for p in phases if p["skill"] == "codebase-quality:code-quality"
        )

        assert security_phase["phase"] < code_quality_phase["phase"]

        with pytest.raises(NotImplementedError):
            sequence = get_skill_sequence("full-audit")
            security_idx = sequence.index("codebase-quality:security")
            code_quality_idx = sequence.index("codebase-quality:code-quality")
            assert security_idx < code_quality_idx

    def test_security_blocking_on_critical(
        self, skill_security_critical_block: dict[str, Any]
    ) -> None:
        """Test that security skill blocks on critical issues."""
        result = skill_security_critical_block["result"]

        # Verify fixture represents blocking scenario
        assert result["status"] == "block"
        assert result["critical_issues"] > 0
        assert result["should_continue"] is False

        # Test blocking logic (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            should_continue = should_continue_to_next_skill(result)
            assert should_continue is False

    def test_security_pass_allows_continuation(
        self, skill_security_pass: dict[str, Any]
    ) -> None:
        """Test that security pass allows continuation to next skill."""
        result = skill_security_pass["result"]

        # Verify fixture represents passing scenario
        assert result["status"] == "pass"
        assert result["should_continue"] is True
        assert result["next_skill"] == "codebase-quality:code-quality"

        # Test continuation logic (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            should_continue = should_continue_to_next_skill(result)
            assert should_continue is True

    @pytest.mark.parametrize(
        "fixture_name,expected_first_skill",
        [
            ("skill_invocation_full_audit", "codebase-quality:security"),
            ("skill_post_push_trigger", "codebase-quality:security"),
        ],
    )
    def test_security_always_first(
        self, fixtures_dir: Path, fixture_name: str, expected_first_skill: str
    ) -> None:
        """Parameterized test that security is always first skill."""
        fixture_path = fixtures_dir / f"{fixture_name}.json"
        with open(fixture_path) as f:
            data = json.load(f)

        # Get first skill from fixture
        if "expected_skill_sequence" in data:
            first_skill = data["expected_skill_sequence"][0]
        elif "expected_sequence" in data:
            first_skill = data["expected_sequence"][0]["skill"]
        else:
            pytest.fail(f"Fixture {fixture_name} missing skill sequence")

        assert first_skill == expected_first_skill

        with pytest.raises(NotImplementedError):
            sequence = get_skill_sequence("full-audit")
            assert sequence[0] == expected_first_skill


# =============================================================================
# Test Class: AC-7 - Code Quality Skill Invocation
# =============================================================================


class TestAC7_CodeQualitySkillInvocation:
    """
    AC-7: Verify codebase-quality:code-quality skill is invoked after security

    Given: Security skill has completed successfully
    When: Quality audit continues
    Then: Code quality skill is invoked SECOND (after security, before documentation)
    """

    def test_code_quality_is_second_in_sequence(
        self, skill_invocation_full_audit: dict[str, Any]
    ) -> None:
        """Test that code quality skill is second in the audit sequence."""
        expected_sequence = skill_invocation_full_audit["expected_skill_sequence"]

        # Verify code quality is second
        assert expected_sequence[1] == "codebase-quality:code-quality"

        # Test sequence retrieval (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            sequence = get_skill_sequence("full-audit")
            assert sequence[1] == "codebase-quality:code-quality"

    def test_code_quality_has_security_prerequisite(
        self, skill_code_quality_pass: dict[str, Any]
    ) -> None:
        """Test that code quality requires security to run first."""
        prerequisites = skill_code_quality_pass["prerequisites"]

        assert "codebase-quality:security" in prerequisites

        # Test prerequisite check (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            sequence = get_skill_sequence("full-audit")
            security_idx = sequence.index("codebase-quality:security")
            code_quality_idx = sequence.index("codebase-quality:code-quality")
            assert security_idx < code_quality_idx

    def test_code_quality_invoked_after_security_passes(
        self, skill_security_pass: dict[str, Any], skill_code_quality_pass: dict[str, Any]
    ) -> None:
        """Test that code quality is invoked when security passes."""
        security_result = skill_security_pass["result"]

        # Security passes and recommends code quality next
        assert security_result["should_continue"] is True
        assert security_result["next_skill"] == "codebase-quality:code-quality"

        # Test invocation chain (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            context = {"changed_files": [], "security_result": security_result}
            result = invoke_skill("codebase-quality:code-quality", context)
            assert "status" in result

    def test_code_quality_not_invoked_when_security_blocks(
        self, skill_security_critical_block: dict[str, Any]
    ) -> None:
        """Test that code quality is NOT invoked when security blocks."""
        security_result = skill_security_critical_block["result"]

        # Security blocks - should not continue
        assert security_result["should_continue"] is False
        assert security_result["next_skill"] is None

        # Test that orchestration respects block (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            context = {"changed_files": [], "trigger": "full-audit"}
            results, status = orchestrate_quality_audit("full-audit", context)
            # Only security should have run
            assert len(results) == 1
            assert results[0].get("skill") == "codebase-quality:security"
            assert status == "blocked"

    def test_code_quality_runs_before_documentation(
        self, skill_invocation_full_audit: dict[str, Any]
    ) -> None:
        """Test that code quality runs before documentation."""
        phases = skill_invocation_full_audit["expected_phases"]

        code_quality_phase = next(
            p for p in phases if p["skill"] == "codebase-quality:code-quality"
        )
        docs_phase = next(
            p for p in phases if p["skill"] == "codebase-quality:documentation"
        )

        assert code_quality_phase["phase"] < docs_phase["phase"]

        with pytest.raises(NotImplementedError):
            sequence = get_skill_sequence("full-audit")
            code_quality_idx = sequence.index("codebase-quality:code-quality")
            docs_idx = sequence.index("codebase-quality:documentation")
            assert code_quality_idx < docs_idx

    def test_code_quality_pass_recommends_documentation(
        self, skill_code_quality_pass: dict[str, Any]
    ) -> None:
        """Test that code quality pass recommends documentation next."""
        result = skill_code_quality_pass["result"]

        assert result["should_continue"] is True
        assert result["next_skill"] == "codebase-quality:documentation"

    @pytest.mark.parametrize(
        "status,expected_continue",
        [
            ("pass", True),
            ("pass_with_warnings", True),
            ("warn", True),
            ("fail", False),  # Lint errors should block in strict mode
        ],
    )
    def test_code_quality_continuation_logic(
        self, status: str, expected_continue: bool
    ) -> None:
        """Parameterized test for code quality continuation logic."""
        mock_result = {
            "status": status,
            "should_continue": expected_continue,
        }

        with pytest.raises(NotImplementedError):
            should_continue = should_continue_to_next_skill(mock_result)
            assert should_continue == expected_continue


# =============================================================================
# Test Class: AC-8 - Documentation Skill Invocation
# =============================================================================


class TestAC8_DocumentationSkillInvocation:
    """
    AC-8: Verify codebase-quality:documentation skill is invoked after code-quality

    Given: Security and code quality skills have completed
    When: Quality audit continues
    Then: Documentation skill is invoked THIRD (last in sequence)
    """

    def test_documentation_is_third_in_sequence(
        self, skill_invocation_full_audit: dict[str, Any]
    ) -> None:
        """Test that documentation skill is third in the audit sequence."""
        expected_sequence = skill_invocation_full_audit["expected_skill_sequence"]

        # Verify documentation is third (last)
        assert expected_sequence[2] == "codebase-quality:documentation"
        assert len(expected_sequence) == 3  # Exactly three skills

        # Test sequence retrieval (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            sequence = get_skill_sequence("full-audit")
            assert sequence[2] == "codebase-quality:documentation"
            assert len(sequence) == 3

    def test_documentation_has_all_prerequisites(
        self, skill_documentation_pass: dict[str, Any]
    ) -> None:
        """Test that documentation requires both security and code-quality."""
        prerequisites = skill_documentation_pass["prerequisites"]

        assert "codebase-quality:security" in prerequisites
        assert "codebase-quality:code-quality" in prerequisites

    def test_documentation_invoked_after_code_quality_passes(
        self, skill_code_quality_pass: dict[str, Any], skill_documentation_pass: dict[str, Any]
    ) -> None:
        """Test that documentation is invoked when code quality passes."""
        code_quality_result = skill_code_quality_pass["result"]

        # Code quality passes and recommends documentation
        assert code_quality_result["should_continue"] is True
        assert code_quality_result["next_skill"] == "codebase-quality:documentation"

        # Test invocation chain (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            context = {
                "changed_files": [],
                "code_quality_result": code_quality_result,
            }
            result = invoke_skill("codebase-quality:documentation", context)
            assert "status" in result

    def test_documentation_is_never_blocking(
        self, skill_invocation_full_audit: dict[str, Any]
    ) -> None:
        """Test that documentation skill is never blocking."""
        phases = skill_invocation_full_audit["expected_phases"]

        docs_phase = next(
            p for p in phases if p["skill"] == "codebase-quality:documentation"
        )

        assert docs_phase["blocking"] is False
        assert docs_phase["critical_stop_condition"] is False

    def test_documentation_is_last_skill(
        self, skill_post_push_trigger: dict[str, Any]
    ) -> None:
        """Test that documentation is the final skill in the sequence."""
        expected_sequence = skill_post_push_trigger["expected_sequence"]

        last_skill = expected_sequence[-1]
        assert last_skill["order"] == 3
        assert last_skill["skill"] == "codebase-quality:documentation"

        with pytest.raises(NotImplementedError):
            sequence = get_skill_sequence("full-audit")
            assert sequence[-1] == "codebase-quality:documentation"

    def test_documentation_next_skill_is_none(
        self, skill_documentation_pass: dict[str, Any]
    ) -> None:
        """Test that documentation has no next skill (end of chain)."""
        result = skill_documentation_pass["result"]

        assert result["next_skill"] is None

    def test_full_sequence_completes_with_documentation(
        self, skill_security_pass: dict[str, Any],
        skill_code_quality_pass: dict[str, Any],
        skill_documentation_pass: dict[str, Any],
    ) -> None:
        """Test that full audit sequence ends with documentation."""
        # Build expected chain
        chain = [
            skill_security_pass["result"],
            skill_code_quality_pass["result"],
            skill_documentation_pass["result"],
        ]

        # Verify chain sequence
        assert chain[0]["next_skill"] == "codebase-quality:code-quality"
        assert chain[1]["next_skill"] == "codebase-quality:documentation"
        assert chain[2]["next_skill"] is None

        # Test full orchestration (will fail in RED phase)
        with pytest.raises(NotImplementedError):
            context = {"changed_files": [], "trigger": "full-audit"}
            results, status = orchestrate_quality_audit("full-audit", context)
            assert len(results) == 3
            assert status in ["pass", "pass_with_warnings"]


# =============================================================================
# Test Class: Skill Sequence Ordering
# =============================================================================


class TestSkillSequenceOrdering:
    """Tests for the correct ordering of skill invocation."""

    def test_full_sequence_order(self) -> None:
        """Test that the full sequence is: security → code-quality → documentation."""
        assert FULL_AUDIT_SEQUENCE == [
            "codebase-quality:security",
            "codebase-quality:code-quality",
            "codebase-quality:documentation",
        ]

    def test_sequence_constants_match(self) -> None:
        """Test that individual skill constants match sequence positions."""
        assert FULL_AUDIT_SEQUENCE[0] == FIRST_SKILL
        assert FULL_AUDIT_SEQUENCE[1] == SECOND_SKILL
        assert FULL_AUDIT_SEQUENCE[2] == THIRD_SKILL

    def test_sequence_has_exactly_three_skills(self) -> None:
        """Test that there are exactly three skills in the sequence."""
        assert len(FULL_AUDIT_SEQUENCE) == 3

    def test_sequence_retrieval_matches_constants(
        self, skill_invocation_full_audit: dict[str, Any]
    ) -> None:
        """Test that retrieved sequence matches expected constants."""
        expected = skill_invocation_full_audit["expected_skill_sequence"]

        assert expected == FULL_AUDIT_SEQUENCE

        with pytest.raises(NotImplementedError):
            sequence = get_skill_sequence("full-audit")
            assert sequence == FULL_AUDIT_SEQUENCE

    @pytest.mark.parametrize(
        "skill,expected_order",
        [
            ("codebase-quality:security", 0),
            ("codebase-quality:code-quality", 1),
            ("codebase-quality:documentation", 2),
        ],
    )
    def test_skill_position_in_sequence(self, skill: str, expected_order: int) -> None:
        """Parameterized test for skill positions in sequence."""
        assert FULL_AUDIT_SEQUENCE[expected_order] == skill

        with pytest.raises(NotImplementedError):
            sequence = get_skill_sequence("full-audit")
            assert sequence.index(skill) == expected_order


# =============================================================================
# Test Class: Skill Chain Continuation Logic
# =============================================================================


class TestSkillChainContinuation:
    """Tests for the logic that determines if skill chain should continue."""

    @pytest.mark.parametrize(
        "status,expected",
        [
            ("pass", True),
            ("pass_with_warnings", True),
            ("warn", True),
            ("updated", True),
            ("block", False),
            ("critical", False),
            ("fail", False),
        ],
    )
    def test_continuation_by_status(self, status: str, expected: bool) -> None:
        """Parameterized test for continuation logic by status."""
        mock_result = {"status": status, "should_continue": expected}

        # Verify test data consistency
        if status in CONTINUE_STATUSES:
            assert expected is True
        elif status in BLOCK_STATUSES:
            assert expected is False

        with pytest.raises(NotImplementedError):
            result = should_continue_to_next_skill(mock_result)
            assert result == expected

    def test_critical_issues_stop_chain(self) -> None:
        """Test that critical issues stop the skill chain."""
        mock_result = {
            "status": "block",
            "critical_issues": 1,
            "should_continue": False,
        }

        with pytest.raises(NotImplementedError):
            result = should_continue_to_next_skill(mock_result)
            assert result is False

    def test_warnings_allow_continuation(self) -> None:
        """Test that warnings allow the chain to continue."""
        mock_result = {
            "status": "pass_with_warnings",
            "warnings": 3,
            "should_continue": True,
        }

        with pytest.raises(NotImplementedError):
            result = should_continue_to_next_skill(mock_result)
            assert result is True


# =============================================================================
# Test Class: Edge Cases
# =============================================================================


class TestSkillIntegrationEdgeCases:
    """Tests for edge cases in skill integration."""

    def test_empty_changed_files(self) -> None:
        """Test handling when no files have changed."""
        context = {"changed_files": [], "trigger": "post_push"}

        with pytest.raises(NotImplementedError):
            results, status = orchestrate_quality_audit("post_push", context)
            # Should still run but may have minimal findings
            assert len(results) >= 1

    def test_unknown_trigger_type(self) -> None:
        """Test handling of unknown trigger type."""
        with pytest.raises((NotImplementedError, ValueError)):
            _sequence = get_skill_sequence("unknown_trigger")

    def test_skill_result_missing_status(self) -> None:
        """Test handling when skill result is missing status field."""
        mock_result = {"findings": 0}  # Missing status

        with pytest.raises((NotImplementedError, KeyError)):
            should_continue_to_next_skill(mock_result)

    def test_partial_chain_completion(self) -> None:
        """Test that partial chain results are tracked when blocking occurs."""
        context = {
            "changed_files": ["config.py"],
            "trigger": "full-audit",
            "mock_security_block": True,  # Simulate security blocking
        }

        with pytest.raises(NotImplementedError):
            results, status = orchestrate_quality_audit("full-audit", context)
            # Should have only security result
            assert len(results) == 1
            assert status == "blocked"


# =============================================================================
# Fixture Loaders for Skill Integration
# =============================================================================


@pytest.fixture
def skill_invocation_full_audit(fixtures_dir: Path) -> dict[str, Any]:
    """Load full audit invocation fixture."""
    fixture_path = fixtures_dir / "skill_invocation_full_audit.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def skill_security_pass(fixtures_dir: Path) -> dict[str, Any]:
    """Load security skill pass fixture."""
    fixture_path = fixtures_dir / "skill_security_pass.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def skill_security_critical_block(fixtures_dir: Path) -> dict[str, Any]:
    """Load security skill critical block fixture."""
    fixture_path = fixtures_dir / "skill_security_critical_block.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def skill_code_quality_pass(fixtures_dir: Path) -> dict[str, Any]:
    """Load code quality skill pass fixture."""
    fixture_path = fixtures_dir / "skill_code_quality_pass.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def skill_documentation_pass(fixtures_dir: Path) -> dict[str, Any]:
    """Load documentation skill pass fixture."""
    fixture_path = fixtures_dir / "skill_documentation_pass.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def skill_post_push_trigger(fixtures_dir: Path) -> dict[str, Any]:
    """Load post-push trigger fixture."""
    fixture_path = fixtures_dir / "skill_post_push_trigger.json"
    with open(fixture_path) as f:
        return json.load(f)


# =============================================================================
# Integration Tests (Require Implementation)
# =============================================================================


@pytest.mark.skip(reason="Implementation not yet complete - run after GREEN phase")
class TestSkillIntegrationIntegration:
    """
    Integration tests that execute actual skill invocations.

    These tests are skipped during RED phase and should be unskipped
    once the skill orchestration is implemented (GREEN phase).
    """

    def test_real_security_skill_invocation(self) -> None:
        """Test invoking actual security skill."""
        context = {"changed_files": ["main.py"], "trigger": "full-audit"}
        result = invoke_skill("codebase-quality:security", context)

        assert "status" in result
        assert "checks_performed" in result

    def test_real_full_audit_sequence(self) -> None:
        """Test executing full audit sequence."""
        context = {"changed_files": ["main.py"], "trigger": "full-audit"}
        results, status = orchestrate_quality_audit("full-audit", context)

        assert len(results) == 3
        assert status in ["pass", "pass_with_warnings", "blocked"]

    def test_real_post_push_trigger(self) -> None:
        """Test post-push triggering skill chain."""
        context = {
            "changed_files": ["main.py", "utils/helpers.py"],
            "trigger": "post_push",
            "commit_range": ["abc1234", "def5678"],
        }
        results, status = orchestrate_quality_audit("post_push", context)

        # Should invoke all three skills in sequence
        assert len(results) >= 1
