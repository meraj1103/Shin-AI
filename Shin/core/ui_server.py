import asyncio
import http.server
import json
import logging
import os
import socketserver
import threading
import websockets

logger = logging.getLogger("shin.ui")

# Global ports (negotiated at runtime if occupied)
HTTP_PORT = 8000
WS_PORT = 8001


def _apply_settings(settings: dict) -> None:
    """
    Write UI settings to the .env file so they persist across restarts.
    Supported keys: tts_backend, asr_backend, wake_word, wake_word_enabled, volume.
    """
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.exists(env_path):
        with open(env_path, "a", encoding="utf-8"):  # create if missing
            pass

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    key_map = {
        "tts_backend":       "TTS_BACKEND",
        "asr_backend":       "ASR_BACKEND",
        "asr_language":      "ASR_LANGUAGE",
        "wake_word":         "WAKE_WORD",
        "wake_word_enabled": "WAKE_WORD_ENABLED",
        "current_model":     "UI_MODEL_FILE",
        "tts_pitch":         "TTS_PITCH",
    }

    for ui_key, env_key in key_map.items():
        if ui_key not in settings:
            continue
        value = str(settings[ui_key])
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{env_key}="):
                lines[i] = f"{env_key}={value}\n"
                found = True
                break
        if not found:
            lines.append(f"{env_key}={value}\n")
        # Hot-reload into the running process so changes take effect immediately
        # without requiring a restart.
        os.environ[env_key] = value

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # Hot-reload voice pitch if specified
    if "tts_pitch" in settings:
        try:
            import assistant
            if hasattr(assistant, "set_voice_pitch"):
                assistant.set_voice_pitch(str(settings["tts_pitch"]))
        except Exception:
            pass

    # Hot-reload volume if specified
    if "volume" in settings:
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            import comtypes
            comtypes.CoInitialize()
            devices = AudioUtilities.GetSpeakers()
            if hasattr(devices, "Activate"):
                interface = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
            else:
                volume = devices.EndpointVolume
            volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, float(settings["volume"]) / 100.0)), None)
        except Exception as exc:
            logger.warning("Settings: volume hot-reload failed: %s", exc)

    logger.info("Settings applied: %s", list(settings.keys()))


def redact_key(key: str) -> str:
    """Helper to redact sensitive API keys for display."""
    if not key:
        return ""
    if len(key) <= 8:
        return "..."
    return f"{key[:4]}...{key[-4:]}"


def _apply_token_keys(openai_key: str | None, gemini_key: str | None) -> None:
    """
    Write API keys to the .env file and update the current process environment variables.
    """
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.exists(env_path):
        with open(env_path, "a", encoding="utf-8"):
            pass

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    updated_keys = {}
    if openai_key is not None:
        updated_keys["OPENAI_API_KEY"] = openai_key.strip()
    if gemini_key is not None:
        updated_keys["GEMINI_API_KEY"] = gemini_key.strip()

    for env_key, value in updated_keys.items():
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{env_key}="):
                lines[i] = f"{env_key}={value}\n"
                found = True
                break
        if not found:
            lines.append(f"{env_key}={value}\n")
            
        os.environ[env_key] = value

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    logger.info("Token keys updated in .env and environment.")


class UIHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve files from the 'ui' subdirectory
        directory = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui")
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        # Suppress heavy logging to console
        logger.debug(format % args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _is_origin_allowed(self) -> bool:
        """Allow only local requests (localhost, 127.0.0.1, or Electron null origin)."""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        origin_lower = origin.lower()
        if origin_lower == "null":
            return True
        from urllib.parse import urlparse
        try:
            parsed = urlparse(origin_lower)
            hostname = (parsed.hostname or "").lower()
            return hostname in ("127.0.0.1", "localhost", "::1")
        except Exception:
            return False

    def _send_cors_headers(self):
        origin = self.headers.get("Origin")
        if origin and self._is_origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
        else:
            self.send_header("Access-Control-Allow-Origin", f"http://127.0.0.1:{HTTP_PORT}")
        self.send_header("X-Content-Type-Options", "nosniff")

    def do_GET(self):
        if not self._is_origin_allowed():
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Forbidden: Cross-origin access denied."}).encode("utf-8"))
            return

        # Endpoint to allow Three.js client to discover the WebSocket server port
        if self.path == "/api/config":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            
            curr_volume = 50
            try:
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                from ctypes import cast, POINTER
                import comtypes
                comtypes.CoInitialize()
                devices = AudioUtilities.GetSpeakers()
                if hasattr(devices, "Activate"):
                    interface = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
                    volume_obj = cast(interface, POINTER(IAudioEndpointVolume))
                else:
                    volume_obj = devices.EndpointVolume
                curr_volume = int(round(volume_obj.GetMasterVolumeLevelScalar() * 100))
            except Exception:
                pass
                
            config_data = {
                "ws_port": WS_PORT,
                "wake_word": os.getenv("WAKE_WORD", "hey shin"),
                "wake_word_enabled": os.getenv("WAKE_WORD_ENABLED", "true"),
                "tts_backend": os.getenv("TTS_BACKEND", "edge"),
                "asr_backend": os.getenv("ASR_BACKEND", "google"),
                "asr_language": os.getenv("ASR_LANGUAGE", "hi-IN"),
                "volume": curr_volume,
            }
            self.wfile.write(json.dumps(config_data).encode("utf-8"))
        elif self.path == "/api/history":
            try:
                import command_log
                entries = command_log.recent_commands(50)
            except Exception:
                entries = []
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(entries).encode("utf-8"))
        elif self.path == "/api/tokens":
            try:
                import token_tracker
                stats = token_tracker.get_usage_stats()
                stats["openai_key_redacted"] = redact_key(os.getenv("OPENAI_API_KEY", ""))
                stats["gemini_key_redacted"] = redact_key(os.getenv("GEMINI_API_KEY", ""))
            except Exception as exc:
                stats = {"error": str(exc)}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode("utf-8"))
        else:
            super().do_GET()

    def do_OPTIONS(self):
        if not self._is_origin_allowed():
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if not self._is_origin_allowed():
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Forbidden: Cross-origin access denied."}).encode("utf-8"))
            return

        if self.path == "/api/settings":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                _apply_settings(body)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            except Exception as exc:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
        elif self.path == "/api/tokens":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                
                openai_key = body.get("openai_key")
                gemini_key = body.get("gemini_key")
                _apply_token_keys(openai_key, gemini_key)
                
                if "monthly_limit_usd" in body:
                    import token_tracker
                    token_tracker.set_monthly_limit(float(body["monthly_limit_usd"]))
                    
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            except Exception as exc:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


UIHttpRequestHandler = UIHTTPHandler


class UIBridge:
    active_clients = set()
    loop = None
    state = "idle"
    orb_visible = True
    lock = threading.Lock()

    @classmethod
    def set_orb_visibility(cls, visible: bool):
        with cls.lock:
            cls.orb_visible = visible
            action = "orb_show" if visible else "orb_hide"
        logger.info("Orb visibility updated: %s", action)
        if cls.loop:
            asyncio.run_coroutine_threadsafe(
                cls._broadcast({"type": action}),
                cls.loop
            )

    @classmethod
    def register(cls, ws):
        with cls.lock:
            cls.active_clients.add(ws)
            logger.debug("Registered new WebSocket client. Active count: %d", len(cls.active_clients))

    @classmethod
    def unregister(cls, ws):
        with cls.lock:
            cls.active_clients.discard(ws)
            logger.debug("Unregistered WebSocket client. Active count: %d", len(cls.active_clients))

    @classmethod
    async def _broadcast(cls, data):
        if not cls.active_clients:
            return
        message = json.dumps(data)
        # Gather all send operations to run in parallel
        await asyncio.gather(
            *[client.send(message) for client in cls.active_clients],
            return_exceptions=True
        )

    @classmethod
    def send_state(cls, new_state: str):
        with cls.lock:
            cls.state = new_state
        logger.info("Shin state changed to: %s", new_state)
        # Notify Dynamic Island & trigger live visual thinking indicator
        try:
            from Shin.core import island_bridge
            if new_state == "processing":
                island_bridge.show_thinking()
            elif new_state == "listening":
                island_bridge.show_listening()
            elif new_state == "idle":
                island_bridge.show_idle()
            elif new_state == "conversation":
                island_bridge.show_conversation()
            elif new_state == "dance":
                island_bridge.show_dance()
        except Exception:
            pass

        # Notify Mate Engine 3D Avatar
        try:
            from Shin.core import mate_bridge
            mate_bridge.MateBridge.get().set_state(new_state)
        except Exception:
            pass

        if cls.loop:
            asyncio.run_coroutine_threadsafe(
                cls._broadcast({"type": "state", "state": new_state}),
                cls.loop
            )

    @classmethod
    def send_transcript(cls, heard: str, response: str):
        """Broadcast the latest command + response for the live transcript panel."""
        if cls.loop:
            asyncio.run_coroutine_threadsafe(
                cls._broadcast({"type": "transcript", "heard": heard, "response": response}),
                cls.loop,
            )

    @classmethod
    def send_now_playing(cls, track: str, artist: str, art_url: str = ""):
        """Broadcast now-playing metadata for the media widget."""
        if cls.loop:
            asyncio.run_coroutine_threadsafe(
                cls._broadcast(
                    {"type": "now_playing", "track": track, "artist": artist, "art": art_url}
                ),
                cls.loop,
            )

    @classmethod
    def send_media_clear(cls):
        """Hide the now-playing widget."""
        if cls.loop:
            asyncio.run_coroutine_threadsafe(
                cls._broadcast({"type": "media_clear"}),
                cls.loop,
            )

    @classmethod
    def send_history_entry(cls, entry: dict):
        """Broadcast a single command history entry to the UI."""
        if cls.loop:
            asyncio.run_coroutine_threadsafe(
                cls._broadcast({"type": "history", "entry": entry}),
                cls.loop,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Desktop Overlay Window (orb_window subprocess)
# ═══════════════════════════════════════════════════════════════════════════════

_orb_process = None
_orb_log_file = None  # kept so we can close it cleanly on shutdown


def launch_orb_window():
    """
    Launch Electron-based orb window overlay as a subprocess.
    On Windows, it uses a lightweight pywebview implementation.
    On other platforms, it falls back to Electron.
    """
    import subprocess
    import sys
    import time

    # Wait for the HTTP server to bind
    time.sleep(0.8)

    global _orb_process, _orb_log_file

    # Prefer native pywebview/Win32 implementation on Windows for performance
    if sys.platform == "win32":
        orb_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orb_window.py")
        python_exe = sys.executable.replace("python.exe", "pythonw.exe")
        cmd = [python_exe, orb_script_path, "--port", str(HTTP_PORT)]
        use_shell = False
    else: # Fallback to Electron for other platforms (macOS, Linux)
        electron_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orb-electron")
        node_modules_path = os.path.join(electron_dir, "node_modules")
        local_electron = os.path.join(node_modules_path, "electron", "dist", "electron.exe")
        use_shell = False
        if os.path.isfile(local_electron):
            cmd = [local_electron, ".", "--port", str(HTTP_PORT)]
        else:
            cmd = ["npx", "electron", ".", "--port", str(HTTP_PORT)]
            if sys.platform == "win32": # npx needs shell on windows
                use_shell = True
    
    try:
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "orb_window.log")
        log_file = open(log_path, "w", encoding="utf-8")
        _orb_log_file = log_file  # store reference so stop_ui_server can close it
        _orb_process = subprocess.Popen(
            cmd,
            cwd=os.path.dirname(cmd[0]) if not use_shell else electron_dir,
            stdout=log_file,
            stderr=log_file,
            shell=use_shell,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        logger.info("Orb overlay process started (PID: %d), logging to: %s", _orb_process.pid, log_path)
    except Exception as exc:
        logger.error("Failed to launch orb overlay: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════════
# Server Execution Threads
# ═══════════════════════════════════════════════════════════════════════════════

class SilentTCPServer(socketserver.TCPServer):
    def handle_error(self, request, client_address):
        import sys
        exctype, value, tb = sys.exc_info()
        if exctype is not None and issubclass(exctype, (ConnectionResetError, ConnectionAbortedError)):
            logger.debug("Client disconnected abruptly from %s: %s", client_address, value)
            return
        super().handle_error(request, client_address)


_MAX_PORT_RETRIES = 10


def run_http_server():
    global HTTP_PORT
    retries = 0
    while retries < _MAX_PORT_RETRIES:
        try:
            handler = UIHTTPHandler
            # Allow address reuse to recover from sudden restarts
            SilentTCPServer.allow_reuse_address = True
            with SilentTCPServer(("127.0.0.1", HTTP_PORT), handler) as httpd:
                logger.info("HTTP Server started at http://127.0.0.1:%d", HTTP_PORT)
                httpd.serve_forever()
        except OSError:
            logger.warning("HTTP port %d is occupied. Trying %d...", HTTP_PORT, HTTP_PORT + 1)
            HTTP_PORT += 1
            retries += 1
    logger.error("HTTP server could not bind after %d attempts. Giving up.", _MAX_PORT_RETRIES)


async def ws_handler(websocket):
    UIBridge.register(websocket)
    # Stream active state immediately to new client
    await websocket.send(json.dumps({"type": "state", "state": UIBridge.state}))
    # Sync initial orb visibility state
    initial_action = "orb_show" if UIBridge.orb_visible else "orb_hide"
    await websocket.send(json.dumps({"type": initial_action}))
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("type") == "orb_hidden_by_user":
                    with UIBridge.lock:
                        UIBridge.orb_visible = False
                    logger.info("Orb hidden by user.")
                elif data.get("type") == "orb_shown_by_user":
                    with UIBridge.lock:
                        UIBridge.orb_visible = True
                    logger.info("Orb shown by user.")
            except Exception:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        UIBridge.unregister(websocket)


def run_ws_server():
    global WS_PORT
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    UIBridge.loop = loop

    async def main_ws():
        async with websockets.serve(ws_handler, "127.0.0.1", WS_PORT) as server:
            logger.info("WebSocket Server started at ws://127.0.0.1:%d", WS_PORT)
            await asyncio.Future()

    retries = 0
    while retries < _MAX_PORT_RETRIES:
        try:
            loop.run_until_complete(main_ws())
        except OSError:
            logger.warning("WebSocket port %d is occupied. Trying %d...", WS_PORT, WS_PORT + 1)
            WS_PORT += 1
            retries += 1
    logger.error("WebSocket server could not bind after %d attempts. Giving up.", _MAX_PORT_RETRIES)


def start_ui_server():
    """Start the HTTP + WebSocket servers, then spawn the orb overlay subprocess."""
    # 1. Start HTTP server
    http_thread = threading.Thread(target=run_http_server, daemon=True, name="UI_HTTP_Server")
    http_thread.start()

    # 2. Start WebSocket server
    ws_thread = threading.Thread(target=run_ws_server, daemon=True, name="UI_WS_Server")
    ws_thread.start()

    # 3. Launch orb overlay as a separate process (needs its own main thread for pywebview)
    orb_thread = threading.Thread(target=launch_orb_window, daemon=True, name="Orb_Overlay_Launcher")
    orb_thread.start()


def stop_ui_server():
    """Terminate the orb overlay subprocess and clean up resources on shutdown."""
    global _orb_process, _orb_log_file
    if _orb_process is not None:
        try:
            logger.info("Terminating orb overlay process (PID: %d)...", _orb_process.pid)
            # Try killing process tree recursively using psutil
            try:
                import psutil
                parent = psutil.Process(_orb_process.pid)
                for child in parent.children(recursive=True):
                    try:
                        child.kill()
                    except Exception:
                        pass
                parent.kill()
            except Exception as e:
                logger.debug("psutil process tree kill failed: %s", e)
                # Fallback to standard terminate/kill or taskkill
                try:
                    if os.name == "nt":
                        import subprocess
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(_orb_process.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        _orb_process.terminate()
                except Exception:
                    try:
                        _orb_process.kill()
                    except Exception:
                        pass
            
            _orb_process.wait(timeout=3)
        except Exception as exc:
            logger.warning("Orb process cleanup failed: %s", exc)
        _orb_process = None

    # Perform a sweep for any remaining orphaned Electron/Orb processes to be 100% sure the screen is clean
    if os.name == "nt":
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cwd', 'cmdline']):
                try:
                    cwd = proc.info.get('cwd')
                    cmdline = proc.info.get('cmdline')
                    name = proc.info.get('name') or ""
                    
                    is_orb = False
                    if cwd and "orb-electron" in cwd:
                        is_orb = True
                    elif cmdline and any("orb-electron" in arg for arg in cmdline):
                        is_orb = True
                        
                    if is_orb:
                        logger.info("Killing orphaned orb process: PID %d (%r)", proc.info['pid'], name)
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.debug("Sweep of orphaned orb processes failed: %s", e)

    # Close the log file handle that was kept open for the subprocess
    if _orb_log_file is not None:
        try:
            _orb_log_file.close()
        except Exception:
            pass
        _orb_log_file = None
