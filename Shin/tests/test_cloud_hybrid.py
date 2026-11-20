"""test_cloud_hybrid.py — Comprehensive tests for Shin Hybrid Cloud Architecture."""

import os
import time
import pytest
from fastapi.testclient import TestClient

from Shin.server.cloud_brain import app, LOCAL_HARDWARE_INTENTS
from Shin.core.cloud_client import CloudBrainClient
from Shin.core import commands


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    key = os.getenv("SHIN_API_KEY", "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


def test_cloud_brain_health(client):
    """Verify health endpoint returns status healthy."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Shin Cloud Brain"
    assert "uptime_seconds" in data


def test_cloud_brain_chat_conversational(client, auth_headers):
    """Verify conversational query produces text response."""
    resp = client.post("/api/chat", json={"text": "hello shin", "client_id": "test-suite"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "spoken_text" in data
    assert len(data["spoken_text"]) > 0
    assert data["is_local_action"] is False
    assert "dynamic_island" in data
    assert "mate_state" in data


def test_cloud_brain_hardware_intent_delegation(client, auth_headers):
    """Verify hardware commands are marked as local actions for client-side execution."""
    resp = client.post("/api/chat", json={"text": "open notepad", "client_id": "test-suite"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] in LOCAL_HARDWARE_INTENTS
    assert data["is_local_action"] is True
    assert "Notepad" in data["spoken_text"] or "notepad" in data["spoken_text"].lower()


def test_cloud_brain_empty_query_rejected(client, auth_headers):
    """Verify empty requests are handled gracefully with 400 Bad Request."""
    resp = client.post("/api/chat", json={"text": "   ", "client_id": "test-suite"}, headers=auth_headers)
    assert resp.status_code == 400


def test_cloud_brain_websocket_stream(client):
    """Verify WebSocket streaming and ping/pong."""
    key = os.getenv("SHIN_API_KEY", "").strip()
    ws_url = f"/ws/shin?token={key}" if key else "/ws/shin"
    with client.websocket_connect(ws_url) as websocket:
        welcome = websocket.receive_json()
        assert welcome["type"] == "welcome"

        # Test ping/pong
        websocket.send_json({"type": "ping"})
        pong = websocket.receive_json()
        assert pong["type"] == "pong"

        # Test utterance turn
        websocket.send_json({"type": "user_utterance", "text": "tell me a joke"})
        state_msg = websocket.receive_json()
        assert state_msg["type"] == "state_change"

        turn_msg = websocket.receive_json()
        assert turn_msg["type"] == "brain_response"
        assert "spoken_text" in turn_msg["data"]


def test_cloud_client_execute_local_action_dict_dispatch():
    """Verify CloudBrainClient safely dispatches local hardware action using single dict payload."""
    client = CloudBrainClient()
    response_data = {
        "is_local_action": True,
        "intent": "tell_time",
        "args": {}
    }
    result = client.execute_local_action_if_needed(response_data)
    assert result is not None
    assert "Action execution error" not in result
    assert ":" in result  # format of tell_time, e.g. "It's 07:44 PM."


def test_cloud_client_execute_local_action_open_app():
    """Verify CloudBrainClient open_app action execution without TypeError."""
    client = CloudBrainClient()
    response_data = {
        "is_local_action": True,
        "intent": "open_app",
        "args": {"app": "whatsapp"}
    }
    result = client.execute_local_action_if_needed(response_data)
    assert result is not None
    assert "takes 1 positional argument" not in str(result)
    assert "Action execution error" not in str(result)


def test_commands_dispatch_polymorphic():
    """Verify commands.dispatch works seamlessly with both dict and (str, dict) arguments."""
    res_dict = commands.dispatch({"intent": "tell_time", "args": {}})
    res_args = commands.dispatch("tell_time", {})
    assert res_dict is not None
    assert res_args is not None
    assert res_dict == res_args


def test_cloud_client_health_check_caching():
    """Verify health check caching respects 30-second TTL."""
    client = CloudBrainClient(base_url="http://127.0.0.1:8080")
    CloudBrainClient._last_health_check = time.time()
    CloudBrainClient._is_healthy = True

    # Immediate call within TTL should return cached state without making HTTP request
    assert client.is_available() is True
