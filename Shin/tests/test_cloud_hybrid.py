"""test_cloud_hybrid.py — Comprehensive tests for Shin Hybrid Cloud Architecture."""

import pytest
from fastapi.testclient import TestClient

from Shin.server.cloud_brain import app, LOCAL_HARDWARE_INTENTS
from Shin.core.cloud_client import CloudBrainClient


@pytest.fixture
def client():
    return TestClient(app)


def test_cloud_brain_health(client):
    """Verify health endpoint returns status healthy."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Shin Cloud Brain"
    assert "uptime_seconds" in data


def test_cloud_brain_chat_conversational(client):
    """Verify conversational query produces text response."""
    resp = client.post("/api/chat", json={"text": "hello shin", "client_id": "test-suite"})
    assert resp.status_code == 200
    data = resp.json()
    assert "spoken_text" in data
    assert len(data["spoken_text"]) > 0
    assert data["is_local_action"] is False
    assert "dynamic_island" in data
    assert "mate_state" in data


def test_cloud_brain_hardware_intent_delegation(client):
    """Verify hardware commands are marked as local actions for client-side execution."""
    resp = client.post("/api/chat", json={"text": "open notepad", "client_id": "test-suite"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] in LOCAL_HARDWARE_INTENTS
    assert data["is_local_action"] is True
    assert "Notepad" in data["spoken_text"] or "notepad" in data["spoken_text"].lower()


def test_cloud_brain_empty_query_rejected(client):
    """Verify empty requests are handled gracefully with 400 Bad Request."""
    resp = client.post("/api/chat", json={"text": "   ", "client_id": "test-suite"})
    assert resp.status_code == 400


def test_cloud_brain_websocket_stream(client):
    """Verify WebSocket streaming and ping/pong."""
    with client.websocket_connect("/ws/shin") as websocket:
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
