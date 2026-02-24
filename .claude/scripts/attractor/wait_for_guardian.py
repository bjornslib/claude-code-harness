"""wait_for_guardian.py — Block until Guardian writes a response for Runner.

Filters for signals with target="runner".

Usage:
    python wait_for_guardian.py --node <node_id> [--timeout <seconds>]

Output (stdout, JSON):
    The signal JSON dict.

On timeout or error:
    {"status": "error", "message": "<error>"}
    exits with code 1
"""

from __future__ import annotations

import argparse
import json
import sys
import os
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from signal_protocol import (  # noqa: E402
    list_signals,
    read_signal,
    move_to_processed,
    _resolve_signals_dir,
    _ensure_dirs,
)


def wait_for_guardian_response(
    node_id: str,
    timeout: float = 300.0,
    poll_interval: float = 5.0,
    signals_dir: str = None,
) -> dict:
    """Wait for a Guardian response signal targeting the runner for a specific node.

    Filters signals with target="runner" and payload.node_id matching the given node_id.

    Args:
        node_id: The node identifier to match in the signal payload.
        timeout: Maximum seconds to wait.
        poll_interval: Seconds between polls.
        signals_dir: Override the default signals directory.

    Returns:
        Parsed signal dict.

    Raises:
        TimeoutError: If no matching signal appears within timeout.
    """
    resolved_dir = _resolve_signals_dir(signals_dir)
    _ensure_dirs(resolved_dir)

    deadline = time.monotonic() + timeout

    while True:
        runner_signals = list_signals(target_layer="runner", signals_dir=resolved_dir)
        for path in runner_signals:
            try:
                data = read_signal(path)
                # Check if this signal is for our node
                payload = data.get("payload", {})
                if payload.get("node_id") == node_id:
                    move_to_processed(path)
                    return data
            except Exception:
                continue

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"No Guardian response for node '{node_id}' within {timeout}s"
            )

        sleep_time = min(poll_interval, remaining)
        if sleep_time <= 0:
            raise TimeoutError(
                f"No Guardian response for node '{node_id}' within {timeout}s"
            )
        time.sleep(sleep_time)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wait_for_guardian.py",
        description="Block until Guardian writes a response for Runner.",
    )
    parser.add_argument("--node", required=True, help="Node identifier to wait for")
    parser.add_argument(
        "--timeout", type=float, default=300.0, help="Timeout in seconds (default: 300)"
    )

    args = parser.parse_args()

    try:
        signal_data = wait_for_guardian_response(
            node_id=args.node,
            timeout=args.timeout,
        )
        print(json.dumps(signal_data))
    except TimeoutError as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        sys.exit(1)
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
