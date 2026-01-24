"""Signal classifier for decision-time guidance.

Lightweight classifier that analyzes the agent's current state and decides
which guidance (if any) to inject. Runs on every PostToolUse call, so it
must be fast (<10ms).

Design principles (from Replit):
- False positives are cheap (guidance is suggestions, not constraints)
- Tune for recall over precision
- Limit concurrent guidance to avoid competition
"""

import os
import re
from pathlib import Path
from typing import Optional

from .state_manager import ErrorTracker, EditHistory
from .guidance_bank import GuidanceBank


class SignalClassifier:
    """Classify signals and decide which guidance to inject."""

    # Edit tools that indicate implementation work
    EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

    # Error patterns in tool output
    ERROR_PATTERNS = [
        r"error:",
        r"Error:",
        r"ERROR",
        r"failed",
        r"Failed",
        r"FAILED",
        r"not found",
        r"No such file",
        r"does not exist",
        r"Permission denied",
        r"command not found",
        r"ModuleNotFoundError",
        r"ImportError",
        r"SyntaxError",
        r"TypeError",
        r"ValueError",
        r"KeyError",
        r"AttributeError",
        r"NameError",
        r"FileNotFoundError",
        r"Exception",
        r"Traceback",
    ]

    def __init__(self, state_dir: Optional[Path] = None):
        if state_dir is None:
            project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
            state_dir = Path(project_dir) / ".claude" / "state" / "decision-guidance"

        self.state_dir = state_dir
        self.error_tracker = ErrorTracker(state_dir=state_dir)
        self.edit_history = EditHistory(state_dir=state_dir)
        self.session_id = os.environ.get("CLAUDE_SESSION_ID", "")

    def is_orchestrator_session(self) -> bool:
        """Check if this is an orchestrator session."""
        return self.session_id.startswith("orch-")

    def classify_tool_result(self, hook_input: dict) -> list[tuple[str, dict]]:
        """Classify a tool result and return guidance candidates.

        Args:
            hook_input: The PostToolUse hook input containing tool_name and result.

        Returns:
            List of (guidance_key, kwargs) tuples for guidance to inject.
        """
        candidates = []

        tool_name = hook_input.get("tool_name", "")
        tool_input = hook_input.get("tool_input", {})
        tool_result = hook_input.get("tool_result", {})

        # Extract relevant info from result
        output = str(tool_result.get("output", ""))[:2000]  # Limit for speed
        error = tool_result.get("error")
        exit_code = tool_result.get("exit_code", 0)

        # Check for errors
        is_error = self._detect_error(output, error, exit_code)

        if is_error:
            error_type = self._classify_error_type(output, error)
            self.error_tracker.record_error(
                tool_name=tool_name,
                error_type=error_type,
                message=self._extract_error_message(output, error),
            )

            # Check if error threshold reached
            if self.error_tracker.is_threshold_reached():
                summary = self.error_tracker.get_error_summary()
                candidates.append((
                    "error_recovery",
                    {
                        "error_count": summary["count"],
                        "window_minutes": summary["window_seconds"] // 60,
                        "error_messages": "\n".join(f"- {m}" for m in summary["messages"]),
                    }
                ))

        # Track file edits
        if tool_name in self.EDIT_TOOLS:
            file_path = self._extract_file_path(tool_input)
            if file_path:
                success = not is_error
                self.edit_history.record_edit(
                    file_path=file_path,
                    tool_name=tool_name,
                    success=success,
                )

                # Check for doom loop
                doom_loop = self.edit_history.detect_doom_loop()
                if doom_loop:
                    candidates.append((
                        "doom_loop",
                        {
                            "file_details": "\n".join(
                                f"- {f}: {c} edits"
                                for f, c in doom_loop["files"].items()
                            ),
                        }
                    ))

                # Check for delegation violation (orchestrator using edit tools)
                if self.is_orchestrator_session():
                    candidates.append((
                        "delegation_reminder",
                        {
                            "tool_name": tool_name,
                            "task_id": "current",  # Would need task tracking
                        }
                    ))

        # Check for "not found" patterns
        if self._detect_not_found(output):
            candidates.append((
                "not_found_reminder",
                {}
            ))

        return candidates

    def _detect_error(
        self,
        output: str,
        error: Optional[str],
        exit_code: int,
    ) -> bool:
        """Detect if the tool result indicates an error."""
        if error:
            return True
        if exit_code != 0:
            return True

        # Check output for error patterns (limit scan for speed)
        output_sample = output[:1000].lower()
        for pattern in self.ERROR_PATTERNS[:10]:  # Check most common first
            if re.search(pattern, output_sample, re.IGNORECASE):
                return True

        return False

    def _classify_error_type(
        self,
        output: str,
        error: Optional[str],
    ) -> str:
        """Classify the type of error."""
        text = (error or output)[:500].lower()

        if "not found" in text or "no such file" in text or "does not exist" in text:
            return "not_found"
        if "permission" in text:
            return "permission"
        if "syntax" in text:
            return "syntax"
        if "import" in text or "module" in text:
            return "import"
        if "timeout" in text:
            return "timeout"
        if "connection" in text or "network" in text:
            return "network"

        return "general"

    def _extract_error_message(
        self,
        output: str,
        error: Optional[str],
    ) -> str:
        """Extract a concise error message."""
        text = error or output

        # Try to find the first error line
        for line in text.split("\n"):
            line = line.strip()
            if any(p.lower() in line.lower() for p in ["error", "Error", "failed", "Failed"]):
                return line[:200]

        # Fall back to first non-empty line
        for line in text.split("\n"):
            line = line.strip()
            if line:
                return line[:200]

        return "Unknown error"

    def _extract_file_path(self, tool_input: dict) -> Optional[str]:
        """Extract file path from tool input."""
        # Different tools use different keys
        for key in ["file_path", "path", "file"]:
            if key in tool_input:
                return tool_input[key]
        return None

    def _detect_not_found(self, output: str) -> bool:
        """Detect if output indicates a resource was not found."""
        output_lower = output[:500].lower()
        patterns = [
            "not found",
            "no such file",
            "does not exist",
            "cannot find",
            "no matches found",
        ]
        return any(p in output_lower for p in patterns)

    def get_guidance_to_inject(self, hook_input: dict) -> Optional[str]:
        """Main entry point: analyze tool result and return guidance if needed.

        Args:
            hook_input: PostToolUse hook input.

        Returns:
            Formatted guidance string to inject, or None if no guidance needed.
        """
        candidates = self.classify_tool_result(hook_input)

        if not candidates:
            return None

        # Select top guidance (respects priority and max count)
        guidance_list = GuidanceBank.select_guidance(candidates)

        if not guidance_list:
            return None

        # Join multiple guidance with separator
        return "\n\n---\n\n".join(guidance_list)
