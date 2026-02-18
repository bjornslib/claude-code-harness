"""Integration tests for cs-verify Gate 2 enforcement and cs-store-validation.

Tests the triple-gate verification system for completion promises:
1. cs-store-validation — stores validation responses linked to promise + AC
2. cs-verify Gate 2 — checks that all ACs have passing validation responses
3. Full lifecycle — create promise, meet ACs, store validations, verify
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import pytest


# === Fixtures ===


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory with completion state structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        promises_dir = Path(tmpdir) / '.claude' / 'completion-state' / 'promises'
        history_dir = Path(tmpdir) / '.claude' / 'completion-state' / 'history'
        validations_dir = Path(tmpdir) / '.claude' / 'completion-state' / 'validations'
        promises_dir.mkdir(parents=True, exist_ok=True)
        history_dir.mkdir(parents=True, exist_ok=True)
        validations_dir.mkdir(parents=True, exist_ok=True)
        yield tmpdir


@pytest.fixture
def scripts_dir():
    """Get the path to the cs-* scripts."""
    script_dir = Path(__file__).parent.parent.parent / 'scripts' / 'completion-state'
    return script_dir


@pytest.fixture
def test_session_id():
    """Generate a unique test session ID."""
    return f"test-session-{int(time.time() * 1000)}"


# === Helpers ===


def run_cs_command(scripts_dir, command, args, env=None, cwd=None):
    """Run a cs-* command and return the result."""
    script_path = scripts_dir / command
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    result = subprocess.run(
        ['bash', str(script_path)] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=full_env,
        timeout=30,
    )
    return result


def create_promise_with_acs(promises_dir, promise_id, session_id, acs, status="in_progress"):
    """Write a promise JSON file directly for testing."""
    acceptance_criteria = [
        {"id": f"AC-{i+1}", "description": desc, "status": "pending", "evidence": None}
        for i, desc in enumerate(acs)
    ]
    promise = {
        "id": promise_id,
        "summary": f"Test promise {promise_id}",
        "status": status,
        "scope": "testing",
        "ownership": {
            "owned_by": session_id,
            "created_by": session_id,
            "created_at": "2026-02-17T00:00:00Z",
            "owned_since": "2026-02-17T00:00:00Z",
        },
        "acceptance_criteria": acceptance_criteria,
        "created_at": "2026-02-17T00:00:00Z",
    }
    promise_file = Path(promises_dir) / f"{promise_id}.json"
    promise_file.write_text(json.dumps(promise, indent=2))
    return promise


def create_validation_response(validations_dir, promise_id, ac_id, verdict="PASS"):
    """Write a validation response file."""
    response = {
        "task_id": f"beads-test-{ac_id.lower()}",
        "verdict": verdict,
        "criteria_results": [
            {"criterion_id": ac_id, "status": verdict, "evidence": f"Test evidence for {ac_id}"}
        ],
        "timestamp": "2026-02-17T00:00:00Z",
        "confidence": 0.95,
        "reasoning": f"Test reasoning for {ac_id}",
    }
    promise_val_dir = Path(validations_dir) / promise_id
    promise_val_dir.mkdir(parents=True, exist_ok=True)
    target = promise_val_dir / f"{ac_id}-validation.json"
    target.write_text(json.dumps(response, indent=2))
    return response


def meet_all_acs(promises_dir, promise_id):
    """Mark all acceptance criteria as met in a promise file."""
    promise_file = Path(promises_dir) / f"{promise_id}.json"
    promise = json.loads(promise_file.read_text())
    for ac in promise.get("acceptance_criteria", []):
        ac["status"] = "met"
        ac["evidence"] = f"Test evidence for {ac['id']}"
    promise_file.write_text(json.dumps(promise, indent=2))


def get_promises_dir(temp_project_dir):
    return Path(temp_project_dir) / '.claude' / 'completion-state' / 'promises'


def get_validations_dir(temp_project_dir):
    return Path(temp_project_dir) / '.claude' / 'completion-state' / 'validations'


def get_history_dir(temp_project_dir):
    return Path(temp_project_dir) / '.claude' / 'completion-state' / 'history'


# === Tests for cs-store-validation ===


class TestCsStoreValidation:
    """Tests for the cs-store-validation command."""

    def test_store_validation_success(self, temp_project_dir, scripts_dir, test_session_id):
        """Store a PASS validation response, verify file created at correct path."""
        promises_dir = get_promises_dir(temp_project_dir)
        validations_dir = get_validations_dir(temp_project_dir)
        promise_id = "promise-store-test-001"

        # Create the promise so cs-store-validation finds it
        create_promise_with_acs(
            promises_dir, promise_id, test_session_id,
            ["First criterion", "Second criterion"],
        )

        response_json = json.dumps({
            "task_id": "beads-xyz-001",
            "verdict": "PASS",
            "criteria_results": [
                {"criterion_id": "AC-1", "status": "PASS", "evidence": "Tests pass"}
            ],
            "timestamp": "2026-02-17T12:00:00Z",
            "confidence": 0.95,
            "reasoning": "All checks passed",
        })

        env = {
            'CLAUDE_PROJECT_DIR': temp_project_dir,
            'CLAUDE_SESSION_ID': test_session_id,
        }

        result = run_cs_command(
            scripts_dir, 'cs-store-validation',
            ['--promise', promise_id, '--ac-id', 'AC-1', '--response', response_json],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert 'STORED:' in result.stdout

        # Verify file was created at the correct path
        stored_file = validations_dir / promise_id / 'AC-1-validation.json'
        assert stored_file.exists(), f"Expected validation file at {stored_file}"

        stored = json.loads(stored_file.read_text())
        assert stored['verdict'] == 'PASS'
        assert stored['task_id'] == 'beads-xyz-001'

    def test_store_validation_requires_promise_id(self, temp_project_dir, scripts_dir):
        """Missing --promise exits with error."""
        env = {'CLAUDE_PROJECT_DIR': temp_project_dir}

        result = run_cs_command(
            scripts_dir, 'cs-store-validation',
            ['--ac-id', 'AC-1', '--response', '{}'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode != 0
        assert '--promise is required' in result.stderr

    def test_store_validation_requires_ac_id(self, temp_project_dir, scripts_dir):
        """Missing --ac-id exits with error."""
        env = {'CLAUDE_PROJECT_DIR': temp_project_dir}

        result = run_cs_command(
            scripts_dir, 'cs-store-validation',
            ['--promise', 'promise-xxx', '--response', '{}'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode != 0
        assert '--ac-id is required' in result.stderr

    def test_store_validation_requires_response(self, temp_project_dir, scripts_dir):
        """Missing --response and --response-file exits with error."""
        env = {'CLAUDE_PROJECT_DIR': temp_project_dir}

        result = run_cs_command(
            scripts_dir, 'cs-store-validation',
            ['--promise', 'promise-xxx', '--ac-id', 'AC-1'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode != 0
        assert '--response or --response-file is required' in result.stderr

    def test_store_validation_rejects_invalid_json(self, temp_project_dir, scripts_dir, test_session_id):
        """Garbage JSON exits with error."""
        promises_dir = get_promises_dir(temp_project_dir)
        promise_id = "promise-badjson-001"
        create_promise_with_acs(promises_dir, promise_id, test_session_id, ["Criterion"])

        env = {
            'CLAUDE_PROJECT_DIR': temp_project_dir,
            'CLAUDE_SESSION_ID': test_session_id,
        }

        result = run_cs_command(
            scripts_dir, 'cs-store-validation',
            ['--promise', promise_id, '--ac-id', 'AC-1', '--response', 'not-valid-json{{{'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode != 0
        assert 'Invalid JSON' in result.stderr

    def test_store_validation_rejects_invalid_verdict(self, temp_project_dir, scripts_dir, test_session_id):
        """verdict="UNKNOWN" is rejected."""
        promises_dir = get_promises_dir(temp_project_dir)
        promise_id = "promise-badverdict-001"
        create_promise_with_acs(promises_dir, promise_id, test_session_id, ["Criterion"])

        response_json = json.dumps({
            "task_id": "beads-xyz",
            "verdict": "UNKNOWN",
            "criteria_results": [],
            "timestamp": "2026-02-17T12:00:00Z",
        })

        env = {
            'CLAUDE_PROJECT_DIR': temp_project_dir,
            'CLAUDE_SESSION_ID': test_session_id,
        }

        result = run_cs_command(
            scripts_dir, 'cs-store-validation',
            ['--promise', promise_id, '--ac-id', 'AC-1', '--response', response_json],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode != 0
        assert 'Invalid verdict' in result.stderr

    def test_store_validation_rejects_missing_fields(self, temp_project_dir, scripts_dir, test_session_id):
        """JSON missing required fields (task_id, verdict, criteria_results, timestamp)."""
        promises_dir = get_promises_dir(temp_project_dir)
        promise_id = "promise-missfields-001"
        create_promise_with_acs(promises_dir, promise_id, test_session_id, ["Criterion"])

        # Only has verdict -- missing task_id, criteria_results, timestamp
        response_json = json.dumps({"verdict": "PASS"})

        env = {
            'CLAUDE_PROJECT_DIR': temp_project_dir,
            'CLAUDE_SESSION_ID': test_session_id,
        }

        result = run_cs_command(
            scripts_dir, 'cs-store-validation',
            ['--promise', promise_id, '--ac-id', 'AC-1', '--response', response_json],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode != 0
        assert 'missing required fields' in result.stderr.lower()
        # Should mention at least one missing field
        assert 'task_id' in result.stderr or 'criteria_results' in result.stderr or 'timestamp' in result.stderr

    def test_store_validation_adds_metadata(self, temp_project_dir, scripts_dir, test_session_id):
        """Stored file includes _metadata wrapper with promise_id, ac_id, stored_at."""
        promises_dir = get_promises_dir(temp_project_dir)
        validations_dir = get_validations_dir(temp_project_dir)
        promise_id = "promise-meta-001"
        create_promise_with_acs(promises_dir, promise_id, test_session_id, ["Criterion"])

        response_json = json.dumps({
            "task_id": "beads-meta-test",
            "verdict": "PASS",
            "criteria_results": [
                {"criterion_id": "AC-1", "status": "PASS", "evidence": "OK"}
            ],
            "timestamp": "2026-02-17T12:00:00Z",
        })

        env = {
            'CLAUDE_PROJECT_DIR': temp_project_dir,
            'CLAUDE_SESSION_ID': test_session_id,
        }

        result = run_cs_command(
            scripts_dir, 'cs-store-validation',
            ['--promise', promise_id, '--ac-id', 'AC-1', '--response', response_json],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"

        stored_file = validations_dir / promise_id / 'AC-1-validation.json'
        stored = json.loads(stored_file.read_text())

        assert '_metadata' in stored
        assert stored['_metadata']['promise_id'] == promise_id
        assert stored['_metadata']['ac_id'] == 'AC-1'
        assert 'stored_at' in stored['_metadata']

    def test_store_validation_from_file(self, temp_project_dir, scripts_dir, test_session_id):
        """Use --response-file to read from a JSON file."""
        promises_dir = get_promises_dir(temp_project_dir)
        validations_dir = get_validations_dir(temp_project_dir)
        promise_id = "promise-fromfile-001"
        create_promise_with_acs(promises_dir, promise_id, test_session_id, ["Criterion"])

        response_data = {
            "task_id": "beads-fileinput",
            "verdict": "PASS",
            "criteria_results": [
                {"criterion_id": "AC-1", "status": "PASS", "evidence": "File-based test"}
            ],
            "timestamp": "2026-02-17T12:00:00Z",
            "confidence": 0.99,
        }

        # Write response to a temp file
        response_file = Path(temp_project_dir) / 'test-response.json'
        response_file.write_text(json.dumps(response_data, indent=2))

        env = {
            'CLAUDE_PROJECT_DIR': temp_project_dir,
            'CLAUDE_SESSION_ID': test_session_id,
        }

        result = run_cs_command(
            scripts_dir, 'cs-store-validation',
            ['--promise', promise_id, '--ac-id', 'AC-1', '--response-file', str(response_file)],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert 'STORED:' in result.stdout

        stored_file = validations_dir / promise_id / 'AC-1-validation.json'
        stored = json.loads(stored_file.read_text())
        assert stored['task_id'] == 'beads-fileinput'
        assert stored['verdict'] == 'PASS'


# === Tests for cs-verify Gate 2 ===


class TestCsVerifyGate2:
    """Tests for cs-verify Gate 2 enforcement (validation response checks)."""

    def test_verify_blocks_without_validation_responses(self, temp_project_dir, scripts_dir, test_session_id):
        """cs-verify on a promise with ACs but no validation files -> exit 1 with Gate 2 BLOCKED."""
        promises_dir = get_promises_dir(temp_project_dir)
        promise_id = "promise-noval-001"

        create_promise_with_acs(
            promises_dir, promise_id, test_session_id,
            ["Must pass unit tests", "Must pass integration tests"],
        )
        meet_all_acs(promises_dir, promise_id)

        env = {
            'CLAUDE_SESSION_ID': test_session_id,
            'CLAUDE_PROJECT_DIR': temp_project_dir,
        }

        result = run_cs_command(
            scripts_dir, 'cs-verify',
            ['--promise', promise_id, '--type', 'test'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode != 0
        assert 'Gate 2 BLOCKED' in result.stderr

    def test_verify_passes_with_all_validations_pass(self, temp_project_dir, scripts_dir, test_session_id):
        """All ACs have validation files with verdict=PASS -> Gate 2 passes."""
        promises_dir = get_promises_dir(temp_project_dir)
        validations_dir = get_validations_dir(temp_project_dir)
        promise_id = "promise-allpass-001"

        create_promise_with_acs(
            promises_dir, promise_id, test_session_id,
            ["Unit tests pass", "Integration tests pass"],
        )
        meet_all_acs(promises_dir, promise_id)

        # Store PASS validation for each AC
        create_validation_response(validations_dir, promise_id, "AC-1", "PASS")
        create_validation_response(validations_dir, promise_id, "AC-2", "PASS")

        env = {
            'CLAUDE_SESSION_ID': test_session_id,
            'CLAUDE_PROJECT_DIR': temp_project_dir,
        }

        result = run_cs_command(
            scripts_dir, 'cs-verify',
            ['--promise', promise_id, '--type', 'test'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert 'VERIFIED:' in result.stdout

    def test_verify_blocks_on_fail_verdict(self, temp_project_dir, scripts_dir, test_session_id):
        """One AC has verdict=FAIL -> exit 1 with FAILED."""
        promises_dir = get_promises_dir(temp_project_dir)
        validations_dir = get_validations_dir(temp_project_dir)
        promise_id = "promise-onefail-001"

        create_promise_with_acs(
            promises_dir, promise_id, test_session_id,
            ["Unit tests pass", "Integration tests pass"],
        )
        meet_all_acs(promises_dir, promise_id)

        create_validation_response(validations_dir, promise_id, "AC-1", "PASS")
        create_validation_response(validations_dir, promise_id, "AC-2", "FAIL")

        env = {
            'CLAUDE_SESSION_ID': test_session_id,
            'CLAUDE_PROJECT_DIR': temp_project_dir,
        }

        result = run_cs_command(
            scripts_dir, 'cs-verify',
            ['--promise', promise_id, '--type', 'test'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode != 0
        assert 'FAIL' in result.stderr

    def test_verify_passes_on_partial_verdict(self, temp_project_dir, scripts_dir, test_session_id):
        """verdict=PARTIAL is acceptable (not blocked)."""
        promises_dir = get_promises_dir(temp_project_dir)
        validations_dir = get_validations_dir(temp_project_dir)
        promise_id = "promise-partial-001"

        create_promise_with_acs(
            promises_dir, promise_id, test_session_id,
            ["Unit tests pass"],
        )
        meet_all_acs(promises_dir, promise_id)

        create_validation_response(validations_dir, promise_id, "AC-1", "PARTIAL")

        env = {
            'CLAUDE_SESSION_ID': test_session_id,
            'CLAUDE_PROJECT_DIR': temp_project_dir,
        }

        result = run_cs_command(
            scripts_dir, 'cs-verify',
            ['--promise', promise_id, '--type', 'test'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert 'VERIFIED:' in result.stdout

    def test_verify_skip_validation_check_flag(self, temp_project_dir, scripts_dir, test_session_id):
        """--skip-validation-check bypasses Gate 2 entirely."""
        promises_dir = get_promises_dir(temp_project_dir)
        promise_id = "promise-skipgate2-001"

        create_promise_with_acs(
            promises_dir, promise_id, test_session_id,
            ["Must pass unit tests"],
        )
        meet_all_acs(promises_dir, promise_id)

        # No validation responses stored -- would normally block at Gate 2

        env = {
            'CLAUDE_SESSION_ID': test_session_id,
            'CLAUDE_PROJECT_DIR': temp_project_dir,
        }

        result = run_cs_command(
            scripts_dir, 'cs-verify',
            ['--promise', promise_id, '--type', 'test', '--skip-validation-check'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert 'VERIFIED:' in result.stdout
        assert 'Skipping Gate 2' in result.stderr

    def test_verify_skips_gate2_for_legacy_promises(self, temp_project_dir, scripts_dir, test_session_id):
        """Promise without acceptance_criteria (legacy) skips Gate 2."""
        promises_dir = get_promises_dir(temp_project_dir)
        promise_id = "promise-legacy-001"

        # Legacy promise: no acceptance_criteria key
        promise = {
            "id": promise_id,
            "summary": "Legacy test promise",
            "status": "in_progress",
            "scope": "testing",
            "ownership": {
                "owned_by": test_session_id,
                "created_by": test_session_id,
                "created_at": "2026-02-17T00:00:00Z",
                "owned_since": "2026-02-17T00:00:00Z",
            },
            "created_at": "2026-02-17T00:00:00Z",
        }
        promise_file = promises_dir / f"{promise_id}.json"
        promise_file.write_text(json.dumps(promise, indent=2))

        env = {
            'CLAUDE_SESSION_ID': test_session_id,
            'CLAUDE_PROJECT_DIR': temp_project_dir,
        }

        # Legacy promises require --proof
        result = run_cs_command(
            scripts_dir, 'cs-verify',
            ['--promise', promise_id, '--type', 'test', '--proof', 'All tests pass'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert 'VERIFIED:' in result.stdout


# === Tests for cs-verify --check mode ===


class TestCsVerifyCheckMode:
    """Tests for cs-verify --check mode used by the stop hook."""

    def test_check_blocks_with_unmet_criteria(self, temp_project_dir, scripts_dir, test_session_id):
        """--check shows per-AC status and NEXT ACTION hint."""
        promises_dir = get_promises_dir(temp_project_dir)
        promise_id = "promise-checkunmet-001"

        create_promise_with_acs(
            promises_dir, promise_id, test_session_id,
            ["First criterion", "Second criterion"],
        )
        # Mark only AC-1 as met, leave AC-2 pending
        promise_file = promises_dir / f"{promise_id}.json"
        promise = json.loads(promise_file.read_text())
        promise["acceptance_criteria"][0]["status"] = "met"
        promise["acceptance_criteria"][0]["evidence"] = "Done"
        promise_file.write_text(json.dumps(promise, indent=2))

        env = {
            'CLAUDE_SESSION_ID': test_session_id,
            'CLAUDE_PROJECT_DIR': temp_project_dir,
        }

        result = run_cs_command(
            scripts_dir, 'cs-verify',
            ['--check'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode == 2
        assert 'COMPLETION CRITERIA NOT MET' in result.stdout
        assert '[MET]' in result.stdout
        assert '[PENDING]' in result.stdout
        assert 'NEXT ACTION' in result.stdout
        # Should suggest cs-promise --meet for the unmet AC
        assert 'cs-promise --meet' in result.stdout

    def test_check_passes_when_no_promises(self, temp_project_dir, scripts_dir, test_session_id):
        """No promises owned -> exit 0."""
        env = {
            'CLAUDE_SESSION_ID': test_session_id,
            'CLAUDE_PROJECT_DIR': temp_project_dir,
        }

        result = run_cs_command(
            scripts_dir, 'cs-verify',
            ['--check'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode == 0

    def test_check_verbose_shows_detail(self, temp_project_dir, scripts_dir, test_session_id):
        """--check --verbose shows criterion-level detail."""
        env = {
            'CLAUDE_SESSION_ID': test_session_id,
            'CLAUDE_PROJECT_DIR': temp_project_dir,
        }

        # With no promises, verbose should say "No promises owned"
        result = run_cs_command(
            scripts_dir, 'cs-verify',
            ['--check', '--verbose'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode == 0
        assert 'No promises owned' in result.stdout


# === Full lifecycle test ===


class TestVerifyFullLifecycle:
    """End-to-end lifecycle: create promise with ACs, meet all, store validations, verify."""

    def test_full_lifecycle_create_meet_store_verify(self, temp_project_dir, scripts_dir, test_session_id):
        """End-to-end: create -> start -> meet ACs -> store validations -> verify -> history."""
        promises_dir = get_promises_dir(temp_project_dir)
        validations_dir = get_validations_dir(temp_project_dir)
        history_dir = get_history_dir(temp_project_dir)

        promise_id = "promise-lifecycle-001"

        env = {
            'CLAUDE_SESSION_ID': test_session_id,
            'CLAUDE_PROJECT_DIR': temp_project_dir,
        }

        # Step 1: Create promise with ACs (write directly since cs-promise --create
        # does not support inline AC creation -- ACs are added separately)
        acs = ["API endpoint works", "Tests pass", "Documentation updated"]
        create_promise_with_acs(promises_dir, promise_id, test_session_id, acs)

        # Verify promise file exists
        promise_file = promises_dir / f"{promise_id}.json"
        assert promise_file.exists()

        # Step 2: Meet all acceptance criteria
        meet_all_acs(promises_dir, promise_id)

        # Verify all ACs are met
        promise = json.loads(promise_file.read_text())
        for ac in promise["acceptance_criteria"]:
            assert ac["status"] == "met", f"{ac['id']} should be met"

        # Step 3: Store validation responses for each AC
        for i in range(len(acs)):
            ac_id = f"AC-{i+1}"
            response_json = json.dumps({
                "task_id": f"beads-lifecycle-{ac_id.lower()}",
                "verdict": "PASS",
                "criteria_results": [
                    {"criterion_id": ac_id, "status": "PASS", "evidence": f"Validated {ac_id}"}
                ],
                "timestamp": "2026-02-17T12:00:00Z",
                "confidence": 0.98,
                "reasoning": f"Lifecycle test for {ac_id}",
            })

            store_result = run_cs_command(
                scripts_dir, 'cs-store-validation',
                ['--promise', promise_id, '--ac-id', ac_id, '--response', response_json],
                env=env, cwd=temp_project_dir,
            )
            assert store_result.returncode == 0, f"Store AC {ac_id} failed: {store_result.stderr}"

        # Verify validation files exist
        for i in range(len(acs)):
            ac_id = f"AC-{i+1}"
            val_file = validations_dir / promise_id / f"{ac_id}-validation.json"
            assert val_file.exists(), f"Validation file for {ac_id} should exist"

        # Step 4: Verify the promise (should pass Gate 2 now)
        verify_result = run_cs_command(
            scripts_dir, 'cs-verify',
            ['--promise', promise_id, '--type', 'test', '--proof', 'Full lifecycle test passed'],
            env=env, cwd=temp_project_dir,
        )

        assert verify_result.returncode == 0, f"Verify failed: {verify_result.stderr}"
        assert 'VERIFIED:' in verify_result.stdout
        assert 'Gate 2: All validation responses verified' in verify_result.stdout

        # Step 5: Promise should be in history, not in promises
        assert not promise_file.exists(), "Promise should have been moved out of promises/"
        history_file = history_dir / f"{promise_id}.json"
        assert history_file.exists(), "Promise should be in history/"

        # Verify final state
        final = json.loads(history_file.read_text())
        assert final['status'] == 'verified'
        assert final['verification']['type'] == 'test'
        assert final['verification']['proof'] == 'Full lifecycle test passed'
        assert final['verification']['verified_by'] == test_session_id


# === Tests for Gate 3 (Agent SDK) ===


class TestCsVerifyGate3:
    """Tests for cs-verify Gate 3 (Agent SDK verification) integration."""

    def test_verify_runs_gate3_by_default(self, temp_project_dir, scripts_dir, test_session_id):
        """cs-verify runs Gate 3 by default (will degrade gracefully in test env)."""
        promises_dir = get_promises_dir(temp_project_dir)
        validations_dir = get_validations_dir(temp_project_dir)
        promise_id = "promise-gate3-default-001"

        # Create promise with met ACs and passing validations
        create_promise_with_acs(
            promises_dir, promise_id, test_session_id,
            ["Unit tests pass"],
        )
        meet_all_acs(promises_dir, promise_id)
        create_validation_response(validations_dir, promise_id, "AC-1", "PASS")

        env = {
            'CLAUDE_SESSION_ID': test_session_id,
            'CLAUDE_PROJECT_DIR': temp_project_dir,
        }

        # Run without --skip-llm-gate
        result = run_cs_command(
            scripts_dir, 'cs-verify',
            ['--promise', promise_id, '--type', 'test'],
            env=env, cwd=temp_project_dir,
        )

        # In test environment, Agent SDK will not be available (no Claude Code CLI)
        # So it should degrade gracefully with WARN verdict and still verify
        # Look for the Gate 3 execution attempt in output
        combined_output = result.stdout + result.stderr

        # Should either succeed with Gate 3 or gracefully degrade
        if result.returncode == 0:
            # Verification succeeded
            assert 'VERIFIED:' in result.stdout
            # Should mention Gate 3 in some form
            assert 'Gate 3' in combined_output or 'Agent SDK' in combined_output
        else:
            # If it failed, it should be a legitimate failure, not a crash
            # (Agent SDK unavailable should NOT block verification)
            pytest.fail(f"Verification failed unexpectedly: {result.stderr}")

    def test_verify_skip_llm_gate_flag(self, temp_project_dir, scripts_dir, test_session_id):
        """--skip-llm-gate skips Gate 3 entirely, prints warning."""
        promises_dir = get_promises_dir(temp_project_dir)
        validations_dir = get_validations_dir(temp_project_dir)
        promise_id = "promise-skipgate3-001"

        create_promise_with_acs(
            promises_dir, promise_id, test_session_id,
            ["Unit tests pass"],
        )
        meet_all_acs(promises_dir, promise_id)
        create_validation_response(validations_dir, promise_id, "AC-1", "PASS")

        env = {
            'CLAUDE_SESSION_ID': test_session_id,
            'CLAUDE_PROJECT_DIR': temp_project_dir,
        }

        result = run_cs_command(
            scripts_dir, 'cs-verify',
            ['--promise', promise_id, '--type', 'test', '--skip-llm-gate'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert 'VERIFIED:' in result.stdout
        assert 'Skipping Gate 3' in result.stderr

    def test_llm_verify_flag_removed(self, temp_project_dir, scripts_dir, test_session_id):
        """--llm-verify is no longer a valid argument (exits with error)."""
        promises_dir = get_promises_dir(temp_project_dir)
        promise_id = "promise-oldarg-001"

        create_promise_with_acs(
            promises_dir, promise_id, test_session_id,
            ["Test"],
        )

        env = {
            'CLAUDE_SESSION_ID': test_session_id,
            'CLAUDE_PROJECT_DIR': temp_project_dir,
        }

        # Try using the old --llm-verify flag
        result = run_cs_command(
            scripts_dir, 'cs-verify',
            ['--promise', promise_id, '--llm-verify'],
            env=env, cwd=temp_project_dir,
        )

        assert result.returncode != 0
        assert 'Unknown option' in result.stderr or 'llm-verify' in result.stderr


# === Entry point ===


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
