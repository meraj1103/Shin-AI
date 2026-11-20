"""
Shin Voice Assistant - Mate Engine LLM Proxy Server
===================================================
Hosts a lightweight HTTP server on port 13333 compatible with LLMUnity (llama.cpp format).
Intercepts queries from Mate Engine's desktop character and routes them directly through
Shin's intelligence engine (Gemini / Groq / OpenAI / Claude / Ollama / Memory), streaming
the response back to render speech bubbles and drive talking animations in real-time.
"""

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class MateLLMRequestHandler(BaseHTTPRequestHandler):
    """Handles LLMUnity/llama.cpp HTTP requests from Mate Engine."""

    # Set by server instance
    router_callback: Optional[Callable[[str, List[Dict[str, str]]], str]] = None
    stream_callback: Optional[Callable[[str, List[Dict[str, str]]], Any]] = None

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard HTTP logs unless debugging
        logger.debug("[MateLLMProxy] %s", format % args)

    def _set_headers(self, status: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self) -> None:
        self._set_headers(200)
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?")[0].rstrip("/")
        if path in ("/health", "/props", ""):
            self._set_headers(200)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "shin_mate_llm_proxy"}).encode("utf-8"))
        elif path == "/slots":
            self._set_headers(200)
            self.end_headers()
            self.wfile.write(b"[]")
        else:
            self._set_headers(200)
            self.end_headers()
            self.wfile.write(b"{}")

    def do_POST(self) -> None:
        path = self.path.split("?")[0].rstrip("/")
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            req_json = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            req_json = {}

        if path == "/completion":
            self._handle_completion(req_json)
        elif path == "/tokenize":
            # Fast mock for LLMUnity Warmup()
            content = req_json.get("content", "")
            tokens = [hash(word) % 10000 for word in content.split()] if content else [1]
            self._set_headers(200)
            self.end_headers()
            self.wfile.write(json.dumps({"tokens": tokens}).encode("utf-8"))
        elif path == "/detokenize":
            self._set_headers(200)
            self.end_headers()
            self.wfile.write(json.dumps({"content": "Shin"}).encode("utf-8"))
        elif path == "/slots":
            self._set_headers(200)
            self.end_headers()
            self.wfile.write(b"[]")
        else:
            self._set_headers(200)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

    def _handle_completion(self, req_json: Dict[str, Any]) -> None:
        prompt = req_json.get("prompt", "")
        messages = req_json.get("messages", [])
        stream = req_json.get("stream", False)

        # Extract user query
        query = ""
        if messages:
            for m in reversed(messages):
                if m.get("role") == "user":
                    query = m.get("content", "")
                    break
        if not query and prompt:
            query = prompt

        logger.info("[MateLLMProxy] Received completion query: %s (stream=%s)", query[:80], stream)

        # Generate response using registered callback or Shin LLMRouter
        full_reply = ""
        if MateLLMRequestHandler.router_callback:
            try:
                full_reply = MateLLMRequestHandler.router_callback(query, messages)
            except Exception as e:
                logger.error("[MateLLMProxy] Router callback error: %e", e)
                full_reply = "Arey MJ! I'm right here with you."
        else:
            full_reply = "Arey MJ! I'm right here with you."

        if stream:
            # Stream in chunks compatible with LLMUnity / llama.cpp SSE
            self._set_headers(200, "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            # Split reply into natural conversational chunks
            words = full_reply.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                event_data = json.dumps({"content": chunk, "stop": False})
                try:
                    self.wfile.write(f"data: {event_data}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    time.sleep(0.02)  # Natural typing latency
                except (BrokenPipeError, ConnectionResetError):
                    break

            # Final stop chunk
            stop_data = json.dumps({"content": "", "stop": True})
            try:
                self.wfile.write(f"data: {stop_data}\n\n".encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass
            self.close_connection = True
        else:
            # Non-streaming JSON response
            self._set_headers(200)
            self.end_headers()
            resp = {
                "content": full_reply,
                "stop": True,
                "model": "Shin-AI-Brain",
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))


class MateLLMProxyServer:
    """Manages the lifecycle of the port 13333 Mate Engine proxy server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 13333):
        self.host = host
        self.port = port
        self.server: Optional[ThreadingSimpleServer] = None
        self._thread: Optional[threading.Thread] = None
        self.is_running = False

    def set_handler(self, callback: Callable[[str, List[Dict[str, str]]], str]) -> None:
        MateLLMRequestHandler.router_callback = callback

    def start(self) -> bool:
        if self.is_running:
            return True
        try:
            self.server = ThreadingSimpleServer((self.host, self.port), MateLLMRequestHandler)
            self.is_running = True
            self._thread = threading.Thread(
                target=self.server.serve_forever, daemon=True, name="MateLLMProxyThread"
            )
            self._thread.start()
            logger.info("[MateLLMProxyServer] Serving Mate Engine LLM proxy on http://%s:%d", self.host, self.port)
            return True
        except Exception as e:
            logger.error("[MateLLMProxyServer] Failed to bind to %s:%d: %s", self.host, self.port, e)
            self.is_running = False
            return False

    def stop(self) -> None:
        if not self.is_running:
            return
        self.is_running = False
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception as e:
                logger.error("[MateLLMProxyServer] Shutdown error: %s", e)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("[MateLLMProxyServer] Proxy stopped.")
