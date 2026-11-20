"""MCP Client & Adapter integration for Shin Voice Assistant.
Adapted from OpenJarvis MCP architecture.
"""

from Shin.core.mcp.protocol import MCPError, MCPRequest, MCPResponse
from Shin.core.mcp.client import StdioMCPClient
from Shin.core.mcp.adapter import MCPToolAdapter
from Shin.core.mcp.registry import MCPRegistry

__all__ = [
    "MCPError",
    "MCPRequest",
    "MCPResponse",
    "StdioMCPClient",
    "MCPToolAdapter",
    "MCPRegistry",
]
