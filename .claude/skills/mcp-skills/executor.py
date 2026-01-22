#!/usr/bin/env python3
"""
MCP Skills Central Executor
===========================
Central executor for all MCP-derived skills in the mcp-skills directory.
Supports stdio, HTTP, and SSE transport types.

Usage:
    # List tools for a skill
    python executor.py --skill shadcn --list

    # Describe a specific tool
    python executor.py --skill github --describe create_issue

    # Call a tool
    python executor.py --skill shadcn --call '{"tool": "search_items_in_registries", "arguments": {...}}'

    # Use explicit config path
    python executor.py --config ./custom/mcp-config.json --list
"""

import json
import sys
import asyncio
import argparse
from pathlib import Path

# Check if mcp package is available
HAS_MCP = False
HAS_HTTP = False
HAS_SSE = False

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    HAS_MCP = True
except ImportError:
    print("Warning: mcp package not installed. Install with: pip install mcp", file=sys.stderr)

try:
    from mcp.client.streamable_http import streamablehttp_client
    HAS_HTTP = True
except ImportError:
    pass  # HTTP support optional

try:
    from mcp.client.sse import sse_client
    HAS_SSE = True
except ImportError:
    pass  # SSE support optional


class MCPExecutorStdio:
    """Execute MCP tool calls via stdio transport."""

    def __init__(self, server_config):
        if not HAS_MCP:
            raise ImportError("mcp package is required. Install with: pip install mcp")

        self.server_config = server_config
        self._server_params = StdioServerParameters(
            command=server_config["command"],
            args=server_config.get("args", []),
            env=server_config.get("env")
        )

    async def _run_with_session(self, operation):
        async with stdio_client(self._server_params) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await operation(session)

    async def list_tools(self):
        async def _list(session):
            response = await session.list_tools()
            return [{"name": tool.name, "description": tool.description} for tool in response.tools]
        return await self._run_with_session(_list)

    async def describe_tool(self, tool_name: str):
        async def _describe(session):
            response = await session.list_tools()
            for tool in response.tools:
                if tool.name == tool_name:
                    return {"name": tool.name, "description": tool.description, "inputSchema": tool.inputSchema}
            return None
        return await self._run_with_session(_describe)

    async def call_tool(self, tool_name: str, arguments: dict):
        async def _call(session):
            response = await session.call_tool(tool_name, arguments)
            return response.content
        return await self._run_with_session(_call)

    async def close(self):
        pass


class MCPExecutorHTTP:
    """Execute MCP tool calls via HTTP transport."""

    def __init__(self, server_config):
        if not HAS_HTTP:
            raise ImportError("HTTP transport requires mcp package with streamable_http support")

        self.server_config = server_config
        self._url = server_config["url"]

    async def _run_with_session(self, operation):
        async with streamablehttp_client(self._url) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await operation(session)

    async def list_tools(self):
        async def _list(session):
            response = await session.list_tools()
            return [{"name": tool.name, "description": tool.description} for tool in response.tools]
        return await self._run_with_session(_list)

    async def describe_tool(self, tool_name: str):
        async def _describe(session):
            response = await session.list_tools()
            for tool in response.tools:
                if tool.name == tool_name:
                    return {"name": tool.name, "description": tool.description, "inputSchema": tool.inputSchema}
            return None
        return await self._run_with_session(_describe)

    async def call_tool(self, tool_name: str, arguments: dict):
        async def _call(session):
            response = await session.call_tool(tool_name, arguments)
            return response.content
        return await self._run_with_session(_call)

    async def close(self):
        pass


class MCPExecutorSSE:
    """Execute MCP tool calls via SSE (Server-Sent Events) transport."""

    def __init__(self, server_config):
        if not HAS_SSE:
            raise ImportError("SSE transport requires mcp package with sse support")

        self.server_config = server_config
        self._url = server_config["url"]

    async def _run_with_session(self, operation):
        async with sse_client(self._url) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await operation(session)

    async def list_tools(self):
        async def _list(session):
            response = await session.list_tools()
            return [{"name": tool.name, "description": tool.description} for tool in response.tools]
        return await self._run_with_session(_list)

    async def describe_tool(self, tool_name: str):
        async def _describe(session):
            response = await session.list_tools()
            for tool in response.tools:
                if tool.name == tool_name:
                    return {"name": tool.name, "description": tool.description, "inputSchema": tool.inputSchema}
            return None
        return await self._run_with_session(_describe)

    async def call_tool(self, tool_name: str, arguments: dict):
        async def _call(session):
            response = await session.call_tool(tool_name, arguments)
            return response.content
        return await self._run_with_session(_call)

    async def close(self):
        pass


def create_executor(config):
    """Factory to create appropriate executor based on config type."""
    server_type = config.get("type", "stdio")
    if server_type == "http":
        return MCPExecutorHTTP(config)
    elif server_type == "sse":
        return MCPExecutorSSE(config)
    else:
        return MCPExecutorStdio(config)


def find_config(skill_name: str = None, config_path: str = None) -> Path:
    """
    Find the MCP config file.

    Priority:
    1. Explicit --config path
    2. --skill name -> <script_dir>/<skill>/mcp-config.json
    """
    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        return path

    if skill_name:
        script_dir = Path(__file__).parent
        path = script_dir / skill_name / "mcp-config.json"
        if not path.exists():
            # List available skills
            available = [d.name for d in script_dir.iterdir()
                        if d.is_dir() and (d / "mcp-config.json").exists()]
            raise FileNotFoundError(
                f"Skill '{skill_name}' not found. "
                f"Available skills: {', '.join(sorted(available))}"
            )
        return path

    raise ValueError("Must specify either --skill or --config")


def list_available_skills() -> list:
    """List all available skills in the mcp-skills directory."""
    script_dir = Path(__file__).parent
    skills = []
    for d in sorted(script_dir.iterdir()):
        if d.is_dir() and (d / "mcp-config.json").exists():
            skills.append(d.name)
    return skills


async def main():
    parser = argparse.ArgumentParser(
        description="Central executor for MCP-derived skills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python executor.py --skill shadcn --list
  python executor.py --skill github --describe create_issue
  python executor.py --skill shadcn --call '{"tool": "search_items_in_registries", "arguments": {"registries": ["@shadcn"], "query": "button"}}'
  python executor.py --skills  # List available skills
"""
    )

    # Skill/config selection
    parser.add_argument("--skill", help="Skill name (subdirectory in mcp-skills/)")
    parser.add_argument("--config", help="Explicit path to mcp-config.json")
    parser.add_argument("--skills", action="store_true", help="List available skills")

    # Actions
    parser.add_argument("--call", help="JSON tool call to execute")
    parser.add_argument("--describe", help="Get tool schema")
    parser.add_argument("--list", action="store_true", help="List all tools")

    args = parser.parse_args()

    # Handle --skills (list available skills)
    if args.skills:
        skills = list_available_skills()
        print("Available skills:")
        for skill in skills:
            print(f"  - {skill}")
        return

    # Validate arguments
    if not args.skill and not args.config:
        parser.error("Must specify --skill or --config (or --skills to list available)")

    if not HAS_MCP:
        print("Error: mcp package not installed", file=sys.stderr)
        print("Install with: pip install mcp", file=sys.stderr)
        sys.exit(1)

    try:
        # Find and load config
        config_path = find_config(args.skill, args.config)
        with open(config_path) as f:
            config = json.load(f)

        executor = create_executor(config)

        if args.list:
            tools = await executor.list_tools()
            print(json.dumps(tools, indent=2))

        elif args.describe:
            schema = await executor.describe_tool(args.describe)
            if schema:
                print(json.dumps(schema, indent=2))
            else:
                print(f"Tool not found: {args.describe}", file=sys.stderr)
                sys.exit(1)

        elif args.call:
            call_data = json.loads(args.call)
            result = await executor.call_tool(
                call_data["tool"],
                call_data.get("arguments", {})
            )

            # Format result
            if isinstance(result, list):
                for item in result:
                    if hasattr(item, 'text'):
                        print(item.text)
                    else:
                        print(json.dumps(item.__dict__ if hasattr(item, '__dict__') else item, indent=2))
            else:
                print(json.dumps(result.__dict__ if hasattr(result, '__dict__') else result, indent=2))
        else:
            parser.print_help()

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
