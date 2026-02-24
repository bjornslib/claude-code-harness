"""escalate_to_terminal.py — Write escalation signal for Layer 0 (Terminal/User).

Usage:
    python escalate_to_terminal.py --pipeline <pipeline_id> --issue <text>
        [--options <json>]

Output (stdout, JSON):
    {"status": "ok", "signal_file": "<path>"}

On error:
    {"status": "error", "message": "<error>"}
    exits with code 1
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
        prog="escalate_to_terminal.py",
        description="Escalate a blocking issue to the Terminal (Layer 0 / user).",
    )
    parser.add_argument("--pipeline", required=True, help="Pipeline identifier")
    parser.add_argument("--issue", required=True, help="Description of the issue")
    parser.add_argument(
        "--options",
        default=None,
        help="JSON-encoded options for the user (e.g., '[\"retry\", \"skip\"]')",
    )

    args = parser.parse_args()

    payload: dict = {
        "pipeline_id": args.pipeline,
        "issue": args.issue,
    }
    if args.options is not None:
        try:
            payload["options"] = json.loads(args.options)
        except json.JSONDecodeError as exc:
            print(json.dumps({
                "status": "error",
                "message": f"Invalid --options JSON: {exc}",
            }))
            sys.exit(1)

    try:
        signal_file = write_signal(
            source="guardian",
            target="terminal",
            signal_type="ESCALATE",
            payload=payload,
        )
        print(json.dumps({
            "status": "ok",
            "signal_file": signal_file,
        }))
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
