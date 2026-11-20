"""Registry of MCP servers and unified tool discovery for Shin."""

from __future__ import annotations
import json
import logging
import os
from typing import Any, Dict, List, Optional

from Shin.core.mcp.client import StdioMCPClient
from Shin.core.mcp.adapter import MCPToolAdapter

logger = logging.getLogger("shin.mcp.registry")


class MCPRegistry:
    """Manages external MCP server instances and routes tool calls."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "mcp_servers.json"
        )
        self.clients: Dict[str, StdioMCPClient] = {}
        self.tools: Dict[str, MCPToolAdapter] = {}

    def register_server(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        """Register and start an MCP server client."""
        client = StdioMCPClient(command=command, args=args, env=env)
        self.clients[name] = client
        try:
            client.initialize()
            raw_tools = client.list_tools()
            for t in raw_tools:
                tool_name = t.get("name")
                if tool_name:
                    qualified_name = f"mcp_{name}_{tool_name}"
                    adapter = MCPToolAdapter(
                        server_name=name,
                        tool_spec=t,
                        invoke_fn=client.call_tool,
                    )
                    self.tools[qualified_name] = adapter
                    # Also register un-prefixed name if no conflict
                    if tool_name not in self.tools:
                        self.tools[tool_name] = adapter
            logger.info(f"Registered MCP server '{name}' with {len(raw_tools)} tools.")
        except Exception as e:
            logger.warning(f"Could not initialize MCP server '{name}': {e}")

    def load_config(self) -> None:
        """Load and instantiate servers configured in JSON."""
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            servers = data.get("mcpServers", {})
            for name, cfg in servers.items():
                cmd = cfg.get("command")
                args = cfg.get("args", [])
                env = cfg.get("env")
                if cmd:
                    self.register_server(name, cmd, args, env)
        except Exception as e:
            logger.error(f"Failed to load MCP configuration from {self.config_path}: {e}")

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool by name."""
        if tool_name not in self.tools:
            raise KeyError(f"Tool '{tool_name}' not found in MCP registry.")
        adapter = self.tools[tool_name]
        return adapter(**arguments)

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all tool schemas for LLM tool calling."""
        return [adapter.to_tool_def() for adapter in self.tools.values()]

    def shutdown(self) -> None:
        """Stop all running MCP servers."""
        for name, client in self.clients.items():
            try:
                client.stop()
            except Exception:
                pass
        self.clients.clear()
        self.tools.clear()
