"""Model Context Protocol (MCP) data structures and error handling."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class MCPError(Exception):
    """Exception raised when an MCP server returns an error response."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"MCP Error [{code}]: {message}")
        self.code = code
        self.message = message
        self.data = data


@dataclass
class MCPRequest:
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params,
        }
        if self.id is not None:
            data["id"] = self.id
        return data


@dataclass
class MCPResponse:
    id: Optional[int]
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    jsonrpc: str = "2.0"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MCPResponse:
        return cls(
            id=data.get("id"),
            result=data.get("result"),
            error=data.get("error"),
            jsonrpc=data.get("jsonrpc", "2.0"),
        )
