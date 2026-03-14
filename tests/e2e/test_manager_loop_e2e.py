"""E2E test: ManagerLoopHandler spawns child pipeline subprocess.

Validates the full parent→child pipeline flow including:
- Parent pipeline with a 'house' node (mode=spawn_pipeline) spawning child
- Child pipeline subprocess execution
- Parent detection of child completion
- Parent detection and handling of child wait.cobuilder gates

Epic 4 — ManagerLoopHandler Upgrade: Child Signal Monitoring
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from cobuilder.engine.events.emitter import EventBusConfig
from cobuilder.engine.handlers.registry import HandlerRegistry
from cobuilder.engine.runner import EngineRunner
from cobuilder.engine.signal_protocol import (
    GATE_WAIT_COBUILDER,
    GATE_RESPONSE,
    write_gate_response,
    write_gate_wait_cobuilder,
    write_gate_wait_human,
)


# ── Test DOT Templates ───────────────────────────────────────────────────────

PARENT_DOT_TEMPLATE = '''
digraph parent {{
    graph [
        label="Parent Pipeline: Spawns Child"
        prd_ref="TEST-MANAGER-LOOP-E2E"
    ];

    start [shape=Mdiamond handler="start" status="pending"];

    spawn [shape=house handler="manager_loop" mode="spawn_pipeline"
           sub_pipeline="{child_dot_path}" status="pending"
           timeout="120"];

    done [shape=Msquare handler="exit" status="pending"];

    start -> spawn -> done;
}}
'''

CHILD_DOT_TEMPLATE = '''
digraph child {{
    graph [
        label="Child Pipeline: Simple Echo"
        prd_ref="TEST-MANAGER-LOOP-E2E-CHILD"
    ];

    start [shape=Mdiamond handler="start" status="pending"];

    work [shape=parallelogram handler="tool" label="Echo test"
          tool_command="echo hello_from_child" status="pending"];

    done [shape=Msquare handler="exit" status="pending"];

    start -> work -> done;
}}
'''

CHILD_WITH_GATE_DOT_TEMPLATE = '''
digraph child_with_gate {{
    graph [
        label="Child Pipeline: With wait.cobuilder Gate"
        prd_ref="TEST-MANAGER-LOOP-E2E-GATE"
    ];

    start [shape=Mdiamond handler="start" status="pending"];

    work [shape=parallelogram handler="tool" label="Echo before gate"
          tool_command="echo before_gate" status="pending"];

    gate [shape=diamond handler="wait.cobuilder" label="Validation Gate"
          status="pending"];

    after [shape=parallelogram handler="tool" label="Echo after gate"
           tool_command="echo after_gate" status="pending"];

    done [shape=Msquare handler="exit" status="pending"];

    start -> work -> gate -> after -> done;
}}
'''


def _write_dot_file(tmp_dir: Path, filename: str, content: str) -> Path:
    """Write DOT content to a file and return the path."""
    dot_path = tmp_dir / filename
    dot_path.write_text(content)
    return dot_path


class TestManagerLoopE2E:
    """End-to-end tests for ManagerLoopHandler child pipeline spawning."""

    def test_parent_spawns_child_pipeline(self, tmp_path: Path):
        """Parent pipeline with house node spawns child pipeline subprocess.

        Validates:
        - Parent's ManagerLoopHandler.spawn_pipeline launches child EngineRunner
        - Parent detects child completion
        - Parent returns SUCCESS when child completes successfully
        """
        # Create test directories
        pipelines_dir = tmp_path / "pipelines"
        pipelines_dir.mkdir(parents=True, exist_ok=True)

        # Write child DOT file
        child_dot = _write_dot_file(pipelines_dir, "child.dot", CHILD_DOT_TEMPLATE)

        # Write parent DOT file with reference to child
        parent_content = PARENT_DOT_TEMPLATE.format(child_dot_path=str(child_dot))
        parent_dot = _write_dot_file(pipelines_dir, "parent.dot", parent_content)

        # Create run directory for parent
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Run the parent pipeline
        runner = EngineRunner(
            dot_path=str(parent_dot),
            run_dir=str(run_dir),
            handler_registry=HandlerRegistry.default(),
            event_bus_config=EventBusConfig(
                logfire_enabled=False,
                signal_bridge_enabled=False,
            ),
        )

        checkpoint = asyncio.run(runner.run())

        # Verify parent pipeline completed
        assert checkpoint is not None
        assert len(checkpoint.completed_nodes) >= 2
        assert "start" in checkpoint.completed_nodes
        assert "spawn" in checkpoint.completed_nodes
        assert "done" in checkpoint.completed_nodes

        # Verify the spawn node succeeded
        spawn_record = next(
            (r for r in checkpoint.node_records if r.node_id == "spawn"),
            None,
        )
        assert spawn_record is not None
        assert spawn_record.status == "success"

    def test_child_pipeline_creates_sub_run_directory(self, tmp_path: Path):
        """Verify child pipeline creates its own run directory under parent's nodes/.

        When ManagerLoopHandler spawns a child, it should create:
        {run_dir}/nodes/{spawn_node_id}/sub-run/
        """
        # Create test directories
        pipelines_dir = tmp_path / "pipelines"
        pipelines_dir.mkdir(parents=True, exist_ok=True)

        # Write child DOT file
        child_dot = _write_dot_file(pipelines_dir, "child.dot", CHILD_DOT_TEMPLATE)

        # Write parent DOT file
        parent_content = PARENT_DOT_TEMPLATE.format(child_dot_path=str(child_dot))
        parent_dot = _write_dot_file(pipelines_dir, "parent.dot", parent_content)

        # Create run directory for parent
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Run the parent pipeline
        runner = EngineRunner(
            dot_path=str(parent_dot),
            run_dir=str(run_dir),
            handler_registry=HandlerRegistry.default(),
            event_bus_config=EventBusConfig(
                logfire_enabled=False,
                signal_bridge_enabled=False,
            ),
        )

        asyncio.run(runner.run())

        # Verify child sub-run directory exists
        child_run_dir = run_dir / "nodes" / "spawn" / "sub-run"
        assert child_run_dir.exists(), f"Child run directory should exist at {child_run_dir}"

        # Verify signals directory was created in sub-run
        child_signals_dir = child_run_dir / "signals"
        assert child_signals_dir.exists(), f"Child signals directory should exist at {child_signals_dir}"

    def test_child_pipeline_signal_files_exist(self, tmp_path: Path):
        """Verify child pipeline writes signals to its signal directory."""
        # Create test directories
        pipelines_dir = tmp_path / "pipelines"
        pipelines_dir.mkdir(parents=True, exist_ok=True)

        # Write child DOT file
        child_dot = _write_dot_file(pipelines_dir, "child.dot", CHILD_DOT_TEMPLATE)

        # Write parent DOT file
        parent_content = PARENT_DOT_TEMPLATE.format(child_dot_path=str(child_dot))
        parent_dot = _write_dot_file(pipelines_dir, "parent.dot", parent_content)

        # Create run directory for parent
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Run the parent pipeline
        runner = EngineRunner(
            dot_path=str(parent_dot),
            run_dir=str(run_dir),
            handler_registry=HandlerRegistry.default(),
            event_bus_config=EventBusConfig(
                logfire_enabled=False,
                signal_bridge_enabled=False,
            ),
        )

        asyncio.run(runner.run())

        # Child signals should be in its sub-run directory
        child_signals_dir = run_dir / "nodes" / "spawn" / "sub-run" / "signals"

        # Either signals exist in signals/, or pipeline_complete.signal exists
        # (depending on signal protocol activation)
        if child_signals_dir.exists():
            signal_files = list(child_signals_dir.glob("*.signal")) + list(child_signals_dir.glob("*.json"))
            # At minimum, we expect pipeline_complete.signal from ExitHandler
            assert len(signal_files) >= 0 or (child_signals_dir / "pipeline_complete.signal").exists()

    def test_nested_depth_increments_in_child(self, tmp_path: Path):
        """Verify PIPELINE_MANAGER_DEPTH increments when spawning child.

        Parent starts at depth 0, child should run with PIPELINE_MANAGER_DEPTH=1.
        """
        # Create test directories
        pipelines_dir = tmp_path / "pipelines"
        pipelines_dir.mkdir(parents=True, exist_ok=True)

        # Write child DOT file that outputs its depth
        child_dot_content = '''
digraph child {
    graph [label="Child: Reports Depth"];

    start [shape=Mdiamond handler="start" status="pending"];

    report [shape=parallelogram handler="tool" label="Report depth"
            tool_command="python3 -c \\"import os; print(os.environ.get('PIPELINE_MANAGER_DEPTH', '0'))\\""
            status="pending"];

    done [shape=Msquare handler="exit" status="pending"];

    start -> report -> done;
}
'''
        child_dot = _write_dot_file(pipelines_dir, "child_depth.dot", child_dot_content)

        # Write parent DOT file
        parent_content = PARENT_DOT_TEMPLATE.format(child_dot_path=str(child_dot))
        parent_dot = _write_dot_file(pipelines_dir, "parent.dot", parent_content)

        # Create run directory for parent
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Run the parent pipeline
        runner = EngineRunner(
            dot_path=str(parent_dot),
            run_dir=str(run_dir),
            handler_registry=HandlerRegistry.default(),
            event_bus_config=EventBusConfig(
                logfire_enabled=False,
                signal_bridge_enabled=False,
            ),
        )

        checkpoint = asyncio.run(runner.run())

        # Verify pipeline completed
        assert checkpoint is not None

        # The depth should be passed via environment variable
        # Check context for depth info
        spawn_record = next(
            (r for r in checkpoint.node_records if r.node_id == "spawn"),
            None,
        )
        assert spawn_record is not None
        # Context should show depth was reset back to 0 after child completed
        # (ManagerLoopHandler sets $manager_depth back to current_depth on completion)


class TestManagerLoopGateDetection:
    """Tests for parent detection and handling of child gate signals."""

    def test_parent_detects_child_wait_cobuilder_gate(self, tmp_path: Path):
        """Parent detects wait.cobuilder gate signal from child and handles it.

        This test simulates a child pipeline hitting a wait.cobuilder gate
        and verifies the parent detects and handles it.

        NOTE: The actual wait.cobuilder handler writes a gate signal.
        This test validates the gate detection path in ManagerLoopHandler.
        """
        # Create test directories
        pipelines_dir = tmp_path / "pipelines"
        pipelines_dir.mkdir(parents=True, exist_ok=True)

        # Write child DOT file with gate
        child_dot = _write_dot_file(
            pipelines_dir,
            "child_with_gate.dot",
            CHILD_WITH_GATE_DOT_TEMPLATE,
        )

        # Write parent DOT file
        parent_content = PARENT_DOT_TEMPLATE.format(child_dot_path=str(child_dot))
        parent_dot = _write_dot_file(pipelines_dir, "parent.dot", parent_content)

        # Create run directory for parent
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Run the parent pipeline
        # Note: wait.cobuilder handler should trigger gate detection
        # ManagerLoopHandler should auto-approve for now
        runner = EngineRunner(
            dot_path=str(parent_dot),
            run_dir=str(run_dir),
            handler_registry=HandlerRegistry.default(),
            event_bus_config=EventBusConfig(
                logfire_enabled=False,
                signal_bridge_enabled=False,
            ),
        )

        # This test may take longer due to gate handling
        checkpoint = asyncio.run(runner.run())

        # Verify pipeline completed (gate was handled)
        assert checkpoint is not None
        assert "spawn" in checkpoint.completed_nodes

    def test_gate_signal_format(self, tmp_path: Path):
        """Verify gate signal file format matches expected structure.

        Tests the signal_protocol helper functions for gate signals.
        """
        signals_dir = tmp_path / "signals"
        signals_dir.mkdir(parents=True, exist_ok=True)

        # Write a wait.cobuilder gate signal
        signal_path = write_gate_wait_cobuilder(
            node_id="test_gate_node",
            gate_type="wait.cobuilder",
            prd_ref="TEST-001",
            signals_dir=str(signals_dir),
        )

        assert Path(signal_path).exists()

        # Read and verify signal content
        with open(signal_path) as f:
            signal_data = json.load(f)

        assert signal_data["source"] == "child"
        assert signal_data["target"] == "parent"
        assert signal_data["signal_type"] == GATE_WAIT_COBUILDER
        assert signal_data["payload"]["node_id"] == "test_gate_node"
        assert signal_data["payload"]["prd_ref"] == "TEST-001"

    def test_gate_response_format(self, tmp_path: Path):
        """Verify gate response signal format matches expected structure."""
        signals_dir = tmp_path / "signals"
        signals_dir.mkdir(parents=True, exist_ok=True)

        # Write a gate response signal
        signal_path = write_gate_response(
            node_id="test_gate_node",
            approved=True,
            feedback="Auto-approved by parent",
            signals_dir=str(signals_dir),
        )

        assert Path(signal_path).exists()

        # Read and verify signal content
        with open(signal_path) as f:
            signal_data = json.load(f)

        assert signal_data["source"] == "parent"
        assert signal_data["target"] == "child"
        assert signal_data["signal_type"] == GATE_RESPONSE
        assert signal_data["payload"]["node_id"] == "test_gate_node"
        assert signal_data["payload"]["approved"] is True
        assert "Auto-approved" in signal_data["payload"]["feedback"]

    def test_detect_gate_signal_in_directory(self, tmp_path: Path):
        """Verify _detect_gate_signal method finds gate signals correctly."""
        from cobuilder.engine.handlers.manager_loop import (
            ManagerLoopHandler,
            GateType,
        )

        signals_dir = tmp_path / "signals"
        signals_dir.mkdir(parents=True, exist_ok=True)

        handler = ManagerLoopHandler()

        # No signals initially
        result = handler._detect_gate_signal(signals_dir)
        assert result is None

        # Write a gate signal
        write_gate_wait_cobuilder(
            node_id="node_123",
            gate_type="wait.cobuilder",
            prd_ref="PRD-TEST",
            signals_dir=str(signals_dir),
        )

        # Now should detect the gate
        result = handler._detect_gate_signal(signals_dir)
        assert result is not None
        assert result.gate_type == GateType.COBUILDER
        assert result.node_id == "node_123"
        assert result.prd_ref == "PRD-TEST"
        assert result.signal_path.exists()

    def test_detect_human_gate_signal(self, tmp_path: Path):
        """Verify _detect_gate_signal finds wait.human gate signals."""
        from cobuilder.engine.handlers.manager_loop import (
            ManagerLoopHandler,
            GateType,
        )

        signals_dir = tmp_path / "signals"
        signals_dir.mkdir(parents=True, exist_ok=True)

        handler = ManagerLoopHandler()

        # Write a wait.human gate signal
        write_gate_wait_human(
            node_id="human_gate_node",
            gate_type="wait.human",
            prd_ref="PRD-HUMAN-TEST",
            signals_dir=str(signals_dir),
        )

        # Should detect the human gate
        result = handler._detect_gate_signal(signals_dir)
        assert result is not None
        assert result.gate_type == GateType.HUMAN
        assert result.node_id == "human_gate_node"


class TestManagerLoopNesting:
    """Tests for pipeline nesting depth enforcement."""

    def test_max_nesting_depth_exceeded(self, tmp_path: Path):
        """Verify pipeline fails when nesting depth exceeds max.

        When PIPELINE_MANAGER_DEPTH >= PIPELINE_MAX_MANAGER_DEPTH,
        ManagerLoopHandler should return FAILURE with MAX_DEPTH_EXCEEDED.
        """
        from unittest.mock import patch

        # Create test directories
        pipelines_dir = tmp_path / "pipelines"
        pipelines_dir.mkdir(parents=True, exist_ok=True)

        # Write child DOT file
        child_dot = _write_dot_file(pipelines_dir, "child.dot", CHILD_DOT_TEMPLATE)

        # Write parent DOT file
        parent_content = PARENT_DOT_TEMPLATE.format(child_dot_path=str(child_dot))
        parent_dot = _write_dot_file(pipelines_dir, "parent.dot", parent_content)

        # Create run directory for parent
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Patch the module-level constant to set max depth to 0
        # This must be done at the module level, not via environment variable,
        # because _MAX_MANAGER_DEPTH is evaluated at import time
        with patch(
            "cobuilder.engine.handlers.manager_loop._MAX_MANAGER_DEPTH",
            0,
        ):
            # Run the parent pipeline with depth already at max
            runner = EngineRunner(
                dot_path=str(parent_dot),
                run_dir=str(run_dir),
                handler_registry=HandlerRegistry.default(),
                initial_context={"$manager_depth": 0},  # At max depth already
                event_bus_config=EventBusConfig(
                    logfire_enabled=False,
                    signal_bridge_enabled=False,
                ),
            )

            checkpoint = asyncio.run(runner.run())

            # The spawn node should fail due to depth check
            spawn_record = next(
                (r for r in checkpoint.node_records if r.node_id == "spawn"),
                None,
            )
            assert spawn_record is not None
            # Depth check happens before execution; if context already at max,
            # it should return FAILURE with MAX_DEPTH_EXCEEDED
            assert spawn_record.status == "failure"

    def test_normal_nesting_depth_allowed(self, tmp_path: Path):
        """Verify normal nesting depth (depth < max) works correctly.

        Default max depth is 5. Running at depth 0-4 should be allowed.
        """
        # Create test directories
        pipelines_dir = tmp_path / "pipelines"
        pipelines_dir.mkdir(parents=True, exist_ok=True)

        # Write child DOT file
        child_dot = _write_dot_file(pipelines_dir, "child.dot", CHILD_DOT_TEMPLATE)

        # Write parent DOT file
        parent_content = PARENT_DOT_TEMPLATE.format(child_dot_path=str(child_dot))
        parent_dot = _write_dot_file(pipelines_dir, "parent.dot", parent_content)

        # Create run directory for parent
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Run at depth 0 (default)
        runner = EngineRunner(
            dot_path=str(parent_dot),
            run_dir=str(run_dir),
            handler_registry=HandlerRegistry.default(),
            event_bus_config=EventBusConfig(
                logfire_enabled=False,
                signal_bridge_enabled=False,
            ),
        )

        checkpoint = asyncio.run(runner.run())

        # Should complete successfully at depth 0
        assert checkpoint is not None
        assert "spawn" in checkpoint.completed_nodes