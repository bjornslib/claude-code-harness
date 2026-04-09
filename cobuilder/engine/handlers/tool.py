"""ToolHandler — handles parallelogram (shell tool) nodes.

Executes ``node.tool_command`` via ``subprocess.run(shell=True)`` in the
pipeline run directory with a configurable timeout.

AC-F12:
- Executes ``node.tool_command`` via ``subprocess.run(shell=True)`` in ``run_dir``.
- Returns ``Outcome(status=SUCCESS)`` for exit code 0.
- Returns ``Outcome(status=FAILURE)`` for non-zero exit codes.
- Captures stdout/stderr into context_updates.
- Timeout: ``PIPELINE_TOOL_TIMEOUT`` seconds (default 300s).

JSON output parsing (Epic 1):
- When ``parse_json_output="true"`` is set on a node, stdout is parsed as JSON.
- If stdout is a valid JSON object, each key is stored as ``${node_id}.{key}``
  in context_updates in addition to the raw ``${node_id}.stdout`` value.
- Non-JSON stdout is silently ignored (debug-level log); raw stdout is always stored.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path

from cobuilder.engine.exceptions import HandlerError
from cobuilder.engine.handlers.base import Handler, HandlerRequest
from cobuilder.engine.outcome import Outcome, OutcomeStatus

logger = logging.getLogger(__name__)

_DEFAULT_TOOL_TIMEOUT_S = 300


class ToolHandler:
    """Shell command executor for tool nodes (``parallelogram`` shape).

    Runs ``node.tool_command`` in a subprocess.  Stdout and stderr are
    captured and stored in the context so downstream nodes and edge
    conditions can read them.

    Args:
        timeout_s: Subprocess timeout in seconds.  Defaults to the
                   ``PIPELINE_TOOL_TIMEOUT`` env var or 300s.
    """

    def __init__(self, timeout_s: float | None = None) -> None:
        self._timeout_s = timeout_s or float(
            os.environ.get("PIPELINE_TOOL_TIMEOUT", _DEFAULT_TOOL_TIMEOUT_S)
        )

    async def execute(self, request: HandlerRequest) -> Outcome:
        """Execute node.tool_command and return Outcome based on exit code.

        Args:
            request: HandlerRequest with node, context, run_dir.

        Returns:
            Outcome with status SUCCESS (exit 0) or FAILURE (non-zero).

        Raises:
            HandlerError: If the command cannot be started (e.g. command
                          not found, permission denied).
        """
        node = request.node
        command = node.tool_command

        if not command:
            # No command — this is a no-op tool node; return SUCCESS
            logger.debug("ToolHandler '%s': no tool_command set; returning SUCCESS", node.id)
            return Outcome(
                status=OutcomeStatus.SUCCESS,
                context_updates={
                    f"${node.id}.exit_code": 0,
                    f"${node.id}.stdout": "",
                    f"${node.id}.stderr": "",
                },
                metadata={"command": "", "exit_code": 0},
            )

        # Run in the pipeline run directory if available
        cwd = request.run_dir if request.run_dir else None

        # Use asyncio to avoid blocking the event loop during subprocess.run
        outcome = await asyncio.to_thread(
            self._run_command,
            command=command,
            cwd=cwd,
            node_id=node.id,
            parse_json_output=node.parse_json_output,
        )
        return outcome

    def _run_command(
        self,
        command: str,
        cwd: str | None,
        node_id: str,
        parse_json_output: bool = False,
    ) -> Outcome:
        """Synchronous command execution (called in a thread via asyncio.to_thread).

        Args:
            command:           Shell command string to run.
            cwd:               Working directory; ``None`` inherits the runner process cwd.
            node_id:           Node ID used to name context keys.
            parse_json_output: When True, attempt to parse stdout as JSON and
                               store each key individually in context_updates.
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=self._timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            return Outcome(
                status=OutcomeStatus.FAILURE,
                context_updates={
                    f"${node_id}.exit_code": -1,
                    f"${node_id}.stdout": exc.stdout or "" if exc.stdout else "",
                    f"${node_id}.stderr": exc.stderr or "" if exc.stderr else "",
                },
                metadata={
                    "command": command,
                    "exit_code": -1,
                    "error_type": "TIMEOUT",
                    "timeout_s": self._timeout_s,
                },
            )
        except OSError as exc:
            raise HandlerError(
                f"Failed to run command '{command}': {exc}",
                node_id=node_id,
                cause=exc,
            )

        status = OutcomeStatus.SUCCESS if result.returncode == 0 else OutcomeStatus.FAILURE

        context_updates: dict = {
            f"${node_id}.exit_code": result.returncode,
            f"${node_id}.stdout": result.stdout,
            f"${node_id}.stderr": result.stderr,
        }

        # Optional JSON output parsing (Epic 1: structured tool output)
        if parse_json_output:
            parsed = self._try_parse_json(result.stdout, node_id)
            if parsed is not None:
                for key, value in parsed.items():
                    context_updates[f"${node_id}.{key}"] = value

        return Outcome(
            status=status,
            context_updates=context_updates,
            metadata={
                "command": command,
                "exit_code": result.returncode,
                "stdout_length": len(result.stdout),
                "stderr_length": len(result.stderr),
            },
        )

    @staticmethod
    def _try_parse_json(stdout: str, node_id: str) -> dict | None:
        """Attempt to parse *stdout* as a JSON object.

        Returns a dict on success, or None if stdout is not valid JSON or not
        a JSON object (e.g., a JSON array or scalar).  Non-JSON output is
        logged at DEBUG level — it is not an error.

        Args:
            stdout:  Raw stdout string from the subprocess.
            node_id: Used only for the debug log message.
        """
        stripped = stdout.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            logger.debug(
                "ToolHandler '%s': stdout is not valid JSON; skipping key extraction",
                node_id,
            )
            return None

        if not isinstance(parsed, dict):
            logger.debug(
                "ToolHandler '%s': JSON stdout is not a dict (got %s); skipping key extraction",
                node_id,
                type(parsed).__name__,
            )
            return None

        return parsed


assert isinstance(ToolHandler(), Handler)
