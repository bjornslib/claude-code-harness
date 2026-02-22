"""Google Chat API client with triple authentication support.

Wraps the Google Chat API (google-api-python-client) with a clean
interface for sending/receiving messages in Google Chat spaces.

Authentication (tried in order):
    1. Service account JSON key file (GOOGLE_CHAT_CREDENTIALS_FILE)
    2. OAuth2 Installed App with stored token (GOOGLE_CHAT_TOKEN_FILE)
    3. OAuth2 Installed App flow (GOOGLE_CHAT_OAUTH_CLIENT_FILE) — opens browser once
    4. Application Default Credentials (ADC) via google.auth.default()

Scopes:
    - https://www.googleapis.com/auth/chat.spaces
    - https://www.googleapis.com/auth/chat.messages
    - https://www.googleapis.com/auth/chat.messages.create
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Google Chat API scopes (user-compatible, works with both SA and ADC)
CHAT_SCOPES = [
    "https://www.googleapis.com/auth/chat.spaces",
    "https://www.googleapis.com/auth/chat.messages",
    "https://www.googleapis.com/auth/chat.messages.create",
]

# Google Chat message character limit
MAX_MESSAGE_LENGTH = 4096


class ChatMessage(BaseModel):
    """Parsed Google Chat message."""

    name: str = Field(description="Resource name: spaces/{space}/messages/{message}")
    sender_name: str = Field(default="unknown")
    sender_display_name: str = Field(default="Unknown")
    sender_type: str = Field(default="", description="HUMAN, BOT, or empty")
    text: str = Field(default="")
    create_time: str = Field(default="")
    thread_name: str = Field(default="")
    space_name: str = Field(default="")


class ChatClient:
    """Client for Google Chat API operations.

    Supports three authentication modes in priority order:
    1. Service account JSON key file (server-to-server, no user interaction)
    2. OAuth2 Installed App with stored token (user-authorized, auto-refreshes)
    3. OAuth2 Installed App flow (opens browser once, then stores token)
    4. Application Default Credentials (ADC) fallback
    """

    def __init__(
        self,
        credentials_file: str = "",
        default_space_id: str = "",
        oauth_client_file: str = "",
        token_file: str = "",
    ) -> None:
        """Initialize the Chat client.

        Args:
            credentials_file: Path to service account JSON key file (optional).
                If empty or file doesn't exist, falls through to OAuth2 paths.
            default_space_id: Default Google Chat space ID (e.g., "spaces/AAAA...").
            oauth_client_file: Path to OAuth2 client secret JSON file (optional).
                Used for the installed app flow when no stored token exists.
            token_file: Path to stored OAuth2 token JSON file (optional).
                Loaded and refreshed automatically on each call.
        """
        self._credentials_file = credentials_file
        self._default_space_id = default_space_id
        self._oauth_client_file = oauth_client_file
        self._token_file = token_file
        self._service: Any = None
        self._credentials: Any = None

    @property
    def default_space(self) -> str:
        """Return the default space resource name."""
        space_id = self._default_space_id
        if space_id and not space_id.startswith("spaces/"):
            return f"spaces/{space_id}"
        return space_id

    def _get_service(self) -> Any:
        """Lazily initialize and return the Google Chat API service.

        Auth priority:
        1. Service account JSON (if credentials_file exists and is a service account)
        2. OAuth2 stored token (if token_file exists and is valid/refreshable)
        3. OAuth2 installed app flow (if oauth_client_file exists, opens browser once)
        4. Application Default Credentials (ADC) fallback
        """
        if self._service is not None:
            return self._service

        from googleapiclient.discovery import build

        creds_path = Path(self._credentials_file) if self._credentials_file else None
        oauth_client_path = Path(self._oauth_client_file) if self._oauth_client_file else None
        token_path = Path(self._token_file) if self._token_file else None

        # --- Auth path 1: Service account ---
        if creds_path and creds_path.exists():
            try:
                from google.oauth2 import service_account

                self._credentials = service_account.Credentials.from_service_account_file(
                    str(creds_path), scopes=CHAT_SCOPES
                )
                logger.info("Using service account credentials from %s", creds_path)
            except Exception:
                logger.info("Service account load failed, trying OAuth2 paths")

        # --- Auth path 2: OAuth2 stored token ---
        if self._credentials is None and token_path and token_path.exists():
            try:
                from google.oauth2.credentials import Credentials

                creds = Credentials.from_authorized_user_file(str(token_path), CHAT_SCOPES)
                if creds and creds.valid:
                    self._credentials = creds
                    logger.info("Using stored OAuth2 token from %s", token_path)
                elif creds and creds.expired and creds.refresh_token:
                    from google.auth.transport.requests import Request

                    creds.refresh(Request())
                    token_path.write_text(creds.to_json())
                    self._credentials = creds
                    logger.info("Refreshed OAuth2 token, saved to %s", token_path)
                else:
                    logger.info("Stored OAuth2 token invalid and cannot refresh, trying flow")
            except Exception as exc:
                logger.info("Failed to load stored OAuth2 token (%s), trying flow", exc)

        # --- Auth path 3: OAuth2 installed app flow (opens browser once) ---
        if self._credentials is None and oauth_client_path and oauth_client_path.exists():
            try:
                from google_auth_oauthlib.flow import InstalledAppFlow

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(oauth_client_path), CHAT_SCOPES
                )
                self._credentials = flow.run_local_server(port=0)
                if token_path:
                    token_path.parent.mkdir(parents=True, exist_ok=True)
                    token_path.write_text(self._credentials.to_json())
                    logger.info("OAuth2 token saved to %s", token_path)
                logger.info("OAuth2 installed app flow completed successfully")
            except Exception as exc:
                logger.info("OAuth2 installed app flow failed (%s), falling back to ADC", exc)

        # --- Auth path 4: ADC fallback ---
        if self._credentials is None:
            import google.auth

            self._credentials, _ = google.auth.default(scopes=CHAT_SCOPES)
            logger.info("Using Application Default Credentials (ADC)")

        self._service = build("chat", "v1", credentials=self._credentials)
        logger.info("Google Chat API service initialized successfully")
        return self._service

    def _resolve_space(self, space_id: str | None) -> str:
        """Resolve space ID to resource name, falling back to default."""
        if space_id:
            if not space_id.startswith("spaces/"):
                return f"spaces/{space_id}"
            return space_id
        if self.default_space:
            return self.default_space
        raise ValueError(
            "No space_id provided and no default space configured. "
            "Set GOOGLE_CHAT_SPACE_ID environment variable."
        )

    def send_message(
        self,
        text: str,
        space_id: str | None = None,
        thread_key: str | None = None,
        cards_v2: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Send a text message to a Google Chat space.

        Args:
            text: Message text (will be chunked if > 4096 chars).
            space_id: Target space. Uses default if not specified.
            thread_key: Optional thread key for threaded replies.
            cards_v2: Optional Google Chat Cards v2 payload. If provided,
                      sends as a card message with fallback text.

        Returns:
            ChatMessage with the sent message details.
        """
        service = self._get_service()
        space = self._resolve_space(space_id)

        # If sending a card, send as a single message (no chunking)
        if cards_v2:
            return self._send_card_message(
                service, space, text, cards_v2, thread_key
            )

        # Chunk long text messages
        chunks = self._chunk_message(text)
        last_message = None

        for chunk in chunks:
            body: dict[str, Any] = {"text": chunk}
            if thread_key:
                body["thread"] = {"threadKey": thread_key}

            request = service.spaces().messages().create(
                parent=space,
                body=body,
                messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
                if thread_key
                else None,
            )
            response = request.execute()
            last_message = self._parse_message(response)
            logger.info("Sent message to %s: %s", space, last_message.name)

        assert last_message is not None
        return last_message

    def _send_card_message(
        self,
        service: Any,
        space: str,
        fallback_text: str,
        cards_v2: list[dict[str, Any]],
        thread_key: str | None = None,
    ) -> ChatMessage:
        """Send a card message with fallback text.

        Args:
            service: Google Chat API service instance.
            space: Resolved space resource name.
            fallback_text: Text shown in notifications and non-card-capable clients.
            cards_v2: Google Chat Cards v2 payload list.
            thread_key: Optional thread key for threaded replies.

        Returns:
            ChatMessage with the sent message details.
        """
        body: dict[str, Any] = {
            "text": fallback_text[:MAX_MESSAGE_LENGTH],
            "cardsV2": cards_v2,
        }
        if thread_key:
            body["thread"] = {"threadKey": thread_key}

        request = service.spaces().messages().create(
            parent=space,
            body=body,
            messageReplyOption="REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
            if thread_key
            else None,
        )
        response = request.execute()
        msg = self._parse_message(response)
        logger.info("Sent card message to %s: %s", space, msg.name)
        return msg

    def list_messages(
        self,
        space_id: str | None = None,
        page_size: int = 25,
        filter_str: str = "",
    ) -> list[ChatMessage]:
        """List recent messages in a Google Chat space.

        Args:
            space_id: Target space. Uses default if not specified.
            page_size: Maximum number of messages to return (max 1000).
            filter_str: Optional filter string (e.g., 'createTime > "2024-01-01T00:00:00Z"').

        Returns:
            List of ChatMessage objects, ordered by create_time ascending.
        """
        service = self._get_service()
        space = self._resolve_space(space_id)

        kwargs: dict[str, Any] = {
            "parent": space,
            "pageSize": min(page_size, 1000),
            "orderBy": "createTime asc",
        }
        if filter_str:
            kwargs["filter"] = filter_str

        request = service.spaces().messages().list(**kwargs)
        response = request.execute()

        messages = []
        for msg in response.get("messages", []):
            messages.append(self._parse_message(msg))

        logger.info("Listed %d messages from %s", len(messages), space)
        return messages

    def get_messages_after(
        self,
        after_time: str,
        space_id: str | None = None,
        page_size: int = 50,
    ) -> list[ChatMessage]:
        """Get messages created after a specific timestamp.

        Args:
            after_time: ISO 8601 timestamp. Messages after this time are returned.
            space_id: Target space. Uses default if not specified.
            page_size: Maximum number of messages to return.

        Returns:
            List of ChatMessage objects created after the given time.
        """
        filter_str = f'createTime > "{after_time}"'
        return self.list_messages(
            space_id=space_id,
            page_size=page_size,
            filter_str=filter_str,
        )

    def test_connection(self, space_id: str | None = None) -> dict[str, Any]:
        """Test the connection to Google Chat API.

        Returns:
            Dict with connection status, space details, and any errors.
        """
        creds_path = Path(self._credentials_file) if self._credentials_file else None
        oauth_client_path = Path(self._oauth_client_file) if self._oauth_client_file else None
        token_path = Path(self._token_file) if self._token_file else None

        # Determine the auth mode description before building service
        if creds_path and creds_path.exists():
            auth_mode = "service_account"
        elif token_path and token_path.exists():
            auth_mode = "oauth2_stored_token"
        elif oauth_client_path and oauth_client_path.exists():
            auth_mode = "oauth2_installed_app_flow"
        else:
            auth_mode = "adc"

        result: dict[str, Any] = {
            "status": "unknown",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "credentials_file": str(self._credentials_file) if self._credentials_file else "(not set)",
            "credentials_exists": creds_path.exists() if creds_path else False,
            "oauth_client_file": str(self._oauth_client_file) if self._oauth_client_file else "(not set)",
            "oauth_client_exists": oauth_client_path.exists() if oauth_client_path else False,
            "token_file": str(self._token_file) if self._token_file else "(not set)",
            "token_exists": token_path.exists() if token_path else False,
            "auth_mode": auth_mode,
        }

        try:
            service = self._get_service()
            space = self._resolve_space(space_id)

            # Try to get space details
            space_info = service.spaces().get(name=space).execute()
            result["status"] = "connected"
            result["space_name"] = space_info.get("name", "")
            result["space_display_name"] = space_info.get("displayName", "")
            result["space_type"] = space_info.get("spaceType", "")
        except FileNotFoundError as exc:
            result["status"] = "error"
            result["error"] = f"Credentials file not found: {exc}"
        except ValueError as exc:
            result["status"] = "error"
            result["error"] = f"Configuration error: {exc}"
        except Exception as exc:
            result["status"] = "error"
            result["error"] = f"Connection failed: {type(exc).__name__}: {exc}"

        return result

    @staticmethod
    def _chunk_message(text: str) -> list[str]:
        """Split a message into chunks respecting the 4096 char limit.

        Tries to split on newlines first, then on spaces, then hard-cuts.
        """
        if len(text) <= MAX_MESSAGE_LENGTH:
            return [text]

        chunks: list[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= MAX_MESSAGE_LENGTH:
                chunks.append(remaining)
                break

            # Find a good split point
            split_at = MAX_MESSAGE_LENGTH

            # Try to split at a newline
            newline_pos = remaining[:split_at].rfind("\n")
            if newline_pos > MAX_MESSAGE_LENGTH // 2:
                split_at = newline_pos + 1
            else:
                # Try to split at a space
                space_pos = remaining[:split_at].rfind(" ")
                if space_pos > MAX_MESSAGE_LENGTH // 2:
                    split_at = space_pos + 1

            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:]

        return chunks

    @staticmethod
    def _parse_message(data: dict[str, Any]) -> ChatMessage:
        """Parse a Google Chat API message response into a ChatMessage."""
        sender = data.get("sender", {})
        thread = data.get("thread", {})

        return ChatMessage(
            name=data.get("name", ""),
            sender_name=sender.get("name", "unknown"),
            sender_display_name=sender.get("displayName", "Unknown"),
            sender_type=sender.get("type", ""),
            text=data.get("text", ""),
            create_time=data.get("createTime", ""),
            thread_name=thread.get("name", ""),
            space_name=data.get("space", {}).get("name", ""),
        )
