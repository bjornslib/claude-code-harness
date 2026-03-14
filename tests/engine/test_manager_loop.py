"""Tests for cobuilder.engine.handlers.manager_loop — ManagerLoopHandler."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cobuilder.engine.context import PipelineContext
from cobuilder.engine.graph import Node
from cobuilder.engine.handlers.base import HandlerRequest
from cobuilder.engine.handlers.manager_loop import ManagerLoopHandler
from cobuilder.engine.outcome import OutcomeStatus


def _make_request(
    node_id: str = "test_node",
    attrs: dict | None = None,
    run_dir: str = "",
    context_data: dict | None = None,
) -> HandlerRequest:
    """Create a HandlerRequest for testing."""
    if attrs is None:
        attrs = {}
    node = Node(
        id=node_id,
        shape="house",
        label="Test Node",
        attrs={"handler": "manager_loop", **attrs},
    )
    ctx = PipelineContext(initial=context_data or {})
    return HandlerRequest(
        node=node,
        context=ctx,
        run_dir=run_dir,
    )


class TestManagerLoopHandler:
    @pytest.mark.asyncio
    async def test_max_depth_exceeded(self) -> None:
        handler = ManagerLoopHandler()
        request = _make_request(
            attrs={"mode": "spawn_pipeline"},
            context_data={"$manager_depth": 10},
        )
        outcome = await handler.execute(request)
        assert outcome.status == OutcomeStatus.FAILURE
        assert outcome.metadata["error_type"] == "MAX_DEPTH_EXCEEDED"

    @pytest.mark.asyncio
    async def test_spawn_pipeline_no_dot_path(self, tmp_path: Path) -> None:
        handler = ManagerLoopHandler()
        request = _make_request(
            attrs={"mode": "spawn_pipeline"},
            run_dir=str(tmp_path),
        )
        outcome = await handler.execute(request)
        assert outcome.status == OutcomeStatus.FAILURE
        assert outcome.metadata["error_type"] == "NO_DOT_PATH"

    @pytest.mark.asyncio
    async def test_spawn_pipeline_with_sub_pipeline(self, tmp_path: Path) -> None:
        """Test that a valid sub_pipeline attribute resolves the DOT path."""
        handler = ManagerLoopHandler()

        # Create a dummy DOT file
        dot_file = tmp_path / "child.dot"
        dot_file.write_text('digraph test { start [shape=Mdiamond]; }')

        request = _make_request(
            attrs={
                "mode": "spawn_pipeline",
                "sub_pipeline": str(dot_file),
            },
            run_dir=str(tmp_path),
        )

        # Mock the subprocess to avoid actually spawning
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.pid = 12345
        mock_proc.communicate = AsyncMock(return_value=(b"done", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            outcome = await handler.execute(request)

        assert outcome.status == OutcomeStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_spawn_pipeline_with_params_file(self, tmp_path: Path) -> None:
        """Test resolution from pipeline_params_file JSON."""
        handler = ManagerLoopHandler()

        # Create child DOT file
        dot_file = tmp_path / "pipelines" / "child.dot"
        dot_file.parent.mkdir(parents=True)
        dot_file.write_text('digraph test { start [shape=Mdiamond]; }')

        # Create params JSON
        params_file = tmp_path / "state" / "plan.json"
        params_file.parent.mkdir(parents=True)
        params_file.write_text(json.dumps({
            "dot_path": str(dot_file),
            "template": "hub-spoke",
        }))

        request = _make_request(
            attrs={
                "mode": "spawn_pipeline",
                "pipeline_params_file": str(params_file),
            },
            run_dir=str(tmp_path),
        )

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.pid = 12345
        mock_proc.communicate = AsyncMock(return_value=(b"done", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            outcome = await handler.execute(request)

        assert outcome.status == OutcomeStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_supervisor_mode_without_sub_pipeline(self) -> None:
        handler = ManagerLoopHandler()
        request = _make_request(attrs={})  # No mode, no sub_pipeline

        with pytest.raises(NotImplementedError, match="supervisor mode"):
            await handler.execute(request)

    @pytest.mark.asyncio
    async def test_child_failure_returns_failure(self, tmp_path: Path) -> None:
        handler = ManagerLoopHandler()

        dot_file = tmp_path / "child.dot"
        dot_file.write_text('digraph test { start [shape=Mdiamond]; }')

        request = _make_request(
            attrs={
                "mode": "spawn_pipeline",
                "sub_pipeline": str(dot_file),
            },
            run_dir=str(tmp_path),
        )

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.pid = 12345
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error occurred"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            outcome = await handler.execute(request)

        assert outcome.status == OutcomeStatus.FAILURE
        assert outcome.metadata["child_returncode"] == 1


class TestGateSignalDetection:
    """Tests for gate signal detection and handling."""

    @pytest.mark.asyncio
    async def test_detect_gate_signal_cobuilder(self, tmp_path: Path) -> None:
        """Test detection of GATE_WAIT_COBUILDER signal."""
        from cobuilder.engine.handlers.manager_loop import GateType
        from cobuilder.engine.signal_protocol import (
            GATE_WAIT_COBUILDER,
            write_signal,
        )

        handler = ManagerLoopHandler()

        # Create signals directory
        signals_dir = tmp_path / "signals"
        signals_dir.mkdir(parents=True)

        # Write a cobuilder gate signal
        write_signal(
            source="child",
            target="parent",
            signal_type=GATE_WAIT_COBUILDER,
            payload={"node_id": "validate_node", "gate_type": "wait.cobuilder"},
            signals_dir=str(signals_dir),
        )

        # Detect the gate signal
        gate = handler._detect_gate_signal(signals_dir)

        assert gate is not None
        assert gate.gate_type == GateType.COBUILDER
        assert gate.node_id == "validate_node"

    @pytest.mark.asyncio
    async def test_detect_gate_signal_human(self, tmp_path: Path) -> None:
        """Test detection of GATE_WAIT_HUMAN signal."""
        from cobuilder.engine.handlers.manager_loop import GateType
        from cobuilder.engine.signal_protocol import (
            GATE_WAIT_HUMAN,
            write_signal,
        )

        handler = ManagerLoopHandler()

        # Create signals directory
        signals_dir = tmp_path / "signals"
        signals_dir.mkdir(parents=True)

        # Write a human gate signal
        write_signal(
            source="child",
            target="parent",
            signal_type=GATE_WAIT_HUMAN,
            payload={"node_id": "approval_node", "gate_type": "wait.human"},
            signals_dir=str(signals_dir),
        )

        # Detect the gate signal
        gate = handler._detect_gate_signal(signals_dir)

        assert gate is not None
        assert gate.gate_type == GateType.HUMAN
        assert gate.node_id == "approval_node"

    @pytest.mark.asyncio
    async def test_detect_no_gate_signal(self, tmp_path: Path) -> None:
        """Test that _detect_gate_signal returns None when no gate signals exist."""
        handler = ManagerLoopHandler()

        # Create empty signals directory
        signals_dir = tmp_path / "signals"
        signals_dir.mkdir(parents=True)

        # No gate signals present
        gate = handler._detect_gate_signal(signals_dir)

        assert gate is None

    @pytest.mark.asyncio
    async def test_handle_cobuilder_gate_auto_approve(self, tmp_path: Path) -> None:
        """Test that cobuilder gates are auto-approved and response signal written."""
        from cobuilder.engine.handlers.manager_loop import GateSignal, GateType

        handler = ManagerLoopHandler()

        # Create signals directory
        signals_dir = tmp_path / "signals"
        signals_dir.mkdir(parents=True)

        # Create a gate signal
        gate = GateSignal(
            gate_type=GateType.COBUILDER,
            node_id="validate_node",
            prd_ref="PRD-TEST-001",
            signal_path=signals_dir / "test-signal.json",
        )

        # Create a mock node
        node = MagicMock()
        node.id = "parent_node"

        # Handle the gate
        result = await handler._handle_gate(
            gate=gate,
            signals_dir=str(signals_dir),
            node=node,
        )

        assert result.get("handled") is True

        # Verify response signal was written
        response_files = list(signals_dir.glob("*GATE_RESPONSE*.json"))
        assert len(response_files) >= 1

    @pytest.mark.asyncio
    async def test_handle_human_gate_not_handled(self, tmp_path: Path) -> None:
        """Test that human gates return not handled (requires external intervention)."""
        from cobuilder.engine.handlers.manager_loop import GateSignal, GateType

        handler = ManagerLoopHandler()

        # Create signals directory
        signals_dir = tmp_path / "signals"
        signals_dir.mkdir(parents=True)

        # Create a gate signal
        gate = GateSignal(
            gate_type=GateType.HUMAN,
            node_id="approval_node",
            prd_ref="PRD-TEST-001",
            signal_path=signals_dir / "test-signal.json",
        )

        # Create a mock node
        node = MagicMock()
        node.id = "parent_node"

        # Handle the gate
        result = await handler._handle_gate(
            gate=gate,
            signals_dir=str(signals_dir),
            node=node,
        )

        assert result.get("handled") is False
        assert "human_intervention_required" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_child_pipeline_with_cobuilder_gate(self, tmp_path: Path) -> None:
        """Test that child hitting wait.cobuilder gate is handled correctly."""
        from cobuilder.engine.signal_protocol import (
            GATE_WAIT_COBUILDER,
            RUNNER_EXITED,
            write_signal,
        )

        handler = ManagerLoopHandler()

        # Create a dummy DOT file
        dot_file = tmp_path / "child.dot"
        dot_file.write_text('digraph test { start [shape=Mdiamond]; }')

        request = _make_request(
            attrs={
                "mode": "spawn_pipeline",
                "sub_pipeline": str(dot_file),
            },
            run_dir=str(tmp_path),
        )

        # Mock subprocess that stays alive while gate is processed
        mock_proc = AsyncMock()
        mock_proc.returncode = None  # Process is running
        mock_proc.pid = 12345
        mock_proc.communicate = AsyncMock(return_value=(b"done", b""))

        signals_dir = tmp_path / "nodes" / "test_node" / "sub-run" / "signals"

        call_count = 0

        async def mock_sleep(interval: float) -> None:
            nonlocal call_count
            call_count += 1

            # On first call, write a cobuilder gate signal
            if call_count == 1:
                signals_dir.mkdir(parents=True, exist_ok=True)
                write_signal(
                    source="child",
                    target="parent",
                    signal_type=GATE_WAIT_COBUILDER,
                    payload={"node_id": "child_gate", "prd_ref": "PRD-001"},
                    signals_dir=str(signals_dir),
                )

            # On third call, write completion signal and set returncode
            if call_count == 3:
                mock_proc.returncode = 0
                write_signal(
                    source="runner",
                    target="parent",
                    signal_type=RUNNER_EXITED,
                    payload={"status": "completed"},
                    signals_dir=str(signals_dir),
                )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("asyncio.sleep", side_effect=mock_sleep):
                outcome = await handler.execute(request)

        assert outcome.status == OutcomeStatus.SUCCESS
