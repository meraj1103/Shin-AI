"""mate_bridge.py — Mate Engine 3D Avatar IPC Bridge for Shin.
Connects Shin directly to MateEngineX.exe (Unity 3D Desktop Mascot):
  • Process lifecycle management (autostart, watchdog auto-recovery, graceful shutdown)
  • Borderless transparent window positioning via Win32 API
  • Synchronous state broadcast: idle, listening, thinking, speaking, dance, error
  • Coordinated parallel presence with Dynamic Island
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("shin.mate_bridge")

# ── Win32 APIs for Window Discovery and Positioning ──────────────────────────
_WIN32_AVAILABLE = False
try:
    import win32gui
    import win32con
    import win32process
    _WIN32_AVAILABLE = True
except ImportError:
    logger.debug("pywin32 not available; running in headless mode for window management.")

try:
    import ctypes
except Exception:
    pass

# Paths
_CORE_DIR = Path(__file__).parent.resolve()
_SHIN_DIR = _CORE_DIR.parent
_ROOT_DIR = _SHIN_DIR.parent
_DATA_DIR = _SHIN_DIR / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

for _p in (str(_ROOT_DIR), str(_SHIN_DIR), str(_CORE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_DEFAULT_ENGINE_EXE = _SHIN_DIR / "mate engin" / "MateEngineX.exe"
_STATE_FILE = _DATA_DIR / "shin_mate_state.json"
_POS_FILE = _DATA_DIR / "mate_position.json"
_MATE_PERSISTENT_DIR = Path(os.environ.get("USERPROFILE", "")) / "AppData" / "LocalLow" / "Shinymoon" / "MateEngineX"
_MATE_PROMPT_FILE = _MATE_PERSISTENT_DIR / "ZomeAI_prompt.txt"


def find_mate_engine_exe() -> Optional[Path]:
    """Search for MateEngineX.exe in known workspace paths."""
    # 1. Direct path in Shin
    if _DEFAULT_ENGINE_EXE.is_file():
        return _DEFAULT_ENGINE_EXE

    # 2. Environment variable
    env_path = os.getenv("MATE_ENGINE_PATH")
    if env_path and Path(env_path).is_file():
        return Path(env_path)

    # 3. Known sibling / alternative directory
    sibling = _SHIN_DIR.parent / "HAYA-AI-Assistant" / "HAYA" / "Public.Release.X3.3.0-HOTFIX-1" / "MateEngineX.exe"
    if sibling.is_file():
        return sibling

    return None


class MateBridge:
    """Manages the 3D Desktop Mascot (MateEngineX) lifecycle and synchronizes
    Shin's voice and thinking states with the avatar.
    """

    _instance: Optional[MateBridge] = None

    _WINDOW_CLASS_HINT = "UnityWndClass"
    _WINDOW_TITLE_HINT = "MateEngineX"

    def __init__(self, exe_path: Optional[Path] = None):
        self.exe_path: Optional[Path] = exe_path or find_mate_engine_exe()
        self.enabled: bool = os.getenv("MATE_ENGINE_ENABLED", "true").lower() in ("true", "1", "yes")
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.hwnd: Optional[int] = None
        self.is_running: bool = False
        self.current_state: str = "idle"
        self._lock = threading.Lock()

        # Window Position
        self.pos_x, self.pos_y = self._load_saved_position()

        # Watchdog & finder threads
        self._finder_thread: Optional[threading.Thread] = None
        self._watchdog_thread: Optional[threading.Thread] = None

        # LLM Proxy Server for Port 13333
        self._proxy_server: Optional[Any] = None

    @classmethod
    def get(cls) -> MateBridge:
        if cls._instance is None:
            cls._instance = MateBridge()
        return cls._instance

    def _load_saved_position(self) -> Tuple[int, int]:
        """Load saved desktop coordinates or default to bottom-right corner."""
        default_x, default_y = 1100, 200
        if _POS_FILE.exists():
            try:
                with open(_POS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return int(data.get("x", default_x)), int(data.get("y", default_y))
            except Exception:
                pass
        return default_x, default_y

    def _save_position(self) -> None:
        """Persist current mascot window coordinates."""
        if self.hwnd and _WIN32_AVAILABLE:
            try:
                rect = win32gui.GetWindowRect(self.hwnd)
                self.pos_x = rect[0]
                self.pos_y = rect[1]
                with open(_POS_FILE, "w", encoding="utf-8") as f:
                    json.dump({"x": self.pos_x, "y": self.pos_y}, f, indent=2)
            except Exception as exc:
                logger.debug("Could not save avatar window position: %s", exc)

    def sync_prompt(self, custom_prompt: Optional[str] = None) -> bool:
        """Synchronize Shin's custom personality prompt directly into Mate Engine's
        ZomeAI_prompt.txt file loaded by AISystemPromptBinder.
        """
        try:
            if not custom_prompt:
                from Shin.core.conversation_flow import ConversationFlowManager
                flow = ConversationFlowManager.get()
                custom_prompt = flow.build_system_prompt()

            _MATE_PERSISTENT_DIR.mkdir(parents=True, exist_ok=True)
            with open(_MATE_PROMPT_FILE, "w", encoding="utf-8") as f:
                f.write(custom_prompt)
            logger.info("Synchronized prompt to Mate Engine: %s (%d chars)", _MATE_PROMPT_FILE, len(custom_prompt))
            return True
        except Exception as exc:
            logger.warning("Failed to sync prompt to Mate Engine: %s", exc)
            return False

    def sync_speech(self, text: str) -> None:
        """Broadcast live speech text and avatar speaking state to Mate Engine."""
        self.set_state("speaking", {"speech_text": text, "length": len(text)})

    def _handle_llm_query(self, query: str, messages: List[Dict[str, str]]) -> str:
        """Handle incoming chat completions from Mate Engine on port 13333."""
        try:
            from Shin.core.conversation_flow import ConversationFlowManager
            from Shin.core.llm_router import LLMRouter

            flow = ConversationFlowManager.get()
            system_prompt = flow.build_system_prompt()

            # Broadcast thinking state
            self.set_state("thinking", {"query": query[:60]})

            # Query Shin's LLM engine
            router = LLMRouter.get_instance()
            chat_msgs = messages if messages else [{"role": "user", "content": query}]
            resp = router.chat(chat_msgs, system_prompt=system_prompt, max_tokens=150)
            reply_text = resp.get("content", "Arey MJ! I am here.")

            # Broadcast speaking state with the response
            self.sync_speech(reply_text)
            return reply_text
        except Exception as exc:
            logger.error("Error generating LLM reply for Mate Engine: %s", exc)
            return "Arey MJ! I am right here with you."

    def start(self) -> bool:
        """Launch MateEngineX.exe as a managed background process with port 13333 proxy."""
        if not self.enabled:
            logger.info("Mate Engine is disabled via configuration.")
            return False

        # 1. Sync persona prompt into Mate Engine
        self.sync_prompt()

        # 2. Start Port 13333 LLM Proxy Server
        if self._proxy_server is None:
            try:
                from Shin.core.mate_llm_proxy import MateLLMProxyServer
                self._proxy_server = MateLLMProxyServer(host="127.0.0.1", port=13333)
                self._proxy_server.set_handler(self._handle_llm_query)
                self._proxy_server.start()
            except Exception as pe:
                logger.warning("Could not start Mate LLM Proxy: %s", pe)

        if not self.exe_path or not self.exe_path.is_file():
            logger.warning("MateEngineX.exe not found at %s", self.exe_path)
            return False

        if self.is_process_alive():
            logger.info("Mate Engine is already running (PID: %s)", self.pid)
            if not self.hwnd:
                self._finder_thread = threading.Thread(
                    target=self._find_window_loop, name="MateFinder", daemon=True
                )
                self._finder_thread.start()
            return True

        with self._lock:
            try:
                logger.info("Starting Mate Engine avatar: %s", self.exe_path)
                creation_flags = 0
                if hasattr(subprocess, "DETACHED_PROCESS"):
                    creation_flags |= subprocess.DETACHED_PROCESS
                if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                    creation_flags |= subprocess.CREATE_NEW_PROCESS_GROUP

                self.process = subprocess.Popen(
                    [str(self.exe_path)],
                    cwd=str(self.exe_path.parent),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creation_flags,
                )
                self.pid = self.process.pid
                self.is_running = True
                logger.info("Mate Engine avatar started (PID: %d)", self.pid)

                # Broadcast initial state
                self.set_state("idle")

                # Launch discovery and watchdog threads
                self._finder_thread = threading.Thread(
                    target=self._find_window_loop, name="MateFinder", daemon=True
                )
                self._finder_thread.start()

                self._watchdog_thread = threading.Thread(
                    target=self._watchdog_loop, name="MateWatchdog", daemon=True
                )
                self._watchdog_thread.start()
                return True
            except Exception as exc:
                logger.error("Failed to start Mate Engine: %s", exc)
                self.is_running = False
                return False

    def is_process_alive(self) -> bool:
        """Check if the MateEngineX process is currently running."""
        if self.process is not None and self.process.poll() is None:
            return True
        try:
            import psutil
            for proc in psutil.process_iter(["pid", "name"]):
                name = proc.info.get("name") or ""
                if "mateenginex" in name.lower():
                    self.pid = proc.info["pid"]
                    self.is_running = True
                    return True
        except Exception:
            pass
        return False

    def _find_window_loop(self) -> None:
        """Locate the Unity mascot window and reposition it."""
        deadline = time.time() + 20.0
        while self.is_running and time.time() < deadline:
            hwnd = self._discover_window()
            if hwnd:
                self.hwnd = hwnd
                logger.info("Attached to Mate Engine window handle: %s", hwnd)
                self.apply_position()
                break
            time.sleep(0.5)

    def _discover_window(self) -> Optional[int]:
        """Find the Unity transparent window belonging to our process."""
        if not _WIN32_AVAILABLE or not self.pid:
            return None

        found_hwnd = [None]

        def _enum_cb(hwnd, _):
            try:
                _, w_pid = win32process.GetWindowThreadProcessId(hwnd)
                if w_pid == self.pid:
                    cls_name = win32gui.GetClassName(hwnd)
                    title = win32gui.GetWindowText(hwnd)
                    if cls_name == self._WINDOW_CLASS_HINT or self._WINDOW_TITLE_HINT.lower() in title.lower():
                        found_hwnd[0] = hwnd
                        return False
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(_enum_cb, None)
        except Exception:
            pass

        if found_hwnd[0]:
            try:
                # Ensure the window is shown and brought to front
                win32gui.ShowWindow(found_hwnd[0], win32con.SW_RESTORE)
                win32gui.ShowWindow(found_hwnd[0], win32con.SW_SHOW)
            except Exception as e:
                logger.debug("Error restoring found window: %s", e)

        return found_hwnd[0]

    def apply_position(self) -> None:
        """Place the mascot at the desired screen coordinates."""
        if not self.hwnd or not _WIN32_AVAILABLE:
            return
        try:
            rect = win32gui.GetWindowRect(self.hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w <= 0 or h <= 0:
                w, h = 400, 600

            # Screen bounds clamp
            user32 = ctypes.windll.user32
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            safe_x = max(10, min(self.pos_x, sw - w))
            safe_y = max(10, min(self.pos_y, sh - h - 40))

            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
            win32gui.SetWindowPos(
                self.hwnd,
                win32con.HWND_TOPMOST,
                safe_x,
                safe_y,
                w,
                h,
                win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE,
            )
            self.pos_x, self.pos_y = safe_x, safe_y
            logger.info("Positioned Mate Engine desktop mascot at (%d, %d) [%dx%d]", safe_x, safe_y, w, h)
        except Exception as exc:
            logger.debug("Error positioning avatar window: %s", exc)

    def _watchdog_loop(self) -> None:
        """Keep the avatar alive unless deliberately stopped."""
        while self.is_running:
            time.sleep(3.0)
            if self.process and self.process.poll() is not None:
                if self.is_running:
                    logger.warning("Mate Engine process exited unexpectedly. Restarting in 2s...")
                    self.hwnd = None
                    time.sleep(2.0)
                    self.start()
                break

    def set_state(self, state: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Broadcast state to the avatar:
        States: 'idle' | 'listening' | 'thinking' | 'speaking' | 'dance' | 'standby' | 'error'
        """
        valid_states = {"idle", "listening", "thinking", "processing", "speaking", "dance", "standby", "error"}
        normalized = "thinking" if state == "processing" else state
        if normalized not in valid_states:
            return

        self.current_state = normalized
        payload: Dict[str, Any] = {
            "state": normalized,
            "timestamp": time.time(),
            "assistant": "Shin",
            "version": "2.0",
        }
        if extra:
            payload.update(extra)

        try:
            with open(_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            # Also write into StreamingAssets if available
            if self.exe_path:
                sa_file = self.exe_path.parent / "MateEngineX_Data" / "StreamingAssets" / "shin_state.json"
                try:
                    with open(sa_file, "w", encoding="utf-8") as f:
                        json.dump(payload, f, indent=2)
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("Failed writing state file: %s", exc)

    def toggle_dance(self) -> str:
        """Toggle dance mode on/off."""
        if self.current_state == "dance":
            self.set_state("idle")
            return "idle"
        else:
            self.set_state("dance")
            return "dance"

    def minimize(self) -> None:
        """Hide the mascot window."""
        if self.hwnd and _WIN32_AVAILABLE:
            try:
                win32gui.ShowWindow(self.hwnd, win32con.SW_MINIMIZE)
            except Exception:
                pass

    def restore(self) -> None:
        """Restore and bring mascot to front."""
        if self.hwnd and _WIN32_AVAILABLE:
            try:
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self.hwnd)
            except Exception:
                pass

    def stop(self) -> None:
        """Gracefully shut down the mascot process and proxy server."""
        self.is_running = False
        self._save_position()

        if self._proxy_server:
            try:
                self._proxy_server.stop()
            except Exception:
                pass
            self._proxy_server = None

        if self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2.5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                logger.info("Mate Engine stopped cleanly.")
            except Exception as exc:
                logger.debug("Warning during avatar shutdown: %s", exc)
            self.process = None
            self.hwnd = None

        if _STATE_FILE.exists():
            try:
                _STATE_FILE.unlink()
            except Exception:
                pass
