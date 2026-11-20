"""
alerts.py — Proactive system alerts and monitoring for Shin
============================================================
Monitors:
  - Battery status (low battery alerts, power connection changes)
  - CPU usage (sustained high usage alerts)
  - Long-running processes (by PID or name)

Runs in a background thread and calls Shin's speak function.
"""

from __future__ import annotations

import logging
import os
import random
import time
import threading
from typing import Callable, Dict, List, Set, Optional
import psutil

logger = logging.getLogger(__name__)

# Callback function to speak alerts (disabled by default to prevent unsolicited auto-talk)
_speak_cb: Optional[Callable[[str], None]] = None
_alerts_stop_event = threading.Event()
PROACTIVE_AUTO_TALK: bool = False  # Strict silent mode: speak only when spoken to by user


def stop_alerts() -> None:
    """Stop the alerts background loop and clear the speak callback."""
    global _speak_cb
    _alerts_stop_event.set()
    _speak_cb = None

# Active process monitoring
# Maps pid -> process_name
_monitored_pids: Dict[int, str] = {}
_pid_lock = threading.Lock()

# Battery state tracking
_last_battery_percent: Optional[float] = None
_last_power_plugged: Optional[bool] = None
_battery_low_alerted: Set[int] = set()  # Tracks which thresholds (20, 15, 10) have been alerted

# CPU state tracking
_high_cpu_count = 0
_last_cpu_alert_time = 0.0

# Calendar tracking
_notified_events: Set[str] = set()
_calendar_lock = threading.Lock()

# Task tracking
_last_todo_alert_time = time.time()  # Start timer at boot so it doesn't alert immediately

# Hydration, screen break, and bedtime tracking
_last_water_reminder_time = time.time()
_last_screen_break_time = time.time()
_bedtime_alerted_today = False

# Contextual and meal alerts state
_lunch_alerted_today = False
_dinner_alerted_today = False
_last_active_app = None
_app_focus_start_time = time.time()
_last_app_nudge_time = 0.0

# Predictive engine integration state
_PREDICTIVE_APPS = {"coding", "blender", "browsing"}
_PREDICTIVE_NUDGE_INTERVAL = 600.0  # speak at most one app suggestion every 10 minutes
_last_predictive_nudge_time = 0.0

# Idle tracking
_last_mouse_pos = None
_last_activity_time = time.time()
_is_idle = False

# Random small talk state
# Fires every 10–20 minutes, with the first talk sooner (3–8 minutes after boot)
_next_random_talk_time = time.time() + random.uniform(180, 480)

def init_alerts(speak_fn: Callable[[str], None]) -> None:
    """Initialize alerts module with assistant speak callback."""
    global _speak_cb
    _speak_cb = speak_fn
    
    # Initialize initial state
    try:
        battery = psutil.sensors_battery()
        if battery:
            global _last_battery_percent, _last_power_plugged
            _last_battery_percent = battery.percent
            _last_power_plugged = battery.power_plugged
    except Exception as exc:
        logger.warning("Failed to initialize battery monitoring: %s", exc)

    # Start background thread
    t = threading.Thread(target=_alerts_monitor_loop, daemon=True)
    t.start()
    logger.info("Proactive system alerts thread started.")


def watch_process(pid: int, name: str) -> bool:
    """Register a process PID to monitor."""
    with _pid_lock:
        if psutil.pid_exists(pid):
            _monitored_pids[pid] = name
            logger.info("Watching process PID %d (%s)", pid, name)
            return True
        return False


def watch_latest_process_by_name(process_name: str) -> Optional[tuple[int, str]]:
    """
    Find the most recently started process matching process_name (excluding Shin itself)
    and monitor it. Returns (pid, name) if found, else None.
    """
    my_pid = os.getpid()
    target_proc = None
    latest_create_time = 0.0

    for proc in psutil.process_iter(['pid', 'name', 'create_time']):
        try:
            pid = proc.info['pid']
            name = proc.info['name']
            create_time = proc.info['create_time']
            if pid == my_pid:
                continue
            if name and isinstance(name, str) and process_name.lower() in name.lower():
                if create_time > latest_create_time:
                    latest_create_time = create_time
                    target_proc = proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if target_proc:
        pid = target_proc.info['pid']
        name = target_proc.info['name'] or process_name
        # Also try to get cmdline for a better descriptive name
        try:
            cmd = target_proc.cmdline()
            if cmd:
                # E.g. "python script.py"
                display_name = " ".join(cmd[:3])
                if len(display_name) > 40:
                    display_name = display_name[:40] + "..."
            else:
                display_name = name
        except Exception:
            display_name = name

        if watch_process(pid, display_name):
            return pid, display_name

    return None


def _speak(text: str) -> None:
    if not PROACTIVE_AUTO_TALK:
        return
    cb = _speak_cb  # capture locally to avoid race with stop_alerts
    if _alerts_stop_event.is_set() or not cb:
        return
    try:
        # Run the speak call in a separate thread so it does not block the monitor loop
        threading.Thread(target=cb, args=(text,), daemon=True).start()
    except Exception as exc:
        logger.error("Failed to speak alert: %s", exc)


def _load_predictive_engine():
    """Return the predictive_engine singleton via a dual-path import, or None."""
    try:
        import predictive_engine as _pe_module
    except ImportError:
        try:
            from core import predictive_engine as _pe_module
        except ImportError:
            logger.debug("predictive_engine module unavailable.")
            return None
    # The module exposes a singleton instance named `predictive_engine`.
    return getattr(_pe_module, "predictive_engine", None)


def _get_active_app_name(window_title: str) -> str:
    """Derive a short, spoken-friendly app name from a window title."""
    try:
        try:
            from app_tracker import _extract_app_name
        except ImportError:
            from core.app_tracker import _extract_app_name
        return _extract_app_name(window_title)
    except Exception:
        return window_title


def _maybe_speak_app_prediction(window_title: str) -> None:
    """Speak a contextual workflow suggestion on a notable app transition."""
    global _last_predictive_nudge_time
    now = time.time()
    if now - _last_predictive_nudge_time < _PREDICTIVE_NUDGE_INTERVAL:
        return
    try:
        engine = _load_predictive_engine()
        if engine is None:
            return
        app_name = _get_active_app_name(window_title)
        result = engine.predict_app_workflow(app_name, window_title)
        suggestion = result.get("prediction") if isinstance(result, dict) else None
        if suggestion:
            _speak(suggestion)
            _last_predictive_nudge_time = now
    except Exception as exc:
        logger.debug("Predictive app workflow suggestion failed: %s", exc)


def _check_battery() -> None:
    global _last_battery_percent, _last_power_plugged, _battery_low_alerted
    try:
        battery = psutil.sensors_battery()
        if not battery:
            return

        percent = battery.percent
        plugged = battery.power_plugged

        # 1. Check power state changes
        if _last_power_plugged is None:
            _last_power_plugged = plugged
        elif plugged != _last_power_plugged:
            if plugged:
                import personality
                _speak(f"{personality.pick('power_connected')} Battery is at {round(percent)} percent.")
                _battery_low_alerted.clear()  # Reset alerts on charge
            else:
                import personality
                _speak(f"{personality.pick('power_disconnected')} At {round(percent)} percent.")
            _last_power_plugged = plugged

        # 2. Check low battery alerts
        if not plugged:
            # Discharging alerts
            for threshold in [20, 15, 10]:
                if percent <= threshold and threshold not in _battery_low_alerted:
                    import personality
                    _speak(f"{personality.pick('battery_low')} At {round(percent)} percent.")
                    _battery_low_alerted.add(threshold)
                    break  # Alert one threshold at a time
        else:
            # If plugged in and we cross above threshold, remove from alerted set
            for threshold in list(_battery_low_alerted):
                if percent >= threshold + 2:
                    _battery_low_alerted.remove(threshold)

        _last_battery_percent = percent
    except Exception as exc:
        logger.debug("Error checking battery: %s", exc)


def _check_cpu() -> None:
    global _high_cpu_count, _last_cpu_alert_time
    try:
        # cpu_percent with interval=None is non-blocking (returns since last call)
        cpu_usage = psutil.cpu_percent(interval=None)
        
        if cpu_usage > 85.0:
            _high_cpu_count += 1
        else:
            _high_cpu_count = max(0, _high_cpu_count - 1)

        # Trigger alert if high usage for 5 consecutive checks (50 seconds)
        # limit frequency to once every 5 minutes
        current_time = time.time()
        if _high_cpu_count >= 5 and (current_time - _last_cpu_alert_time > 300.0):
            _speak(f"Warning: CPU usage has been very high at {round(cpu_usage)} percent.")
            _last_cpu_alert_time = current_time
            _high_cpu_count = 2  # Set back slightly so it doesn't trigger immediately again
    except Exception as exc:
        logger.debug("Error checking CPU: %s", exc)


def _check_monitored_processes() -> None:
    global _monitored_pids
    with _pid_lock:
        exited_pids: List[int] = []
        for pid, name in _monitored_pids.items():
            if not psutil.pid_exists(pid):
                exited_pids.append(pid)
                # Format PID to speak individual digits
                pid_spaced = " ".join(list(str(pid)))
                _speak(f"MJ, the process {name} with P I D {pid_spaced} has finished executing.")

        for pid in exited_pids:
            _monitored_pids.pop(pid)

def _check_calendar() -> None:
    global _notified_events
    # Prevent overlapping API calls if the network is extremely slow
    if not _calendar_lock.acquire(blocking=False):
        return
        
    try:
        import calendar_ai
        import datetime
        events = calendar_ai.get_upcoming_events(max_results=3)
        if not events or isinstance(events, str):
            return
            
        now = datetime.datetime.now(datetime.timezone.utc)
        for event in events:
            start_time_str = event.get('start', {}).get('dateTime')
            if not start_time_str:
                continue # Skip all-day events
                
            event_time = datetime.datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            # Ensure event_time is always timezone-aware (some calendar APIs omit tzinfo)
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=datetime.timezone.utc)
            diff = (event_time - now).total_seconds()
            event_id = event.get('id', '')
            
            # Alert if event is within 15 minutes (900 seconds) and not yet notified
            if 0 < diff <= 900 and event_id not in _notified_events:
                summary = event.get('summary', 'Untitled Event')
                mins = int(diff // 60)
                _speak(f"MJ, heads up! You have: {summary}, starting in {mins} minute{'s' if mins != 1 else ''}.")
                _notified_events.add(event_id)
    except Exception as exc:
        logger.debug("Error checking calendar alerts: %s", exc)
    finally:
        _calendar_lock.release()


def _check_todos() -> None:
    global _last_todo_alert_time
    current_time = time.time()
    # Nudge every 2 hours (7200 seconds) if there are open tasks
    if current_time - _last_todo_alert_time < 7200:
        return
        
    try:
        import todo
        pending = todo.pending_count()
        if pending > 0:
            task_word = "task" if pending == 1 else "tasks"
            _speak(f"MJ, yaad dilana tha — abhi bhi {pending} pending {task_word} hain to-do list mein!")
            _last_todo_alert_time = current_time
    except Exception as exc:
        logger.debug("Error checking todos for alerts: %s", exc)


def _check_bedtime_reminder() -> None:
    global _bedtime_alerted_today, _last_water_reminder_time
    try:
        from datetime import datetime
        now = datetime.now()
        # Between 12:00 AM (0) and 6:00 AM (exclusive)
        if 0 <= now.hour < 6:
            if not _bedtime_alerted_today:
                import personality
                _speak(personality.pick("bedtime"))
                _bedtime_alerted_today = True
                # Reset hourly water reminder to avoid double-reminder
                _last_water_reminder_time = time.time()
        else:
            # Reset the alert flag outside bedtime hours
            _bedtime_alerted_today = False
    except Exception as exc:
        logger.debug("Error checking bedtime reminder: %s", exc)


def _check_water_reminder() -> None:
    global _last_water_reminder_time
    if _last_active_app == "gaming":
        return
    try:
        current_time = time.time()
        # 1 hour = 3600 seconds
        if current_time - _last_water_reminder_time >= 3600:
            import personality
            _speak(personality.pick("water"))
            _last_water_reminder_time = current_time
    except Exception as exc:
        logger.debug("Error checking water reminder: %s", exc)


def _check_screen_break() -> None:
    global _last_screen_break_time
    if _last_active_app == "gaming":
        return
    try:
        current_time = time.time()
        # 30 minutes = 1800 seconds
        if current_time - _last_screen_break_time >= 1800:
            import personality
            _speak(personality.pick("screen_break"))
            _last_screen_break_time = current_time
    except Exception as exc:
        logger.debug("Error checking screen break: %s", exc)


def _check_meal_reminders() -> None:
    global _lunch_alerted_today, _dinner_alerted_today
    try:
        from datetime import datetime
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        
        # Lunch (between 1:30 PM and 2:30 PM)
        in_lunch_window = (hour == 13 and minute >= 30) or (hour == 14 and minute < 30)
        if in_lunch_window:
            if not _lunch_alerted_today:
                import personality
                _speak(personality.pick("lunch"))
                _lunch_alerted_today = True
        else:
            _lunch_alerted_today = False

        # Dinner (between 8:30 PM and 9:30 PM)
        in_dinner_window = (hour == 20 and minute >= 30) or (hour == 21 and minute < 30)
        if in_dinner_window:
            if not _dinner_alerted_today:
                import personality
                _speak(personality.pick("dinner"))
                _dinner_alerted_today = True
        else:
            _dinner_alerted_today = False
    except Exception as exc:
        logger.debug("Error checking meal reminders: %s", exc)


def _check_app_activity() -> None:
    global _last_active_app, _app_focus_start_time, _last_app_nudge_time
    try:
        import pygetwindow as gw
        active_win = gw.getActiveWindow()
        if not active_win or not active_win.title:
            return
            
        title = active_win.title.lower()
        
        # Determine app type
        current_app = None
        if "visual studio code" in title or "vscode" in title or ".py" in title or "clion" in title or "codeblocks" in title:
            current_app = "coding"
        elif "blender" in title:
            current_app = "blender"
        elif "steam" in title or any(game in title for game in ("cyberpunk", "gta", "witcher", "valorant", "fifa", "counter-strike", "fortnite", "apex legends", "minecraft", "red dead")):
            current_app = "gaming"
        elif any(browser in title for browser in ("google chrome", "chrome", "msedge", "firefox", "brave", "opera")):
            current_app = "browsing"
            
        if current_app != _last_active_app:
            _last_active_app = current_app
            _app_focus_start_time = time.time()
            _last_app_nudge_time = 0.0
            # On a notable transition (coding / 3D / browser), speak a contextual suggestion
            if current_app in _PREDICTIVE_APPS:
                _maybe_speak_app_prediction(active_win.title)
            
        # Update mood when gaming
        if current_app == "gaming":
            try:
                import personality
                personality.update_mood("gaming")
            except Exception:
                pass

        # Nudge coding/blender users if they've been at it for 1 hour (3600 seconds)
        if current_app in ("coding", "blender"):
            focused_duration = time.time() - _app_focus_start_time
            if focused_duration >= 3600 and (time.time() - _last_app_nudge_time > 3600):
                import personality
                if current_app == "coding":
                    _speak(personality.pick("coding_nudge"))
                    personality.update_mood("long_session")
                elif current_app == "blender":
                    _speak(personality.pick("blender_nudge"))
                _last_app_nudge_time = time.time()
                
    except Exception as exc:
        logger.debug("Error checking app activity: %s", exc)


def _check_idle_and_activity() -> None:
    global _last_mouse_pos, _last_activity_time, _is_idle
    try:
        import pyautogui
        pos = pyautogui.position()
        if _last_mouse_pos is None:
            _last_mouse_pos = pos
            _last_activity_time = time.time()
        elif pos != _last_mouse_pos:
            _last_mouse_pos = pos
            if _is_idle:
                # Returned from idle
                _is_idle = False
                import personality
                _speak(personality.pick("return_idle"))
            _last_activity_time = time.time()
        else:
            # Went idle after 10 minutes (600 seconds)
            if not _is_idle and (time.time() - _last_activity_time > 600):
                _is_idle = True
                logger.info("System went idle (no mouse movement for 10 minutes).")
    except Exception as exc:
        logger.debug("Error in idle tracking: %s", exc)


def _build_chatter_prompt() -> str:
    """Build a rich context-aware prompt for dynamic proactive chatter."""
    from datetime import datetime
    now = datetime.now()
    hour = now.hour
    weekday = now.strftime("%A")
    is_weekend = now.weekday() >= 5

    # Time-of-day label
    if 5 <= hour < 12:
        time_label = "morning"
    elif 12 <= hour < 17:
        time_label = "afternoon"
    elif 17 <= hour < 21:
        time_label = "evening"
    else:
        time_label = "late night"

    app_context = _last_active_app or "general use"
    weekend_note = " It's the weekend." if is_weekend else ""

    try:
        import personality
        mood = personality.get_mood()
    except Exception:
        mood = "normal"

    # Enrich context with the predictive engine's routine prediction (best-effort)
    prediction_note = ""
    try:
        engine = _load_predictive_engine()
        if engine is not None:
            prediction = engine.predict_daily_routine()
            pred_text = prediction.get("prediction") if isinstance(prediction, dict) else None
            if pred_text:
                prediction_note = f"Predictive context: {pred_text} "
    except Exception as exc:
        logger.debug("Predictive routine unavailable for chatter: %s", exc)

    return (
        f"You are Shin — MJ's closest best friend and personal AI assistant. "
        f"MJ is a 17-year-old ENTC student from Kolhapur who codes, uses Blender, and games. "
        f"It is {time_label} on {weekday}.{weekend_note} "
        f"MJ is currently doing: {app_context}. Shin's current mood: {mood}. "
        f"{prediction_note}\n\n"
        f"You feel like saying something to MJ right now — completely unprompted, "
        f"just like a best friend would check in. "
        f"Say ONE short, warm, natural Hinglish sentence (under 20 words). "
        f"Don't ask a question every time — sometimes just comment, tease lightly, "
        f"encourage, or say something funny. Never start with 'Hey' or 'MJ' every time. "
        f"Sound human and spontaneous, not like a bot. "
        f"Reply with ONLY the sentence — nothing else, no quotes, no labels."
    )


def _dynamic_chatter_ollama(prompt: str) -> str | None:
    """Try to generate a chatter line using local Ollama (100% free, offline)."""
    try:
        import urllib.request
        import json
        import os
        model = os.getenv("OLLAMA_MODEL", "llama3").split(",")[0].strip()
        if not model:
            return None
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 40, "temperature": 0.9}
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            result = json.loads(resp.read().decode())
            line = result.get("response", "").strip()
            return line if line else None
    except Exception as exc:
        logger.debug("Ollama chatter failed: %s", exc)
        return None


def _dynamic_chatter_gemini(prompt: str) -> str | None:
    """Try to generate a chatter line using Gemini free tier (1,500 req/day, $0)."""
    try:
        import os
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            return None
        import urllib.request
        import json
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={api_key}"
        )
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 50, "temperature": 0.95}
        }).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            result = json.loads(resp.read().decode())
            line = (
                result.get("candidates", [{}])[0]
                      .get("content", {})
                      .get("parts", [{}])[0]
                      .get("text", "")
                      .strip()
            )
            return line if line else None
    except Exception as exc:
        logger.debug("Gemini chatter failed: %s", exc)
        return None


def _fire_random_observation() -> None:
    """Speak a proactive random one-liner. NOT logged — casual background chatter.

    Tier order (all completely free):
      1. Ollama local LLM  — offline, no quota, instant
      2. Gemini free tier  — 1,500 req/day, no credit card needed
      3. Static pool       — personality.py phrases, always available
    """
    def _generate_and_speak():
        try:
            prompt = _build_chatter_prompt()

            # Tier 1 — Ollama (local, free, offline)
            line = _dynamic_chatter_ollama(prompt)

            # Tier 2 — Gemini free tier
            if not line:
                line = _dynamic_chatter_gemini(prompt)

            # Tier 3 — static personality pool
            if not line:
                import personality
                line = personality.get_random_observation()

            if line and _speak_cb and not _alerts_stop_event.is_set():
                _speak_cb(line)
        except Exception as exc:
            logger.debug("Random observation failed: %s", exc)

    threading.Thread(target=_generate_and_speak, daemon=True).start()


def _alerts_monitor_loop() -> None:
    global _next_random_talk_time

    # Warm up CPU checks
    psutil.cpu_percent(interval=None)

    check_counter = 0
    while not _alerts_stop_event.is_set():
        try:
            # Check monitored processes and user activity (every 2 seconds)
            _check_monitored_processes()
            _check_idle_and_activity()
            _check_app_activity()

            # Check CPU every 10 seconds
            if check_counter % 5 == 0:
                _check_cpu()

            # Check Battery, bedtime, water, screen breaks, and meals every 30 seconds
            if check_counter % 15 == 0:
                _check_battery()
                _check_bedtime_reminder()
                _check_water_reminder()
                _check_screen_break()
                _check_meal_reminders()

            # Check Calendar every 60 seconds
            if check_counter % 30 == 0:
                threading.Thread(target=_check_calendar, daemon=True).start()

            # Check To-Dos every ~2 minutes (the function restricts announcements to every 2 hours)
            if check_counter == 0:
                _check_todos()

            # Random proactive small talk — every 10–20 minutes, randomised each cycle
            # Only fires when system is not idle and no other alert just spoke
            if time.time() >= _next_random_talk_time and not _is_idle:
                _fire_random_observation()
                # Schedule next observation: 10–20 minutes from now
                _next_random_talk_time = time.time() + random.uniform(600, 1200)

            check_counter = (check_counter + 1) % 60
        except Exception as exc:
            logger.exception("Error in alert monitoring loop: %s", exc)

        time.sleep(2.0)
