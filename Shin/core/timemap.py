"""
Shin Voice Assistant - Proactive Timemap & Heartbeat Scheduler
Inspired by DesktopFriends (TableFri) agent architecture.

Features:
- Pure local 60-second heartbeat ticker (zero token cost per tick)
- Semantic schedule entries (HH:mm, action, repeat: daily | once)
- Daily rollover and automated expiry of one-off entries
- Autonomous trigger dispatch to Mate Engine and Dynamic Island
"""

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
TIMEMAP_FILE = os.path.join(DATA_DIR, "timemap.json")


class TimemapEntry:
    def __init__(
        self,
        time_str: str,
        action: str,
        repeat: str = "once",
        entry_id: Optional[str] = None,
        status: str = "pending",
        created_at: Optional[str] = None,
    ):
        self.id = entry_id or str(uuid.uuid4())[:8]
        self.time = time_str  # format "HH:MM" (24-hour)
        self.action = action
        self.repeat = repeat if repeat in ("daily", "once") else "once"
        self.status = status  # "pending", "triggered", "done"
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "time": self.time,
            "action": self.action,
            "repeat": self.repeat,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimemapEntry":
        return cls(
            time_str=data.get("time", "12:00"),
            action=data.get("action", ""),
            repeat=data.get("repeat", "once"),
            entry_id=data.get("id"),
            status=data.get("status", "pending"),
            created_at=data.get("created_at"),
        )


class TimemapManager:
    """Manages persistent schedule storage and day rollover."""

    def __init__(self, filepath: str = TIMEMAP_FILE):
        self.filepath = filepath
        self.entries: List[TimemapEntry] = []
        self.last_date: str = datetime.now().strftime("%Y-%m-%d")
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.filepath):
            self._save_default()
            return
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.last_date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
                raw_entries = data.get("entries", [])
                self.entries = [TimemapEntry.from_dict(e) for e in raw_entries]
        except Exception as e:
            logger.error(f"[TimemapManager] Failed to load {self.filepath}: {e}")
            self.entries = []

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        data = {
            "date": self.last_date,
            "last_heartbeat": int(time.time()),
            "entries": [e.to_dict() for e in self.entries],
        }
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[TimemapManager] Failed to save {self.filepath}: {e}")

    def _save_default(self) -> None:
        """Seed reasonable defaults if empty."""
        self.entries = [
            TimemapEntry("09:00", "Morning greeting and daily check-in with MJ", repeat="daily"),
            TimemapEntry("14:30", "Afternoon hydration check-in and stretch break", repeat="daily"),
        ]
        self.save()

    def add_entry(self, time_str: str, action: str, repeat: str = "once") -> Optional[TimemapEntry]:
        # Validate HH:MM format
        parts = time_str.strip().split(":")
        if len(parts) != 2:
            return None
        try:
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                return None
            norm_time = f"{h:02d}:{m:02d}"
        except ValueError:
            return None

        entry = TimemapEntry(norm_time, action.strip(), repeat=repeat)
        self.entries.append(entry)
        self.save()
        logger.info(f"[TimemapManager] Added entry {entry.id}: {entry.time} - {entry.action} ({entry.repeat})")
        return entry

    def remove_entry(self, entry_id: str) -> bool:
        initial_len = len(self.entries)
        self.entries = [e for e in self.entries if e.id != entry_id]
        if len(self.entries) < initial_len:
            self.save()
            return True
        return False

    def clear_entries(self) -> None:
        self.entries = []
        self.save()

    def get_summary(self) -> str:
        """Returns concise text summary of pending tasks for prompt injection."""
        pending = [e for e in self.entries if e.status == "pending"]
        if not pending:
            return "No scheduled tasks for today."
        return "\n".join([f"- {e.time} {e.action} ({'Daily' if e.repeat == 'daily' else 'Today'})" for e in pending])

    def check_and_rollover(self) -> None:
        """Handles midnight rollover: resets daily tasks and purges triggered one-off tasks."""
        current_date = datetime.now().strftime("%Y-%m-%d")
        if current_date != self.last_date:
            logger.info(f"[TimemapManager] New day detected ({current_date}), resetting daily tasks.")
            self.last_date = current_date
            retained = []
            for e in self.entries:
                if e.repeat == "daily":
                    e.status = "pending"
                    retained.append(e)
                elif e.status != "triggered":
                    retained.append(e)
            self.entries = retained
            self.save()

    def get_due_entries(self, current_hhmm: Optional[str] = None) -> List[TimemapEntry]:
        """Finds all pending entries that are due at or before current time."""
        if not current_hhmm:
            current_hhmm = datetime.now().strftime("%H:%M")

        self.check_and_rollover()
        due = []
        for e in self.entries:
            if e.status == "pending" and e.time <= current_hhmm:
                due.append(e)
        return due

    def mark_triggered(self, entry_id: str) -> None:
        for e in self.entries:
            if e.id == entry_id:
                e.status = "triggered"
                break
        self.save()


class HeartbeatScheduler:
    """
    Background 60-second ticker inspired by DesktopFriends.
    Evaluates due timemap entries purely locally with zero token consumption.
    Dispatches on_trigger callbacks when actions are due.
    """

    def __init__(
        self,
        timemap_manager: Optional[TimemapManager] = None,
        on_trigger: Optional[Callable[[TimemapEntry], None]] = None,
        interval_seconds: int = 60,
    ):
        self.timemap = timemap_manager or TimemapManager()
        self.on_trigger = on_trigger
        self.interval = interval_seconds
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ShinHeartbeatThread")
        self._thread.start()
        logger.info(f"[HeartbeatScheduler] Started local heartbeat loop (interval: {self.interval}s)")

    def stop(self) -> None:
        self.is_running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("[HeartbeatScheduler] Stopped local heartbeat loop")

    def tick_once(self) -> List[TimemapEntry]:
        """Manually runs one tick (useful for test verification)."""
        due_entries = self.timemap.get_due_entries()
        for entry in due_entries:
            self.timemap.mark_triggered(entry.id)
            if self.on_trigger:
                try:
                    self.on_trigger(entry)
                except Exception as e:
                    logger.error(f"[HeartbeatScheduler] Trigger callback error for {entry.id}: {e}")
        return due_entries

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.tick_once()
            except Exception as e:
                logger.error(f"[HeartbeatScheduler] Tick error: {e}")

            # Sleep in short increments for responsive shutdown
            for _ in range(self.interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1.0)
