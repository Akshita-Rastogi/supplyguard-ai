import asyncio
import json
from urllib.parse import urlparse

from mcp import ClientSession

try:
    # MCP 2.x introduced a first-class Client that owns transport negotiation.
    from mcp import Client as MCPClient
except ImportError:  # pragma: no cover - exercised with MCP 1.x
    MCPClient = None
    from mcp.client.streamable_http import streamablehttp_client as streamable_http_client
else:
    streamable_http_client = None

if MCPClient is None and streamable_http_client is None:  # pragma: no cover - defensive import
    from mcp.client.streamable_http import streamablehttp_client as streamable_http_client


class MCPToolError(RuntimeError):
    """Stable application error for all MCP transport and tool failures."""


class MCPGateway:
    """Small client boundary for invoking independently served MCP tools."""

    def __init__(self, url: str):
        """Store the streamable-HTTP endpoint without opening a connection early."""
        self.url = url

    async def call(self, name: str, arguments: dict) -> dict:
        """Initialize an MCP session, call one tool, and normalize its JSON result."""
        try:
            if MCPClient is not None:
                async with MCPClient(self.url) as client:
                    result = await client.call_tool(name, arguments)
            else:
                async with streamable_http_client(self.url) as streams:
                    read, write = streams[:2]
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(name, arguments=arguments)
            is_error = getattr(result, "is_error", getattr(result, "isError", False))
            if is_error or not result.content:
                raise MCPToolError(f"MCP tool {name} returned an error")
            return json.loads(result.content[0].text)
        except Exception as exc:  # Normalize MCP transport/session error groups.
            raise MCPToolError(f"MCP tool unavailable: {type(exc).__name__}") from exc

    async def ready(self) -> bool:
        """Check MCP network reachability without invoking a data-producing tool."""
        parsed = urlparse(self.url)
        if not parsed.hostname:
            return False
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(parsed.hostname, port), timeout=2
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, TimeoutError):
            return False
