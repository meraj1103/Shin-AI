import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from Shin.core.mate_bridge import MateBridge, find_mate_engine_exe, _STATE_FILE, _POS_FILE


def test_find_mate_engine_exe():
    exe = find_mate_engine_exe()
    assert exe is not None
    assert exe.name == "MateEngineX.exe"
    assert exe.exists()


def test_mate_bridge_initialization():
    bridge = MateBridge.get()
    assert bridge is not None
    assert bridge.current_state in ("idle", "thinking", "listening", "speaking", "dance")
    assert isinstance(bridge.pos_x, int)
    assert isinstance(bridge.pos_y, int)


def test_mate_bridge_state_persistence(tmp_path):
    bridge = MateBridge.get()
    test_state = "listening"
    bridge.set_state(test_state, extra={"user": "MJ"})

    assert bridge.current_state == "listening"
    assert _STATE_FILE.exists()

    with open(_STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["state"] == "listening"
    assert data["assistant"] == "Shin"
    assert data["user"] == "MJ"
    assert "timestamp" in data


def test_mate_bridge_dance_toggle():
    bridge = MateBridge.get()
    bridge.set_state("idle")
    assert bridge.current_state == "idle"

    res = bridge.toggle_dance()
    assert res == "dance"
    assert bridge.current_state == "dance"

    res = bridge.toggle_dance()
    assert res == "idle"
    assert bridge.current_state == "idle"


def test_mate_bridge_position_save_load(tmp_path):
    bridge = MateBridge.get()
    bridge.pos_x = 1200
    bridge.pos_y = 700

    # Test saving
    pos_data = {"x": 1200, "y": 700}
    with open(_POS_FILE, "w", encoding="utf-8") as f:
        json.dump(pos_data, f)

    loaded_x, loaded_y = bridge._load_saved_position()
    assert loaded_x == 1200
    assert loaded_y == 700


def test_mate_bridge_sync_prompt_and_speech(tmp_path):
    bridge = MateBridge.get()
    
    # Test speech sync
    bridge.sync_speech("Hello MJ! Testing speech sync.")
    assert bridge.current_state == "speaking"
    with open(_STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["state"] == "speaking"
    assert data["speech_text"] == "Hello MJ! Testing speech sync."

    # Test prompt sync
    assert bridge.sync_prompt("Test prompt for Shin and Mate Engine") is True
