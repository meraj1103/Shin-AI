"""Unit tests for Mate Engine LLM Proxy Server."""

import json
import urllib.request
import pytest
from Shin.core.mate_llm_proxy import MateLLMProxyServer


@pytest.fixture
def test_proxy_server():
    server = MateLLMProxyServer(host="127.0.0.1", port=13337)
    server.set_handler(lambda query, msgs: f"Echo: {query}")
    assert server.start() is True
    yield server
    server.stop()


def test_proxy_health(test_proxy_server):
    req = urllib.request.Request("http://127.0.0.1:13337/health")
    with urllib.request.urlopen(req, timeout=2.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("status") == "ok"


def test_proxy_tokenize(test_proxy_server):
    payload = json.dumps({"content": "Hello world"}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:13337/tokenize", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=2.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "tokens" in data
        assert len(data["tokens"]) == 2


def test_proxy_completion_json(test_proxy_server):
    payload = json.dumps({"prompt": "Hello Shin", "stream": False}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:13337/completion", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=2.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("content") == "Echo: Hello Shin"
        assert data.get("stop") is True


def test_proxy_completion_stream(test_proxy_server):
    payload = json.dumps({"prompt": "Hello Shin", "stream": True}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:13337/completion", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=2.0) as resp:
        assert resp.status == 200
        lines = resp.read().decode("utf-8").split("\n")
        data_lines = [line[6:] for line in lines if line.startswith("data: ")]
        assert len(data_lines) >= 2
        first_chunk = json.loads(data_lines[0])
        assert "content" in first_chunk
        last_chunk = json.loads(data_lines[-1])
        assert last_chunk.get("stop") is True
