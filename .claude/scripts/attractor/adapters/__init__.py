"""Channel Adapter registry for the Pipeline Runner.

Provides a factory function to create the appropriate adapter based on the
deployment context:

    - "stdout"       → StdoutAdapter (POC/local runs, default)
    - "message_bus"  → MessageBusAdapter (cross-session, tmux-based)
    - "native_teams" → NativeTeamsAdapter (Agent Teams member)

Usage:
    from adapters import create_adapter

    adapter = create_adapter("stdout")
    adapter = create_adapter("message_bus", target="system3", session_id="runner-123")
    adapter = create_adapter("native_teams", team_name="s3-live-workers")
"""

from __future__ import annotations

from typing import Any

from .base import ChannelAdapter, ChannelError, ChannelMessage
from .message_bus import MessageBusAdapter
from .native_teams import NativeTeamsAdapter
from .stdout import StdoutAdapter

__all__ = [
    "ChannelAdapter",
    "ChannelError",
    "ChannelMessage",
    "MessageBusAdapter",
    "NativeTeamsAdapter",
    "StdoutAdapter",
    "create_adapter",
]

_REGISTRY: dict[str, type[ChannelAdapter]] = {
    "stdout": StdoutAdapter,
    "message_bus": MessageBusAdapter,
    "native_teams": NativeTeamsAdapter,
}


def create_adapter(channel: str = "stdout", **kwargs: Any) -> ChannelAdapter:
    """Create a ChannelAdapter by name.

    Args:
        channel: Adapter type. One of: "stdout", "message_bus", "native_teams".
        **kwargs: Passed directly to the adapter's __init__.

    Returns:
        Configured ChannelAdapter instance (not yet registered).

    Raises:
        ValueError: If the channel name is unknown.

    Examples:
        >>> adapter = create_adapter("stdout")
        >>> adapter = create_adapter("message_bus", target="system3")
        >>> adapter = create_adapter("native_teams", team_name="s3-live-workers")
    """
    cls = _REGISTRY.get(channel)
    if cls is None:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(
            f"Unknown channel adapter: {channel!r}. Available: {available}"
        )
    return cls(**kwargs)
