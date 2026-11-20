"""
api_manager.py — Simple API manager for Shin's NLP

This module provides a stable interface for other parts of the system (or
future HTTP/IPC layers) to call the intent parser.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from nlp import parse_intent

logger = logging.getLogger(__name__)


def handle_command(text: str) -> Dict[str, Any]:
    """
    High-level API for running the NLP pipeline.

    Parameters
    ----------
    text : str
        Raw user utterance (e.g. from speech recognition).

    Returns
    -------
    dict
        {
          "ok": bool,          # whether parsing succeeded without internal error
          "intent": str,       # e.g. "open_app", "web_search", "unknown"
          "args": dict,        # intent-specific payload
          "error": str | None  # optional error description if ok == False
        }
    """
    try:
        if text is None:
            return {
                "ok": False,
                "intent": "unknown",
                "args": {},
                "error": "text is None",
            }

        text = str(text).strip()
        if not text:
            return {
                "ok": True,
                "intent": "unknown",
                "args": {},
                "error": None,
            }

        intent_result = parse_intent(text)

        # Ensure minimal schema
        intent = intent_result.get("intent", "unknown")
        args = intent_result.get("args", {}) or {}

        return {
            "ok": True,
            "intent": intent,
            "args": args,
            "_confidence": intent_result.get("_confidence", 1.0),
            "_confirm": intent_result.get("_confirm", False),
            "error": None,
        }

    except Exception as exc:
        logger.exception("Error in handle_command(%r): %s", text, exc)
        return {
            "ok": False,
            "intent": "unknown",
            "args": {},
            "error": str(exc),
        }


def is_action_intent(intent: str) -> bool:
    """
    Helper: return True if intent is one that should trigger an action
    instead of a chat response.
    """
    if not intent:
        return False

    # Mirror the list used in the AI system prompt
    ACTION_INTENTS = {
        "open_app", "close_app", "close_active_window",
        "mute_volume", "unmute_volume", "volume_up", "volume_down", "set_volume",
        "brightness_up", "brightness_down", "set_brightness",
        "web_search", "open_url",
        "open_folder", "open_file", "save_note", "set_reminder",
        "shutdown", "shutdown_timer", "restart", "sleep", "lock_screen",
        "tell_time", "tell_date", "screenshot", "type_text", "press_key", "click_text",
        # Screen vision
        "screen_query",
        # Window management
        "window_minimize_all", "window_snap_left", "window_snap_right", "window_snap_quadrant",
        "window_maximize", "window_minimize", "scroll",
        # Media controls
        "media_play_pause", "media_next", "media_prev",
        # Clipboard AI
        "clipboard_translate", "clipboard_rewrite",
        "clipboard_summarize", "clipboard_fix", "clipboard_history",
        # Macros
        "run_macro",
        "tell_news",
        # Calendar
        "calendar_list", "calendar_add",
        # Spotify
        "spotify_play", "spotify_status",
        # YouTube
        "youtube_play",
        # Smart home
        "smart_home_control", "activate_scene", "smart_home_status",
        # Monitoring
        "monitor_process",
        "check_system_status",
        "quit_assistant",
        # Meta & Memory
        "set_personality", "save_memory", "recall_memory", "forget_memory",
        "list_open_windows", "pause_listening", "resume_listening", "wifi_control",
        # Missing & New feature intents
        "weather_query", "pomodoro", "battery_status",
        "todo_add", "todo_list", "todo_complete", "todo_delete",
        "convert", "read_emails", "enroll_voice", "delete_voice_profile", "app_volume",
        "clean_pc", "read_clipboard", "learn_macro", "list_macros", "delete_macro",
        "bluetooth_control", "airplane_mode_control", "night_light_control", "mobile_hotspot_control", "nearby_share_control"
    }

    return intent in ACTION_INTENTS


if __name__ == "__main__":
    # Simple manual test / REPL
    logging.basicConfig(level=logging.INFO)
    print("Shin API manager — type commands, Ctrl+C to exit.")
    try:
        while True:
            text = input("You: ").strip()
            result = handle_command(text)
            print("Result:", result)
    except KeyboardInterrupt:
        print("\nBye.")
