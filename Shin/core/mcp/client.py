"""MCP Client supporting JSON-RPC over stdio for Shin Voice Assistant."""

from __future__ import annotations
import json
import logging
import subprocess
import threading
from typing import Any, Dict, List, Optional

from Shin.core.mcp.protocol import MCPError, MCPRequest, MCPResponse

logger = logging.getLogger("shin.mcp")


class StdioMCPClient:
    """Manages an active child process MCP server communicating via stdin/stdout."""

    def __init__(self, command: str, args: Optional[List[str]] = None, env: Optional[Dict[str, str]] = None):
        self.command = command
        self.args = args or []
        self.env = env
        self.process: Optional[subprocess.Popen] = None
        self._id_counter = 0
        self._lock = threading.Lock()
        self._initialized = False

    def start(self) -> None:
        """Spawn the child process server."""
        if self.process is not None:
            return

        cmd = [self.command] + self.args
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=self.env,
        )

    def stop(self) -> None:
        """Terminate child process server gracefully."""
        if self.process is not None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            finally:
                self.process = None
                self._initialized = False

    def send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> MCPResponse:
        """Send a JSON-RPC request and wait synchronously for response."""
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError(f"MCP server '{self.command}' is not running.")

        with self._lock:
            self._id_counter += 1
            req_id = self._id_counter
            req = MCPRequest(method=method, params=params or {}, id=req_id)
            payload = json.dumps(req.to_dict()) + "\n"

            assert self.process.stdin is not None
            assert self.process.stdout is not None

            try:
                self.process.stdin.write(payload)
                self.process.stdin.flush()
            except Exception as e:
                raise RuntimeError(f"Failed to write to MCP server stdin: {e}")

            # Read response line
            line = self.process.stdout.readline()
            if not line:
                stderr_out = ""
                if self.process.stderr:
                    stderr_out = self.process.stderr.read()
                raise RuntimeError(f"MCP server closed stream unexpectedly. Stderr: {stderr_out}")

            try:
                data = json.loads(line.strip())
            except Exception as e:
                raise RuntimeError(f"Failed to parse JSON response from MCP server: {line.strip()} ({e})")

            resp = MCPResponse.from_dict(data)
            if resp.error:
                raise MCPError(
                    code=resp.error.get("code", -1),
                    message=resp.error.get("message", "Unknown error"),
                    data=resp.error.get("data"),
                )
            return resp

    def initialize(self) -> Dict[str, Any]:
        """Perform MCP initialize handshake."""
        self.start()
        resp = self.send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "Shin-Voice-Assistant", "version": "2.0"},
            },
        )
        self._initialized = True
        return resp.result or {}

    def list_tools(self) -> List[Dict[str, Any]]:
        """Query available tools from server."""
        if not self._initialized:
            self.initialize()
        resp = self.send_request("tools/list", {})
        return (resp.result or {}).get("tools", [])

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a specific tool on the server."""
        if not self._initialized:
            self.initialize()
        resp = self.send_request("tools/call", {"name": name, "arguments": arguments})
        return resp.result
