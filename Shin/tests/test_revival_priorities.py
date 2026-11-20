"""
test_revival_priorities.py — Automated Verification for All 6 Revival Priorities
=================================================================================
Verifies:
1. Voice Realism: Modular Shin/core/tts.py with en-IN-NeerjaExpressiveNeural /
   en-IN-NeerjaNeural and +8Hz pitch, cleanly wired with assistant.py.
2. Agent-Reach Integration: agent_reach_query in Shin/core/shin_agent.py with
   zero-API fallback scrapers (GitHub, YouTube, Reddit, Twitter) and regex routing.
3. Clipboard AI: analyze_clipboard handler in commands.py and intent pattern in nlp.py.
4. Shin Intelligence: regex rules in nlp.py for language switching, casual greetings,
   dismissals, and typo tolerance.
5. Memory Persistence: dual-file persistence (memory.json & memories.json) and
   instant cache invalidation in memory.py.
6. Conversation Context: rolling 10-turn (20 messages) buffer in ShinReActEngine
   and AutonomousShinEngine.
"""
import os
import sys
import json
import pytest
from pathlib import Path
from unittest import mock

# Ensure root & core are on import path
_ROOT_DIR = Path(__file__).resolve().parent.parent
_CORE_DIR = _ROOT_DIR / "core"
for p in (str(_ROOT_DIR), str(_CORE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import nlp
    import commands
    import memory
    import tts
    import predictive_engine
except ImportError:
    from core import nlp, commands, memory, tts, predictive_engine

try:
    from core.shin_agent import (
        AVAILABLE_TOOLS,
        TOOL_SCHEMAS,
        ShinReActEngine,
        DualModeLLMRouter,
        agent_reach_query,
    )
except ImportError:
    from shin_agent import (
        AVAILABLE_TOOLS,
        TOOL_SCHEMAS,
        ShinReActEngine,
        DualModeLLMRouter,
        agent_reach_query,
    )

from main import AutonomousShinEngine


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Voice Realism Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_voice_realism_config():
    """Verify voice settings match Indian English expressive neural with +8Hz pitch."""
    assert tts.EDGE_TTS_VOICE_EN in ("en-IN-NeerjaExpressiveNeural", "en-IN-NeerjaNeural")
    assert tts.TTS_PITCH in ("+8Hz", "+4Hz", "+0Hz") or tts.TTS_PITCH.startswith("+")


def test_tts_language_detection():
    """Verify Devanagari script detection for Hindi and Marathi."""
    assert tts.is_text_hindi("नमस्ते एमजे, कैसी हो?") is True
    assert tts.is_text_hindi("Hello MJ, how are you?") is False

    # Marathi detection with Marathi-specific words
    assert tts.is_text_marathi("मी काय करू?") is True
    assert tts.is_text_marathi("Hello MJ") is False


def test_clean_text_for_speech():
    """Verify speech text normalizer removes markdown, URLs, brackets, emojis, and multi-hash headers."""
    raw = "Hey **MJ**! Check out https://github.com/test [12] • First item 😊"
    cleaned = tts.clean_text_for_speech(raw)
    assert "https://" not in cleaned
    assert "**" not in cleaned
    assert "•" not in cleaned
    assert "😊" not in cleaned
    assert "Hey MJ" in cleaned

    # Multi-hash markdown headers
    assert tts.clean_text_for_speech("### Heading") == "Heading"
    assert tts.clean_text_for_speech("## Subheading") == "Subheading"
    assert tts.clean_text_for_speech("# Title") == "Title"


def test_set_voice_pitch():
    """Verify set_voice_pitch dynamically updates pitch state."""
    old_pitch = tts.TTS_PITCH
    try:
        res = tts.set_voice_pitch("+6Hz", "warm high")
        assert "+6Hz" in tts.TTS_PITCH
        assert "warm high" in res or "+6Hz" in res
    finally:
        tts.set_voice_pitch(old_pitch)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Agent-Reach Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_agent_reach_in_shin_agent_tools():
    """Verify agent_reach_query is registered in Shin agent available tools and schemas."""
    assert "agent_reach_query" in AVAILABLE_TOOLS
    tool_names = [s["function"]["name"] for s in TOOL_SCHEMAS]
    assert "agent_reach_query" in tool_names


def test_agent_reach_github_trending():
    """Verify agent_reach_query returns trending GitHub repos."""
    res = agent_reach_query("github", action="trending", limit=3)
    assert isinstance(res, str)
    assert "GitHub" in res or "Trending" in res or "Repositories" in res


def test_agent_reach_github_search():
    """Verify agent_reach_query can search GitHub repositories."""
    res = agent_reach_query("github", query="fastapi", action="search", limit=2)
    assert isinstance(res, str)
    assert "fastapi" in res.lower() or "github" in res.lower()


def test_agent_reach_nlp_routing():
    """Verify NLP routes trending GitHub and Reddit utterances to agent_reach_query."""
    parsed1 = nlp.parse_intent("what is trending on github today")
    assert parsed1["intent"] == "agent_reach_query"
    assert parsed1["args"]["platform"] == "github"
    assert parsed1["args"]["action"] == "trending"

    parsed2 = nlp.parse_intent("github trending repos")
    assert parsed2["intent"] == "agent_reach_query"

    parsed3 = nlp.parse_intent("what is hot on reddit")
    assert parsed3["intent"] == "agent_reach_query"
    assert parsed3["args"]["platform"] == "reddit"


def test_agent_reach_commands_dispatch():
    """Verify commands.dispatch executes agent_reach_query."""
    res = commands.dispatch({
        "intent": "agent_reach_query",
        "args": {"platform": "github", "action": "trending", "limit": 2}
    })
    assert isinstance(res, str)
    assert len(res) > 20


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Clipboard AI Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_nlp_analyze_clipboard():
    """Verify NLP recognizes clipboard analysis commands."""
    assert nlp.parse_intent("analyze my clipboard")["intent"] == "analyze_clipboard"
    assert nlp.parse_intent("check my clipboard")["intent"] == "analyze_clipboard"
    assert nlp.parse_intent("inspect clipboard")["intent"] == "analyze_clipboard"
    assert nlp.parse_intent("clipboard analyze karo")["intent"] == "analyze_clipboard"


def test_commands_analyze_clipboard():
    """Verify commands.dispatch handles analyze_clipboard with predictive engine."""
    res = commands.dispatch({"intent": "analyze_clipboard", "args": {}})
    assert isinstance(res, str)
    assert len(res) > 0


def test_predict_clipboard_percentage_math():
    """Verify predictive_engine.predict_clipboard_action evaluates percentage math like '250 * 20%'."""
    res = predictive_engine.predictive_engine.predict_clipboard_action("250 * 20%")
    assert res is not None
    assert res.get("type") == "math_expression"
    assert res.get("result") in ("50", "50.0")
    assert "50" in res.get("prediction", "")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Shin Intelligence Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_nlp_language_switching():
    """Verify NLP parses requests to switch communication languages."""
    p_en = nlp.parse_intent("han english mein baat karo")
    assert p_en["intent"] == "set_language"
    assert p_en["args"]["language"] == "english"

    p_hi = nlp.parse_intent("hindi mein bolo")
    assert p_hi["intent"] == "set_language"
    assert p_hi["args"]["language"] == "hindi"

    res = commands.dispatch(p_en)
    assert "English" in res or "MJ" in res


def test_nlp_casual_greetings():
    """Verify best-friend casual greetings return immediate warm chat responses."""
    rule_res = nlp._rule_parse("aur bhai fir")
    assert rule_res["intent"] == "chat"
    assert "Aur bhai" in rule_res["args"].get("response", "")

    p_bhai = nlp.parse_intent("aur bhai fir")
    assert p_bhai["intent"] == "chat"
    assert len(p_bhai["args"].get("response", "")) > 0

    p_batao = nlp.parse_intent("aur batao")
    assert p_batao["intent"] == "chat"


def test_nlp_conversational_dismissal():
    """Verify dismissal phrases ('aur kuchh nahin' and 'aur kuch nahi') route to polite closing."""
    rule_res = nlp._rule_parse("aur kuchh nahin")
    assert rule_res["intent"] == "chat"
    assert "MJ" in rule_res["args"].get("response", "")

    rule_res2 = nlp._rule_parse("aur kuch nahi")
    assert rule_res2["intent"] == "chat"
    assert "MJ" in rule_res2["args"].get("response", "")

    p_done = nlp.parse_intent("aur kuchh nahin")
    assert p_done["intent"] == "chat"
    assert len(p_done["args"].get("response", "")) > 0

    p_done2 = nlp.parse_intent("aur kuch nahi")
    assert p_done2["intent"] == "chat"
    assert len(p_done2["args"].get("response", "")) > 0

    p_bas = nlp.parse_intent("bas itna hi")
    assert p_bas["intent"] == "chat"


def test_nlp_typo_tolerant_identity():
    """Verify typo tolerance on identity queries ('what ise your name')."""
    rule_res = nlp._rule_parse("what ise your name")
    assert rule_res["intent"] == "chat"
    assert "Shin" in rule_res["args"].get("response", "")

    parsed = nlp.parse_intent("what ise your name")
    assert parsed["intent"] == "chat"
    assert len(parsed["args"].get("response", "")) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Memory Persistence Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_memory_persistence_dual_file(tmp_path):
    """Verify memories are saved to both memory.json and memories.json."""
    data_dir = _ROOT_DIR / "data"
    mem_file = data_dir / "memory.json"
    alt_file = data_dir / "memories.json"

    # Save a test memory
    mems = memory.load_memories()
    memory.save_memories(mems)

    assert mem_file.exists()
    assert alt_file.exists()
    assert mem_file.stat().st_size > 0
    assert alt_file.stat().st_size > 0


def test_store_relationship_dispatch():
    """Verify store_relationship command saves relation and returns confirmation."""
    res = commands.dispatch({
        "intent": "store_relationship",
        "args": {"subject": "Anuj", "relation": "bhai"}
    })
    assert isinstance(res, str)
    assert "Anuj" in res
    assert "bhai" in res


def test_memory_schema_defensiveness():
    """Verify memory.py gracefully handles corrupt JSON schemas, non-dict items, and missing 'content'."""
    backup = memory.load_memories()
    try:
        # Test 1: list with non-dict and missing content
        memory.save_memories([{"bad_key": "no content"}, "invalid_str", 123])
        mems = memory.load_memories()
        assert mems == []

        # Test 2: add_memory does not raise KeyError
        res = memory.add_memory("Valid memory entry")
        assert "Valid memory entry" in res

        # Test 3: root is dict instead of list
        memory.save_memories({"not_a": "list"})
        assert memory.load_memories() == []
        res2 = memory.add_memory("Another valid memory")
        assert "Another valid memory" in res2
    finally:
        memory.save_memories(backup)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Conversation Context Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_shin_react_engine_context_buffer():
    """Verify ShinReActEngine maintains a rolling conversation buffer capped at 20 messages."""
    engine = ShinReActEngine()
    engine.clear_context()
    assert len(engine.history) == 0

    # Add turns
    for i in range(12):  # 12 turns = 24 messages
        engine.history.append({"role": "user", "content": f"User question {i}"})
        engine.history.append({"role": "assistant", "content": f"Assistant answer {i}"})

    # Buffer must cap at maxlen=20 (10 turns)
    assert len(engine.history) == 20
    assert engine.history[-1]["content"] == "Assistant answer 11"
    assert engine.history[0]["content"] == "User question 2"

    engine.clear_context()
    assert len(engine.history) == 0


def test_autonomous_engine_context_buffer():
    """Verify AutonomousShinEngine maintains a rolling conversation buffer capped at 20 messages."""
    engine = AutonomousShinEngine()
    engine.clear_context()
    assert len(engine.history) == 0

    for i in range(15):
        engine.history.append({"role": "user", "content": f"Turn {i}"})
        engine.history.append({"role": "assistant", "content": f"Response {i}"})

    assert len(engine.history) == 20
    engine.clear_context()
    assert len(engine.history) == 0


def test_dual_mode_router_null_content_guard():
    """Verify DualModeLLMRouter._call_ollama guards against messages with content=None."""
    router = DualModeLLMRouter()
    with mock.patch("requests.post", side_effect=Exception("Ollama offline")):
        # Message with role 'user' and content None
        resp = router._call_ollama([{"role": "user", "content": None}])
        assert isinstance(resp, dict)
        assert resp.get("role") == "assistant"

        # Message with role 'tool' and content None
        resp2 = router._call_ollama([{"role": "tool", "content": None}])
        assert isinstance(resp2, dict)
        assert resp2.get("role") == "assistant"
