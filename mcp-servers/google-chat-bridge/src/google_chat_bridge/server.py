"""Google Chat Bridge MCP Server.

FastMCP server providing Google Chat integration tools for System 3.
Runs as stdio transport for use as an MCP server in Claude Code.

Environment Variables:
    GOOGLE_CHAT_CREDENTIALS_FILE: Path to service account JSON key file (required).
    GOOGLE_CHAT_SPACE_ID: Default Google Chat space ID (optional, can be passed per-call).

Tools (Core):
    send_chat_message      - Send a message to a Google Chat space
    get_new_messages       - Get unread messages since last check
    mark_messages_read     - Mark messages as read (update read watermark)
    send_task_completion   - Send a structured task completion notification
    get_message_stats      - Get message statistics and read state
    test_webhook_connection - Test the Google Chat API connection

Tools (Outbound Formatting - F2.3):
    send_progress_update   - Send orchestrator progress update
    send_card_message      - Send a rich card-formatted message
    send_daily_briefing    - Send morning/EOD briefing
    send_blocked_alert     - Send blocked work alert with options
    send_heartbeat_finding - Send heartbeat finding notification

Tools (Inbound Routing - F2.2):
    poll_inbound_messages  - Fetch, normalize, rate-limit, and queue new messages
    get_queued_messages    - Get unconsumed messages from the local queue
    consume_messages       - Mark queued messages as consumed
    get_thread_messages    - Get messages grouped by thread
    get_queue_stats        - Get message queue and rate limiter statistics
    purge_consumed         - Remove old consumed messages from queue
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastmcp import FastMCP

from google_chat_bridge.chat_client import ChatClient
from google_chat_bridge.formatter import (
    CardBuilder,
    build_briefing_card,
    build_task_card,
    chunk_with_continuation,
    format_beads_change,
    format_blocked_alert,
    format_daily_briefing,
    format_heartbeat_finding,
    format_option_question,
    format_progress_update,
    markdown_to_gchat,
)
from google_chat_bridge.message_queue import MessageQueueManager
from google_chat_bridge.router import MessageRouter, RateLimiter
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
_queue_manager: MessageQueueManager | None = None
_router: MessageRouter | None = None


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


def _get_queue_manager() -> MessageQueueManager:
    """Get or create the message queue manager."""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = MessageQueueManager()
    return _queue_manager


def _get_router() -> MessageRouter:
    """Get or create the message router."""
    global _router
    if _router is None:
        _router = MessageRouter(
            client=_get_client(),
            queue_manager=_get_queue_manager(),
        )
    return _router


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


# ---------------------------------------------------------------------------
# F2.3: Outbound Message Formatting Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def send_progress_update(
    orchestrator_name: str,
    status: str,
    tasks_completed: int = 0,
    tasks_total: int = 0,
    current_task: str = "",
    elapsed_time: str = "",
    details: str = "",
    space_id: str = "",
    thread_key: str = "system3-progress",
) -> dict[str, Any]:
    """Send an orchestrator progress update to Google Chat.

    Sends a formatted progress message with a visual progress bar,
    current task info, and optional details. Messages are grouped
    in a thread for clean organization.

    Args:
        orchestrator_name: Name of the orchestrator session (e.g., "epic2-gchat").
        status: Current status - "running", "idle", "completed", "error", or "blocked".
        tasks_completed: Number of tasks completed so far.
        tasks_total: Total number of tasks in the session.
        current_task: Description of the task currently being worked on.
        elapsed_time: Human-readable elapsed time (e.g., "1h 23m").
        details: Optional additional details or context.
        space_id: Target space ID. If empty, uses the default space.
        thread_key: Thread key for grouping progress updates (default: "system3-progress").

    Returns:
        Dict with send status and message details.
    """
    text = format_progress_update(
        orchestrator_name=orchestrator_name,
        status=status,
        tasks_completed=tasks_completed,
        tasks_total=tasks_total,
        current_task=current_task,
        elapsed_time=elapsed_time,
        details=details,
    )

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
        "orchestrator": orchestrator_name,
        "progress": f"{tasks_completed}/{tasks_total}" if tasks_total else "N/A",
    }


@mcp.tool()
def send_card_message(
    title: str,
    subtitle: str = "",
    sections: str = "[]",
    fallback_text: str = "",
    space_id: str = "",
    thread_key: str = "",
) -> dict[str, Any]:
    """Send a rich card-formatted message to Google Chat.

    Creates a Google Chat Card v2 with a header, optional sections
    containing text and key-value widgets. Use this for structured
    information that benefits from visual organization.

    Args:
        title: Card title (displayed prominently in the header).
        subtitle: Optional card subtitle (displayed below the title).
        sections: JSON string of sections array. Each section is an object with:
                  - "header": section title (optional)
                  - "text": list of text paragraphs (optional)
                  - "kv": list of {"label": "...", "value": "..."} pairs (optional)
                  Example: '[{"header": "Summary", "text": ["All tests passed"]}]'
        fallback_text: Plain text shown in notifications. If empty, uses the title.
        space_id: Target space ID. If empty, uses the default space.
        thread_key: Optional thread key for threaded replies.

    Returns:
        Dict with send status and message details.
    """
    import json

    builder = CardBuilder(title)
    if subtitle:
        builder.subtitle(subtitle)

    # Parse sections JSON
    try:
        section_list = json.loads(sections) if sections else []
    except json.JSONDecodeError:
        return {
            "status": "error",
            "error": f"Invalid sections JSON: {sections[:100]}",
        }

    for sec in section_list:
        widgets: list[dict[str, Any]] = []

        # Add text paragraphs
        for text_item in sec.get("text", []):
            widgets.append(CardBuilder.text_widget(text_item))

        # Add key-value pairs
        for kv in sec.get("kv", []):
            widgets.append(
                CardBuilder.kv_widget(
                    label=kv.get("label", ""),
                    value=kv.get("value", ""),
                    icon=kv.get("icon", ""),
                )
            )

        builder.section(header=sec.get("header", ""), widgets=widgets)

    card_payload = builder.build()
    fallback = fallback_text or title

    client = _get_client()
    msg = client.send_message(
        text=fallback,
        space_id=space_id or None,
        thread_key=thread_key or None,
        cards_v2=card_payload.get("cardsV2", []),
    )

    return {
        "status": "sent",
        "message_name": msg.name,
        "create_time": msg.create_time,
        "card_title": title,
        "sections_count": len(section_list),
    }


@mcp.tool()
def send_daily_briefing(
    briefing_type: str = "morning",
    date: str = "",
    beads_summary: str = "",
    orchestrator_summary: str = "",
    git_summary: str = "",
    priorities: str = "[]",
    accomplishments: str = "[]",
    blockers: str = "[]",
    use_card: bool = True,
    space_id: str = "",
    thread_key: str = "system3-briefings",
) -> dict[str, Any]:
    """Send a daily briefing (morning or end-of-day) to Google Chat.

    Formats a comprehensive daily summary with beads status, orchestrator
    activity, git changes, priorities, accomplishments, and blockers.
    Can be sent as a rich card or plain text.

    Args:
        briefing_type: "morning" for morning briefing or "eod" for end-of-day summary.
        date: Date string (defaults to today in YYYY-MM-DD format).
        beads_summary: Summary of beads/issue status (open, in-progress, blocked counts).
        orchestrator_summary: Summary of orchestrator sessions and their status.
        git_summary: Summary of git activity (commits, PRs, branches).
        priorities: JSON string of priority items list (for morning).
                    Example: '["Finish auth feature", "Review PR #42"]'
        accomplishments: JSON string of accomplishments list (for EOD).
                        Example: '["Deployed auth service", "Fixed 3 bugs"]'
        blockers: JSON string of blockers list.
                  Example: '["Waiting for API key", "Chrome extension issue"]'
        use_card: Whether to send as a rich card (true) or plain text (false).
        space_id: Target space ID. If empty, uses the default space.
        thread_key: Thread key for grouping briefings (default: "system3-briefings").

    Returns:
        Dict with send status and briefing details.
    """
    import json

    try:
        priorities_list = json.loads(priorities) if priorities else []
        accomplishments_list = json.loads(accomplishments) if accomplishments else []
        blockers_list = json.loads(blockers) if blockers else []
    except json.JSONDecodeError as exc:
        return {"status": "error", "error": f"Invalid JSON in list field: {exc}"}

    if use_card:
        # Build card sections
        sections_data: dict[str, list[str]] = {}
        if beads_summary:
            sections_data["Beads"] = [beads_summary]
        if orchestrator_summary:
            sections_data["Orchestrators"] = [orchestrator_summary]
        if git_summary:
            sections_data["Git Activity"] = [git_summary]
        if priorities_list:
            sections_data["Priorities"] = [
                f"{i}. {p}" for i, p in enumerate(priorities_list, 1)
            ]
        if accomplishments_list:
            sections_data["Accomplishments"] = accomplishments_list
        if blockers_list:
            sections_data["Blockers"] = blockers_list

        card_payload = build_briefing_card(
            briefing_type=briefing_type,
            date=date,
            sections_data=sections_data,
        )

        fallback_text = format_daily_briefing(
            briefing_type=briefing_type,
            date=date,
            beads_summary=beads_summary,
            orchestrator_summary=orchestrator_summary,
            git_summary=git_summary,
            priorities=priorities_list,
            accomplishments=accomplishments_list,
            blockers=blockers_list,
        )

        client = _get_client()
        msg = client.send_message(
            text=fallback_text[:4096],
            space_id=space_id or None,
            thread_key=thread_key,
            cards_v2=card_payload.get("cardsV2", []),
        )
    else:
        text = format_daily_briefing(
            briefing_type=briefing_type,
            date=date,
            beads_summary=beads_summary,
            orchestrator_summary=orchestrator_summary,
            git_summary=git_summary,
            priorities=priorities_list,
            accomplishments=accomplishments_list,
            blockers=blockers_list,
        )

        # Use continuation-marker chunking for plain text
        chunks = chunk_with_continuation(text)

        client = _get_client()
        msg = None
        for chunk in chunks:
            msg = client.send_message(
                text=chunk,
                space_id=space_id or None,
                thread_key=thread_key,
            )

        assert msg is not None

    return {
        "status": "sent",
        "message_name": msg.name,
        "create_time": msg.create_time,
        "briefing_type": briefing_type,
        "format": "card" if use_card else "text",
    }


@mcp.tool()
def send_blocked_alert(
    task_title: str,
    task_id: str = "",
    blocker_description: str = "",
    options: str = "[]",
    urgency: str = "medium",
    space_id: str = "",
    thread_key: str = "system3-alerts",
) -> dict[str, Any]:
    """Send a blocked work alert requesting user input via Google Chat.

    Formats and sends an alert when work is blocked and user input is needed.
    Supports urgency levels and presents options for the user to choose from.

    Args:
        task_title: Title of the blocked task.
        task_id: Optional task/bead ID (e.g., "beads-abc123").
        blocker_description: Description of what is blocking progress.
        options: JSON string of option descriptions list.
                 Example: '["Retry with Sonnet model", "Skip this task", "Escalate to manual review"]'
        urgency: Urgency level - "low", "medium", "high", or "critical".
        space_id: Target space ID. If empty, uses the default space.
        thread_key: Thread key for grouping alerts (default: "system3-alerts").

    Returns:
        Dict with send status and alert details.
    """
    import json

    try:
        options_list = json.loads(options) if options else []
    except json.JSONDecodeError:
        options_list = []

    text = format_blocked_alert(
        task_title=task_title,
        task_id=task_id,
        blocker_description=blocker_description,
        options=options_list,
        urgency=urgency,
    )

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
        "urgency": urgency,
        "task_title": task_title,
        "options_count": len(options_list),
    }


@mcp.tool()
def send_heartbeat_finding(
    finding_type: str,
    summary: str,
    details: str = "",
    action_needed: bool = True,
    space_id: str = "",
    thread_key: str = "system3-heartbeat",
) -> dict[str, Any]:
    """Send a heartbeat finding notification to Google Chat.

    Used by the System 3 Communicator to relay actionable findings
    from heartbeat checks to the user via Google Chat.

    Args:
        finding_type: Type of finding. One of:
                      "beads_ready" - Ready beads needing attention
                      "git_changes" - Uncommitted changes or PR reviews
                      "orchestrator_stuck" - Orchestrator blocked or errored
                      "orchestrator_complete" - Orchestrator finished work
                      "pr_review" - Pull request needing review
                      "error" - Error condition detected
        summary: Brief summary of the finding (1-2 sentences).
        details: Optional detailed information.
        action_needed: Whether user action is required (default: true).
        space_id: Target space ID. If empty, uses the default space.
        thread_key: Thread key for grouping heartbeat messages (default: "system3-heartbeat").

    Returns:
        Dict with send status and finding details.
    """
    text = format_heartbeat_finding(
        finding_type=finding_type,
        summary=summary,
        details=details,
        action_needed=action_needed,
    )

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
        "finding_type": finding_type,
        "action_needed": action_needed,
    }


# ---------------------------------------------------------------------------
# F2.2: Inbound Message Routing Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def poll_inbound_messages(
    space_id: str = "",
    max_messages: int = 50,
) -> dict[str, Any]:
    """Fetch new messages from Google Chat, normalize, and queue them locally.

    This is the primary inbound message processing tool. It:
    1. Fetches recent messages from the Google Chat API
    2. Normalizes them into a standard format (sender, text, timestamp, thread_id)
    3. Applies per-sender rate limiting
    4. Queues new messages (with deduplication)

    Call this periodically (e.g., during heartbeat checks) to pull in
    user messages for processing.

    Args:
        space_id: Google Chat space to poll. If empty, uses the default space.
        max_messages: Maximum messages to fetch per poll (1-100, default 50).

    Returns:
        Dict with polling results: fetched, queued, rate_limited, duplicates.
    """
    router = _get_router()
    result = router.poll_and_route(
        space_id=space_id or None,
        max_messages=min(max_messages, 100),
    )
    return result


@mcp.tool()
def get_queued_messages(
    limit: int = 25,
    thread_grouped: bool = False,
) -> dict[str, Any]:
    """Get unconsumed messages from the local queue.

    Returns messages that have been fetched and queued but not yet
    consumed (processed) by System 3. Messages are returned in FIFO order.

    Args:
        limit: Maximum number of messages to return (1-100, default 25).
        thread_grouped: If true, return messages grouped by thread instead of flat list.

    Returns:
        Dict with messages (flat list or thread groups) and queue stats.
    """
    queue_mgr = _get_queue_manager()

    if thread_grouped:
        groups = queue_mgr.get_thread_groups(unconsumed_only=True)
        return {
            "thread_count": len(groups),
            "total_messages": sum(g.message_count for g in groups),
            "threads": [
                {
                    "thread_id": g.thread_id,
                    "message_count": g.message_count,
                    "latest_timestamp": g.latest_timestamp,
                    "messages": [
                        {
                            "message_id": m.message_id,
                            "sender": m.sender,
                            "text": m.text,
                            "timestamp": m.timestamp,
                        }
                        for m in g.messages
                    ],
                }
                for g in groups
            ],
        }
    else:
        messages = queue_mgr.get_unconsumed(limit=min(limit, 100))
        return {
            "message_count": len(messages),
            "messages": [
                {
                    "message_id": m.message_id,
                    "sender": m.sender,
                    "text": m.text,
                    "timestamp": m.timestamp,
                    "thread_id": m.thread_id,
                    "space_id": m.space_id,
                    "queued_at": m.queued_at,
                }
                for m in messages
            ],
        }


@mcp.tool()
def consume_messages(
    message_ids: str = "[]",
    consume_all: bool = False,
) -> dict[str, Any]:
    """Mark queued messages as consumed (processed).

    After System 3 or the Communicator has processed messages from the queue,
    call this to mark them as consumed so they won't appear in future
    get_queued_messages calls.

    Args:
        message_ids: JSON string of message ID list to consume.
                     Example: '["spaces/X/messages/1", "spaces/X/messages/2"]'
        consume_all: If true, consume ALL unconsumed messages (ignores message_ids).

    Returns:
        Dict with number of messages consumed.
    """
    import json

    queue_mgr = _get_queue_manager()

    if consume_all:
        unconsumed = queue_mgr.get_unconsumed(limit=1000)
        ids = [m.message_id for m in unconsumed]
    else:
        try:
            ids = json.loads(message_ids) if message_ids else []
        except json.JSONDecodeError:
            return {"status": "error", "error": f"Invalid message_ids JSON: {message_ids[:100]}"}

    if not ids:
        return {"status": "ok", "consumed": 0, "note": "No messages to consume"}

    consumed = queue_mgr.consume(ids)
    return {
        "status": "ok",
        "consumed": consumed,
        "requested": len(ids),
    }


@mcp.tool()
def get_thread_messages(
    thread_id: str,
    include_consumed: bool = False,
) -> dict[str, Any]:
    """Get all messages in a specific thread.

    Returns messages from the local queue that belong to the specified
    thread, enabling conversation-aware processing.

    Args:
        thread_id: Thread resource name (e.g., "spaces/X/threads/Y").
        include_consumed: If true, include already-consumed messages.

    Returns:
        Dict with thread messages ordered by timestamp.
    """
    queue_mgr = _get_queue_manager()
    messages = queue_mgr.get_thread_messages(
        thread_id=thread_id,
        include_consumed=include_consumed,
    )

    return {
        "thread_id": thread_id,
        "message_count": len(messages),
        "messages": [
            {
                "message_id": m.message_id,
                "sender": m.sender,
                "text": m.text,
                "timestamp": m.timestamp,
                "consumed": m.consumed,
            }
            for m in messages
        ],
    }


@mcp.tool()
def get_queue_stats() -> dict[str, Any]:
    """Get message queue and rate limiter statistics.

    Returns comprehensive statistics about the inbound message queue
    including queue size, consumption rates, active threads, and
    rate limiter state.

    Returns:
        Dict with queue stats and rate limiter stats.
    """
    queue_mgr = _get_queue_manager()
    router = _get_router()

    return {
        "queue": queue_mgr.get_stats(),
        "rate_limiter": router.rate_limiter.get_stats(),
    }


@mcp.tool()
def purge_consumed(
    keep_recent: int = 50,
) -> dict[str, Any]:
    """Remove old consumed messages from the queue to free space.

    Cleans up the message queue by removing consumed messages that are
    no longer needed. Keeps a configurable number of recent consumed
    messages for reference.

    Args:
        keep_recent: Number of most recent consumed messages to keep (default: 50).

    Returns:
        Dict with number of messages purged and remaining queue size.
    """
    queue_mgr = _get_queue_manager()
    purged = queue_mgr.purge_consumed(keep_recent=keep_recent)

    stats = queue_mgr.get_stats()
    return {
        "status": "ok",
        "purged": purged,
        "remaining_queue_size": stats["queue_size"],
        "unconsumed": stats["unconsumed"],
    }
