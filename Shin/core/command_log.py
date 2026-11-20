"""
command_log.py — Command history logger for Shin Voice Assistant
================================================================
Persists up to MAX_ENTRIES command records to ~/Documents/Shin/command_history.json.
Also exposes recent_commands() for the UI history feed.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_LOG_DIR = Path(__file__).parent.parent / "data"
_LOG_FILE = _LOG_DIR / "command_history.json"

# Migrate old data if it exists in the Documents/Shin folder
_OLD_LOG_DIR = Path.home() / "Documents" / "Shin"
if _OLD_LOG_DIR.exists() and (_OLD_LOG_DIR / "command_history.json").exists() and not _LOG_FILE.exists():
    import shutil
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(_OLD_LOG_DIR / "command_history.json", _LOG_FILE)
        logger.info("Migrated command_history.json from %s to %s", _OLD_LOG_DIR, _LOG_DIR)
    except Exception as exc:
        logger.warning("Failed to migrate command_history.json: %s", exc)
MAX_ENTRIES = 200


def _load() -> list[dict]:
    if not _LOG_FILE.exists():
        return []
    try:
        with open(_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(entries: list[dict]) -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warning("command_log save failed: %s", exc)


def log_command(heard: str, intent: str, response: str) -> dict:
    """
    Append a command record and return it (for immediate WS broadcast).
    Auto-rotates at MAX_ENTRIES.
    """
    entries = _load()
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "heard": heard,
        "intent": intent,
        "response": response,
    }
    entries.append(entry)
    # Trim to most recent MAX_ENTRIES
    if len(entries) > MAX_ENTRIES:
        entries = entries[-MAX_ENTRIES:]
    _save(entries)
    return entry


def recent_commands(n: int = 20) -> list[dict]:
    """Return the *n* most recent command entries (newest first)."""
    entries = _load()
    return list(reversed(entries[-n:]))
