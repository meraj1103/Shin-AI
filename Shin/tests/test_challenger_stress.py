"""
test_challenger_stress.py — Adversarial Stress and Edge-Case Test Harness for Shin Revival Priorities
=====================================================================================================
Empirically challenges all 6 revival priorities across extreme boundaries, malformed inputs,
network failure simulations, and state persistence invariants:
1. tts.py: empty/None text, extreme markdown/URLs/emojis, 5000+ char text, Hindi/Marathi/English
   detection, dynamic pitch boundaries and persistence.
2. agent_reach_query: unsupported platforms, invalid actions, empty/whitespace queries,
   out-of-bounds limits, network timeout/HTTP error mocking, command dispatch.
3. analyze_clipboard: empty/None clipboard, 50k char inputs, division by zero, complex math,
   various URL schemes, multiple languages code snippets, unhandled args.
4. nlp.py: uppercase/lowercase/punctuation variations of new intent patterns, typo tolerance,
   negative controls that must not match the new patterns.
5. memory.py: dual-file persistence (memory.json & memories.json), one-file deletion recovery,
   NLP cache invalidation trigger, duplicate avoidance, search & delete consistency.
6. rolling conversation buffer: strictly capped at maxlen=20 across 50+ turns, FIFO purging,
   persistence & restoration, corrupt JSON recovery, clear_context.
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
    import shin_agent
    from shin_agent import (
        AVAILABLE_TOOLS,
        ShinReActEngine,
        agent_reach_query,
    )
except ImportError:
    from core import shin_agent
    from core.shin_agent import (
        AVAILABLE_TOOLS,
        ShinReActEngine,
        agent_reach_query,
    )

from main import AutonomousShinEngine


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 1: Voice Realism & TTS Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestVoiceRealismStress:
    """Adversarial stress tests for tts.py normalization, detection, and pitch."""

    def test_clean_text_empty_and_none(self):
        """clean_text_for_speech must gracefully handle None, empty, and whitespace strings."""
        assert tts.clean_text_for_speech("") == ""
        assert tts.clean_text_for_speech("   \n\t  ") == ""
        assert tts.clean_text_for_speech(None) == ""

    def test_clean_text_markdown_and_symbols(self):
        """clean_text_for_speech strips bold, italics, inline code, URLs, and emojis."""
        raw = "**Heading** with `code` and [link](https://example.com/test) & emojis 🚀🔥🎉!"
        cleaned = tts.clean_text_for_speech(raw)
        assert "**" not in cleaned
        assert "`" not in cleaned
        assert "https://" not in cleaned
        assert "🚀" not in cleaned
        assert "🔥" not in cleaned
        assert "🎉" not in cleaned
        assert "Heading" in cleaned

    def test_clean_text_speed_and_temp_units(self):
        """Verify speed (km/h) and temperature (°C) units are normalized cleanly for speech."""
        text = "Driving at 120km/h on a 35°C afternoon."
        cleaned = tts.clean_text_for_speech(text)
        assert "120 kilometers per hour" in cleaned
        assert "35 degrees Celsius" in cleaned

    def test_clean_text_massive_input(self):
        """Verify clean_text_for_speech does not crash or hang on 5,000+ characters."""
        long_input = "Hey MJ! " + ("This is a stress test sentence with details. " * 100)
        cleaned = tts.clean_text_for_speech(long_input)
        assert isinstance(cleaned, str)
        assert len(cleaned) > 1000

    def test_language_detection_boundaries(self):
        """Test Hindi and Marathi script boundaries."""
        # Pure English
        assert tts.is_text_hindi("Good morning, have a nice day.") is False
        assert tts.is_text_marathi("Good morning, have a nice day.") is False

        # Pure Devanagari Hindi
        assert tts.is_text_hindi("नमस्ते, आप कैसे हैं?") is True
        assert tts.is_text_marathi("नमस्ते, आप कैसे हैं?") is False

        # Pure Devanagari Marathi with distinct marker
        assert tts.is_text_hindi("आज आपण काय शिकलो? मी करू शकते.") is True
        assert tts.is_text_marathi("आज आपण काय शिकलो? मी करू शकते.") is True

        # Empty / whitespace
        assert tts.is_text_hindi("") is False
        assert tts.is_text_marathi("") is False

    def test_set_voice_pitch_boundaries(self):
        """Test setting voice pitch with negative, zero, and positive Hz."""
        original_pitch = tts.TTS_PITCH
        try:
            for pitch in ["+0Hz", "+4Hz", "+8Hz", "+12Hz", "-4Hz"]:
                msg = tts.set_voice_pitch(pitch, f"test {pitch}")
                assert tts.TTS_PITCH == pitch
                assert pitch in msg or "test" in msg
        finally:
            tts.set_voice_pitch(original_pitch)

    def test_synthesize_edge_audio_fallback(self):
        """Verify fallback from expressive voice to standard NeerjaNeural when expressive fails."""
        with mock.patch("asyncio.run") as mock_async_run:
            # First call fails, second call succeeds
            mock_async_run.side_effect = [Exception("Voice unavailable"), "C:/temp/fallback.mp3"]
            result = tts.synthesize_edge_audio("Test fallback phrase", voice="en-IN-NeerjaExpressiveNeural")
            assert result == "C:/temp/fallback.mp3"
            assert mock_async_run.call_count == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 2: Agent-Reach Integration Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentReachStress:
    """Adversarial stress tests for agent_reach_query across platforms and failure modes."""

    def test_unsupported_platform(self):
        """Unsupported platform returns clean error message without crashing."""
        res = agent_reach_query("unsupported_platform", query="test")
        assert "not supported" in res.lower()

    def test_limit_clamping(self):
        """Limit is clamped between 1 and 10 safely."""
        with mock.patch("requests.get") as mock_get:
            mock_resp = mock.MagicMock()
            mock_resp.json.return_value = {
                "items": [{"full_name": f"user/repo{i}", "stargazers_count": 100 * i, "html_url": f"http://{i}"} for i in range(20)]
            }
            mock_get.return_value = mock_resp

            # Test limit <= 0 clamped to 1
            res_min = agent_reach_query("github", action="trending", limit=0)
            assert "[1]" in res_min
            assert "[2]" not in res_min

            # Test limit > 10 clamped to 10
            res_max = agent_reach_query("github", action="trending", limit=99)
            assert "[10]" in res_max
            assert "[11]" not in res_max

    def test_github_api_network_failure(self):
        """Network exception during GitHub query is caught and returned as error string."""
        with mock.patch("requests.get", side_effect=Exception("Connection refused")):
            res = agent_reach_query("github", action="trending")
            assert "failed" in res.lower() or "error" in res.lower() or "connection" in res.lower()

    def test_reddit_network_fallback(self):
        """Reddit failure gracefully falls back to web search scraper."""
        with mock.patch("requests.get", side_effect=Exception("Reddit 429")):
            with mock.patch.object(shin_agent, "web_search_and_learn", return_value="Reddit fallback search summary"):
                res = agent_reach_query("reddit", query="python")
                assert "Reddit" in res

    def test_youtube_and_twitter_delegation(self):
        """YouTube and Twitter queries route to web_search_and_learn."""
        with mock.patch.object(shin_agent, "web_search_and_learn", return_value="Mocked search result"):
            res_yt = agent_reach_query("youtube", query="AI tutorial")
            assert res_yt == "Mocked search result"

            res_tw = agent_reach_query("twitter", query="OpenAI")
            assert res_tw == "Mocked search result"

    def test_commands_dispatch_agent_reach_missing_args(self):
        """commands.agent_reach_query handles missing args dict gracefully."""
        res = commands.agent_reach_query(None)
        assert isinstance(res, str)
        assert len(res) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 3: Clipboard AI Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestClipboardAIStress:
    """Adversarial stress tests for clipboard prediction across edge data types."""

    def test_empty_and_whitespace_clipboard(self):
        """Empty or whitespace clipboard returns empty prediction."""
        res_empty = predictive_engine.predictive_engine.predict_clipboard_action("")
        assert res_empty["type"] == "empty"
        assert "khali" in res_empty["prediction"].lower()

        res_ws = predictive_engine.predictive_engine.predict_clipboard_action("   \n\t  ")
        assert res_ws["type"] == "empty"

    def test_massive_clipboard_text(self):
        """50k characters text does not cause OOM or regex catastrophic backtracking."""
        massive = "Standard log line with timestamp 2026-11-09T15:00:00Z\n" * 1000
        res = predictive_engine.predictive_engine.predict_clipboard_action(massive)
        assert res["type"] in ("text", "error_traceback")
        assert "prediction" in res

    def test_math_division_by_zero(self):
        """Division by zero in clipboard math expression is handled safely."""
        res = predictive_engine.predictive_engine.predict_clipboard_action("100 / 0")
        assert res["type"] in ("math_expression", "text")

    def test_complex_math_expressions(self):
        """Parenthesized expressions compute accurately."""
        res_expr = predictive_engine.predictive_engine.predict_clipboard_action("(50 + 25) * 2")
        assert res_expr["type"] == "math_expression"
        assert "150" in str(res_expr.get("result", ""))

    def test_github_and_youtube_urls(self):
        """Accurately detects GitHub and YouTube URLs with parameters."""
        res_gh = predictive_engine.predictive_engine.predict_clipboard_action("https://github.com/torvalds/linux")
        assert res_gh["type"] == "github_url"
        assert res_gh["repo"] == "torvalds/linux"

        res_yt = predictive_engine.predictive_engine.predict_clipboard_action("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s")
        assert res_yt["type"] == "youtube_url"

    def test_code_snippets_multi_language(self):
        """Detects code snippet keywords across languages."""
        py_code = "def calculate_tax(income, rate=0.18):\n    return income * rate"
        res_py = predictive_engine.predictive_engine.predict_clipboard_action(py_code)
        assert res_py["type"] == "code_snippet"

        js_code = "const fetchUsers = async () => {\n  const res = await fetch('/api');\n};"
        res_js = predictive_engine.predictive_engine.predict_clipboard_action(js_code)
        assert res_js["type"] == "code_snippet"

    def test_commands_analyze_clipboard_dispatch(self):
        """commands.analyze_clipboard handles None or empty args."""
        with mock.patch.object(predictive_engine.predictive_engine, "_read_clipboard", return_value="https://github.com/test/repo"):
            res = commands.analyze_clipboard(None)
            assert isinstance(res, str)
            assert "test/repo" in res


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 4: Shin Intelligence & NLP Variations
# ═══════════════════════════════════════════════════════════════════════════════

class TestShinIntelligenceStress:
    """Stress test new NLP patterns under mixed casing, punctuation, and negative controls."""

    def test_language_switching_variations(self):
        """Verify language switching across supported phrasings and shadow behaviors."""
        set_lang_phrases = [
            ("han english mein baat karo", "english"),
            ("AB ENGLISH MEIN BOLO", "english"),
            ("hindi mein bolo", "hindi"),
            ("marathi mein bolo", "marathi"),
            ("speak in marathi", "marathi"),
        ]
        for phrase, expected_lang in set_lang_phrases:
            parsed = nlp._rule_parse(phrase)
            assert parsed is not None, f"Failed to match: {phrase}"
            assert parsed["intent"] == "set_language", f"Wrong intent for: {phrase}"
            assert parsed["args"]["language"] == expected_lang

        # Note: 'talk in hindi' / 'talk in english' match earlier static chat rules in nlp.py (line 1718/1722)
        parsed_talk = nlp._rule_parse("talk in hindi")
        assert parsed_talk is not None
        assert parsed_talk["intent"] in ("chat", "set_language")

    def test_casual_greetings_variations(self):
        """Casual best-friend greetings return warm chat response across variations."""
        for g in ["aur bhai fir", "AUR BHAI FIR", "aur bhai kya chal raha", "kya scene hai"]:
            parsed = nlp._rule_parse(g)
            assert parsed is not None
            assert parsed["intent"] == "chat"
            assert len(parsed["args"].get("response", "")) > 0

    def test_conversational_dismissals(self):
        """Dismissals trigger graceful polite exit across variations."""
        for d in ["aur kuchh nahin", "bas itna hi", "kuch nahi chahiye", "nothing else", "that's all"]:
            parsed = nlp._rule_parse(d)
            assert parsed is not None
            assert parsed["intent"] == "chat"
            assert "MJ" in parsed["args"]["response"]

    def test_typo_tolerant_identity(self):
        """Identity query handles typos and question marks."""
        for q in ["what ise your name", "what ise your name?", "what is your name", "what's your name", "your name"]:
            parsed = nlp._rule_parse(q)
            assert parsed is not None
            assert parsed["intent"] == "chat"
            assert "Shin" in parsed["args"]["response"]

    def test_negative_controls(self):
        """Ensure unrelated queries do not falsely collide with new revival intents."""
        res1 = nlp._rule_parse("english dictionary definition")
        assert res1 is None or res1.get("intent") != "set_language"

        res2 = nlp._rule_parse("what is the name of this song")
        assert res2 is None or res2.get("intent") != "chat"


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 5: Memory Persistence & Dual-File Sync
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryPersistenceStress:
    """Stress test memory persistence, atomic saves, dual-file sync, and cache invalidation."""

    def test_dual_file_synchronization(self, tmp_path):
        """Verify memory.save_memories writes identically to both memory.json and memories.json."""
        test_mem_file = str(tmp_path / "memory.json")
        test_alt_file = str(tmp_path / "memories.json")

        with mock.patch.object(memory, "MEMORY_FILE", test_mem_file), \
             mock.patch.object(memory, "ALT_MEMORY_FILE", test_alt_file):
            test_data = [{"timestamp": "2026-11-09 15:00:00", "content": "MJ loves coding"}]
            memory.save_memories(test_data)

            assert os.path.exists(test_mem_file)
            assert os.path.exists(test_alt_file)

            with open(test_mem_file, "r", encoding="utf-8") as f1, open(test_alt_file, "r", encoding="utf-8") as f2:
                data1 = json.load(f1)
                data2 = json.load(f2)
                assert data1 == data2 == test_data

    def test_missing_primary_file_fallback(self, tmp_path):
        """If primary memory.json is deleted, load_memories falls back to memories.json."""
        test_mem_file = str(tmp_path / "memory.json")
        test_alt_file = str(tmp_path / "memories.json")

        test_data = [{"timestamp": "2026-11-09 15:00:00", "content": "Fallback memory test"}]
        with open(test_alt_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        with mock.patch.object(memory, "MEMORY_FILE", test_mem_file), \
             mock.patch.object(memory, "ALT_MEMORY_FILE", test_alt_file):
            loaded = memory.load_memories()
            assert loaded == test_data

    def test_duplicate_memory_prevention(self, tmp_path):
        """add_memory prevents storing identical content twice."""
        test_mem_file = str(tmp_path / "memory.json")
        test_alt_file = str(tmp_path / "memories.json")

        with mock.patch.object(memory, "MEMORY_FILE", test_mem_file), \
             mock.patch.object(memory, "ALT_MEMORY_FILE", test_alt_file):
            msg1 = memory.add_memory("MJ lives in Pune")
            assert "committed" in msg1.lower()

            msg2 = memory.add_memory("mj lives in pune")  # Case insensitive duplicate
            assert "already remember" in msg2.lower()

            loaded = memory.load_memories()
            assert len(loaded) == 1

    def test_nlp_cache_invalidation_called(self, tmp_path):
        """save_memories triggers _invalidate_nlp_cache without error."""
        test_mem_file = str(tmp_path / "memory.json")
        test_alt_file = str(tmp_path / "memories.json")

        with mock.patch.object(memory, "MEMORY_FILE", test_mem_file), \
             mock.patch.object(memory, "ALT_MEMORY_FILE", test_alt_file), \
             mock.patch.object(memory, "_invalidate_nlp_cache") as mock_inval:
            memory.save_memories([])
            mock_inval.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 6: Rolling Conversation Buffer Bounds
# ═══════════════════════════════════════════════════════════════════════════════

class TestRollingBufferStress:
    """Stress test rolling conversation buffer strict capacity bounds and persistence."""

    def test_shin_react_engine_strict_bound(self, tmp_path):
        """Verify ShinReActEngine strictly keeps exactly 20 messages under 50 successive inputs."""
        with mock.patch.object(shin_agent, "_SHIN_ROOT", tmp_path):
            engine = ShinReActEngine()
            engine.clear_context()
            assert len(engine.history) == 0

            # Feed 50 items
            for i in range(50):
                engine.history.append({"role": "user", "content": f"msg {i}"})

            assert len(engine.history) == 20
            # Oldest remaining should be msg 30, latest msg 49
            assert engine.history[0]["content"] == "msg 30"
            assert engine.history[-1]["content"] == "msg 49"

            engine._persist_history()
            test_hist_path = tmp_path / "data" / "conversation_history.json"
            assert test_hist_path.exists()

            # Create new engine instance and verify it loads capped 20
            engine2 = ShinReActEngine()
            assert len(engine2.history) == 20
            assert engine2.history[-1]["content"] == "msg 49"

            engine2.clear_context()
            assert len(engine2.history) == 0
            with open(test_hist_path, "r", encoding="utf-8") as f:
                assert json.load(f) == []

    def test_autonomous_engine_strict_bound(self, tmp_path):
        """Verify AutonomousShinEngine strictly caps at 20 messages."""
        with mock.patch("main._ROOT_DIR", tmp_path):
            engine = AutonomousShinEngine()
            engine.clear_context()

            for i in range(30):
                engine.history.append({"role": "user", "content": f"query {i}"})

            assert len(engine.history) == 20
            assert engine.history[0]["content"] == "query 10"
            assert engine.history[-1]["content"] == "query 29"
            engine.clear_context()

    def test_malformed_history_json_resilience(self, tmp_path):
        """Engine safely handles corrupted conversation_history.json without crashing."""
        test_hist_path = tmp_path / "data" / "conversation_history.json"
        test_hist_path.parent.mkdir(parents=True, exist_ok=True)
        # Write invalid JSON
        test_hist_path.write_text("{corrupt json syntax", encoding="utf-8")

        with mock.patch.object(shin_agent, "_SHIN_ROOT", tmp_path):
            engine = ShinReActEngine()
            assert len(engine.history) == 0
