"""
app_tracker.py — Foreground window usage tracker for Shin Voice Assistant
==========================================================================
Samples the active window title every 5 seconds and accumulates
time-per-app in data/app_usage.json. Provides on-demand usage stats.

Usage
-----
    import app_tracker
    app_tracker.start_tracking()   # call on Shin startup
    app_tracker.stop_tracking()    # call on Shin exit
    stats = app_tracker.get_tracker().get_stats()  # {app: seconds}
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger("shin.app_tracker")

_DATA_FILE      = Path(__file__).parent.parent / "data" / "app_usage.json"
_SAMPLE_INTERVAL = 5   # seconds between samples
_SAVE_EVERY      = 12  # save to disk every N samples (= 60 s)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_foreground_title() -> str:
    """Return the title of the current foreground window on Windows."""
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd) or ""
    except Exception:
        return ""


def _extract_app_name(title: str) -> str:
    """
    Derive a short, spoken-friendly app name from a window title.

    Examples
    --------
    "index.html - Visual Studio Code" → "Visual Studio Code"
    "YouTube - Google Chrome"         → "Google Chrome"
    "Untitled - Notepad"              → "Notepad"
    """
    if not title:
        return "Unknown"
    parts = [p.strip() for p in title.split(" - ") if p.strip()]
    return (parts[-1] if parts else title)[:50]


def _format_duration(seconds: int) -> str:
    """Convert seconds to a human-readable spoken string."""
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours   = minutes // 60
    mins    = minutes % 60
    h_str   = f"{hours} hour{'s' if hours != 1 else ''}"
    if mins:
        return f"{h_str} and {mins} minute{'s' if mins != 1 else ''}"
    return h_str


# ── Core tracker class ────────────────────────────────────────────────────────

class AppTracker:
    """Thread-safe background tracker for foreground window usage."""

    def __init__(self) -> None:
        self._lock        = threading.Lock()
        self._stop_event  = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # Structure: {date_iso: {app_name: total_seconds}}
        self._usage: dict[str, dict[str, int]] = {}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if _DATA_FILE.exists():
            try:
                with open(_DATA_FILE, "r", encoding="utf-8") as f:
                    self._usage = json.load(f)
            except Exception as exc:
                logger.warning("AppTracker: failed to load usage data: %s", exc)
                self._usage = {}

    def _save(self) -> None:
        try:
            _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self._usage, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning("AppTracker: failed to save usage data: %s", exc)

    # ── Background sampling loop ──────────────────────────────────────────────

    def _run(self) -> None:
        sample_count = 0
        while not self._stop_event.is_set():
            try:
                title = _get_foreground_title()
                app   = _extract_app_name(title)
                today = date.today().isoformat()
                with self._lock:
                    day = self._usage.setdefault(today, {})
                    day[app] = day.get(app, 0) + _SAMPLE_INTERVAL
                sample_count += 1
                if sample_count >= _SAVE_EVERY:
                    with self._lock:
                        snapshot = {k: dict(v) for k, v in self._usage.items()}
                    # Save outside the lock to keep the lock short
                    self._save_snapshot(snapshot)
                    sample_count = 0
            except Exception as exc:
                logger.debug("AppTracker sample error: %s", exc)
            self._stop_event.wait(_SAMPLE_INTERVAL)

    def _save_snapshot(self, snapshot: dict) -> None:
        try:
            _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning("AppTracker snapshot save failed: %s", exc)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        # Join any previous (dead) thread to clean up OS resources
        if self._thread is not None:
            self._thread.join(timeout=0)
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="shin-app-tracker", daemon=True
        )
        self._thread.start()
        logger.info("AppTracker started (sampling every %ds).", _SAMPLE_INTERVAL)

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            self._save()
        logger.info("AppTracker stopped; usage data saved.")

    # ── Query API ─────────────────────────────────────────────────────────────

    def get_stats(self, for_date: Optional[str] = None) -> dict[str, int]:
        """Return {app_name: seconds} for the given date (default: today)."""
        target = for_date or date.today().isoformat()
        with self._lock:
            return dict(self._usage.get(target, {}))

    def get_top_apps(self, n: int = 5, for_date: Optional[str] = None) -> list[tuple[str, int]]:
        """Return the top-N apps sorted by time descending."""
        stats = self.get_stats(for_date)
        return sorted(stats.items(), key=lambda x: x[1], reverse=True)[:n]

    def get_app_time(self, app_query: str, for_date: Optional[str] = None) -> int:
        """
        Return seconds spent on an app matching *app_query* today.
        Uses substring match then rapidfuzz fuzzy match as fallback.
        """
        stats = self.get_stats(for_date)
        if not stats:
            return 0
        app_lower = app_query.lower()
        # Exact / substring match
        for name, secs in stats.items():
            if app_lower in name.lower():
                return secs
        # Fuzzy fallback
        try:
            from rapidfuzz import process as fz
            result = fz.extractOne(app_query, stats.keys(), score_cutoff=60)
            if result:
                return stats[result[0]]
        except Exception:
            pass
        return 0

    def build_summary(self, for_date: Optional[str] = None) -> str:
        """Return a spoken summary of today's top-5 app usage."""
        top = self.get_top_apps(5, for_date)
        if not top:
            return "I haven't tracked any app usage yet today."
        lines = ["Here is your app usage for today:"]
        for rank, (app, secs) in enumerate(top, 1):
            lines.append(f"{rank}. {app}: {_format_duration(secs)}.")
        return " ".join(lines)


# ── Module-level singleton ────────────────────────────────────────────────────

_tracker: Optional[AppTracker] = None
_tracker_lock = threading.Lock()


def get_tracker() -> AppTracker:
    """Return the module-level AppTracker singleton, creating it if needed (thread-safe)."""
    global _tracker
    if _tracker is None:
        with _tracker_lock:
            # Double-checked locking: re-test inside the lock
            if _tracker is None:
                _tracker = AppTracker()
    return _tracker


def start_tracking() -> None:
    """Start the background sampling thread. Safe to call multiple times."""
    get_tracker().start()


def stop_tracking() -> None:
    """Flush data to disk and stop the background thread."""
    if _tracker is not None:
        _tracker.stop()
