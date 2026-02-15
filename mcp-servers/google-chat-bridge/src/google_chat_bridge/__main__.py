"""Entry point for running google-chat-bridge as a module.

Usage:
    python -m google_chat_bridge
    uv run google-chat-bridge
"""

from google_chat_bridge.server import mcp


def main() -> None:
    """Run the Google Chat Bridge MCP server via stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
