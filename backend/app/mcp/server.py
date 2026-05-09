"""
MCP server registration.
Exposes the curated tools as an MCP server so the service can later be
connected to by external MCP clients (e.g., Claude Desktop) via stdio or SSE.
For v1 in-process use the agent calls tool functions directly from tools.py.
"""
import json
import logging

from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.types as types

from app.mcp.tools import TOOL_REGISTRY, TOOL_SCHEMAS

logger = logging.getLogger(__name__)

mcp_server = Server("survey-ai-mcp")


@mcp_server.list_tools()
async def list_tools() -> list[types.Tool]:
    result = []
    for schema in TOOL_SCHEMAS:
        fn = schema["function"]
        result.append(
            types.Tool(
                name=fn["name"],
                description=fn["description"],
                inputSchema=fn["parameters"],
            )
        )
    return result


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        raise ValueError(f"Unknown tool: {name}")
    try:
        result = await fn(**arguments)
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    except Exception as exc:
        logger.error("Tool %s failed: %s", name, exc)
        return [types.TextContent(type="text", text=json.dumps({"error": str(exc)}))]
