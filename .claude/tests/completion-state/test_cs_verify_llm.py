"""Unit tests for cs-verify-llm.py (Agent SDK verification gate).

Tests the Python module functions directly without launching the Agent SDK
(which requires Claude Code CLI and would be too expensive for unit tests).
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Path to the script
SCRIPTS_DIR = Path(__file__).parent.parent.parent / 'scripts' / 'completion-state'
CS_VERIFY_LLM_SCRIPT = SCRIPTS_DIR / 'cs-verify-llm.py'

# Import the module by loading it manually (script has hyphens, can't use normal import)
import importlib.util
spec = importlib.util.spec_from_file_location("cs_verify_llm", CS_VERIFY_LLM_SCRIPT)
cs_verify_llm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs_verify_llm)


class TestBuildEvaluationPrompt:
    """Tests for build_evaluation_prompt function."""

    def test_basic_prompt_includes_all_sections(self):
        """Prompt includes summary, criteria, and proof sections."""
        summary = "Test promise summary"
        criteria = [
            {"id": "AC-1", "description": "First criterion", "status": "met", "evidence": "Done"}
        ]
        proof = "All tests pass"

        prompt = cs_verify_llm.build_evaluation_prompt(summary, criteria, proof)

        assert "Test promise summary" in prompt
        assert "AC-1" in prompt
        assert "First criterion" in prompt
        assert "All tests pass" in prompt

    def test_prompt_includes_validator_evidence(self):
        """Prompt includes Gate 2 validator assessments when provided."""
        summary = "Test"
        criteria = [
            {"id": "AC-1", "description": "Criterion", "status": "met", "evidence": "Evidence"}
        ]
        proof = ""
        validator_evidence = {
            "AC-1": "Verdict: PASS (confidence: 0.95)\nReasoning: Tests verified"
        }

        prompt = cs_verify_llm.build_evaluation_prompt(summary, criteria, proof, validator_evidence)

        assert "Validator Assessment (Gate 2)" in prompt
        assert "Verdict: PASS" in prompt
        assert "Tests verified" in prompt

    def test_prompt_handles_multiple_criteria(self):
        """Prompt includes all acceptance criteria."""
        summary = "Multi-AC promise"
        criteria = [
            {"id": "AC-1", "description": "First", "status": "met", "evidence": "Done 1"},
            {"id": "AC-2", "description": "Second", "status": "met", "evidence": "Done 2"},
            {"id": "AC-3", "description": "Third", "status": "met", "evidence": "Done 3"},
        ]
        proof = ""

        prompt = cs_verify_llm.build_evaluation_prompt(summary, criteria, proof)

        assert "AC-1" in prompt
        assert "AC-2" in prompt
        assert "AC-3" in prompt
        assert "First" in prompt
        assert "Second" in prompt
        assert "Third" in prompt

    def test_prompt_handles_missing_evidence(self):
        """Prompt shows 'None provided' when evidence is missing."""
        summary = "Test"
        criteria = [
            {"id": "AC-1", "description": "Criterion", "status": "pending"}
        ]
        proof = ""

        prompt = cs_verify_llm.build_evaluation_prompt(summary, criteria, proof)

        assert "None provided" in prompt


class TestLoadValidatorEvidence:
    """Tests for load_validator_evidence function."""

    def test_load_validator_evidence_empty_when_no_dir(self):
        """Returns empty dict when validations directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ['CLAUDE_PROJECT_DIR'] = tmpdir
            result = cs_verify_llm.load_validator_evidence("promise-nonexistent-001")
            assert result == {}

    def test_load_validator_evidence_reads_files(self):
        """Reads validation files and builds evidence map."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ['CLAUDE_PROJECT_DIR'] = tmpdir
            promise_id = "promise-test-001"

            # Create validations directory
            val_dir = Path(tmpdir) / '.claude' / 'completion-state' / 'validations' / promise_id
            val_dir.mkdir(parents=True)

            # Write validation file
            validation_data = {
                "_metadata": {"promise_id": promise_id, "ac_id": "AC-1"},
                "verdict": "PASS",
                "reasoning": "All checks passed",
                "confidence": 0.95,
                "criteria_results": [
                    {"criterion_id": "AC-1", "status": "PASS", "evidence": "Tests pass"}
                ],
            }
            (val_dir / "AC-1-validation.json").write_text(json.dumps(validation_data))

            result = cs_verify_llm.load_validator_evidence(promise_id)

            assert "AC-1" in result
            assert "PASS" in result["AC-1"]
            assert "All checks passed" in result["AC-1"]
            assert "Tests pass" in result["AC-1"]

    def test_load_validator_evidence_derives_ac_id_from_filename(self):
        """Derives AC-ID from filename when _metadata.ac_id is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ['CLAUDE_PROJECT_DIR'] = tmpdir
            promise_id = "promise-test-002"

            val_dir = Path(tmpdir) / '.claude' / 'completion-state' / 'validations' / promise_id
            val_dir.mkdir(parents=True)

            # Write validation file without _metadata.ac_id
            validation_data = {
                "verdict": "PASS",
                "reasoning": "OK",
                "confidence": 0.9,
                "criteria_results": [],
            }
            (val_dir / "AC-2-validation.json").write_text(json.dumps(validation_data))

            result = cs_verify_llm.load_validator_evidence(promise_id)

            assert "AC-2" in result

    def test_load_validator_evidence_skips_invalid_json(self):
        """Skips files with invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ['CLAUDE_PROJECT_DIR'] = tmpdir
            promise_id = "promise-test-003"

            val_dir = Path(tmpdir) / '.claude' / 'completion-state' / 'validations' / promise_id
            val_dir.mkdir(parents=True)

            # Write invalid JSON
            (val_dir / "AC-1-validation.json").write_text("not valid json{{{")

            result = cs_verify_llm.load_validator_evidence(promise_id)

            # Should return empty since the only file is invalid
            assert result == {}

    def test_load_validator_evidence_multiple_files(self):
        """Loads evidence from multiple validation files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ['CLAUDE_PROJECT_DIR'] = tmpdir
            promise_id = "promise-test-004"

            val_dir = Path(tmpdir) / '.claude' / 'completion-state' / 'validations' / promise_id
            val_dir.mkdir(parents=True)

            # Write multiple validation files
            for ac_id in ["AC-1", "AC-2", "AC-3"]:
                validation_data = {
                    "_metadata": {"ac_id": ac_id},
                    "verdict": "PASS",
                    "reasoning": f"Reasoning for {ac_id}",
                    "confidence": 0.9,
                    "criteria_results": [],
                }
                (val_dir / f"{ac_id}-validation.json").write_text(json.dumps(validation_data))

            result = cs_verify_llm.load_validator_evidence(promise_id)

            assert len(result) == 3
            assert "AC-1" in result
            assert "AC-2" in result
            assert "AC-3" in result


class TestWarnResult:
    """Tests for warn_result function (graceful degradation)."""

    def test_warn_result_format(self, capsys):
        """Outputs JSON with verdict=WARN and fallback=True."""
        cs_verify_llm.warn_result("Test warning reason")

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["verdict"] == "WARN"
        assert output["reasoning"] == "Test warning reason"
        assert output["fallback"] is True


# Entry point
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
