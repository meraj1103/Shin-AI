"""Unit tests for Shin Universal MCP Client and Registry."""

import pytest
from Shin.core.mcp.protocol import MCPRequest, MCPResponse, MCPError
from Shin.core.mcp.adapter import MCPToolAdapter
from Shin.core.mcp.registry import MCPRegistry


def test_mcp_protocol_models():
    """Verify request and response serialization."""
    req = MCPRequest(method="tools/list", params={}, id=1)
    d = req.to_dict()
    assert d["jsonrpc"] == "2.0"
    assert d["method"] == "tools/list"
    assert d["id"] == 1

    resp = MCPResponse.from_dict({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"tools": [{"name": "test_tool"}]}
    })
    assert resp.id == 1
    assert resp.result["tools"][0]["name"] == "test_tool"
    assert resp.error is None


def test_mcp_tool_adapter():
    """Verify conversion of MCP tool spec to OpenAI function schema."""
    spec = {
        "name": "read_file",
        "description": "Reads file contents from disk.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        }
    }

    invoked_with = []
    def dummy_invoke(name, args):
        invoked_with.append((name, args))
        return f"Contents of {args.get('path')}"

    adapter = MCPToolAdapter("filesystem", spec, dummy_invoke)
    tool_def = adapter.to_tool_def()

    assert tool_def["type"] == "function"
    assert tool_def["function"]["name"] == "mcp_filesystem_read_file"
    assert "[filesystem]" in tool_def["function"]["description"]

    # Test direct invocation
    out = adapter(path="/tmp/test.txt")
    assert out == "Contents of /tmp/test.txt"
    assert invoked_with == [("read_file", {"path": "/tmp/test.txt"})]


def test_mcp_registry_routing():
    """Verify MCP registry manages tools and routes invocations."""
    registry = MCPRegistry()

    # Manually register a mock adapter
    spec = {
        "name": "calc_add",
        "description": "Adds two numbers",
        "inputSchema": {"type": "object"}
    }
    adapter = MCPToolAdapter("math", spec, lambda name, args: args["a"] + args["b"])
    registry.tools["calc_add"] = adapter

    res = registry.call_tool("calc_add", {"a": 10, "b": 25})
    assert res == 35

    with pytest.raises(KeyError):
        registry.call_tool("non_existent_tool", {})
