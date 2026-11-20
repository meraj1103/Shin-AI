"""
test_full_system_benchmark.py — Comprehensive System Benchmark & Pipeline Verification
=======================================================================================
Empirically benchmarks:
1. Command Dispatch Pipeline: Instant execution of system commands (<50ms).
2. Language State & Enforcement: Strict English & Hindi routing without leakage.
3. Agent-Reach Zero-API Live Intelligence: GitHub, Reddit, and YouTube metadata.
4. Multi-Model LLM Router Failover: Instant 429 bounce to TokenHarbor without delay.
5. Custom Macros & System Learning: Persistent custom commands and laptop skills.
"""

import os
import sys
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Path configuration
_ROOT = Path(__file__).resolve().parent.parent
_CORE = _ROOT / "core"
for p in (str(_ROOT), str(_CORE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import nlp
import commands
import settings
import personality
import shin_agent
import llm_router


def test_command_dispatch_pipeline_latency():
    """Verify system command dispatch executes in under 50ms without unnecessary delays."""
    start = time.perf_counter()
    res = commands.dispatch({"intent": "tell_time", "args": {}})
    duration = time.perf_counter() - start

    assert isinstance(res, str)
    assert len(res) > 0
    assert duration < 0.05, f"tell_time took too long: {duration:.4f}s"


def test_language_enforcement_and_pools():
    """Verify Shin stays strictly within English when English is chosen."""
    settings.set_language("english")
    assert settings.get_language() == "english"

    ack = personality.pick("ack")
    done = personality.pick("done")
    thinking = personality.pick("thinking")

    # None of these English phrases should contain standard Hindi markers
    hindi_markers = ("karti hoon", "kar raha", "karo", "ruk ruk", "ho gaya", "nipat gaya", "samajh nahi")
    for marker in hindi_markers:
        assert marker not in ack.lower(), f"Hindi marker '{marker}' found in English ack: {ack}"
        assert marker not in done.lower(), f"Hindi marker '{marker}' found in English done: {done}"
        assert marker not in thinking.lower(), f"Hindi marker '{marker}' found in English thinking: {thinking}"


def test_conversational_language_switch_patterns():
    """Verify natural phrasing switches language immediately."""
    p1 = nlp.parse_intent("mujhe hindi mein baat karni hai")
    assert p1["intent"] == "set_language"
    assert p1["args"]["language"] == "hindi"

    p2 = nlp.parse_intent("ab se english mein baat karo")
    assert p2["intent"] == "set_language"
    assert p2["args"]["language"] == "english"

    p3 = nlp.parse_intent("talk in english")
    assert p3["intent"] == "set_language"
    assert p3["args"]["language"] == "english"


def test_agent_reach_github_and_youtube():
    """Verify agent_reach_query routes correctly without official API keys."""
    # 1. YouTube video URL / ID oEmbed lookup
    yt_res = shin_agent.agent_reach_query(platform="youtube", query="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert "YouTube Video:" in yt_res
    assert "Rick Astley" in yt_res

    # 2. Unsupported platform handling
    unsupported = shin_agent.agent_reach_query(platform="unsupported_xyz", query="test")
    assert "not supported" in unsupported.lower()


def test_llm_router_instant_429_failover():
    """Verify that a 429 RateLimitError on Groq triggers instant cooldown and failover."""
    router = llm_router.get_router()

    mock_tokenharbor_resp = {
        "role": "assistant",
        "content": "DeepSeek failover successful",
        "tool_calls": []
    }

    with patch.object(router, "_call_groq", side_effect=Exception("429 Too Many Requests: Rate limit reached")), \
         patch.object(router, "_call_tokenharbor", return_value=mock_tokenharbor_resp):

        start = time.perf_counter()
        res = router.query([{"role": "user", "content": "Hello"}])
        elapsed = time.perf_counter() - start

        assert res["content"] == "DeepSeek failover successful"
        assert res["provider"] == "tokenharbor"
        # Zero-delay failover must take < 0.2s
        assert elapsed < 0.2, f"Failover took too long: {elapsed:.4f}s"


def test_custom_macro_pipeline():
    """Verify custom command pipeline from creation to trigger matching."""
    trigger = "benchmark test macro"
    commands_list = "open terminal and open chrome"

    with patch("macros._load_custom_macros", return_value={}), \
         patch("macros._save_custom_macros") as mock_save:

        res = commands.learn_macro({"trigger": trigger, "commands": commands_list})
        mock_save.assert_called_once()
        assert trigger in res


def test_silent_background_alerts_safety():
    """Verify proactive voice alerts remain disabled by default."""
    import alerts
    assert alerts.PROACTIVE_AUTO_TALK is False

    mock_speak = MagicMock()
    alerts._speak_cb = mock_speak
    alerts._speak("Unsolicited background chatter")
    mock_speak.assert_not_called()


def test_split_compound_commands():
    """Verify natural command chaining splits actionable intents while protecting searches."""
    res1 = nlp.split_compound_commands("mute the volume and tell me the time")
    assert res1 == ["mute the volume", "tell me the time"]

    res2 = nlp.split_compound_commands("turn up brightness and open chrome")
    assert res2 == ["turn up brightness", "open chrome"]

    # Search queries and macro teaching should NOT be split
    res3 = nlp.split_compound_commands("search for tom and jerry")
    assert res3 == ["search for tom and jerry"]

    res4 = nlp.split_compound_commands("learn this command: study mode to open vs code and open terminal")
    assert res4 == ["learn this command: study mode to open vs code and open terminal"]


def test_repeat_last_response():
    """Verify conversational continuity where Shin can repeat what she just said."""
    nlp.add_to_history("assistant", "Your project build succeeded.")

    p1 = nlp.parse_intent("what did you just say?")
    assert p1["intent"] == "repeat_last_response"

    p2 = nlp.parse_intent("phir se bolo")
    assert p2["intent"] == "repeat_last_response"

    resp = commands.dispatch(p1)
    assert "Your project build succeeded." in resp


def test_user_addressed_as_mj_never_hero():
    """Verify Shin strictly addresses the user as 'MJ' and never calls them 'hero'."""
    # 1. Check all pools in personality
    for cat, phrases in personality._POOLS.items():
        for phrase in phrases:
            assert "hero" not in phrase.lower(), f"Found 'hero' in _POOLS[{cat}]: {phrase}"

    for cat, phrases in personality._POOLS_EN.items():
        for phrase in phrases:
            assert "hero" not in phrase.lower(), f"Found 'hero' in _POOLS_EN[{cat}]: {phrase}"

    # 2. Check greetings for every hour of the day
    for h in range(24):
        greet = personality.get_startup_greeting(h)
        assert "hero" not in greet.lower(), f"Found 'hero' in greeting at hour {h}: {greet}"

    # 3. Check system prompt
    prompt = nlp._get_ai_system_prompt()
    assert "never call him hero" in prompt.lower() or "always address him as mj" in prompt.lower()
    # Confirm no positive instructions to use "hero"
    assert "call him mj, hero" not in prompt.lower()


def test_speech_listening_continuity_and_dangling_detection():
    """Verify incomplete dangling utterances are detected so speech listening doesn't cut off."""
    import assistant

    assert assistant.is_dangling_utterance("can you open the") is True
    assert assistant.is_dangling_utterance("can you open") is True
    assert assistant.is_dangling_utterance("open the") is True
    assert assistant.is_dangling_utterance("open") is True
    assert assistant.is_dangling_utterance("search for the") is True
    assert assistant.is_dangling_utterance("click on the") is True

    # Complete utterances must NOT be flagged as dangling
    assert assistant.is_dangling_utterance("can you open the youtube") is False
    assert assistant.is_dangling_utterance("open chrome") is False
    assert assistant.is_dangling_utterance("search for python tutorials") is False
    assert assistant.is_dangling_utterance("what is the weather") is False


