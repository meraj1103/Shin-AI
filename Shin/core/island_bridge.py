"""island_bridge.py — Dynamic Island Direct IPC Bridge for Shin.
Connects Shin directly to Windhawk Dynamic Island via Named Pipe:
    \\\\.\\pipe\\ShinDynamicIsland

Bypasses Windows Action Center so the Dynamic Island pill expands instantly
at the top of the monitor with zero delay.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Optional

logger = logging.getLogger("shin.island_bridge")

_WIND_SDK_AVAILABLE = False
try:
    import winsdk.windows.ui.notifications as win_notif
    import winsdk.windows.data.xml.dom as win_xml
    _WIND_SDK_AVAILABLE = True
except Exception:
    pass

_WIN32_AVAILABLE = False
try:
    import win32file
    _WIN32_AVAILABLE = True
except Exception:
    pass


class TerminalThinkingSpinner:
    """Non-blocking live visual thinking indicator for the terminal.
    Shows animated living pulse dots instead of writing 'Thinking...' or 'Processing...'.
    """

    FRAMES = [
        "⠋ [ ●     ]",
        "⠙ [  ●    ]",
        "⠹ [   ●   ]",
        "⠸ [    ●  ]",
        "⠼ [     ● ]",
        "⠴ [    ●  ]",
        "⠦ [   ●   ]",
        "⠧ [  ●    ]",
        "⠇ [ ●     ]",
        "⠏ [● ● ● ●]",
    ]

    def __init__(self, prefix: str = "🤖 Shin"):
        self.prefix = prefix
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the live animated thinking loop in background."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._animate, daemon=True, name="ShinThinkingSpinner")
        self._thread.start()

    def _animate(self) -> None:
        idx = 0
        try:
            sys.stdout.write("\n")
            while not self._stop_event.is_set():
                frame = self.FRAMES[idx % len(self.FRAMES)]
                sys.stdout.write(f"\r\033[36m{self.prefix}\033[0m: \033[33m{frame}\033[0m")
                sys.stdout.flush()
                idx += 1
                time.sleep(0.09)
        except Exception:
            pass

    def stop(self) -> None:
        """Stop animation and cleanly clear the thinking line."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.3)
        try:
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()
        except Exception:
            pass


class IslandBridge:
    """Connects Shin's states and responses directly to Dynamic Island on Windows."""

    PIPE_NAME = r"\\.\pipe\ShinDynamicIsland"
    APP_ID = "Shin.VoiceAssistant"
    _instance: Optional[IslandBridge] = None

    def __init__(self):
        self.spinner = TerminalThinkingSpinner()
        self._last_send_time = 0.0

    @classmethod
    def get(cls) -> IslandBridge:
        if cls._instance is None:
            cls._instance = IslandBridge()
        return cls._instance

    def _send_to_island(self, title: str, body: str, duration: float = 4.0) -> bool:
        """Send message directly to Dynamic Island Named Pipe.
        Falls back to WinRT toast if pipe is not currently connected.
        """
        # 1. Try Direct Named Pipe (Instant < 1ms, bypasses Windows Action Center)
        if _WIN32_AVAILABLE:
            try:
                handle = win32file.CreateFile(
                    self.PIPE_NAME,
                    win32file.GENERIC_WRITE,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    0,
                    None,
                )
                if body == "CLEAR":
                    payload = b"CLEAR"
                else:
                    payload = f"{title}|{body}|{duration}".encode("utf-8")
                win32file.WriteFile(handle, payload)
                win32file.CloseHandle(handle)
                return True
            except Exception as exc:
                logger.debug("Dynamic Island pipe write failed: %s", exc)

        # 2. Fallback: WinRT toast
        if _WIND_SDK_AVAILABLE and body != "CLEAR":
            self._send_fallback_toast(title, body)
            return True

        return False

    def connect_and_greet(self) -> bool:
        """Verify connection to Dynamic Island named pipe and show a welcome pill."""
        ok = self._send_to_island("🤖 Shin Voice Assistant", "Active & Connected ✦ Ready, MJ!", duration=3.5)
        if ok:
            logger.info("Dynamic Island direct pipe connected (%s)", self.PIPE_NAME)
        else:
            logger.warning("Dynamic Island pipe not found (%s). Fallback toast active.", self.PIPE_NAME)
        return ok

    def show_thinking(self) -> None:
        """Visually indicate that Shin is actively thinking."""
        self.spinner.start()
        now = time.time()
        if now - self._last_send_time > 1.0:
            self._send_to_island("🤖 Shin", "💭 Thinking... ✦", duration=4.0)
            self._last_send_time = now

    def show_speaking(self, text: str) -> None:
        """Stop thinking animation and display the final answer in Dynamic Island."""
        self.spinner.stop()
        if text and len(text.strip()) > 0:
            clean_text = text.strip()
            display_body = clean_text[:110] + "..." if len(clean_text) > 110 else clean_text
            self._send_to_island("🤖 Shin", display_body, duration=5.0)
            self._last_send_time = time.time()

    def show_listening(self) -> None:
        """Indicate that Shin is listening to the user."""
        self.spinner.stop()
        now = time.time()
        if now - self._last_send_time > 2.0:
            self._send_to_island("🎙️ Shin", "[ ılılı. ]", duration=3.0)
            self._last_send_time = now

    def show_idle(self) -> None:
        """Reset state to idle."""
        self.spinner.stop()
        self._send_to_island("Shin", "CLEAR", duration=0.0)

    def show_conversation(self, countdown: float = 6.0) -> None:
        """Indicate an active conversational follow-up window."""
        self.spinner.stop()
        self._send_to_island("💬 Shin", f"Listening... ({int(countdown)}s)", duration=countdown)

    def show_dance(self) -> None:
        """Indicate dance animation."""
        self.spinner.stop()
        self._send_to_island("🎵 Shin", "Dancing! ✨", duration=6.0)

    def show_timemap_due(self, action: str) -> None:
        """Indicate scheduled timemap reminder."""
        self.spinner.stop()
        self._send_to_island("⏰ Scheduled Reminder", action, duration=6.0)

    def show_thought(self, thought: str) -> None:
        """Indicate inner thought cognitive reasoning."""
        self.spinner.stop()
        self._send_to_island("💭 Shin", thought, duration=4.0)

    def _send_fallback_toast(self, title: str, body: str) -> None:
        """Background fallback toast."""
        def _do_send():
            try:
                safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                safe_body = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                xml_str = f"""<toast><visual><binding template="ToastGeneric"><text>{safe_title}</text><text>{safe_body}</text></binding></visual></toast>"""
                xml_doc = win_xml.XmlDocument()
                xml_doc.load_xml(xml_str)
                toast = win_notif.ToastNotification(xml_doc)
                notifier = win_notif.ToastNotificationManager.create_toast_notifier(self.APP_ID)
                notifier.show(toast)
            except Exception:
                pass

        threading.Thread(target=_do_send, daemon=True).start()


def show_thinking() -> None:
    IslandBridge.get().show_thinking()


def show_speaking(text: str) -> None:
    IslandBridge.get().show_speaking(text)


def show_listening() -> None:
    IslandBridge.get().show_listening()


def show_idle() -> None:
    IslandBridge.get().show_idle()


def show_conversation(countdown: float = 6.0) -> None:
    IslandBridge.get().show_conversation(countdown)


def show_dance() -> None:
    IslandBridge.get().show_dance()


def show_timemap_due(action: str) -> None:
    IslandBridge.get().show_timemap_due(action)


def show_thought(thought: str) -> None:
    IslandBridge.get().show_thought(thought)


def connect_and_greet() -> bool:
    return IslandBridge.get().connect_and_greet()

