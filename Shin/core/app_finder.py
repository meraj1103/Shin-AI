"""
app_finder.py — Deep Windows Application Discovery & Launcher for Shin
========================================================================
Discovers all installed desktop applications, Windows Store (UWP) apps,
and system utilities on the laptop using Start Menu scanning, Registry App Paths,
and PowerShell Get-StartApps.

Provides fuzzy matching so MJ can say "open PC manager", "open blender",
"open discord", "open terminal", etc., and Shin will locate and launch it instantly.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
import subprocess
import time
import winreg
from pathlib import Path
from typing import Optional

logger = logging.getLogger("shin.app_finder")

_CACHE_FILE = Path(__file__).parent.parent / "data" / "installed_apps_cache.json"
_CACHE_TTL_HOURS = 24  # rescan every 24 hours or on demand

# In-memory dictionary of {normalized_name: launch_target}
_APPS_CACHE: dict[str, str] = {}
_LAST_SCAN_TIME: float = 0.0

# Built-in essential Windows aliases & protocol URIs
_BUILTIN_MAP: dict[str, str] = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "vs code": "code.exe",
    "visual studio code": "code.exe",
    "vscode": "code.exe",
    "settings": "ms-settings:",
    "control panel": "control.exe",
    "whatsapp": "whatsapp:",
    "clock": "ms-clock:",
    "camera": "microsoft.windows.camera:",
    "paint": "mspaint.exe",
    "blender": "blender.exe",
    "pc manager": "ms-pcmanager:",
    "microsoft pc manager": "ms-pcmanager:",
    "pc cleaner": "ms-pcmanager:",
    "ram cleaner": "ms-pcmanager:",
}


def _normalize(name: str) -> str:
    """Normalize string for fuzzy comparison."""
    import re
    clean = re.sub(r'[\(\)\[\]\-_\.]+', ' ', name.lower())
    clean = re.sub(r'\b(app|application|desktop|version|edition|x64|x86|64 bit|32 bit)\b', '', clean)
    return " ".join(clean.split())


def _scan_start_menu() -> dict[str, str]:
    """Scan Start Menu folders for all shortcut (.lnk) files."""
    apps = {}
    search_dirs = [
        Path(os.environ.get("ProgramData", r"C:\ProgramData")) / r"Microsoft\Windows\Start Menu\Programs",
        Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs",
    ]

    for base_dir in search_dirs:
        if not base_dir.exists():
            continue
        try:
            for root, _, files in os.walk(base_dir):
                for f in files:
                    if f.lower().endswith(".lnk"):
                        full_path = os.path.join(root, f)
                        name_stem = Path(f).stem
                        norm = _normalize(name_stem)
                        if norm and norm not in apps:
                            apps[norm] = full_path
        except Exception as e:
            logger.debug("Start menu scan failed for %s: %s", base_dir, e)

    return apps


def _scan_registry_app_paths() -> dict[str, str]:
    """Scan HKLM & HKCU App Paths for registered executables."""
    apps = {}
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
    ]

    for hive, subkey in keys:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                num_subkeys = winreg.QueryInfoKey(key)[0]
                for i in range(num_subkeys):
                    try:
                        app_key_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, app_key_name) as app_key:
                            exe_path, _ = winreg.QueryValueEx(app_key, "")
                            if exe_path and os.path.exists(exe_path):
                                stem = Path(app_key_name).stem
                                norm = _normalize(stem)
                                if norm and norm not in apps:
                                    apps[norm] = exe_path
                    except Exception:
                        continue
        except Exception:
            continue

    return apps


def _scan_uwp_apps() -> dict[str, str]:
    """Scan modern Windows Store / UWP apps using PowerShell Get-StartApps."""
    apps = {}
    try:
        ps_cmd = 'Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress'
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=8
        )
        if proc.returncode == 0 and proc.stdout.strip():
            raw = json.loads(proc.stdout.strip())
            items = raw if isinstance(raw, list) else [raw]
            for item in items:
                name = item.get("Name", "")
                appid = item.get("AppID", "")
                if name and appid:
                    norm = _normalize(name)
                    # UWP apps are launched via shell:AppsFolder\<AppID>
                    if norm and norm not in apps:
                        apps[norm] = f"shell:AppsFolder\\{appid}"
    except Exception as exc:
        logger.debug("UWP app scan failed: %s", exc)

    return apps


def scan_all_installed_apps(force: bool = False) -> dict[str, str]:
    """Scan and cache all installed apps from all sources."""
    global _APPS_CACHE, _LAST_SCAN_TIME

    now = time.time()
    if not force and _APPS_CACHE and (now - _LAST_SCAN_TIME) < (_CACHE_TTL_HOURS * 3600):
        return _APPS_CACHE

    # Try loading disk cache if fresh
    if not force and _CACHE_FILE.exists():
        try:
            mtime = _CACHE_FILE.stat().st_mtime
            if (now - mtime) < (_CACHE_TTL_HOURS * 3600):
                with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                    _APPS_CACHE = json.load(f)
                    _LAST_SCAN_TIME = now
                    logger.info("Loaded %d installed apps from cache.", len(_APPS_CACHE))
                    return _APPS_CACHE
        except Exception:
            pass

    logger.info("Scanning laptop for all installed applications...")
    combined = dict(_BUILTIN_MAP)
    combined.update(_scan_registry_app_paths())
    combined.update(_scan_start_menu())
    combined.update(_scan_uwp_apps())

    _APPS_CACHE = combined
    _LAST_SCAN_TIME = now

    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_APPS_CACHE, f, indent=2, ensure_ascii=False)
        logger.info("Indexed and cached %d installed apps.", len(_APPS_CACHE))
    except Exception as e:
        logger.warning("Failed to save app cache: %s", e)

    return _APPS_CACHE


def find_app(query: str) -> Optional[tuple[str, str]]:
    """
    Find best matching app for `query`.
    Returns (matched_app_name, launch_target) or None.
    """
    if not query:
        return None

    clean_q = _normalize(query)
    apps = scan_all_installed_apps()

    # 1. Exact match
    if clean_q in apps:
        return (clean_q, apps[clean_q])

    # 2. Strict prefix and word-boundary matching
    # Sort apps by length descending so specific matches win over short substrings
    sorted_apps = sorted(apps.items(), key=lambda kv: len(kv[0]), reverse=True)

    # 2a. App name starts with query or query starts with app name
    for app_name, target in sorted_apps:
        if app_name.startswith(clean_q) or clean_q.startswith(app_name):
            return (app_name, target)

    # 2b. Query is a whole word inside app name (e.g. query='chrome' inside 'google chrome')
    pattern_q = r'\b' + re.escape(clean_q) + r'\b'
    for app_name, target in sorted_apps:
        if re.search(pattern_q, app_name):
            return (app_name, target)

    # 2c. App name is a whole word inside query (e.g. app='unity hub' inside query='open unity hub please')
    # Must be at least 3 characters and match with word boundaries to avoid false positives (e.g. 'hub' in 'github')
    for app_name, target in sorted_apps:
        if len(app_name) >= 3:
            pattern_app = r'\b' + re.escape(app_name) + r'\b'
            if re.search(pattern_app, clean_q):
                return (app_name, target)

    # 3. Fuzzy matching with difflib (high precision to avoid false matches like github -> unity hub)
    matches = difflib.get_close_matches(clean_q, apps.keys(), n=1, cutoff=0.75)
    if matches:
        best = matches[0]
        return (best, apps[best])

    return None


def launch_application(query: str) -> tuple[bool, str]:
    """
    Locate and launch an application by name.
    Returns (success: bool, spoken_message: str).
    """
    match = find_app(query)
    if not match:
        return False, f"Mujhe '{query}' app nahi mili laptop mein. Check karo ki installed hai ya nahi."

    app_name, target = match

    try:
        # Protocol or UWP AppFolder URI
        if target.startswith("shell:") or ":" in target and not Path(target).is_absolute():
            os.startfile(target)
            return True, f"Maine '{app_name.title()}' launch kar diya!"

        # Shortcut (.lnk)
        if target.lower().endswith(".lnk"):
            os.startfile(target)
            return True, f"Maine '{app_name.title()}' open kar diya!"

        # Absolute executable path
        if os.path.exists(target):
            subprocess.Popen([target], shell=False)
            return True, f"Maine '{app_name.title()}' start kar diya!"

        # Fallback to system start
        os.startfile(target)
        return True, f"Maine '{app_name.title()}' open kar diya!"
    except Exception as exc:
        logger.error("Failed to launch %s (%s): %s", app_name, target, exc)
        return False, f"'{app_name}' open karne mein error aaya: {exc}"


def resolve_shortcut(lnk_path: str) -> str:
    """Resolve a .lnk Windows shortcut to its actual target executable path."""
    if not lnk_path.lower().endswith(".lnk") or not os.path.exists(lnk_path):
        return lnk_path
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(lnk_path)
        target = shortcut.TargetPath
        if target and os.path.exists(target):
            return target
    except Exception:
        pass
    return lnk_path


def reveal_in_explorer(target_path: str) -> bool:
    """Open Windows File Explorer with the specific file or shortcut highlighted."""
    try:
        actual_path = resolve_shortcut(target_path) if target_path.lower().endswith(".lnk") else target_path
        if os.path.exists(actual_path):
            subprocess.Popen(f'explorer.exe /select,"{actual_path}"')
            return True
        elif os.path.exists(target_path):
            subprocess.Popen(f'explorer.exe /select,"{target_path}"')
            return True
    except Exception as exc:
        logger.error("Failed to reveal %s in explorer: %s", target_path, exc)
    return False


def locate_app_path(query: str) -> tuple[bool, str, str]:
    """
    Locate where an application is installed on disk.
    Returns (found: bool, app_name: str, resolved_path: str).
    """
    match = find_app(query)
    if not match:
        return False, query, "App is not indexed on this laptop."

    app_name, target = match
    resolved = resolve_shortcut(target) if target.lower().endswith(".lnk") else target
    return True, app_name, resolved


def explain_where_app_is(query: str, reveal: bool = True) -> str:
    """
    Explain where an app is located and optionally reveal its executable in File Explorer.
    """
    found, name, path = locate_app_path(query)
    if not found:
        return f"Mujhe '{query}' app ki installation location nahi mili laptop pe."

    folder = os.path.dirname(path) if os.path.exists(path) else path
    if reveal and os.path.exists(path):
        reveal_in_explorer(path)
        return f"'{name.title()}' yahan installed hai: {folder}. Maine File Explorer mein show kar diya hai!"
    return f"'{name.title()}' is installed at: {folder}."


def list_installed_apps_summary(limit: int = 15) -> str:
    """Return a spoken-friendly summary of major installed apps on the laptop."""
    apps = scan_all_installed_apps()
    notable = [
        name.title() for name in apps.keys()
        if len(name) > 2 and not any(k in name for k in ("unins", "setup", "helper", "update", "crash", "host", "service"))
    ]
    sample = sorted(notable)[:limit]
    total = len(notable)
    return f"Tere laptop mein total {total} apps indexed hain. Jaise ki {', '.join(sample[:8])}, aur bhi bahut kuch!"
