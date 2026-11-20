import threading
import time
import logging
from collections import deque
import pyperclip

logger = logging.getLogger("shin.clipboard")

# Store up to 10 recent clipboard items
_HISTORY = deque(maxlen=10)
_history_lock = threading.Lock()
_last_content = ""

def _monitor_loop():
    global _last_content
    while True:
        try:
            current = pyperclip.paste()
            if current and current.strip() and current != _last_content:
                with _history_lock:
                    # Avoid consecutive duplicates
                    if not _HISTORY or _HISTORY[0] != current:
                        _HISTORY.appendleft(current)
                _last_content = current
        except Exception as exc:
            logger.debug("Clipboard read error: %s", exc)
        time.sleep(1.0)

def start_monitoring():
    t = threading.Thread(target=_monitor_loop, daemon=True)
    t.start()
    logger.info("Clipboard history monitor started.")

def get_history(index: int = 1) -> str | None:
    """Get the Nth most recent clipboard item (1-based index)."""
    with _history_lock:
        if not _HISTORY:
            return None
        # Adjust index to be 0-based
        idx = max(0, min(index - 1, len(_HISTORY) - 1))
        return _HISTORY[idx]