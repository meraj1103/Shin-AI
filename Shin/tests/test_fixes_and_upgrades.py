"""
test_fixes_and_upgrades.py — Unit tests verifying model switching, language enforcement,
Chrome profile launch, compound command parsing, and app launch truthfulness.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_SHIN_DIR = Path(__file__).resolve().parent.parent
if str(_SHIN_DIR) not in sys.path:
    sys.path.insert(0, str(_SHIN_DIR))
_CORE_DIR = _SHIN_DIR / "core"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from core import settings
from core import nlp
from core import commands
from core import personality
from core import llm_router


def test_language_intent_parsing():
    """Verify that language commands map directly to set_language intent instead of chat."""
    res1 = nlp.parse_intent("talk in english")
    assert res1["intent"] == "set_language"
    assert res1["args"].get("language") == "english"

    res2 = nlp.parse_intent("talk ine english")
    assert res2["intent"] == "set_language"
    assert res2["args"].get("language") == "english"

    res3 = nlp.parse_intent("speak english")
    assert res3["intent"] == "set_language"
    assert res3["args"].get("language") == "english"

    res4 = nlp.parse_intent("switch to hindi")
    assert res4["intent"] == "set_language"
    assert res4["args"].get("language") == "hindi"


def test_model_switch_intent_parsing():
    """Verify that model switching commands map to switch_model and get_active_model."""
    res1 = nlp.parse_intent("switch to gemini")
    assert res1["intent"] == "switch_model"
    assert "gemini" in res1["args"].get("model", "")

    res2 = nlp.parse_intent("shine switch to gemini")
    assert res2["intent"] == "switch_model"
    assert "gemini" in res2["args"].get("model", "")

    res3 = nlp.parse_intent("switch model to groq")
    assert res3["intent"] == "switch_model"
    assert "groq" in res3["args"].get("model", "")

    res4 = nlp.parse_intent("what model are you using")
    assert res4["intent"] == "get_active_model"

    res5 = nlp.parse_intent("active model")
    assert res5["intent"] == "get_active_model"


def test_compound_browser_search_parsing():
    """Verify compound open and search commands route directly to web_search."""
    res1 = nlp.parse_intent("open chrome and search who is talented boy")
    assert res1["intent"] == "web_search"
    assert "who is talented boy" in res1["args"].get("query", "")

    res2 = nlp.parse_intent("chrome open karo aur search karo python tutorial")
    assert res2["intent"] == "web_search"
    assert "python tutorial" in res2["args"].get("query", "")


def test_language_state_persistence_and_prompt():
    """Verify language preference changes update settings and AI system prompt."""
    settings.set_language("english")
    assert settings.get_language() == "english"

    nlp.invalidate_system_prompt_cache()
    prompt = nlp._get_ai_system_prompt()
    assert "MANDATORY LANGUAGE & FEMALE PERSONA RULE" in prompt
    assert "100% IN ENGLISH" in prompt

    # Offline replies should be in English
    offline_reply = personality.get_offline_chat_response("hello")
    assert any(w in offline_reply.lower() for w in ("hey", "mj", "hero", "systems", "what's up"))
    assert "kya" not in offline_reply.lower()

    # Reset back to hindi for test isolation
    settings.set_language("hindi")
    nlp.invalidate_system_prompt_cache()
    prompt_hi = nlp._get_ai_system_prompt()
    assert "MANDATORY GENDER IDENTITY & GRAMMAR RULE" in prompt_hi


def test_model_switching_dispatch():
    """Verify switch_model command execution."""
    msg = commands.dispatch({"intent": "switch_model", "args": {"model": "gemini"}})
    assert "Gemini" in msg
    assert llm_router.get_preferred_provider() == "gemini"

    status_msg = commands.dispatch({"intent": "get_active_model", "args": {}})
    assert "Gemini" in status_msg

    # Switch to auto
    msg_auto = commands.dispatch({"intent": "switch_model", "args": {"model": "auto"}})
    assert "Auto" in msg_auto
    assert llm_router.get_preferred_provider() is None


def test_chrome_profile_directory():
    """Verify Chrome is launched with Default profile."""
    with patch("subprocess.Popen") as mock_popen, \
         patch("core.commands._find_chrome_path", return_value="C:\\chrome.exe"):
        commands._open_in_browser("https://google.com")
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert "--profile-directory=Default" in cmd
        assert "https://google.com" in cmd


def test_open_app_browser_alias():
    """Verify 'browser' resolves to Chrome with profile."""
    with patch("core.commands._open_in_browser", return_value=True) as mock_open:
        res = commands.open_app({"app": "browser"})
        mock_open.assert_called_once()
        assert "Chrome" in res or "open" in res.lower()


def test_open_app_non_existent_truthful():
    """Verify non-existent apps do not hallucinate success."""
    with patch("shutil.which", return_value=None), \
         patch("os.path.exists", return_value=False), \
         patch("core.commands._detect_and_dismiss_error_popup", return_value=False), \
         patch("app_finder.launch_application", return_value=(False, "Not found")):
        res = commands.open_app({"app": "completely_fake_nonexistent_xyz_app_12345"})
        assert "nahi mila" in res or "couldn't find" in res
        assert "open kar diya" not in res


def test_screen_seeing_intents():
    """Verify screen vision and what's open commands route to describe_screen."""
    queries = [
        "can you see the screen",
        "can you see my screen",
        "what is open on the screen",
        "what is open on my screen",
        "i am talking about can you see my screen what is open on the screen",
        "screen pe kya hai",
        "screen pe kya khula hai",
        "screen pe kya open hai",
        "what is on the screen",
    ]
    for q in queries:
        res = nlp.parse_intent(q)
        assert res["intent"] in ("describe_screen", "explain_screen_activity", "screen_query"), f"Failed for {q}: {res}"


def test_click_commands_and_news_separation():
    """Verify click commands do not collide with tell_news and strip 'on screen'."""
    res1 = nlp.parse_intent("click google news on screen")
    assert res1["intent"] == "click_text"
    assert res1["args"].get("text") == "google news"

    res2 = nlp.parse_intent("click home india")
    assert res2["intent"] == "click_text"
    assert res2["args"].get("text") == "home india"

    res3 = nlp.parse_intent("click home")
    assert res3["intent"] == "click_text"
    assert res3["args"].get("text") == "home"

    # News queries with news verbs still work
    res_news = nlp.parse_intent("tell me the latest news on sports")
    assert res_news["intent"] == "tell_news"
    assert "sports" in res_news["args"].get("topic", "")


def test_close_app_clean_title():
    """Verify closing YouTube or browser tabs returns clean spoken names without emojis or long URLs."""
    mock_win = MagicMock()
    mock_win.title = "(1473) A Chatpati Playlist Only For Chatpata People 😋✨ | Ultimate Vibe Songs Playlist 🎧💖 - YouTube"
    mock_win.activate.return_value = None

    with patch("pygetwindow.getAllWindows", return_value=[mock_win]), \
         patch("pyautogui.hotkey") as mock_hotkey:
        res = commands.close_app({"app": "the youtube"})
        mock_hotkey.assert_called_with("ctrl", "w")
        assert "YouTube" in res
        assert "Chatpati" not in res
        assert "😋" not in res


def test_click_text_ui_automation():
    """Verify click_text uses Windows UI Automation first without failing on missing Tesseract."""
    with patch("core.ui_tree.click_ui_element_by_name", return_value=(True, "Clicked")) as mock_click:
        res = commands.click_text({"text": "Google News on screen", "action": "click"})
        mock_click.assert_called_once_with("google news")
        assert "Clicked on 'google news'" in res


def test_web_search_news_bypass_and_cleaning():
    """Verify web_search strips 'on chrome' prefix and bypasses smart_answer for live news."""
    with patch("core.commands._open_in_browser") as mock_open, \
         patch("live_search.smart_answer") as mock_smart:
        commands.web_search({"query": "on chrome latest news of india"})
        # Should NOT call smart_answer / wikipedia for live news
        mock_smart.assert_not_called()
        mock_open.assert_called_once()
        url = mock_open.call_args[0][0]
        assert "latest+news+of+india" in url
        assert "on+chrome" not in url


def test_clean_wiki_text():
    """Verify wiki text cleans markdown headers and collapses newlines."""
    from core.live_search import _clean_wiki_text
    raw = "== Background ==\n\nPrashant Tamang is an Indian singer.\n== Career ==\nHe won Indian Idol."
    cleaned = _clean_wiki_text(raw)
    assert "==" not in cleaned
    assert "Background" not in cleaned
    assert "Prashant Tamang is an Indian singer." in cleaned


def test_file_manager_search_and_open():
    """Verify 'open file manager and search hh' routes to file_search."""
    res1 = nlp.parse_intent("open file manager and search hh")
    assert res1["intent"] == "file_search"
    assert res1["args"].get("query") == "hh"

    res2 = nlp.parse_intent("open file explorer and search project")
    assert res2["intent"] == "file_search"
    assert res2["args"].get("query") == "project"

    res3 = nlp.parse_intent("open file manager")
    assert res3["intent"] == "open_app"
    assert "explorer" in res3["args"].get("app", "")


def test_youtube_lagakar_koi_intent():
    """Verify Hinglish compound play requests map directly to youtube_play."""
    res1 = nlp.parse_intent("youtube lagakar koi")
    assert res1["intent"] == "youtube_play"

    res2 = nlp.parse_intent("youtube lagakar koi gana")
    assert res2["intent"] == "youtube_play"


def test_train_shin_guard_false_positives():
    """Verify general questions like 'install kaise karna hai mujhe' never trigger train_shin."""
    res = nlp.parse_intent("install kaise karna hai mujhe")
    assert res["intent"] != "train_shin"


def test_ai_parse_unparsed_json_recovery_and_suppression():
    """Verify truncated or broken model JSON output is recovered or suppressed from speech."""
    from core import nlp as nlp_mod

    # Case 1: Truncated JSON recovery
    fake_router = MagicMock()
    fake_router.query.return_value = {"content": '{"intent": "youtube_play", "'}
    with patch("core.llm_router.get_router", return_value=fake_router):
        parsed = nlp_mod._ai_parse("youtube lagakar koi")
        assert parsed["intent"] == "youtube_play"

    # Case 2: Broken JSON never spoken as raw syntax
    fake_router.query.return_value = {"content": '{"broken_json": true, "intent": ???'}
    with patch("core.llm_router.get_router", return_value=fake_router):
        parsed = nlp_mod._ai_parse("some command")
        # Should NOT return raw code syntax as spoken text
        response_text = parsed.get("args", {}).get("response", "")
        assert not response_text.startswith("{")
        assert "???" not in response_text


def test_click_targeting_and_extension_rejection():
    """Verify clicking 'My mix' does not match toolbar/extension buttons and parses cleanly."""
    from core.ui_tree import clean_target_name, find_best_ui_element_match

    # 1. NLP parsing cleanly strips leading 'on', 'the', and trailing fillers
    r1 = nlp.parse_intent("click on My mix")
    assert r1["intent"] == "click_text"
    assert r1["args"]["text"] == "My mix"

    r2 = nlp.parse_intent("click on the My mix video")
    assert r2["intent"] == "click_text"
    assert r2["args"]["text"] == "My mix"

    r3 = nlp.parse_intent("My mix pe click karo")
    assert r3["intent"] == "click_text"
    assert r3["args"]["text"] == "My mix"

    # 2. UI Automation element matching: empty names and single-letter avatars NEVER match
    toolbar_elements = [
        {"name": "", "type": "Button", "x": 1180, "y": 56, "width": 24, "height": 24},   # Extension icon
        {"name": "m", "type": "Button", "x": 1220, "y": 56, "width": 24, "height": 24},  # User avatar
        {"name": "Reload", "type": "Button", "x": 75, "y": 56, "width": 24, "height": 24},
        {"name": "Search", "type": "Edit", "x": 300, "y": 56, "width": 200, "height": 30},
    ]
    matched, score = find_best_ui_element_match("My mix", toolbar_elements)
    assert matched is None, f"Toolbar element falsely matched: {matched}"
    assert score == 0.0

    # When target IS present in UI tree, it matches with high confidence
    all_elements = toolbar_elements + [
        {"name": "My Mix", "type": "Button", "x": 825, "y": 348, "width": 50, "height": 20}
    ]
    matched_exact, score_exact = find_best_ui_element_match("click on My mix", all_elements)
    assert matched_exact is not None
    assert matched_exact["name"] == "My Mix"
    assert score_exact >= 95.0


def test_click_text_fallback_to_ocr():
    """Verify click_text falls back to screen OCR/vision when UIA does not find the element."""
    with patch("core.ui_tree.click_ui_element_by_name", return_value=(False, "Not found")), \
         patch("core.vision.find_text_on_screen", return_value=(True, {"x": 844, "y": 354, "left": 825, "top": 348, "width": 39, "height": 13, "text": "My Mix"})) as mock_ocr, \
         patch("pyautogui.moveTo") as mock_move, \
         patch("pyautogui.click") as mock_click:

        res = commands.click_text({"text": "click on My mix", "action": "click"})
        mock_ocr.assert_called_once_with("my mix")
        mock_move.assert_called_once_with(844, 354, duration=0.2)
        mock_click.assert_called_once()
        assert "Clicked on 'my mix'" in res


def test_remove_greetings_and_auto_talk():
    """Verify unprompted auto-talk and startup greetings are completely disabled."""
    from core import alerts
    assert hasattr(alerts, "PROACTIVE_AUTO_TALK")
    assert alerts.PROACTIVE_AUTO_TALK is False

    mock_speak = MagicMock()
    alerts._speak_cb = mock_speak
    alerts._speak("Unsolicited message")
    # Must NOT call speak because PROACTIVE_AUTO_TALK is False
    mock_speak.assert_not_called()


def test_learn_laptop_skills_intent_and_execution():
    """Verify 'learn new things about laptop and commands' parses and executes."""
    queries = [
        "learn new things about laptop",
        "learn new things about laptop and commands",
        "learn new commands",
        "learn laptop commands",
        "laptop ke baare mein nayi cheezein seekho",
    ]
    for q in queries:
        parsed = nlp.parse_intent(q)
        assert parsed["intent"] == "learn_laptop_skills", f"Failed for query: {q}"

    with patch("core.memory.add_memory") as mock_add_mem:
        res = commands.learn_laptop_skills({})
        assert "learned and memorized new laptop skills" in res.lower() or "power skills seekh kar" in res.lower()
        assert mock_add_mem.call_count >= 5


def test_learn_custom_command_intent_and_macro():
    """Verify teaching custom commands like 'learn command study mode to open vs code'."""
    parsed1 = nlp.parse_intent("learn command study mode to open vs code")
    assert parsed1["intent"] == "learn_macro"
    assert parsed1["args"]["trigger"] == "study mode"
    assert parsed1["args"]["commands"] == "open vs code"

    parsed2 = nlp.parse_intent("learn this command: open workspace to open vs code")
    assert parsed2["intent"] == "learn_macro"
    assert parsed2["args"]["trigger"] == "open workspace"

    with patch("macros._load_custom_macros", return_value={}), \
         patch("macros._save_custom_macros") as mock_save:
        res = commands.learn_macro({"trigger": "study mode", "commands": "open vs code and open terminal"})
        mock_save.assert_called_once()
        assert "study mode" in res
        assert "open vs code" in res


def test_model_switching_aliases_and_cascade():
    """Verify model switching handles aliases and cascades cleanly."""
    from core import llm_router

    # DeepSeek / TokenHarbor alias
    ok, name = llm_router.set_preferred_provider("deepseek")
    assert ok is True
    assert "Tokenharbor" in name

    # Groq / Qwen alias
    ok2, name2 = llm_router.set_preferred_provider("qwen")
    assert ok2 is True
    assert "Groq" in name2

    # Auto cascade
    ok3, name3 = llm_router.set_preferred_provider("auto")
    assert ok3 is True
    assert "Auto Cascade" in name3
    assert llm_router.get_preferred_provider() is None





