"""Adapts external MCP tool specs into Shin callable actions."""

from __future__ import annotations
from typing import Any, Callable, Dict, Optional


class MCPToolAdapter:
    """Wraps an MCP tool declaration into a standardized Shin action."""

    def __init__(self, server_name: str, tool_spec: Dict[str, Any], invoke_fn: Callable[[str, Dict[str, Any]], Any]):
        self.server_name = server_name
        self.name = tool_spec.get("name", "unnamed_tool")
        self.description = tool_spec.get("description", "")
        self.input_schema = tool_spec.get("inputSchema", {})
        self._invoke_fn = invoke_fn

    def __call__(self, **kwargs: Any) -> Any:
        return self._invoke_fn(self.name, kwargs)

    def to_tool_def(self) -> Dict[str, Any]:
        """Convert to OpenAI / Groq tool definition format."""
        return {
            "type": "function",
            "function": {
                "name": f"mcp_{self.server_name}_{self.name}",
                "description": f"[{self.server_name}] {self.description}",
                "parameters": self.input_schema,
            },
        }
