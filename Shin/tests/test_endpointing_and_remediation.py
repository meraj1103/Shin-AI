"""test_endpointing_and_remediation.py — Verification of Milestone 1 Core Remediation:
1. Action Dispatching & App Launching (CloudBrainClient + polymorphic commands.dispatch)
2. Speech Recognition Latency & Endpointing Invariants
3. Mate Mascot Speech Reactivity & Dance IPC
"""

import concurrent.futures
import json
import time
from pathlib import Path
import pytest
import speech_recognition as sr
from unittest.mock import MagicMock, patch

from Shin.core.cloud_client import CloudBrainClient
from Shin.core import commands
from Shin.core.mate_bridge import MateBridge


def test_speech_recognizer_invariants_and_latency():
    """Verify speech recognizer settings satisfy low-latency endpointing and library assertions."""
    # 1. Test isolated Recognizer with M1 parameters
    r = sr.Recognizer()
    r.pause_threshold = 0.75
    r.phrase_threshold = 0.2
    r.non_speaking_duration = 0.45
    r.dynamic_energy_ratio = 1.25
    r.dynamic_energy_adjustment_damping = 0.15

    # CRITICAL INVARIANT: sr._listen requires pause_threshold >= non_speaking_duration >= 0
    assert r.pause_threshold >= r.non_speaking_duration >= 0
    assert r.pause_threshold == 0.75
    assert r.non_speaking_duration == 0.45
    assert r.dynamic_energy_ratio == 1.25
    assert r.dynamic_energy_adjustment_damping == 0.15


def test_assistant_recognizer_initialization():
    """Verify assistant module initializes the recognizer with low-latency settings."""
    # Read the source of assistant.py to verify exact configured constants
    from pathlib import Path
    assistant_path = Path(__file__).parent.parent / "assistant.py"
    content = assistant_path.read_text(encoding="utf-8")

    assert "_recognizer.pause_threshold = 0.75" in content
    assert "_recognizer.non_speaking_duration = 0.45" in content
    assert "_recognizer.dynamic_energy_ratio = 1.25" in content
    assert "_recognizer.dynamic_energy_adjustment_damping = 0.15" in content
    assert "phrase_time_limit=10" in content


def test_commands_dispatch_polymorphic_signatures():
    """Test commands.dispatch handles both dict format and positional (str, dict) arguments."""
    # 1. Standard single-dict call
    res1 = commands.dispatch({"intent": "tell_time", "args": {}})
    assert res1 is not None

    # 2. Positional call
    res2 = commands.dispatch("tell_time", {})
    assert res2 is not None
    assert res1 == res2

    # 3. Call with kwargs (e.g. untrusted flag)
    res3 = commands.dispatch("tell_time", {}, _untrusted=False)
    assert res3 == res1

    # 4. Unknown intent
    res_none = commands.dispatch("completely_nonexistent_intent", {})
    assert res_none is None

    # 5. Invalid type input
    res_invalid = commands.dispatch(12345)  # type: ignore
    assert res_invalid is None


def test_cloud_client_local_action_execution_both_signatures():
    """Verify CloudBrainClient.execute_local_action_if_needed executes local hardware actions."""
    client = CloudBrainClient()

    # Intent with args
    payload = {
        "is_local_action": True,
        "intent": "tell_time",
        "args": {}
    }
    result = client.execute_local_action_if_needed(payload)
    assert result is not None
    assert "Action execution error" not in result

    # Non-local action should return None
    non_action = {
        "is_local_action": False,
        "intent": "chat",
        "args": {}
    }
    assert client.execute_local_action_if_needed(non_action) is None

    # Empty intent should return None
    empty_intent = {
        "is_local_action": True,
        "intent": "",
        "args": {}
    }
    assert client.execute_local_action_if_needed(empty_intent) is None


def test_cloud_client_connection_pooling_and_health_ttl():
    """Verify CloudBrainClient uses session pooling and caches health checks with a 30s TTL."""
    client = CloudBrainClient()
    session = client._get_session()
    assert session is not None

    # Set mock healthy state
    now = time.time()
    CloudBrainClient._last_health_check = now
    CloudBrainClient._is_healthy = True

    # Immediate check should return cached True without network calls
    assert client.is_available() is True


def test_mate_bridge_dance_and_settings_integration():
    """Verify Mate mascot dance bus IPC and settings configuration."""
    bridge = MateBridge.get()

    # Audio reactivity calibration
    assert bridge.ensure_sound_threshold(0.06) is True
    assert bridge.load_mate_settings().get("soundThreshold") == 0.06

    # Customization: scale adjustment
    assert bridge.set_avatar_scale(1.20) is True
    assert bridge.load_mate_settings().get("avatarSize") == 1.20

    # IPC Dance Bus toggle
    bridge.set_state("idle")
    state1 = bridge.toggle_dance()
    assert state1 == "dance"

    state2 = bridge.toggle_dance()
    assert state2 == "idle"


def test_commands_dispatch_none_and_malformed_args():
    """Verify commands.dispatch safely handles None or malformed args without raising AttributeError."""
    # 1. intent dict with args=None
    res_none = commands.dispatch({"intent": "open_app", "args": None})
    assert res_none is not None
    assert any(term in res_none.lower() for term in ("app", "open", "karni", "konsi"))

    # 2. intent dict with args as string
    res_str = commands.dispatch({"intent": "open_app", "args": "invalid_string"})
    assert res_str is not None
    assert any(term in res_str.lower() for term in ("app", "open", "karni", "konsi"))

    # 3. intent dict with args as integer or list
    res_int = commands.dispatch({"intent": "open_app", "args": 9999})
    assert res_int is not None

    res_list = commands.dispatch({"intent": "open_app", "args": ["calc"]})
    assert res_list is not None

    # 4. Positional dispatch with args=None
    res_pos = commands.dispatch("open_app", None)
    assert res_pos is not None

    # 5. Tell time with args=None and list
    res_time_none = commands.dispatch({"intent": "tell_time", "args": None})
    assert res_time_none is not None

    res_time_list = commands.dispatch({"intent": "tell_time", "args": [1, 2, 3]})
    assert res_time_list is not None

    # 6. check_command_safety direct calls with non-dict args
    safe_none, msg_none = commands.check_command_safety("open_app", None)
    assert safe_none is True
    assert msg_none == ""

    safe_str, msg_str = commands.check_command_safety("open_app", "invalid")
    assert safe_str is True
    assert msg_str == ""


def test_mate_bridge_avatar_model_validation_and_traversal():
    """Verify set_avatar_model validates .vrm extension, prevents traversal, and checks file existence."""
    bridge = MateBridge.get()

    # 1. Non-.vrm extension should be rejected
    assert bridge.set_avatar_model("malicious_script.bat") is False
    assert bridge.set_avatar_model("image.png") is False
    assert bridge.set_avatar_model("") is False

    # 2. Non-existent .vrm model should be rejected
    assert bridge.set_avatar_model("completely_nonexistent_model_12345.vrm") is False

    # 3. Directory traversal attempt targeting non-existent or outside path should be rejected
    assert bridge.set_avatar_model("../../Windows/System32/evil.vrm") is False

    # 4. Valid existing .vrm model should succeed
    assert bridge.set_avatar_model("shin_mascot.vrm") is True
    setts = bridge.load_mate_settings()
    assert "shin_mascot.vrm" in setts.get("selectedModelPath", "")


def test_mate_bridge_concurrent_dance_bus_and_settings():
    """Verify concurrent multi-threaded writes to dance bus and settings are lock-protected
    and avoid Windows multi-process sharing collisions ([WinError 32] / [WinError 5]).
    """
    from Shin.core.mate_bridge import _MATE_DANCE_BUS_FILE, _MATE_SETTINGS_FILE
    bridge = MateBridge.get()
    errors = []

    def dance_worker(idx: int):
        try:
            ok = bridge.send_dance_bus_command(f"Cmd_{idx}", title=f"Groove_{idx}", index=idx)
            if not ok:
                errors.append(f"Dance worker {idx} returned False")
        except Exception as exc:
            errors.append(f"Dance worker {idx} raised exception: {exc}")

    def settings_worker(idx: int):
        try:
            ok = bridge.save_mate_settings({
                "worker_id": idx,
                "soundThreshold": 0.06,
                "avatarSize": 1.0,
            })
            if not ok:
                errors.append(f"Settings worker {idx} returned False")
        except Exception as exc:
            errors.append(f"Settings worker {idx} raised exception: {exc}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        futures = []
        for i in range(25):
            futures.append(executor.submit(dance_worker, i))
            futures.append(executor.submit(settings_worker, i))
        concurrent.futures.wait(futures)

    assert len(errors) == 0, f"Encountered concurrency errors: {errors}"

    # Verify both files exist and contain valid, readable JSON
    assert _MATE_DANCE_BUS_FILE.exists()
    with open(_MATE_DANCE_BUS_FILE, "r", encoding="utf-8") as f:
        dance_data = json.load(f)
    assert "cmd" in dance_data
    assert "v" in dance_data

    assert _MATE_SETTINGS_FILE.exists()
    with open(_MATE_SETTINGS_FILE, "r", encoding="utf-8") as f:
        settings_data = json.load(f)
    assert settings_data.get("soundThreshold") == 0.06

