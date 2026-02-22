#!/usr/bin/env python3
"""
Notification hook: gchat-notification-dispatch.py
===================================================

Forwards Claude Code notifications to Google Chat via the gchat-send.sh CLI.

This hook fires on every Claude Code Notification event and sends a summary
to GChat. It is fire-and-forget — failures are silently swallowed to avoid
blocking Claude Code operation.

Hook type : Notification
Input     : JSON on stdin — {"message": "...", "session_id": "...", ...}
Output    : Always exits 0 (notifications must not block Claude Code)

GChat Integration:
  - Calls $CLAUDE_PROJECT_DIR/.claude/scripts/gchat-send.sh
  - Determines message type from notification content
  - Includes session context in message footer
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


# ---------------------------------------------------------------------------
# Notification Type Detection
# ---------------------------------------------------------------------------


def detect_message_type(message: str) -> str:
    """
    Infer the gchat-send --type from the notification message content.

    Returns one of: task_completion, progress_update, blocked_alert,
                    error, heartbeat, message
    """
    if not message:
        return "message"

    lower = message.lower()

    # Task / subagent completion signals
    if any(kw in lower for kw in ("complete", "completed", "done", "finished", "success")):
        return "task_completion"

    # Error signals
    if any(kw in lower for kw in ("error", "failed", "failure", "exception", "traceback")):
        return "error"

    # Blocked / waiting signals
    if any(kw in lower for kw in ("blocked", "waiting", "stuck", "need", "attention")):
        return "blocked_alert"

    # Heartbeat / health signals
    if any(kw in lower for kw in ("heartbeat", "healthy", "alive", "status")):
        return "heartbeat"

    # Progress signals
    if any(kw in lower for kw in ("progress", "working", "started", "in progress", "%")):
        return "progress_update"

    return "message"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    # Extract notification fields
    message: str = hook_input.get("message", "")
    session_id: str = hook_input.get("session_id", os.environ.get("CLAUDE_SESSION_ID", ""))
    title: str = hook_input.get("title", "")

    # Truncate very long messages (GChat has limits and this is a summary)
    max_msg_len = 800
    if len(message) > max_msg_len:
        message = message[:max_msg_len] + "…"

    if not message:
        # Nothing to send
        sys.exit(0)

    # ── Suppress generic "waiting for input" notifications ──
    # These are fired by Claude Code when AskUserQuestion is shown interactively
    # (non-S3 sessions). They carry no question content — just noise.
    # S3 sessions forward the full question via gchat-ask-user-forward.py instead.
    lower_msg = message.lower()
    if any(phrase in lower_msg for phrase in (
        "waiting for your input",
        "waiting for input",
        "is waiting for",
    )):
        sys.exit(0)

    # Detect type for appropriate formatting
    msg_type = detect_message_type(message)

    # Resolve gchat-send script
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if project_dir:
        gchat_send = os.path.join(project_dir, ".claude", "scripts", "gchat-send.sh")
    else:
        # Fallback: search relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        gchat_send = os.path.join(script_dir, "..", "scripts", "gchat-send.sh")
        gchat_send = os.path.normpath(gchat_send)

    if not os.path.isfile(gchat_send):
        # gchat-send not found — silently exit (don't block Claude Code)
        sys.exit(0)

    # Build command
    cmd: list[str] = [gchat_send, "--type", msg_type]

    if title:
        cmd += ["--title", title]

    if session_id:
        cmd += ["--session", session_id]

    cmd.append(message)

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            timeout=5,  # Hard limit — notifications must not block
            check=False,  # Don't raise on non-zero exit
        )
    except Exception:
        # Silently swallow all errors (fire-and-forget)
        pass

    # Always exit 0 — notification hooks must not interfere with Claude Code
    sys.exit(0)


if __name__ == "__main__":
    main()
