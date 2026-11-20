import json
import time
import pytest
from pathlib import Path

from Shin.core.conversation_flow import ConversationFlowManager


def test_conversation_flow_defaults(tmp_path):
    cfg_file = tmp_path / "test_flow.json"
    flow = ConversationFlowManager(config_path=cfg_file)

    assert flow.is_enabled() is True
    assert flow.is_continuous_mode() is True
    assert flow.get_follow_up_timeout() == 6.0
    assert flow.is_barge_in_enabled() is True


def test_session_lifecycle(tmp_path):
    cfg_file = tmp_path / "test_flow.json"
    flow = ConversationFlowManager(config_path=cfg_file)

    assert flow.is_in_active_session() is False

    flow.start_session()
    assert flow.is_in_active_session() is True
    assert flow.in_conversation is True

    flow.record_turn("What is the weather?", "It is 29°C and sunny.")
    assert flow.turn_count == 1
    assert flow.is_in_active_session() is True

    flow.end_session(reason="test")
    assert flow.is_in_active_session() is False


def test_exit_phrases(tmp_path):
    cfg_file = tmp_path / "test_flow.json"
    flow = ConversationFlowManager(config_path=cfg_file)

    assert flow.should_exit_conversation("that's all") is True
    assert flow.should_exit_conversation("bye Shin") is True
    assert flow.should_exit_conversation("thank you") is True
    assert flow.should_exit_conversation("bas") is True
    assert flow.should_exit_conversation("What is quantum computing?") is False


def test_system_prompt_builder(tmp_path):
    cfg_file = tmp_path / "test_flow.json"
    flow = ConversationFlowManager(config_path=cfg_file)

    prompt = flow.build_system_prompt(memory_context="MJ loves 3D coding", language="Hinglish")
    assert "Shin" in prompt
    assert "MJ" in prompt
    assert "Hinglish" in prompt
    assert "MJ loves 3D coding" in prompt


def test_custom_persona_override(tmp_path):
    cfg_file = tmp_path / "test_flow.json"
    custom_cfg = {
        "enabled": True,
        "conversation_mode": "continuous",
        "follow_up_timeout_seconds": 10.0,
        "persona": {
            "assistant_name": "Shin-Prime",
            "user_name": "MJ",
            "system_prompt_template": "CUSTOM TEMPLATE FOR {assistant_name} and {user_name}!"
        }
    }
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(custom_cfg, f)

    flow = ConversationFlowManager(config_path=cfg_file)
    assert flow.get_follow_up_timeout() == 10.0
    prompt = flow.build_system_prompt()
    assert "CUSTOM TEMPLATE FOR Shin-Prime and MJ!" in prompt


def test_barge_in_signaling(tmp_path):
    cfg_file = tmp_path / "test_flow.json"
    flow = ConversationFlowManager(config_path=cfg_file)

    assert flow.is_interrupted() is False
    flow.request_barge_in()
    assert flow.is_interrupted() is True
    flow.reset_barge_in()
    assert flow.is_interrupted() is False
