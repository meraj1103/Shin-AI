"""
predictive_engine.py — Real-Life Work Intelligence & Proactive Predictions for Shin
===================================================================================
Anticipates user workflows, daily routines, clipboard activity, real-time power/battery
events, alarms, and multi-app developer contexts. Tailored for MJ's real life as an
engineering student and builder in Maharashtra.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("shin.predictive_engine")


class PredictiveEngine:
    """Core intelligence engine for proactive predictions and real-life context awareness."""

    def __init__(self):
        self._last_prediction_time: Optional[datetime] = None

    # ── 1. Daily Routine & Time Context Predictions ────────────────────────────

    def predict_daily_routine(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Evaluate time of day, active processes, pending to-dos, and battery status
        to predict MJ's current workflow phase and next best action.
        """
        now = datetime.now()
        hour = now.hour
        weekday_name = now.strftime("%A")

        # Battery & Power status check
        battery_info = self.get_power_status()

        # To-Dos / Pending tasks check
        pending_tasks = self._get_pending_tasks()

        # Active App check
        active_app, active_title = self._get_active_window_info()

        period = "day"
        prediction_msg = ""
        suggested_actions = []

        # Subah (Morning: 5 AM - 11:59 AM)
        if 5 <= hour < 12:
            period = "morning"
            task_str = f" Tere paas '{pending_tasks[0]}' pending hai." if pending_tasks else ""
            prediction_msg = (
                f"Good morning, MJ! Aaj {weekday_name} hai.{task_str} "
                f"Mera prediction: Subah ka fresh dimaag hai, pehle sabse tough coding ya assignment complete kar le!"
            )
            suggested_actions = [
                "Aaj ka schedule check karo",
                "Top news headlines suno",
                "Coding sprint start karo",
            ]

        # Dopahar (Afternoon Work / Focus: 12 PM - 4:59 PM)
        elif 12 <= hour < 17:
            period = "afternoon"
            if "code" in active_app or "pycharm" in active_app or "terminal" in active_app:
                prediction_msg = (
                    "Dopahar ka coding session chal raha hai MJ! Dhyan se logic check karte reh, "
                    "aur agar koi bug aaye toh mujhe bol dena, main traceback dekh lungi."
                )
                suggested_actions = ["Run pytest", "Inspect active error", "Take a 5-minute break"]
            elif "blender" in active_app:
                prediction_msg = (
                    "Blender pe 3D modeling chal rahi hai! Scene render karne se pehle lighting "
                    "aur normals verify kar lena. Kuch reference dhoondhoon kya?"
                )
                suggested_actions = ["Save blender file", "Search 3D reference"]
            else:
                task_str = f" Pending task '{pending_tasks[0]}' finish kar lein?" if pending_tasks else "Kya task start karein?"
                prediction_msg = f"Afternoon focus mode active hai MJ. {task_str}"
                suggested_actions = ["Check to-do list", "Focus timer 25 min"]

        # Shaam (Evening / Unwind & Fitness: 5 PM - 9:59 PM)
        elif 17 <= hour < 22:
            period = "evening"
            prediction_msg = (
                "Shaam ka time hai MJ! Screen se thodi der aakhein hata ke walk ya exercise kar le, "
                "fir refresh hoke shaam ka project review karte hain."
            )
            suggested_actions = ["Exercise reminder", "Play chill music on Spotify", "Review today's progress"]

        # Raat (Late Night / Wind-down: 10 PM - 4:59 AM)
        else:
            period = "night"
            if hour >= 23 or hour < 4:
                prediction_msg = (
                    f"Raat ke {now.strftime('%I:%M %p')} baj gaye hain MJ! Kaafi late night work chal raha hai. "
                    "Mera sincere recommendation: code save kar le, aur so ja — kal fresh dimaag se aur tezi se hoga!"
                )
                suggested_actions = ["Set morning alarm", "Sleep wind-down", "Save all work"]
            else:
                prediction_msg = "Late evening ho chuki hai MJ. Dinner ho gaya? Thoda relax kar le ya music sun le."
                suggested_actions = ["Play Spotify", "Wrap up open files"]

        # If on battery and below 25%, elevate warning in prediction
        if not battery_info.get("plugged", True) and battery_info.get("percent", 100) < 25:
            prediction_msg += f" Waise charger laga le — battery sirf {battery_info['percent']}% bachi hai!"

        return {
            "period": period,
            "current_time": now.strftime("%Y-%m-%d %I:%M %p"),
            "prediction": prediction_msg,
            "suggested_actions": suggested_actions,
            "active_app": active_app,
            "battery": battery_info,
            "pending_tasks_count": len(pending_tasks),
        }

    # ── 2. Real-Life Clipboard Predictions ─────────────────────────────────────

    def predict_clipboard_action(self, clipboard_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze clipboard content to predict immediate user intent:
        - Python / Language Error Tracebacks -> Instant diagnostic & fix suggestion
        - GitHub / YouTube / Web URLs -> Repo inspection or playback summary
        - Math & Currency expressions -> Evaluated computation
        - JSON / Code snippets -> Linting / formatting
        """
        if clipboard_text is None:
            clipboard_text = self._read_clipboard()

        text = (clipboard_text or "").strip()
        if not text:
            return {
                "type": "empty",
                "prediction": "Clipboard khali hai MJ! Kuch copy kar fir dekhte hain kya predict karna hai.",
            }

        # Case A: Error Traceback Detection (Python, Node, C++, Java)
        if any(marker in text for marker in ("Traceback (most recent call last):", "Error:", "Exception:", "at line ")):
            error_type = "Error"
            error_detail = ""
            for line in reversed(text.splitlines()):
                line = line.strip()
                if any(err in line for err in ("Error:", "Exception:", "SyntaxError", "TypeError", "ValueError", "AttributeError", "KeyError", "IndexError", "ImportError")):
                    error_type = line
                    break

            return {
                "type": "error_traceback",
                "detected": error_type,
                "prediction": f"Clipboard mein code traceback detect hua: '{error_type}'. Kya iska fix aur explanation chahiye?",
                "suggested_action": "explain_error",
                "raw_snippet": text[:400],
            }

        # Case B: GitHub Repo URL
        if re.search(r"https?://github\.com/([\w\-]+)/([\w\-]+)", text):
            match = re.search(r"https?://github\.com/([\w\-]+)/([\w\-]+)", text)
            repo_owner, repo_name = match.group(1), match.group(2)
            return {
                "type": "github_url",
                "repo": f"{repo_owner}/{repo_name}",
                "prediction": f"GitHub repo '{repo_owner}/{repo_name}' copy kiya tune! Kya iska code inspect karein ya clone command run karein?",
                "suggested_action": "inspect_repo",
                "url": match.group(0),
            }

        # Case C: YouTube URL
        if re.search(r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w\-]+)", text):
            return {
                "type": "youtube_url",
                "prediction": "YouTube video link clipboard mein hai! Video play karoon ya summary nikaaloon?",
                "suggested_action": "play_youtube",
                "url": text,
            }

        # Case D: Math or Unit Expression in clipboard
        # e.g., "4500 * 18%", "sqrt(144) + 20", "50 USD in INR"
        if re.match(r"^[\d\s\+\-\*\/\^\(\)\.\%]+$", text) and len(text) >= 3 and any(op in text for op in "+-*/%"):
            try:
                try:
                    import calculator as _calc_mod
                    _evaluate = _calc_mod.evaluate_expression
                except ImportError:
                    from core import calculator as _calc_mod
                    _evaluate = _calc_mod.evaluate_expression
                # Pre-process percentage math expressions before calling calculator (e.g. "250 * 20%" -> "250 * (20/100)")
                eval_expr = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'(\1/100)', text)
                result_str = _evaluate(eval_expr)
                # evaluate_expression returns a natural-language string like "The result is 450."
                # Extract the numeric part for structured output
                _num_match = re.search(r"[\d,]+\.?\d*", result_str)
                if _num_match:
                    _raw_num = _num_match.group(0).replace(",", "").rstrip(".")
                    result_val = _raw_num
                else:
                    result_val = result_str
                return {
                    "type": "math_expression",
                    "expression": text,
                    "result": result_val,
                    "prediction": f"Clipboard ka math expression: {text} = {result_val}",
                    "suggested_action": "copy_result",
                }
            except Exception:
                pass

        # Case E: Generic URL
        if text.startswith(("http://", "https://")):
            return {
                "type": "web_url",
                "prediction": f"Web URL copy kiya hai: '{text[:60]}...'. Is page ki summary nikaaloon?",
                "suggested_action": "summarize_url",
                "url": text,
            }

        # Case F: Short Code Snippet
        if any(kw in text for kw in ("def ", "class ", "import ", "function ", "const ", "let ", "for (", "while (")):
            return {
                "type": "code_snippet",
                "prediction": "Code snippet clipboard mein hai! Review karoon ya improve karein?",
                "suggested_action": "review_code",
                "raw_snippet": text[:300],
            }

        return {
            "type": "text",
            "prediction": f"Clipboard text: '{text[:80]}{'...' if len(text) > 80 else ''}'. Ispe koi AI action perform karna hai?",
            "suggested_action": "transform_text",
        }

    # ── 3. App Workflow Context Predictions ────────────────────────────────────

    def predict_app_workflow(self, app_name: Optional[str] = None, window_title: Optional[str] = None) -> Dict[str, Any]:
        """Deep contextual predictions based on the active application and window title."""
        if app_name is None or window_title is None:
            detected_app, detected_title = self._get_active_window_info()
            app_name = app_name or detected_app
            window_title = window_title or detected_title

        app_lower = (app_name or "").lower()
        title_lower = (window_title or "").lower()

        # 1. VS Code / Development IDE
        if any(editor in app_lower for editor in ("code", "visual studio", "pycharm", "sublime")):
            if "test_" in title_lower or "test" in title_lower:
                return {
                    "context": "testing",
                    "prediction": "Tu test file pe kaam kar raha hai! pytest run karke sare test cases verify kar lein?",
                    "suggested_command": "run_python_code",
                }
            return {
                "context": "coding",
                "prediction": "Code editor active hai. Agla logical step: code save karke linter check karo ya tests run karo.",
                "suggested_command": "inspect_active_app",
            }

        # 2. Blender / 3D
        if "blender" in app_lower:
            return {
                "context": "3d_modeling",
                "prediction": "Blender khula hai! Autosave check kar le aur camera view (Numpad 0) se composition verify kar.",
                "suggested_command": "blender_helper",
            }

        # 3. Web Browsers
        if any(b in app_lower for b in ("chrome", "edge", "firefox", "brave")):
            if "youtube" in title_lower:
                return {
                    "context": "youtube",
                    "prediction": "YouTube chal raha hai! Agar study time hai toh focus mode on kar doon?",
                    "suggested_command": "manage_tab",
                }
            if "github" in title_lower:
                return {
                    "context": "github",
                    "prediction": "GitHub browsing chal rahi hai! Repo clone karna hai ya PR inspect karni hai?",
                    "suggested_command": "inspect_repo",
                }
            return {
                "context": "browsing",
                "prediction": "Browser open hai. Jo articles padh raha hai unka quick summary chahiye?",
                "suggested_command": "summarize_screen",
            }

        # 4. Terminal / Shell
        if any(t in app_lower for t in ("terminal", "powershell", "cmd", "bash")):
            return {
                "context": "shell",
                "prediction": "Terminal open hai! Koi complex git command ya server run karna hai toh bata.",
                "suggested_command": "terminal_assistant",
            }

        return {
            "context": "general",
            "prediction": f"Abhi '{app_name or 'desktop'}' active hai. Bata MJ, kya help chahiye?",
            "suggested_command": "none",
        }

    # ── 4. Real-Life Power Cut / Battery Event ─────────────────────────────────

    def get_power_status(self) -> Dict[str, Any]:
        """Fetch battery percentage and charging state safely."""
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                return {
                    "percent": round(battery.percent),
                    "plugged": bool(battery.power_plugged),
                    "seconds_left": battery.secsleft if battery.secsleft > 0 else None,
                }
        except Exception as exc:
            logger.debug("psutil battery query failed: %s", exc)

        return {"percent": 100, "plugged": True, "seconds_left": None}

    def handle_power_event(self, event: str = "cut") -> str:
        """Handle real-life Indian power outages ('light is gone' / 'bijli chali gayi')."""
        battery = self.get_power_status()
        pct = battery["percent"]
        plugged = battery["plugged"]

        if not plugged:
            mins_left = round(battery["seconds_left"] / 60) if battery.get("seconds_left") else None
            time_str = f" Lagbhag {mins_left} minute ka backup bacha hai." if mins_left else ""
            return (
                f"Are re, light chali gayi kya! Laptop abhi battery pe chal raha hai ({pct}% bachi hai).{time_str} "
                "Main suggest karungi ki sab open files aur code abhi save kar lo! Chaho toh screen brightness thodi kam kar doon?"
            )
        else:
            return (
                f"Maine check kiya, charger abhi connected dikh raha hai ({pct}% battery). "
                "Agar power cut hua hai toh switch check kar lo ya battery backup mode mein save kar lena!"
            )

    # ── 5. Natural Time Parsing (Alarms & Wall-Clock Reminders) ────────────────

    @staticmethod
    def parse_natural_time(time_str: str) -> Optional[Tuple[int, int]]:
        """
        Convert time phrases like:
        - "6:00 p.m.", "6:00pm", "6 pm", "18:00" -> (18, 0)
        - "7:30 am", "7:30am", "7 am" -> (7, 30)
        - "11 pm" -> (23, 0)
        - "6 baje", "shaam 6 baje", "subah 7 baje" -> (18, 0), (7, 0)
        """
        raw = time_str.lower().strip()
        # Clean punctuation
        raw = raw.replace(".", "").strip()

        # Check for Hinglish prefixes: "subah 7", "shaam 6", "raat 11"
        is_subah = any(w in raw for w in ("subah", "morning", "am"))
        is_shaam_raat = any(w in raw for w in ("shaam", "dopahar", "raat", "evening", "night", "pm"))

        # Match "HH:MM"
        match_hm = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)?", raw)
        if match_hm:
            h = int(match_hm.group(1))
            m = int(match_hm.group(2))
            meridiem = match_hm.group(3)
            if meridiem == "pm" and h < 12:
                h += 12
            elif meridiem == "am" and h == 12:
                h = 0
            elif not meridiem:
                if is_shaam_raat and h < 12:
                    h += 12
                elif is_subah and h == 12:
                    h = 0
            return (h % 24, m % 60)

        # Match single digit hour: "7 am", "11 pm", "6 baje"
        match_h = re.search(r"(\d{1,2})\s*(?:o'?clock|baje)?\s*(am|pm)?", raw)
        if match_h:
            h = int(match_h.group(1))
            meridiem = match_h.group(2)
            if meridiem == "pm" and h < 12:
                h += 12
            elif meridiem == "am" and h == 12:
                h = 0
            elif not meridiem:
                if is_shaam_raat and h < 12:
                    h += 12
                elif is_subah and h == 12:
                    h = 0
                elif h in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11) and "baje" in raw and not is_subah:
                    # In India, "6 baje" / "8 baje" spoken during daytime/evening usually means evening
                    current_h = datetime.now().hour
                    if current_h >= 12 and h <= 11:
                        h += 12
            return (h % 24, 0)

        return None

    @staticmethod
    def calculate_delay_seconds(target_h: int, target_m: int) -> int:
        """Calculate seconds from now until next occurrence of target (hour, minute)."""
        now = datetime.now()
        target = now.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
        if target <= now:
            # Time has passed today, schedule for tomorrow
            target += timedelta(days=1)
        return int((target - now).total_seconds())

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_pending_tasks(self) -> List[str]:
        try:
            try:
                import todo
            except ImportError:
                from core import todo
            items = todo.get_todos()
            return [t["task"] for t in items if not t.get("done", False)]
        except Exception:
            return []

    def _get_active_window_info(self) -> Tuple[str, str]:
        try:
            try:
                import app_tracker
            except ImportError:
                from core import app_tracker
            title = app_tracker._get_foreground_title()
            app = app_tracker._extract_app_name(title).lower()
            return app, title
        except Exception:
            return "", ""

    def _read_clipboard(self) -> str:
        try:
            try:
                import clipboard_ai
            except ImportError:
                from core import clipboard_ai
            return clipboard_ai.get_clipboard()
        except Exception:
            try:
                import pyperclip
                return pyperclip.paste() or ""
            except Exception:
                return ""


# Singleton instance
predictive_engine = PredictiveEngine()
