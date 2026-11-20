"""Unit tests for Timemap and Heartbeat Scheduler."""

import os
import tempfile
import pytest
from Shin.core.timemap import TimemapEntry, TimemapManager, HeartbeatScheduler


@pytest.fixture
def temp_timemap_file():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    if os.path.exists(path):
        os.remove(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_timemap_entry_serialization():
    entry = TimemapEntry("14:30", "Test action", repeat="daily")
    d = entry.to_dict()
    assert d["time"] == "14:30"
    assert d["action"] == "Test action"
    assert d["repeat"] == "daily"
    assert d["status"] == "pending"

    restored = TimemapEntry.from_dict(d)
    assert restored.id == entry.id
    assert restored.time == "14:30"
    assert restored.repeat == "daily"


def test_timemap_add_and_validation(temp_timemap_file):
    tm = TimemapManager(filepath=temp_timemap_file)
    tm.clear_entries()

    # Valid entry
    e1 = tm.add_entry("15:45", "Drink green tea", repeat="once")
    assert e1 is not None
    assert e1.time == "15:45"
    assert len(tm.entries) == 1

    # Invalid time formats
    assert tm.add_entry("invalid", "test") is None
    assert tm.add_entry("25:00", "test") is None
    assert tm.add_entry("12:60", "test") is None


def test_timemap_due_and_trigger(temp_timemap_file):
    tm = TimemapManager(filepath=temp_timemap_file)
    tm.clear_entries()

    e = tm.add_entry("10:00", "Stand up and walk", repeat="once")
    assert e is not None

    # Time before entry
    due_before = tm.get_due_entries(current_hhmm="09:59")
    assert len(due_before) == 0

    # Time at/after entry
    due_after = tm.get_due_entries(current_hhmm="10:00")
    assert len(due_after) == 1
    assert due_after[0].id == e.id

    # Mark triggered
    tm.mark_triggered(e.id)
    assert len(tm.get_due_entries(current_hhmm="10:00")) == 0


def test_heartbeat_scheduler_tick(temp_timemap_file):
    tm = TimemapManager(filepath=temp_timemap_file)
    tm.clear_entries()

    triggered = []

    def on_trigger(entry):
        triggered.append(entry.action)

    scheduler = HeartbeatScheduler(timemap_manager=tm, on_trigger=on_trigger, interval_seconds=1)
    tm.add_entry("00:00", "Midnight check-in", repeat="daily")

    # Tick once manually
    due = scheduler.tick_once()
    assert len(due) == 1
    assert "Midnight check-in" in triggered
