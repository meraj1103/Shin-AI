"""Trace Collector context manager for Shin executions."""

from __future__ import annotations
import time
import uuid
from typing import Any, Dict, List, Optional

from Shin.core.traces.store import TraceStore


class TraceContext:
    """Active execution span being recorded."""

    def __init__(self, trace_id: str, intent: str, query: str, store: TraceStore):
        self.trace_id = trace_id
        self.intent = intent
        self.query = query
        self.store = store
        self.steps: List[Dict[str, Any]] = []
        self.status = "running"
        self.error: Optional[str] = None
        self.provider = "local"
        self.metadata: Dict[str, Any] = {}
        self._start_time = time.monotonic()

    def add_step(self, step_name: str, success: bool = True, output: Any = None, error: Optional[str] = None) -> None:
        self.steps.append(
            {
                "step": step_name,
                "success": success,
                "output": str(output)[:500] if output is not None else None,
                "error": error,
                "timestamp": time.time(),
            }
        )

    def set_provider(self, provider: str) -> None:
        self.provider = provider

    def set_metadata(self, key: str, value: Any) -> None:
        self.metadata[key] = value

    def fail(self, error: str) -> None:
        self.status = "failed"
        self.error = error

    def finish(self) -> None:
        if self.status == "running":
            self.status = "success"
        duration_ms = (time.monotonic() - self._start_time) * 1000
        self.store.record_trace(
            trace_id=self.trace_id,
            intent=self.intent,
            query=self.query,
            status=self.status,
            duration_ms=duration_ms,
            provider=self.provider,
            steps=self.steps,
            error=self.error,
            metadata=self.metadata,
        )


class TraceCollector:
    """Manages creation and completion of trace spans."""

    def __init__(self, store: Optional[TraceStore] = None):
        self.store = store or TraceStore()

    def trace(self, intent: str, query: str = "") -> TraceContextManager:
        return TraceContextManager(intent, query, self.store)


class TraceContextManager:
    """Context manager wrapping TraceContext."""

    def __init__(self, intent: str, query: str, store: TraceStore):
        self.trace_id = str(uuid.uuid4())
        self.ctx = TraceContext(self.trace_id, intent, query, store)

    def __enter__(self) -> TraceContext:
        return self.ctx

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.ctx.fail(str(exc_val))
        self.ctx.finish()
        return False
