"""Local Trace Store for Shin Voice Assistant.
Adapted from OpenJarvis trace store architecture for continuous self-improvement.
"""

from __future__ import annotations
import contextlib
import json
import logging
import os
import sqlite3
import time
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger("shin.traces.store")


class TraceStore:
    """Manages local SQLite database storing execution telemetry and traces."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "traces.db")
        self.db_path = db_path
        self._init_db()

    @contextlib.contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provides a managed connection that is guaranteed to close on Windows."""
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        try:
            with self._connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS traces (
                        id TEXT PRIMARY KEY,
                        timestamp REAL,
                        intent TEXT,
                        query TEXT,
                        status TEXT,
                        duration_ms REAL,
                        provider TEXT,
                        steps_json TEXT,
                        error TEXT,
                        metadata_json TEXT
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_traces_timestamp ON traces (timestamp DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_traces_intent ON traces (intent)"
                )
        except Exception as e:
            logger.error(f"Failed to initialize trace database: {e}")

    def record_trace(
        self,
        trace_id: str,
        intent: str,
        query: str,
        status: str,
        duration_ms: float,
        provider: str = "local",
        steps: Optional[List[Dict[str, Any]]] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insert or replace a completed execution trace."""
        try:
            with self._connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO traces (
                        id, timestamp, intent, query, status, duration_ms, provider, steps_json, error, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trace_id,
                        time.time(),
                        intent,
                        query,
                        status,
                        duration_ms,
                        provider,
                        json.dumps(steps or []),
                        error,
                        json.dumps(metadata or {}),
                    ),
                )
        except Exception as e:
            logger.warning(f"Failed to record trace '{trace_id}': {e}")

    def get_recent_traces(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve the most recent execution traces."""
        try:
            with self._connection() as conn:
                cur = conn.execute(
                    "SELECT * FROM traces ORDER BY timestamp DESC LIMIT ?", (limit,)
                )
                rows = cur.fetchall()
                results = []
                for r in rows:
                    results.append(
                        {
                            "id": r["id"],
                            "timestamp": r["timestamp"],
                            "intent": r["intent"],
                            "query": r["query"],
                            "status": r["status"],
                            "duration_ms": r["duration_ms"],
                            "provider": r["provider"],
                            "steps": json.loads(r["steps_json"] or "[]"),
                            "error": r["error"],
                            "metadata": json.loads(r["metadata_json"] or "{}"),
                        }
                    )
                return results
        except Exception as e:
            logger.warning(f"Failed to query recent traces: {e}")
            return []

    def get_intent_stats(self, intent: Optional[str] = None) -> Dict[str, Any]:
        """Compute aggregated statistics (success rate, avg duration) for intents."""
        try:
            with self._connection() as conn:
                if intent:
                    cur = conn.execute(
                        """
                        SELECT
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successes,
                            AVG(duration_ms) as avg_duration
                        FROM traces WHERE intent = ?
                        """,
                        (intent,),
                    )
                else:
                    cur = conn.execute(
                        """
                        SELECT
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successes,
                            AVG(duration_ms) as avg_duration
                        FROM traces
                        """
                    )
                row = cur.fetchone()
                if not row or row["total"] == 0:
                    return {"total": 0, "success_rate": 0.0, "avg_duration_ms": 0.0}
                total = row["total"]
                successes = row["successes"] or 0
                return {
                    "total": total,
                    "success_rate": round(successes / total, 3),
                    "avg_duration_ms": round(row["avg_duration"] or 0.0, 1),
                }
        except Exception as e:
            logger.warning(f"Failed to compute intent stats: {e}")
            return {"total": 0, "success_rate": 0.0, "avg_duration_ms": 0.0}
