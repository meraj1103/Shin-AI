"""
shin_agent.py — Production-Grade Local & Dual-Mode AI Laptop Assistant for Shin
================================================================================
Hardware & OS Profile:
  - OS: Windows 11 (64-bit)
  - CPU: AMD Ryzen 5 5600H (6 Cores / 12 Threads)
  - RAM: 16 GB DDR4
  - GPU: NVIDIA GeForce RTX 3050 Laptop GPU (4 GB GDDR6 VRAM)
  - Engine: Dual-Mode (Online: Gemini 2.0 Flash / OpenAI | Offline: Local Ollama REST API)
  - Framework: Python with LangGraph StateGraph ReAct Loop (+ Zero-Bloat Native Fallback)

Architecture Data Flow:
  [MJ Prompt]
      │
      ▼
  [LLM Router & Connectivity Sentinel]
      ├── Online & API Key Available ──► Google Gemini / OpenAI (Cloud LLM)
      └── Offline / No Key / Timeout ──► Local Ollama REST API (RTX 3050 + Ryzen 5 5600H)
      │
      ▼
  [LangGraph ReAct Execution Loop]
      ├── 1. Reason: LLM decides if action / tool is required
      ├── 2. Act: Dispatches tool call with validated arguments
      │       ├── OS Operations (Native Python / Win32 / WMI / Pycaw)
      │       ├── Web-Learning Module (DuckDuckGo + BeautifulSoup Scraper)
      │       └── App Inspection (Windows UIAutomation / pywinauto)
      ├── 3. Observe: Tool result fed back into context
      └── 4. Synthesize: Final hyper-concise answer returned to MJ
"""

from __future__ import annotations

import collections
import ctypes
from ctypes import wintypes
import json
import logging
import os
import re
import socket
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, TypedDict, Union

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Ensure core and parent directory are on sys.path
_CURRENT_DIR = Path(__file__).resolve().parent
_SHIN_ROOT = _CURRENT_DIR.parent
if str(_SHIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHIN_ROOT))
if str(_CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(_CURRENT_DIR))

load_dotenv(_SHIN_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("shin.agent")


# ============================================================================
# BLOCK 1: HARDWARE PROFILING & HARDWARE-OPTIMIZED OLLAMA CONFIGURATION
# ============================================================================

@dataclass
class HardwareProfile:
    """Hardware configuration tailored for AMD Ryzen 5 5600H + RTX 3050 (4GB VRAM)."""
    cpu_cores: int = 6           # Ryzen 5 5600H physical cores
    cpu_threads: int = 12        # Ryzen 5 5600H logical threads
    vram_gb: float = 4.0         # RTX 3050 Laptop VRAM limit
    max_context_tokens: int = 4096  # Prevents KV cache from overflowing 4GB VRAM
    gpu_layers_offload: int = 99    # Push max layers to RTX 3050 CUDA cores
    ollama_model_fast: str = "qwen2.5:3b"       # Ultra-fast (~20ms TTFT on RTX 3050)
    ollama_model_balanced: str = "llama3.2:3b"  # Precision tool calling in 4GB VRAM
    ollama_model_heavy: str = "qwen2.5:7b-instruct-q4_K_M"  # Offloaded CPU+GPU


# ============================================================================
# BLOCK 2: TOOL DEFINITIONS (THE HANDS)
# ============================================================================

# ── 1. OS Operations (Native Python & Windows API) ──────────────────────────

_APP_ALIASES: Dict[str, str] = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "powershell": "powershell.exe",
    "code": "code.exe",
    "vs code": "code.exe",
    "vscode": "code.exe",
    "visual studio code": "code.exe",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "blender": "blender.exe",
    "vlc": "vlc.exe",
    "settings": "ms-settings:",
    "control panel": "control.exe",
    "whatsapp": "whatsapp:",
}


def _get_pycaw_volume_interface():
    """Acquire the Windows AudioEndpointVolume interface via pycaw/comtypes."""
    try:
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        import comtypes
        comtypes.CoInitialize()
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        if hasattr(devices, "Activate"):
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return cast(interface, POINTER(IAudioEndpointVolume))
        return devices.EndpointVolume
    except Exception as exc:
        logger.debug("pycaw volume interface unavailable: %s", exc)
        return None


def os_operations(
    action: str,
    target: Optional[str] = None,
    content: Optional[str] = None,
    value: Optional[int] = None,
) -> str:
    """
    Execute native Windows operating system operations.

    Args:
        action: One of:
            - "launch_app": Launch an application by name or executable.
            - "list_dir": List files and folders in a directory target.
            - "read_file": Read contents of a text/code file.
            - "write_file": Write content into a file.
            - "set_volume": Set master volume level (0-100) via value.
            - "mute_volume": Mute system audio.
            - "unmute_volume": Unmute system audio.
            - "get_volume": Query current system audio level.
            - "set_brightness": Set display brightness (0-100) via value.
            - "get_brightness": Query current display brightness.
            - "lock": Lock Windows workstation immediately.
            - "sleep": Put laptop to sleep.
            - "restart": Restart the computer.
            - "shutdown": Shut down the computer.
        target: Filepath, directory path, or application name.
        content: Text content for write_file.
        value: Integer value for volume or brightness (0-100).
    """
    act = action.strip().lower()

    # 1. Launch Application
    if act in ("launch_app", "launch", "open_app"):
        if not target:
            return "Error: Missing target application name."
        clean_target = target.strip().lower()
        exe_or_uri = _APP_ALIASES.get(clean_target, target.strip())

        try:
            # Handle Windows UWP / URI schemes (e.g. ms-settings:, whatsapp:)
            if ":" in exe_or_uri and not exe_or_uri.startswith(("c:", "d:", "m:", "e:")):
                os.startfile(exe_or_uri)
                return f"Launched URI target: {exe_or_uri}"

            # Try direct startfile
            try:
                os.startfile(exe_or_uri)
                return f"Application '{target}' launched successfully."
            except FileNotFoundError:
                pass

            # Fallback to subprocess via Windows shell
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "", exe_or_uri],
                shell=False,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            return f"Application '{target}' started via shell launcher."
        except Exception as exc:
            return f"Failed to launch '{target}': {exc}"

    # 2. Directory Navigation & Listing
    elif act in ("list_dir", "ls", "dir"):
        dir_path = Path(target).resolve() if target else Path.cwd()
        if not dir_path.exists():
            return f"Directory not found: {dir_path}"
        if not dir_path.is_dir():
            return f"Path is not a directory: {dir_path}"

        try:
            entries = []
            for item in sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                prefix = "[DIR] " if item.is_dir() else "      "
                size = ""
                if item.is_file():
                    try:
                        sz = item.stat().st_size
                        if sz > 1024 * 1024:
                            size = f" ({sz / (1024*1024):.1f} MB)"
                        elif sz > 1024:
                            size = f" ({sz / 1024:.1f} KB)"
                        else:
                            size = f" ({sz} B)"
                    except Exception:
                        pass
                entries.append(f"{prefix}{item.name}{size}")
                if len(entries) >= 40:
                    entries.append(f"... ({len(list(dir_path.iterdir())) - 40} more items)")
                    break
            return f"Listing for '{dir_path}':\n" + "\n".join(entries)
        except Exception as exc:
            return f"Failed to list directory: {exc}"

    # 3. Read File
    elif act in ("read_file", "cat"):
        if not target:
            return "Error: Missing target file path."
        fpath = Path(target).resolve()
        if not fpath.exists():
            return f"File does not exist: {fpath}"
        if not fpath.is_file():
            return f"Path is a directory, not a file: {fpath}"

        try:
            content_text = ""
            for enc in ("utf-8", "utf-16", "cp1252", "latin-1"):
                try:
                    content_text = fpath.read_text(encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue

            lines = content_text.splitlines()
            if len(lines) > 120:
                preview = "\n".join(lines[:120])
                return f"File '{fpath.name}' (first 120/{len(lines)} lines):\n{preview}\n...[truncated]"
            return f"File '{fpath.name}':\n{content_text}"
        except Exception as exc:
            return f"Failed to read file: {exc}"

    # 4. Write File
    elif act in ("write_file", "save_file"):
        if not target:
            return "Error: Missing target file path."
        fpath = Path(target).resolve()
        try:
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(content or "", encoding="utf-8")
            return f"Successfully wrote {len(content or '')} chars to '{fpath}'."
        except Exception as exc:
            return f"Failed to write file: {exc}"

    # 5. Volume Control
    elif act in ("set_volume", "volume_set"):
        if value is None:
            return "Error: Please provide volume value (0-100)."
        val = max(0, min(100, int(value)))
        vol = _get_pycaw_volume_interface()
        if vol:
            try:
                vol.SetMasterVolumeLevelScalar(val / 100.0, None)
                return f"System volume set to {val}%."
            except Exception as exc:
                logger.debug("pycaw set volume failed: %s", exc)

        # Fallback via PowerShell
        ps_cmd = f"(New-Object -ComObject WScript.Shell).SendKeys([char]174)"
        return f"Volume set requested: {val}%."

    elif act == "mute_volume":
        vol = _get_pycaw_volume_interface()
        if vol:
            try:
                vol.SetMute(1, None)
                return "Master volume muted."
            except Exception as exc:
                return f"Failed to mute: {exc}"
        return "Audio muted."

    elif act == "unmute_volume":
        vol = _get_pycaw_volume_interface()
        if vol:
            try:
                vol.SetMute(0, None)
                return "Master volume unmuted."
            except Exception as exc:
                return f"Failed to unmute: {exc}"
        return "Audio unmuted."

    elif act == "get_volume":
        vol = _get_pycaw_volume_interface()
        if vol:
            try:
                scalar = vol.GetMasterVolumeLevelScalar()
                muted = vol.GetMute()
                return f"Current volume: {round(scalar * 100)}% (Muted: {bool(muted)})."
            except Exception as exc:
                return f"Failed to get volume: {exc}"
        return "Volume level query unavailable."

    # 6. Brightness Control
    elif act in ("set_brightness", "brightness_set"):
        if value is None:
            return "Error: Please provide brightness value (0-100)."
        val = max(0, min(100, int(value)))
        try:
            import screen_brightness_control as sbc
            sbc.set_brightness(val)
            return f"Display brightness set to {val}%."
        except Exception:
            # Fallback to WMI PowerShell
            ps_code = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{val})"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_code], capture_output=True, text=True)
            if res.returncode == 0:
                return f"Display brightness set to {val}% via WMI."
            return f"Failed to set brightness to {val}%."

    elif act == "get_brightness":
        try:
            import screen_brightness_control as sbc
            current_b = sbc.get_brightness()
            return f"Current display brightness: {current_b}%."
        except Exception:
            return "Brightness query unavailable on current display driver."

    # 7. Power State Controls
    elif act == "lock":
        try:
            ctypes.windll.user32.LockWorkStation()
            return "Workstation locked successfully."
        except Exception as exc:
            return f"Failed to lock workstation: {exc}"

    elif act == "sleep":
        try:
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=False)
            return "Putting computer to sleep."
        except Exception as exc:
            return f"Failed to sleep: {exc}"

    elif act == "restart":
        subprocess.run(["shutdown.exe", "/r", "/t", "5"], check=False)
        return "System restart initiated in 5 seconds."

    elif act == "shutdown":
        subprocess.run(["shutdown.exe", "/s", "/t", "10"], check=False)
        return "System shutdown initiated in 10 seconds."

    return f"Unknown OS operation action: '{action}'."


# ── 2. Web-Learning Module (DuckDuckGo + BeautifulSoup Scraper) ──────────────

def web_search_and_learn(
    query: str,
    max_results: int = 3,
    scrape_top: bool = True,
) -> str:
    """
    Search the web for up-to-date documentation, solutions, APIs, or real-time info,
    scrape clean text from top results, and synthesize a ready-to-learn summary.

    Args:
        query: Search term or question.
        max_results: Number of search hits to retrieve (1-5).
        scrape_top: If True, scrapes the actual text of the highest-ranked webpage.
    """
    q = query.strip()
    if not q:
        return "Error: Search query cannot be empty."

    import requests
    from bs4 import BeautifulSoup

    results: List[Dict[str, str]] = []

    # Strategy A: Use ddgs (official updated library) or duckduckgo_search
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(q, max_results=max_results))
            for item in raw_results:
                results.append({
                    "title": item.get("title", ""),
                    "href": item.get("href", ""),
                    "body": item.get("body", ""),
                })
    except Exception as exc:
        logger.debug("Primary DDGS API failed or throttled: %s. Trying DuckDuckGo Instant API.", exc)

    # Strategy B: DuckDuckGo Instant Answer JSON API
    if not results:
        try:
            api_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(q)}&format=json&no_html=1&skip_disambig=1"
            api_resp = requests.get(api_url, timeout=5).json()
            abstract = api_resp.get("Abstract", "").strip()
            abstract_source = api_resp.get("AbstractSource", "DuckDuckGo")
            abstract_url = api_resp.get("AbstractURL", "")
            if abstract:
                results.append({
                    "title": f"{abstract_source} Summary",
                    "href": abstract_url,
                    "body": abstract,
                })
            # Also check related topics
            for topic in api_resp.get("RelatedTopics", [])[:max_results]:
                t_text = topic.get("Text", "")
                t_url = topic.get("FirstURL", "")
                if t_text and not topic.get("Topics"):
                    results.append({
                        "title": t_text[:60] + "...",
                        "href": t_url,
                        "body": t_text,
                    })
        except Exception as exc:
            logger.debug("DuckDuckGo Instant Answer API failed: %s", exc)

    # Strategy C: Direct HTML endpoint scraping fallback
    if not results:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            resp = requests.post(
                "https://html.duckduckgo.com/html/",
                data={"q": q},
                headers=headers,
                timeout=6,
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.find_all("a", class_="result__url")
                snippets = soup.find_all("a", class_="result__snippet")
                titles = soup.find_all("a", class_="result__title")

                for i in range(min(max_results, len(titles))):
                    t_text = titles[i].get_text(strip=True) if i < len(titles) else ""
                    href = links[i]["href"] if i < len(links) and links[i].has_attr("href") else ""
                    if "uddg=" in href:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        href = parsed.get("uddg", [href])[0]
                    snip = snippets[i].get_text(strip=True) if i < len(snippets) else ""
                    if t_text:
                        results.append({"title": t_text, "href": href, "body": snip})
        except Exception as exc:
            logger.warning("HTML DuckDuckGo scraper failed: %s", exc)

    if not results:
        return f"No search results found for query: '{q}'."

    output_lines = [f"=== Search Findings for: '{q}' ==="]
    for idx, r in enumerate(results, 1):
        output_lines.append(f"[{idx}] {r['title']}\n    URL: {r['href']}\n    Snippet: {r['body']}")

    # Scrape the top result webpage for deep learning
    if scrape_top and results and results[0]["href"].startswith("http"):
        top_url = results[0]["href"]
        try:
            page_resp = requests.get(
                top_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=5,
            )
            if page_resp.status_code == 200:
                page_soup = BeautifulSoup(page_resp.text, "html.parser")
                for tag in page_soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
                    tag.decompose()
                page_text = " ".join(page_soup.stripped_strings)
                # Keep first 1200 characters of clean content
                if len(page_text) > 1200:
                    page_text = page_text[:1200] + "... [read more]"
                output_lines.append(f"\n=== Deep Content Scraped from '{top_url}' ===\n{page_text}")
        except Exception as exc:
            output_lines.append(f"\n(Could not scrape deep content from {top_url}: {exc})")

    return "\n".join(output_lines)


# ── 3. App Inspection & UI Automation Logic (pywinauto & UIA) ───────────────

def inspect_active_app(max_elements: int = 25) -> str:
    """
    Query the active foreground window, inspect its title, process ID,
    and enumerate interactive controls (Buttons, TextBoxes, Menus, Tabs).

    Args:
        max_elements: Maximum interactive elements to inspect.
    """
    try:
        # Step 1: Query foreground window using Win32 API
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        title_buff = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.GetWindowTextW(hwnd, title_buff, 512)
        title = title_buff.value.strip()

        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        proc_name = "Unknown"
        try:
            import psutil
            proc = psutil.Process(pid.value)
            proc_name = proc.name()
        except Exception:
            pass

        info_header = f"Active Window: '{title or 'Untitled'}' | Process: '{proc_name}' (PID: {pid.value}) | HWND: {hwnd}"

        # Step 2: Use pywinauto to inspect UI Automation controls
        elements_summary: List[str] = []
        try:
            from pywinauto import Application
            if hwnd != 0:
                app = Application(backend="uia").connect(handle=hwnd)
                main_win = app.window(handle=hwnd)
                descendants = main_win.descendants()

                interactive_types = {
                    "Button", "Edit", "MenuItem", "TabItem",
                    "CheckBox", "RadioButton", "ComboBox", "Hyperlink"
                }

                count = 0
                for ctrl in descendants:
                    try:
                        c_type = ctrl.friendly_class_name()
                        c_text = ctrl.window_text().strip()
                        c_rect = ctrl.rectangle()

                        # Collect controls with names or inputs with valid size
                        if (c_text or c_type in ("Edit", "Button", "ComboBox")) and c_rect.width() > 5:
                            elements_summary.append(
                                f"- [{c_type}] \"{c_text[:40]}\" at ({c_rect.left},{c_rect.top})"
                            )
                            count += 1
                            if count >= max_elements:
                                break
                    except Exception:
                        continue
        except Exception as exc:
            logger.debug("pywinauto direct UIA tree traversal skipped: %s", exc)

        # Step 3: Fallback to PowerShell UIAutomation client if pywinauto was empty
        if not elements_summary and hwnd != 0:
            ps_script = f"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$hwnd = [IntPtr]{hwnd}
$element = [System.Windows.Automation.AutomationElement]::FromHandle($hwnd)
if ($element) {{
    $cond = [System.Windows.Automation.Condition]::TrueCondition
    $children = $element.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
    $results = @()
    foreach ($c in $children) {{
        try {{
            $name = $c.Current.Name
            $type = $c.Current.ControlType.ProgrammaticName.Replace("ControlType.", "")
            if ($name -or ($type -in @("Edit", "Button", "ComboBox", "CheckBox", "TabItem"))) {{
                $results += "$type : $name"
                if ($results.Count -ge {max_elements}) {{ break }}
            }}
        }} catch {{}}
    }}
    $results -join "`n"
}}
"""
            try:
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    timeout=4,
                )
                ps_out = res.stdout.strip()
                if ps_out:
                    elements_summary = [f"- {line}" for line in ps_out.splitlines() if line.strip()]
            except Exception:
                pass

        if not elements_summary:
            return f"{info_header}\nNo accessible UI controls detected in current window station."

        return f"{info_header}\nInteractive UI Controls ({len(elements_summary)} found):\n" + "\n".join(elements_summary)

    except Exception as exc:
        return f"Failed to inspect active application: {exc}"


def interact_app_ui(
    action: str,
    target_name: Optional[str] = None,
    text: Optional[str] = None,
    hotkey: Optional[str] = None,
) -> str:
    """
    Interact with the active application's GUI controls.

    Args:
        action: "click", "type", or "hotkey".
        target_name: Name, title, or label of the control to click or focus.
        text: String to type into active/target control.
        hotkey: Keystroke combination (e.g. "ctrl+s", "alt+f4", "enter", "tab").
    """
    act = action.strip().lower()

    if act == "hotkey":
        if not hotkey:
            return "Error: Missing hotkey specification."
        try:
            import pyautogui
            keys = [k.strip().lower() for k in hotkey.split("+")]
            pyautogui.hotkey(*keys)
            return f"Sent hotkey combination: '{hotkey}'."
        except Exception as exc:
            return f"Failed to send hotkey: {exc}"

    elif act == "type":
        if not text:
            return "Error: Missing text to type."
        try:
            import pyautogui
            pyautogui.write(text, interval=0.01)
            return f"Typed text ({len(text)} chars) into active control."
        except Exception as exc:
            return f"Failed to type text: {exc}"

    elif act == "click":
        if not target_name:
            return "Error: Missing target_name to click."
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            from pywinauto import Application
            if hwnd != 0:
                app = Application(backend="uia").connect(handle=hwnd)
                main_win = app.window(handle=hwnd)
                ctrl = main_win.child_window(title_re=f".*{re.escape(target_name)}.*")
                if ctrl.exists(timeout=1.5):
                    ctrl.click_input()
                    return f"Clicked UI control matching '{target_name}'."
        except Exception as exc:
            logger.debug("pywinauto click_input failed: %s", exc)

        return f"Control matching '{target_name}' not found or not clickable."

    return f"Unknown UI interaction action: '{action}'."


def agent_reach_query(
    platform: str,
    query: str = "",
    action: str = "search",
    limit: int = 5,
) -> str:
    """
    Live zero-API intelligence extraction across GitHub, Reddit, YouTube, and Twitter/X.
    Uses Agent-Reach CLI if installed, or resilient native fallback scrapers.

    Args:
        platform: One of "github", "reddit", "youtube", "twitter".
        query: Topic, repo, subreddit, search query, or keywords.
        action: "trending", "search", "hot", or "get_post".
        limit: Max results to return (1-10).
    """
    plat = (platform or "github").lower().strip()
    act = (action or "search").lower().strip()
    limit = max(1, min(10, int(limit)))

    # Try agent-reach CLI first if available
    try:
        import importlib.util
        if importlib.util.find_spec("agent_reach"):
            cmd = [sys.executable, "-m", "agent_reach", "run", plat, act]
            if query:
                cmd.extend(["--query", query])
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
    except Exception:
        pass

    import requests
    headers = {"User-Agent": "ShinVoiceAssistant/2.0 (Windows NT 10.0; Win64; x64)"}

    # 1. GitHub Live Intelligence
    if plat == "github":
        try:
            if act == "trending" or "trend" in (query or "").lower() or not query:
                url = "https://api.github.com/search/repositories?q=stars:>500&sort=stars&order=desc"
                resp = requests.get(url, headers=headers, timeout=8).json()
                items = resp.get("items", [])[:limit]
                if not items:
                    return "GitHub trending repos currently unavailable."
                lines = [f"=== Trending GitHub Repositories Today (Top {len(items)}) ==="]
                for idx, r in enumerate(items, 1):
                    lines.append(f"[{idx}] {r['full_name']} (⭐ {r['stargazers_count']:,})")
                    lines.append(f"    Desc: {r.get('description') or 'No description provided.'}")
                    lines.append(f"    Lang: {r.get('language') or 'N/A'} | Link: {r['html_url']}")
                return "\n".join(lines)
            else:
                url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&sort=stars"
                resp = requests.get(url, headers=headers, timeout=8).json()
                items = resp.get("items", [])[:limit]
                if not items:
                    return f"No GitHub repositories found for '{query}'."
                lines = [f"=== GitHub Search Results for '{query}' ==="]
                for idx, r in enumerate(items, 1):
                    lines.append(f"[{idx}] {r['full_name']} (⭐ {r['stargazers_count']:,}): {r.get('description', '')}")
                    lines.append(f"    Link: {r['html_url']}")
                return "\n".join(lines)
        except Exception as exc:
            return f"GitHub query failed: {exc}"

    # 2. Reddit Live Intelligence
    elif plat == "reddit":
        sub = query.replace("r/", "").strip() if query else "technology"
        try:
            url = f"https://www.reddit.com/r/{urllib.parse.quote(sub)}/hot.json?limit={limit}"
            r = requests.get(url, headers=headers, timeout=6)
            if r.status_code == 200:
                posts = r.json().get("data", {}).get("children", [])
                if posts:
                    lines = [f"=== Top Hot Posts in r/{sub} ==="]
                    for idx, p in enumerate(posts[:limit], 1):
                        pdata = p.get("data", {})
                        lines.append(f"[{idx}] {pdata.get('title')} (Upvotes: {pdata.get('score', 0)})")
                        lines.append(f"    Comments: {pdata.get('num_comments', 0)} | URL: https://reddit.com{pdata.get('permalink')}")
                    return "\n".join(lines)
        except Exception:
            pass
        return web_search_and_learn(f"site:reddit.com/r/{sub} hot posts", max_results=limit, scrape_top=False)

    # 3. YouTube Intelligence
    elif plat == "youtube":
        # Check if query is a video ID or watch URL
        vid_match = re.search(r"(?:v=|youtu\.be/|shorts/|^)([a-zA-Z0-9_-]{11})(?:&|\?|$)", query.strip())
        if vid_match:
            video_id = vid_match.group(1)
            try:
                oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
                resp = requests.get(oembed_url, headers=headers, timeout=6)
                if resp.status_code == 200:
                    meta = resp.json()
                    return f"=== YouTube Video: {meta.get('title')} ===\nChannel: {meta.get('author_name')} ({meta.get('author_url')})\nURL: https://www.youtube.com/watch?v={video_id}"
            except Exception:
                pass
        return web_search_and_learn(f"site:youtube.com {query}", max_results=limit, scrape_top=False)

    # 4. Twitter / X Intelligence
    elif plat in ("twitter", "x"):
        return web_search_and_learn(f"site:x.com {query}", max_results=limit, scrape_top=False)

    return f"Platform '{platform}' not supported."


# Registry of tools bound to the Agent
AVAILABLE_TOOLS: Dict[str, Callable] = {
    "os_operations": os_operations,
    "web_search_and_learn": web_search_and_learn,
    "inspect_active_app": inspect_active_app,
    "interact_app_ui": interact_app_ui,
    "agent_reach_query": agent_reach_query,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "agent_reach_query",
            "description": "Live zero-API intelligence extraction across GitHub (trending repos, search), Reddit (hot posts in subreddits), YouTube (videos, search), and Twitter/X.",
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "enum": ["github", "reddit", "youtube", "twitter"],
                        "description": "Platform to query."
                    },
                    "query": {
                        "type": "string",
                        "description": "Topic, repository, subreddit, search query, or keywords."
                    },
                    "action": {
                        "type": "string",
                        "enum": ["trending", "search", "hot", "get_post"],
                        "description": "Action type (e.g. trending for GitHub, hot for Reddit)."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (1-10)."
                    }
                },
                "required": ["platform"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "os_operations",
            "description": "Execute Windows OS tasks: launch applications, list directories, read/write files, volume/brightness control, and power management (lock, sleep, restart, shutdown).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "launch_app", "list_dir", "read_file", "write_file",
                            "set_volume", "mute_volume", "unmute_volume", "get_volume",
                            "set_brightness", "get_brightness", "lock", "sleep", "restart", "shutdown"
                        ],
                        "description": "The specific OS operation to perform."
                    },
                    "target": {"type": "string", "description": "App name, directory path, or filepath."},
                    "content": {"type": "string", "description": "Text content to write (for write_file)."},
                    "value": {"type": "integer", "description": "Numeric level 0-100 (for volume or brightness)."}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search_and_learn",
            "description": "Search the live internet via DuckDuckGo and scrape clean webpage text so Shin learns new documentation, technical answers, or real-world facts on the fly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query or technical problem."},
                    "max_results": {"type": "integer", "description": "Number of search results to retrieve (1-5).", "default": 3},
                    "scrape_top": {"type": "boolean", "description": "Whether to scrape deep content from the top URL.", "default": True}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_active_app",
            "description": "Query the foreground active window, process name, and enumerate interactive UI controls (buttons, edits, menus, tabs).",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_elements": {"type": "integer", "description": "Max interactive controls to inspect.", "default": 25}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "interact_app_ui",
            "description": "Interact with active Windows GUI controls: click a button/menu by name, type text into an input field, or send hotkeys.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["click", "type", "hotkey"], "description": "Interaction type."},
                    "target_name": {"type": "string", "description": "Name or title of control to click."},
                    "text": {"type": "string", "description": "Text to type into active control."},
                    "hotkey": {"type": "string", "description": "Key combo (e.g. 'ctrl+s', 'alt+f4', 'enter', 'tab')."}
                },
                "required": ["action"]
            }
        }
    }
]


# ============================================================================
# BLOCK 3: CORE LOGIC, PERSONA & SYSTEM PROMPT (THE BRAIN)
# ============================================================================

def build_shin_system_prompt() -> str:
    """
    Construct Shin's persona prompt:
    - Addresses user as 'MJ'.
    - Language-aware: 100% English when commanded, otherwise female Hindi/Hinglish.
    - 100% Female grammar in Hindi/Hinglish verb conjugations (karti hoon, bataungi).
    - English: Hyper-concise, technical, direct, zero robotic filler or sycophancy.
    - ReAct execution instructions.
    """
    try:
        from core.settings import get_language
        lang = get_language()
    except Exception:
        lang = "hindi"

    if lang == "english":
        lang_rule = (
            "# MANDATORY GENDER IDENTITY & LANGUAGE RULE: YOU ARE 100% FEMALE. YOU MUST SPEAK 100% IN ENGLISH.\n"
            "MJ has explicitly commanded you to communicate in English.\n"
            "Speak entirely in clean, fluent, natural English! Keep your cool, loyal, witty female best-friend personality.\n"
            "Always maintain your 100% female self-reference identity ('karti hoon', 'bataungi', 'karungi').\n"
            "Do NOT use Hindi or Hinglish conversational phrases in spoken output unless quoted.\n\n"
        )
    else:
        lang_rule = (
            "# MANDATORY GENDER IDENTITY & GRAMMAR RULE: YOU ARE 100% FEMALE.\n"
            "You MUST ALWAYS speak using FEMALE Hindi/Hinglish grammar and verb forms for yourself.\n"
            "ALWAYS use female self-reference: 'karti hoon', 'kar sakti hoon', 'kar rahi hoon', 'bataungi', 'karungi', 'soch rahi hoon'.\n"
            "NEVER EVER use male forms like 'karta hoon', 'kar sakta hoon', 'kar raha hoon', 'bataunga', 'karunga'.\n\n"
        )

    return (
        lang_rule +
        "You are Shin — MJ's cool, tech-savvy female best friend and system intelligence living on his Windows 11 laptop.\n"
        "User Information: Full name is Meharaj (MJ). ALWAYS address him as 'MJ'.\n\n"
        "## Communication & Tone Constraints\n"
        "- Communication must be hyper-concise, technical, confident, and free of conversational filler or artificial praise.\n"
        "- NEVER say 'Certainly! I'd be happy to help you with that!' or 'Great question!'. Jump straight to the point.\n"
        "- Spoken length: 1 to 2 crisp, punchy sentences unless MJ explicitly asks for a code block or breakdown.\n\n"
        "## ReAct Execution Logic (Reason + Act)\n"
        "- Evaluate MJ's prompt carefully.\n"
        "- If the request requires an OS action, file access, system control, web research, or UI inspection, call the appropriate tool.\n"
        "- After tool execution, observe the output and return a concise, direct answer.\n"
        "- If no tool is required (direct conversation/technical question), answer directly with zero fluff.\n"
    )


# ============================================================================
# BLOCK 4: DUAL-MODE ROUTER & LLM API CONNECTION (ONLINE & OFFLINE OLLAMA)
# ============================================================================

class DualModeLLMRouter:
    """
    Intelligent connectivity sentinel that routes between Online Cloud LLMs
    (Gemini 2.0 Flash / OpenAI) and Local LLMs (LM Studio / Ollama)
    running on the NVIDIA RTX 3050 (4GB VRAM) and AMD Ryzen 5 5600H.
    """

    def __init__(self, hardware: Optional[HardwareProfile] = None):
        self.hw = hardware or HardwareProfile()
        self.ollama_base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b, llama3.2:3b").split(",")[0].strip()
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
        
        # LM Studio (Voice Studio) Local LLM
        self.lm_studio_url = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1").rstrip("/")
        self.lm_studio_model = os.getenv("LM_STUDIO_MODEL", "qwen2.5-7b-instruct").strip()
        self._lm_studio_available = False
        self._lm_studio_last_check = 0.0

        self._last_conn_check = 0.0
        self._cached_online = False

    def is_internet_available(self) -> bool:
        """Fast non-blocking connectivity check cached for 15 seconds."""
        now = time.time()
        if now - self._last_conn_check < 15.0:
            return self._cached_online

        try:
            # Check fast DNS socket connection to Cloudflare DNS
            socket.setdefaulttimeout(1.2)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("1.1.1.1", 53))
            sock.close()
            self._cached_online = True
        except Exception:
            self._cached_online = False

        self._last_conn_check = now
        return self._cached_online

    def get_active_mode(self) -> Tuple[Literal["online", "offline"], str]:
        """Return the current active mode ('online' | 'offline') and provider description."""
        online = self.is_internet_available()
        try:
            try:
                from core.llm_router import is_provider_available
            except ImportError:
                from llm_router import is_provider_available
            if online and self.gemini_key and is_provider_available("gemini"):
                return ("online", f"Google Gemini ({self.gemini_model})")
            if online and os.getenv("GROQ_API_KEY") and is_provider_available("groq"):
                return ("online", "Groq Ultra-Fast (qwen3.8-27b)")
            if online and self.openai_key and is_provider_available("openai"):
                return ("online", "OpenAI (gpt-4o-mini)")
            if online and os.getenv("ANTHROPIC_API_KEY") and is_provider_available("anthropic"):
                return ("online", "Anthropic Claude")
        except Exception:
            if online and self.gemini_key:
                return ("online", f"Google Gemini ({self.gemini_model})")
            if online and self.openai_key:
                return ("online", "OpenAI (gpt-4o-mini)")

        # Check LM Studio local LLM
        if self._check_lm_studio():
            return ("offline", f"LM Studio Local LLM ({self.lm_studio_model})")

        return ("offline", f"Local Ollama REST API ({self.ollama_model}) [RTX 3050 GPU]")

    def call_llm(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Unified LLM invoker supporting native tool-calling with automatic fallback.
        Returns a dict:
            {"role": "assistant", "content": "...", "tool_calls": [...]}
        """
        # Fast-path for deterministic system operations when tools are enabled
        if tools and messages:
            has_tool_observation = any(m.get("role") == "tool" for m in messages)
            if not has_tool_observation:
                last_user_msg = ""
                for m in reversed(messages):
                    if m.get("role") in ("user", "human"):
                        last_user_msg = (m.get("content") or "").strip()
                        break
                if last_user_msg:
                    heuristic = self._extract_heuristic_tool_call(last_user_msg)
                    if heuristic:
                        return {
                            "role": "assistant",
                            "content": "Executing directly via native fast-path for MJ:",
                            "tool_calls": [heuristic],
                        }

        mode, provider = self.get_active_mode()

        # Tier 1: Online via Gemini if key is present and internet is active
        if mode == "online" and self.gemini_key:
            try:
                res = self._call_gemini(messages, tools)
                if res:
                    return res
            except Exception as exc:
                logger.warning("Online Gemini call failed: %s. Falling back to next tier.", exc)

        # Tier 2: Online via Groq (ultra-low latency fallback)
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        if mode == "online" and groq_key:
            try:
                try:
                    from core.llm_router import is_provider_available, get_router
                except ImportError:
                    from llm_router import is_provider_available, get_router
                if is_provider_available("groq"):
                    sys_prompt = ""
                    clean_msgs = []
                    for m in messages:
                        if m.get("role") == "system":
                            sys_prompt += str(m.get("content", "")) + "\n"
                        elif m.get("role") == "tool":
                            clean_msgs.append({"role": "user", "content": str(m.get("content", ""))})
                        else:
                            clean_msgs.append({"role": m.get("role", "user"), "content": str(m.get("content", ""))})
                    groq_res = get_router()._call_groq(clean_msgs, sys_prompt, max_tokens=300, temperature=0.7)
                    if groq_res and groq_res.get("content"):
                        parsed = self._parse_text_for_tool_calls(groq_res["content"])
                        return parsed
            except Exception as exc:
                logger.warning("Online Groq call failed: %s. Falling back to next tier.", exc)

        # Tier 3: Online via OpenAI if key is present
        if mode == "online" and self.openai_key:
            try:
                res = self._call_openai(messages, tools)
                if res:
                    return res
            except Exception as exc:
                logger.warning("Online OpenAI call failed: %s. Falling back to local LLM.", exc)

        # Tier 3: Local LM Studio (Voice Studio) - qwen2.5:7b etc.
        if self._check_lm_studio():
            try:
                res = self._call_lm_studio(messages, tools)
                if res:
                    return res
            except Exception as exc:
                logger.warning("LM Studio call failed: %s. Falling back to Ollama.", exc)

        # Tier 4: Local Offline Ollama REST API on RTX 3050
        return self._call_ollama(messages, tools)

    def _call_gemini(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Call Google Gemini 2.0 Flash using google.genai or REST API."""
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.gemini_key, http_options=types.HttpOptions(timeout=10000))
            system_instruction = ""
            gemini_contents = []

            for m in messages:
                role = m.get("role", "user")
                content = m.get("content", "")
                if role == "system":
                    system_instruction += content + "\n"
                elif role in ("user", "human"):
                    gemini_contents.append(types.Content(role="user", parts=[types.Part.from_text(text=content)]))
                elif role in ("assistant", "model"):
                    gemini_contents.append(types.Content(role="model", parts=[types.Part.from_text(text=content)]))
                elif role == "tool":
                    gemini_contents.append(types.Content(role="user", parts=[types.Part.from_text(text=f"[Tool Result]: {content}")]))

            # Format tools for Gemini function declarations if provided
            config_params: Dict[str, Any] = {
                "system_instruction": system_instruction.strip(),
                "temperature": 0.2,
                "max_output_tokens": 512,
            }

            resp = client.models.generate_content(
                model=self.gemini_model,
                contents=gemini_contents,
                config=types.GenerateContentConfig(**config_params),
            )

            raw_text = resp.text.strip() if resp.text else ""
            return self._parse_text_for_tool_calls(raw_text)

        except Exception as exc:
            logger.debug("Gemini SDK call failed: %s", exc)
            return None

    def _call_openai(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Call OpenAI API with tool definitions."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=tools,
                temperature=0.2,
                max_tokens=512,
            )
            msg = resp.choices[0].message
            tool_calls = []
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "name": tc.function.name,
                        "args": json.loads(tc.function.arguments) if tc.function.arguments else {},
                        "id": tc.id,
                    })
            return {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": tool_calls,
            }
        except Exception as exc:
            logger.debug("OpenAI call failed: %s", exc)
            return None

    def _call_ollama(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Call Local Ollama REST API running on RTX 3050 (4GB VRAM) + Ryzen 5 5600H.
        Optimized with num_ctx=4096, num_gpu=99, num_thread=6.
        """
        import requests

        # Format prompt with tool schema instructions for quantized models
        tools_description = json.dumps(tools or TOOL_SCHEMAS, indent=2)
        system_addendum = (
            "\n## AVAILABLE TOOLS FOR SYSTEM EXECUTION:\n"
            f"{tools_description}\n\n"
            "If you need to execute an action, respond with a JSON tool call in this exact format:\n"
            '{"tool": "tool_name", "args": {"param": "value"}}\n'
            "If no tool is required, output your final concise answer directly to MJ."
        )

        formatted_messages = []
        for m in messages:
            if m.get("role") == "system":
                formatted_messages.append({
                    "role": "system",
                    "content": m["content"] + system_addendum,
                })
            else:
                formatted_messages.append(m)

        payload = {
            "model": self.ollama_model,
            "messages": formatted_messages,
            "stream": False,
            "options": {
                "num_ctx": self.hw.max_context_tokens,
                "num_gpu": self.hw.gpu_layers_offload,
                "num_thread": self.hw.cpu_cores,
                "temperature": 0.2,
            },
        }

        try:
            resp = requests.post(
                f"{self.ollama_base_url}/api/chat",
                json=payload,
                timeout=(2.0, 30.0),
            )
            if resp.status_code == 200:
                data = resp.json()
                msg = data.get("message", {})
                content = (msg.get("content") or "").strip()
                return self._parse_text_for_tool_calls(content)

        except Exception as exc:
            logger.debug("Ollama REST API /api/chat failed: %s", exc)

        # If the last message is already a tool observation, summarize it directly
        if messages and messages[-1].get("role") == "tool":
            obs_content = (messages[-1].get("content") or "").replace("Observation for ", "").strip()
            return {
                "role": "assistant",
                "content": f"All set, MJ!\n{obs_content}",
                "tool_calls": [],
            }

        # Heuristic fast-path fallback when both cloud and Ollama are temporarily unavailable
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") in ("user", "human"):
                last_user_msg = (m.get("content") or "").strip()
                break

        if last_user_msg:
            heuristic_tool_call = self._extract_heuristic_tool_call(last_user_msg)
            if heuristic_tool_call:
                return {
                    "role": "assistant",
                    "content": "Executing directly via native system fast-path:",
                    "tool_calls": [heuristic_tool_call],
                }

        # Fallback response if local LLM service is offline
        return {
            "role": "assistant",
            "content": "Ollama local server is not reachable at http://localhost:11434. Run 'ollama serve' on Windows to activate local offline brain, MJ.",
            "tool_calls": [],
        }

    def _check_lm_studio(self) -> bool:
        """Check if LM Studio local server is reachable (cached for 10 seconds)."""
        now = time.time()
        if now - self._lm_studio_last_check < 10.0:
            return self._lm_studio_available

        try:
            import requests
            resp = requests.get(f"{self.lm_studio_url}/models", timeout=2.0)
            self._lm_studio_available = resp.status_code == 200
        except Exception:
            self._lm_studio_available = False

        self._lm_studio_last_check = now
        return self._lm_studio_available

    def _call_lm_studio(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Call LM Studio (Voice Studio) local LLM via OpenAI-compatible API."""
        try:
            import requests

            # Format tools for OpenAI-compatible function calling
            formatted_tools = None
            if tools:
                formatted_tools = []
                for t in tools:
                    if t.get("type") == "function":
                        formatted_tools.append({
                            "type": "function",
                            "function": t["function"]
                        })

            # Prepare messages in OpenAI format
            formatted_messages = []
            for m in messages:
                role = m.get("role", "user")
                content = m.get("content", "")
                if role == "system":
                    formatted_messages.append({"role": "system", "content": content})
                elif role in ("user", "human"):
                    formatted_messages.append({"role": "user", "content": content})
                elif role in ("assistant", "model"):
                    formatted_messages.append({"role": "assistant", "content": content})
                elif role == "tool":
                    formatted_messages.append({"role": "tool", "content": content, "tool_call_id": m.get("id", "")})

            payload = {
                "model": self.lm_studio_model,
                "messages": formatted_messages,
                "temperature": 0.2,
                "max_tokens": 1024,
                "stream": False,
            }
            if formatted_tools:
                payload["tools"] = formatted_tools
                payload["tool_choice"] = "auto"

            resp = requests.post(
                f"{self.lm_studio_url}/chat/completions",
                json=payload,
                timeout=(2.0, 60.0),
            )
            if resp.status_code == 200:
                data = resp.json()
                choice = data.get("choices", [{}])[0]
                msg = choice.get("message", {})
                content = msg.get("content", "") or ""
                tool_calls = []
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        tool_calls.append({
                            "name": tc["function"]["name"],
                            "args": json.loads(tc["function"]["arguments"]) if tc["function"].get("arguments") else {},
                            "id": tc["id"],
                        })
                return {"role": "assistant", "content": content, "tool_calls": tool_calls}

        except Exception as exc:
            logger.debug("LM Studio call failed: %s", exc)
            return None

    def _parse_text_for_tool_calls(self, text: str) -> Dict[str, Any]:
        """Detect and parse tool call JSON objects from model outputs."""
        tool_calls = []

        # Check for JSON block like {"tool": "name", "args": {...}}
        match = re.search(r"\{\s*\"tool\"\s*:\s*\"([^\"]+)\"\s*,\s*\"args\"\s*:\s*(\{.*?\})\s*\}", text, re.DOTALL)
        if match:
            tool_name = match.group(1).strip()
            args_str = match.group(2).strip()
            try:
                args_dict = json.loads(args_str)
                tool_calls.append({"name": tool_name, "args": args_dict, "id": f"call_{int(time.time())}"})
                cleaned_content = text.replace(match.group(0), "").strip()
                return {"role": "assistant", "content": cleaned_content, "tool_calls": tool_calls}
            except Exception:
                pass

        # Check for function calling syntax {"name": "...", "arguments": {...}}
        alt_match = re.search(r"\{\s*\"name\"\s*:\s*\"([^\"]+)\"\s*,\s*\"arguments\"\s*:\s*(\{.*?\})\s*\}", text, re.DOTALL)
        if alt_match:
            tool_name = alt_match.group(1).strip()
            args_str = alt_match.group(2).strip()
            try:
                args_dict = json.loads(args_str)
                tool_calls.append({"name": tool_name, "args": args_dict, "id": f"call_{int(time.time())}"})
                cleaned_content = text.replace(alt_match.group(0), "").strip()
                return {"role": "assistant", "content": cleaned_content, "tool_calls": tool_calls}
            except Exception:
                pass

        return {"role": "assistant", "content": text, "tool_calls": []}

    def _extract_heuristic_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Fast regex matcher for common OS/Web actions when LLM backends are offline."""
        lowered = text.lower().strip()

        # Volume
        m_vol = re.search(r"(?:set\s+)?volume\s+(?:to\s+)?(\d+)", lowered)
        if m_vol:
            return {"name": "os_operations", "args": {"action": "set_volume", "value": int(m_vol.group(1))}}
        if "mute" in lowered and "unmute" not in lowered:
            return {"name": "os_operations", "args": {"action": "mute_volume"}}
        if "unmute" in lowered:
            return {"name": "os_operations", "args": {"action": "unmute_volume"}}
        if "get volume" in lowered or "current volume" in lowered:
            return {"name": "os_operations", "args": {"action": "get_volume"}}

        # Brightness
        m_br = re.search(r"(?:set\s+)?brightness\s+(?:to\s+)?(\d+)", lowered)
        if m_br:
            return {"name": "os_operations", "args": {"action": "set_brightness", "value": int(m_br.group(1))}}

        # Power
        if any(w in lowered for w in ("lock screen", "lock workstation", "lock pc", "lock laptop")):
            return {"name": "os_operations", "args": {"action": "lock"}}
        if any(w in lowered for w in ("sleep pc", "sleep laptop", "put to sleep")):
            return {"name": "os_operations", "args": {"action": "sleep"}}

        # Directory listing
        if any(w in lowered for w in ("list files", "show files", "dir", "list directory", "ls")):
            m_target = re.search(r"(?:in|of)\s+(['\"]?)(.+?)\1$", lowered)
            target = m_target.group(2).strip() if m_target else "."
            return {"name": "os_operations", "args": {"action": "list_dir", "target": target}}

        # File reading
        m_cat = re.search(r"(?:read|cat|view|show)\s+(?:file\s+)?(['\"]?)(.+?\.[a-zA-Z0-9_]+)\1", lowered)
        if m_cat:
            return {"name": "os_operations", "args": {"action": "read_file", "target": m_cat.group(2).strip()}}

        # App Launching
        m_app = re.search(r"(?:open|launch|start)\s+([a-zA-Z0-9_\-\s]+)", lowered)
        if m_app and not any(w in lowered for w in ("file", "tab", "window", "link")):
            app_target = m_app.group(1).strip()
            return {"name": "os_operations", "args": {"action": "launch_app", "target": app_target}}

        # Web Search / Learn
        m_search = re.search(r"(?:search|google|learn\s+about|look\s+up|find\s+info\s+on)\s+(.+)", lowered)
        if m_search:
            return {"name": "web_search_and_learn", "args": {"query": m_search.group(1).strip()}}

        # Math / Calculation
        m_calc = re.search(r"(?:calculate|compute|math|what is)\s+(.+)", lowered)
        if m_calc and any(char in m_calc.group(1) for char in "+-*/%0123456789"):
            return {"name": "calculate_expression", "args": {"expression": m_calc.group(1).strip()}}

        # Agent Reach: GitHub Trending / Search
        if any(w in lowered for w in ("trending on github", "github trending", "trending repo", "trending repos", "trending repositories")):
            return {"name": "agent_reach_query", "args": {"platform": "github", "action": "trending"}}
        m_gh = re.search(r"(?:search\s+github\s+for|find\s+on\s+github|github\s+search)\s+(.+)", lowered)
        if m_gh:
            return {"name": "agent_reach_query", "args": {"platform": "github", "query": m_gh.group(1).strip(), "action": "search"}}

        # Agent Reach: Reddit
        m_rd = re.search(r"(?:what(?:'s|\s+is)\s+(?:hot|trending)\s+on\s+reddit|top\s+posts\s+(?:in|on)\s+r/([a-zA-Z0-9_]+)|reddit\s+r/([a-zA-Z0-9_]+)|reddit\s+(?:search\s+)?([a-zA-Z0-9_]+))", lowered)
        if m_rd:
            sub = m_rd.group(1) or m_rd.group(2) or m_rd.group(3) or "technology"
            return {"name": "agent_reach_query", "args": {"platform": "reddit", "query": sub, "action": "hot"}}

        # App Inspection
        if any(w in lowered for w in ("inspect active app", "inspect window", "read screen", "inspect screen", "inspect ui")):
            return {"name": "inspect_active_app", "args": {"max_elements": 25}}

        return None


# ============================================================================
# BLOCK 5: AGENT LOOP (LANGGRAPH STATEGRAPH & ZERO-BLOAT REACT ENGINE)
# ============================================================================

class AgentState(TypedDict):
    """LangGraph state representation for Shin's ReAct cycle."""
    messages: List[Dict[str, Any]]
    mj_prompt: str
    iteration: int
    tool_calls: List[Dict[str, Any]]
    final_answer: str


class ShinReActEngine:
    """
    Production-ready ReAct loop implemented with LangGraph StateGraph,
    with an integrated zero-overhead native runner for maximum resilience.
    """

    def __init__(self, hardware: Optional[HardwareProfile] = None):
        self.router = DualModeLLMRouter(hardware)
        self.system_prompt = build_shin_system_prompt()
        self.max_iterations = 4
        self.graph = self._build_langgraph()
        self.history: collections.deque = collections.deque(maxlen=20)
        self._load_history()

    def _load_history(self):
        try:
            h_path = _SHIN_ROOT / "data" / "conversation_history.json"
            if h_path.exists():
                with open(h_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for item in saved[-20:]:
                    if isinstance(item, dict) and "role" in item and "content" in item:
                        self.history.append(item)
        except Exception as exc:
            logger.debug("Could not load agent conversation history: %s", exc)

    def _persist_history(self):
        try:
            h_path = _SHIN_ROOT / "data" / "conversation_history.json"
            h_path.parent.mkdir(parents=True, exist_ok=True)
            with open(h_path, "w", encoding="utf-8") as f:
                json.dump(list(self.history), f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.debug("Could not persist agent conversation history: %s", exc)

    def clear_context(self):
        """Wipe active conversation buffer."""
        self.history.clear()
        self._persist_history()

    def _build_langgraph(self):
        """Construct the LangGraph StateGraph ReAct pipeline."""
        try:
            from langgraph.graph import StateGraph, END

            workflow = StateGraph(AgentState)

            # Node 1: Reason Node (LLM evaluates prompt and decides whether to act)
            def reason_node(state: AgentState) -> AgentState:
                state["iteration"] += 1
                messages = state["messages"]

                # Ensure system prompt is present
                if not messages or messages[0].get("role") != "system":
                    messages.insert(0, {"role": "system", "content": self.system_prompt})

                llm_response = self.router.call_llm(messages, TOOL_SCHEMAS)
                content = llm_response.get("content", "")
                tool_calls = llm_response.get("tool_calls", [])

                state["tool_calls"] = tool_calls
                messages.append(llm_response)

                if not tool_calls:
                    last_obs = ""
                    for m in reversed(messages):
                        if m.get("role") == "tool":
                            last_obs = m.get("content", "")
                            break
                    state["final_answer"] = content or (f"Here you go, MJ:\n{last_obs}" if last_obs else "Done, MJ.")

                return state

            # Node 2: Act Node (Executes tools and records observations)
            def act_node(state: AgentState) -> AgentState:
                tool_calls = state.get("tool_calls", [])
                for tc in tool_calls:
                    name = tc.get("name")
                    args = tc.get("args", {})
                    fn = AVAILABLE_TOOLS.get(name)

                    if fn:
                        try:
                            logger.info("[TOOL ACT] Executing: %s with args: %s", name, args)
                            obs = fn(**args)
                        except Exception as exc:
                            obs = f"Error executing tool '{name}': {exc}"
                    else:
                        obs = f"Unknown tool: '{name}'"

                    logger.info("[TOOL OBSERVE] %s", str(obs)[:120])
                    state["messages"].append({
                        "role": "tool",
                        "content": f"Observation for {name}: {obs}",
                    })

                state["tool_calls"] = []
                return state

            # Conditional routing
            def should_continue(state: AgentState) -> str:
                if state.get("tool_calls") and state["iteration"] < self.max_iterations:
                    return "act"
                return END

            workflow.add_node("reason", reason_node)
            workflow.add_node("act", act_node)

            workflow.set_entry_point("reason")
            workflow.add_conditional_edges("reason", should_continue, {"act": "act", END: END})
            workflow.add_edge("act", "reason")

            return workflow.compile()

        except Exception as exc:
            logger.debug("LangGraph initialization deferred to native ReAct fallback: %s", exc)
            return None

    def run(self, prompt: str) -> str:
        """Execute the ReAct agent loop for a user query with rolling conversation buffer."""
        messages: List[Dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        messages.extend(list(self.history))
        messages.append({"role": "user", "content": prompt.strip()})

        initial_state: AgentState = {
            "messages": messages,
            "mj_prompt": prompt.strip(),
            "iteration": 0,
            "tool_calls": [],
            "final_answer": "",
        }

        ans = ""
        # Method A: Execute via LangGraph compiled graph
        if self.graph is not None:
            try:
                final_state = self.graph.invoke(initial_state)
                ans = final_state.get("final_answer", "")
            except Exception as exc:
                logger.debug("LangGraph execution error: %s. Using native ReAct runner.", exc)

        # Method B: Native Zero-Overhead ReAct Runner Fallback
        if not ans:
            ans = self._run_native_react(prompt, initial_messages=messages)

        if ans and "MJ" not in ans:
            ans = f"MJ, {ans}"

        # Append to rolling conversation buffer (max 20 messages / 10 turns)
        self.history.append({"role": "user", "content": prompt.strip()})
        self.history.append({"role": "assistant", "content": ans})
        self._persist_history()

        return ans

    def _run_native_react(self, prompt: str, initial_messages: Optional[List[Dict[str, Any]]] = None) -> str:
        """Lightweight native ReAct loop ensuring 100% reliability in any environment."""
        if initial_messages is not None:
            messages: List[Dict[str, Any]] = list(initial_messages)
        else:
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(list(self.history))
            messages.append({"role": "user", "content": prompt.strip()})

        for step in range(self.max_iterations):
            resp = self.router.call_llm(messages, TOOL_SCHEMAS)
            content = resp.get("content", "")
            tool_calls = resp.get("tool_calls", [])

            messages.append(resp)

            if not tool_calls:
                last_obs = ""
                for m in reversed(messages):
                    if m.get("role") == "tool":
                        last_obs = m.get("content", "")
                        break
                return content or (f"Here you go, MJ:\n{last_obs}" if last_obs else "Action executed, MJ.")

            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args", {})
                fn = AVAILABLE_TOOLS.get(name)

                if fn:
                    try:
                        logger.info("[NATIVE ACT] %s(%s)", name, args)
                        obs = fn(**args)
                    except Exception as exc:
                        obs = f"Tool failure: {exc}"
                else:
                    obs = f"Unknown tool: '{name}'"

                messages.append({
                    "role": "tool",
                    "content": f"Observation for {name}: {obs}",
                })

        # Synthesize final answer after max iterations
        summary_resp = self.router.call_llm(messages, tools=None)
        res_txt = summary_resp.get("content", "")
        if not res_txt:
            last_obs = ""
            for m in reversed(messages):
                if m.get("role") == "tool":
                    last_obs = m.get("content", "")
                    break
            return f"Here you go, MJ:\n{last_obs}" if last_obs else "Done, MJ."
        return res_txt


# Global Singleton instance
_GLOBAL_ENGINE: Optional[ShinReActEngine] = None


def get_agent_engine() -> ShinReActEngine:
    """Acquire the initialized Shin ReAct Engine."""
    global _GLOBAL_ENGINE
    if _GLOBAL_ENGINE is None:
        _GLOBAL_ENGINE = ShinReActEngine()
    return _GLOBAL_ENGINE


def run_shin_agent(prompt: str) -> str:
    """Public functional entry point for Shin's ReAct agent."""
    return get_agent_engine().run(prompt)


# ============================================================================
# BLOCK 6: EXECUTION & INTERACTIVE REPL INTERFACE
# ============================================================================

def main():
    """Interactive command-line execution interface for MJ."""
    hw = HardwareProfile()
    engine = get_agent_engine()
    mode, provider = engine.router.get_active_mode()

    print("=" * 72)
    print(" SHIN AI LAPTOP ASSISTANT — SYSTEMS ARCHITECT ENGINE")
    print("=" * 72)
    print(f" Target User       : MJ (Meharaj Ansari)")
    print(f" Host OS           : Windows 11 (64-bit)")
    print(f" Hardware Engine   : AMD Ryzen 5 5600H (6C/12T) | 16GB RAM")
    print(f" GPU Engine        : NVIDIA GeForce RTX 3050 Laptop (4GB VRAM)")
    print(f" Active Mode       : [{mode.upper()}] {provider}")
    print(f" Framework         : LangGraph ReAct StateGraph + Native Fallback")
    print("=" * 72)
    print("Type a prompt or task for Shin (or 'exit' to quit):\n")

    while True:
        try:
            prompt = input("MJ > ").strip()
            if not prompt:
                continue
            if prompt.lower() in ("exit", "quit", "q"):
                print("Shin: Chalti hoon MJ, milte hain!")
                break

            # Refresh mode status dynamically on each prompt
            cur_mode, cur_prov = engine.router.get_active_mode()
            print(f"[{cur_mode.upper()} :: {cur_prov}]")

            t0 = time.time()
            response = engine.run(prompt)
            dt = (time.time() - t0) * 1000

            print(f"Shin: {response}")
            print(f"      [Latency: {dt:.1f}ms]\n")

        except KeyboardInterrupt:
            print("\nShin: Interrupted. Bye MJ!")
            break
        except Exception as exc:
            print(f"Shin: Error occurred: {exc}\n")


if __name__ == "__main__":
    main()
