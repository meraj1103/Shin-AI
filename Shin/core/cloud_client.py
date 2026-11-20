"""cloud_client.py — Lightweight Client to connect local PC to Shin Cloud Brain.
Runs locally on your Windows machine in HYBRID mode:
  • Captures mic audio and forwards query to Cloud Brain via WebSocket or REST
  • Receives responses and local hardware execution instructions
  • Controls local Mate Engine 3D Avatar and Windhawk Dynamic Island
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("shin.cloud_client")

try:
    import requests
except ImportError:
    requests = None


class CloudBrainClient:
    """Client for Shin Cloud Brain service."""

    _session: Optional[Any] = None
    _last_health_check: float = 0.0
    _is_healthy: bool = False

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        raw_url = base_url or os.getenv("SHIN_CLOUD_URL", "http://127.0.0.1:8080")
        self.base_url = raw_url.rstrip("/")
        self.api_key = api_key or os.getenv("SHIN_API_KEY", "")
        self.timeout = float(os.getenv("SHIN_CLOUD_TIMEOUT", "15.0"))
        if CloudBrainClient._session is None and requests:
            CloudBrainClient._session = requests.Session()

    def _get_session(self):
        if CloudBrainClient._session is None and requests:
            CloudBrainClient._session = requests.Session()
        return CloudBrainClient._session or requests

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def is_available(self, force: bool = False) -> bool:
        """Check if Cloud Brain server is reachable and healthy (cached with 30s TTL)."""
        if not requests:
            return False
        now = time.time()
        if not force and (now - CloudBrainClient._last_health_check < 30.0):
            return CloudBrainClient._is_healthy

        try:
            url = f"{self.base_url}/api/health"
            session = self._get_session()
            resp = session.get(url, headers=self._headers(), timeout=2.5)
            CloudBrainClient._is_healthy = (resp.status_code == 200)
            CloudBrainClient._last_health_check = now
            return CloudBrainClient._is_healthy
        except Exception:
            CloudBrainClient._is_healthy = False
            CloudBrainClient._last_health_check = now
            return False

    def process_utterance(self, text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send utterance to Cloud Brain and receive response payload."""
        if not requests:
            raise RuntimeError("requests library not installed")

        url = f"{self.base_url}/api/chat"
        payload = {
            "text": text,
            "client_id": "windows-desktop",
            "context": context or {},
        }

        # Indicate thinking on local hardware
        try:
            from Shin.core import island_bridge
            island_bridge.show_thinking()
        except Exception:
            pass

        try:
            from Shin.core import mate_bridge
            mate_bridge.MateBridge.get().set_state("thinking")
        except Exception:
            pass

        session = self._get_session()
        resp = session.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        # Synchronize Dynamic Island and Mate states
        self._sync_peripherals(data)
        return data

    def _sync_peripherals(self, response_data: Dict[str, Any]) -> None:
        """Broadcast state updates to local Dynamic Island and Mate Engine mascot."""
        try:
            from Shin.core import island_bridge
            island_data = response_data.get("dynamic_island", {})
            title = island_data.get("title", "🤖 Shin")
            body = island_data.get("body", response_data.get("spoken_text", ""))
            duration = float(island_data.get("duration", 4.0))
            island_bridge.IslandBridge.get()._send_to_island(title, body, duration)
        except Exception as e:
            logger.debug("Failed syncing island in cloud client: %s", e)

        try:
            from Shin.core import mate_bridge
            mate_state = response_data.get("mate_state", "speaking")
            mate_bridge.MateBridge.get().set_state(mate_state)
            spoken = response_data.get("spoken_text", "")
            if spoken:
                mate_bridge.MateBridge.get().sync_speech(spoken)
        except Exception as e:
            logger.debug("Failed syncing mate in cloud client: %s", e)

    def execute_local_action_if_needed(self, response_data: Dict[str, Any]) -> Optional[str]:
        """If Cloud Brain indicated a local PC hardware action, execute it via local commands."""
        if not response_data.get("is_local_action"):
            return None

        intent = response_data.get("intent")
        args = response_data.get("args", {})
        if not intent:
            return None

        logger.info("Executing local hardware action requested by Cloud Brain: %s (args: %s)", intent, args)
        try:
            try:
                from Shin.core import commands
            except ImportError:
                import commands

            intent_payload = {
                "intent": intent,
                "args": args if isinstance(args, dict) else {},
            }
            if response_data.get("_untrusted"):
                intent_payload["_untrusted"] = True

            result = commands.dispatch(intent_payload)
            return str(result) if result else None
        except getattr(commands, "ConfirmationRequired", Exception) as req:
            if hasattr(req, "prompt"):
                return req.prompt
            raise
        except getattr(commands, "MissingArgument", Exception) as req:
            if hasattr(req, "prompt"):
                return req.prompt
            raise
        except Exception as exc:
            logger.error("Error executing local action %s: %s", intent, exc)
            return f"Action execution error: {exc}"
