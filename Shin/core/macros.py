"""
macros.py — Multi-step named routines for Shin Voice Assistant
================================================================
Each macro is a sequence of actions that Shin executes in order.
The `speak` callable is injected from assistant.py to avoid circular imports.

Built-in macros:
  "morning"  — volume up, weather, open email, motivational greeting
  "focus"    — mute sound, open VS Code
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_MACROS_DIR = Path(__file__).parent.parent / "data"
_MACROS_FILE = _MACROS_DIR / "custom_macros.json"

# Migrate old data if it exists in the Documents/Shin folder
_OLD_MACROS_DIR = Path.home() / "Documents" / "Shin"
if _OLD_MACROS_DIR.exists() and (_OLD_MACROS_DIR / "custom_macros.json").exists() and not _MACROS_FILE.exists():
    import shutil
    _MACROS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(_OLD_MACROS_DIR / "custom_macros.json", _MACROS_FILE)
        logger.info("Migrated custom_macros.json from %s to %s", _OLD_MACROS_DIR, _MACROS_DIR)
    except Exception as exc:
        logger.error("Failed to migrate custom_macros.json: %s", exc)


def _load_custom_macros() -> dict:
    if not _MACROS_FILE.exists():
        return {}
    try:
        with open(_MACROS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load custom macros: %s", exc)
        return {}


def _save_custom_macros(data: dict) -> None:
    _MACROS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(_MACROS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as exc:
        logger.error("Failed to save custom macros: %s", exc)


def match_custom_macro(text: str) -> Optional[str]:
    """
    Check if a spoken command matches a custom macro trigger, directly
    or with standard start prefixes. Returns the normalized macro name if matched.
    """
    text = text.lower().strip()
    # Remove simple punctuation
    text = re.sub(r'^[^\w]+|[^\w]+$', '', text)

    custom_macros = _load_custom_macros()
    if not custom_macros:
        return None

    for name in custom_macros:
        name_lower = name.lower().strip()
        # Direct exact match
        if text == name_lower:
            return name

        # Pattern match: start/run prefix
        pattern = rf"^(?:start|run|begin|launch|activate|enable)\s+(?:my\s+)?(?:routine\s+|mode\s+|shortcut\s+)?{re.escape(name_lower)}(?:\s+(?:routine|mode|shortcut))?$"
        if re.match(pattern, text):
            return name

    return None


def run_custom_macro(name: str, speak: Callable[[str], None]) -> str:
    """
    Execute a user-defined custom macro by executing its commands sequentially.
    """
    custom_macros = _load_custom_macros()
    macro = custom_macros.get(name.lower().strip())
    if not macro:
        return f"Macro '{name}' not found."

    commands_list = macro.get("commands", [])
    if not commands_list:
        return f"Macro '{name}' contains no commands."

    speak(f"Activating custom routine '{name}'.")

    # Lazy imports to avoid circular dependencies
    import nlp as _nlp
    import commands as _cmds

    for cmd_text in commands_list:
        logger.info("Executing custom macro step: %r", cmd_text)
        speak(f"Running: {cmd_text}")

        # Parse intent of cmd_text
        res = _nlp.parse_intent(cmd_text)
        intent_name = res.get("intent", "unknown")
        args = res.get("args", {})

        if intent_name != "unknown":
            try:
                response = _cmds.dispatch({"intent": intent_name, "args": args})
                if response:
                    speak(response)
            except Exception as exc:
                logger.error("Failed to run custom macro step '%s': %s", cmd_text, exc)
                speak(f"Error executing step: {exc}")
        else:
            speak(f"I didn't understand how to run: {cmd_text}")

    return f"Routine '{name}' complete."


# ── Public entry point ─────────────────────────────────────────────────────────

def run_macro(name: str, speak: Callable[[str], None]) -> str:
    """
    Execute a named macro sequence.

    Parameters
    ----------
    name : str
        The macro name (e.g. "morning", "focus", "briefing").
    speak : callable
        The TTS function from assistant.py — injected to avoid circular imports.

    Returns
    -------
    str
        A short summary message spoken after the macro finishes.
    """
    name = name.lower().strip()
    _registry = {
        "morning":  _morning_routine,
        "focus":    _focus_routine,
        "work":     _focus_routine,
        "study":    _focus_routine,
        "gaming":   _gaming_routine,
        "game":     _gaming_routine,
        "briefing": _daily_briefing,
        "daily":    _daily_briefing,
        "brief":    _daily_briefing,
        "evening":  _evening_routine,
        "night":    _evening_routine,
        "wind down":_evening_routine,
        "dev":      _dev_routine,
        "developer":_dev_routine,
        "coding":   _dev_routine,
        "programming":_dev_routine,
        "entertainment":_entertainment_routine,
        "movie":    _entertainment_routine,
        "relax":    _entertainment_routine,
        "leaving":  _leaving_routine,
        "bye":      _leaving_routine,
    }
    fn = _registry.get(name)
    if fn:
        return fn(speak)

    custom = _load_custom_macros()
    if name in custom:
        return run_custom_macro(name, speak)

    custom_names = ", ".join(custom.keys())
    custom_suffix = f", or custom: {custom_names}" if custom_names else ""
    return f"I don't know a routine called '{name}'. Available routines: morning, evening, focus, dev, gaming, briefing{custom_suffix}."


# ── Weather helper ──────────────────────────────────────────────────────────────────────────────

def _get_weather(city: str = None) -> str:
    """Delegate to the dedicated weather module."""
    try:
        import weather as _weather_mod
        return _weather_mod.get_current_weather(city)
    except Exception:
        return ""


# ── Individual routines ────────────────────────────────────────────────────────

def _morning_routine(speak: Callable[[str], None]) -> str:
    """
    Morning routine:
      1. Greet with today's date
      2. Speak today's weather
      3. News headlines
      4. Calendar events today
      5. To-do count
      6. Turn volume up
      7. Open the mail app
    """
    import commands  # lazy import — avoids circular dependency at module load time

    now = datetime.datetime.now()
    greeting = (
        f"Good morning! Today is {now.strftime('%A, %B %d')}. "
        "Let me get you set up."
    )
    speak(greeting)

    # Step 1: Weather
    weather = _get_weather()
    if weather:
        speak(weather)
    else:
        speak("I couldn't fetch the weather right now, but let's keep going.")

    # Step 2: News headlines
    try:
        import news
        headlines = news.get_top_headlines(count=3)
        if headlines:
            speak("Here are today's top headlines.")
            formatted = news.format_headlines_for_speech(headlines, max_articles=3)
            speak(formatted)
    except Exception as exc:
        logger.warning("Morning routine news fetch failed: %s", exc)

    # Step 3: Calendar events
    try:
        import calendar_ai
        events = calendar_ai.get_upcoming_events(max_results=3)
        if events and not isinstance(events, str):
            speak(f"You have {len(events)} upcoming calendar event{'s' if len(events) != 1 else ''} today.")
        elif isinstance(events, str):
            pass  # error string — skip silently
        else:
            speak("You have no calendar events scheduled for today.")
    except Exception as exc:
        logger.warning("Morning routine calendar fetch failed: %s", exc)

    # Step 4: To-do count
    try:
        import todo
        pending = todo.pending_count()
        if pending:
            speak(f"You have {pending} open task{'s' if pending != 1 else ''} on your to-do list.")
    except Exception:
        pass

    # Step 5: Turn volume up
    commands.volume_up({"delta": 20})

    # Step 6: Open email
    speak("Opening your email.")
    commands.open_app({"app": "mail"})

    return "Morning routine complete. Have a great day!"


def _focus_routine(speak: Callable[[str], None]) -> str:
    """
    Focus / deep-work routine:
      1. Mute audio distractions
      2. Open VS Code
      3. Encouraging message
    """
    import commands  # lazy import

    speak("Activating focus mode. Muting distractions.")
    commands.mute_volume({})
    commands.open_app({"app": "vs code"})
    speak("VS Code is opening. Volume is muted. Time to get in the zone.")

    return "Focus routine active."


def _gaming_routine(speak: Callable[[str], None]) -> str:
    """
    Gaming routine:
      1. Turn up volume
      2. Open Discord and Steam
    """
    import commands  # lazy import

    speak("Activating gaming mode. Game on!")
    commands.set_volume({"level": 80})
    commands.open_app({"app": "discord"})
    commands.open_app({"app": "steam"})

    return "Gaming mode active."


def _daily_briefing(speak: Callable[[str], None]) -> str:
    """
    Daily briefing:
      1. Time-appropriate greeting
      2. Weather
      3. Top 3 news
      4. Calendar events today
      5. Pending to-dos
    """
    now = datetime.datetime.now()
    hour = now.hour
    if hour < 12:
        greeting = "Good morning!"
    elif hour < 17:
        greeting = "Good afternoon!"
    else:
        greeting = "Good evening!"

    speak(f"{greeting} Here's your daily briefing.")

    # Weather
    weather = _get_weather()
    if weather:
        speak(weather)

    # News
    try:
        import news
        headlines = news.get_top_headlines(count=3)
        if headlines:
            speak("Today's top headlines:")
            speak(news.format_headlines_for_speech(headlines, max_articles=3))
    except Exception as exc:
        logger.warning("Briefing news failed: %s", exc)

    # Calendar
    try:
        import calendar_ai
        events = calendar_ai.get_upcoming_events(max_results=5)
        if isinstance(events, list) and events:
            speak(f"You have {len(events)} upcoming event{'s' if len(events) != 1 else ''}.")
        elif not isinstance(events, list):
            pass  # error string — skip silently
        else:
            speak("No calendar events scheduled.")
    except Exception:
        pass

    # To-do count
    try:
        import todo
        pending = todo.pending_count()
        if pending:
            speak(f"You have {pending} pending task{'s' if pending != 1 else ''} on your to-do list.")
        else:
            speak("Your to-do list is clear. Nice work!")
    except Exception:
        pass

    return "Briefing complete."


def _evening_routine(speak: Callable[[str], None]) -> str:
    """
    Evening routine:
      1. Lower brightness to 30%
      2. Lower volume to 20%
      3. Read tomorrow's calendar events
      4. Read pending to-do count
      5. Activate sleep scene in smart home
    """
    import commands  # lazy import

    speak("Good evening! Time to wind down.")
    commands.set_volume({"level": 20})
    commands.set_brightness({"level": 30})

    try:
        import calendar_ai
        events = calendar_ai.get_upcoming_events(max_results=3, day="tomorrow")
        if isinstance(events, list) and events:
            speak(f"You have {len(events)} event{'s' if len(events) != 1 else ''} scheduled for tomorrow.")
        elif not isinstance(events, list):
            pass  # error string — skip silently
        else:
            speak("Your calendar is clear for tomorrow. Rest easy.")
    except Exception:
        pass

    try:
        import todo
        pending = todo.pending_count()
        if pending:
            speak(f"You have {pending} pending task{'s' if pending != 1 else ''} on your to-do list.")
    except Exception:
        pass

    try:
        import smart_home
        smart_home.activate_scene("sleep")
    except Exception as exc:
        logger.warning("Failed to activate sleep scene in evening routine: %s", exc)

    return "Evening routine complete. Sleep well!"


def _dev_routine(speak: Callable[[str], None]) -> str:
    """
    Developer routine: Set volume, open VS Code, GitHub, and Command Prompt.
    """
    import commands  # lazy import
    speak("Setting up your developer environment.")
    commands.set_volume({"level": 40})
    commands.open_app({"app": "vs code"})
    commands.open_url({"url": "https://github.com"})
    commands.open_app({"app": "cmd"})
    return "Developer environment ready. Happy coding!"


def _entertainment_routine(speak: Callable[[str], None]) -> str:
    """
    Entertainment routine: Dim brightness, increase volume, open Netflix.
    """
    import commands  # lazy import
    speak("Setting up entertainment mode.")
    commands.set_brightness({"level": 50})
    commands.set_volume({"level": 75})
    commands.open_app({"app": "netflix"})
    return "Entertainment mode active. Enjoy your watch!"


def _leaving_routine(speak: Callable[[str], None]) -> str:
    """
    Leaving routine: Greet, mute volume, minimize all windows, lock screen.
    """
    import commands  # lazy import
    speak("Goodbye! Preparing for your departure.")
    commands.mute_volume({})
    commands.window_minimize_all({})
    commands.lock_screen({})
    return "Systems secured. Goodbye!"
