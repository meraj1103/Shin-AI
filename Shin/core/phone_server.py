"""
phone_server.py — Shin Mobile Companion API
============================================
A lightweight Flask server that lets you control Shin from your phone browser.

Security features
-----------------
  • PIN authentication  → 4-digit PIN set in .env (PHONE_PIN)
  • Session tokens      → 256-bit random token per login, stored in memory
  • Brute-force lockout → 5 failed attempts → 15-minute lockout per IP
  • Rate limiting       → 60 req/min per IP, 10 req/min for /auth
  • Token expiry        → sessions expire after 12 hours of inactivity
  • CORS               → allow * (needed for public tunnel URLs)
  • No sensitive data   → API keys / env vars are never exposed

Endpoints
---------
  POST /auth           Login with PIN → {"ok": true, "token": "..."}
  GET  /status         Shin state     → {"state": "idle", "ok": true}
  POST /command        Send command   → {"ok": true, "response": "..."}
  GET  /transcript     Last 30 items  → {"ok": true, "history": [...]}
  GET  /stream         SSE live feed  (requires ?token=...)
  POST /logout         Invalidate token
  GET  /ping           Health check   (no auth required)
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import queue
import secrets
import threading
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger("shin.phone")

# ── Configuration (read from .env via os.getenv) ──────────────────────────────
PHONE_PORT           = int(os.getenv("PHONE_PORT", "5055"))
PHONE_TUNNEL_ENABLED = os.getenv("PHONE_TUNNEL_ENABLED", "true").lower() in ("true", "1", "yes")
PHONE_PIN_HASH       = ""          # computed at startup from PHONE_PIN
SESSION_TTL    = 12 * 3600  # 12 hours in seconds
MAX_HISTORY    = 50          # max transcript entries to keep

# ── Security state ────────────────────────────────────────────────────────────
_sessions:       dict[str, float] = {}       # token → last_access timestamp
_failed_attempts: dict[str, list] = {}       # ip → [timestamp, ...]
_rate_counters:   dict[str, list] = {}       # ip → [timestamp, ...]
_lock = threading.Lock()

LOCKOUT_THRESHOLD = 5       # failed attempts before lockout
LOCKOUT_WINDOW    = 900     # 15 minutes lockout (seconds)
RATE_WINDOW       = 60      # seconds
RATE_LIMIT_GENERAL = 60     # max requests per RATE_WINDOW
RATE_LIMIT_AUTH    = 10     # max auth attempts per RATE_WINDOW

# ── Transcript / SSE ──────────────────────────────────────────────────────────
_transcript: list[dict] = []
_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()

# ── Callback: set by assistant.py so phone commands trigger Shin ──────────────
_command_callback = None   # Callable[[str], str]


def set_command_callback(cb) -> None:
    """Register the function to call when the phone sends a command."""
    global _command_callback
    _command_callback = cb


def push_transcript(heard: str, response: str) -> None:
    """Called by assistant.py whenever Shin speaks, to update phone clients."""
    entry = {
        "ts":       datetime.now().strftime("%H:%M:%S"),
        "heard":    heard,
        "response": response,
    }
    with _sse_lock:
        _transcript.append(entry)
        if len(_transcript) > MAX_HISTORY:
            _transcript.pop(0)
        # Push to all live SSE connections
        for q in _sse_clients:
            try:
                q.put_nowait(json.dumps({"type": "transcript", **entry}))
            except queue.Full:
                pass


def push_state(state: str) -> None:
    """Called by assistant.py on state change (idle/listening/speaking/etc.)."""
    event = json.dumps({"type": "state", "state": state})
    with _sse_lock:
        for q in _sse_clients:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass


def push_notification(title: str, message: str) -> None:
    """Broadcast a push notification event to all connected phone clients."""
    event = json.dumps({"type": "notification", "title": title, "message": message})
    with _sse_lock:
        for q in _sse_clients:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass


# ══════════════════════════════════════════════════════════════════════════════
# Security helpers
# ══════════════════════════════════════════════════════════════════════════════

def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.strip().encode()).hexdigest()


def _get_pin_hash() -> str:
    """Lazily read (or default) the PIN from environment."""
    raw = os.getenv("PHONE_PIN", "2442").strip()
    return _hash_pin(raw)


def _client_ip(request) -> str:
    """Get real client IP, only trusting X-Forwarded-For if request came from local reverse proxy."""
    remote = request.remote_addr or "unknown"
    if remote in ("127.0.0.1", "::1", "localhost"):
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            candidate = xff.split(",")[0].strip()
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                pass
    return remote


def _is_locked_out(ip: str) -> bool:
    """Return True if this IP has too many recent failed attempts."""
    with _lock:
        attempts = _failed_attempts.get(ip, [])
        now = time.time()
        recent = [t for t in attempts if now - t < LOCKOUT_WINDOW]
        _failed_attempts[ip] = recent
        return len(recent) >= LOCKOUT_THRESHOLD


def _record_failure(ip: str) -> int:
    """Record a failed login attempt. Return remaining attempts before lockout."""
    with _lock:
        now = time.time()
        attempts = _failed_attempts.get(ip, [])
        attempts = [t for t in attempts if now - t < LOCKOUT_WINDOW]
        attempts.append(now)
        _failed_attempts[ip] = attempts
        return max(0, LOCKOUT_THRESHOLD - len(attempts))


def _clear_failures(ip: str) -> None:
    with _lock:
        _failed_attempts.pop(ip, None)


def _is_rate_limited(ip: str, limit: int = RATE_LIMIT_GENERAL) -> bool:
    """Sliding-window rate limiter. Returns True if limit exceeded."""
    with _lock:
        now = time.time()
        counts = _rate_counters.get(ip, [])
        counts = [t for t in counts if now - t < RATE_WINDOW]
        if len(counts) >= limit:
            _rate_counters[ip] = counts
            return True
        counts.append(now)
        _rate_counters[ip] = counts
        return False


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _create_session() -> str:
    token = _new_token()
    with _lock:
        _sessions[token] = time.time()
    return token


def _validate_token(token: str) -> bool:
    """Check token exists and refresh its TTL if valid."""
    if not token:
        return False
    with _lock:
        ts = _sessions.get(token)
        if ts is None:
            return False
        if time.time() - ts > SESSION_TTL:
            del _sessions[token]
            return False
        _sessions[token] = time.time()   # refresh TTL
        return True


def _revoke_token(token: str) -> None:
    with _lock:
        _sessions.pop(token, None)


def _cleanup_sessions() -> None:
    """Background thread: prune expired sessions every 10 minutes."""
    while True:
        time.sleep(600)
        now = time.time()
        with _lock:
            expired = [t for t, ts in _sessions.items() if now - ts > SESSION_TTL]
            for t in expired:
                del _sessions[t]
        if expired:
            logger.debug("Phone server: pruned %d expired session(s).", len(expired))


# ══════════════════════════════════════════════════════════════════════════════
# Flask app
# ══════════════════════════════════════════════════════════════════════════════

def _create_app():
    from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory

    app = Flask(__name__)

    # Redirect root to phone companion UI
    @app.route("/")
    def root_redirect():
        from flask import redirect
        return redirect("/phone/")

    # Serve the mobile web app static files
    @app.route("/phone/")
    @app.route("/phone/<path:path>")
    def serve_phone_ui(path="index.html"):
        ui_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "phone")
        if not path:
            path = "index.html"
        return send_from_directory(ui_dir, path)

    # ── /qr  (QR code for local URL — no internet required) ───────────────────
    @app.route("/qr")
    @app.route("/qr.png")
    def qr_code():
        """Return a PNG QR code for the local Wi-Fi URL so phones can scan it."""
        url_to_encode = _local_url or f"http://127.0.0.1:{PHONE_PORT}/phone/"
        try:
            import qrcode
            import io
            from flask import send_file
            img = qrcode.make(url_to_encode)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            return send_file(buf, mimetype="image/png")
        except ImportError:
            # Fallback: redirect to a QR-code-as-a-service if qrcode package missing
            from flask import redirect
            import urllib.parse
            encoded = urllib.parse.quote(url_to_encode, safe="")
            return redirect(f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded}")

    # ── /link  (plain text links — local access only) ─────────────────────────
    @app.route("/link")
    def link_info():
        """Return a simple HTML page with access links and QR code (local PC access only)."""
        client_addr = request.remote_addr or ""
        if client_addr not in ("127.0.0.1", "::1", "localhost"):
            logger.warning("Blocked remote access attempt to /link from %s", client_addr)
            from flask import jsonify
            return jsonify({"ok": False, "error": "Access denied. PIN link is only accessible directly from the host PC."}), 403

        local = _local_url or "(not available)"
        tunnel = (f"{_tunnel_url}/phone/") if _tunnel_url else "(tunnel not connected)"
        pin = os.getenv("PHONE_PIN", "2442")
        html = f"""
        <!DOCTYPE html><html><head><meta charset=utf-8>
        <meta name=viewport content="width=device-width,initial-scale=1">
        <title>Shin Access Links</title>
        <style>
          body{{font-family:system-ui,sans-serif;max-width:480px;margin:40px auto;padding:16px;background:#0d0d0d;color:#e0e0e0}}
          h1{{color:#00ffcc;font-size:1.4rem;margin-bottom:4px}}
          .card{{background:#1a1a2e;border-radius:12px;padding:16px;margin:12px 0;border:1px solid #333}}
          .label{{color:#888;font-size:0.8rem;text-transform:uppercase;letter-spacing:1px}}
          .url{{color:#00ffcc;word-break:break-all;font-size:0.95rem;margin-top:4px}}
          .pin{{color:#ffd700;font-size:2rem;font-weight:700;letter-spacing:8px;text-align:center;padding:8px 0}}
          img{{display:block;margin:16px auto;border-radius:8px;border:4px solid #00ffcc}}
          .note{{color:#666;font-size:0.8rem;margin-top:8px}}
        </style></head><body>
        <h1>🤖 Shin Access Links</h1>
        <div class=card><div class=label>Local Wi-Fi (same network)</div>
          <div class=url><a href="{local}" style="color:#00ffcc">{local}</a></div></div>
        <div class=card><div class=label>Public Tunnel (internet)</div>
          <div class=url>{tunnel}</div></div>
        <div class=card><div class=label>PIN</div>
          <div class=pin>{pin}</div></div>
        <div class=card><div class=label>Scan QR (local Wi-Fi)</div>
          <img src="/qr" width=200 height=200 alt="QR code">
          <div class=note>Scan this with your phone camera to open Shin. Must be on same Wi-Fi.</div>
        </div>
        </body></html>"""
        from flask import Response as _Resp
        return _Resp(html, mimetype="text/html")

    # ── CORS headers on every response ────────────────────────────────────────
    @app.after_request
    def _add_cors(response):
        origin = request.headers.get("Origin", "")
        # Allow requests from same origin, local network, or tunnel domain
        if not origin or "127.0.0.1" in origin or "localhost" in origin or (_tunnel_url and _tunnel_url in origin):
            response.headers["Access-Control-Allow-Origin"] = origin or "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Auth-Token"
        return response

    @app.route("/", methods=["OPTIONS"])
    @app.route("/<path:p>", methods=["OPTIONS"])
    def _options(p=""):
        return "", 204

    # ── Auth helper ───────────────────────────────────────────────────────────
    def _require_auth():
        """Return (token, None) if authorised, or (None, error_response)."""
        token = (
            request.headers.get("X-Auth-Token")
            or request.args.get("token")
            or (request.json or {}).get("token") if request.is_json else None
        )
        if not _validate_token(token):
            return None, (jsonify({"ok": False, "error": "Unauthorised. Please log in."}), 401)
        return token, None

    # ── /ping  (public, no auth) ───────────────────────────────────────────────
    @app.route("/ping")
    def ping():
        return jsonify({"ok": True, "msg": "Shin is online 🤖"})

    # ── /auth  (login) ────────────────────────────────────────────────────────
    @app.route("/auth", methods=["POST"])
    def auth():
        ip = _client_ip(request)

        # Rate-limit auth endpoint tighter
        if _is_rate_limited(ip, RATE_LIMIT_AUTH):
            logger.warning("Phone auth: rate-limited %s", ip)
            return jsonify({"ok": False, "error": "Too many requests. Wait a minute."}), 429

        if _is_locked_out(ip):
            logger.warning("Phone auth: locked-out %s", ip)
            return jsonify({
                "ok":    False,
                "error": "Too many failed attempts. Try again in 15 minutes.",
            }), 403

        data = request.get_json(silent=True) or {}
        pin  = str(data.get("pin", "")).strip()

        if not hmac.compare_digest(_hash_pin(pin), _get_pin_hash()):
            remaining = _record_failure(ip)
            logger.warning("Phone auth: wrong PIN from %s (%d attempts remaining)", ip, remaining)
            if remaining == 0:
                return jsonify({
                    "ok":    False,
                    "error": "Account locked for 15 minutes due to too many failed attempts.",
                }), 403
            return jsonify({
                "ok":    False,
                "error": f"Wrong PIN. {remaining} attempt(s) remaining before lockout.",
            }), 401

        _clear_failures(ip)
        token = _create_session()
        logger.info("Phone auth: successful login from %s", ip)
        return jsonify({"ok": True, "token": token})

    # ── /logout ───────────────────────────────────────────────────────────────
    @app.route("/logout", methods=["POST"])
    def logout():
        token, err = _require_auth()
        if err:
            return err
        _revoke_token(token)
        return jsonify({"ok": True})

    # ── /status ───────────────────────────────────────────────────────────────
    @app.route("/status")
    def status():
        ip = _client_ip(request)
        if _is_rate_limited(ip):
            return jsonify({"ok": False, "error": "Rate limit exceeded."}), 429
        _, err = _require_auth()
        if err:
            return err
        try:
            import ui_server
            state = ui_server.UIBridge.state
        except Exception:
            state = "unknown"
        return jsonify({"ok": True, "state": state})

    # ── /command ──────────────────────────────────────────────────────────────
    @app.route("/command", methods=["POST"])
    def command():
        ip = _client_ip(request)
        if _is_rate_limited(ip):
            return jsonify({"ok": False, "error": "Rate limit exceeded."}), 429
        _, err = _require_auth()
        if err:
            return err

        data = request.get_json(silent=True) or {}
        text = str(data.get("text", "")).strip()
        if not text:
            return jsonify({"ok": False, "error": "No command text provided."}), 400
        if len(text) > 500:
            return jsonify({"ok": False, "error": "Command too long (max 500 chars)."}), 400

        # CaMeL Defense Shield: Sanitize input from phone companion & block prompt injection
        try:
            import security_shield
            sanitized_text, injection_detected = security_shield.sanitize_untrusted_input(text, source="phone_companion")
            if injection_detected:
                logger.warning("Prompt injection detected in phone command from %s: %s", ip, text)
                return jsonify({"ok": False, "error": "Security Shield: Blocked malicious prompt injection directive."}), 403

            # Pre-check parsed intent for dangerous / destructive commands under Zero-Trust
            import nlp as _nlp
            parsed = _nlp.parse_intent(sanitized_text)
            intent_name = parsed.get("intent", "unknown")
            is_safe, reason = security_shield.is_safe_action_plan(intent_name, parsed.get("args", {}), triggered_by_untrusted=True)
            if not is_safe:
                logger.warning("Blocked dangerous phone command '%s' (intent: %s): %s", text, intent_name, reason)
                return jsonify({"ok": False, "error": f"Security Shield: {reason}"}), 403
            text = sanitized_text
        except Exception as sec_exc:
            logger.debug("Phone command security check notice: %s", sec_exc)

        logger.info("Phone command from %s: %r", ip, text)

        if _command_callback is None:
            return jsonify({"ok": False, "error": "Shin command handler not ready yet."}), 503

        # Run the command in Shin's dispatch pipeline and capture the spoken response
        result_holder: list = []
        exc_holder:    list = []

        def _run():
            try:
                result_holder.append(_command_callback(text))
            except Exception as exc:
                exc_holder.append(str(exc))

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=30)

        if exc_holder:
            return jsonify({"ok": False, "error": exc_holder[0]}), 500
        if not result_holder:
            return jsonify({"ok": False, "error": "Command timed out."}), 504

        response_text = result_holder[0] or ""
        push_transcript(text, response_text)
        return jsonify({"ok": True, "response": response_text})

    # ── /transcript ───────────────────────────────────────────────────────────
    @app.route("/transcript")
    def transcript():
        ip = _client_ip(request)
        if _is_rate_limited(ip):
            return jsonify({"ok": False, "error": "Rate limit exceeded."}), 429
        _, err = _require_auth()
        if err:
            return err
        with _sse_lock:
            history = list(_transcript[-30:])
        return jsonify({"ok": True, "history": history})

    # ── /stream  (Server-Sent Events — live feed) ─────────────────────────────
    @app.route("/stream")
    def stream():
        token = request.args.get("token", "")
        if not _validate_token(token):
            return jsonify({"ok": False, "error": "Unauthorised."}), 401

        client_q: queue.Queue = queue.Queue(maxsize=50)
        with _sse_lock:
            _sse_clients.append(client_q)

        @stream_with_context
        def _generate():
            try:
                # Send initial ping
                yield "data: " + json.dumps({"type": "connected"}) + "\n\n"
                while True:
                    try:
                        event = client_q.get(timeout=25)
                        yield f"data: {event}\n\n"
                    except queue.Empty:
                        # Heartbeat to keep connection alive
                        yield "data: " + json.dumps({"type": "ping"}) + "\n\n"
            except GeneratorExit:
                pass
            finally:
                with _sse_lock:
                    try:
                        _sse_clients.remove(client_q)
                    except ValueError:
                        pass

        return Response(
            _generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control":   "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return app

app = _create_app()


# ══════════════════════════════════════════════════════════════════════════════
# Start / Stop
# ══════════════════════════════════════════════════════════════════════════════

_server_thread: Optional[threading.Thread] = None
_tunnel_process: Optional[subprocess.Popen] = None
_tunnel_url: Optional[str] = None
_local_url: Optional[str] = None
_speak_callback = None

# File that stores the last URL we successfully sent, to avoid re-sending on every restart
_LAST_SENT_URL_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", ".last_wa_sent_url")


def get_local_ip() -> str:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def get_tunnel_url() -> Optional[str]:
    """Return the active Cloudflare tunnel URL, if any."""
    global _tunnel_url
    return f"{_tunnel_url}/phone/" if _tunnel_url else None


def get_local_url() -> Optional[str]:
    """Return the active local Wi-Fi connection URL."""
    global _local_url
    return _local_url


def _read_last_sent_url() -> str:
    """Return the URL string that was last successfully sent via WhatsApp, or empty string."""
    try:
        if os.path.exists(_LAST_SENT_URL_FILE):
            with open(_LAST_SENT_URL_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def _write_last_sent_url(url: str) -> None:
    """Persist the URL that was just sent successfully."""
    try:
        os.makedirs(os.path.dirname(_LAST_SENT_URL_FILE), exist_ok=True)
        with open(_LAST_SENT_URL_FILE, "w", encoding="utf-8") as f:
            f.write(url)
    except Exception as e:
        logger.debug("Failed to write last-sent-URL cache: %s", e)


def send_links_via_whatsapp() -> None:
    """Send both local and tunnel URLs to the user via WhatsApp automation.
    
    Only sends if SEND_WHATSAPP_LINK=true in .env and the tunnel URL has changed.
    """
    if not os.getenv("SEND_WHATSAPP_LINK", "false").lower() in ("true", "1", "yes"):
        logger.debug("WhatsApp automated link send skipped (set SEND_WHATSAPP_LINK=true in .env to enable).")
        return

    global _tunnel_url, _local_url
    if not _local_url and not _tunnel_url:
        return

    # --- De-duplication: skip if URL hasn't changed since last send ---
    current_tunnel = _tunnel_url or ""
    last_sent = _read_last_sent_url()
    if current_tunnel and current_tunnel == last_sent:
        logger.info("WhatsApp link skipped — tunnel URL unchanged since last send (%s).", current_tunnel)
        return

    import json
    import time
    from urllib.parse import quote
    import pyautogui

    core_dir = os.path.dirname(os.path.abspath(__file__))
    contacts_file = os.path.join(os.path.dirname(core_dir), "data", "whatsapp_contacts.json")
    if not os.path.exists(contacts_file):
        logger.warning("WhatsApp contacts file not found at %s", contacts_file)
        return

    try:
        with open(contacts_file, "r", encoding="utf-8") as f:
            contacts = json.load(f)
    except Exception as e:
        logger.warning("Failed to load WhatsApp contacts: %s", e)
        return

    # Find the user's phone number
    phone = contacts.get("mj") or contacts.get("me") or contacts.get("self")
    if not phone:
        logger.warning("User 'mj' contact not found in whatsapp_contacts.json. Cannot send WhatsApp link.")
        return

    phone_digits = "".join(c for c in phone if c.isdigit())
    
    # Construct the message
    msg_lines = ["🤖 Shin Companion Server is online!"]
    if _local_url:
        msg_lines.append(f"📱 Local Wi-Fi Link: {_local_url}")
    if _tunnel_url:
        msg_lines.append(f"🌐 Public Tunnel Link: {_tunnel_url}/phone/")
    
    # Get PIN from env
    pin = os.getenv("PHONE_PIN", "2442")
    msg_lines.append(f"🔑 PIN: {pin}")
    
    message = "\n\n".join(msg_lines)

    logger.info("Sending companion links to 'mj' via WhatsApp...")
    try:
        # Open WhatsApp link
        os.startfile(f"whatsapp://send?phone={phone_digits}&text={quote(message)}")
        
        # Smart wait: poll for the WhatsApp window to actually appear
        # instead of a fixed sleep. On cold boot WhatsApp can take 15-30+ seconds.
        import ctypes
        user32 = ctypes.windll.user32

        def _find_whatsapp_window() -> bool:
            """Check if a WhatsApp window is open and in the foreground."""
            try:
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    buf = ctypes.create_unicode_buffer(512)
                    user32.GetWindowTextW(hwnd, buf, 512)
                    title = buf.value.lower()
                    if "whatsapp" in title:
                        return True
            except Exception:
                pass
            return False

        MAX_WAIT_SECONDS = 45  # max time to wait for WhatsApp to load
        POLL_INTERVAL = 1.0
        elapsed = 0.0
        whatsapp_ready = False

        logger.info("Waiting for WhatsApp window to appear (max %ds)...", MAX_WAIT_SECONDS)
        while elapsed < MAX_WAIT_SECONDS:
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            if _find_whatsapp_window():
                # Window found — give UI a few more seconds to fully render the chat
                logger.info("WhatsApp window detected after %.0fs. Waiting for UI to stabilize...", elapsed)
                time.sleep(3)
                whatsapp_ready = True
                break

        if not whatsapp_ready:
            # WhatsApp might not have been running — try relaunching the deep link once
            logger.warning(
                "WhatsApp window did not appear within %ds. Retrying deep link launch...",
                MAX_WAIT_SECONDS,
            )
            try:
                os.startfile(f"whatsapp://send?phone={phone_digits}&text={quote(message)}")
            except Exception:
                pass
            # Give it up to 30 more seconds on the retry
            RETRY_WAIT = 30
            elapsed = 0.0
            while elapsed < RETRY_WAIT:
                time.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
                if _find_whatsapp_window():
                    logger.info("WhatsApp window detected on retry after %.0fs.", elapsed)
                    time.sleep(3)
                    whatsapp_ready = True
                    break

        if not whatsapp_ready:
            logger.warning("WhatsApp window did not appear after retry. Aborting send.")
            return


        def _get_whatsapp_hwnd() -> int | None:
            """Return the HWND of any open WhatsApp window, or None."""
            found = []

            def _cb(hwnd, _):
                if not user32.IsWindowVisible(hwnd):
                    return True
                buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, buf, 512)
                if "whatsapp" in buf.value.lower():
                    found.append(hwnd)
                return True

            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            user32.EnumWindows(EnumWindowsProc(_cb), 0)
            return found[0] if found else None

        def _focus_whatsapp() -> bool:
            """Bring WhatsApp to foreground. Returns True if successful."""
            hwnd = _get_whatsapp_hwnd()
            if not hwnd:
                return False
            try:
                # Restore if minimised
                SW_RESTORE = 9
                user32.ShowWindow(hwnd, SW_RESTORE)
                time.sleep(0.3)
                # Force foreground
                user32.SetForegroundWindow(hwnd)
                time.sleep(0.5)
                # Verify focus
                return user32.GetForegroundWindow() == hwnd
            except Exception:
                return False

        # Press Enter to send — actively refocus WhatsApp first
        if _get_whatsapp_hwnd():
            if _focus_whatsapp():
                time.sleep(0.3)   # brief pause after focus switch
                pyautogui.press("enter")
                logger.info("WhatsApp: Enter sent successfully.")
            else:
                logger.warning("WhatsApp: could not bring window to foreground. Aborting.")
                return
        else:
            logger.warning("WhatsApp lost focus before Enter could be pressed. Aborting.")
            return

        
        # Wait a moment for the message to send
        time.sleep(2)
        
        # Close the WhatsApp window (Alt+F4)
        if _find_whatsapp_window():
            pyautogui.hotkey("alt", "f4")
        logger.info("WhatsApp companion links sent successfully and window closed.")

        # Persist the sent URL so we don't re-send on the next restart
        _write_last_sent_url(current_tunnel)

    except Exception as e:
        logger.error("Failed to send WhatsApp companion links: %s", e)


def _start_tunnel_in_background() -> None:
    """Start cloudflared in a background thread to find the URL without blocking Flask start."""
    global _tunnel_process, _tunnel_url, _speak_callback

    if not PHONE_TUNNEL_ENABLED:
        logger.info("Cloudflare tunnel disabled via PHONE_TUNNEL_ENABLED=false. Phone server is local Wi-Fi only.")
        return
    import subprocess
    import sys
    import re
    import pyperclip

    core_dir = os.path.dirname(os.path.abspath(__file__))
    cloudflared_path = os.path.join(core_dir, "cloudflared.exe")

    if not os.path.exists(cloudflared_path):
        logger.warning("cloudflared.exe not found at %s. Direct local access only.", cloudflared_path)
        return

    port = int(os.getenv("PHONE_PORT", "5055"))
    cmd = [cloudflared_path, "tunnel", "--protocol", "http2", "--url", f"http://127.0.0.1:{port}"]

    logger.info("Starting Cloudflare tunnel for port %d...", port)
    try:
        # Hide console window on Windows
        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0 # SW_HIDE
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

        # Cloudflared prints logs to stderr
        _tunnel_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            startupinfo=startupinfo,
            creationflags=creationflags
        )

        # Read stderr line-by-line in a loop to capture the public URL and keep process pipe clear
        tunnel_found = False
        for line in iter(_tunnel_process.stderr.readline, ""):
            if not line:
                break
            if not tunnel_found:
                match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if match:
                    candidate = match.group(0)
                    if "api.trycloudflare.com" in candidate or "update.trycloudflare.com" in candidate:
                        continue
                    _tunnel_url = candidate
                    logger.info("📱 Cloudflare tunnel created successfully: %s", _tunnel_url)
                    tunnel_found = True

                    # Write to files
                    try:
                        root_dir = os.path.dirname(core_dir)
                        with open(os.path.join(root_dir, "tunnel_url.txt"), "w", encoding="utf-8") as f:
                            f.write(f"{_tunnel_url}/phone/")
                        data_dir = os.path.join(root_dir, "data")
                        if os.path.isdir(data_dir):
                            with open(os.path.join(data_dir, "tunnel_url.txt"), "w", encoding="utf-8") as f:
                                f.write(f"{_tunnel_url}/phone/")
                    except Exception as e:
                        logger.debug("Failed to save tunnel URL to file: %s", e)

                    # Copy to clipboard
                    try:
                        pyperclip.copy(f"{_tunnel_url}/phone/")
                        logger.info("Tunnel URL copied to clipboard.")
                    except Exception as e:
                        logger.debug("Failed to copy tunnel URL to clipboard: %s", e)

                    # Announce to user (optional, disabled by default to avoid interrupting speech)
                    if _speak_callback and os.getenv("ANNOUNCE_PHONE_TUNNEL", "false").lower() == "true":
                        _speak_callback("Phone companion is ready. The public link has been copied to your clipboard!", wait=False)
                    else:
                        logger.info("Phone companion is ready: %s/phone/", _tunnel_url)
                    
                    # Send links via WhatsApp in a non-blocking daemon thread
                    threading.Thread(target=send_links_via_whatsapp, daemon=True, name="WhatsAppLinkSender").start()

        if not tunnel_found:
            logger.warning("Cloudflare tunnel failed or not found. Trying ngrok fallback...")
            # Try ngrok as a fallback tunnel when Cloudflare is unreliable
            if not _try_ngrok_fallback():
                logger.warning("ngrok also unavailable. Sending local link only.")
            threading.Thread(target=send_links_via_whatsapp, daemon=True, name="WhatsAppLinkSenderLocal").start()

    except Exception as e:
        logger.error("Failed to start Cloudflare tunnel: %s", e)


def _try_ngrok_fallback() -> bool:
    """Try to start an ngrok tunnel as a fallback when Cloudflare fails.
    
    Requires: pip install pyngrok
    Optional: Set NGROK_AUTH_TOKEN in .env for a stable/named subdomain.
    Returns True if the tunnel was started successfully.
    """
    global _tunnel_url, _speak_callback
    port = int(os.getenv("PHONE_PORT", "5055"))
    ngrok_token = os.getenv("NGROK_AUTH_TOKEN", "").strip()

    try:
        from pyngrok import ngrok, conf

        # Set auth token if provided (enables stable URLs and higher limits)
        if ngrok_token:
            conf.get_default().auth_token = ngrok_token

        logger.info("Starting ngrok tunnel for port %d...", port)
        tunnel = ngrok.connect(port, "http")
        public_url = tunnel.public_url

        # ngrok may return http, upgrade to https
        if public_url.startswith("http://"):
            public_url = public_url.replace("http://", "https://", 1)

        _tunnel_url = public_url
        logger.info("📱 ngrok tunnel active: %s", _tunnel_url)

        # Write to files
        try:
            core_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.dirname(core_dir)
            with open(os.path.join(root_dir, "tunnel_url.txt"), "w", encoding="utf-8") as f:
                f.write(f"{_tunnel_url}/phone/")
        except Exception as e:
            logger.debug("Failed to save ngrok URL to file: %s", e)

        # Copy to clipboard
        try:
            import pyperclip
            pyperclip.copy(f"{_tunnel_url}/phone/")
            logger.info("ngrok URL copied to clipboard.")
        except Exception:
            pass

        # Announce
        if _speak_callback:
            _speak_callback("Phone companion is ready via ngrok. The link has been copied to your clipboard!", wait=False)

        return True

    except ImportError:
        logger.info("pyngrok not installed \u2014 ngrok fallback unavailable. Run: pip install pyngrok")
        return False
    except Exception as e:
        logger.warning("ngrok fallback failed: %s", e)
        return False


def stop_phone_server() -> None:
    """Terminate the Cloudflare tunnel process if running."""
    global _tunnel_process
    if _tunnel_process is not None:
        try:
            logger.info("Terminating Cloudflare tunnel process...")
            _tunnel_process.terminate()
            try:
                _tunnel_process.wait(timeout=3)
            except Exception:
                _tunnel_process.kill()
        except Exception as exc:
            logger.warning("Error stopping Cloudflare tunnel: %s", exc)
        _tunnel_process = None


def start_phone_server(command_callback=None, speak_callback=None) -> None:
    """
    Start the phone companion API server in a daemon thread.
    Call this from assistant.py after Shin's main systems are ready.
    """
    global _server_thread, _local_url, _speak_callback

    if command_callback is not None:
        set_command_callback(command_callback)

    if speak_callback is not None:
        _speak_callback = speak_callback

    # Set local Wi-Fi URL
    port = int(os.getenv("PHONE_PORT", "5055"))
    local_ip = get_local_ip()
    _local_url = f"http://{local_ip}:{port}/phone/"
    logger.info("📱 Phone companion local URL: %s", _local_url)

    # Start session cleanup thread
    threading.Thread(target=_cleanup_sessions, daemon=True, name="PhoneSessionCleanup").start()

    # Start Cloudflare tunnel in background
    threading.Thread(target=_start_tunnel_in_background, daemon=True, name="PhoneTunnelStarter").start()

    def _serve():
        try:
            from flask import Flask
        except ImportError:
            logger.error("Flask is not installed. Phone server cannot start. Run: pip install flask")
            return

        app = _create_app()

        import logging as _logging
        wz_log = _logging.getLogger("werkzeug")
        wz_log.setLevel(_logging.WARNING)   # suppress request noise

        app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )

    _server_thread = threading.Thread(target=_serve, daemon=True, name="PhoneServer")
    _server_thread.start()
    logger.info("Phone server thread started.")

