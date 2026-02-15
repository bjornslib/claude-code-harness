"""Google Chat webhook client for outbound messaging.

Sends messages to a Google Chat space via an incoming webhook URL.
No service account or OAuth credentials needed — just the webhook URL.

Environment Variables:
    GOOGLE_CHAT_WEBHOOK_URL: Full webhook URL including key and token params.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


class WebhookClient:
    """Send messages to Google Chat via webhook URL."""

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    def send_message(
        self,
        text: str,
        thread_key: str | None = None,
        cards_v2: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a message via the webhook.

        Args:
            text: Message text to send.
            thread_key: Optional thread key for threaded replies.
            cards_v2: Optional Google Chat Cards v2 payload.

        Returns:
            Dict with the API response.
        """
        body: dict[str, Any] = {"text": text}
        if thread_key:
            body["thread"] = {"threadKey": thread_key}
        if cards_v2:
            body["cardsV2"] = cards_v2

        if thread_key:
            url = f"{self._webhook_url}&messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
        else:
            url = self._webhook_url

        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())
        logger.info("Webhook message sent: %s", result.get("name", "unknown"))
        return result
