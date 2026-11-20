"""Unit tests for Shin Local Execution Traces and Telemetry."""

import os
import tempfile
import pytest
from Shin.core.traces.store import TraceStore
from Shin.core.traces.collector import TraceCollector


def test_trace_store_lifecycle():
    """Verify trace recording, retrieval, and statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_traces.db")
        store = TraceStore(db_path=db_path)

        store.record_trace(
            trace_id="tr-001",
            intent="click_text",
            query="click on My mix",
            status="success",
            duration_ms=45.2,
            provider="local",
            steps=[{"step": "ocr_search", "success": True}],
        )

        store.record_trace(
            trace_id="tr-002",
            intent="click_text",
            query="click on extension",
            status="failed",
            duration_ms=120.5,
            provider="local",
            error="Element not found",
        )

        recent = store.get_recent_traces(limit=10)
        assert len(recent) == 2
        assert recent[0]["id"] == "tr-002"
        assert recent[1]["id"] == "tr-001"

        stats = store.get_intent_stats(intent="click_text")
        assert stats["total"] == 2
        assert stats["success_rate"] == 0.5
        assert stats["avg_duration_ms"] > 0


def test_trace_collector_context_manager():
    """Verify trace context manager records duration, steps, and status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_traces.db")
        store = TraceStore(db_path=db_path)
        collector = TraceCollector(store=store)

        with collector.trace(intent="open_app", query="open chrome") as t:
            t.add_step("resolve_path", success=True, output="chrome.exe")
            t.add_step("launch_process", success=True, output="PID 1234")
            t.set_provider("groq")

        recent = store.get_recent_traces(limit=1)
        assert len(recent) == 1
        tr = recent[0]
        assert tr["intent"] == "open_app"
        assert tr["status"] == "success"
        assert tr["provider"] == "groq"
        assert len(tr["steps"]) == 2
        assert tr["steps"][0]["step"] == "resolve_path"
