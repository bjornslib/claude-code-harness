#!/usr/bin/env python3
"""Main entry point for unified stop gate hook.

This module reads JSON from stdin, runs the PriorityEvaluator,
and outputs formatted JSON to stdout.

Usage:
    echo '{"session_id": "abc", "iteration": 5}' | python -m unified_stop_gate.main
"""

import json
import sys
from typing import Any, Dict

from .checkers import SessionInfo
from .config import EnvironmentConfig
from .evaluator import PriorityEvaluator
from .formatter import DecisionFormatter


def parse_stdin() -> Dict[str, Any]:
    """Read and parse JSON from stdin.

    Returns:
        Parsed JSON dict, or empty dict on error.
    """
    try:
        input_text = sys.stdin.read()
        if not input_text.strip():
            return {}
        return json.loads(input_text)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"Warning: Invalid JSON input: {e}\n")
        return {}
    except Exception as e:
        sys.stderr.write(f"Warning: Error reading stdin: {e}\n")
        return {}


def main() -> None:
    """Main entry point for the unified stop gate hook."""
    try:
        # Parse input from stdin
        hook_input = parse_stdin()

        # Load configuration from environment
        config = EnvironmentConfig.from_env()

        # Extract session info from hook input
        session = SessionInfo.from_hook_input(hook_input)

        # Run priority evaluation
        evaluator = PriorityEvaluator(config, session)
        result = evaluator.evaluate()

        # Format and output result
        output = DecisionFormatter.format(result)
        print(json.dumps(output, indent=2))

    except Exception as e:
        # On any error, approve to avoid blocking
        # but include error information
        output = DecisionFormatter.format_error(e)
        print(json.dumps(output, indent=2))
        sys.stderr.write(f"Error in unified stop gate: {e}\n")


if __name__ == "__main__":
    main()
