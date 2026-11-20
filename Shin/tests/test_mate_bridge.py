import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from Shin.core.mate_bridge import (
    MateBridge,
    find_mate_engine_exe,
    _STATE_FILE,
    _POS_FILE,
    _MATE_DANCE_BUS_FILE,
    _MATE_SETTINGS_FILE,
    _CUSTOM_MODELS_DIR,
)
from Shin.core import commands


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


def test_mate_bridge_dance_bus_ipc():
    bridge = MateBridge.get()
    bridge.set_state("idle")

    # 1. Start dance -> PlayCurrentOrFirst
    ok = bridge.start_dance(title="Special Groove")
    assert ok is True
    assert _MATE_DANCE_BUS_FILE.exists()

    with open(_MATE_DANCE_BUS_FILE, "r", encoding="utf-8") as f:
        bus_cmd = json.load(f)

    assert bus_cmd["cmd"] == "PlayCurrentOrFirst"
    assert bus_cmd["title"] == "Special Groove"
    assert bus_cmd["v"] >= 1
    assert "atUtc" in bus_cmd
    assert "writeUtc" in bus_cmd
    first_v = bus_cmd["v"]

    # 2. Stop dance -> StopPlay
    ok = bridge.stop_dance()
    assert ok is True
    with open(_MATE_DANCE_BUS_FILE, "r", encoding="utf-8") as f:
        bus_cmd_stop = json.load(f)

    assert bus_cmd_stop["cmd"] == "StopPlay"
    assert bus_cmd_stop["v"] == first_v + 1


def test_mate_bridge_sound_threshold_calibration():
    bridge = MateBridge.get()
    # Calibrate sound threshold for clean WASAPI audio loopback reactivity
    ok = bridge.ensure_sound_threshold(0.06)
    assert ok is True

    settings = bridge.load_mate_settings()
    assert settings.get("soundThreshold") == 0.06


def test_mate_bridge_avatar_customization():
    bridge = MateBridge.get()

    # Scale adjustment
    assert bridge.set_avatar_scale(1.35) is True
    setts = bridge.load_mate_settings()
    assert setts.get("avatarSize") == 1.35

    # Scale clamping test
    bridge.set_avatar_scale(5.0)  # clamped to 3.0
    setts_clamped = bridge.load_mate_settings()
    assert setts_clamped.get("avatarSize") == 3.0

    # Model path assignment
    test_vrm = "shin_mascot.vrm"
    assert bridge.set_avatar_model(test_vrm) is True
    setts_model = bridge.load_mate_settings()
    assert test_vrm in setts_model.get("selectedModelPath")

    # Available models listing
    models = bridge.get_available_models()
    assert isinstance(models, list)


def test_commands_mate_handlers():
    # Dispatch mate_dance
    reply = commands.dispatch({"intent": "mate_dance", "args": {}})
    assert reply is not None
    assert "groove" in reply.lower() or "back to work" in reply.lower()

    # Dispatch set_avatar_scale
    reply_scale = commands.dispatch("set_avatar_scale", {"scale": 1.15})
    assert reply_scale is not None
    assert "1.15" in reply_scale

    # Dispatch set_avatar_model
    reply_model = commands.dispatch("set_avatar_model", {"path": "shin_v2.vrm"})
    assert reply_model is not None
    assert "shin_v2.vrm" in reply_model


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
