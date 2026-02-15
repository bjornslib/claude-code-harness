"""Google Chat Bridge MCP Server.

FastMCP server providing Google Chat integration tools for System 3.
Runs as stdio transport for use as an MCP server in Claude Code.

Environment Variables:
    GOOGLE_CHAT_CREDENTIALS_FILE: Path to service account JSON key file (required).
    GOOGLE_CHAT_SPACE_ID: Default Google Chat space ID (optional, can be passed per-call).

Tools:
    send_chat_message     - Send a message to a Google Chat space
    get_new_messages      - Get unread messages since last check
    mark_messages_read    - Mark messages as read (update read watermark)
    send_task_completion  - Send a structured task completion notification
    get_message_stats     - Get message statistics and read state
    test_webhook_connection - Test the Google Chat API connection
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastmcp import FastMCP

from google_chat_bridge.chat_client import ChatClient
from google_chat_bridge.state import ReadStateManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server initialization
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="google-chat-bridge",
    instructions=(
        "Google Chat Bridge provides tools for sending and receiving messages "
        "in Google Chat spaces. Use send_chat_message for outbound messages, "
        "get_new_messages to check for user responses, and mark_messages_read "
        "to advance the read watermark. Service account credentials must be "
        "configured via GOOGLE_CHAT_CREDENTIALS_FILE environment variable."
    ),
)

# Lazy-initialized singletons
_client: ChatClient | None = None
_state_manager: ReadStateManager | None = None


def _get_client() -> ChatClient:
    """Get or create the Google Chat API client."""
    global _client
    if _client is None:
        creds_file = os.environ.get("GOOGLE_CHAT_CREDENTIALS_FILE", "")
        if not creds_file:
            raise RuntimeError(
                "GOOGLE_CHAT_CREDENTIALS_FILE environment variable is not set. "
                "Set it to the path of your Google service account JSON key file."
            )
        default_space = os.environ.get("GOOGLE_CHAT_SPACE_ID", "")
        _client = ChatClient(
            credentials_file=creds_file,
            default_space_id=default_space,
        )
    return _client


def _get_state_manager() -> ReadStateManager:
    """Get or create the read state manager."""
    global _state_manager
    if _state_manager is None:
        _state_manager = ReadStateManager()
    return _state_manager


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def send_chat_message(
    text: str,
    space_id: str = "",
    thread_key: str = "",
) -> dict[str, Any]:
    """Send a message to a Google Chat space.

    Sends a text message to the specified (or default) Google Chat space.
    Long messages (>4096 chars) are automatically chunked.

    Args:
        text: The message text to send. Supports Google Chat markdown formatting.
        space_id: Target space ID (e.g., "spaces/AAAA..." or just "AAAA...").
                  If empty, uses the default space from GOOGLE_CHAT_SPACE_ID.
        thread_key: Optional thread key for threaded replies. If provided,
                    the message will be posted as a reply in that thread.

    Returns:
        Dict with message details including name, create_time, and thread info.
    """
    client = _get_client()
    msg = client.send_message(
        text=text,
        space_id=space_id or None,
        thread_key=thread_key or None,
    )
    return {
        "status": "sent",
        "message_name": msg.name,
        "create_time": msg.create_time,
        "thread_name": msg.thread_name,
        "text_length": len(text),
        "chunks_sent": max(1, (len(text) - 1) // 4096 + 1),
    }


@mcp.tool()
def get_new_messages(
    space_id: str = "",
    max_messages: int = 25,
) -> dict[str, Any]:
    """Get new (unread) messages from a Google Chat space.

    Returns messages created after the last read watermark for the space.
    If no messages have been read yet, returns the most recent messages.

    Args:
        space_id: Target space ID. If empty, uses the default space.
        max_messages: Maximum number of messages to return (1-100, default 25).

    Returns:
        Dict with list of new messages, count, and the space ID checked.
    """
    client = _get_client()
    state_mgr = _get_state_manager()

    resolved_space = client._resolve_space(space_id or None)
    last_read = state_mgr.get_last_read_time(resolved_space)

    if last_read:
        messages = client.get_messages_after(
            after_time=last_read,
            space_id=resolved_space,
            page_size=min(max_messages, 100),
        )
    else:
        messages = client.list_messages(
            space_id=resolved_space,
            page_size=min(max_messages, 100),
        )

    return {
        "space_id": resolved_space,
        "new_message_count": len(messages),
        "last_read_time": last_read or "never",
        "messages": [
            {
                "name": m.name,
                "sender": m.sender_display_name,
                "text": m.text,
                "create_time": m.create_time,
                "thread": m.thread_name,
            }
            for m in messages
        ],
    }


@mcp.tool()
def mark_messages_read(
    space_id: str = "",
    up_to_message_name: str = "",
    up_to_time: str = "",
) -> dict[str, Any]:
    """Mark messages as read up to a specific point.

    Advances the read watermark for the space. Subsequent calls to
    get_new_messages will only return messages after this point.

    You must provide either up_to_message_name or up_to_time (or both).

    Args:
        space_id: Target space ID. If empty, uses the default space.
        up_to_message_name: Resource name of the last message to mark as read
                           (e.g., "spaces/AAAA/messages/BBBB").
        up_to_time: ISO 8601 timestamp to mark messages read up to.
                    If not provided and message_name is given, uses current time.

    Returns:
        Dict with the updated read state for the space.
    """
    if not up_to_message_name and not up_to_time:
        return {
            "status": "error",
            "error": "Must provide either up_to_message_name or up_to_time",
        }

    client = _get_client()
    state_mgr = _get_state_manager()

    resolved_space = client._resolve_space(space_id or None)
    mark_time = up_to_time or datetime.now(timezone.utc).isoformat()
    mark_name = up_to_message_name or ""

    state_mgr.mark_read(
        space_id=resolved_space,
        message_name=mark_name,
        message_time=mark_time,
    )

    return {
        "status": "marked_read",
        "space_id": resolved_space,
        "up_to_message_name": mark_name,
        "up_to_time": mark_time,
    }


@mcp.tool()
def send_task_completion(
    task_title: str,
    task_id: str = "",
    status: str = "completed",
    summary: str = "",
    details: str = "",
    space_id: str = "",
    thread_key: str = "system3-tasks",
) -> dict[str, Any]:
    """Send a structured task completion notification to Google Chat.

    Formats a task status update as a structured message with clear
    visual markers for quick scanning.

    Args:
        task_title: Title of the completed task.
        task_id: Optional task/bead ID (e.g., "beads-abc123").
        status: Task status - "completed", "failed", "blocked", or "in_progress".
        summary: Brief summary of what was accomplished or what went wrong.
        details: Optional detailed information (will be included in a code block).
        space_id: Target space ID. If empty, uses the default space.
        thread_key: Thread key for grouping task notifications (default: "system3-tasks").

    Returns:
        Dict with send status and message details.
    """
    # Status emoji mapping
    status_emoji = {
        "completed": "+++",
        "failed": "---",
        "blocked": "***",
        "in_progress": ">>>",
    }
    marker = status_emoji.get(status, "???")

    # Build the message
    parts = [f"{marker} *Task {status.upper()}*: {task_title}"]
    if task_id:
        parts.append(f"ID: `{task_id}`")
    if summary:
        parts.append(f"\n{summary}")
    if details:
        parts.append(f"\n```\n{details}\n```")

    text = "\n".join(parts)

    client = _get_client()
    msg = client.send_message(
        text=text,
        space_id=space_id or None,
        thread_key=thread_key,
    )

    return {
        "status": "sent",
        "message_name": msg.name,
        "create_time": msg.create_time,
        "task_status": status,
        "task_title": task_title,
    }


@mcp.tool()
def get_message_stats(
    space_id: str = "",
) -> dict[str, Any]:
    """Get message statistics and read state information.

    Returns statistics about tracked spaces including total messages read,
    last read timestamps, and connection status.

    Args:
        space_id: Optional space ID to get stats for a specific space.
                  If empty, returns stats for all tracked spaces.

    Returns:
        Dict with read state stats and current configuration info.
    """
    state_mgr = _get_state_manager()
    stats = state_mgr.get_stats()

    # Add configuration info
    creds_file = os.environ.get("GOOGLE_CHAT_CREDENTIALS_FILE", "")
    default_space = os.environ.get("GOOGLE_CHAT_SPACE_ID", "")

    result: dict[str, Any] = {
        "configuration": {
            "credentials_file": creds_file or "(not set)",
            "default_space_id": default_space or "(not set)",
            "state_file": str(state_mgr.path),
        },
        "read_state": stats,
    }

    if space_id:
        resolved = space_id if space_id.startswith("spaces/") else f"spaces/{space_id}"
        space_stats = stats.get("spaces", {}).get(resolved, {})
        result["requested_space"] = {
            "space_id": resolved,
            "stats": space_stats or "no data",
        }

    return result


@mcp.tool()
def test_webhook_connection(
    space_id: str = "",
) -> dict[str, Any]:
    """Test the Google Chat API connection and credentials.

    Verifies that the service account credentials are valid, the API
    is reachable, and the target space is accessible.

    Args:
        space_id: Space ID to test against. If empty, uses the default space.

    Returns:
        Dict with connection test results including status, space info, and errors.
    """
    client = _get_client()
    result = client.test_connection(space_id=space_id or None)

    # Add environment info
    result["environment"] = {
        "GOOGLE_CHAT_CREDENTIALS_FILE": os.environ.get(
            "GOOGLE_CHAT_CREDENTIALS_FILE", "(not set)"
        ),
        "GOOGLE_CHAT_SPACE_ID": os.environ.get("GOOGLE_CHAT_SPACE_ID", "(not set)"),
    }

    return result
