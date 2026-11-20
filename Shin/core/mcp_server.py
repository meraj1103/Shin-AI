"""
mcp_server.py — Model Context Protocol (MCP) Standard Server for Shin
====================================================================
Implements Anthropic's open-source Model Context Protocol (JSON-RPC 2.0):
Enables any MCP-compliant Host (Antigravity, Claude Desktop, IDEs, or web agents)
to discover and execute Shin's voice, vision, OS, and coding tools.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

logger = logging.getLogger("shin.mcp")

# Tool definitions advertised via MCP tools/list
TOOLS = [
    {
        "name": "shin_inspect_screen",
        "description": "Examine the active window and screen content to diagnose errors or summarize workspace activity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "diagnose_errors": {"type": "boolean", "description": "Scan specifically for code or terminal bugs"}
            }
        }
    },
    {
        "name": "shin_get_ui_tree",
        "description": "Extract structured Windows UIAutomation interactive controls (buttons, inputs, tabs) with 0-token overhead.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "shin_click_ui_element",
        "description": "Click an interactive UI control by name without spatial hallucination.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "element_name": {"type": "string", "description": "Name or text of the button/control"}
            },
            "required": ["element_name"]
        }
    },
    {
        "name": "shin_run_python_code",
        "description": "Safely execute a snippet of Python code in the project workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"}
            },
            "required": ["code"]
        }
    },
    {
        "name": "shin_review_code",
        "description": "Analyze code for security risks, anti-patterns, and enterprise compliance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Path to file, or leave empty to scan clipboard"}
            }
        }
    },
    {
        "name": "shin_check_git_status",
        "description": "Inspect Git branch, uncommitted changes, and repository status.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


def handle_mcp_request(request: dict) -> dict:
    """Process a single JSON-RPC 2.0 MCP request."""
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "shin-mcp-server", "version": "2.0.0"}
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS}
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        try:
            if tool_name == "shin_inspect_screen":
                import vision
                if args.get("diagnose_errors"):
                    res = vision.diagnose_screen_error()
                else:
                    res = vision.summarize_screen_activity()
                return _tool_success(req_id, res)

            elif tool_name == "shin_get_ui_tree":
                import ui_tree
                res = ui_tree.format_ui_tree_summary()
                return _tool_success(req_id, res or "No active UI controls found.")

            elif tool_name == "shin_click_ui_element":
                import ui_tree
                ok, msg = ui_tree.click_ui_element_by_name(args.get("element_name", ""))
                return _tool_success(req_id, msg)

            elif tool_name == "shin_run_python_code":
                import commands
                res = commands.run_python_code({"code": args.get("code", "")})
                return _tool_success(req_id, res)

            elif tool_name == "shin_review_code":
                import commands
                res = commands.review_code(args)
                return _tool_success(req_id, res)

            elif tool_name == "shin_check_git_status":
                import commands
                res = commands.project_git_status({})
                return _tool_success(req_id, res)

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {tool_name}"}
                }
        except Exception as exc:
            return _tool_success(req_id, f"Execution failed: {exc}", is_error=True)

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"}
    }


def _tool_success(req_id: Any, text: str, is_error: bool = False) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "content": [{"type": "text", "text": text}],
            "isError": is_error
        }
    }


if __name__ == "__main__":
    # Stdio-based JSON-RPC MCP server
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_mcp_request(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            logger.error("MCP stdio error: %s", e)
