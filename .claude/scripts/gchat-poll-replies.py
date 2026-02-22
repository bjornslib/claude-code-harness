#!/usr/bin/env python3
"""Poll Google Chat for replies to forwarded AskUserQuestion markers.

Called by s3-heartbeat to check for user responses to questions
that were forwarded to GChat via gchat-ask-user-forward.py.

Usage:
    python3 .claude/scripts/gchat-poll-replies.py [--marker-dir DIR]

Output (JSON to stdout):
    {"replies": [{"question_id": "...", "session_id": "...", "reply_text": "...", "replied_at": "..."}]}

Exit codes:
    0 = success (check "replies" array)
    1 = error (check stderr)
    2 = no credentials configured
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# Default marker directory
DEFAULT_MARKER_DIR = PROJECT_ROOT / ".claude" / "state" / "gchat-forwarded-ask"

# Credentials
CREDENTIALS_DIR = PROJECT_ROOT / ".claude" / "credentials"
CLIENT_SECRET = CREDENTIALS_DIR / "google-chat-oauth-client.json"
TOKEN_FILE = CREDENTIALS_DIR / "google-chat-token.json"


def get_chat_service():
    """Initialize Google Chat API service with OAuth2 credentials."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    SCOPES = [
        "https://www.googleapis.com/auth/chat.spaces",
        "https://www.googleapis.com/auth/chat.messages",
        "https://www.googleapis.com/auth/chat.messages.create",
    ]

    if not TOKEN_FILE.exists():
        print("No OAuth2 token found. Run gchat-oauth-setup.py first.", file=sys.stderr)
        sys.exit(2)

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    if not creds.valid:
        print("OAuth2 token invalid and cannot be refreshed. Re-run gchat-oauth-setup.py.", file=sys.stderr)
        sys.exit(2)

    return build("chat", "v1", credentials=creds)


def find_pending_markers(marker_dir: Path) -> list[dict]:
    """Find all marker files with status 'pending'."""
    markers = []
    if not marker_dir.exists():
        return markers

    for f in marker_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("status") == "pending":
                data["_marker_path"] = str(f)
                markers.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return markers


def poll_thread_for_replies(service, marker: dict) -> dict | None:
    """Check a GChat thread for replies after the question was forwarded.

    Returns reply dict if found, None otherwise.
    """
    thread_name = marker.get("thread_name", "")
    if not thread_name:
        return None

    # Extract space from thread_name (format: spaces/{id}/threads/{id})
    parts = thread_name.split("/")
    if len(parts) < 2:
        return None
    space_name = f"{parts[0]}/{parts[1]}"

    forwarded_at = marker.get("forwarded_at", "")
    if not forwarded_at:
        return None

    try:
        # List messages in the space, filtered by time
        # Note: Chat API doesn't support thread filtering directly,
        # so we filter by time and then match thread_name
        result = service.spaces().messages().list(
            parent=space_name,
            pageSize=50,
            orderBy="createTime asc",
            filter=f'createTime > "{forwarded_at}"',
        ).execute()

        messages = result.get("messages", [])

        for msg in messages:
            msg_thread = msg.get("thread", {}).get("name", "")
            sender = msg.get("sender", {})
            sender_type = sender.get("type", "")

            # Match: same thread, from a HUMAN (not bot), after our question
            if msg_thread == thread_name and sender_type == "HUMAN":
                return {
                    "question_id": marker.get("question_id", ""),
                    "session_id": marker.get("session_id", ""),
                    "reply_text": msg.get("text", ""),
                    "replied_at": msg.get("createTime", ""),
                    "sender_name": sender.get("displayName", "unknown"),
                    "thread_name": thread_name,
                }

    except Exception as e:
        print(f"Error polling thread {thread_name}: {e}", file=sys.stderr)

    return None


def update_marker(marker: dict, reply: dict):
    """Update marker file to 'answered' status."""
    marker_path = Path(marker["_marker_path"])
    try:
        data = json.loads(marker_path.read_text())
        data["status"] = "answered"
        data["answer"] = reply["reply_text"]
        data["answered_at"] = reply["replied_at"]
        data["answered_by"] = reply["sender_name"]
        marker_path.write_text(json.dumps(data, indent=2))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error updating marker {marker_path}: {e}", file=sys.stderr)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Poll GChat for replies to forwarded questions")
    parser.add_argument("--marker-dir", type=Path, default=DEFAULT_MARKER_DIR,
                        help="Directory containing marker files")
    args = parser.parse_args()

    # Find pending markers
    markers = find_pending_markers(args.marker_dir)
    if not markers:
        print(json.dumps({"replies": [], "pending_count": 0}))
        sys.exit(0)

    # Initialize service
    try:
        service = get_chat_service()
    except SystemExit:
        raise
    except Exception as e:
        print(f"Failed to initialize Chat service: {e}", file=sys.stderr)
        sys.exit(1)

    # Poll each pending marker
    replies = []
    for marker in markers:
        reply = poll_thread_for_replies(service, marker)
        if reply:
            replies.append(reply)
            update_marker(marker, reply)

    output = {
        "replies": replies,
        "pending_count": len(markers) - len(replies),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
