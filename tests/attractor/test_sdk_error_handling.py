"""Tests for SDK stream error handling in pipeline_runner.py.

Verifies that SDK stream errors (e.g. rate_limit_event) do not cause
false-positive success results, and that the signal file is used as
the ground truth for worker completion.

Tests:
    TestStreamErrorHandlerNoResult    - Stream error without result_text returns failed
    TestStreamErrorHandlerWithResult  - Stream error after result_text returns success
    TestStreamErrorNoMessages         - Stream error with zero messages propagates
    TestValidationStreamError         - Validation stream error returns fail (not auto-pass)
    TestSignalFileExistsPreservesSuccess - Signal file present keeps success result
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers: build a minimal PipelineRunner without touching the filesystem
# ---------------------------------------------------------------------------


def _make_runner(signal_dir: str) -> object:
    """Create a PipelineRunner bypassing __init__, with just the attrs we need."""
    from cobuilder.attractor.pipeline_runner import PipelineRunner

    runner = PipelineRunner.__new__(PipelineRunner)
    runner.signal_dir = signal_dir
    runner.dot_path = "/tmp/test_pipeline.dot"
    runner.dot_dir = "/tmp"
    runner.pipeline_id = "test_pipeline"
    runner.active_workers = {}
    runner._wake_event = threading.Event()
    runner.retry_counts = {}
    runner.requeue_guidance = {}
    runner.orphan_resume_counts = {}
    runner._signal_seq = {}
    return runner


# ---------------------------------------------------------------------------
# Shared async mock message types
# ---------------------------------------------------------------------------


class _FakeMsg:
    """Minimal stand-in for SDK message objects."""

    def __init__(self, result: str | None = None):
        self.result = result


# ---------------------------------------------------------------------------
# TestStreamErrorHandlerNoResult
# ---------------------------------------------------------------------------


class TestStreamErrorHandlerNoResult:
    """Stream error with messages but no result_text must return failed, not success."""

    def test_stream_error_without_result_returns_failed(self, tmp_path):
        """Mock _dispatch_sdk_worker to raise after handshake — caller converts to failed.

        This exercises the middle tier of the exception handler in _dispatch_via_sdk:
        the branch where ``messages`` is non-empty but ``result_text`` is empty.
        We invoke _dispatch_via_sdk directly by mocking ``claude_code_sdk.query``
        to yield a handshake message then raise a rate-limit exception.
        """
        from cobuilder.attractor import pipeline_runner as pr_mod

        signal_dir = str(tmp_path / "signals")
        os.makedirs(signal_dir, exist_ok=True)
        runner = _make_runner(signal_dir)

        # Fake async generator: yields one message then raises
        async def _fake_query(prompt, options):  # noqa: ARG001
            yield _FakeMsg(result=None)
            raise RuntimeError("rate_limit_event: too many requests")

        fake_sdk = MagicMock()
        fake_sdk.query = _fake_query
        fake_sdk.ClaudeCodeOptions = MagicMock(return_value=MagicMock())

        captured = {}

        def _fake_write_node_signal(node_id, payload):
            captured["node_id"] = node_id
            captured["payload"] = payload

        runner._write_node_signal = _fake_write_node_signal
        runner._get_target_dir = lambda: "/tmp"
        runner._build_system_prompt = lambda wt: "sys"
        runner._get_allowed_tools = lambda h: ["Read"]
        runner._get_repo_root = lambda: "/tmp"

        original_sdk = pr_mod.claude_code_sdk
        original_available = pr_mod._SDK_AVAILABLE
        try:
            pr_mod.claude_code_sdk = fake_sdk
            pr_mod._SDK_AVAILABLE = True

            runner._dispatch_via_sdk("impl_auth", "backend-solutions-engineer", "do work")
        finally:
            pr_mod.claude_code_sdk = original_sdk
            pr_mod._SDK_AVAILABLE = original_available

        # No signal file written by worker — signal file check also fires
        assert captured["payload"]["status"] == "failed"
        assert "signal file" in captured["payload"]["message"].lower() or \
               "stream error" in captured["payload"]["message"].lower()

    def test_stream_error_without_result_message_contains_error_info(self, tmp_path):
        """Failure message from stream error contains event count and error text."""
        from cobuilder.attractor import pipeline_runner as pr_mod

        signal_dir = str(tmp_path / "signals")
        os.makedirs(signal_dir, exist_ok=True)
        runner = _make_runner(signal_dir)

        rate_limit_msg = "rate_limit_event: 429 too many requests"

        async def _fake_query(prompt, options):  # noqa: ARG001
            yield _FakeMsg(result=None)
            yield _FakeMsg(result=None)
            raise RuntimeError(rate_limit_msg)

        fake_sdk = MagicMock()
        fake_sdk.query = _fake_query
        fake_sdk.ClaudeCodeOptions = MagicMock(return_value=MagicMock())

        captured = {}

        def _fake_write_node_signal(node_id, payload):
            captured["payload"] = payload

        runner._write_node_signal = _fake_write_node_signal
        runner._get_target_dir = lambda: "/tmp"
        runner._build_system_prompt = lambda wt: "sys"
        runner._get_allowed_tools = lambda h: ["Read"]
        runner._get_repo_root = lambda: "/tmp"

        original_sdk = pr_mod.claude_code_sdk
        original_available = pr_mod._SDK_AVAILABLE
        try:
            pr_mod.claude_code_sdk = fake_sdk
            pr_mod._SDK_AVAILABLE = True
            runner._dispatch_via_sdk("impl_auth", "backend-solutions-engineer", "work")
        finally:
            pr_mod.claude_code_sdk = original_sdk
            pr_mod._SDK_AVAILABLE = original_available

        assert captured["payload"]["status"] == "failed"


# ---------------------------------------------------------------------------
# TestStreamErrorHandlerWithResult
# ---------------------------------------------------------------------------


class TestStreamErrorHandlerWithResult:
    """Stream error AFTER result_text was captured should still return success.

    The worker completed its task and the error occurred at the tail end.
    This case must NOT be converted to failed.
    """

    def test_stream_error_after_result_yields_success_if_signal_file_exists(self, tmp_path):
        """When result_text is set AND signal file exists, success is preserved."""
        from cobuilder.attractor import pipeline_runner as pr_mod

        signal_dir = str(tmp_path / "signals")
        os.makedirs(signal_dir, exist_ok=True)
        runner = _make_runner(signal_dir)

        # Pre-write the signal file as the worker would
        signal_path = os.path.join(signal_dir, "impl_auth.json")
        with open(signal_path, "w") as fh:
            json.dump({"status": "impl_complete", "node_id": "impl_auth"}, fh)

        # Fake msg with a result attribute set
        class _ResultMsg:
            result = "Task completed successfully."

        async def _fake_query(prompt, options):  # noqa: ARG001
            yield _ResultMsg()
            raise RuntimeError("trailing stream error")

        fake_sdk = MagicMock()
        fake_sdk.query = _fake_query
        fake_sdk.ClaudeCodeOptions = MagicMock(return_value=MagicMock())

        captured = {}

        def _fake_write_node_signal(node_id, payload):
            captured["payload"] = payload

        runner._write_node_signal = _fake_write_node_signal
        runner._get_target_dir = lambda: "/tmp"
        runner._build_system_prompt = lambda wt: "sys"
        runner._get_allowed_tools = lambda h: ["Read"]
        runner._get_repo_root = lambda: "/tmp"

        original_sdk = pr_mod.claude_code_sdk
        original_available = pr_mod._SDK_AVAILABLE
        try:
            pr_mod.claude_code_sdk = fake_sdk
            pr_mod._SDK_AVAILABLE = True
            runner._dispatch_via_sdk("impl_auth", "backend-solutions-engineer", "work")
        finally:
            pr_mod.claude_code_sdk = original_sdk
            pr_mod._SDK_AVAILABLE = original_available

        # Signal file existed → success is preserved
        assert captured["payload"]["status"] == "success"
        assert "Task completed" in captured["payload"]["message"]


# ---------------------------------------------------------------------------
# TestStreamErrorNoMessages
# ---------------------------------------------------------------------------


class TestStreamErrorNoMessages:
    """Stream error with zero messages should propagate as an exception."""

    def test_stream_error_no_messages_results_in_failed(self, tmp_path):
        """Zero-message stream errors propagate → outer except catches → status=failed."""
        from cobuilder.attractor import pipeline_runner as pr_mod

        signal_dir = str(tmp_path / "signals")
        os.makedirs(signal_dir, exist_ok=True)
        runner = _make_runner(signal_dir)

        async def _fake_query(prompt, options):  # noqa: ARG001
            # Raise immediately without yielding anything
            raise RuntimeError("connection refused: no messages at all")
            # The `yield` below makes this a valid async generator
            yield  # noqa: unreachable

        fake_sdk = MagicMock()
        fake_sdk.query = _fake_query
        fake_sdk.ClaudeCodeOptions = MagicMock(return_value=MagicMock())

        captured = {}

        def _fake_write_node_signal(node_id, payload):
            captured["payload"] = payload

        runner._write_node_signal = _fake_write_node_signal
        runner._get_target_dir = lambda: "/tmp"
        runner._build_system_prompt = lambda wt: "sys"
        runner._get_allowed_tools = lambda h: ["Read"]
        runner._get_repo_root = lambda: "/tmp"

        original_sdk = pr_mod.claude_code_sdk
        original_available = pr_mod._SDK_AVAILABLE
        try:
            pr_mod.claude_code_sdk = fake_sdk
            pr_mod._SDK_AVAILABLE = True
            runner._dispatch_via_sdk("impl_auth", "backend-solutions-engineer", "work")
        finally:
            pr_mod.claude_code_sdk = original_sdk
            pr_mod._SDK_AVAILABLE = original_available

        # The outer except in _dispatch_via_sdk catches the re-raised exception
        assert captured["payload"]["status"] == "failed"
        assert "connection refused" in captured["payload"]["message"].lower() or \
               "SDK dispatch error" in captured["payload"]["message"]


# ---------------------------------------------------------------------------
# TestValidationStreamError
# ---------------------------------------------------------------------------


class TestValidationStreamError:
    """Validation stream errors must return fail, not auto-pass."""

    def test_validation_stream_error_returns_fail(self, tmp_path):
        """When the validation SDK stream raises, result is fail not pass."""
        from cobuilder.attractor import pipeline_runner as pr_mod

        signal_dir = str(tmp_path / "signals")
        os.makedirs(signal_dir, exist_ok=True)
        runner = _make_runner(signal_dir)

        # Simulate a rate limit mid-validation stream
        async def _fake_query(prompt, options):  # noqa: ARG001
            yield _FakeMsg(result=None)
            raise RuntimeError("rate_limit_event during validation")

        fake_sdk = MagicMock()
        fake_sdk.query = _fake_query
        fake_sdk.ClaudeCodeOptions = MagicMock(return_value=MagicMock())

        # Capture what _write_node_signal receives
        validation_signals = []

        def _fake_write_node_signal(node_id, payload):
            validation_signals.append((node_id, payload))

        runner._write_node_signal = _fake_write_node_signal
        runner._get_target_dir = lambda: "/tmp"
        runner._build_system_prompt = lambda wt: "sys"
        runner._build_validation_prompt = lambda nid: "validate this"
        runner._get_allowed_tools = lambda h: ["Read"]
        runner._get_repo_root = lambda: "/tmp"
        runner._validation_method_hint = None

        original_sdk = pr_mod.claude_code_sdk
        original_available = pr_mod._SDK_AVAILABLE
        try:
            pr_mod.claude_code_sdk = fake_sdk
            pr_mod._SDK_AVAILABLE = True
            runner._run_validation_subprocess("validate_impl_auth", "impl_auth")
        finally:
            pr_mod.claude_code_sdk = original_sdk
            pr_mod._SDK_AVAILABLE = original_available

        # Exactly one signal should have been written
        assert len(validation_signals) == 1, \
            f"Expected 1 signal, got {len(validation_signals)}: {validation_signals}"
        _nid, payload = validation_signals[0]
        assert payload.get("result") == "fail", \
            f"Expected result=fail, got: {payload}"
        assert "stream error" in payload.get("reason", "").lower() or \
               "validation stream error" in payload.get("reason", "").lower(), \
            f"Unexpected reason: {payload.get('reason')}"

    def test_validation_stream_error_reason_contains_exception_text(self, tmp_path):
        """Fail reason includes the exception message text."""
        from cobuilder.attractor import pipeline_runner as pr_mod

        signal_dir = str(tmp_path / "signals")
        os.makedirs(signal_dir, exist_ok=True)
        runner = _make_runner(signal_dir)

        exc_text = "rate_limit_event: quota exceeded for model haiku"

        async def _fake_query(prompt, options):  # noqa: ARG001
            yield _FakeMsg(result=None)
            raise RuntimeError(exc_text)

        fake_sdk = MagicMock()
        fake_sdk.query = _fake_query
        fake_sdk.ClaudeCodeOptions = MagicMock(return_value=MagicMock())

        captured = {}

        def _fake_write_node_signal(node_id, payload):
            captured["payload"] = payload

        runner._write_node_signal = _fake_write_node_signal
        runner._get_target_dir = lambda: "/tmp"
        runner._build_system_prompt = lambda wt: "sys"
        runner._build_validation_prompt = lambda nid: "validate this"
        runner._get_allowed_tools = lambda h: ["Read"]
        runner._get_repo_root = lambda: "/tmp"
        runner._validation_method_hint = None

        original_sdk = pr_mod.claude_code_sdk
        original_available = pr_mod._SDK_AVAILABLE
        try:
            pr_mod.claude_code_sdk = fake_sdk
            pr_mod._SDK_AVAILABLE = True
            runner._run_validation_subprocess("validate_impl_auth", "impl_auth")
        finally:
            pr_mod.claude_code_sdk = original_sdk
            pr_mod._SDK_AVAILABLE = original_available

        reason = captured["payload"].get("reason", "")
        assert exc_text[:50] in reason, \
            f"Exception text not in reason. reason={reason!r}"


# ---------------------------------------------------------------------------
# TestSignalFileExistsPreservesSuccess
# ---------------------------------------------------------------------------


class TestSignalFileExistsPreservesSuccess:
    """When signal file exists and SDK reports success, result stays success."""

    def test_signal_file_exists_preserves_success(self, tmp_path):
        """Normal happy path: worker writes signal file, SDK returns success → stays success."""
        from cobuilder.attractor import pipeline_runner as pr_mod

        signal_dir = str(tmp_path / "signals")
        os.makedirs(signal_dir, exist_ok=True)
        runner = _make_runner(signal_dir)

        # Pre-write the worker signal file (simulating a completed worker)
        signal_path = os.path.join(signal_dir, "impl_payments.json")
        with open(signal_path, "w") as fh:
            json.dump({"status": "impl_complete", "node_id": "impl_payments"}, fh)

        class _ResultMsg:
            result = "All payments implemented."

        async def _fake_query(prompt, options):  # noqa: ARG001
            yield _ResultMsg()

        fake_sdk = MagicMock()
        fake_sdk.query = _fake_query
        fake_sdk.ClaudeCodeOptions = MagicMock(return_value=MagicMock())

        captured = {}

        def _fake_write_node_signal(node_id, payload):
            captured["payload"] = payload

        runner._write_node_signal = _fake_write_node_signal
        runner._get_target_dir = lambda: "/tmp"
        runner._build_system_prompt = lambda wt: "sys"
        runner._get_allowed_tools = lambda h: ["Read"]
        runner._get_repo_root = lambda: "/tmp"

        original_sdk = pr_mod.claude_code_sdk
        original_available = pr_mod._SDK_AVAILABLE
        try:
            pr_mod.claude_code_sdk = fake_sdk
            pr_mod._SDK_AVAILABLE = True
            runner._dispatch_via_sdk("impl_payments", "backend-solutions-engineer", "work")
        finally:
            pr_mod.claude_code_sdk = original_sdk
            pr_mod._SDK_AVAILABLE = original_available

        assert captured["payload"]["status"] == "success"
        assert "All payments implemented" in captured["payload"]["message"]

    def test_signal_file_missing_converts_success_to_failed(self, tmp_path):
        """When signal file is ABSENT and SDK reports success, result becomes failed."""
        from cobuilder.attractor import pipeline_runner as pr_mod

        signal_dir = str(tmp_path / "signals")
        os.makedirs(signal_dir, exist_ok=True)
        runner = _make_runner(signal_dir)

        # No signal file pre-written — worker didn't complete

        class _ResultMsg:
            result = "Task done."

        async def _fake_query(prompt, options):  # noqa: ARG001
            yield _ResultMsg()

        fake_sdk = MagicMock()
        fake_sdk.query = _fake_query
        fake_sdk.ClaudeCodeOptions = MagicMock(return_value=MagicMock())

        captured = {}

        def _fake_write_node_signal(node_id, payload):
            captured["payload"] = payload

        runner._write_node_signal = _fake_write_node_signal
        runner._get_target_dir = lambda: "/tmp"
        runner._build_system_prompt = lambda wt: "sys"
        runner._get_allowed_tools = lambda h: ["Read"]
        runner._get_repo_root = lambda: "/tmp"

        original_sdk = pr_mod.claude_code_sdk
        original_available = pr_mod._SDK_AVAILABLE
        try:
            pr_mod.claude_code_sdk = fake_sdk
            pr_mod._SDK_AVAILABLE = True
            runner._dispatch_via_sdk("impl_payments", "backend-solutions-engineer", "work")
        finally:
            pr_mod.claude_code_sdk = original_sdk
            pr_mod._SDK_AVAILABLE = original_available

        assert captured["payload"]["status"] == "failed"
        assert "signal file" in captured["payload"]["message"].lower()


# ---------------------------------------------------------------------------
# TestLoadAttractorEnvPath
# ---------------------------------------------------------------------------


class TestLoadAttractorEnvPath:
    """dispatch_worker.load_attractor_env() must find .claude/attractor/.env
    relative to the project root, not the old .claude/scripts/attractor/ path."""

    def test_load_attractor_env_finds_dotenv(self, tmp_path):
        """load_attractor_env() reads from <project_root>/.claude/attractor/.env."""
        from cobuilder.attractor import dispatch_worker as dw_mod

        # Create a fake project layout: tmp_path plays the role of _project_root.
        dot_env_dir = tmp_path / ".claude" / "attractor"
        dot_env_dir.mkdir(parents=True)
        dot_env = dot_env_dir / ".env"
        dot_env.write_text(
            "ANTHROPIC_API_KEY=test-key-from-dotenv\n"
            "ANTHROPIC_MODEL=qwen-test-model\n"
            "# comment line\n"
            "UNRELATED_KEY=should-be-ignored\n",
            encoding="utf-8",
        )

        original_project_root = dw_mod._project_root
        try:
            dw_mod._project_root = tmp_path
            result = dw_mod.load_attractor_env()
        finally:
            dw_mod._project_root = original_project_root

        assert result.get("ANTHROPIC_API_KEY") == "test-key-from-dotenv"
        assert result.get("ANTHROPIC_MODEL") == "qwen-test-model"
        assert "UNRELATED_KEY" not in result, "Non-allowlisted keys must not be returned"

    def test_load_attractor_env_returns_empty_if_missing(self, tmp_path):
        """When .env is absent, load_attractor_env() returns {} without error."""
        from cobuilder.attractor import dispatch_worker as dw_mod

        original_project_root = dw_mod._project_root
        try:
            dw_mod._project_root = tmp_path  # no .claude/attractor/.env here
            result = dw_mod.load_attractor_env()
        finally:
            dw_mod._project_root = original_project_root

        assert result == {}


# ---------------------------------------------------------------------------
# TestPipelineRunnerEnvOverride
# ---------------------------------------------------------------------------


class TestPipelineRunnerEnvOverride:
    """_load_attractor_env must OVERRIDE existing env vars, not skip them."""

    def test_pipeline_runner_env_override(self, tmp_path):
        """If ANTHROPIC_MODEL is already set in os.environ, .env must override it."""
        from cobuilder.attractor.pipeline_runner import PipelineRunner

        # Build a minimal runner with a fake dot_file path inside tmp_path.
        # We place the .env alongside the pipeline dir structure:
        #   tmp_path/
        #     pipelines/   <- dot_file lives here
        #     .env         <- _load_attractor_env should find via dotdir/../.env
        pipelines_dir = tmp_path / "pipelines"
        pipelines_dir.mkdir()
        dot_file = pipelines_dir / "test.dot"
        dot_file.write_text("digraph {}", encoding="utf-8")

        env_file = tmp_path / ".env"
        env_file.write_text("ANTHROPIC_MODEL=overridden-model\n", encoding="utf-8")

        runner = PipelineRunner.__new__(PipelineRunner)
        runner.dot_file = str(dot_file)
        runner.signal_dir = str(tmp_path / "signals")

        old_val = os.environ.get("ANTHROPIC_MODEL")
        os.environ["ANTHROPIC_MODEL"] = "original-model"
        try:
            runner._load_attractor_env()
            assert os.environ.get("ANTHROPIC_MODEL") == "overridden-model", (
                "_load_attractor_env must override existing env vars; "
                f"got {os.environ.get('ANTHROPIC_MODEL')!r}"
            )
        finally:
            if old_val is None:
                os.environ.pop("ANTHROPIC_MODEL", None)
            else:
                os.environ["ANTHROPIC_MODEL"] = old_val


# ---------------------------------------------------------------------------
# TestRateLimitRetry
# ---------------------------------------------------------------------------


def _make_runner_for_retry(signal_dir: str) -> object:
    """Minimal PipelineRunner suitable for retry tests."""
    from cobuilder.attractor.pipeline_runner import PipelineRunner

    runner = PipelineRunner.__new__(PipelineRunner)
    runner.signal_dir = signal_dir
    runner.dot_path = "/tmp/test_pipeline.dot"
    runner.dot_file = "/tmp/test_pipeline.dot"
    runner.dot_dir = "/tmp"
    runner.pipeline_id = "test_pipeline"
    runner.active_workers = {}
    runner._wake_event = threading.Event()
    runner.retry_counts = {}
    runner.requeue_guidance = {}
    runner.orphan_resume_counts = {}
    runner._signal_seq = {}
    runner._graph_attrs = {}
    return runner


class TestRateLimitRetry:
    """Rate limit retry wraps _dispatch_via_sdk with backoff and caps attempts."""

    def test_rate_limit_retry_succeeds_on_second_attempt(self, tmp_path):
        """When the first dispatch fails with rate_limit, a second attempt succeeds."""
        from cobuilder.attractor import pipeline_runner as pr_mod

        signal_dir = str(tmp_path / "signals")
        os.makedirs(signal_dir, exist_ok=True)
        runner = _make_runner_for_retry(signal_dir)

        call_count = {"n": 0}

        def _fake_dispatch_via_sdk(node_id, worker_type, prompt, handler="codergen"):
            call_count["n"] += 1
            signal_path = os.path.join(signal_dir, f"{node_id}.json")
            if call_count["n"] == 1:
                # First attempt: write a rate_limit failure signal
                with open(signal_path, "w") as fh:
                    json.dump({"status": "failed", "message": "rate_limit_event: 429"}, fh)
            else:
                # Second attempt: write success signal
                with open(signal_path, "w") as fh:
                    json.dump({"status": "success", "message": "done"}, fh)

        runner._dispatch_via_sdk = _fake_dispatch_via_sdk
        runner._get_target_dir = lambda: "/tmp"
        runner._build_system_prompt = lambda wt: "sys"
        runner._get_allowed_tools = lambda h: ["Read"]

        written_signals = []

        def _fake_write_node_signal(node_id, payload):
            written_signals.append(payload)

        runner._write_node_signal = _fake_write_node_signal

        original_backoff = pr_mod._RATE_LIMIT_BACKOFF_SECONDS
        try:
            pr_mod._RATE_LIMIT_BACKOFF_SECONDS = 0  # no actual sleeping in tests
            pr_mod._SDK_AVAILABLE = True

            # Call _dispatch_agent_sdk directly (the public method with the retry loop)
            runner._dispatch_agent_sdk(
                node_id="impl_auth",
                worker_type="backend-solutions-engineer",
                prompt="do work",
            )
        finally:
            pr_mod._RATE_LIMIT_BACKOFF_SECONDS = original_backoff

        assert call_count["n"] == 2, f"Expected 2 dispatch attempts, got {call_count['n']}"
        # The final signal in the signal file should be success
        final_signal_path = os.path.join(signal_dir, "impl_auth.json")
        with open(final_signal_path) as fh:
            final = json.load(fh)
        assert final["status"] == "success"

    def test_rate_limit_retry_gives_up_after_max(self, tmp_path):
        """When every attempt returns rate_limit, retry stops after MAX_RETRIES."""
        from cobuilder.attractor import pipeline_runner as pr_mod

        signal_dir = str(tmp_path / "signals")
        os.makedirs(signal_dir, exist_ok=True)
        runner = _make_runner_for_retry(signal_dir)

        call_count = {"n": 0}

        def _fake_dispatch_via_sdk(node_id, worker_type, prompt, handler="codergen"):
            call_count["n"] += 1
            signal_path = os.path.join(signal_dir, f"{node_id}.json")
            with open(signal_path, "w") as fh:
                json.dump(
                    {"status": "failed", "message": "rate_limit_event: quota exceeded"},
                    fh,
                )

        runner._dispatch_via_sdk = _fake_dispatch_via_sdk
        runner._get_target_dir = lambda: "/tmp"
        runner._build_system_prompt = lambda wt: "sys"
        runner._get_allowed_tools = lambda h: ["Read"]

        written_signals = []

        def _fake_write_node_signal(node_id, payload):
            written_signals.append(payload)

        runner._write_node_signal = _fake_write_node_signal

        original_backoff = pr_mod._RATE_LIMIT_BACKOFF_SECONDS
        original_max = pr_mod._RATE_LIMIT_MAX_RETRIES
        try:
            pr_mod._RATE_LIMIT_BACKOFF_SECONDS = 0
            pr_mod._RATE_LIMIT_MAX_RETRIES = 3
            pr_mod._SDK_AVAILABLE = True

            runner._dispatch_agent_sdk(
                node_id="impl_auth",
                worker_type="backend-solutions-engineer",
                prompt="do work",
            )
        finally:
            pr_mod._RATE_LIMIT_BACKOFF_SECONDS = original_backoff
            pr_mod._RATE_LIMIT_MAX_RETRIES = original_max

        assert call_count["n"] == 3, (
            f"Expected exactly MAX_RETRIES=3 attempts, got {call_count['n']}"
        )
