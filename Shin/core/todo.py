"""
todo.py — Persistent To-Do list for Shin Voice Assistant
=========================================================
Stores tasks in ~/Documents/Shin/todos.json.

Operations: add, list (open/done/all), complete, delete.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_TODO_DIR = Path(__file__).parent.parent / "data"
_TODO_FILE = _TODO_DIR / "todos.json"

# Migrate old data if it exists in the Documents/Shin folder
_OLD_TODO_DIR = Path.home() / "Documents" / "Shin"
if _OLD_TODO_DIR.exists() and (_OLD_TODO_DIR / "todos.json").exists() and not _TODO_FILE.exists():
    import shutil
    _TODO_DIR.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(_OLD_TODO_DIR / "todos.json", _TODO_FILE)
        logger.info("Migrated todos.json from %s to %s", _OLD_TODO_DIR, _TODO_DIR)
    except Exception as exc:
        logger.error("Failed to migrate todos.json: %s", exc)


def _load() -> list[dict]:
    if not _TODO_FILE.exists():
        return []
    try:
        with open(_TODO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load todos: %s", exc)
        return []


def _save(todos: list[dict]) -> None:
    _TODO_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(_TODO_FILE, "w", encoding="utf-8") as f:
            json.dump(todos, f, indent=4, ensure_ascii=False)
    except Exception as exc:
        logger.error("Failed to save todos: %s", exc)


def add_todo(task: str) -> str:
    """Add a new open task."""
    task = task.strip()
    if not task:
        return "What would you like me to add to your to-do list?"

    todos = _load()
    # Avoid duplicates
    for t in todos:
        if t["task"].lower() == task.lower() and not t["done"]:
            return f"'{task}' is already on your to-do list."

    todos.append({
        "id": len(todos) + 1,
        "task": task,
        "done": False,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "completed_at": None,
    })
    _save(todos)
    return f"Added to your to-do list: {task}."


def list_todos(filter_: str = "open") -> str:
    """
    List tasks. filter_ is 'open' (default), 'done', or 'all'.
    """
    todos = _load()

    if filter_ == "done":
        items = [t for t in todos if t["done"]]
        label = "completed"
    elif filter_ == "all":
        items = todos
        label = "all"
    else:
        items = [t for t in todos if not t["done"]]
        label = "open"

    if not items:
        if label == "open":
            return "Your to-do list is empty. Well done!"
        return f"You have no {label} tasks."

    task_names = [f"'{t['task']}'" for t in items[:10]]
    if len(task_names) == 1:
        joined = task_names[0]
    else:
        joined = ", ".join(task_names[:-1]) + " and " + task_names[-1]
    count = len(items)
    return f"You have {count} {label} task{'s' if count != 1 else ''}: {joined}."


def complete_todo(query: str) -> str:
    """Mark a task matching *query* as done."""
    query = query.strip().lower()
    todos = _load()

    for t in todos:
        if not t["done"] and query in t["task"].lower():
            t["done"] = True
            t["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            _save(todos)
            return f"Marked as done: '{t['task']}'. Great job!"

    return f"I couldn't find an open task matching '{query}'."


def delete_todo(query: str) -> str:
    """Remove a task matching *query* (done or open)."""
    query = query.strip().lower()
    todos = _load()

    original_count = len(todos)
    remaining = [t for t in todos if query not in t["task"].lower()]

    if len(remaining) == original_count:
        return f"I couldn't find a task matching '{query}' to remove."

    _save(remaining)
    removed = original_count - len(remaining)
    return f"Removed {removed} task{'s' if removed != 1 else ''} from your list."


def pending_count() -> int:
    """Return number of open (not done) tasks — useful for daily briefing."""
    return sum(1 for t in _load() if not t["done"])
