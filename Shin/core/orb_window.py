"""
orb_window.py — Shin desktop orb overlay (Win32 click-through transparency).

Uses pywebview to create a frameless, always-on-top transparent window that renders orb.html,
and uses Win32 API to dynamically toggle WS_EX_TRANSPARENT click-through style based on cursor position.
"""

import os
import sys
import threading
import time
import ctypes
import ctypes.wintypes
import argparse
import math

# Set WebView2 default background to transparent (ARGB 0x00000000) before initialization
os.environ["WEBVIEW2_DEFAULT_BACKGROUND_COLOR"] = "00000000"

GWL_EXSTYLE       = -20
WS_EX_LAYERED     = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
LWA_COLORKEY      = 0x00000001

# Global references
hwnd = None
api_instance = None


class API:
    def __init__(self):
        self.orb_x = 0
        self.orb_y = 0
        self.orb_radius = 0
        self.is_clickthrough = True

    def update_geometry(self, x, y, r):
        self.orb_x = int(x)
        self.orb_y = int(y)
        self.orb_radius = int(r)


def _find_hwnd(title: str, timeout: float = 10.0):
    """Find the window by title and store it globally."""
    global hwnd
    user32   = ctypes.windll.user32
    deadline = time.time() + timeout

    def get_hwnd():
        h = user32.FindWindowW(None, title)
        if h:
            return h
        h = user32.FindWindowW(None, "Shin - Orb")
        if h:
            return h
        h = user32.FindWindowW(None, "Shin — Orb")
        if h:
            return h
            
        found_hwnd = [0]
        def enum_cb(h_val, extra):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(h_val, buf, 512)
            if "Shin" in buf.value:
                if user32.IsWindowVisible(h_val):
                    found_hwnd[0] = h_val
                    return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        return found_hwnd[0]

    while time.time() < deadline:
        hwnd = get_hwnd()
        if hwnd:
            break
        time.sleep(0.1)

    if not hwnd:
        print(f"[orb_window] WARNING: Could not find window '{title}'", flush=True)
        return

    print(f"[orb_window] Found window HWND={hwnd}. Setting initial click-through style.", flush=True)
    
    # Set initial click-through style (layered + transparent)
    ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027) # SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER

    # Set ColorKey transparency for white background pixels
    try:
        user32.SetLayeredWindowAttributes(hwnd, 0x00FFFFFF, 0, LWA_COLORKEY)
    except Exception as e:
        print(f"[orb_window] SetLayeredWindowAttributes warning: {e}", flush=True)

    # Extend DWM frame into client area to support true transparency
    try:
        class MARGINS(ctypes.Structure):
            _fields_ = [
                ("cxLeftWidth", ctypes.c_int),
                ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int),
                ("cyBottomHeight", ctypes.c_int),
            ]
        margins = MARGINS(-1, -1, -1, -1)
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
        print("[orb_window] DWM frame extended into client area.", flush=True)
    except Exception as e:
        print(f"[orb_window] WARNING: Failed to extend DWM frame: {e}", flush=True)

    # Force the WinForms Form & WebView2 control BackColor to Transparent / Black
    try:
        import webview
        if webview.windows:
            win = webview.windows[0]
            if win.native:
                import clr
                clr.AddReference('System.Drawing')
                from System.Drawing import Color
                win.native.BackColor = Color.Black
                win.native.AllowTransparency = True
                if hasattr(win.native, "Controls"):
                    for ctrl in win.native.Controls:
                        try:
                            ctrl.DefaultBackgroundColor = Color.Transparent
                        except Exception:
                            try:
                                ctrl.DefaultBackgroundColor = Color.FromArgb(0, 0, 0, 0)
                            except Exception:
                                pass
                print("[orb_window] Form & WebView2 BackColor set to Transparent.", flush=True)
    except Exception as e:
        print(f"[orb_window] WARNING: Failed to set Form/WebView2 BackColor: {e}", flush=True)

    print("[orb_window] Initial click-through style applied.", flush=True)


def _mouse_polling_loop():
    """Poll mouse position and toggle WS_EX_TRANSPARENT based on proximity to the orb."""
    global hwnd, api_instance
    user32 = ctypes.windll.user32

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    while True:
        if not hwnd or not api_instance:
            time.sleep(0.1)
            continue

        pt = POINT()
        if user32.GetCursorPos(ctypes.byref(pt)):
            dx = pt.x - api_instance.orb_x
            dy = pt.y - api_instance.orb_y
            dist = math.hypot(dx, dy)

            # Interactive if within radius, click-through otherwise
            is_over = (dist <= api_instance.orb_radius) and (api_instance.orb_radius > 0)

            if is_over and api_instance.is_clickthrough:
                # Disable click-through (make clickable)
                ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, (ex_style | WS_EX_LAYERED) & ~WS_EX_TRANSPARENT)
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
                api_instance.is_clickthrough = False
            elif not is_over and not api_instance.is_clickthrough:
                # Enable click-through
                ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
                api_instance.is_clickthrough = True

        time.sleep(0.04)  # ~25 checks per second


def main():
    global api_instance
    parser = argparse.ArgumentParser(description="Shin Orb Overlay Window")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port of ui_server")
    parser.add_argument("--width", type=int, default=500, help="Initial width")
    parser.add_argument("--height", type=int, default=500, help="Initial height")
    args = parser.parse_args()

    mascot_mode = os.getenv("MASCOT_MODE", "mate").lower()
    html_target = "mate.html" if mascot_mode == "mate" else "orb.html"
    url = f"http://127.0.0.1:{args.port}/{html_target}?platform=overlay"
    print(f"[orb_window] Loading: {url}", flush=True)

    try:
        import webview
    except ImportError:
        print("ERROR: pywebview not installed. Run: pip install pywebview", file=sys.stderr)
        sys.exit(1)

    # Screen size
    user32   = ctypes.windll.user32
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    print(f"[orb_window] Screen: {screen_w}x{screen_h}", flush=True)

    WIN_TITLE = "Shin"
    api_instance = API()

    # Create the window with native transparency enabled
    webview.create_window(
        title=WIN_TITLE,
        url=url,
        transparent=True,            # Native pywebview transparency
        frameless=True,
        on_top=True,
        background_color="#00000000", # ARGB zero transparent background
        width=screen_w,
        height=screen_h,
        x=0,
        y=0,
        resizable=False,
        minimized=False,
        fullscreen=False,
        js_api=api_instance,         # Expose update_geometry API to JavaScript
    )

    t_find = threading.Thread(target=_find_hwnd, args=(WIN_TITLE,), daemon=True)
    t_find.start()

    t_poll = threading.Thread(target=_mouse_polling_loop, daemon=True)
    t_poll.start()

    # Blocks until window is closed
    webview.start(debug=False)


if __name__ == "__main__":
    main()
