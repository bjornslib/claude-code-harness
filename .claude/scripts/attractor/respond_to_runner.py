"""respond_to_runner.py — Write Guardian response signal for Runner.

Usage:
    python respond_to_runner.py <SIGNAL_TYPE> --node <node_id>
        [--feedback <text>] [--response <text>] [--reason <text>]
        [--new-status <status>] [--message <text>]

Output (stdout, JSON):
    {"status": "ok", "signal_file": "<path>", "signal_type": "<type>"}

On error:
    {"status": "error", "message": "<error>"}
    exits with code 1

Note: Writes signal with source="guardian", target="runner".
"""

from __future__ import annotations

import argparse
import json
import sys
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from signal_protocol import write_signal  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="respond_to_runner.py",
        description="Write a Guardian response signal for Runner.",
    )
    parser.add_argument(
        "signal_type",
        metavar="SIGNAL_TYPE",
        help="Signal type (e.g., APPROVED, REJECTED, NEEDS_CHANGES)",
    )
    parser.add_argument("--node", required=True, help="Node identifier")
    parser.add_argument("--feedback", default=None, help="Feedback text")
    parser.add_argument("--response", default=None, help="Response text")
    parser.add_argument("--reason", default=None, help="Reason for decision")
    parser.add_argument("--new-status", default=None, dest="new_status",
                        help="New status to assign")
    parser.add_argument("--message", default=None, help="Additional message")

    args = parser.parse_args()

    payload: dict = {"node_id": args.node}
    if args.feedback is not None:
        payload["feedback"] = args.feedback
    if args.response is not None:
        payload["response"] = args.response
    if args.reason is not None:
        payload["reason"] = args.reason
    if args.new_status is not None:
        payload["new_status"] = args.new_status
    if args.message is not None:
        payload["message"] = args.message

    try:
        signal_file = write_signal(
            source="guardian",
            target="runner",
            signal_type=args.signal_type,
            payload=payload,
        )
        print(json.dumps({
            "status": "ok",
            "signal_file": signal_file,
            "signal_type": args.signal_type,
        }))
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
