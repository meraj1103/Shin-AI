"""
test_real_life_scenarios.py — Automated verification for Real-Life Work Intelligence & Proactive Predictions
=============================================================================================================
Validates:
1. Real user queries from historical missed_intents.log
2. PredictiveEngine time parsing, routine predictions, and clipboard AI actions
3. Commands dispatch for alarms, tabs, messaging, power cut awareness, and sleep routines
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

_SHIN_DIR = Path(__file__).resolve().parent.parent
if str(_SHIN_DIR) not in sys.path:
    sys.path.insert(0, str(_SHIN_DIR))
_CORE_DIR = _SHIN_DIR / "core"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

import nlp
import commands
from predictive_engine import PredictiveEngine, predictive_engine


# ── Test Suite 1: Historical Real-Life Missed Intents ──────────────────────────

class TestRealLifeMissedIntents:
    """Verifies that queries previously logged as NO_MATCH or UNKNOWN_INTENT now parse correctly."""

    def test_alarm_for_6pm(self):
        parsed = nlp.parse_intent("set alarm for 6:00 p.m.")
        assert parsed["intent"] == "set_alarm"
        assert "6:00 p.m" in parsed["args"]["time"]

    def test_alarm_natural_hinglish(self):
        parsed = nlp.parse_intent("alarm laga do 7 baje")
        assert parsed["intent"] in ("set_alarm", "set_reminder")
        assert "7" in parsed["args"]["time"]

    def test_wake_me_up_at_7am(self):
        parsed = nlp.parse_intent("wake me up at 7 am")
        assert parsed["intent"] == "set_alarm"
        assert "7 am" in parsed["args"]["time"]

    def test_remind_me_to_exercise_at_11pm(self):
        parsed = nlp.parse_intent("Remind me to exercise at 11 pm")
        assert parsed["intent"] == "set_reminder"
        assert parsed["args"]["task"] == "exercise"
        assert parsed["args"]["time"] == "11 pm"

    def test_send_message_to_contact(self):
        parsed = nlp.parse_intent("Send message to anuj kaha hai")
        assert parsed["intent"] == "send_whatsapp_message"
        assert parsed["args"]["contact"] == "anuj"
        assert parsed["args"]["message"] == "kaha hai"

    def test_momo_message_karo(self):
        parsed = nlp.parse_intent("momo message karo 10 minut mein aata")
        assert parsed["intent"] == "send_whatsapp_message"
        assert parsed["args"]["contact"] == "momo"
        assert "10 minut" in parsed["args"]["message"]

    def test_tab_with_a(self):
        parsed = nlp.parse_intent("Tab With A")
        assert parsed["intent"] == "manage_tab"
        assert parsed["args"]["action"] == "switch"
        assert parsed["args"]["query"] == "A"

    def test_next_tab(self):
        parsed = nlp.parse_intent("next tab")
        assert parsed["intent"] == "manage_tab"
        assert parsed["args"]["action"] == "next"

    def test_close_tab(self):
        parsed = nlp.parse_intent("close tab")
        assert parsed["intent"] == "manage_tab"
        assert parsed["args"]["action"] == "close"

    def test_power_cut_light_is_gone(self):
        parsed = nlp.parse_intent("light is gone")
        assert parsed["intent"] == "power_status"

    def test_power_cut_bijli_chali_gayi(self):
        parsed = nlp.parse_intent("bijli chali gayi")
        assert parsed["intent"] == "power_status"

    def test_identity_i_am_mj(self):
        parsed = nlp.parse_intent("I am mj")
        assert parsed["intent"] == "store_relationship"
        assert "MJ" in parsed["args"]["raw"]

    def test_identity_she_is_my_sister(self):
        parsed = nlp.parse_intent("She is mys sister")
        assert parsed["intent"] == "store_relationship"
        assert "sister" in parsed["args"]["raw"].lower()

    def test_screen_vision_queries(self):
        for phrase in ("what is this", "what am I looking at", "describe my screen", "summarize this"):
            parsed = nlp.parse_intent(phrase)
            assert parsed["intent"] == "screen_query", f"Failed for '{phrase}'"

    def test_sleep_routine(self):
        for phrase in ("main sone ja raha hun", "neend aa rahi hai", "sone ka time ho gaya"):
            parsed = nlp.parse_intent(phrase)
            assert parsed["intent"] == "sleep_routine", f"Failed for '{phrase}'"

    def test_proactive_prediction_request(self):
        for phrase in ("give me a prediction", "predict my day", "real life work update", "predict what i need"):
            parsed = nlp.parse_intent(phrase)
            assert parsed["intent"] == "predict_next_move", f"Failed for '{phrase}'"


# ── Test Suite 2: Predictive Engine Intelligence ───────────────────────────────

class TestPredictiveEngine:
    """Verifies core logic of PredictiveEngine."""

    def test_natural_time_parser(self):
        assert PredictiveEngine.parse_natural_time("6:00 p.m.") == (18, 0)
        assert PredictiveEngine.parse_natural_time("6:00pm") == (18, 0)
        assert PredictiveEngine.parse_natural_time("18:00") == (18, 0)
        assert PredictiveEngine.parse_natural_time("7:30 am") == (7, 30)
        assert PredictiveEngine.parse_natural_time("11 pm") == (23, 0)
        assert PredictiveEngine.parse_natural_time("subah 7 baje") == (7, 0)

    def test_delay_seconds_is_future(self):
        delay = PredictiveEngine.calculate_delay_seconds(18, 0)
        assert isinstance(delay, int)
        assert 0 < delay <= 86400

    def test_predict_daily_routine(self):
        res = predictive_engine.predict_daily_routine()
        assert "period" in res
        assert "prediction" in res
        assert "suggested_actions" in res
        assert len(res["suggested_actions"]) > 0
        assert "battery" in res
        assert isinstance(res["prediction"], str)
        assert len(res["prediction"]) > 10

    def test_predict_clipboard_error_traceback(self):
        traceback_sample = """
Traceback (most recent call last):
  File "main.py", line 42, in <module>
    result = compute_metrics(data)
  File "calc.py", line 12, in compute_metrics
ZeroDivisionError: division by zero
"""
        pred = predictive_engine.predict_clipboard_action(traceback_sample)
        assert pred["type"] == "error_traceback"
        assert "ZeroDivisionError" in pred["detected"]
        assert pred["suggested_action"] == "explain_error"

    def test_predict_clipboard_github_url(self):
        url = "https://github.com/google/gemini-api"
        pred = predictive_engine.predict_clipboard_action(url)
        assert pred["type"] == "github_url"
        assert pred["repo"] == "google/gemini-api"
        assert pred["suggested_action"] == "inspect_repo"

    def test_predict_clipboard_youtube_url(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        pred = predictive_engine.predict_clipboard_action(url)
        assert pred["type"] == "youtube_url"
        assert pred["suggested_action"] == "play_youtube"

    def test_predict_clipboard_math_expression(self):
        expr = "2500 * 0.18"
        pred = predictive_engine.predict_clipboard_action(expr)
        assert pred["type"] == "math_expression"
        assert pred["result"] in ("450.0", "450", 450.0, 450)

    def test_predict_app_workflow(self):
        wf_code = predictive_engine.predict_app_workflow("Code.exe", "test_nlp.py - Shin")
        assert wf_code["context"] == "testing"

        wf_blender = predictive_engine.predict_app_workflow("blender.exe", "character_rig.blend")
        assert wf_blender["context"] == "3d_modeling"

        wf_chrome = predictive_engine.predict_app_workflow("chrome.exe", "YouTube - Lo-Fi Beats")
        assert wf_chrome["context"] == "youtube"


# ── Test Suite 3: End-to-End Command Dispatch ──────────────────────────────────

class TestRealLifeCommandDispatch:
    """Verifies that command handlers return correct, human-readable strings."""

    def test_dispatch_set_alarm(self):
        res = commands.dispatch({"intent": "set_alarm", "args": {"time": "06:30 am"}})
        assert "alarm set kar diya" in res
        assert "06:30" in res

    def test_dispatch_set_reminder_with_time(self):
        res = commands.dispatch({"intent": "set_reminder", "args": {"task": "standup meeting", "time": "11 pm"}})
        assert "Reminder set for 11 pm: standup meeting." in res

    def test_dispatch_power_status(self):
        res = commands.dispatch({"intent": "power_status", "args": {}})
        assert any(k in res for k in ("battery", "charger", "light", "power"))

    def test_dispatch_sleep_routine(self):
        res = commands.dispatch({"intent": "sleep_routine", "args": {}})
        assert "Good night" in res or "so jao" in res

    def test_dispatch_manage_tab_action(self):
        # manage_tab shouldn't crash in headless environments
        res = commands.dispatch({"intent": "manage_tab", "args": {"action": "next"}})
        assert isinstance(res, str)
        assert len(res) > 0

    def test_dispatch_store_relationship(self):
        res = commands.dispatch({"intent": "store_relationship", "args": {"raw": "User test fact"}})
        assert "yaad rakh liya" in res or "note kar liya" in res

    def test_dispatch_predict_next_move(self):
        res = commands.dispatch({"intent": "predict_next_move", "args": {}})
        assert isinstance(res, str)
        assert len(res) > 20
