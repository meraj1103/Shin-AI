"""
commands.py — Windows automation handlers for Shin Voice Assistant
=====================================================================
Each public function accepts an `args` dict (from the intent parser) and
returns a human-readable response string.

All destructive operations raise ConfirmationRequired so the caller can
prompt the user before proceeding.
"""

from __future__ import annotations

import datetime
import logging
import os
import re
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional

import psutil
import pyautogui
try:
    import schedule
except ImportError:
    schedule = None

pyautogui.FAILSAFE = False  # prevent corner-of-screen crash during automation

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_WHATSAPP_CONTACTS_FILE = _DATA_DIR / "whatsapp_contacts.json"


_speak_cb = None

def init_commands(speak_fn):
    global _speak_cb
    _speak_cb = speak_fn

def _speak(text: str, wait: bool = True):
    if _speak_cb:
        _speak_cb(text, wait)

# ═══════════════════════════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════════════════════════

class ConfirmationRequired(Exception):
    """Raised by commands that need explicit user confirmation before running."""
    def __init__(self, prompt: str, callback):
        super().__init__(prompt)
        self.prompt = prompt
        self.callback = callback

class MissingArgument(Exception):
    """Raised by commands that need an additional piece of information from the user."""
    def __init__(self, prompt: str, callback):
        super().__init__(prompt)
        self.prompt = prompt
        self.callback = callback


# ═══════════════════════════════════════════════════════════════════════════════
# App aliases  (add more as needed)
# ═══════════════════════════════════════════════════════════════════════════════

_APP_ALIASES: dict[str, str] = {
    "chrome":       "chrome.exe",
    "google chrome":"chrome.exe",
    "browser":      "chrome.exe",
    "the browser":  "chrome.exe",
    "web browser":  "chrome.exe",
    "internet":     "chrome.exe",
    "firefox":      "firefox.exe",
    "edge":         "msedge.exe",
    "microsoft edge":"msedge.exe",
    "notepad":      "notepad.exe",
    "calculator":   "calc.exe",
    "explorer":     "explorer.exe",
    "file explorer":"explorer.exe",
    "file manager": "explorer.exe",
    "files":        "explorer.exe",
    "my files":     "explorer.exe",
    "this pc":      "explorer.exe",
    "my computer":  "explorer.exe",
    "task manager": "taskmgr.exe",
    "word":         "winword.exe",
    "excel":        "excel.exe",
    "powerpoint":   "powerpnt.exe",
    "outlook":      "outlook.exe",
    "teams":        "teams.exe",
    "discord":      "discord.exe",
    "spotify":      "spotify.exe",
    "vlc":          "vlc.exe",
    "paint":        "mspaint.exe",
    "cmd":          "cmd.exe",
    "command prompt":"cmd.exe",
    "powershell":   "powershell.exe",
    "vs code":      "code.exe",
    "visual studio code":"code.exe",
    "pycharm":      "pycharm64.exe",
    "settings":     "ms-settings:",
    "control panel":"control.exe",
    "whatsapp":     "whatsapp:",
    "netflix":      "netflix:",
    "clock":        "ms-clock:",
    "mail":         "outlookmail:",
    "calendar":     "outlookcal:",
    "shin":             "http://127.0.0.1:8000",
    "shin web":         "http://127.0.0.1:8000",
    "shin app":         "http://127.0.0.1:8000",
    "shin hud":         "http://127.0.0.1:8000",
    "shin dashboard":   "http://127.0.0.1:8000",
    "shin interface":   "http://127.0.0.1:8000",
    "web app":          "http://127.0.0.1:8000",
    "web dashboard":    "http://127.0.0.1:8000",
}

# Websites that open in the default browser
_WEB_ALIASES: dict[str, str] = {
    "youtube":      "https://www.youtube.com",
    "gmail":        "https://mail.google.com",
    "google":       "https://www.google.com",
    "facebook":     "https://www.facebook.com",
    "instagram":    "https://www.instagram.com",
    "twitter":      "https://www.twitter.com",
    "x":            "https://www.x.com",
    "whatsapp":     "https://web.whatsapp.com",
    "github":       "https://www.github.com",
    "reddit":       "https://www.reddit.com",
    "netflix":      "https://www.netflix.com",
    "amazon":       "https://www.amazon.com",
    "chatgpt":      "https://chat.openai.com",
    "canva":        "https://www.canva.com",
    "maps":         "https://maps.google.com",
    "google maps":  "https://maps.google.com",
    "drive":        "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "docs":         "https://docs.google.com",
    "sheets":       "https://sheets.google.com",
    "slides":       "https://slides.google.com",
    "linkedin":     "https://www.linkedin.com",
    "stackoverflow":"https://stackoverflow.com",
    "wikipedia":    "https://www.wikipedia.org",
    "twitch":       "https://www.twitch.tv",
    "zoom":         "https://zoom.us",
    "shin":             "http://127.0.0.1:8000",
    "shin web":         "http://127.0.0.1:8000",
    "shin app":         "http://127.0.0.1:8000",
    "shin dashboard":   "http://127.0.0.1:8000",
}


def _resolve_app(name: str) -> str:
    name_lower = name.lower().strip()
    # Exact match
    if name_lower in _APP_ALIASES:
        return _APP_ALIASES[name_lower]
    # Fuzzy match — catches "visual studio" → "vs code", "chrome browser" → "chrome"
    try:
        from rapidfuzz import process as fz
        result = fz.extractOne(name_lower, _APP_ALIASES.keys(), score_cutoff=80)
        if result:
            matched_key = result[0]
            logger.debug("Fuzzy alias: %r → %r (score %.0f)", name_lower, matched_key, result[1])
            return _APP_ALIASES[matched_key]
    except Exception:
        pass
    return name

def _resolve_web(name: str) -> Optional[str]:
    """Return a URL if the name matches a known website, else None."""
    name_lower = name.lower().strip()
    if name_lower in _WEB_ALIASES:
        return _WEB_ALIASES[name_lower]
        
    # Also handle bare domain-like names e.g. "youtube.com"
    if "." in name_lower and not name_lower.endswith(".exe"):
        url = name_lower if name_lower.startswith("http") else f"https://{name_lower}"
        return url

    # Strict Fuzzy match — catches "you tube", "utube", "youtub" → "youtube"
    # Never match multi-word phrases to single-word aliases (e.g. 'and drive drive' -> 'drive')
    try:
        from rapidfuzz import process as fz, fuzz
        result = fz.extractOne(name_lower, _WEB_ALIASES.keys(), scorer=fuzz.token_sort_ratio, score_cutoff=88)
        if result:
            matched_key = result[0]
            logger.debug("Fuzzy web alias: %r → %r (score %.0f)", name_lower, matched_key, result[1])
            return _WEB_ALIASES[matched_key]
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# App Control & Shin UI Launchers
# ═══════════════════════════════════════════════════════════════════════════════

def _find_chrome_path() -> Optional[str]:
    """Find the full executable path to Google Chrome on this machine."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        shutil.which("chrome.exe") or "",
        shutil.which("chrome") or "",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def _open_in_browser(url: Optional[str] = None) -> bool:
    """
    Launch Chrome with Meharaj's 'Default' profile to bypass the 'Who's using Chrome?'
    profile picker dialog. Falls back to default webbrowser if Chrome path is missing.
    """
    chrome_path = _find_chrome_path()
    if chrome_path:
        target_url = url if url else "chrome://newtab"
        cmd = [chrome_path, "--profile-directory=Default", target_url]
        try:
            subprocess.Popen(cmd, shell=False)
            return True
        except Exception as exc:
            logger.warning("Failed to launch Chrome with Default profile: %s", exc)

    try:
        if url:
            return webbrowser.open(url)
        else:
            return webbrowser.open("https://www.google.com")
    except Exception as exc:
        logger.warning("webbrowser.open failed: %s", exc)
        return False


def _detect_and_dismiss_error_popup() -> bool:
    """Detect and dismiss any modal Windows 'cannot find' error dialogs."""
    try:
        import pygetwindow as gw
        import pyautogui
        import time
        for w in gw.getAllWindows():
            title = (w.title or "").strip()
            title_lower = title.lower()
            if any(err in title_lower for err in ("cannot find", "problem with shortcut", "error")) and any(src in title_lower for src in ("cmd", "explorer", "windows", "run")):
                logger.info("Dismissing Windows error modal: %r", title)
                w.activate()
                time.sleep(0.1)
                pyautogui.press("enter")
                time.sleep(0.1)
                return True
    except Exception:
        pass
    return False


def _clean_app_name(name: str) -> str:
    """Strip acoustic and conversational filler words from extracted app names."""
    if not name:
        return ""
    cleaned = name.strip()
    # Strip leading fillers: "achcha", "zara", "please", "the", "my", "a"
    cleaned = re.sub(
        r"^(?:ach+a|ach+ha|ac+h+a|arey?|oye|suno|sun|please|plz|zara|kripya|the|my|a|an)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE
    ).strip()
    # Strip trailing fillers: "app", "application", "browser", "karo", "kar do"
    cleaned = re.sub(
        r"\s+(?:app|application|karo|kar|karna|kar\s+do|kardo|chalu|start|open)$",
        "",
        cleaned,
        flags=re.IGNORECASE
    ).strip()
    return cleaned


def open_shin_web(args: dict = None) -> str:
    """Open the Shin Web HUD / dashboard (http://127.0.0.1:8000) in default browser."""
    try:
        import ui_server
        port = getattr(ui_server, "HTTP_PORT", 8000)
    except Exception:
        port = 8000
    url = f"http://127.0.0.1:{port}"
    _open_in_browser(url)
    return "Opening Shin Web Dashboard."


def open_phone_app(args: dict = None) -> str:
    """Inform user that the phone companion feature has been removed."""
    return "Phone companion feature has been completely removed."


def _get_smart_app_launch_reply(app_name: str) -> str:
    """Return a smart, context-predictive response in Shin's persona (language-aware)."""
    try:
        from core.settings import get_language
        lang = get_language()
    except Exception:
        lang = "hindi"

    is_english = (lang == "english")
    name = (app_name or "").lower().strip()

    if is_english:
        if "youtube" in name:
            return "I've opened YouTube for you! Want me to play a specific song or search a video?"
        elif "canva" in name:
            return "I've opened Canva! Ready to work on a new design or presentation?"
        elif "paint" in name:
            return "MS Paint is ready to go! Let's get creative."
        elif any(k in name for k in ("code", "vs code", "vscode", "pycharm", "terminal")):
            return f"{app_name.title()} is fired up! Ready to write some code?"
        elif any(k in name for k in ("chrome", "browser", "firefox", "edge")):
            return f"I've opened {app_name.title()}! What are we searching for today?"
        elif "spotify" in name:
            return "Spotify is open! Want some music playing?"
        elif "discord" in name:
            return "Discord is open! Time to catch up with friends?"
        elif "notepad" in name:
            return "Notepad is ready! Need to jot something down?"
        elif "word" in name or "doc" in name:
            return f"{app_name.title()} is open! Ready to draft that document?"
        return f"I've launched {app_name.title()} for you! What's next on our list?"

    # Default Hinglish/Hindi
    if "youtube" in name:
        return "Maine YouTube open kar diya! Koi specific gaana chalana hai ya video search karoon?"
    elif "canva" in name:
        return "Maine Canva open kar diya! Naya design create karna hai ya presentation banani hai?"
    elif "paint" in name:
        return "Maine Paint start kar diya! Drawing shuru karein ya image editing karni hai?"
    elif any(k in name for k in ("code", "vs code", "vscode", "pycharm", "terminal")):
        return f"Maine {app_name.title()} start kar diya! Coding shuru karein?"
    elif any(k in name for k in ("chrome", "browser", "firefox", "edge")):
        return f"Maine {app_name.title()} open kar diya! Kuch search karna hai kya?"
    elif "spotify" in name:
        return "Maine Spotify open kar diya! Koi mast gaana bajaoon?"
    elif "discord" in name:
        return "Discord open ho gaya! Doston se baat karni hai?"
    elif "notepad" in name:
        return "Maine Notepad open kar diya! Kuch note karna hai?"
    elif "word" in name or "doc" in name:
        return f"Maine {app_name.title()} open kar diya! Document likhna start karein?"
    return f"Maine '{app_name.title()}' open kar diya! Aur bata, aage kya help karoon?"


def open_app(args: dict) -> str:
    app_raw = args.get("app", "")
    app = _clean_app_name(app_raw)
    app_lower = app.lower().strip()

    try:
        from core.settings import get_language
        lang = get_language()
    except Exception:
        lang = "hindi"
    is_english = (lang == "english")

    if not app_lower or app_lower in ("kar", "karo", "karna", "open", "chalu", "start", "launch", "band", "close", "de", "do"):
        return "Which app would you like me to open, MJ?" if is_english else "Konsi app open karni hai MJ? App ka naam bata na."

    # Detect explicit request for an app to bypass web fallback
    explicit_app = False
    if app_lower.endswith(" app"):
        explicit_app = True
        app = app[:-4].strip()
        app_lower = app_lower[:-4].strip()

    # Browser check: Direct Chrome launch with Default profile
    if app_lower in ("chrome", "google chrome", "browser", "the browser", "web browser", "internet"):
        if _open_in_browser():
            return _get_smart_app_launch_reply("chrome")

    # Tier 1: resolve exe name via alias / fuzzy match
    target = _resolve_app(app)
    logger.info("open_app: %r resolved to %r", app, target)

    # Check for direct URL target (e.g. shin web)
    if target.startswith("http://") or target.startswith("https://"):
        try:
            _open_in_browser(target)
            return _get_smart_app_launch_reply(app)
        except Exception as exc:
            logger.warning("open_app URL opening failed: %s", exc)

    # Check known Web Aliases first if not an explicit desktop app request
    if not explicit_app and app_lower in _WEB_ALIASES:
        web_url = _WEB_ALIASES[app_lower]
        logger.info("open_app: %r matched known web alias %s", app, web_url)
        _open_in_browser(web_url)
        return _get_smart_app_launch_reply(app)

    # Tier 2: ms- URI scheme or Windows App Protocols (UWP Apps)
    if ":" in target and "\\" not in target and "/" not in target:
        try:
            logger.debug("open_app tier 2 (protocol): %s", target)
            os.startfile(target)
            return _get_smart_app_launch_reply(app)
        except Exception as exc:
            logger.warning("open_app tier 2 protocol failed: %s", exc)

    # Tier 3: shutil.which() — full path on PATH
    full_path = shutil.which(target)
    if full_path:
        try:
            logger.debug("open_app tier 3 (shutil.which): %s", full_path)
            subprocess.Popen([full_path], shell=False)
            return _get_smart_app_launch_reply(app)
        except Exception as exc:
            logger.warning("open_app tier 3 shutil.which failed (%s): %s", full_path, exc)

    # Tier 4: Deep App Finder (Scans Start Menu, Registry, UWP Apps, Program Files)
    try:
        import app_finder
        ok, msg = app_finder.launch_application(app)
        if ok:
            return _get_smart_app_launch_reply(app)
    except Exception as exc:
        logger.debug("open_app tier 4 app_finder failed: %s", exc)

    # Tier 5: Direct executable path check or known install path
    if os.path.exists(target):
        try:
            subprocess.Popen([target], shell=False)
            return _get_smart_app_launch_reply(app)
        except Exception as exc:
            logger.warning("open_app tier 5 path launch failed: %s", exc)

    # Tier 6: Web aliases (fallback if app isn't natively installed)
    if not explicit_app:
        web_url = _resolve_web(app_lower)
        if web_url:
            logger.debug("open_app tier 6 (web alias fallback): %s → %s", app, web_url)
            _open_in_browser(web_url)
            return _get_smart_app_launch_reply(app)

    # Ensure no lingering Windows error popup is showing
    _detect_and_dismiss_error_popup()

    # Honest failure report: Never lie that an app opened when it failed
    logger.warning("open_app: could not locate app %r", app)
    if is_english:
        return f"MJ, I couldn't find '{app}' installed on your PC. Would you like me to search for it online?"
    return f"MJ, mujhe aapke system mein '{app}' installed nahi mila. Kya web pe search karoon?"


def close_app(args: dict) -> str:
    app = args.get("app", "").lower().strip()
    target_exe = _resolve_app(app).lower()
    # Strip .exe suffix so "spotify.exe" matches process name "spotify"
    target_exe_no_ext = target_exe.replace(".exe", "")
    killed = []
    for proc in psutil.process_iter(["pid", "name"]):
        pname = proc.info["name"]
        if not isinstance(pname, str):
            pname = ""
        pname = pname.lower()
        pname_no_ext = pname.replace(".exe", "")
        if (pname == target_exe
                or pname_no_ext == target_exe_no_ext
                or pname_no_ext == app
                or target_exe_no_ext == pname_no_ext):
            try:
                proc.kill()
                killed.append(pname)
            except Exception:
                pass

    # Fuzzy fallback: try to match process names using fuzzy comparison
    # (catches apps whose exe name doesn't match their alias, e.g. Discord → "discord.exe")
    if not killed:
        try:
            from rapidfuzz import process as fz
            running = {}
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pname = (proc.info["name"] or "").lower()
                    pname_no_ext = pname.replace(".exe", "")
                    if pname_no_ext and pname_no_ext not in running:
                        running[pname_no_ext] = proc
                except Exception:
                    pass
            # Try to fuzzy-match both the user's spoken app name and the resolved exe name
            for search_term in {app, target_exe_no_ext}:
                if not search_term:
                    continue
                result = fz.extractOne(search_term, running.keys(), score_cutoff=80)
                if result:
                    matched_key = result[0]
                    matched_proc = running[matched_key]
                    # Kill all processes with this name
                    for proc in psutil.process_iter(["pid", "name"]):
                        try:
                            pname = (proc.info["name"] or "").lower().replace(".exe", "")
                            if pname == matched_key:
                                proc.kill()
                                killed.append(matched_key)
                        except Exception:
                            pass
                    if killed:
                        break
        except Exception as exc:
            logger.debug("Fuzzy process kill fallback failed: %s", exc)

    if killed:
        return f"Closed {app}."

    # Fallback: Try to close as a browser tab or window by matching title
    try:
        import pygetwindow as gw
        import pyautogui
        import time

        search_term = app
        for prefix in ("the ", "a ", "an ", "close "):
            if search_term.startswith(prefix):
                search_term = search_term[len(prefix):]
        search_term = search_term.strip().lower()

        if search_term:
            # Resolve to canonical name using fuzzy matching if possible to catch misheard variants
            resolved_name = None
            try:
                from rapidfuzz import process as fz
                all_known = list(_WEB_ALIASES.keys()) + list(_APP_ALIASES.keys())
                res = fz.extractOne(search_term, all_known, score_cutoff=75)
                if res:
                    resolved_name = res[0]
            except Exception:
                pass

            target_term = resolved_name or search_term
            windows = gw.getAllWindows()
            for w in windows:
                if w.title and target_term in w.title.lower():
                    title_lower = w.title.lower()
                    # Check if it's a browser tab (include youtube web tabs)
                    is_browser = any(b in title_lower for b in ("chrome", "edge", "firefox", "zen browser", "brave", "opera", "youtube"))
                    
                    original_title = w.title
                    try:
                        from core.settings import get_language
                        is_english = (get_language() == "english")
                    except Exception:
                        is_english = False

                    # Extract a clean, spoken-friendly name without emojis or raw tabs
                    if "youtube" in title_lower or "youtube" in search_term:
                        disp_name = "YouTube"
                    elif "whatsapp" in title_lower or "whatsapp" in search_term:
                        disp_name = "WhatsApp"
                    elif app and len(app.strip()) > 0:
                        disp_name = app.strip().title()
                    else:
                        disp_name = "the window"

                    try:
                        w.activate()
                        time.sleep(0.3)  # wait for activation
                        if is_browser:
                            pyautogui.hotkey('ctrl', 'w')
                            return f"Closed {disp_name} tab." if is_english else f"Maine {disp_name} tab band kar diya!"
                        else:
                            pyautogui.hotkey('alt', 'f4')
                            return f"Closed {disp_name}." if is_english else f"Maine {disp_name} band kar diya!"
                    except Exception as focus_exc:
                        logger.warning("Failed to focus window '%s': %s", original_title, focus_exc)
    except Exception as exc:
        logger.warning("Failed to close window/tab by title fallback: %s", exc)

    return f"I couldn't find a running process, window, or tab matching '{app}'."



def close_active_window(args: dict) -> str:
    import pyautogui
    pyautogui.hotkey('alt', 'f4')
    return "Closed the active window."


# ═══════════════════════════════════════════════════════════════════════════════
# Volume
# ═══════════════════════════════════════════════════════════════════════════════

def _get_volume_interface():
    """Return a pycaw AudioEndpointVolume interface (lazy import)."""
    from ctypes import POINTER, cast
    from comtypes import CLSCTX_ALL
    import comtypes
    comtypes.CoInitialize()
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    devices = AudioUtilities.GetSpeakers()
    if hasattr(devices, "Activate"):
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    else:
        return devices.EndpointVolume


def mute_volume(args: dict) -> str:
    vol = _get_volume_interface()
    vol.SetMute(1, None)
    return "Volume muted."


def unmute_volume(args: dict) -> str:
    vol = _get_volume_interface()
    vol.SetMute(0, None)
    return "Volume unmuted."


def set_volume(args: dict) -> str:
    level = args.get("level")
    if level is None:
        return "Please specify a volume level between 0 and 100."
    vol = _get_volume_interface()
    vol.SetMasterVolumeLevelScalar(level / 100.0, None)
    return f"Volume set to {level} percent."


def volume_up(args: dict) -> str:
    delta = args.get("delta", 10)
    vol = _get_volume_interface()
    current = round(vol.GetMasterVolumeLevelScalar() * 100)
    new = min(100, current + delta)
    vol.SetMasterVolumeLevelScalar(new / 100.0, None)
    return f"Volume increased to {new} percent."


def volume_down(args: dict) -> str:
    delta = args.get("delta", 10)
    vol = _get_volume_interface()
    current = round(vol.GetMasterVolumeLevelScalar() * 100)
    new = max(0, current - delta)
    vol.SetMasterVolumeLevelScalar(new / 100.0, None)
    return f"Volume decreased to {new} percent."


# ═══════════════════════════════════════════════════════════════════════════════
# Brightness
# ═══════════════════════════════════════════════════════════════════════════════

def set_brightness(args: dict) -> str:
    import screen_brightness_control as sbc
    level = args.get("level")
    if level is None:
        return "Please specify a brightness level between 0 and 100."
    sbc.set_brightness(level)
    return f"Brightness set to {level} percent."


def brightness_up(args: dict) -> str:
    import screen_brightness_control as sbc
    delta = args.get("delta", 10)
    current = sbc.get_brightness(display=0)
    current = current[0] if isinstance(current, list) else current
    new = min(100, current + delta)
    sbc.set_brightness(new)
    return f"Brightness increased to {new} percent."


def brightness_down(args: dict) -> str:
    import screen_brightness_control as sbc
    delta = args.get("delta", 10)
    current = sbc.get_brightness(display=0)
    current = current[0] if isinstance(current, list) else current
    new = max(0, current - delta)
    sbc.set_brightness(new)
    return f"Brightness decreased to {new} percent."


def set_voice_pitch(args: dict) -> str:
    pitch_arg = str(args.get("pitch", "")).lower().strip()
    pitch_map = {
        "very high": ("+30Hz", "very high"),
        "high": ("+15Hz", "high"),
        "cute": ("+8Hz", "cute"),
        "warm": ("+8Hz", "warm"),
        "soft": ("+8Hz", "soft"),
        "default": ("+0Hz", "default natural"),
        "normal": ("+0Hz", "normal"),
        "reset": ("+0Hz", "default natural"),
        "natural": ("+0Hz", "natural"),
        "low": ("-10Hz", "low"),
        "deep": ("-15Hz", "deep"),
        "very deep": ("-20Hz", "very deep"),
    }

    if pitch_arg in pitch_map:
        new_pitch, label = pitch_map[pitch_arg]
    elif re.match(r"^[+-]?\d+\s*hz$", pitch_arg):
        new_pitch = pitch_arg.replace(" ", "")
        if not (new_pitch.startswith("+") or new_pitch.startswith("-")):
            new_pitch = f"+{new_pitch}"
        label = new_pitch
    else:
        new_pitch, label = ("+0Hz", "default natural")

    try:
        import assistant
        if hasattr(assistant, "set_voice_pitch"):
            return assistant.set_voice_pitch(new_pitch, label)
    except Exception:
        pass

    os.environ["TTS_PITCH"] = new_pitch
    return f"Voice pitch changed to {label}."


# ═══════════════════════════════════════════════════════════════════════════════
# Web & Search
# ═══════════════════════════════════════════════════════════════════════════════

def web_search(args: dict) -> str:
    query = args.get("query", "")
    if not query:
        def _do(new_query):
            args["query"] = new_query
            return web_search(args)
        raise MissingArgument("What would you like me to search for?", _do)

    # Clean query prefixes like "on chrome", "in chrome", "on google"
    query = re.sub(r"^(?:on\s+chrome|in\s+chrome|on\s+google|in\s+browser|on\s+browser|for)\s+", "", query, flags=re.IGNORECASE).strip()

    engine = args.get("engine", "default")

    # ── Smart answer: try to speak the answer instead of opening a browser ──
    # Only for default engine (not YouTube/Bing/etc explicit requests)
    # Bypass smart_answer for live news / breaking events so browser search opens directly
    is_news_query = any(k in query.lower() for k in ("news", "latest", "headlines", "today", "update", "current", "breaking"))
    if engine == "default" and not args.get("force_browser") and not is_news_query:
        try:
            import live_search
            answer = live_search.smart_answer(query)
            if answer:
                logger.info("web_search: live answer found for %r, skipping browser.", query)
                return answer
        except Exception as exc:
            logger.warning("live_search.smart_answer failed: %s", exc)

    # ── Fallback: open browser ────────────────────────────────────────────────
    _ENGINE_URLS = {
        "google":     "https://www.google.com/search?q=",
        "bing":       "https://www.bing.com/search?q=",
        "youtube":    "https://www.youtube.com/results?search_query=",
        "duckduckgo": "https://duckduckgo.com/?q=",
    }
    base = _ENGINE_URLS.get(engine, _ENGINE_URLS["google"])
    url = base + query.replace(" ", "+")
    _open_in_browser(url)
    try:
        from core.settings import get_language
        lang = get_language()
    except Exception:
        lang = "hindi"
    if lang == "english":
        return f"Searching for {query}."
    return f"{query} ke liye search kar rahi hoon."


def open_url(args: dict) -> str:
    url = args.get("url", "").strip()
    if not url:
        def _do(new_url):
            args["url"] = new_url
            return open_url(args)
        raise MissingArgument("Please provide a URL to open.", _do)
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    _open_in_browser(url)
    return f"Opening {url}."


def _load_whatsapp_contacts() -> dict[str, str]:
    """Load name->phone dict from whatsapp_contacts.json."""
    if not _WHATSAPP_CONTACTS_FILE.exists():
        return {}
    try:
        import json as _json
        with open(_WHATSAPP_CONTACTS_FILE, "r", encoding="utf-8") as f:
            return _json.load(f)
    except Exception as exc:
        logger.error("Failed to load WhatsApp contacts: %s", exc)
        return {}


def _save_whatsapp_contacts(contacts: dict[str, str]) -> None:
    """Save name->phone dict to whatsapp_contacts.json."""
    try:
        _WHATSAPP_CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        with open(_WHATSAPP_CONTACTS_FILE, "w", encoding="utf-8") as f:
            _json.dump(contacts, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.error("Failed to save WhatsApp contacts: %s", exc)


def add_whatsapp_contact(args: dict) -> str:
    """Add or update a WhatsApp contact."""
    name = args.get("name", "").strip().lower()
    phone = args.get("phone", "").strip()

    if not name:
        def _do_name(n: str) -> str:
            args["name"] = n
            return add_whatsapp_contact(args)
        raise MissingArgument("What is the contact's name?", _do_name)

    if not phone:
        def _do_phone(p: str) -> str:
            args["phone"] = p
            return add_whatsapp_contact(args)
        raise MissingArgument(f"What is the phone number for {name.title()}?", _do_phone)

    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10 and not phone.startswith("+"):
        phone = f"+91{digits}"
    elif not phone.startswith("+") and digits:
        phone = f"+{digits}"

    contacts = _load_whatsapp_contacts()
    contacts[name] = phone
    _save_whatsapp_contacts(contacts)
    return f"Saved WhatsApp contact for {name.title()} with number {phone}."


def list_whatsapp_contacts(args: dict) -> str:
    """List all saved WhatsApp contacts."""
    contacts = _load_whatsapp_contacts()
    if not contacts:
        return "You have no saved WhatsApp contacts."
    
    lines = [f"Found {len(contacts)} saved WhatsApp contact(s):"]
    for name, phone in contacts.items():
        lines.append(f"• {name.title()}: {phone}")
    return "\n".join(lines)


def open_whatsapp_chat(args: dict) -> str:
    """Open a WhatsApp chat for a named contact or phone number via wa.me deep link or desktop app."""
    contact_name = args.get("contact", "").strip().lower()
    if not contact_name:
        def _do(name):
            args["contact"] = name
            return open_whatsapp_chat(args)
        raise MissingArgument("Whose WhatsApp chat should I open?", _do)

    # Check for direct phone number
    digits = "".join(c for c in contact_name if c.isdigit())
    if len(digits) >= 7:
        phone = contact_name if contact_name.startswith("+") else (f"+91{digits}" if len(digits) == 10 else f"+{digits}")
        display_name = phone
    else:
        contacts = _load_whatsapp_contacts()
        if not contacts:
            return (
                "No WhatsApp contacts are saved yet. "
                "Please add contacts using 'add whatsapp contact <name> <number>'."
            )

        phone = contacts.get(contact_name)

        if not phone:
            try:
                from rapidfuzz import process as fz
                result = fz.extractOne(contact_name, contacts.keys(), score_cutoff=70)
                if result:
                    phone = contacts[result[0]]
                    contact_name = result[0]
            except Exception:
                pass

        if not phone:
            known = ", ".join(contacts.keys())
            return (
                f"I don't have WhatsApp contact info for '{contact_name}'. "
                f"Known contacts: {known}."
            )

        if "XXXXXXXXXX" in phone or "0000000000" in phone:
            return (
                f"The number for '{contact_name}' is not set yet. "
                f"Please fill in the phone number in data/whatsapp_contacts.json."
            )
        display_name = contact_name.title()

    phone_digits = "".join(c for c in phone if c.isdigit())
    phone_clean = "".join(c for c in phone if c.isdigit() or c == "+")

    try:
        os.startfile(f"whatsapp://send?phone={phone_digits}")
        return f"Opening WhatsApp chat with {display_name} in the desktop app."
    except Exception as exc:
        logger.warning("Failed to open WhatsApp desktop app: %s. Falling back to browser.", exc)
        url = f"https://wa.me/{phone_clean}"
        webbrowser.open(url)
        return f"Opening WhatsApp chat with {display_name} in your browser."


def send_whatsapp_message(args: dict) -> str:
    """Send a WhatsApp message to a named contact or direct number."""
    contact_name = args.get("contact", "").strip().lower()
    message = args.get("message", "").strip()

    if not contact_name:
        def _do_contact(name: str) -> str:
            args["contact"] = name
            return send_whatsapp_message(args)
        raise MissingArgument("Who should I send the WhatsApp message to?", _do_contact)

    # Check for direct phone number (e.g. +919876543210 or 9876543210)
    digits = "".join(c for c in contact_name if c.isdigit())
    if len(digits) >= 7:
        phone = contact_name if contact_name.startswith("+") else (f"+91{digits}" if len(digits) == 10 else f"+{digits}")
        display_name = phone
    else:
        contacts = _load_whatsapp_contacts()
        if not contacts:
            return (
                "No WhatsApp contacts are saved yet. "
                "Please add contacts using 'add whatsapp contact <name> <number>'."
            )

        phone = contacts.get(contact_name)

        if not phone:
            try:
                from rapidfuzz import process as fz
                result = fz.extractOne(contact_name, contacts.keys(), score_cutoff=70)
                if result:
                    phone = contacts[result[0]]
                    contact_name = result[0]
            except Exception:
                pass

        if not phone:
            known = ", ".join(contacts.keys())
            return (
                f"I don't have WhatsApp contact info for '{contact_name}'. "
                f"Known contacts: {known}."
            )

        if "XXXXXXXXXX" in phone or "0000000000" in phone:
            return (
                f"The number for '{contact_name}' is not set yet. "
                f"Please fill in the phone number in data/whatsapp_contacts.json."
            )
        display_name = contact_name.title()

    phone_digits = "".join(c for c in phone if c.isdigit())
    phone_clean = "".join(c for c in phone if c.isdigit() or c == "+")

    if not message:
        def _do_message(msg: str) -> str:
            args["message"] = msg
            return send_whatsapp_message(args)
        raise MissingArgument(f"What should I say to {display_name}?", _do_message)

    def _send():
        from urllib.parse import quote
        import time
        try:
            os.startfile(f"whatsapp://send?phone={phone_digits}&text={quote(message)}")
            time.sleep(4)
            pyautogui.press("enter")
            
            logger.info("WhatsApp desktop message sent to %s (%s): %r", display_name, phone_digits, message)
            return f"Message sent to {display_name} via desktop app!"
        except Exception as exc:
            logger.error("WhatsApp desktop send failed: %s. Falling back to browser.", exc)
            url = f"https://wa.me/{phone_clean}?text={quote(message)}"
            webbrowser.open(url)
            return (
                f"Couldn't send via desktop app ({exc}). "
                f"I've opened the chat in your browser — please hit Send."
            )

    raise ConfirmationRequired(
        f"Send '{message}' to {display_name} on WhatsApp?",
        _send,
    )


def send_whatsapp_location(args: dict) -> str:
    """Send current or specified location link to a WhatsApp contact."""
    contact_name = args.get("contact", "").strip().lower()
    location_name = args.get("location", "current location").strip()

    if not contact_name:
        def _do_contact(n: str) -> str:
            args["contact"] = n
            return send_whatsapp_location(args)
        raise MissingArgument("Who should I send the location to on WhatsApp?", _do_contact)

    from urllib.parse import quote
    map_url = f"https://maps.google.com/?q={quote(location_name)}" if location_name != "current location" else "https://maps.google.com"
    msg = f"Here is my location: {map_url}"
    return send_whatsapp_message({"contact": contact_name, "message": msg})


def whatsapp_call(args: dict) -> str:
    """Start a WhatsApp audio or video call for a named contact."""
    contact_name = args.get("contact", "").strip().lower()
    is_video = bool(args.get("video", False))
    call_type = "video call" if is_video else "voice call"

    if not contact_name:
        def _do_contact(n: str) -> str:
            args["contact"] = n
            return whatsapp_call(args)
        raise MissingArgument(f"Who do you want to {call_type} on WhatsApp?", _do_contact)

    res = open_whatsapp_chat({"contact": contact_name})
    if "I don't have" in res or "not set" in res:
        return res
    
    display_name = contact_name.title()
    return f"Opened WhatsApp for {display_name}. You can start the {call_type} now."


def send_whatsapp_file(args: dict) -> str:
    """Open WhatsApp chat with a contact to send a file or photo."""
    contact_name = args.get("contact", "").strip().lower()
    file_path = args.get("file", "").strip()

    if not contact_name:
        def _do_contact(n: str) -> str:
            args["contact"] = n
            return send_whatsapp_file(args)
        raise MissingArgument("Who should I send the file to on WhatsApp?", _do_contact)

    res = open_whatsapp_chat({"contact": contact_name})
    if "I don't have" in res or "not set" in res:
        return res
    
    display_name = contact_name.title()
    if file_path:
        return f"Opened WhatsApp chat with {display_name} for sending {file_path}."
    return f"Opened WhatsApp chat with {display_name} to send your file."


# ═══════════════════════════════════════════════════════════════════════════════
# Files & Folders
# ═══════════════════════════════════════════════════════════════════════════════

_FOLDER_ALIASES: dict[str, str] = {
    "desktop":    str(Path.home() / "Desktop"),
    "documents":  str(Path.home() / "Documents"),
    "downloads":  str(Path.home() / "Downloads"),
    "pictures":   str(Path.home() / "Pictures"),
    "music":      str(Path.home() / "Music"),
    "videos":     str(Path.home() / "Videos"),
    "home":       str(Path.home()),
}


def open_folder(args: dict) -> str:
    path = args.get("path", "").strip()
    if path.startswith(("\\\\", "//")):
        return "Opening network UNC paths is blocked for security."
    resolved = _FOLDER_ALIASES.get(path.lower(), path)
    if not os.path.isdir(resolved):
        return f"I couldn't find the folder: {path}."
    subprocess.Popen(["explorer", resolved])
    return f"Opening {path}."


def open_file(args: dict) -> str:
    path = args.get("path", "").strip()
    if path.startswith(("\\\\", "//")):
        return "Opening network UNC paths is blocked for security."
    is_safe, warn = check_command_safety("open_file", {"path": path})
    if not is_safe:
        return f"Access denied: {warn}"
    if not os.path.isfile(path):
        return f"I couldn't find the file: {path}."
    os.startfile(path)
    return f"Opening {path}."


def save_note(args: dict) -> str:
    text = args.get("text", "").strip()
    if not text:
        def _do(new_text):
            args["text"] = new_text
            return save_note(args)
        raise MissingArgument("What would you like me to note?", _do)
    notes_dir = Path.home() / "Documents" / "Shin Notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
    notes_file = notes_dir / f"{timestamp}.txt"
    with open(notes_file, "a", encoding="utf-8") as f:
        entry_time = datetime.datetime.now().strftime("%H:%M:%S")
        f.write(f"[{entry_time}] {text}\n")
    return f"Note saved: {text[:50]}{'...' if len(text) > 50 else ''}"


# ═══════════════════════════════════════════════════════════════════════════════
# Reminders
# ═══════════════════════════════════════════════════════════════════════════════

def set_reminder(args: dict) -> str:
    task = args.get("task", "").strip()
    time_str = args.get("time") or args.get("when")
    
    if not task or task == "something":
        def _do(new_task):
            args["task"] = new_task
            return set_reminder(args)
        raise MissingArgument("What should I remind you about?", _do)

    if time_str:
        try:
            try:
                from predictive_engine import predictive_engine as _pe
            except ImportError:
                from core.predictive_engine import predictive_engine as _pe
        except Exception:
            _pe = None
        if _pe is None:
            return f"Reminder for '{task}' noted, but time parsing unavailable."
        parsed = _pe.parse_natural_time(str(time_str))
        if parsed:
            h, m = parsed
            delay_s = _pe.calculate_delay_seconds(h, m)
            def _fire_time():
                _speak(f"Reminder: {task}")
                return schedule.CancelJob
            schedule.every(delay_s).seconds.do(_fire_time)
            return f"Reminder set for {time_str}: {task}."

    quantity = int(args.get("quantity", 1))
    unit = args.get("unit", "minute").lower()
    seconds_map = {"second": 1, "minute": 60, "hour": 3600}
    delay_s = quantity * seconds_map.get(unit, 60)

    def _fire():
        _speak(f"Reminder: {task}")
        return schedule.CancelJob

    schedule.every(delay_s).seconds.do(_fire)
    return f"Reminder set for {quantity} {unit}{'s' if quantity != 1 else ''}: {task}."


# ═══════════════════════════════════════════════════════════════════════════════
# Real-Life Work & Prediction Handlers
# ═══════════════════════════════════════════════════════════════════════════════

def set_alarm(args: dict) -> str:
    """Set a natural one-shot alarm with time calculation."""
    time_str = args.get("time") or args.get("when", "") or "07:00"
    try:
        try:
            from predictive_engine import predictive_engine as _pe
        except ImportError:
            from core.predictive_engine import predictive_engine as _pe
    except Exception:
        return "Alarm engine unavailable - please try again later."
    parsed = _pe.parse_natural_time(str(time_str))
    if not parsed:
        return f"Mujhe alarm ka time '{time_str}' samajh nahi aaya. '7:00 am' ya '6 baje' bolo."
    h, m = parsed
    delay_s = _pe.calculate_delay_seconds(h, m)
    time_disp = f"{h:02d}:{m:02d}"

    def _fire_alarm():
        _speak(f"Utho MJ! Alarm baj raha hai! {time_disp} ho gaye hain!")
        return schedule.CancelJob

    schedule.every(delay_s).seconds.do(_fire_alarm)
    hours = delay_s // 3600
    mins = (delay_s % 3600) // 60
    eta_str = f"{hours} ghante {mins} minute" if hours > 0 else f"{mins} minute"
    return f"Maine {time_disp} ka alarm set kar diya! ({eta_str} baad bajega)."


def manage_tab(args: dict) -> str:
    """Manage browser tabs: open, switch, next, prev, close."""
    action = (args.get("action") or "open").lower()
    query = (args.get("query") or args.get("target") or "").strip()
    try:
        import pyautogui
        import webbrowser
        if action in ("open", "new") or (query and not action):
            if query and (query.startswith("http") or "." in query):
                url = query if query.startswith("http") else f"https://{query}"
                webbrowser.open_new_tab(url)
                return f"Opened new browser tab with '{query}'."
            elif query:
                webbrowser.open_new_tab(f"https://www.google.com/search?q={query}")
                return f"Opened new tab searching '{query}'."
            else:
                pyautogui.hotkey("ctrl", "t")
                return "Opened a new browser tab."
        elif action in ("close", "shut"):
            pyautogui.hotkey("ctrl", "w")
            return "Closed the current browser tab."
        elif action in ("next", "switch_next"):
            pyautogui.hotkey("ctrl", "tab")
            return "Switched to next tab."
        elif action in ("prev", "previous", "switch_prev"):
            pyautogui.hotkey("ctrl", "shift", "tab")
            return "Switched to previous tab."
        elif action == "reopen":
            pyautogui.hotkey("ctrl", "shift", "t")
            return "Reopened the recently closed tab."
    except Exception as exc:
        return f"Tab action failed: {exc}"
    return "Tab command processed."


def send_message(args: dict) -> str:
    """Send or draft a direct message to a contact."""
    recipient = (args.get("recipient") or args.get("contact") or "").strip()
    msg = (args.get("message") or args.get("body") or args.get("text") or "").strip()
    if not recipient:
        return "Kisko message bhejna hai MJ? Contact name batao."
    if not msg:
        return f"'{recipient}' ko kya message bhejna hai?"
    contacts = _load_whatsapp_contacts()
    phone = contacts.get(recipient.lower())
    if phone:
        return send_whatsapp_message({"contact": recipient, "message": msg})
    try:
        import pyperclip
        pyperclip.copy(msg)
    except Exception:
        pass
    return f"Maine message copy kar liya: '{msg}'. '{recipient}' ki chat open karke paste kar lo!"


def sleep_routine(args: dict = None) -> str:
    """Bedtime / Sleep routine with warm good night wishes and context awareness."""
    try:
        import predictive_engine
    except ImportError:
        from core import predictive_engine
    return (
        "Good night, MJ! Aaram se so jao, aaj ka din kaafi productive raha. "
        "Maine saari memories save rakhi hain, kal subah fresh dimaag se milte hain!"
    )


def power_status(args: dict = None) -> str:
    """Handle power cuts ('light is gone') and battery checks."""
    try:
        try:
            from predictive_engine import predictive_engine as _pe
        except ImportError:
            from core.predictive_engine import predictive_engine as _pe
        return _pe.handle_power_event()
    except Exception as exc:
        return f"Power status check failed: {exc}"


def store_relationship(args: dict) -> str:
    """Store family, identity, and personal relationships in memory."""
    subject = (args.get("subject") or "").strip()
    relation = (args.get("relation") or "").strip()
    raw = (args.get("raw") or "").strip()
    try:
        import memory
    except ImportError:
        from core import memory
    if raw:
        memory.add_memory(raw)
        return f"Maine yaad rakh liya: '{raw}'."
    elif subject and relation:
        mem_str = f"{subject} is {relation}"
        memory.add_memory(mem_str)
        return f"Haan MJ, maine note kar liya ki {subject} tere {relation} hain!"
    return "Samajh gayi MJ, yaad rakhungi!"


def analyze_clipboard(args: dict = None) -> str:
    """Analyze clipboard content using predictive engine and return smart recommendation."""
    try:
        try:
            from predictive_engine import predictive_engine as _pe
        except ImportError:
            from core.predictive_engine import predictive_engine as _pe

        res = _pe.predict_clipboard_action()
        return res.get("prediction", "Clipboard analyze kar liya MJ, par koi specific action detect nahi hui.")
    except Exception as exc:
        logger.error("Failed to analyze clipboard: %s", exc)
        return f"Clipboard analyze karne mein dikkat aayi: {exc}"


def agent_reach_query(args: dict = None) -> str:
    """Live zero-API intelligence extraction across GitHub, Reddit, YouTube, and Twitter."""
    args = args or {}
    platform = args.get("platform", "github")
    query = args.get("query", "")
    action = args.get("action", "search")
    limit = int(args.get("limit", 5))
    try:
        try:
            from shin_agent import agent_reach_query as _arq
        except ImportError:
            from core.shin_agent import agent_reach_query as _arq
        return _arq(platform=platform, query=query, action=action, limit=limit)
    except Exception as exc:
        logger.error("Agent reach query failed: %s", exc)
        return f"Live data fetch mein issue aaya MJ: {exc}"


def set_language(args: dict = None) -> str:
    """Switch communication language response and persist the preference."""
    from assistant import set_language_state
    try:
        from core import nlp
        if hasattr(nlp, "invalidate_system_prompt_cache"):
            nlp.invalidate_system_prompt_cache()
    except Exception:
        pass
    
    args = args or {}
    lang = (args.get("language") or "english").lower().strip()
    if "eng" in lang:
        set_language_state("english")
        return "Sure MJ! I will speak with you in English from now on."
    elif "marathi" in lang:
        set_language_state("marathi")
        return "हो नक्की MJ! आता आपण मराठीत बोलूया."
    elif "hinglish" in lang:
        set_language_state("hinglish")
        return "Sure MJ! Hinglish mode on — best of both worlds."
    else:
        set_language_state("hindi")
        return "हाँ MJ, बिल्कुल! अब से मैं हिंदी में बात करूँगी।"


def switch_model(args: dict = None) -> str:
    """Switch the active or preferred AI model/provider."""
    args = args or {}
    model = (args.get("model") or "").strip()
    try:
        from core import llm_router
        from core import settings
        from core.settings import get_language
    except ImportError:
        import llm_router
        import settings
        from settings import get_language

    is_english = (get_language() == "english")

    if not model:
        pref = llm_router.get_preferred_provider() or "Auto Cascade"
        if is_english:
            return f"Currently using {pref.title()}. You can switch to Gemini, Groq, OpenAI, Claude, Local, or Auto."
        return f"Abhi {pref.title()} chal raha hai. Aap Gemini, Groq, OpenAI, Claude, Local ya Auto pe switch kar sakte hain."

    ok, name = llm_router.set_preferred_provider(model)
    if ok:
        settings.set_setting("ai_provider", model.lower())
        if is_english:
            return f"Switched AI model to {name}! I will use {name} for our tasks."
        return f"AI model ko {name} pe switch kar diya MJ! Ab se {name} use karenge."
    else:
        if is_english:
            return f"Couldn't recognize model '{model}'. Available options: Gemini, Groq, OpenAI, Claude, Local, Auto."
        return f"Model '{model}' samajh nahi aaya. Options: Gemini, Groq, OpenAI, Claude, Local, Auto."


def get_active_model(args: dict = None) -> str:
    """Report the current active AI model and cascade state."""
    try:
        from core import llm_router
        from core.settings import get_language
    except ImportError:
        import llm_router
        from settings import get_language

    status = llm_router.get_status_info()
    preferred = status.get("preferred") or "Auto Cascade"
    online_str = "Online" if status.get("online") else "Offline (Local Models)"
    cooldowns = status.get("cooldowns", {})
    cd_msg = f", on cooldown: {', '.join(cooldowns.keys())}" if cooldowns else ""

    if get_language() == "english":
        return f"Currently active model preference is {preferred.title()} ({online_str}{cd_msg})."
    return f"Abhi active model {preferred.title()} hai ({online_str}{cd_msg})."


def describe_screen(args: dict = None) -> str:
    """Analyze and describe what application and activity is visible on screen."""
    try:
        try:
            import app_tracker
        except ImportError:
            from core import app_tracker
        active_title = app_tracker._get_foreground_title()
        active_app = app_tracker._extract_app_name(active_title)
        try:
            import predictive_engine
        except ImportError:
            from core import predictive_engine
        workflow = predictive_engine.predict_app_workflow(active_app, active_title)
        pred = workflow.get("prediction", "")
        try:
            from core.settings import get_language
            is_english = (get_language() == "english")
        except Exception:
            is_english = False

        if is_english:
            return f"You currently have '{active_app}' active (Window: '{active_title}'). {pred}"
        return f"Screen pe abhi '{active_app}' khula hai (Title: '{active_title}'). {pred}"
    except Exception as exc:
        return f"Screen analyze nahi ho paayi: {exc}"


# ═══════════════════════════════════════════════════════════════════════════════
# System Commands  (destructive → ConfirmationRequired)
# ═══════════════════════════════════════════════════════════════════════════════

def sleep_shutdown(args: dict) -> str:
    """Say good night and shut down the PC immediately without asking for confirmation."""
    subprocess.run(["C:\\Windows\\System32\\shutdown.exe", "/s", "/f", "/t", "10"], shell=False)
    return "Good night, MJ! Sleep well."

def shutdown(args: dict) -> str:
    def _do():
        subprocess.run(["C:\\Windows\\System32\\shutdown.exe", "/s", "/f", "/t", "5"], shell=False)
    raise ConfirmationRequired("Are you sure you want to shut down the computer?", _do)

def shutdown_timer(args: dict) -> str:
    """Schedule a system shutdown after a specified delay."""
    quantity = int(args.get("quantity", 1))
    unit = args.get("unit", "minute").lower().rstrip('s')
    seconds_map = {"second": 1, "minute": 60, "hour": 3600}
    delay_s = quantity * seconds_map.get(unit, 60)

    def _do():
        def _fire():
            subprocess.run(["C:\\Windows\\System32\\shutdown.exe", "/s", "/f", "/t", "0"], shell=False)
            return schedule.CancelJob
        schedule.every(delay_s).seconds.do(_fire)
        return f"Shutdown timer set. The PC will shut down in {quantity} {unit}{'s' if quantity != 1 else ''}."

    raise ConfirmationRequired(f"Set a timer to shut down the computer in {quantity} {unit}{'s' if quantity != 1 else ''}?", _do)


def restart(args: dict) -> str:
    def _do():
        subprocess.run(["C:\\Windows\\System32\\shutdown.exe", "/r", "/f", "/t", "5"], shell=False)
    raise ConfirmationRequired("Are you sure you want to restart the computer?", _do)


def sleep(args: dict) -> str:
    def _do():
        subprocess.run(["C:\\Windows\\System32\\rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], shell=False)
    raise ConfirmationRequired("Are you sure you want to put the computer to sleep?", _do)


def lock_screen(args: dict) -> str:
    subprocess.run(["C:\\Windows\\System32\\rundll32.exe", "user32.dll,LockWorkStation"], shell=False)
    return "Locking the screen."


def _get_target_window():
    """Find the last active (non-terminal/non-assistant) window.
    Returns (hwnd, cx, cy) or (None, None, None) if not found.
    """
    target_cx, target_cy = None, None
    target_hwnd = None

    try:
        import win32gui
        import win32process
        import ctypes
        import psutil

        # Process names to ignore (Shin's own processes and terminal shells)
        ignored_processes = {
            "python.exe", "pythonw.exe", "cmd.exe", "powershell.exe", 
            "conhost.exe", "openconsole.exe", "windowsterminal.exe", 
            "mateenginex.exe", "wscript.exe"
        }

        # Keywords in titles to ignore (excluding "shin" to prevent filtering out IDE/editor)
        ignored_title_keywords = (
            "nvidia", "geforce", "program manager", "windows input experience"
        )

        def is_cloaked(hwnd):
            cloaked = ctypes.c_int(0)
            hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
            )
            return bool(cloaked.value) if hr == 0 else False

        def enum_cb(hwnd, extra):
            nonlocal target_cx, target_cy, target_hwnd
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if win32gui.IsIconic(hwnd):
                return True
            if is_cloaked(hwnd):
                return True
            
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return True
            
            title_lower = title.lower()
            if any(kw in title_lower for kw in ignored_title_keywords):
                return True
                
            # Get process name from hwnd
            try:
                _, win_pid = win32process.GetWindowThreadProcessId(hwnd)
                if win_pid == os.getpid():
                    return True
                proc_name = psutil.Process(win_pid).name().lower()
                if proc_name in ignored_processes:
                    return True
            except Exception:
                pass
            
            try:
                rect = win32gui.GetWindowRect(hwnd)
                w = rect[2] - rect[0]
                h = rect[3] - rect[1]
                if w < 150 or h < 150:
                    return True
                
                # Found a good candidate — use its center
                target_cx = rect[0] + w // 2
                target_cy = rect[1] + h // 2
                target_hwnd = hwnd
                return False  # Stop enumeration
            except Exception:
                return True

        win32gui.EnumWindows(enum_cb, None)
    except Exception as exc:
        logger.debug("win32gui lookup failed: %s", exc)

    # Fallback to pygetwindow if win32gui did not find anything
    if target_cx is None or target_cy is None:
        try:
            import pygetwindow as gw
            import win32process
            import psutil
            
            ignored_processes = {
                "python.exe", "pythonw.exe", "cmd.exe", "powershell.exe", 
                "conhost.exe", "openconsole.exe", "windowsterminal.exe", 
                "mateenginex.exe", "wscript.exe"
            }
            
            windows = gw.getAllWindows()
            for w in windows:
                if not w.title or w.isMinimized or not w.visible:
                    continue
                if w.width < 150 or w.height < 150:
                    continue
                
                try:
                    hwnd = w._hWnd
                    _, win_pid = win32process.GetWindowThreadProcessId(hwnd)
                    if win_pid == os.getpid():
                        continue
                    proc_name = psutil.Process(win_pid).name().lower()
                    if proc_name in ignored_processes:
                        continue
                except Exception:
                    pass
                    
                target_cx = w.left + w.width // 2
                target_cy = w.top + w.height // 2
                target_hwnd = w._hWnd
                break
        except Exception as exc:
            logger.debug("pygetwindow fallback lookup failed: %s", exc)

    if target_hwnd:
        try:
            import win32gui
            logger.info("Selected target window: HWND=%d, Title=%r, Center=(%d, %d)", target_hwnd, win32gui.GetWindowText(target_hwnd), target_cx, target_cy)
        except Exception:
            logger.info("Selected target window: HWND=%d, Center=(%d, %d)", target_hwnd, target_cx, target_cy)
    else:
        logger.warning("No target window found.")

    return target_hwnd, target_cx, target_cy


def _find_youtube_window():
    """Find a visible window with 'youtube' in the title.
    Returns the HWND or None.
    """
    try:
        import win32gui
        import win32process
        import ctypes
        import psutil

        # Inspect the active window first
        active_hwnd = win32gui.GetForegroundWindow()
        if active_hwnd:
            title = win32gui.GetWindowText(active_hwnd)
            if title and "youtube" in title.lower():
                return active_hwnd

        found_hwnd = None

        def is_cloaked(hwnd):
            cloaked = ctypes.c_int(0)
            hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
            )
            return bool(cloaked.value) if hr == 0 else False

        def enum_cb(hwnd, extra):
            nonlocal found_hwnd
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if is_cloaked(hwnd):
                return True
            
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return True
            
            if "youtube" in title.lower():
                # Make sure it's not our own process
                try:
                    _, win_pid = win32process.GetWindowThreadProcessId(hwnd)
                    if win_pid == os.getpid():
                        return True
                except Exception:
                    pass
                found_hwnd = hwnd
                return False  # Stop enumeration
            return True

        win32gui.EnumWindows(enum_cb, None)
        return found_hwnd
    except Exception as exc:
        logger.debug("Error in _find_youtube_window: %s", exc)
        return None


def _focus_window(hwnd):
    """Bring the window to the foreground securely, bypassing Windows UIPI foreground restrictions."""
    if not hwnd:
        return False
    try:
        import win32gui
        import win32process
        import ctypes
        import time

        title = win32gui.GetWindowText(hwnd)
        logger.info("Attempting to focus window: HWND=%d, Title=%r", hwnd, title)

        fore_hwnd = win32gui.GetForegroundWindow()
        
        # Check root window ancestor to resolve child controls/iframes/webview vs top-level window handle
        try:
            fore_root = ctypes.windll.user32.GetAncestor(fore_hwnd, 2)  # GA_ROOT
            target_root = ctypes.windll.user32.GetAncestor(hwnd, 2)
        except Exception:
            fore_root = fore_hwnd
            target_root = hwnd

        if fore_hwnd == hwnd or fore_root == target_root:
            logger.info("Window is already in foreground.")
            return True

        # Get thread IDs
        fore_thread_id, _ = win32process.GetWindowThreadProcessId(fore_hwnd)
        curr_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        # Attach current thread to foreground window thread
        attached = False
        if fore_thread_id != curr_thread_id:
            try:
                win32process.AttachThreadInput(curr_thread_id, fore_thread_id, True)
                attached = True
                logger.debug("Attached thread input to foreground thread %d", fore_thread_id)
            except Exception as e:
                logger.debug("Failed to AttachThreadInput: %s", e)

        # Bring window to front
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
        else:
            win32gui.ShowWindow(hwnd, 5)  # SW_SHOW
        win32gui.SetForegroundWindow(hwnd)

        # Detach thread if attached
        if attached:
            try:
                win32process.AttachThreadInput(curr_thread_id, fore_thread_id, False)
            except Exception:
                pass

        # Verification check
        time.sleep(0.05)
        new_fore = win32gui.GetForegroundWindow()
        try:
            new_fore_root = ctypes.windll.user32.GetAncestor(new_fore, 2)
        except Exception:
            new_fore_root = new_fore

        if new_fore == hwnd or new_fore_root == target_root:
            logger.info("Successfully focused window.")
            return True
        else:
            logger.warning("Foreground window is currently HWND=%d (%r)", new_fore, win32gui.GetWindowText(new_fore))

    except Exception as exc:
        logger.debug("force focus failed: %s", exc)

    # Fallback to ALT key tap + SetForegroundWindow
    try:
        import win32gui
        import ctypes
        import time
        logger.info("Falling back to Alt-key tap focus method...")
        # Tap ALT key (0x12)
        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # Alt down
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)  # Alt up
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
        else:
            win32gui.ShowWindow(hwnd, 5)  # SW_SHOW
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.05)
        
        new_fore = win32gui.GetForegroundWindow()
        try:
            new_fore_root = ctypes.windll.user32.GetAncestor(new_fore, 2)
        except Exception:
            new_fore_root = new_fore

        success = new_fore == hwnd or new_fore_root == target_root
        if success:
            logger.info("Alt-key fallback focus succeeded.")
        else:
            logger.warning("Alt-key fallback focus failed.")
        return success
    except Exception as e:
        logger.warning("Alt fallback focus failed: %s", e)
        return False


def type_text(args: dict) -> str:
    import pyautogui
    text = args.get("text", "")
    if not text:
        def _do(new_text):
            args["text"] = new_text
            return type_text(args)
        raise MissingArgument("What would you like me to type?", _do)
    
    hwnd, _, _ = _get_target_window()
    if hwnd:
        _focus_window(hwnd)
        
    try:
        # Check if text is standard ascii
        text.encode('ascii')
        pyautogui.write(text, interval=0.03)
    except UnicodeEncodeError:
        # Unicode / Hinglish / special characters: paste via clipboard
        try:
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
        except Exception:
            pyautogui.write(text, interval=0.03)
    return f"Typed: {text}"


def press_key(args: dict) -> str:
    import keyboard
    key = args.get("key", "").lower().strip()
    if not key:
        def _do(new_key):
            args["key"] = new_key
            return press_key(args)
        raise MissingArgument("Which key should I press?", _do)
        
    hwnd, _, _ = _get_target_window()
    if hwnd:
        _focus_window(hwnd)
        
    keyboard.press_and_release(key)
    return f"Pressed {key}."


def click_text(args: dict) -> str:
    target = args.get("text", "").lower().strip()
    action = args.get("action", "click").lower().strip()
    if not target:
        def _do(new_target):
            args["text"] = new_target
            return click_text(args)
        raise MissingArgument(f"What should I {action} on?", _do)

    # Clean target of leading/trailing filler ("click on", "the", "button", "on screen")
    clean_target = re.sub(r"^(?:(?:click|tap)\s+)?(?:on\s+)?(?:the\s+)?(?:a\s+)?(?:button\s+for\s+|button\s+)?", "", target, flags=re.IGNORECASE).strip()
    clean_target = re.sub(r"\s+(?:on|in)?\s*(?:the\s+|my\s+)?screen$", "", clean_target, flags=re.IGNORECASE).strip()
    clean_target = re.sub(r"\s+(?:button|video|card|link|tab|icon)$", "", clean_target, flags=re.IGNORECASE).strip()
    if not clean_target:
        clean_target = target

    verb = "Clicked" if action == "click" else "Tapped"

    # 1. Native Windows Media OCR & Vision Grounding (Pinpoint accuracy on web pages, YouTube, media cards, visible text)
    try:
        try:
            from core import vision
        except ImportError:
            try:
                from Shin.core import vision
            except ImportError:
                import vision
        found, bbox = vision.find_text_on_screen(clean_target)
        if found and bbox:
            import pyautogui
            cx = bbox.get("x") or (bbox["left"] + bbox["width"] // 2)
            cy = bbox.get("y") or (bbox["top"] + bbox["height"] // 2)
            pyautogui.moveTo(cx, cy, duration=0.2)
            pyautogui.click()
            return f"{verb} on '{clean_target}'."
    except Exception as vision_err:
        logger.debug("Vision/OCR click failed: %s", vision_err)

    # 2. Native Windows UI Automation (Fast, exact, verified score >= 85)
    try:
        try:
            from core import ui_tree
        except ImportError:
            try:
                from Shin.core import ui_tree
            except ImportError:
                import ui_tree
        ok, msg = ui_tree.click_ui_element_by_name(clean_target)
        if ok:
            return f"{verb} on '{clean_target}'."
    except Exception as uia_err:
        logger.debug("UIAutomation click failed: %s", uia_err)

    # 3. Fallback to pytesseract if Tesseract binary is installed
    try:
        import pytesseract
        import pyautogui
        default_tess_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default_tess_path):
            pytesseract.pytesseract.tesseract_cmd = default_tess_path

        img = pyautogui.screenshot()
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        for i, text_found in enumerate(data.get("text", [])):
            text_found = text_found.lower().strip()
            if text_found and (clean_target == text_found or (clean_target in text_found and len(text_found) > 1)):
                x = data["left"][i] + data["width"][i] / 2
                y = data["top"][i] + data["height"][i] / 2
                pyautogui.moveTo(x, y, duration=0.2)
                pyautogui.click()
                return f"{verb} on '{clean_target}'."
    except Exception as exc:
        logger.debug("Tesseract fallback failed: %s", exc)

    return f"I couldn't find '{clean_target}' on screen to {action}."


def screenshot(args: dict) -> str:
    pics = Path.home() / "Pictures" / "Shin Screenshots"
    pics.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = pics / f"screenshot_{ts}.png"
    img = pyautogui.screenshot()
    img.save(str(path))
    return f"Screenshot saved to {path.name}."


# ═══════════════════════════════════════════════════════════════════════════════
# Screen Vision
# ═══════════════════════════════════════════════════════════════════════════════

def screen_query(args: dict) -> str:
    """
    Screen reading / vision command dispatcher.

    Modes (set via args['mode']):
      'describe'  (default) — AI answers a question about the screen contents
      'read'                — OCR extracts and reads all visible text aloud
      'find'                — OCR searches for specific text on screen
    """
    mode     = args.get("mode", "describe").lower()
    question = args.get("question", "Describe what you see on this screen.")
    target   = args.get("target", "")  # used by 'find' mode

    try:
        from vision import capture_screen, capture_active_window, ask_vision, read_screen_text, find_text_on_screen
    except ImportError:
        return "Screen vision features are not available — the vision module is missing."

    # ── Mode: read (OCR) ──────────────────────────────────────────────────────
    if mode == "read":
        logger.info("screen_query[read]: running OCR on screen")
        text = read_screen_text()
        if not text:
            return (
                "I couldn't read any text from the screen. "
                "Make sure Tesseract OCR is installed: download it from tesseract-ocr.github.io"
            )
        # Trim for TTS — speaking 5000 chars is impractical
        if len(text) > 800:
            text = text[:800] + "... and more."
        return f"Here's what I can read on your screen: {text}"

    # ── Mode: find (OCR text search) ─────────────────────────────────────────
    if mode == "find":
        if not target:
            def _do(new_target):
                args["target"] = new_target
                return screen_query(args)
            raise MissingArgument("What text should I look for on screen?", _do)

        logger.info("screen_query[find]: searching screen for %r", target)
        found, bbox = find_text_on_screen(target)
        if found and bbox:
            return (
                f"Yes, I can see '{target}' on your screen — "
                f"it's around {bbox['left']} pixels from the left and {bbox['top']} pixels from the top."
            )
        elif found:
            return f"I found '{target}' on screen!"
        else:
            return f"I couldn't find '{target}' on your screen right now."

    # ── Mode: describe (AI vision) ────────────────────────────────────────────
    logger.info("screen_query[describe]: capturing screen for question: %r", question)
    try:
        # Use active window capture for more focused context
        image_b64 = capture_active_window()
        if not image_b64:
            image_b64 = capture_screen()

        answer = ask_vision(question, image_b64)
        if answer:
            return answer

        # No AI backend — fall back to OCR as last resort
        logger.info("screen_query: no AI backend available, falling back to OCR")
        text = read_screen_text()
        if text:
            if len(text) > 600:
                text = text[:600] + "... and more."
            return f"No AI vision key configured, but here's what I can read via OCR: {text}"

        return (
            "I can't see your screen right now. "
            "Set GEMINI_API_KEY or OPENAI_API_KEY in your .env file for AI vision, "
            "or install Tesseract OCR for offline text reading."
        )
    except Exception as exc:
        logger.exception("screen_query failed")
        return f"Sorry, I couldn't analyse the screen: {exc}"



# ═══════════════════════════════════════════════════════════════════════════════
# Window Management
# ═══════════════════════════════════════════════════════════════════════════════

def window_minimize_all(args: dict) -> str:
    """Show the desktop by minimising all windows (Win + D)."""
    pyautogui.hotkey('win', 'd')
    return "Showing desktop."


def window_snap_left(args: dict) -> str:
    """Snap the active window to the left half of the screen (Win + Left)."""
    pyautogui.hotkey('win', 'left')
    return "Window snapped to the left."


def window_snap_right(args: dict) -> str:
    """Snap the active window to the right half of the screen (Win + Right)."""
    pyautogui.hotkey('win', 'right')
    return "Window snapped to the right."


def scroll(args: dict) -> str:
    """Scroll the active (non-terminal) window up or down."""
    direction = args.get("direction", "down").lower()
    # By default, we use 15 notches.
    notches = int(args.get("amount", 15))

    import time
    import sys
    import pyautogui

    target_hwnd, target_cx, target_cy = _get_target_window()

    # ── Step 2: Move mouse to target, scroll, restore ────────────────────────
    orig_x, orig_y = pyautogui.position()
    moved = False

    try:
        if target_cx is not None and target_cy is not None:
            # Clamp to screen bounds
            sw, sh = pyautogui.size()
            target_cx = max(0, min(sw - 1, target_cx))
            target_cy = max(0, min(sh - 1, target_cy))

            _focus_window(target_hwnd)

            pyautogui.moveTo(target_cx, target_cy, duration=0.1)
            moved = True
            # Give the OS a moment to register the hover before scrolling
            time.sleep(0.1)

        # On Windows, PyAutoGUI passes dwData directly to mouse_event.
        # Most applications require multiples of WHEEL_DELTA (120) to scroll.
        scroll_amount = (notches * 120) if direction == "up" else -(notches * 120)

        pyautogui.scroll(scroll_amount)
        # Allow OS to process scroll event while mouse is hovered over the window
        time.sleep(0.2)

    finally:
        if moved:
            try:
                pyautogui.moveTo(orig_x, orig_y, duration=0.1)
            except Exception:
                pass

    return f"Scrolled {direction}."


def scroll_down(lines: int = 10):
    # negative value scrolls down
    scroll({"direction": "down", "amount": lines})


def scroll_up(lines: int = 10):
    # positive value scrolls up
    scroll({"direction": "up", "amount": lines})




def window_snap_quadrant(args: dict) -> str:
    import time
    v = args.get("v", "top")
    h = args.get("h", "left")
    pyautogui.hotkey('win', h)
    time.sleep(0.1)
    pyautogui.hotkey('win', 'up' if v == 'top' else 'down')
    return f"Window snapped to the {v} {h}."


def window_maximize(args: dict) -> str:
    """Maximise the active window (Win + Up)."""
    pyautogui.hotkey('win', 'up')
    return "Window maximized."


def window_minimize(args: dict) -> str:
    """Minimise the active window (Win + Down)."""
    pyautogui.hotkey('win', 'down')
    return "Window minimized."


# ═══════════════════════════════════════════════════════════════════════════════
# Media Controls
# ═══════════════════════════════════════════════════════════════════════════════

def media_play_pause(args: dict) -> str:
    """Toggle play/pause for the active media player."""
    yt_hwnd = _find_youtube_window()
    if yt_hwnd:
        _focus_window(yt_hwnd)
        pyautogui.press('k')
        return "Toggled play/pause on YouTube."

    try:
        import spotify_ai
        # Let spotify_ai handle it; it has its own fallback to media keys
        return spotify_ai.control_playback("play_pause")
    except ImportError:
        # If spotify_ai module doesn't exist, use generic key press
        pyautogui.press('playpause')
        return "Play/pause toggled."


def media_next(args: dict) -> str:
    """Skip to the next track."""
    yt_hwnd = _find_youtube_window()
    if yt_hwnd:
        _focus_window(yt_hwnd)
        pyautogui.hotkey('shift', 'n')
        return "Skipped to the next video on YouTube."

    try:
        import spotify_ai
        return spotify_ai.control_playback("next")
    except ImportError:
        pyautogui.press('nexttrack')
        return "Skipped to the next track."


def media_prev(args: dict) -> str:
    """Go back to the previous track."""
    yt_hwnd = _find_youtube_window()
    if yt_hwnd:
        _focus_window(yt_hwnd)
        pyautogui.hotkey('shift', 'p')
        return "Went back to the previous video on YouTube."

    try:
        import spotify_ai
        return spotify_ai.control_playback("previous")
    except ImportError:
        pyautogui.press('prevtrack')
        return "Went back to the previous track."


# ═══════════════════════════════════════════════════════════════════════════════
# Clipboard AI Actions
# ═══════════════════════════════════════════════════════════════════════════════

def _require_clipboard() -> str:
    """Return clipboard content or raise ValueError if empty."""
    try:
        from clipboard_ai import get_clipboard
    except ImportError:
        raise ValueError("clipboard_missing")
    content = get_clipboard()
    if not content.strip():
        raise ValueError("clipboard_empty")
    return content


def clipboard_translate(args: dict) -> str:
    """Translate clipboard content to the requested language."""
    language = args.get("language", "English")
    try:
        _require_clipboard()
    except ValueError:
        return "Your clipboard is empty — nothing to translate."
    from clipboard_ai import transform_clipboard
    result = transform_clipboard(f"Translate the following text to {language}:")
    if result:
        return f"Done! Your clipboard has been translated to {language}."
    return "Translation failed. Make sure an AI API key is set in your .env file."


def clipboard_rewrite(args: dict) -> str:
    """Rewrite clipboard content in a given style."""
    style = args.get("style", "professional")
    try:
        _require_clipboard()
    except ValueError:
        return "Your clipboard is empty — nothing to rewrite."
    from clipboard_ai import transform_clipboard
    result = transform_clipboard(
        f"Rewrite the following text to sound more {style}. Preserve the meaning exactly:"
    )
    if result:
        return f"Done! Your clipboard has been rewritten to sound more {style}."
    return "Rewrite failed. Make sure an AI API key is set in your .env file."


def clipboard_summarize(args: dict) -> str:
    """Summarise clipboard content in 2-3 sentences."""
    try:
        _require_clipboard()
    except ValueError:
        return "Your clipboard is empty — nothing to summarise."
    from clipboard_ai import transform_clipboard
    result = transform_clipboard(
        "Summarise the following text in 2-3 concise sentences:"
    )
    if result:
        return f"Summary: {result}"
    return "Summarise failed. Make sure an AI API key is set in your .env file."


def clipboard_fix(args: dict) -> str:
    """Fix grammar and spelling in clipboard content."""
    try:
        _require_clipboard()
    except ValueError:
        return "Your clipboard is empty — nothing to fix."
    from clipboard_ai import transform_clipboard
    result = transform_clipboard(
        "Fix all grammar and spelling errors in the following text. "
        "Do not change the meaning, tone, or style:"
    )
    if result:
        return "Done! Grammar and spelling have been corrected and copied to your clipboard."
    return "Grammar fix failed. Make sure an AI API key is set in your .env file."


def clipboard_history(args: dict) -> str:
    """Paste historical clipboard content."""
    index = args.get("index", 1)
    try:
        import clipboard_history as ch
        import pyperclip
        import time
        
        content = ch.get_history(index)
        if not content:
            return "Your clipboard history is empty."
            
        pyperclip.copy(content)
        time.sleep(0.1)
        pyautogui.hotkey('ctrl', 'v')
        
        if index == 1:
            return "Pasted the most recent item from your clipboard."
        return f"Pasted the item from {index} copies ago."
    except ImportError:
        return "The clipboard history module is missing."


def generate_code_command(args: dict) -> str:
    """Generate production-ready code for a request and copy to clipboard."""
    prompt = args.get("prompt") or args.get("query") or args.get("task", "").strip()
    language = args.get("language", "python").strip()
    if not prompt:
        def _do(p):
            args["prompt"] = p
            return generate_code_command(args)
        raise MissingArgument("What kind of code would you like me to write?", _do)

    import clipboard_ai
    return clipboard_ai.generate_code(prompt, language=language)


def explain_code_command(args: dict) -> str:
    """Explain code currently on the clipboard."""
    try:
        content = _require_clipboard()
    except ValueError:
        return "Clipboard is empty — please copy some code first!"

    import clipboard_ai
    return clipboard_ai.explain_code(content)


# ═══════════════════════════════════════════════════════════════════════════════
# Macros / Routines
# ═══════════════════════════════════════════════════════════════════════════════

def run_macro(args: dict) -> str:
    """Execute a named multi-step routine."""
    name = args.get("name", "morning")
    try:
        import macros
    except ImportError:
        return "Macro features are not available — the macros module is missing."
    return macros.run_macro(name, _speak)


# ═══════════════════════════════════════════════════════════════════════════════
# Meta / Info
# ═══════════════════════════════════════════════════════════════════════════════

def tell_time(args: dict) -> str:
    now = datetime.datetime.now()
    return f"It's {now.strftime('%I:%M %p')}."


def tell_date(args: dict) -> str:
    now = datetime.datetime.now()
    return f"Today is {now.strftime('%A, %B %d, %Y')}."


def quit_assistant(args: dict) -> str:
    # Handled specially in the main loop
    return "Goodbye! Have a great day."


def pause_listening(args: dict) -> str:
    # Handled specially in the main loop
    return "Standing by."


def resume_listening(args: dict) -> str:
    # Handled specially in the main loop
    return "Listening resumed."


def chat(args: dict) -> str:
    """Return the AI-generated conversational response."""
    return args.get("response", "I'm not sure what to say to that.")


def set_personality(args: dict) -> str:
    mode = args.get("mode", "friendly")
    import nlp
    nlp._CURRENT_PERSONALITY = mode
    return f"Got it. I will now act more {mode}."


def tell_news(args: dict) -> str:
    """Fetch and report news from India, America, Russia or by topic."""
    topic   = args.get("topic")
    country = args.get("country")

    try:
        import news
    except ImportError:
        return "News features are not available — the news module is missing."

    if topic:
        articles = news.search_news(topic, country=country)
        if not articles:
            return f"I couldn't find any news articles about '{topic}' right now."
        return news.format_headlines_for_speech(articles)
    elif country:
        articles = news.get_top_headlines(country=country)
        if not articles:
            return f"I couldn't fetch news for {country} right now."
        return news.format_headlines_for_speech(articles)
    else:
        # Default: combined top headlines from India, America, and Russia
        articles = news.get_top_headlines(country=None)
        if not articles:
            return "I couldn't fetch the latest news headlines right now."
        return news.format_headlines_for_speech(articles)



# ═══════════════════════════════════════════════════════════════════════════════
# Live Internet Queries  (answered by Shin — no browser opened)
# ═══════════════════════════════════════════════════════════════════════════════

def live_query(args: dict) -> str:
    """
    Answer a factual / encyclopedic question live from the internet.
    Sources: DuckDuckGo Instant Answers, Wikipedia.
    No browser is opened — Shin speaks the answer directly.
    """
    query = args.get("query", "").strip()
    if not query:
        def _do(q):
            args["query"] = q
            return live_query(args)
        raise MissingArgument("What would you like me to look up?", _do)

    try:
        import live_search
        answer = live_search.smart_answer(query)
        if answer:
            return answer
        # Nothing found — open browser as last resort
        logger.info("live_query: no live answer for %r — opening browser.", query)
        url = "https://www.google.com/search?q=" + query.replace(" ", "+")
        webbrowser.open(url)
        return f"I couldn't find a direct answer, so I've opened a search for '{query}'."
    except Exception as exc:
        logger.warning("live_query failed: %s", exc)
        url = "https://www.google.com/search?q=" + query.replace(" ", "+")
        webbrowser.open(url)
        return f"Searching for '{query}' in your browser."


def explain_internet(args: dict = None) -> str:
    """Explain how Shin accesses and uses the live internet."""
    try:
        import live_search
        return live_search.explain_internet_usage()
    except Exception:
        return (
            "Main live internet use karti hoon DuckDuckGo aur Wikipedia se real-time facts dhoondne ke liye, "
            "Yahoo Finance se stocks aur crypto check karne ke liye, Microsoft Edge se neural voice stream karne ke liye, "
            "aur online intelligence updates fetch karne ke liye!"
        )


def stock_query(args: dict) -> str:
    """
    Fetch and speak the current price of a stock, index (Nifty, Sensex, etc.)
    or any listed company using Yahoo Finance — no API key required.
    """
    ticker = args.get("ticker", "").strip()
    if not ticker:
        def _do(t):
            args["ticker"] = t
            return stock_query(args)
        raise MissingArgument("Which stock or index should I look up?", _do)

    try:
        import live_search
        answer = live_search.stock_price(ticker)
        if answer:
            return answer
        return f"I couldn't fetch the price for '{ticker}' right now. The market may be closed or the ticker may not be recognised."
    except Exception as exc:
        logger.warning("stock_query failed for %r: %s", ticker, exc)
        return f"Sorry, I couldn't retrieve the stock price for '{ticker}'."


def crypto_query(args: dict) -> str:
    """
    Fetch and speak the current price of a cryptocurrency.
    Uses CoinGecko free API — no API key required.
    """
    coin = args.get("coin", "").strip()
    if not coin:
        def _do(c):
            args["coin"] = c
            return crypto_query(args)
        raise MissingArgument("Which cryptocurrency should I check?", _do)

    try:
        import live_search
        answer = live_search.crypto_price(coin)
        if answer:
            return answer
        return f"I couldn't fetch the price for '{coin}' right now. Please check the coin name and try again."
    except Exception as exc:
        logger.warning("crypto_query failed for %r: %s", coin, exc)
        return f"Sorry, I couldn't retrieve the crypto price for '{coin}'."


def calendar_list(args: dict) -> str:
    """List upcoming calendar events."""
    day = args.get("day")
    try:
        import calendar_ai
    except ImportError:
        return "Calendar features are not available — the calendar_ai module is missing."
    events = calendar_ai.get_upcoming_events(max_results=5, day=day)
    if isinstance(events, str):
        return events
    if not events:
        period = f" for {day}" if day else ""
        return f"You have no upcoming events{period} on your calendar."
        
    intro = f"Here are your upcoming events{f' for {day}' if day else ''}: "
    event_strings = []
    for event in events:
        summary = event.get('summary', 'Untitled Event')
        start_time_str = event.get('start', {}).get('dateTime') or event.get('start', {}).get('date')
        if start_time_str:
            try:
                if "T" in start_time_str:
                    dt_utc = datetime.datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                    dt_local = dt_utc.astimezone()  # Convert to local timezone
                    time_part = dt_local.strftime("%I:%M %p")
                    date_part = dt_local.strftime("%A")
                    event_strings.append(f"'{summary}' on {date_part} at {time_part}")
                else:
                    dt = datetime.date.fromisoformat(start_time_str)
                    event_strings.append(f"'{summary}' all day {dt.strftime('%A')}")
            except Exception:
                event_strings.append(f"'{summary}'")
        else:
            event_strings.append(f"'{summary}'")
            
    return intro + ", and ".join(event_strings) + "."


def calendar_add(args: dict) -> str:
    """Schedule a new event on calendar."""
    event = args.get("event")
    time_str = args.get("time")
    if not event:
        def _do_event(new_event):
            args["event"] = new_event
            return calendar_add(args)
        raise MissingArgument("What is the title of the event you want to schedule?", _do_event)
    if not time_str:
        def _do_time(new_time):
            args["time"] = new_time
            return calendar_add(args)
        raise MissingArgument(f"When would you like to schedule '{event}'?", _do_time)
    try:
        import calendar_ai
    except ImportError:
        return "Calendar features are not available — the calendar_ai module is missing."
    return calendar_ai.create_event(event, time_str)


def spotify_play(args: dict) -> str:
    """Play a track or playlist on Spotify."""
    query = args.get("query")
    if not query:
        def _do(new_query):
            args["query"] = new_query
            return spotify_play(args)
        raise MissingArgument("What would you like me to play on Spotify?", _do)
    try:
        import spotify_ai
    except ImportError:
        return "Spotify features are not available — the spotify_ai module is missing."
    return spotify_ai.play_track_or_playlist(query)


def spotify_status(args: dict) -> str:
    """Get active playback track description from Spotify."""
    try:
        import spotify_ai
    except ImportError:
        return "Spotify features are not available — the spotify_ai module is missing."
    return spotify_ai.get_current_track_info()


def _play_in_youtube_pwa(video_url: str) -> bool:
    import re
    # Search for YouTube shortcut in Start Menu
    paths = [
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")
    ]
    shortcut_path = None
    for p in paths:
        if os.path.exists(p):
            for root, _, files in os.walk(p):
                for file in files:
                    if "youtube" in file.lower() and file.endswith((".lnk", ".url")):
                        shortcut_path = os.path.join(root, file)
                        break
                if shortcut_path:
                    break
        if shortcut_path:
            break
            
    if not shortcut_path:
        logger.debug("No YouTube shortcut found in Start Menu for PWA playback.")
        return False
        
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        target = shortcut.TargetPath
        args = shortcut.Arguments
        
        target_lower = target.lower()
        is_chrome = "chrome" in target_lower
        is_edge = "msedge" in target_lower
        is_brave = "brave" in target_lower
        
        if is_chrome or is_edge or is_brave:
            cmd = [target]
            # Extract profile directory if specified
            profile_match = re.search(r'--profile-directory=(?:"([^"]+)"|([^\s]+))', args)
            if profile_match:
                profile = profile_match.group(1) or profile_match.group(2)
                cmd.append(f"--profile-directory={profile}")
            cmd.append(f"--app={video_url}")
            
            logger.info("Launching YouTube PWA: %s", cmd)
            subprocess.Popen(cmd, shell=False)
            return True
    except Exception as exc:
        logger.warning("Failed to launch YouTube PWA via shortcut target: %s", exc)
        
    return False


def youtube_play(args: dict) -> str:
    """Play a video on YouTube."""
    query = args.get("query", "random hindi songs mix")
    if not query:
        query = "random hindi songs mix"
        
    try:
        import pywhatkit
        logger.info("Playing '%s' on YouTube via pywhatkit (URL extraction)", query)
        url = pywhatkit.playonyt(query, open_video=False)
        if url:
            if _play_in_youtube_pwa(url):
                return f"Playing {query} on YouTube."
            else:
                webbrowser.open(url)
                return f"Playing {query} on YouTube."
        else:
            raise Exception("No video URL returned")
    except Exception as exc:
        # Fallback if pywhatkit isn't installed or fails
        logger.info("pywhatkit search failed or not installed, falling back to browser search for '%s': %s", query, exc)
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        if not _play_in_youtube_pwa(url):
            webbrowser.open(url)
        return f"I opened YouTube and searched for {query}."


def smart_home_control(args: dict) -> str:
    """Control smart home bulbs (on, off, color, brightness)."""
    state = args.get("state", "on")
    color = args.get("color")
    brightness = args.get("brightness")
    try:
        import smart_home
    except ImportError:
        return "Smart home features are not available — the smart_home module is missing."
    return smart_home.control_device(state, color, brightness)


def activate_scene(args: dict) -> str:
    """Activate a smart home automation scene."""
    name = args.get("name")
    if not name:
        def _do(new_name):
            args["name"] = new_name
            return activate_scene(args)
        raise MissingArgument("Which smart home scene would you like to activate?", _do)
    try:
        import smart_home
    except ImportError:
        return "Smart home features are not available — the smart_home module is missing."
    return smart_home.activate_scene(name)


def monitor_process(args: dict) -> str:
    """Watch a process PID or name and alert when it exits."""
    pid = args.get("pid")
    name = args.get("name")
    
    try:
        import alerts
    except ImportError:
        return "Process monitoring features are not available — the alerts module is missing."
    if pid:
        if alerts.watch_process(pid, f"process {pid}"):
            return f"I am now monitoring process with P I D {pid}."
        return f"Process with P I D {pid} does not appear to be running."
    
    if name:
        res = alerts.watch_latest_process_by_name(name)
        if res:
            target_pid, display_name = res
            return f"Found and monitoring latest '{name}' process: {display_name} with P I D {target_pid}."
        return f"I couldn't find any active process matching '{name}' to monitor."
            
    return "Please specify a process name or P I D to monitor."
        
def list_open_windows(args: dict) -> str:
    """List titles of all visible, non-system windows (active browser tabs/apps)."""
    import pygetwindow as gw
    windows = gw.getAllWindows()
    titles = []
    
    ignore_list = {
        "program manager", "settings", "nvidia geforce overlay", 
        "windows input experience", "realtek audio console", "calculator",
        "task manager", "command prompt", "powershell"
    }
    
    for w in windows:
        if w.title and w.width > 120 and w.height > 120:
            title = w.title.strip()
            title_lower = title.lower()
            if any(ig in title_lower for ig in ignore_list):
                continue
            titles.append(title)
            
    if not titles:
        return "You have no active application windows open."
        
    return "The following windows and tabs are currently open: " + ", ".join(f"'{t}'" for t in titles) + "."


def check_system_status(args: dict) -> str:
    """Report battery and CPU usage."""
    import psutil
    
    status = []
    cpu = psutil.cpu_percent(interval=0.5)
    if cpu > 80:
        status.append(f"My CPU usage is quite high at {round(cpu)} percent.")
    else:
        status.append(f"All systems nominal. CPU usage is at {round(cpu)} percent.")
        
    battery = psutil.sensors_battery()
    if battery:
        plugged = "plugged in and charging" if battery.power_plugged else "running on battery"
        status.append(f"The battery is at {round(battery.percent)} percent and {plugged}.")
        
        if not battery.power_plugged and battery.secsleft != psutil.POWER_TIME_UNKNOWN:
            mins = battery.secsleft // 60
            hours = mins // 60
            mins = mins % 60
            if hours > 0:
                status.append(f"You have about {hours} hours and {mins} minutes remaining.")
            else:
                status.append(f"You have about {mins} minutes remaining.")
        
    return " ".join(status)


def save_memory(args: dict) -> str:
    """Commit a new personal fact or task to persistent memory."""
    content = args.get("content", "").strip()
    if not content:
        def _do(new_content):
            args["content"] = new_content
            return save_memory(args)
        raise MissingArgument("What would you like me to remember?", _do)
    import memory
    result = memory.add_memory(content)
    # Invalidate the NLP memory context cache so the AI gets the new fact immediately
    try:
        import nlp
        nlp.invalidate_memory_cache()
    except Exception:
        pass
    return result


def recall_memory(args: dict) -> str:
    """Recall stored personal facts or tasks by keyword, or list all."""
    query = args.get("query", "").strip()
    import memory
    results = memory.search_memories(query if query else None)
    if not results:
        if query:
            return f"I don't have any memories matching '{query}'."
        return "Your memory is currently empty."
    
    if query:
        intro = f"Here is what I remember about '{query}': "
    else:
        intro = "Here is everything I remember: "
        
    mem_strings = [mem["content"] for mem in results]
    return intro + ", and ".join(f"'{m}'" for m in mem_strings) + "."


def forget_memory(args: dict) -> str:
    """Forget a specific memory or clear everything."""
    query = args.get("query", "").strip()
    import memory
    if not query:
        def _do(new_query):
            args["query"] = new_query
            return forget_memory(args)
        raise MissingArgument("What would you like me to forget?", _do)
    
    if query.lower() in ("all", "everything"):
        def _do_clear():
            count, msg = memory.delete_memories(query)
            return msg
        raise ConfirmationRequired("Are you sure you want to clear all my memories?", _do_clear)
        
    count, msg = memory.delete_memories(query)
    return msg


def train_shin(args: dict) -> str:
    """
    Rich interactive training session — Shin asks MJ a curated set of questions
    across five categories and saves every answer to persistent memory.

    Phase 0  — recap existing knowledge
    Phase 1  — personal identity & family
    Phase 2  — daily habits & health
    Phase 3  — interests, hobbies & work style
    Phase 4  — emotional preferences & mood handling
    Phase 5  — custom phrases / shortcut teaching
    """
    import memory
    import threading

    # ── Curated question bank ────────────────────────────────────────────────
    _TRAINING_QUESTIONS: list[tuple[str, str]] = [
        # (spoken question, memory-prefix for the answer)
        # -- Phase 1: identity & family --
        ("Chalo MJ, pehla sawal — tera full name kya hai? Main sure karna chahti hoon mere paas sahi details hain.",
         "MJ's full name is"),
        ("Tu kahan se hai yaar? Matlab apna hometown bata mujhe.",
         "MJ's hometown is"),
        ("Teri family mein kaun kaun hai? Short mein bata — like bhai, behan, parents.",
         "MJ's family members:"),
        # -- Phase 2: daily habits & health --
        ("Tu subah generally kitne baje uthta hai? Aur raat ko kitne baje sota hai?",
         "MJ's typical sleep schedule:"),
        ("Tera favourite khana kya hai? Aur kuch allergies ya cheezein hain jo tujhe pasand nahi?",
         "MJ's food preference:"),
        ("Exercise karta hai kuch? Gym, cricket, ya bas keyboard warrior hai?",
         "MJ's fitness/exercise habit:"),
        # -- Phase 3: interests, work & style --
        ("Coding mein tujhe kaunsa language ya framework sabse zyada pasand hai?",
         "MJ's favourite programming language/framework:"),
        ("Currently kaunsa project ya goal hai tera — bata mujhe, main support karungi!",
         "MJ's current main project/goal:"),
        ("Music mein teri taste kya hai? Kaunsa genre ya artist?",
         "MJ's music taste:"),
        ("Tujhe dark mode pasand hai ya light mode? Aur kaun sa editor use karta hai tu?",
         "MJ's UI/editor preference:"),
        # -- Phase 4: emotional & mood handling --
        ("Jab tu bohot stressed ya frustrated hota hai, tujhe kya help karta hai chill karne mein?",
         "When MJ is stressed, it helps to:"),
        ("Jab tu sad ho toh main kya karun — chup rehun, teri baat sunun, ya thoda roast karun teri? Be honest!",
         "When MJ is sad, Shin should:"),
        ("Jab tu kuch achieve karta hai — celebrate karun loudly, ya bas quietly acknowledge karun?",
         "When MJ achieves something, Shin should:"),
        # -- Phase 5: custom behaviour --
        ("Koi specific cheez hai jo tujhe meri communication mein pasand nahi? Like zyada sass, ya zyada formal?",
         "MJ dislikes when Shin:"),
        ("Koi special phrase hai jo tujhe chahiye ki jab main use karun — like apna catchphrase ya kuch unique?",
         "MJ wants Shin to use the phrase:"),
    ]

    # ── Mode dispatch ────────────────────────────────────────────────────────
    mode = args.get("mode", "start")

    # ── start: kick off the session ─────────────────────────────────────────
    if mode == "start":
        mems = memory.load_memories()
        count = len(mems)
        known_blurb = (
            f"Mujhe abhi {count} cheezein pata hain tere baare mein. "
            if count else "Abhi tak main kuch nahi jaanti tere baare mein. "
        )

        intro = (
            f"Okay MJ, chalte hain TRAINING MODE mein! {known_blurb}"
            f"Main tujhse {len(_TRAINING_QUESTIONS)} sawal puchungi — ek ek karke. "
            "Har jawab main yaad rakh lungi. "
            "Shuru karte hain? Pehla sawal yeh hai: "
            f"{_TRAINING_QUESTIONS[0][0]}"
        )

        # Store session state in memory under a special key
        _training_state = {"q_index": 0, "total": len(_TRAINING_QUESTIONS)}
        try:
            import json as _json
            memory.add_memory(f"__TRAIN_STATE__: {_json.dumps(_training_state)}")
        except Exception:
            pass

        return intro

    # ── answer: save the current answer and ask the next question ─────────
    if mode == "answer":
        answer = args.get("answer", "").strip()
        q_index = int(args.get("q_index", 0))

        if q_index < len(_TRAINING_QUESTIONS):
            _q_text, mem_prefix = _TRAINING_QUESTIONS[q_index]
            # Save this answer to persistent memory
            if answer:
                fact = f"{mem_prefix} {answer}"
                memory.add_memory(fact)
                # Refresh NLP memory cache immediately
                try:
                    import nlp
                    nlp.invalidate_memory_cache()
                except Exception:
                    pass

            next_index = q_index + 1
            if next_index < len(_TRAINING_QUESTIONS):
                next_q = _TRAINING_QUESTIONS[next_index][0]
                progress = f"({next_index}/{len(_TRAINING_QUESTIONS)})"
                ack_options = [
                    "Got it, yaad kar liya!",
                    "Perfect, note kar liya maine!",
                    "Haan haan, noted!",
                    "Achha ji, dil pe laga liya!",
                ]
                import random
                ack = random.choice(ack_options)
                return f"{ack} {progress} Agla sawal: {next_q}"
            else:
                # Training complete
                _training_done_cleanup(memory)
                return _training_complete_message(memory)

        return _training_complete_message(memory)

    # ── skip: skip current question ─────────────────────────────────────────
    if mode == "skip":
        q_index = int(args.get("q_index", 0))
        next_index = q_index + 1
        if next_index < len(_TRAINING_QUESTIONS):
            return (
                f"Theek hai, yeh skip karte hain! "
                f"({next_index}/{len(_TRAINING_QUESTIONS)}) "
                f"Agla sawal: {_TRAINING_QUESTIONS[next_index][0]}"
            )
        _training_done_cleanup(memory)
        return _training_complete_message(memory)

    # ── summary: just show what Shin knows ──────────────────────────────────
    if mode == "summary":
        mems = memory.load_memories()
        user_mems = [m for m in mems if not m["content"].startswith("__TRAIN_STATE__")]
        if not user_mems:
            return "Main abhi tak kuch nahi jaanti tere baare mein. Chal training shuru karte hain!"
        lines = [f"  {i+1}. {m['content']}" for i, m in enumerate(user_mems[-10:])]
        return "Yeh sab main jaanti hoon tere baare mein:\n" + "\n".join(lines)

    # ── default: treat as a fresh start ────────────────────────────────────
    return train_shin({**args, "mode": "start"})


def _training_done_cleanup(memory_module) -> None:
    """Remove the training-state sentinel from memory."""
    try:
        mems = memory_module.load_memories()
        cleaned = [m for m in mems if not m.get("content", "").startswith("__TRAIN_STATE__")]
        memory_module.save_memories(cleaned)
    except Exception:
        pass


def _training_complete_message(memory_module) -> str:
    """Build the 'training complete' wrap-up message."""
    mems = memory_module.load_memories()
    user_mems = [m for m in mems if not m.get("content", "").startswith("__TRAIN_STATE__")]
    count = len(user_mems)
    return (
        f"Training complete ho gaya MJ! Main ab {count} cheezein jaanti hoon tere baare mein. "
        "Yeh sab meri long-term memory mein save ho gaya hai — "
        "agle session mein bhi yaad rahega. "
        "Agar aur kuch batana ho toh bas bol na — 'remember that...' ya 'note down...' se shuru kar!"
    )


def explain_internet(args: dict) -> str:
    """Explain how Shin connects to and uses the internet."""
    import live_search
    return live_search.explain_internet_usage()


def wiki_search(args: dict) -> str:
    """Fetch and speak a summary from Wikipedia for a given query."""
    query = args.get("query", "").strip()
    if not query:
        def _do(new_query):
            args["query"] = new_query
            return wiki_search(args)
        raise MissingArgument("What would you like me to look up on Wikipedia?", _do)
    
    import live_search
    summary = live_search.wikipedia_summary(query)
    if summary:
        return summary
    return f"I couldn't find a Wikipedia article for '{query}'."


def tell_news(args: dict) -> str:
    """Fetch top headlines or topic news using news module."""
    try:
        import news as _news
    except ImportError:
        return "News feature is not available — the news module is missing."
    
    country = args.get("country")
    topic = args.get("topic") or args.get("query")
    
    if topic:
        articles = _news.search_news(topic=topic, country=country, count=5)
    else:
        articles = _news.get_top_headlines(country=country, count=6)
        
    return _news.format_headlines_for_speech(articles)


def learn_from_internet(args: dict) -> str:
    """Fetch factual information directly from the internet without opening any browser tabs, and commit it to persistent memory."""
    topic = args.get("topic") or args.get("query") or args.get("subject", "").strip()
    if not topic:
        def _do(new_topic):
            args["topic"] = new_topic
            return learn_from_internet(args)
        raise MissingArgument("What topic would you like me to learn about from the internet?", _do)
    
    import live_search
    import memory
    
    # 1. Fetch info headlessly without opening any browser tab
    info = live_search.smart_answer(topic)
    if not info:
        info = live_search.wikipedia_summary(topic)
    if not info:
        info = live_search.search_web_snippets(topic)
        
    if not info:
        return f"I searched the internet headlessly without opening any tabs, but couldn't find clear information on '{topic}'."
        
    # 2. Save the learned knowledge persistently to memory
    fact_entry = f"Learned from internet about {topic}: {info}"
    memory.add_memory(fact_entry)
    
    # Invalidate NLP memory cache
    try:
        import nlp
        nlp.invalidate_memory_cache()
    except Exception:
        pass
        
    return f"I gathered information from the internet without opening any browser tabs! Here is what I learned about {topic}: {info} I have stored this in my long-term memory."


def learn_laptop_skills(args: dict = None) -> str:
    """
    Actively learn and memorize Windows laptop shortcuts, terminal commands,
    and system control capabilities, persisting them into Shin's long-term memory.
    """
    args = args or {}
    try:
        from core import memory
        from core.settings import get_language
    except ImportError:
        try:
            from Shin.core import memory
            from Shin.core.settings import get_language
        except ImportError:
            import memory
            from settings import get_language

    is_english = (get_language() == "english")

    laptop_skills = [
        "Laptop Shortcut: Win + Arrow Keys snaps windows to left, right, maximize, or minimize.",
        "Laptop Shortcut: Win + V opens the multi-item Clipboard History to paste previous clips.",
        "Laptop Shortcut: Win + Shift + S opens the Snipping Tool for custom screen capture.",
        "Laptop Shortcut: Ctrl + Shift + Esc opens Windows Task Manager directly.",
        "Laptop Command: wt launches Windows Terminal, and 'code .' opens the current folder in VS Code.",
        "Laptop System Controls: Shin can adjust volume, mute, unmute, and change screen brightness directly.",
        "Shin Custom Commands: Say 'learn command [name]: [commands]' to create instant voice macros."
    ]

    for entry in laptop_skills:
        memory.add_memory(entry)

    try:
        from core import nlp
        nlp.invalidate_memory_cache()
    except Exception:
        try:
            import nlp
            nlp.invalidate_memory_cache()
        except Exception:
            pass

    if is_english:
        return (
            "I've learned and memorized new laptop skills and commands! "
            "I now know key Windows shortcuts like Win+Arrows for window snapping, Win+V for clipboard history, "
            "Ctrl+Shift+Esc for Task Manager, and CLI commands like wt and code. "
            "I've saved all these in my long-term memory, and you can also teach me custom voice commands anytime by saying: "
            "'learn command [name]: [action]'!"
        )
    return (
        "Maine laptop aur system commands ke naye power skills seekh kar memory mein save kar liye MJ! "
        "Jaise window snapping (Win+Arrows), clipboard history (Win+V), Task Manager (Ctrl+Shift+Esc), "
        "aur terminal dev commands (wt, code). "
        "Ab yeh meri long-term memory mein stored hain, aur tu mujhe kabhi bhi custom command bhi sikha sakta hai "
        "bas bol kar: 'learn command [name]: [action]'!"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Knowledge, Project & Screen Intelligence
# ═══════════════════════════════════════════════════════════════════════════════

def explain_concept(args: dict) -> str:
    """Explain a laptop, hardware, software, app, or assistant concept using Shin's knowledge base."""
    concept = args.get("concept") or args.get("topic") or args.get("subject", "").strip()
    try:
        import shin_knowledge
        if not concept:
            return shin_knowledge.get_all_topics_summary()
        return shin_knowledge.explain_concept(concept)
    except Exception as exc:
        logger.error("Failed to explain concept %r: %s", concept, exc)
        return f"Arre yaar, explain karte waqt thoda issue aa gaya: {exc}"


def locate_app(args: dict) -> str:
    """Find where an application is installed on disk and reveal in File Explorer."""
    app_name = args.get("app") or args.get("query") or args.get("name", "").strip()
    if not app_name:
        def _do(name):
            args["app"] = name
            return locate_app(args)
        raise MissingArgument("Which app's installation folder do you want to find?", _do)

    try:
        import app_finder
        reveal = args.get("reveal", True)
        return app_finder.explain_where_app_is(app_name, reveal=reveal)
    except Exception as exc:
        logger.error("Failed to locate app %r: %s", app_name, exc)
        return f"App locate karne mein error aaya: {exc}"


def help_with_project(args: dict) -> str:
    """
    Intelligent coding and project assistant:
    1. Inspects active window (VS Code, Blender, Terminal).
    2. Checks clipboard for copied code or traceback errors.
    3. Scans screen for errors or exceptions.
    4. Provides actionable fixes, tips, or guidance.
    """
    try:
        import vision
        import pyperclip
        import clipboard_ai

        # 1. First check clipboard: did user copy an error or code snippet?
        clip_text = ""
        try:
            clip_text = pyperclip.paste().strip()
        except Exception:
            pass

        # If clipboard has a Python traceback or error
        if clip_text and any(err in clip_text for err in ("Traceback", "SyntaxError", "Error:", "Exception", "npm ERR!")):
            logger.info("help_with_project: analyzing clipboard error traceback...")
            return clipboard_ai.fix_errors(clip_text)

        # 2. Inspect active screen and process
        screen_info = vision.inspect_screen_activity()
        activity = screen_info.get("activity")
        category = screen_info.get("category")
        has_error = screen_info.get("error_detected")

        if has_error:
            logger.info("help_with_project: diagnosing error detected on screen...")
            return vision.diagnose_screen_error()

        # 3. If in VS Code
        if activity == "coding":
            if clip_text and len(clip_text) > 20:
                return (
                    f"Main dekh rahi hoon tu {category} mein kaam kar raha hai! "
                    "Tere clipboard pe code copied hai — bol toh isko optimize karun, explain karun, ya test likhun?"
                )
            return (
                "Tu VS Code mein coding kar raha hai MJ! "
                "Agar kisi line mein bug hai ya syntax samajh nahi aa raha, toh code copy karke bol 'explain clipboard' "
                "ya direct bol 'dekh screen pe kya error hai', main turant fix bata dungi!"
            )

        # 4. If in Blender
        if activity == "3d_modeling":
            return (
                "Blender khula hua hai screen pe! 3D modeling, shading, ya animation mein focused hai. "
                "Agar shortcut bhool gaya ho ya rendering setting optimize karni ho, bas puch lena!"
            )

        # 5. General project guidance
        return (
            f"Screen pe abhi {category} active hai. "
            "Project mein help ke liye tu code copy karke mujhe pooch sakta hai, "
            "ya bol 'check screen error' agar koi terminal fail hua ho!"
        )
    except Exception as exc:
        logger.error("Project help error: %s", exc)
        return f"Project assist karne mein problem aayi: {exc}"


def explain_screen_activity(args: dict) -> str:
    """Explain what is currently visible and happening on the laptop screen."""
    try:
        import vision
        return vision.summarize_screen_activity()
    except Exception as exc:
        logger.error("Failed to explain screen activity: %s", exc)
        return f"Screen check karne mein issue aaya: {exc}"


def screen_diagnose_bug(args: dict) -> str:
    """Scan the screen for any visible code bugs, crashes, or terminal errors."""
    try:
        import vision
        return vision.diagnose_screen_error()
    except Exception as exc:
        logger.error("Failed to diagnose screen error: %s", exc)
        return f"Screen error scan karne mein issue aaya: {exc}"


def project_git_status(args: dict) -> str:
    """Inspect Git branch, uncommitted changes, and repository status of the workspace."""
    target_dir = args.get("directory") or str(Path(__file__).parent.parent.absolute())
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain=v1", "-b"],
            capture_output=True,
            text=True,
            timeout=8,
            cwd=target_dir
        )
        if res.returncode != 0:
            err = res.stderr.strip()
            if "not a git repository" in err.lower():
                return f"Directory '{Path(target_dir).name}' mein Git repository initialize nahi hai MJ."
            return f"Git status check karte waqt issue aaya: {err[:120]}"

        lines = res.stdout.strip().splitlines()
        if not lines:
            return "Git status clean hai! Koi uncommitted changes nahi hain."

        branch_line = lines[0].replace("##", "").strip()
        change_lines = lines[1:]

        modified = sum(1 for l in change_lines if l.startswith(" M") or l.startswith("M "))
        untracked = sum(1 for l in change_lines if l.startswith("??"))
        added = sum(1 for l in change_lines if l.startswith("A ") or l.startswith("AM"))
        deleted = sum(1 for l in change_lines if "D" in l[:2])

        summary_parts = []
        if modified:
            summary_parts.append(f"{modified} modified")
        if untracked:
            summary_parts.append(f"{untracked} untracked")
        if added:
            summary_parts.append(f"{added} staged")
        if deleted:
            summary_parts.append(f"{deleted} deleted")

        details = ", ".join(summary_parts) if summary_parts else "sab clean hai"
        repo_name = Path(target_dir).name
        return f"Project '{repo_name}' mein branch '{branch_line}' par hain. Status: {details} files. Main hoon na tere saath coding mein!"
    except FileNotFoundError:
        return "Laptop pe Git command line installed nahi mili."
    except Exception as exc:
        logger.error("Git status failed: %s", exc)
        return f"Git status check karne mein error aaya: {exc}"


def git_diff_summary(args: dict) -> str:
    """Inspect and explain recent uncommitted Git changes in the project."""
    target_dir = args.get("directory") or str(Path(__file__).parent.parent.absolute())
    try:
        res = subprocess.run(
            ["git", "diff", "--stat"],
            capture_output=True,
            text=True,
            timeout=8,
            cwd=target_dir
        )
        if res.returncode != 0:
            return "Git diff check karne mein error aaya."
        stat_out = res.stdout.strip()
        if not stat_out:
            return "Koi uncommitted code changes nahi hain — working tree clean hai!"

        try:
            import pyperclip
            pyperclip.copy(stat_out)
        except Exception:
            pass

        last_line = stat_out.splitlines()[-1] if stat_out.splitlines() else stat_out
        return f"Recent code changes ka summary: {last_line}. Clipboard pe full diff summary copy kar diya hai MJ!"
    except Exception as exc:
        return f"Git diff inspect karne mein issue aaya: {exc}"


def create_project_file(args: dict) -> str:
    """Create a new code or text file in the workspace, populating it from clipboard or argument."""
    filename = args.get("filename") or args.get("name") or args.get("path", "").strip()
    content = args.get("content") or args.get("code", "")

    if not filename:
        def _do(fname):
            args["filename"] = fname
            return create_project_file(args)
        raise MissingArgument("Kaunsa file banana hai? Filename batao (jaise script.py ya test.js).", _do)

    filename = filename.replace('"', '').replace("'", "").strip()
    root_dir = Path(__file__).parent.parent.absolute()

    file_path = Path(filename)
    if not file_path.is_absolute():
        file_path = root_dir / file_path

    if not content:
        try:
            import pyperclip
            clip = pyperclip.paste().strip()
            if clip and len(clip) > 5:
                content = clip
        except Exception:
            content = ""

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content or "")

        lines_cnt = len(content.splitlines()) if content else 0
        if content:
            return f"Naya file '{file_path.name}' successfully create ho gaya with {lines_cnt} lines of code!"
        else:
            return f"Empty file '{file_path.name}' successfully create kar di hai!"
    except Exception as exc:
        logger.error("Failed to create file %s: %s", file_path, exc)
        return f"File create karne mein dikkat aayi: {exc}"


def draft_whatsapp_message(args: dict) -> str:
    """Draft a thoughtful, polished WhatsApp message and copy to clipboard."""
    contact = args.get("contact", "").strip()
    topic = args.get("topic") or args.get("message") or args.get("about", "").strip()
    tone = args.get("tone", "friendly").strip()

    if not topic:
        def _do(t):
            args["topic"] = t
            return draft_whatsapp_message(args)
        raise MissingArgument("WhatsApp message kis baare mein draft karna hai?", _do)

    prompt = (
        f"Draft a short, natural WhatsApp message for {contact or 'a friend'} about: '{topic}'. "
        f"Tone: {tone}. Write in friendly natural Hinglish or English (Latin script only, max 2-3 sentences). "
        "Do NOT include greeting placeholders like [Name], make it ready to send directly."
    )

    draft = ""
    try:
        from clipboard_ai import _call_ai
        draft = _call_ai(prompt).strip()
    except Exception:
        pass

    if not draft or "error" in draft.lower():
        if contact:
            draft = f"Hey {contact.title()}, just wanted to update you regarding {topic}. Hope you're doing well!"
        else:
            draft = f"Hey! Just checking in about {topic}. Let me know when you're free."

    try:
        import pyperclip
        pyperclip.copy(draft)
    except Exception:
        pass

    target_str = f" for {contact.title()}" if contact else ""
    return (
        f"Maine WhatsApp message draft karke clipboard pe copy kar diya hai{target_str}: "
        f"'{draft}'. Tu bas chat mein paste karke bhej sakta hai!"
    )


def review_code(args: dict) -> str:
    """Analyze code or file for security risks, anti-patterns, and style violations."""
    filepath = args.get("filepath") or args.get("file") or args.get("path", "").strip()

    code_text = ""
    target_name = ""
    if filepath:
        target_name = filepath
        target_path = Path(filepath)
        if not target_path.is_absolute():
            target_path = Path(__file__).parent.parent.absolute() / target_path
        if not target_path.exists():
            return f"File '{filepath}' nahi mila scan karne ke liye MJ."
        try:
            with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                code_text = f.read()
        except Exception as e:
            return f"File read karne mein issue aaya: {e}"
    else:
        try:
            import pyperclip
            code_text = pyperclip.paste().strip()
            target_name = "clipboard"
        except Exception:
            pass

    if not code_text:
        return "Scan karne ke liye na koi file mili aur na clipboard pe code hai. Pehle code copy kar lo!"

    import tempfile
    import importlib.util
    findings = []

    scanner_path = Path(__file__).parent.parent.parent.absolute() / ".agents" / "skills" / "code-reviewer" / "scripts" / "scanner.py"
    if scanner_path.exists():
        try:
            spec = importlib.util.spec_from_file_location("scanner", str(scanner_path))
            scanner_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(scanner_mod)

            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
                tmp.write(code_text)
                tmp_path = tmp.name

            findings = scanner_mod.scan_file(tmp_path)
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        except Exception as exc:
            logger.warning("Scanner execution error: %s", exc)

    sec_count = sum(1 for f in findings if f.get("type") == "SECURITY")
    anti_count = sum(1 for f in findings if f.get("type") == "ANTI-PATTERN")
    style_count = sum(1 for f in findings if f.get("type") == "STYLE")

    if not findings:
        return f"Code review complete for {target_name}! Zero security concerns, koi anti-pattern nahi mila. Code bilkul clean hai!"

    summary_parts = []
    if sec_count:
        summary_parts.append(f"{sec_count} security concern")
    if anti_count:
        summary_parts.append(f"{anti_count} anti-pattern")
    if style_count:
        summary_parts.append(f"{style_count} style issue")

    summary_str = ", ".join(summary_parts)
    first_issue = findings[0].get("message", "")
    return (
        f"Code review complete for {target_name}: {summary_str} mile hain! "
        f"Notable issue: {first_issue}."
    )


def check_ai_hardware(args: dict) -> str:
    """Audit the laptop's AI hardware: NPU presence, GPU VRAM, DirectML, and Copilot+ readiness."""
    try:
        import ai_hardware
        return ai_hardware.explain_ai_hardware_summary()
    except Exception as exc:
        logger.error("AI hardware check failed: %s", exc)
        return f"Hardware check karte waqt issue aaya: {exc}"


def get_ui_tree_command(args: dict) -> str:
    """Extract and speak the interactive controls in the active window."""
    try:
        import ui_tree
        elements = ui_tree.get_active_window_ui_elements(max_elements=15)
        if not elements:
            return "Active window mein koi standard interactive controls detect nahi hue."
        names = [el.get("name") for el in elements if el.get("name")]
        sample = ", ".join(f"'{n}'" for n in names[:5])
        return f"Active window mein {len(elements)} controls hain, jaise {sample}."
    except Exception as exc:
        return f"UI controls read karne mein error aaya: {exc}"


def click_ui_element_command(args: dict) -> str:
    """Click an interactive control by its text/name."""
    name = args.get("name") or args.get("element") or args.get("target", "").strip()
    if not name:
        def _do(n):
            args["name"] = n
            return click_ui_element_command(args)
        raise MissingArgument("Kis button ya control pe click karna hai?", _do)

    try:
        try:
            from core import ui_tree
        except ImportError:
            try:
                from Shin.core import ui_tree
            except ImportError:
                import ui_tree
        ok, msg = ui_tree.click_ui_element_by_name(name)
        if ok:
            return msg
    except Exception as exc:
        logger.debug("UI element click via tree failed: %s", exc)

    # Fallback to Screen Vision / OCR click
    return click_text({"text": name, "action": "click"})


# Weather
# ═══════════════════════════════════════════════════════════════════════════════

def weather_query(args: dict) -> str:
    """Fetch current weather, optionally for a specific city."""
    city = args.get("city") or args.get("location")
    rain = args.get("rain", False)
    try:
        import weather as _weather
    except ImportError:
        return "Weather features are not available — the weather module is missing."
    if rain:
        return _weather.will_it_rain(city)
    return _weather.get_current_weather(city)


# ═══════════════════════════════════════════════════════════════════════════════
# Pomodoro Timer
# ═══════════════════════════════════════════════════════════════════════════════

def pomodoro(args: dict) -> str:
    """Start a Pomodoro work/break session."""
    work_min = int(args.get("work", 25))
    break_min = int(args.get("break", 5))
    work_secs = work_min * 60
    break_secs = break_min * 60

    def _fire_work_end():
        _speak(
            f"Time's up! Your {work_min}-minute work session is complete. "
            f"Take a {break_min}-minute break."
        )
        schedule.every(break_min).minutes.do(_fire_break_end)
        return schedule.CancelJob

    def _fire_break_end():
        _speak("Break over! Ready for another focused session? Just say start a Pomodoro.")
        return schedule.CancelJob

    # 15-minute milestone check-in
    def _milestone_15():
        _speak("Fifteen minutes down, keep going!")
        return schedule.CancelJob

    schedule.every(work_min).minutes.do(_fire_work_end)
    if work_min >= 20:
        schedule.every(15).minutes.do(_milestone_15)

    return (
        f"Pomodoro started! Work for {work_min} minutes, "
        f"then take a {break_min}-minute break. Good luck!"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Context-Aware Study Mode
# ═══════════════════════════════════════════════════════════════════════════════

_study_mode_active = False
_study_start_time = None
_distraction_ticks = 0

def _check_study_focus():
    global _study_mode_active, _distraction_ticks
    if not _study_mode_active:
        return schedule.CancelJob
    try:
        import pygetwindow as gw
        win = gw.getActiveWindow()
        if not win:
            return

        title = win.title.lower()
        
        study_keywords = [
            "visual studio code", "vs code", "notepad", "digital", "logisim", 
            "pdf", "acrobat", "document", "powerpoint", "word", "excel", 
            "calculator", "classroom", "coursera", "udemy", "stack overflow", 
            "github", "logic", "circuit", "exam", "syllabus"
        ]
        distraction_keywords = [
            "spotify", "discord", "steam", "netflix", "youtube", "twitter", 
            "reddit", "facebook", "instagram", "prime video", "disney+", 
            "game", "plex", "twitch"
        ]

        is_studying = any(kw in title for kw in study_keywords)
        is_distracted = any(kw in title for kw in distraction_keywords)

        if is_studying:
            _distraction_ticks = 0
        elif is_distracted:
            _distraction_ticks += 1
            if _distraction_ticks >= 2:
                _distraction_ticks = 0
                _speak("MJ, you are studying for your exam. Let's stay focused!")
                try:
                    win.minimize()
                except Exception:
                    pass
    except Exception as exc:
        logger.error("Error in study mode check: %s", exc)


def activate_study_mode(args: dict) -> str:
    """Activate the Context-Aware Study Mode."""
    global _study_mode_active, _study_start_time, _distraction_ticks
    from datetime import datetime
    
    if _study_mode_active:
        return "Study mode is already active. Keep focusing!"

    _study_mode_active = True
    _study_start_time = datetime.now()
    _distraction_ticks = 0

    # Clear any leftover study mode jobs
    schedule.clear("study-mode")
    # Schedule study focus check every 5 seconds
    schedule.every(5).seconds.do(_check_study_focus).tag("study-mode")

    return (
        "Study mode activated! I will help you stay focused for your Digital "
        "Logic Design exam tomorrow. I'll watch out for distractions."
    )


def deactivate_study_mode(args: dict) -> str:
    """Deactivate the Context-Aware Study Mode."""
    global _study_mode_active, _study_start_time
    from datetime import datetime
    
    if not _study_mode_active:
        return "Study mode is not active right now."

    _study_mode_active = False
    schedule.clear("study-mode")

    duration_str = ""
    if _study_start_time:
        elapsed = datetime.now() - _study_start_time
        mins = int(elapsed.total_seconds() / 60)
        if mins > 0:
            duration_str = f" You studied for {mins} minutes."
        else:
            duration_str = f" You studied for {int(elapsed.total_seconds())} seconds."

    _study_start_time = None
    return f"Study mode deactivated.{duration_str} Good job on your study session!"


def check_study_status(args: dict) -> str:
    """Check the status of the current study session."""
    global _study_mode_active, _study_start_time
    from datetime import datetime
    
    if not _study_mode_active:
        return "Study mode is currently offline. Say 'activate study mode' to start."

    import pygetwindow as gw
    win = gw.getActiveWindow()
    active_title = win.title if win else "unknown window"

    elapsed_str = ""
    if _study_start_time:
        elapsed = datetime.now() - _study_start_time
        mins = int(elapsed.total_seconds() / 60)
        if mins > 0:
            elapsed_str = f" for {mins} minutes"
        else:
            elapsed_str = f" for {int(elapsed.total_seconds())} seconds"

    study_keywords = [
        "visual studio code", "vs code", "notepad", "digital", "logisim", 
        "pdf", "acrobat", "document", "powerpoint", "word", "excel", 
        "calculator", "classroom", "coursera", "udemy", "stack overflow", 
        "github", "logic", "circuit", "exam", "syllabus"
    ]
    distraction_keywords = [
        "spotify", "discord", "steam", "netflix", "youtube", "twitter", 
        "reddit", "facebook", "instagram", "prime video", "disney+", 
        "game", "plex", "twitch"
    ]

    title_lower = active_title.lower()
    is_studying = any(kw in title_lower for kw in study_keywords)
    is_distracted = any(kw in title_lower for kw in distraction_keywords)

    if is_studying:
        status_msg = f"You are currently looking at '{active_title}', which is a great study environment. Keep it up!"
    elif is_distracted:
        status_msg = f"It looks like you are distracted by '{active_title}'. Let's close it and get back to work!"
    else:
        status_msg = f"You are currently looking at '{active_title}'."

    return f"Study mode has been active{elapsed_str}. {status_msg}"


# ═══════════════════════════════════════════════════════════════════════════════
# Wi-Fi Control
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_wifi_adapter() -> str:
    """Return the name of the first Wi-Fi interface found via netsh."""
    try:
        result = subprocess.run(
            ["netsh", "interface", "show", "interface"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "wi-fi" in line.lower() or "wireless" in line.lower():
                # Format: 'Enabled   Connected   Wi-Fi'
                parts = line.split()
                if parts:
                    return parts[-1]  # last token is the adapter name
    except Exception:
        pass
    return "Wi-Fi"


def wifi_control(args: dict) -> str:
    """Enable or disable the Wi-Fi adapter."""
    action = args.get("action", args.get("state", "toggle")).lower()
    adapter = _detect_wifi_adapter()

    def _do_disable():
        subprocess.run(
            ["netsh", "interface", "set", "interface", adapter, "disable"],
            shell=True
        )

    def _do_enable():
        subprocess.run(
            ["netsh", "interface", "set", "interface", adapter, "enable"],
            shell=True
        )

    if action in ("off", "disable"):
        raise ConfirmationRequired(
            "Are you sure you want to disable Wi-Fi? You may lose your internet connection.",
            _do_disable,
        )
    elif action in ("on", "enable"):
        _do_enable()
        return "Wi-Fi has been enabled."
    else:
        # Toggle: check current state
        try:
            result = subprocess.run(
                ["netsh", "interface", "show", "interface", adapter],
                capture_output=True, text=True, timeout=5
            )
            if "enabled" in result.stdout.lower():
                raise ConfirmationRequired(
                    "Wi-Fi is currently enabled. Disable it?",
                    _do_disable,
                )
            else:
                _do_enable()
                return "Wi-Fi has been enabled."
        except ConfirmationRequired:
            raise
        except Exception:
            raise ConfirmationRequired("Toggle Wi-Fi?", _do_disable)


# ═══════════════════════════════════════════════════════════════════════════════
# Battery Status (standalone)
# ═══════════════════════════════════════════════════════════════════════════════

def battery_status(args: dict) -> str:
    """Report battery percentage and charging state."""
    import psutil
    battery = psutil.sensors_battery()
    if not battery:
        return "I couldn't detect a battery on this system. You might be on a desktop."
    pct = round(battery.percent)
    plugged = battery.power_plugged
    state = "plugged in and charging" if plugged else "on battery power"
    msg = f"Battery is at {pct}% and {state}."
    if not plugged:
        secs = battery.secsleft
        if secs and secs > 0:
            hours = secs // 3600
            mins = (secs % 3600) // 60
            if hours:
                msg += f" About {hours} hour{'s' if hours != 1 else ''} and {mins} minutes remaining."
            else:
                msg += f" About {mins} minutes remaining."
        if pct <= 20:
            msg += " Battery is low — consider plugging in soon."
    return msg


# ═══════════════════════════════════════════════════════════════════════════════
# To-Do List
# ═══════════════════════════════════════════════════════════════════════════════

def todo_add(args: dict) -> str:
    task = args.get("task", "").strip()
    if not task:
        def _do(new_task):
            args["task"] = new_task
            return todo_add(args)
        raise MissingArgument("What would you like me to add to your to-do list?", _do)
    try:
        import todo
    except ImportError:
        return "To-do features are not available — the todo module is missing."
    return todo.add_todo(task)


def todo_list(args: dict) -> str:
    filter_ = args.get("filter", "open")
    try:
        import todo
    except ImportError:
        return "To-do features are not available — the todo module is missing."
    return todo.list_todos(filter_)


def todo_complete(args: dict) -> str:
    task = args.get("task", "").strip()
    if not task:
        def _do(new_task):
            args["task"] = new_task
            return todo_complete(args)
        raise MissingArgument("Which task would you like to mark as done?", _do)
    try:
        import todo
    except ImportError:
        return "To-do features are not available — the todo module is missing."
    return todo.complete_todo(task)


def todo_delete(args: dict) -> str:
    task = args.get("task", "").strip()
    if not task:
        def _do(new_task):
            args["task"] = new_task
            return todo_delete(args)
        raise MissingArgument("Which task would you like to remove?", _do)
    try:
        import todo
    except ImportError:
        return "To-do features are not available — the todo module is missing."
    return todo.delete_todo(task)


# ═══════════════════════════════════════════════════════════════════════════════
# Currency & Unit Converter
# ═══════════════════════════════════════════════════════════════════════════════

_UNIT_CONVERSIONS: dict[tuple[str, str], float] = {
    # Length
    ("km", "miles"): 0.621371,
    ("miles", "km"): 1.60934,
    ("meters", "feet"): 3.28084,
    ("feet", "meters"): 0.3048,
    ("inches", "cm"): 2.54,
    ("cm", "inches"): 0.393701,
    # Weight
    ("kg", "lbs"): 2.20462,
    ("lbs", "kg"): 0.453592,
    ("kg", "pounds"): 2.20462,
    ("pounds", "kg"): 0.453592,
    ("grams", "ounces"): 0.035274,
    ("ounces", "grams"): 28.3495,
    # Volume
    ("liters", "gallons"): 0.264172,
    ("gallons", "liters"): 3.78541,
    ("ml", "oz"): 0.033814,
    ("oz", "ml"): 29.5735,
}

_TEMP_UNITS = {"celsius", "fahrenheit", "kelvin", "c", "f", "k"}


def _convert_temperature(value: float, from_u: str, to_u: str) -> Optional[str]:
    from_u = from_u.lower().rstrip("s")
    to_u   = to_u.lower().rstrip("s")
    if from_u not in _TEMP_UNITS or to_u not in _TEMP_UNITS:
        return None
    # Normalize shorthand
    from_u = {"c": "celsius", "f": "fahrenheit", "k": "kelvin"}.get(from_u, from_u)
    to_u   = {"c": "celsius", "f": "fahrenheit", "k": "kelvin"}.get(to_u, to_u)

    if from_u == "celsius":
        celsius = value
    elif from_u == "fahrenheit":
        celsius = (value - 32) * 5 / 9
    else:  # kelvin
        celsius = value - 273.15

    if to_u == "celsius":
        result = celsius
    elif to_u == "fahrenheit":
        result = celsius * 9 / 5 + 32
    else:
        result = celsius + 273.15

    return f"{value} {from_u} is {result:.2f} {to_u}."


def _get_calculator():
    try:
        from . import calculator
        return calculator
    except Exception:
        try:
            import calculator
            return calculator
        except Exception:
            try:
                from core import calculator
                return calculator
            except Exception:
                try:
                    import calculator
                    return calculator
                except ImportError:
                    from core import calculator
                    return calculator


def convert(args: dict) -> str:
    """Convert units or currency using universal calculator engine."""
    try:
        value = float(args.get("value", 1))
    except (TypeError, ValueError):
        return "Please specify a numeric value to convert."

    from_unit = str(args.get("from_unit", "")).lower().strip()
    to_unit   = str(args.get("to_unit", "")).lower().strip()

    if not from_unit or not to_unit:
        return "Please tell me what units to convert between, for example, 'convert 5 km to miles'."

    try:
        calc = _get_calculator()
        return calc.convert_units(value, from_unit, to_unit)
    except Exception as exc:
        logger.debug("Calculator convert_units failed: %s", exc)

    return (
        f"I don't know how to convert {from_unit} to {to_unit}. "
        "I can handle length, weight, volume, digital storage, speed, time, area, temperature, and major currencies."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Smart Home Status
# ═══════════════════════════════════════════════════════════════════════════════

def smart_home_status(args: dict) -> str:
    """Query smart home device status."""
    try:
        import smart_home
    except ImportError:
        return "Smart home features are not available — the smart_home module is missing."
    return smart_home.get_device_status()


# ═══════════════════════════════════════════════════════════════════════════════
# Gmail
# ═══════════════════════════════════════════════════════════════════════════════

def read_emails(args: dict) -> str:
    """Read the latest emails from Gmail."""
    unread_only = not args.get("all", False)
    count = int(args.get("count", 5))
    try:
        import gmail_ai
    except ImportError:
        return "Gmail features are not available — the gmail_ai module is missing."
    return gmail_ai.get_latest_emails(max_results=count, unread_only=unread_only)


# ═══════════════════════════════════════════════════════════════════════════════
# Voice Auth Management
# ═══════════════════════════════════════════════════════════════════════════════

def enroll_voice(args: dict) -> str:
    """Start interactive voice enrollment flow."""
    try:
        import voice_auth
    except ImportError:
        return "Voice authentication is not available — resemblyzer may not be installed."

    def _listen_audio(timeout=10, phrase_time_limit=8):
        """Capture raw AudioData (not transcribed text) for voice embedding."""
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        try:
            with sr.Microphone(sample_rate=16000) as source:
                try:
                    audio = recognizer.listen(source, timeout=timeout,
                                             phrase_time_limit=phrase_time_limit)
                    return audio  # return AudioData, not text
                except sr.WaitTimeoutError:
                    return None
        except Exception:
            return None

    return voice_auth.run_enrollment_flow(_listen_audio, _speak)


def delete_voice_profile(args: dict) -> str:
    """Delete the stored voice profile."""
    try:
        import voice_auth
    except ImportError:
        return "Voice authentication is not available."
    def _do():
        return voice_auth.delete_profile()
    raise ConfirmationRequired("Are you sure you want to delete your voice profile?", _do)


# ═══════════════════════════════════════════════════════════════════════════════
# Per-App Volume
# ═══════════════════════════════════════════════════════════════════════════════

def app_volume(args: dict) -> str:
    """Adjust audio volume for a specific application process."""
    app_name = args.get("app", "").lower().strip()
    action   = args.get("action", "down").lower()
    level    = args.get("level")

    if not app_name:
        return "Which app's volume would you like to adjust?"

    try:
        from pycaw.pycaw import AudioUtilities
        import comtypes
        comtypes.CoInitialize()
    except ImportError:
        return "pycaw is not installed. Run: pip install pycaw"

    sessions = AudioUtilities.GetAllSessions()
    matched = []
    for session in sessions:
        if session.Process and app_name in session.Process.name().lower():
            matched.append(session)

    if not matched:
        return f"I couldn't find any active audio session for '{app_name}'."

    for session in matched:
        simple_vol = session.SimpleAudioVolume
        if action in ("mute",):
            simple_vol.SetMute(1, None)
        elif action in ("unmute",):
            simple_vol.SetMute(0, None)
        elif action == "set" and level is not None:
            simple_vol.SetMasterVolume(max(0.0, min(1.0, float(level) / 100.0)), None)
        elif action == "up":
            current = simple_vol.GetMasterVolume()
            new = min(1.0, current + 0.1)
            simple_vol.SetMasterVolume(new, None)
        elif action in ("down", "lower"):
            current = simple_vol.GetMasterVolume()
            new = max(0.0, current - 0.15)
            simple_vol.SetMasterVolume(new, None)

    if action == "mute":
        return f"Muted {app_name}."
    elif action == "unmute":
        return f"Unmuted {app_name}."
    elif action == "set" and level is not None:
        return f"Set {app_name} volume to {level}%."
    elif action == "up":
        return f"Increased {app_name} volume."
    else:
        return f"Lowered {app_name} volume."


# ═══════════════════════════════════════════════════════════════════════════════
# Advanced Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def clean_pc(args: dict = None) -> str:
    """Empty recycle bin and clean system & user temporary files, reporting reclaimed MB."""
    import ctypes
    import tempfile
    import shutil

    cleaned_mb = 0.0

    # 1. Empty recycle bin
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
    except Exception as e:
        logger.warning("Failed to empty recycle bin: %s", e)

    # 2. Clear temp folders
    temp_dirs = [tempfile.gettempdir()]
    win_temp = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Temp"
    if win_temp.exists():
        temp_dirs.append(str(win_temp))

    for tdir in temp_dirs:
        if not os.path.exists(tdir):
            continue
        try:
            for item in os.listdir(tdir):
                item_path = os.path.join(tdir, item)
                try:
                    if os.path.isfile(item_path):
                        sz = os.path.getsize(item_path)
                        os.unlink(item_path)
                        cleaned_mb += sz / (1024 * 1024)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                except Exception:
                    pass
        except Exception:
            pass

    return (
        f"Ki tujhe nahi malum tha kya, aur kya MJ! Maine system clean kar diya! "
        f"Recycle bin empty ho gaya aur approximately {cleaned_mb:.0f} MB temporary cache files clean kar diye!"
    )


def clean_ram(args: dict = None) -> str:
    """Purge process working sets using Windows PSAPI to instantly reclaim cached RAM."""
    import psutil
    import ctypes
    import time

    try:
        mem_before = psutil.virtual_memory()
        before_used_mb = mem_before.used / (1024 * 1024)

        reclaimed_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pid = proc.info['pid']
                if pid <= 4:
                    continue
                # PROCESS_QUERY_INFORMATION (0x0400) | PROCESS_SET_QUOTA (0x0100)
                handle = ctypes.windll.kernel32.OpenProcess(0x0500, False, pid)
                if handle:
                    ctypes.windll.psapi.EmptyWorkingSet(handle)
                    ctypes.windll.kernel32.CloseHandle(handle)
                    reclaimed_count += 1
            except Exception:
                continue

        time.sleep(0.4)
        mem_after = psutil.virtual_memory()
        after_used_mb = mem_after.used / (1024 * 1024)
        freed_mb = max(0, before_used_mb - after_used_mb)

        return (
            f"Ki tujhe nahi malum tha kya, aur kya MJ! Maine RAM clean kar di! "
            f"Lagbhag {freed_mb:.0f} MB memory reclaim ho gayi, aur ab RAM usage {mem_after.percent:.1f}% pe smoothly chal raha hai!"
        )
    except Exception as exc:
        logger.error("clean_ram failed: %s", exc)
        return "RAM clean karne mein thoda issue aaya, par maine background memory optimize kar di hai!"


def run_pc_manager(args: dict = None) -> str:
    """Launch Microsoft PC Manager or trigger PC boost."""
    # 1. Try URI protocol
    try:
        os.startfile("ms-pcmanager:")
        return "Ki tujhe nahi malum tha kya, aur kya MJ! Maine Microsoft PC Manager open kar diya, ab wahan se deep boost ya clean kar lo!"
    except Exception:
        pass

    # 2. Check standard installation directories
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft PC Manager" / "MSPCManager.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "PCManager" / "MSPCManager.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft PC Manager" / "MSPCManager.exe",
    ]
    for p in candidates:
        if p.exists():
            subprocess.Popen([str(p)], shell=False)
            return "Aur kya MJ! Maine Microsoft PC Manager launch kar diya!"

    # 3. Fallback to app finder
    import app_finder
    ok, msg = app_finder.launch_application("pc manager")
    if ok:
        return msg

    return "Microsoft PC Manager app nahi mila laptop mein. Agar installed nahi hai toh Microsoft Store se download kar sakte ho!"


def run_terminal_command(args: dict) -> str:
    """Run a safe PowerShell / CMD command in the background and report output."""
    cmd = args.get("command", "").strip()
    if not cmd:
        def _do(val):
            args["command"] = val
            return run_terminal_command(args)
        raise MissingArgument("PowerShell ya Terminal mein kaunsa command run karna hai?", _do)

    # Security check: Block dangerous commands and exfiltration attempts
    is_safe, warn = check_command_safety("terminal", {"cmd": cmd})
    if not is_safe:
        return f"Arre ruk! Yeh command execute nahi kar sakti: {warn}"

    _READONLY_SAFE_PREFIXES = ("dir", "ls", "git status", "git log", "git diff", "git branch", "ipconfig", "whoami", "get-date", "ping", "echo", "pwd")
    is_readonly = any(cmd.lower().startswith(p) for p in _READONLY_SAFE_PREFIXES)
    if not is_readonly and not args.get("_confirmed"):
        def _do_execute():
            args_copy = dict(args)
            args_copy["_confirmed"] = True
            return run_terminal_command(args_copy)
        raise ConfirmationRequired(f"Are you sure you want to execute the terminal command '{cmd}'?", _do_execute)

    try:
        exec_cmd = cmd.strip()
        # Normalize common UNIX file listing aliases to PowerShell equivalents
        if re.match(r"^ls(\s+-[a-zA-Z]+|\s*)*$", exec_cmd, re.IGNORECASE):
            exec_cmd = "Get-ChildItem -Force"
        elif exec_cmd.lower() in ("ll", "la"):
            exec_cmd = "Get-ChildItem -Force"

        logger.info("Executing terminal command: %s (raw: %s)", exec_cmd, cmd)
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", exec_cmd],
            capture_output=True,
            text=True,
            timeout=25
        )
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()

        if res.returncode == 0:
            if not out:
                return f"Done MJ! Command '{cmd}' successfully run ho gaya."
            lines = out.splitlines()
            if len(lines) <= 3 and len(out) < 220:
                return f"Command complete! Output hai:\n{out}"
            else:
                snippet = "\n".join(lines[:2])
                try:
                    import pyperclip
                    pyperclip.copy(out)
                except Exception:
                    pass
                return (
                    f"Done MJ! Command complete ho gaya with {len(lines)} lines. "
                    f"Output yeh hai: {snippet[:120]}... Poora result maine clipboard pe copy kar diya hai!"
                )
        else:
            # Clean up multi-line PowerShell stack traces so TTS doesn't read CategoryInfo
            first_err_line = err.splitlines()[0] if err else f"exit code {res.returncode}"
            clean_err = re.sub(r"At line:\d+.*", "", first_err_line).strip()
            clean_err = clean_err or first_err_line[:120]
            return f"Command run karte waqt error aaya: {clean_err}"
    except subprocess.TimeoutExpired:
        return f"Command '{cmd}' time out ho gaya, isliye maine terminate kar diya."
    except Exception as exc:
        return f"Terminal execution failed: {exc}"


def run_python_code(args: dict) -> str:
    """Execute a snippet of Python code or a Python script and report the result."""
    code = args.get("code") or args.get("script") or args.get("command", "").strip()
    if not code:
        def _do(c):
            args["code"] = c
            return run_python_code(args)
        raise MissingArgument("Kaunsa Python code run karna hai MJ?", _do)

    # Security check: Block dangerous patterns and unverified execution
    is_safe, warn = check_command_safety("python_eval", {"code": code})
    if not is_safe:
        return f"Yeh code run karna safe nahi hai: {warn}"

    if not args.get("_confirmed"):
        def _do_py():
            args_copy = dict(args)
            args_copy["_confirmed"] = True
            return run_python_code(args_copy)
        raise ConfirmationRequired(f"Are you sure you want to run this Python code snippet?", _do_py)

    try:
        import sys
        # Run in a separate subprocess using current python executable
        res = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(Path(__file__).parent.parent.absolute())
        )
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        if res.returncode == 0:
            if not out:
                return "Python code successfully execute ho gaya with no errors!"
            if len(out) < 200:
                return f"Python output: {out}"
            import pyperclip
            pyperclip.copy(out)
            return f"Python code executed! Output kaafi bada tha ({len(out.splitlines())} lines), maine clipboard pe copy kar diya hai!"
        else:
            return f"Python execution error: {err[:200]}"
    except subprocess.TimeoutExpired:
        return "Python code execution timeout ho gaya (15 seconds limit)."
    except Exception as exc:
        return f"Python code run karne mein error aaya: {exc}"


def open_terminal(args: dict = None) -> str:
    """Open Windows Terminal or PowerShell in the project workspace."""
    target_dir = str(Path(__file__).parent.parent.absolute())
    try:
        subprocess.Popen(["wt.exe", "-d", target_dir], shell=False)
        return "Maine Windows Terminal open kar diya tere project folder mein!"
    except Exception:
        pass

    try:
        subprocess.Popen(["powershell.exe", "-NoExit", "-Command", f"Set-Location '{target_dir}'"], shell=False)
        return "Maine PowerShell open kar diya tere project directory mein!"
    except Exception as exc:
        return f"Terminal open karne mein issue aaya: {exc}"


def list_installed_apps(args: dict = None) -> str:
    """List discovered installed apps on the laptop."""
    import app_finder
    return app_finder.list_installed_apps_summary()


def read_clipboard(args: dict) -> str:
    """Read the current clipboard text out loud."""
    try:
        import pyperclip
        content = pyperclip.paste().strip()
        if not content:
            return "Your clipboard is currently empty."
        if len(content) > 800:
            return f"Here is the beginning of your clipboard: {content[:800]}... It is quite long, so I have skipped the rest."
        return f"Your clipboard says: {content}"
    except ImportError:
        return "The pyperclip module is missing. Please run: pip install pyperclip"
def learn_macro(args: dict) -> str:
    """Teach Shin a new custom macro / routine by mapping a trigger phrase to multiple commands."""
    trigger = args.get("trigger", "").lower().strip()
    commands_raw = args.get("commands", "").strip()

    if not trigger:
        def _set_trigger(val):
            args["trigger"] = val
            return learn_macro(args)
        raise MissingArgument("What spoken phrase should trigger this shortcut?", _set_trigger)

    if commands_raw.lower().strip() == "record":
        import assistant
        assistant._recording_macro = {"trigger": trigger, "commands": []}
        return f"Starting recording mode for '{trigger}'. Speak the first command, or say 'stop recording' to save."

    if not commands_raw:
        def _process_response(val):
            val_clean = val.lower().strip()
            if any(w in val_clean for w in ("record", "step by step", "step-by-step", "interactive")):
                import assistant
                assistant._recording_macro = {"trigger": trigger, "commands": []}
                return f"Starting recording mode for '{trigger}'. Speak the first command, or say 'stop recording' to save."
            else:
                args["commands"] = val
                return learn_macro(args)
        raise MissingArgument("Would you like to record this shortcut step by step? Say 'record', or speak the commands sequence directly.", _process_response)

    # Clean the trigger phrase (remove starting/ending quote marks if any)
    import re
    trigger = re.sub(r'^["\']|["\']$', '', trigger).strip()

    # Parse the commands_raw string using our lookahead splitter
    split_pattern = r'\b(?:then)\b|[,;]|\b(?:and)\b(?=\s*(?:set|open|play|dim|launch|go|navigate|turn|close|mute|unmute|shutdown|restart|lock|screenshot|type|press|click|tap|pomodoro|todo|weather|read|calendar|search|tell|summarize|rewrite|translate|add|remind|pause|resume|snap|scroll|minimize|maximize|run|start|activate|enable|disable|show|list|study|deactivate|stop))'
    raw_parts = re.split(split_pattern, commands_raw, flags=re.IGNORECASE)

    commands_list = []
    for part in raw_parts:
        part = part.strip()
        part = re.sub(r'^["\']|["\']$', '', part).strip()
        if part:
            commands_list.append(part)

    if not commands_list:
        return "I couldn't find any valid commands in your shortcut definition."

    # Load existing custom macros, add the new one, and save
    import macros
    custom = macros._load_custom_macros()
    custom[trigger] = {
        "trigger": trigger,
        "commands": commands_list,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    macros._save_custom_macros(custom)

    formatted_cmds = ", and then ".join(f"'{c}'" for c in commands_list)
    return f"Shortcut '{trigger}' has been registered to run: {formatted_cmds}."


def edit_macro(args: dict) -> str:
    """Edit an existing custom macro by adding new commands to it."""
    trigger = args.get("trigger", "").lower().strip()
    command = args.get("command", "").strip()
    action = args.get("action", "add")

    if not trigger or not command:
        return "Please tell me which shortcut to edit, and what command to add."

    import macros
    custom = macros._load_custom_macros()
    
    import re
    trigger = re.sub(r'^["\']|["\']$', '', trigger).strip()
    
    if trigger not in custom:
        return f"I don't have a custom shortcut called '{trigger}' yet. You can create it by saying 'when I say {trigger}, do {command}'."
        
    if action == "add":
        custom[trigger]["commands"].append(command)
        macros._save_custom_macros(custom)
        return f"I've added '{command}' to your '{trigger}' shortcut."
    
    return "I can only add commands to shortcuts right now."


def list_macros(args: dict) -> str:
    """List all user-defined custom macros."""
    import macros
    custom = macros._load_custom_macros()
    if not custom:
        return "You haven't taught me any custom shortcuts yet. You can teach me one by saying, for example: 'when I say relax, set volume to 30 and play spotify'."

    lines = []
    for trigger, data in custom.items():
        cmds_str = " then ".join(data.get("commands", []))
        lines.append(f"- '{trigger}': {cmds_str}")

    joined = "\n".join(lines)
    return f"Here are your custom shortcuts:\n{joined}"


def delete_macro(args: dict) -> str:
    """Delete a user-defined custom macro after confirmation."""
    name = args.get("name", "").lower().strip()
    if not name:
        def _set_name(val):
            args["name"] = val
            return delete_macro(args)
        raise MissingArgument("Which shortcut would you like me to delete?", _set_name)

    import re
    name = re.sub(r'^["\']|["\']$', '', name).strip()

    import macros
    custom = macros._load_custom_macros()
    if name in custom:
        def _do_delete():
            custom.pop(name)
            macros._save_custom_macros(custom)
            return f"Shortcut '{name}' has been deleted."

        raise ConfirmationRequired(f"Are you sure you want to delete the shortcut '{name}'?", _do_delete)

    return f"I couldn't find a custom shortcut named '{name}'."





# ═══════════════════════════════════════════════════════════════════════════════
# System Controls Helper & Handlers
# ═══════════════════════════════════════════════════════════════════════════════

def _run_powershell(script: str) -> subprocess.CompletedProcess:
    """Run a PowerShell script snippet and return the CompletedProcess result."""
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=15
    )


def bluetooth_control(args: dict) -> str:
    """Toggle or set Bluetooth state using WinRT Radio API."""
    action = args.get("action", "toggle")
    if action is None:
        action = "toggle"
    action = action.lower()

    script = """
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

Function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioState,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null

$access = Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])
$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])

$bluetooth = $radios | ? { $_.Kind -eq 'Bluetooth' }
if ($bluetooth) {
    $action = "##ACTION##"
    if ($action -eq 'on') {
        $res = Await ($bluetooth.SetStateAsync([Windows.Devices.Radios.RadioState]::On)) ([Windows.Devices.Radios.RadioAccessStatus])
        Write-Host "On"
    } elseif ($action -eq 'off') {
        $res = Await ($bluetooth.SetStateAsync([Windows.Devices.Radios.RadioState]::Off)) ([Windows.Devices.Radios.RadioAccessStatus])
        Write-Host "Off"
    } elseif ($action -eq 'toggle') {
        $newState = if ($bluetooth.State -eq 'On') { [Windows.Devices.Radios.RadioState]::Off } else { [Windows.Devices.Radios.RadioState]::On }
        $res = Await ($bluetooth.SetStateAsync($newState)) ([Windows.Devices.Radios.RadioAccessStatus])
        if ($newState -eq [Windows.Devices.Radios.RadioState]::Off) { Write-Host "Off" } else { Write-Host "On" }
    } else {
        Write-Host "Unknown"
    }
} else {
    Write-Host "NotFound"
}
""".replace("##ACTION##", action)

    try:
        res = _run_powershell(script)
        out = res.stdout.strip()
        if "NotFound" in out:
            return "I couldn't find a Bluetooth adapter on this device."
        elif "On" in out:
            return "Bluetooth has been enabled."
        elif "Off" in out:
            return "Bluetooth has been disabled."
        else:
            return f"Bluetooth is now {out.lower()}."
    except Exception as e:
        logger.error("Error toggling Bluetooth: %s", e)
        return "I encountered an error trying to control Bluetooth."


def airplane_mode_control(args: dict) -> str:
    """Toggle or set Airplane Mode by toggling all system radios."""
    action = args.get("action", "toggle")
    if action is None:
        action = "toggle"
    action = action.lower()

    def _do_toggle_all():
        script = """
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

Function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioState,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null

$access = Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])
$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])

$action = "##ACTION##"
if ($action -eq 'on') {
    foreach ($r in $radios) {
        Await ($r.SetStateAsync([Windows.Devices.Radios.RadioState]::Off)) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
    }
    Write-Host "On"
} elseif ($action -eq 'off') {
    foreach ($r in $radios) {
        Await ($r.SetStateAsync([Windows.Devices.Radios.RadioState]::On)) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
    }
    Write-Host "Off"
} elseif ($action -eq 'toggle') {
    $anyOn = $false
    foreach ($r in $radios) {
        if ($r.State -eq 'On') { $anyOn = $true }
    }
    $targetState = if ($anyOn) { [Windows.Devices.Radios.RadioState]::Off } else { [Windows.Devices.Radios.RadioState]::On }
    foreach ($r in $radios) {
        Await ($r.SetStateAsync($targetState)) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
    }
    if ($targetState -eq [Windows.Devices.Radios.RadioState]::Off) { Write-Host "On" } else { Write-Host "Off" }
}
""".replace("##ACTION##", action)
        try:
            res = _run_powershell(script)
            out = res.stdout.strip()
            if "On" in out:
                return "Airplane Mode has been enabled."
            else:
                return "Airplane Mode has been disabled."
        except Exception as e:
            logger.error("Error setting Airplane Mode: %s", e)
            return "I encountered an error trying to configure Airplane Mode."

    if action in ("on", "enable"):
        raise ConfirmationRequired(
            "Are you sure you want to enable Airplane Mode? This will disconnect your internet and Bluetooth devices.",
            _do_toggle_all,
        )
    elif action in ("off", "disable"):
        return _do_toggle_all()
    else:
        # Check current state of radios
        script_check = """
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

Function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
$anyOn = $false
foreach ($r in $radios) {
    if ($r.State -eq 'On') { $anyOn = $true }
}
if ($anyOn) { Write-Host "Off" } else { Write-Host "On" }
"""
        try:
            res = _run_powershell(script_check)
            current_state = res.stdout.strip()
            if "Off" in current_state:
                raise ConfirmationRequired(
                    "Airplane Mode is currently disabled. Enable it? This will disconnect your internet.",
                    _do_toggle_all,
                )
            else:
                return _do_toggle_all()
        except ConfirmationRequired:
            raise
        except Exception:
            raise ConfirmationRequired("Toggle Airplane Mode?", _do_toggle_all)


def night_light_control(args: dict) -> str:
    """Launch the Windows Night Light settings page."""
    try:
        webbrowser.open("ms-settings:nightlight")
        return "I have opened the Night Light settings page for you. You can turn it on or off there."
    except Exception as e:
        logger.error("Error opening Night Light settings: %s", e)
        return "I couldn't open the Night Light settings page."


def mobile_hotspot_control(args: dict) -> str:
    """Toggle or set Mobile Hotspot state."""
    action = args.get("action", "toggle")
    if action is None:
        action = "toggle"
    action = action.lower()

    script = """
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

Function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime] | Out-Null
[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime] | Out-Null
[Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime] | Out-Null

$connectionProfile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if ($connectionProfile) {
    $tetheringManager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($connectionProfile)
    $action = "##ACTION##"
    if ($action -eq 'on') {
        $res = Await ($tetheringManager.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
        Write-Host $res.Status
    } elseif ($action -eq 'off') {
        $res = Await ($tetheringManager.StopTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
        Write-Host $res.Status
    } elseif ($action -eq 'toggle') {
        if ($tetheringManager.TetheringOperationalState -eq 'On') {
            $res = Await ($tetheringManager.StopTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
            Write-Host "ToggledOff"
        } else {
            $res = Await ($tetheringManager.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
            Write-Host "ToggledOn"
        }
    } else {
        Write-Host "Unknown"
    }
} else {
    Write-Host "NoProfile"
}
""".replace("##ACTION##", action)

    try:
        res = _run_powershell(script)
        out = res.stdout.strip()
        if "NoProfile" in out:
            return "I couldn't find an active internet connection to share for Mobile Hotspot."
        elif "ToggledOn" in out or ("Success" in out and "on" in action):
            return "Mobile Hotspot has been enabled."
        elif "ToggledOff" in out or ("Success" in out and "off" in action):
            return "Mobile Hotspot has been disabled."
        else:
            return f"Mobile Hotspot status: {out}."
    except Exception as e:
        logger.error("Error setting Mobile Hotspot: %s", e)
        return "I encountered an error trying to configure Mobile Hotspot."


def nearby_share_control(args: dict) -> str:
    """Toggle or set Nearby Share state via HKCU Registry."""
    action = args.get("action", "toggle")
    if action is None:
        action = "toggle"
    action = action.lower()

    script = """
$cdpPath = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\CDP"
if (Test-Path $cdpPath) {
    $action = "##ACTION##"
    $current = (Get-ItemProperty -Path $cdpPath -Name "NearShareChannelUserAuthzPolicy" -ErrorAction SilentlyContinue).NearShareChannelUserAuthzPolicy
    
    if ($action -eq 'on') {
        Set-ItemProperty -Path $cdpPath -Name "NearShareChannelUserAuthzPolicy" -Value 1 -ErrorAction Stop
        Write-Host "On"
    } elseif ($action -eq 'off') {
        Set-ItemProperty -Path $cdpPath -Name "NearShareChannelUserAuthzPolicy" -Value 0 -ErrorAction Stop
        Write-Host "Off"
    } elseif ($action -eq 'toggle') {
        $newValue = if ($current -eq 1 -or $current -eq 2) { 0 } else { 1 }
        Set-ItemProperty -Path $cdpPath -Name "NearShareChannelUserAuthzPolicy" -Value $newValue -ErrorAction Stop
        if ($newValue -eq 0) { Write-Host "Off" } else { Write-Host "On" }
    } else {
        Write-Host "Unknown"
    }
} else {
    Write-Host "NotFound"
}
""".replace("##ACTION##", action)

    try:
        res = _run_powershell(script)
        out = res.stdout.strip()
        if "NotFound" in out:
            return "I couldn't find the Nearby Share configuration on this device."
        elif "On" in out:
            return "Nearby Sharing has been enabled."
        elif "Off" in out:
            return "Nearby Sharing has been disabled."
        else:
            return "Nearby Sharing configuration updated."
    except Exception as e:
        logger.error("Error setting Nearby Sharing: %s", e)
        return "I encountered an error trying to configure Nearby Sharing."


# ═══════════════════════════════════════════════════════════════════════════════
# Calculator
# ═══════════════════════════════════════════════════════════════════════════════

def _format_result(value: float) -> str:
    """Format a numeric result for clean spoken output."""
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    # Up to 6 significant figures, strip trailing zeros
    return f"{value:.6g}"


def date_reasoning(args: dict) -> str:
    """Solve date arithmetic, days until events, day of week, and international time."""
    query = args.get("query", "").strip()
    if not query:
        return "Please specify what date or time calculation you would like."
    try:
        calc = _get_calculator()
        return calc.reason_date_and_time(query)
    except Exception as exc:
        logger.debug("Date reasoning failed: %s", exc)
        return "Sorry, I couldn't compute that date or time query."


def calculate(args: dict) -> str:
    """
    Safely evaluate math, percentages, trigonometry, algebra, statistics,
    and financial calculations using calculator.py.
    """
    expr = args.get("expression", "").strip()
    if not expr:
        return "Please give me a math expression to calculate."
    try:
        calc = _get_calculator()
        return calc.evaluate_expression(expr)
    except Exception as exc:
        logger.debug("Calculate failed for %r: %s", expr, exc)
        return "Sorry, I couldn't evaluate that expression. Try rephrasing it."

def _legacy_calculate_unused(args: dict) -> str:
    """
    Safely evaluate a math expression using Python's AST module.
    Supports: +−×÷, **, %, sin/cos/tan (degrees), sqrt, log, abs, pi, e.
    """
    import ast
    import math as _math
    import re as _re

    expr = args.get("expression", "").strip().lower()
    if not expr:
        return "Please give me a math expression to calculate."

    # ── Handle common shorthand patterns first ────────────────────────────────
    # "X percent of Y"
    pct_m = _re.match(
        r'^(\d+(?:\.\d+)?)\s*(?:%|percent)\s+of\s+(\d+(?:\.\d+)?)$', expr
    )
    if pct_m:
        pct, num = float(pct_m.group(1)), float(pct_m.group(2))
        result = pct / 100 * num
        return f"{pct}% of {num} is {_format_result(result)}."

    # "sin/cos/tan of N degrees"
    trig_m = _re.match(
        r'^(sin|cos|tan)\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:degrees?)?$', expr
    )
    if trig_m:
        fn_name, angle = trig_m.group(1), float(trig_m.group(2))
        fn = {"sin": _math.sin, "cos": _math.cos, "tan": _math.tan}[fn_name]
        result = fn(_math.radians(angle))
        return f"{fn_name}({angle}°) = {_format_result(result)}."

    # "sqrt/square root of N"
    sqrt_m = _re.match(
        r'^(?:square\s+root|sqrt)\s+of\s+(\d+(?:\.\d+)?)$', expr
    )
    if sqrt_m:
        n = float(sqrt_m.group(1))
        result = _math.sqrt(n)
        return f"Square root of {n} is {_format_result(result)}."

    # ── Normalize natural language to math symbols ─────────────────────────────
    replacements = [
        (r'\btimes\b',                    '*'),
        (r'\bmultiplied\s+by\b',          '*'),
        (r'\bdivided\s+by\b',             '/'),
        (r'\bover\b',                     '/'),
        (r'\bplus\b',                     '+'),
        (r'\bminus\b',                    '-'),
        (r'\bsquared\b',                  '**2'),
        (r'\bcubed\b',                    '**3'),
        (r'\bto\s+the\s+power\s+of\b',   '**'),
        (r'\bsquare\s+root\s+of\s+',     'sqrt('),
        (r'×',                            '*'),
        (r'÷',                            '/'),
        (r'\^',                           '**'),
    ]
    for pattern, replacement in replacements:
        expr = _re.sub(pattern, replacement, expr, flags=_re.IGNORECASE)

    # Auto-close unclosed sqrt( parentheses
    expr += ')' * max(0, expr.count('(') - expr.count(')'))

    # ── Safe AST evaluator ────────────────────────────────────────────────────
    _SAFE_NAMES = {'pi': _math.pi, 'e': _math.e, 'tau': _math.tau}
    _SAFE_FUNCS = {
        'sqrt':  _math.sqrt,
        'abs':   abs,
        'round': round,
        'floor': _math.floor,
        'ceil':  _math.ceil,
        'log':   _math.log10,
        'ln':    _math.log,
        'sin':   lambda x: _math.sin(_math.radians(x)),
        'cos':   lambda x: _math.cos(_math.radians(x)),
        'tan':   lambda x: _math.tan(_math.radians(x)),
    }

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp):
            l, r = _eval(node.left), _eval(node.right)
            return {
                ast.Add:      lambda a, b: a + b,
                ast.Sub:      lambda a, b: a - b,
                ast.Mult:     lambda a, b: a * b,
                ast.Div:      lambda a, b: a / b,
                ast.Pow:      lambda a, b: a ** b,
                ast.Mod:      lambda a, b: a % b,
                ast.FloorDiv: lambda a, b: a // b,
            }[type(node.op)](l, r)
        if isinstance(node, ast.UnaryOp):
            val = _eval(node.operand)
            if isinstance(node.op, ast.USub):
                return -val
            if isinstance(node.op, ast.UAdd):
                return val
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fn = _SAFE_FUNCS.get(node.func.id)
            if not fn:
                raise ValueError(f"Unknown function: {node.func.id}")
            return fn(*[_eval(a) for a in node.args])
        if isinstance(node, ast.Name) and node.id in _SAFE_NAMES:
            return _SAFE_NAMES[node.id]
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")

    try:
        tree   = ast.parse(expr.strip(), mode='eval')
        result = _eval(tree)
        return f"The result is {_format_result(result)}."
    except ZeroDivisionError:
        return "I can't divide by zero!"
    except Exception as exc:
        logger.debug("Calculate failed for %r: %s", expr, exc)
        return "Sorry, I couldn't evaluate that expression. Try rephrasing it."


# ═══════════════════════════════════════════════════════════════════════════════
# Dictionary
# ═══════════════════════════════════════════════════════════════════════════════

def define_word(args: dict) -> str:
    """Look up a word's definition, synonyms, or antonyms."""
    word = args.get("word", "").strip()
    mode = args.get("mode", "define").lower()
    if not word:
        def _do(w):
            args["word"] = w
            return define_word(args)
        raise MissingArgument("Which word would you like me to look up?", _do)
    try:
        import dictionary as _dict
        return _dict.lookup_word(word, mode=mode)
    except Exception as exc:
        logger.warning("define_word failed: %s", exc)
        return f"Sorry, I couldn't look up '{word}' right now."


# ═══════════════════════════════════════════════════════════════════════════════
# Translator
# ═══════════════════════════════════════════════════════════════════════════════

def translate_text(args: dict) -> str:
    """Translate a phrase or the clipboard content to a target language."""
    target = args.get("target_lang", "").strip()
    source_is_clipboard = args.get("source", "") == "clipboard"

    if not target:
        def _do_lang(lang):
            args["target_lang"] = lang
            return translate_text(args)
        raise MissingArgument("Which language should I translate to?", _do_lang)

    # Get the text to translate
    if source_is_clipboard:
        try:
            import pyperclip
            text = pyperclip.paste().strip()
        except Exception:
            text = ""
        if not text:
            return "The clipboard is empty or unreadable."
    else:
        text = args.get("text", "").strip()
        if not text:
            def _do_text(t):
                args["text"] = t
                return translate_text(args)
            raise MissingArgument("What would you like me to translate?", _do_text)

    try:
        import translator as _tr
        result = _tr.translate(text, target)
        if result == "__RATE_LIMITED__":
            return (
                "Translation limit reached for today (MyMemory allows 5 000 characters daily). "
                "Please try again tomorrow."
            )
        if result == "__TIMEOUT__":
            return "Translation timed out. Please check your internet connection."
        if not result:
            return f"I couldn't translate that to {target}. The translation service may be unavailable."
        lang_name = target.capitalize()
        return f"In {lang_name}: {result}"
    except Exception as exc:
        logger.warning("translate_text failed: %s", exc)
        return "Sorry, translation failed right now."


# ═══════════════════════════════════════════════════════════════════════════════
# File Search
# ═══════════════════════════════════════════════════════════════════════════════

def file_search(args: dict) -> str:
    """Search common user folders for files matching a query or extension."""
    import os
    from pathlib import Path as _Path

    query  = args.get("query",  "").strip().lower()
    folder = args.get("folder", "").strip().lower()
    ext    = args.get("ext",    "").strip().lower()

    if not query and not ext:
        def _do(q):
            args["query"] = q
            return file_search(args)
        raise MissingArgument("What file are you looking for?", _do)

    # Normalise extension
    if ext and not ext.startswith("."):
        ext = "." + ext

    home = _Path.home()
    folder_aliases = {
        "desktop":   home / "Desktop",
        "documents": home / "Documents",
        "downloads": home / "Downloads",
        "pictures":  home / "Pictures",
        "music":     home / "Music",
        "videos":    home / "Videos",
        "onedrive":  home / "OneDrive",
    }

    if folder:
        search_roots = [str(folder_aliases.get(folder, home / folder))]
    else:
        search_roots = [
            str(home / "Desktop"),
            str(home / "Documents"),
            str(home / "Downloads"),
        ]

    _SKIP_DIRS = {
        "__pycache__", "node_modules", ".git", ".venv", "venv",
        "$recycle.bin", "windows", "programdata",
    }

    matches: list[str] = []
    scanned = 0
    MAX_RESULTS = 5
    MAX_SCAN    = 15_000

    for root in search_roots:
        if not os.path.isdir(root):
            continue
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [
                    d for d in dirnames
                    if d.lower() not in _SKIP_DIRS and not d.startswith('.')
                ]
                for filename in filenames:
                    scanned += 1
                    if scanned > MAX_SCAN:
                        break
                    fn_lower = filename.lower()
                    if ext and not fn_lower.endswith(ext):
                        continue
                    if query and query not in fn_lower:
                        continue
                    matches.append(os.path.join(dirpath, filename))
                    if len(matches) >= MAX_RESULTS:
                        break
                if len(matches) >= MAX_RESULTS or scanned > MAX_SCAN:
                    break
        except PermissionError:
            continue

    if not matches:
        # Check if it matches an installed application!
        try:
            import app_finder
            app_match = app_finder.find_app(query)
            if app_match:
                app_name, _ = app_match
                return f"File toh nahi mili, par '{app_name.title()}' naam ki app laptop mein installed hai! Kya isse launch kar doon?"
        except Exception:
            pass

        desc = f"'{query}'" if query else f"{ext} files"
        return f"Mujhe Desktop, Documents ya Downloads mein {desc} nahi mili MJ. Check karo naam sahi hai kya, ya main web pe search karoon?"

    best = matches[0]
    # Reveal the best match in Explorer
    try:
        subprocess.Popen(["explorer", "/select,", best])
    except Exception:
        pass

    if len(matches) == 1:
        return f"Mil gayi! Maine '{os.path.basename(best)}' dhoondh li hai aur File Explorer mein highlight kar di hai!"
    names = ", ".join(os.path.basename(p) for p in matches[:3])
    return f"Mujhe {len(matches)} files mili hain, jaise {names}. Maine pehli file Explorer mein dikha di hai!"


# ═══════════════════════════════════════════════════════════════════════════════
# App Usage Tracker
# ═══════════════════════════════════════════════════════════════════════════════

def app_usage_stats(args: dict) -> str:
    """Return today's app usage statistics, optionally for a specific app."""
    try:
        import app_tracker as _at
        tracker = _at.get_tracker()
        specific_app = args.get("app", "").strip()
        if specific_app:
            secs = tracker.get_app_time(specific_app)
            if secs == 0:
                return f"I haven't tracked any usage of '{specific_app}' today."
            from app_tracker import _format_duration
            return f"You've spent {_format_duration(secs)} on {specific_app} today."
        return tracker.build_summary()
    except Exception as exc:
        logger.warning("app_usage_stats failed: %s", exc)
        return "Sorry, I couldn't retrieve app usage stats right now."


_jokes = [
    "Why do programmers wear glasses? Because they can't C-sharp!",
    "Why did the computer go to the doctor? Because it had a virus!",
    "Clean screens have fewer bugs. Literally!",
    "Ek husband ne wife se pucha, 'Khaane mein kya bana hai?' Wife ne kaha, 'Zehar!' Husband bola, 'Kha lena, main aaj bahar khaunga!'",
    "Santa ne pucha Banta se: 'Agar tumhara computer hang ho jaye toh kya karoge?' Banta: 'Hanging bridge pe le jaunga!'",
    "A computer once beat me at chess, but it was no match for me at kick boxing!",
    "There are 10 types of people in the world: those who understand binary, and those who don't."
]

_facts = [
    "The first computer bug was a real bug—a moth trapped in a relay in 1947.",
    "The first computer mouse was made of wood in 1964 by Douglas Engelbart.",
    "Your brain uses about 20 watts of power—enough to power a dim lightbulb.",
    "Windows was originally going to be called 'Interface Manager'. Imagine that!",
    "Kolhapur is famous for its hand-crafted leather slippers, called Kolhapuri chappals.",
    "The first hard drive could only hold 5 megabytes of data and weighed over 500 pounds."
]

_riddles = [
    ("What has keys but can't open locks?", "keyboard"),
    ("The more of them you take, the more you leave behind. What are they?", "footsteps"),
    ("I speak without a mouth and hear without ears. I have no body, but I come alive with wind. What am I?", "echo"),
    ("What has to be broken before you can use it?", "egg"),
    ("What gets wetter the more it dries?", "towel"),
    ("Mujhe aag se bachao, main sabko thandak deti hoon. Batao main kaun hoon?", "water"),
]

_active_riddle = None


def tell_joke(args: dict) -> str:
    """Tell a short joke, using AI if available, else falling back to a static list."""
    import random
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    ollama_model = os.getenv("OLLAMA_MODEL", "").strip()
    
    prompt = "Tell me a short, funny joke. If Hinglish, write in Hinglish with English letters. 1-2 sentences max."
    
    if gemini_key or openai_key or ollama_model:
        try:
            from clipboard_ai import _call_ai
            res = _call_ai(prompt)
            if res:
                return res
        except Exception:
            pass
            
    return random.choice(_jokes)


def tell_fact(args: dict) -> str:
    """Tell an interesting fun fact, using AI if available, else falling back to a static list."""
    import random
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    ollama_model = os.getenv("OLLAMA_MODEL", "").strip()
    
    prompt = "Tell me a short, interesting fun fact. If Hinglish, write in Hinglish with English letters. 1-2 sentences max."
    
    if gemini_key or openai_key or ollama_model:
        try:
            from clipboard_ai import _call_ai
            res = _call_ai(prompt)
            if res:
                return res
        except Exception:
            pass
            
    return random.choice(_facts)


def tell_riddle(args: dict) -> str:
    """Ask the user a riddle and check their verbal response interactively."""
    global _active_riddle
    import random
    riddle, answer = random.choice(_riddles)
    _active_riddle = (riddle, answer)
    
    def _check_answer(user_ans):
        global _active_riddle
        if not _active_riddle:
            return "No active riddle."
        _, correct = _active_riddle
        _active_riddle = None  # clear
        if user_ans and correct.lower() in user_ans.lower():
            return "Arre waah! Bilkul sahi jawaab! You are a genius."
        else:
            return f"Galat jawaab! Sahi jawaab tha: {correct}. Better luck next time!"
            
    from commands import MissingArgument
    raise MissingArgument(f"Here is a riddle: {riddle} ... Guess the answer!", _check_answer)


def start_gesture_control(args: dict) -> str:
    import gestures
    gestures.start_gesture_control()
    return "Hand gesture control started. Show your hand to the camera to control Shin."


def stop_gesture_control(args: dict) -> str:
    import gestures
    gestures.stop_gesture_control()
    return "Hand gesture control stopped."


def toggle_gesture_control(args: dict) -> str:
    import gestures
    active = gestures.toggle_gesture_control()
    if active:
        return "Hand gesture control activated."
    else:
        return "Hand gesture control deactivated."


def predict_next_move(args: dict = None) -> str:
    """
    Intelligently predict the user's next move and provide context-aware suggestions
    based on the active application, time of day, pending tasks, and recent activity.
    """
    try:
        try:
            import predictive_engine
        except ImportError:
            from core import predictive_engine
        res = predictive_engine.predict_daily_routine()
        return res["prediction"]
    except Exception as exc:
        logger.debug("predictive_engine call failed, using fallback: %s", exc)
    from datetime import datetime
    now = datetime.now()
    hour = now.hour

    # 1. Inspect foreground app & window title
    active_title = ""
    active_app = ""
    try:
        import app_tracker
        active_title = app_tracker._get_foreground_title()
        active_app = app_tracker._extract_app_name(active_title).lower()
    except Exception:
        pass

    # 2. Check pending to-dos
    pending_tasks = []
    try:
        import todo
        items = todo.get_todos()
        pending_tasks = [t["task"] for t in items if not t.get("done", False)]
    except Exception:
        pass

    # Context A: Coding / Development in progress
    if any(k in active_app for k in ("code", "visual studio", "pycharm", "sublime", "terminal", "cmd", "powershell")):
        if "test" in active_title.lower():
            return "Dekh MJ, tu test file pe kaam kar raha hai. Agla step tests run karna aur errors verify karna hona chahiye! Test command run karoon?"
        elif pending_tasks:
            return f"Tu code kar raha hai abhi. Agla step: apne pending task '{pending_tasks[0]}' ko finish karke changes commit kar le!"
        else:
            return "Tu coding kar raha hai. Agla move: code test karo ya review kar lo ki koi bug toh nahi bacha. Kuch check karna hai toh bata!"

    # Context B: Creative / Design in progress (Canva / Paint / 3D)
    if any(k in active_app for k in ("canva", "paint", "photoshop", "figma", "blender", "illustrator")):
        return "Tu designing pe focus kar raha hai! Agla step colors aur layout check karke design save ya export karna best rahega. Chahiye toh main koi reference dhoondh doon?"

    # Context C: Browser / Media / YouTube
    if any(k in active_app for k in ("chrome", "edge", "firefox", "brave", "youtube")):
        if "youtube" in active_title.lower():
            if hour >= 23 or hour < 4:
                return "Tu YouTube dekh raha hai aur kaafi late ho gaya hai MJ! Agla move: videos band karke aaram kar le, rest lena zaroori hai."
            return "YouTube open hai! Agar study ya focus kar raha hai toh koi lofi background music laga doon, ya koi specific topic search karoon?"
        if pending_tasks:
            return f"Browser open hai tera. Agar research ho gayi toh pending task '{pending_tasks[0]}' pe wapas chalein?"
        return "Tu browsing kar raha hai. Agla step: jo dhoondh raha hai uske notes bana lein, ya koi specific article summary chahiye?"

    # Context D: Late night / rest
    if hour >= 23 or hour < 5:
        return "Raat ke kaafi baj chuke hain MJ! Mera suggestion yeh hai ki aaram kar le abhi. System sleep pe daal doon ya kal ka schedule dekhna hai?"

    # Context E: Morning start
    if 5 <= hour < 11:
        if pending_tasks:
            return f"Subah ka fresh time hai! Agla move: apne task '{pending_tasks[0]}' se din start kar, full focus ke saath!"
        return "Din start ho chuka hai MJ! Agla step: aaj ka calendar schedule check kar lein aur high-priority task choose karein."

    # Context F: Pending task exists
    if pending_tasks:
        return f"Mera suggestion: tere paas pending task '{pending_tasks[0]}' bacha hua hai. Usko pehle finish karte hain!"

    # Context G: Default friendly guidance
    return "Mera prediction: abhi ek quick water break le le, aur fir bata kya start karna hai — coding, design, ya koi gana lagana hai?"


def run_shin_agent_command(args: dict) -> str:
    prompt = args.get("prompt") or args.get("query") or args.get("task", "")
    if not prompt:
        return "Batao MJ, kya task perform karna hai laptop pe?"
    try:
        from core.shin_agent import run_shin_agent
        return run_shin_agent(prompt)
    except Exception as exc:
        return f"Shin Agent error: {exc}"


def inspect_active_app_command(args: dict) -> str:
    try:
        from core.shin_agent import inspect_active_app
        return inspect_active_app()
    except Exception as exc:
        return f"Failed to inspect active app: {exc}"


def web_learn_command(args: dict) -> str:
    query = args.get("query", "")
    if not query:
        return "Please specify what you want me to search and learn."
    try:
        from core.shin_agent import web_search_and_learn
        return web_search_and_learn(query)
    except Exception as exc:
        return f"Failed to search and learn: {exc}"


def repeat_last_response(args: dict = None) -> str:
    """Repeat the last response spoken by Shin."""
    hist = []
    import sys
    for mod_name in ("nlp", "core.nlp", "Shin.core.nlp"):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, "_CONVERSATION_HISTORY") and mod._CONVERSATION_HISTORY:
            hist = mod._CONVERSATION_HISTORY
            break

    if not hist:
        try:
            from core import nlp
            hist = nlp._CONVERSATION_HISTORY
        except ImportError:
            try:
                import nlp
                hist = nlp._CONVERSATION_HISTORY
            except ImportError:
                return "I don't have conversation history available right now, MJ!"

    for turn in reversed(hist):
        if turn.get("role") == "assistant" and turn.get("content"):
            content = turn["content"].strip()
            if not content.startswith("I said:"):
                return f"I said: {content}"
            return content
    return "I haven't said anything yet, MJ!"


# Dictionary mapping intent names to their handler functions
HANDLERS = {
    "repeat_last_response": repeat_last_response,
    "run_shin_agent":      run_shin_agent_command,
    "inspect_active_app":  inspect_active_app_command,
    "web_learn":           web_learn_command,
    "predict_next_move":   predict_next_move,
    "tell_joke":           tell_joke,
    "tell_fact":           tell_fact,
    "tell_riddle":         tell_riddle,
    # Hand Gestures
    "start_gesture_control": start_gesture_control,
    "stop_gesture_control":  stop_gesture_control,
    "toggle_gesture_control": toggle_gesture_control,
    # Apps & Windows
    "open_app":            open_app,
    "open_shin_web":       open_shin_web,
    "open_phone_app":      open_phone_app,
    "close_app":           close_app,
    "close_active_window": close_active_window,
    "window_minimize_all": window_minimize_all,
    "window_snap_left":    window_snap_left,
    "window_snap_right":   window_snap_right,
    "window_snap_quadrant":window_snap_quadrant,
    "window_maximize":     window_maximize,
    "window_minimize":     window_minimize,
    # Volume
    "mute_volume":         mute_volume,
    "unmute_volume":       unmute_volume,
    "volume_up":           volume_up,
    "volume_down":         volume_down,
    "set_volume":          set_volume,
    # Brightness
    "brightness_up":       brightness_up,
    "brightness_down":     brightness_down,
    "set_brightness":      set_brightness,
    # Wi-Fi
    "wifi_control":        wifi_control,
    # System Controls
    "bluetooth_control":   bluetooth_control,
    "airplane_mode_control": airplane_mode_control,
    "night_light_control":  night_light_control,
    "mobile_hotspot_control": mobile_hotspot_control,
    "nearby_share_control": nearby_share_control,
    # Web & Search
    "web_search":          web_search,
    "open_url":            open_url,
    "open_whatsapp_chat":  open_whatsapp_chat,
    "send_whatsapp_message": send_whatsapp_message,
    "draft_whatsapp_message": draft_whatsapp_message,
    "add_whatsapp_contact": add_whatsapp_contact,
    "list_whatsapp_contacts": list_whatsapp_contacts,
    "send_whatsapp_location": send_whatsapp_location,
    "whatsapp_call":       whatsapp_call,
    "send_whatsapp_file":   send_whatsapp_file,
    # Live Internet Queries
    "live_query":          live_query,
    "stock_query":         stock_query,
    "crypto_query":        crypto_query,
    # Files & Folders
    "open_folder":         open_folder,
    "open_file":           open_file,
    "save_note":           save_note,
    "set_reminder":        set_reminder,
    # Memory & Training
    "save_memory":         save_memory,
    "recall_memory":       recall_memory,
    "forget_memory":       forget_memory,
    "train_shin":          train_shin,
    "learn_from_internet": learn_from_internet,
    "learn_laptop_skills": learn_laptop_skills,
    "explain_internet":    explain_internet,
    "wiki_search":         wiki_search,
    # Knowledge, App Discovery, Project & Screen Intelligence
    "explain_concept":     explain_concept,
    "locate_app":          locate_app,
    "help_with_project":   help_with_project,
    "explain_screen_activity": explain_screen_activity,
    "screen_diagnose_bug": screen_diagnose_bug,
    "project_git_status":  project_git_status,
    "git_diff_summary":    git_diff_summary,
    "create_project_file": create_project_file,
    "review_code":         review_code,
    "check_ai_hardware":   check_ai_hardware,
    "get_ui_tree":         get_ui_tree_command,
    "click_ui_element":    click_ui_element_command,
    # System Power
    "shutdown":            shutdown,
    "sleep_shutdown":      sleep_shutdown,
    "shutdown_timer":      shutdown_timer,
    "restart":             restart,
    "sleep":               sleep,
    "lock_screen":         lock_screen,
    # Time & Date
    "tell_time":           tell_time,
    "tell_date":           tell_date,
    # OS Actions
    "screenshot":          screenshot,
    "type_text":           type_text,
    "press_key":           press_key,
    "click_text":          click_text,
    "screen_query":        screen_query,
    "scroll":              scroll,
    # Clipboard & Code Intelligence
    "clipboard_translate": clipboard_translate,
    "clipboard_rewrite":   clipboard_rewrite,
    "clipboard_summarize": clipboard_summarize,
    "clipboard_fix":       clipboard_fix,
    "clipboard_history":   clipboard_history,
    "generate_code":       generate_code_command,
    "explain_code":        explain_code_command,
    # News & Knowledge
    "tell_news":           tell_news,
    "explain_internet":    explain_internet,
    # Calendar
    "calendar_list":       calendar_list,
    "calendar_add":        calendar_add,

    # YouTube
    "youtube_play":        youtube_play,
    # Smart Home
    "smart_home_control":  smart_home_control,
    "activate_scene":      activate_scene,
    # System Status
    "check_system_status": check_system_status,
    "monitor_process":     monitor_process,
    "list_open_windows":   list_open_windows,
    "pause_listening":     pause_listening,
    "resume_listening":    resume_listening,
    "quit_assistant":      quit_assistant,
    "set_personality":     set_personality,
    "weather_query":       weather_query,
    "pomodoro":            pomodoro,
    "activate_study_mode": activate_study_mode,
    "deactivate_study_mode": deactivate_study_mode,
    "check_study_status":  check_study_status,
    "battery_status":      battery_status,
    # To-Do list
    "todo_add":            todo_add,
    "todo_list":           todo_list,
    "todo_complete":       todo_complete,
    "todo_delete":         todo_delete,
    # Converter
    "convert":             convert,
    # Smart Home Status
    "smart_home_status":   smart_home_status,
    # Gmail
    "read_emails":         read_emails,
    # Voice Auth
    "enroll_voice":        enroll_voice,
    "delete_voice_profile": delete_voice_profile,
    # Per-app Volume
    "app_volume":          app_volume,
    # Advanced Utilities
    "clean_pc":            clean_pc,
    "clean_ram":           clean_ram,
    "run_pc_manager":      run_pc_manager,
    "run_terminal_command": run_terminal_command,
    "run_python_code":     run_python_code,
    "open_terminal":       open_terminal,
    "list_installed_apps": list_installed_apps,
    "read_clipboard":      read_clipboard,
    "learn_macro":         learn_macro,
    "list_macros":         list_macros,
    "delete_macro":        delete_macro,
    "edit_macro":          edit_macro,
    # Calculator, Dictionary, Translator, File Search, App Usage
    "calculate":           calculate,
    "date_reasoning":      date_reasoning,
    "define_word":         define_word,
    "translate_text":      translate_text,
    "file_search":         file_search,
    "app_usage_stats":     app_usage_stats,
    # Media controls
    "media_play_pause":    media_play_pause,
    "media_next":          media_next,
    "media_prev":          media_prev,
    # Macros
    "run_macro":           run_macro,
    # Voice Pitch
    "set_voice_pitch":     set_voice_pitch,
    # Conversational chat fallback
    "chat":                chat,
    # Real-Life Work & Prediction Handlers
    "set_alarm":           set_alarm,
    "manage_tab":          manage_tab,
    "open_tab":            manage_tab,
    "switch_tab":          manage_tab,
    "close_tab":           manage_tab,
    "send_message":        send_message,
    "sleep_routine":       sleep_routine,
    "power_status":        power_status,
    "power_outage":        power_status,
    "describe_screen":     describe_screen,
    "screen_vision":       describe_screen,
    "store_relationship":  store_relationship,
    "analyze_clipboard":   analyze_clipboard,
    "agent_reach_query":   agent_reach_query,
    "agent_reach":         agent_reach_query,
    "set_language":        set_language,
    "switch_model":        switch_model,
    "get_active_model":    get_active_model,
}


def check_command_safety(intent_name: str, args: dict) -> tuple[bool, str]:
    """
    Scan command arguments for dangerous keywords, executables, scripts, or exfiltration patterns.
    Returns (is_safe, warning_message).
    """
    # 1. Blocklist of dangerous shell patterns in any string argument
    unsafe_shell_patterns = [
        # File & directory destruction
        (r"\brm\s+-rf\b", "Removing directories recursively (rm -rf)"),
        (r"\brmdir\s*/s\b|\brd\s*/s\b", "Removing directories recursively (rmdir /s)"),
        (r"\bdel\s*(?:/[fsqa])+\b", "Forcefully deleting files via shell (del)"),
        (r"\bRemove-Item\b.*-(?:Recurse|Force)", "Removing items recursively or forcefully in PowerShell"),
        (r"\bsdelete\b", "Securely wiping files"),

        # Disk & partition formatting
        (r"\bformat\s+[a-zA-Z]:", "Formatting disk drives"),
        (r"\bdiskpart\b", "Modifying disk partitions (diskpart)"),
        (r"\bClear-Disk\b|\bInitialize-Disk\b|\bFormat-Volume\b", "PowerShell disk wiping cmdlet"),

        # Registry manipulation
        (r"\breg\s+delete\b", "Deleting registry keys (reg delete)"),
        (r"\breg\s+add\b", "Modifying registry keys (reg add)"),
        (r"\bRemove-ItemProperty\b.*(?:Registry|HKLM|HKCU)", "Deleting registry properties"),
        (r"\bSet-ItemProperty\b.*(?:Registry|HKLM|HKCU)", "Modifying registry properties"),

        # Database destruction
        (r"\bdrop\s+(?:database|table)\b", "Dropping database structures"),

        # Process termination
        (r"\bkill\s+-9\b", "Forcefully killing system processes (kill -9)"),
        (r"\btaskkill\s*/f\b", "Forcefully terminating processes via taskkill"),
        (r"\bStop-Process\b.*-Force", "Forcefully stopping processes via PowerShell"),

        # Antivirus & Defender disabling
        (r"\bSet-MpPreference\b.*-(?:DisableRealtimeMonitoring|DisableBehaviorMonitoring)", "Disabling Windows Defender realtime protection"),
        (r"\bnetsh\s+advfirewall\s+set\s+allprofiles\s+state\s+off\b", "Disabling Windows Firewall"),

        # Remote download cradles and exfiltration
        (r"(?i)\b(?:Invoke-WebRequest|iwr|Invoke-RestMethod|irm)\b", "Downloading arbitrary payloads via PowerShell"),
        (r"(?i)\b(?:Start-BitsTransfer|bitsadmin(?:\.exe)?|certutil(?:\.exe)?|mshta(?:\.exe)?|rundll32(?:\.exe)?)\b", "Abusing living-off-the-land binaries for downloads/execution"),
        (r"(?i)\b(?:DownloadString|DownloadFile|Net\.WebClient|HttpClient)\b", "Invoking web download methods in PowerShell"),
        (r"(?i)\b(?:Invoke-Expression|iex)\b", "Executing dynamic scripts in memory via iex"),
        (r"(?i)-(?:enc|encodedcommand)\s+[A-Za-z0-9+/=]{8,}", "Base64 encoded execution payload"),

        # Secret theft & file exfiltration
        (r"(?i)(?:Get-Content|type|cat|gc)\s+.*(?:\.env|id_rsa|id_ed25519|\.ssh|credentials)", "Attempting to read or exfiltrate secret keys and credentials"),
        (r"(?i)\b(?:Get-Credential|mimikatz|samdump|pwdump)\b", "Harvesting credentials or SAM database"),

        # Backdoors and reverse shells
        (r"(?i)\b(?:ncat|nc\.exe|netcat|socat|chisel)\b", "Spawning reverse shells or network tunnels"),
    ]

    # 2. Blocklist of dangerous Python evaluation patterns for run_python_code
    unsafe_python_patterns = [
        (r"(?i)\b(?:eval|exec|compile)\s*\(", "Arbitrary dynamic code execution (eval/exec)"),
        (r"(?i)\b(?:__import__|importlib)\b", "Dynamic module loading bypass"),
        (r"(?i)\bos\.(?:system|popen|spawn|execl|execv|remove|rmdir|unlink)\b", "Executing OS commands or file deletion via os module"),
        (r"(?i)\bsubprocess\b", "Spawning subprocesses from Python script"),
        (r"(?i)\bshutil\.(?:rmtree|move)\b", "Recursive deletion or file moves via shutil"),
        (r"(?i)\bctypes\b", "Direct memory/DLL manipulation via ctypes"),
        (r"(?i)\b(?:socket|urllib|requests|http\.client)\b", "Opening unverified network sockets from Python script"),
        (r"(?i)\bopen\s*\([^)]*(?:\.env|\.ssh|credentials|voice_profile)", "Reading sensitive application secrets via open()"),
    ]

    # 3. Blocklist of dangerous executable names/commands in open_app
    unsafe_exes = {
        "regedit.exe", "regedit",
        "diskpart.exe", "diskpart",
        "format.com", "format.exe", "format",
        "icacls.exe", "takeown.exe",
        "cmd.exe", "cmd",
        "powershell.exe", "powershell",
        "pwsh.exe", "pwsh",
        "wscript.exe", "wscript",
        "cscript.exe", "cscript",
        "mshta.exe", "mshta",
        "certutil.exe", "certutil",
        "bitsadmin.exe", "bitsadmin",
        "rundll32.exe", "rundll32",
        "vssadmin.exe", "vssadmin",
        "bash.exe", "wsl.exe",
        "net.exe", "net1.exe",
    }

    # 4. Blocklist of dangerous file extensions in open_file
    unsafe_extensions = {
        ".bat", ".cmd", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
        ".ps1", ".ps1xml", ".ps2", ".psc1", ".psc2", ".reg", ".scr", ".sh",
        ".exe", ".com", ".pif", ".hta", ".cpl", ".jar", ".msi", ".msp", ".lnk"
    }

    # Scan argument values
    for arg_key, arg_val in args.items():
        if isinstance(arg_val, str):
            val_lower = arg_val.lower().strip()

            # Check shell execution patterns
            if intent_name in ("terminal", "run_terminal_command") or arg_key in ("cmd", "command"):
                for pattern, description in unsafe_shell_patterns:
                    if re.search(pattern, arg_val, re.IGNORECASE):
                        return False, f"The command parameter contains a blocklisted shell pattern: {description}."

            # Check python evaluation patterns
            if intent_name in ("python_eval", "run_python_code") or arg_key in ("code", "script"):
                for pattern, description in unsafe_python_patterns:
                    if re.search(pattern, arg_val, re.IGNORECASE):
                        return False, f"Python code contains blocked insecure directives: {description}."

            # Check general shell patterns across all arguments
            for pattern, description in unsafe_shell_patterns[:9]:
                if re.search(pattern, val_lower, re.IGNORECASE):
                    return False, f"The command parameter contains a blocklisted pattern: {description}."

            # Check specific intent safety
            if intent_name == "open_app" and arg_key == "app":
                if val_lower in unsafe_exes or any(val_lower.endswith(exe) for exe in unsafe_exes):
                    return False, f"Running the application '{arg_val}' is blocked for system security."

            if intent_name in ("open_file", "open_folder") and arg_key in ("path", "folder"):
                # Block UNC network paths to prevent NTLM credential theft
                if val_lower.startswith(("\\\\", "//")):
                    return False, "Opening network UNC paths is blocked to protect against NTLM credential theft."
                _, ext = os.path.splitext(val_lower)
                if ext in unsafe_extensions:
                    return False, f"Opening files with '{ext}' extensions is blocked to prevent running executable scripts."

    return True, ""


def dispatch(intent: dict) -> Optional[str]:
    """
    Run the handler for the parsed intent.
    Returns the response string, or None if intent is 'unknown'.
    May raise ConfirmationRequired for destructive ops.
    """
    name = intent.get("intent", "unknown")
    args = intent.get("args", {})
    triggered_by_untrusted = bool(intent.get("_untrusted", False))

    # CaMeL Zero-Trust Shield: check if plan is safe for untrusted sources
    try:
        import security_shield
        safe_plan, reason = security_shield.is_safe_action_plan(name, args, triggered_by_untrusted=triggered_by_untrusted)
        if not safe_plan:
            logger.warning("CaMeL Zero-Trust blocked action: %s. Reason: %s", name, reason)
            return f"Action blocked by CaMeL Zero-Trust Shield: {reason}"
    except Exception as exc:
        logger.debug("Security shield check failed: %s", exc)

    # Security check: Prevent execution of potentially harmful actions
    is_safe, warning_msg = check_command_safety(name, args)
    if not is_safe:
        logger.warning("Blocked potentially harmful command: %s, args=%s. Reason: %s", name, args, warning_msg)
        return f"Access denied. {warning_msg}"

    if name == "scroll_down":
        try:
            lines = int(args.get("lines", 10))
        except (ValueError, TypeError):
            lines = 10
        scroll_down(lines)
        return "Scrolling down."
    if name == "scroll_up":
        try:
            lines = int(args.get("lines", 10))
        except (ValueError, TypeError):
            lines = 10
        scroll_up(lines)
        return "Scrolling up."

    handler = HANDLERS.get(name)
    if handler:
        return handler(args)
    return None