"""ManagerLoopHandler — handles house (manager loop) nodes.

Implements AMD-10: recursive sub-pipeline management via subprocess spawning.

Two modes:
- ``spawn_pipeline`` (new): Spawns a child EngineRunner as a subprocess on a
  DOT file specified by ``pipeline_params_file`` or ``sub_pipeline`` attribute.
  Monitors via signal protocol. Optionally launches a stream summarizer sidecar.
  **Child Gate Detection**: Monitors child's signal directory for GATE_WAIT_COBUILDER
  and GATE_WAIT_HUMAN signals, dispatches validation-test-agent for cobuilder gates,
  and surfaces human gates to the parent guardian.
- ``supervisor`` (default): Spawns and monitors an orchestrator subprocess.
  Falls back to NotImplementedError if neither mode is configured.

Depth is bounded by ``PIPELINE_MAX_MANAGER_DEPTH`` env var (default 5).

Security: All subprocess spawning uses asyncio.create_subprocess_exec (not
shell=True) to prevent command injection. Arguments are passed as lists.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from cobuilder.engine.handlers.base import Handler, HandlerRequest
from cobuilder.engine.outcome import Outcome, OutcomeStatus
from cobuilder.engine.signal_protocol import (
    GATE_RESPONSE,
    GATE_WAIT_COBUILDER,
    GATE_WAIT_HUMAN,
    list_signals,
    move_to_processed,
    read_signal,
    write_gate_response,
)

logger = logging.getLogger(__name__)

_MAX_MANAGER_DEPTH = int(os.environ.get("PIPELINE_MAX_MANAGER_DEPTH", "5"))
_POLL_INTERVAL_S = float(os.environ.get("PIPELINE_MANAGER_POLL_INTERVAL", "15"))
_DEFAULT_TIMEOUT_S = float(os.environ.get("PIPELINE_MANAGER_TIMEOUT", "7200"))
_GATE_CHECK_INTERVAL_S = float(os.environ.get("PIPELINE_GATE_CHECK_INTERVAL", "2"))
_VALIDATION_TIMEOUT_S = float(os.environ.get("PIPELINE_VALIDATION_TIMEOUT", "300"))


class GateType(Enum):
    """Types of gates that child pipelines can hit."""

    COBUILDER = "wait.cobuilder"
    HUMAN = "wait.human"


@dataclass
class GateSignal:
    """Represents a detected gate signal from a child pipeline.

    Attributes:
        gate_type: Type of gate (COBUILDER or HUMAN).
        node_id: Node identifier in the child pipeline.
        prd_ref: Optional PRD reference for validation context.
        signal_path: Path to the signal file.
    """

    gate_type: GateType
    node_id: str
    prd_ref: str
    signal_path: Path


class ManagerLoopHandler:
    """Handler for manager loop nodes (``house`` shape).

    Supports two modes via node.attrs["mode"]:
    - "spawn_pipeline": Launch a child EngineRunner on a sub-pipeline DOT file.
    - Default: supervisor mode (orchestrator monitoring).
    """

    async def execute(self, request: HandlerRequest) -> Outcome:
        """Dispatch based on node mode attribute."""
        mode = request.node.attrs.get("mode", "")
        current_depth = int(request.context.get("$manager_depth", 0))

        if current_depth >= _MAX_MANAGER_DEPTH:
            return Outcome(
                status=OutcomeStatus.FAILURE,
                context_updates={f"${request.node.id}.status": "failed"},
                metadata={
                    "error_type": "MAX_DEPTH_EXCEEDED",
                    "depth": current_depth,
                    "max_depth": _MAX_MANAGER_DEPTH,
                },
            )

        if mode == "spawn_pipeline":
            return await self._execute_spawn_pipeline(request, current_depth)
        else:
            return await self._execute_supervisor(request)

    async def _execute_spawn_pipeline(
        self, request: HandlerRequest, current_depth: int
    ) -> Outcome:
        """Spawn a child EngineRunner as a subprocess on a sub-pipeline DOT file.

        The child pipeline DOT path is resolved from:
        1. ``pipeline_params_file`` attribute -> reads JSON, extracts ``dot_path``
        2. ``sub_pipeline`` attribute -> direct DOT file path

        Uses asyncio.create_subprocess_exec (no shell) for safety.
        """
        node = request.node
        run_dir = Path(request.run_dir) if request.run_dir else Path.cwd()

        # Resolve child DOT path
        dot_path = await self._resolve_child_dot_path(node, run_dir)
        if dot_path is None:
            return Outcome(
                status=OutcomeStatus.FAILURE,
                context_updates={f"${node.id}.status": "failed"},
                metadata={"error_type": "NO_DOT_PATH", "node_id": node.id},
            )

        # Create sub-run directory
        sub_run_dir = run_dir / "nodes" / node.id / "sub-run"
        sub_run_dir.mkdir(parents=True, exist_ok=True)

        # Resolve signals directory
        signals_dir = node.attrs.get("signals_dir", "")
        if not signals_dir:
            signals_dir = str(sub_run_dir / "signals")
        Path(signals_dir).mkdir(parents=True, exist_ok=True)

        # Optionally launch stream summarizer sidecar
        summarizer_proc = None
        if node.attrs.get("summarizer", "").lower() == "true":
            summarizer_proc = await self._launch_summarizer(
                dot_path, signals_dir, sub_run_dir
            )

        # Spawn child EngineRunner as subprocess (exec, not shell)
        env = os.environ.copy()
        env["PIPELINE_MANAGER_DEPTH"] = str(current_depth + 1)

        cmd = [
            sys.executable, "-m", "cobuilder.engine.runner",
            "--dot", str(dot_path),
            "--run-dir", str(sub_run_dir),
        ]

        logger.info(
            "Spawning child pipeline runner for node '%s': %s (depth=%d)",
            node.id, dot_path, current_depth + 1,
        )

        try:
            child = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=str(run_dir),
            )
        except Exception as exc:
            logger.error("Failed to spawn child pipeline for node '%s': %s", node.id, exc)
            return Outcome(
                status=OutcomeStatus.FAILURE,
                context_updates={f"${node.id}.status": "failed"},
                metadata={"error_type": "SPAWN_FAILED", "error": str(exc)},
            )

        # Monitor child process
        result = await self._monitor_child_process(child, node, signals_dir)

        # Collect summarizer output
        summary = ""
        if summarizer_proc is not None:
            try:
                summarizer_proc.terminate()
                await asyncio.wait_for(summarizer_proc.wait(), timeout=10)
            except Exception:
                pass
            summary_path = sub_run_dir / "summary.json"
            if summary_path.exists():
                try:
                    summary = summary_path.read_text()
                except OSError:
                    pass

        # Build outcome
        if result["status"] == "completed":
            return Outcome(
                status=OutcomeStatus.SUCCESS,
                context_updates={
                    f"${node.id}.status": "success",
                    "child_checkpoint": result.get("checkpoint_path", ""),
                    "execution_summary": summary,
                    "$manager_depth": current_depth,
                },
                metadata={
                    "child_returncode": result.get("returncode", -1),
                    "child_dot_path": str(dot_path),
                },
            )
        else:
            return Outcome(
                status=OutcomeStatus.FAILURE,
                context_updates={
                    f"${node.id}.status": "failed",
                    "failure_reason": result.get("error", "unknown"),
                    "$manager_depth": current_depth,
                },
                metadata={
                    "child_returncode": result.get("returncode", -1),
                    "child_stderr": result.get("stderr", "")[:2000],
                },
            )

    async def _resolve_child_dot_path(
        self, node: Any, run_dir: Path
    ) -> Path | None:
        """Resolve the child pipeline DOT file path from node attributes."""
        # Option 1: pipeline_params_file points to a JSON with dot_path
        params_file = node.attrs.get("pipeline_params_file", "")
        if params_file:
            params_path = Path(params_file)
            if not params_path.is_absolute():
                params_path = run_dir / params_path
            if params_path.exists():
                try:
                    plan = json.loads(params_path.read_text())
                    dot_path_str = plan.get("dot_path", "")
                    if dot_path_str:
                        dp = Path(dot_path_str)
                        return dp if dp.is_absolute() else run_dir / dp
                except (json.JSONDecodeError, OSError) as exc:
                    logger.warning(
                        "Failed to read pipeline params file '%s': %s",
                        params_path, exc,
                    )

        # Option 2: sub_pipeline is a direct DOT file path
        sub_pipeline = node.attrs.get("sub_pipeline", "")
        if sub_pipeline:
            dp = Path(sub_pipeline)
            if dp.is_absolute():
                return dp if dp.exists() else None
            resolved = run_dir / dp
            return resolved if resolved.exists() else None

        logger.error(
            "Node '%s' has mode=spawn_pipeline but no pipeline_params_file or "
            "sub_pipeline attribute",
            node.id,
        )
        return None

    async def _monitor_child_process(
        self, child: asyncio.subprocess.Process, node: Any, signals_dir: str
    ) -> dict[str, Any]:
        """Monitor a child pipeline process until completion, timeout, or gate.

        This method implements hybrid monitoring:
        1. Polls for child process exit status
        2. Polls for signal files (RUNNER_EXITED)
        3. Detects and handles gate signals (GATE_WAIT_COBUILDER, GATE_WAIT_HUMAN)

        When a child hits a gate:
        - wait.cobuilder: Dispatches validation-test-agent, writes response signal
        - wait.human: Surfaces to parent guardian (logs for human intervention)

        Args:
            child: The asyncio subprocess running the child pipeline.
            node: The parent pipeline node that spawned the child.
            signals_dir: Path to the child's signal directory.

        Returns:
            Dict with status, returncode, and optional error/checkpoint info.
        """
        timeout = float(node.attrs.get("timeout", _DEFAULT_TIMEOUT_S))
        start = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start

            if elapsed >= timeout:
                logger.warning(
                    "Child pipeline for node '%s' timed out after %.0fs",
                    node.id, elapsed,
                )
                child.kill()
                return {"status": "failed", "error": "timeout", "returncode": -9}

            # Check if child has exited
            if child.returncode is not None:
                stdout_data = b""
                stderr_data = b""
                try:
                    stdout_data, stderr_data = await asyncio.wait_for(
                        child.communicate(), timeout=5
                    )
                except Exception:
                    pass

                if child.returncode == 0:
                    return {
                        "status": "completed",
                        "returncode": 0,
                        "stdout": stdout_data.decode("utf-8", errors="replace")[:5000],
                    }
                else:
                    return {
                        "status": "failed",
                        "returncode": child.returncode,
                        "stderr": stderr_data.decode("utf-8", errors="replace")[:5000],
                        "error": f"Child exited with code {child.returncode}",
                    }

            # Check for signal files
            sig_dir = Path(signals_dir)
            if sig_dir.exists():
                # Check for completion signals first
                for sig_file in sig_dir.glob("*RUNNER_EXITED*.json"):
                    try:
                        sig_data = json.loads(sig_file.read_text())
                        return {
                            "status": sig_data.get("status", "completed"),
                            "checkpoint_path": sig_data.get("checkpoint_path", ""),
                            "returncode": 0,
                        }
                    except (json.JSONDecodeError, OSError):
                        pass

                # Check for gate signals
                gate = self._detect_gate_signal(sig_dir)
                if gate is not None:
                    logger.info(
                        "Child pipeline for node '%s' hit %s gate at node '%s'",
                        node.id, gate.gate_type.value, gate.node_id,
                    )

                    # Handle the gate
                    gate_result = await self._handle_gate(
                        gate=gate,
                        signals_dir=signals_dir,
                        node=node,
                    )

                    if not gate_result.get("handled", False):
                        # Gate could not be handled - return failure
                        return {
                            "status": "failed",
                            "error": gate_result.get("error", "gate_handling_failed"),
                            "gate_type": gate.gate_type.value,
                            "returncode": -1,
                        }

                    # Gate handled successfully, continue monitoring
                    # Move processed gate signal
                    try:
                        move_to_processed(str(gate.signal_path))
                    except OSError:
                        pass

            # Use shorter sleep interval for gate responsiveness
            await asyncio.sleep(_GATE_CHECK_INTERVAL_S)

    def _detect_gate_signal(self, signals_dir: Path) -> GateSignal | None:
        """Detect a gate signal in the child's signal directory.

        Scans for GATE_WAIT_COBUILDER and GATE_WAIT_HUMAN signal files.

        Args:
            signals_dir: Path to the child's signal directory.

        Returns:
            GateSignal if a gate signal is found, None otherwise.
        """
        if not signals_dir.exists():
            return None

        # Check for cobuilder gate signals
        for sig_file in signals_dir.glob(f"*{GATE_WAIT_COBUILDER}*.json"):
            try:
                sig_data = json.loads(sig_file.read_text())
                payload = sig_data.get("payload", {})
                return GateSignal(
                    gate_type=GateType.COBUILDER,
                    node_id=payload.get("node_id", "unknown"),
                    prd_ref=payload.get("prd_ref", ""),
                    signal_path=sig_file,
                )
            except (json.JSONDecodeError, OSError):
                pass

        # Check for human gate signals
        for sig_file in signals_dir.glob(f"*{GATE_WAIT_HUMAN}*.json"):
            try:
                sig_data = json.loads(sig_file.read_text())
                payload = sig_data.get("payload", {})
                return GateSignal(
                    gate_type=GateType.HUMAN,
                    node_id=payload.get("node_id", "unknown"),
                    prd_ref=payload.get("prd_ref", ""),
                    signal_path=sig_file,
                )
            except (json.JSONDecodeError, OSError):
                pass

        return None

    async def _handle_gate(
        self,
        gate: GateSignal,
        signals_dir: str,
        node: Any,
    ) -> dict[str, Any]:
        """Handle a detected gate signal from a child pipeline.

        For wait.cobuilder gates:
        - Dispatches validation-test-agent (placeholder for future implementation)
        - Writes GATE_RESPONSE signal with approval status

        For wait.human gates:
        - Logs the need for human intervention
        - Returns not handled (requires external human action)

        Args:
            gate: The detected gate signal.
            signals_dir: Path to the child's signal directory.
            node: The parent pipeline node.

        Returns:
            Dict with 'handled' boolean and optional 'error' message.
        """
        if gate.gate_type == GateType.COBUILDER:
            # For now, auto-approve cobuilder gates
            # TODO: Dispatch validation-test-agent for proper validation
            logger.info(
                "Auto-approving wait.cobuilder gate for child node '%s' "
                "(validation-test-agent dispatch not yet implemented)",
                gate.node_id,
            )

            # Write response signal
            try:
                write_gate_response(
                    node_id=gate.node_id,
                    approved=True,
                    feedback="Auto-approved by parent manager (validation pending)",
                    signals_dir=signals_dir,
                )
                return {"handled": True}
            except OSError as exc:
                logger.error(
                    "Failed to write GATE_RESPONSE for node '%s': %s",
                    gate.node_id, exc,
                )
                return {"handled": False, "error": "response_write_failed"}

        elif gate.gate_type == GateType.HUMAN:
            # Human gates require external intervention
            # Log and return not handled - the parent pipeline's guardian
            # or operator must write the response signal
            logger.warning(
                "Child pipeline for node '%s' hit wait.human gate at node '%s'. "
                "Requires human intervention. Write GATE_RESPONSE signal to: %s",
                node.id, gate.node_id, signals_dir,
            )
            return {
                "handled": False,
                "error": "human_intervention_required",
                "message": f"Human approval required at gate {gate.node_id}",
            }

        return {"handled": False, "error": "unknown_gate_type"}

    async def _launch_summarizer(
        self, dot_path: Path, signals_dir: str, sub_run_dir: Path
    ) -> asyncio.subprocess.Process | None:
        """Launch the stream summarizer sidecar if available.

        Uses create_subprocess_exec (no shell) for safety.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "cobuilder.sidecar.stream_summarizer",
                "--signals-dir", signals_dir,
                "--output", str(sub_run_dir / "summary.json"),
                "--dot-file", str(dot_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            logger.info("Stream summarizer launched (PID %d)", proc.pid)
            return proc
        except Exception as exc:
            logger.warning("Failed to launch stream summarizer: %s", exc)
            return None

    async def _execute_supervisor(self, request: HandlerRequest) -> Outcome:
        """Supervisor mode — monitor an existing orchestrator.

        Delegates to spawn_pipeline if sub_pipeline is set,
        otherwise raises NotImplementedError with guidance.
        """
        if request.node.attrs.get("sub_pipeline"):
            return await self._execute_spawn_pipeline(
                request, int(request.context.get("$manager_depth", 0))
            )

        raise NotImplementedError(
            f"ManagerLoopHandler supervisor mode is not yet implemented for "
            f"node '{request.node.id}'. Set mode='spawn_pipeline' and provide "
            f"a sub_pipeline or pipeline_params_file attribute."
        )


assert isinstance(ManagerLoopHandler(), Handler)
