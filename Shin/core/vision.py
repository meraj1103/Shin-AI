"""
vision.py — Screen awareness for Shin Voice Assistant
=========================================================
Captures a screenshot and sends it to a vision-capable AI model
so Shin can see and describe what is on the screen.

Supported backends (tried in order):
  1. Gemini 2.0 Flash   (GEMINI_API_KEY)  — fast, free tier
  2. OpenAI GPT-4o      (OPENAI_API_KEY)
  3. Ollama LLaVA       (OLLAMA_MODEL includes llava/llama3.2-vision)  — offline
  4. pytesseract OCR    (no API key needed)  — reads visible text only

Public API
----------
  capture_screen()          → base64 PNG of the full screen
  capture_active_window()   → base64 PNG cropped to the active window
  ask_vision(question, img) → AI answer about the screen image
  read_screen_text()        → plain text extracted from the screen via OCR
  find_text_on_screen(query)→ True/False + bounding box if found via OCR
"""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import io
import json
import logging
import os
import re
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


# ── Screenshot helpers ────────────────────────────────────────────────────────

def capture_screen() -> str:
    """
    Take a screenshot of the entire screen.
    Returns the image as a base64-encoded PNG string.
    """
    import pyautogui
    try:
        img = pyautogui.screenshot()
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as exc:
        logger.error("Failed to capture screen: %s", exc)
        return ""


def capture_active_window() -> str:
    """
    Capture only the active (foreground) window.
    Falls back to full-screen capture if the window rect can't be determined.
    Returns base64-encoded PNG.
    """
    try:
        import ctypes
        import pyautogui
        from PIL import ImageGrab

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            rect = ctypes.wintypes.RECT()
            if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                bbox = (rect.left, rect.top, rect.right, rect.bottom)
                # Clamp to screen bounds
                sw, sh = pyautogui.size()
                bbox = (
                    max(0, bbox[0]), max(0, bbox[1]),
                    min(sw, bbox[2]), min(sh, bbox[3]),
                )
                if bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                    img = ImageGrab.grab(bbox=bbox)
                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG")
                    return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as exc:
        logger.debug("Active window capture failed, falling back to full screen: %s", exc)

    return capture_screen()


def _run_coro_sync(coro):
    """Safely run an async coroutine synchronously, avoiding event loop conflicts."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


def _run_windows_media_ocr(img) -> list[dict]:
    """
    Run Windows 10/11 built-in OCR via winsdk.
    Returns a list of line dicts:
    [
        {
            "text": "My Mix",
            "rect": (left, top, width, height),
            "words": [
                {"text": "My", "rect": (left, top, width, height)},
                {"text": "Mix", "rect": (left, top, width, height)}
            ]
        }
    ]
    """
    try:
        import winsdk.windows.media.ocr as ocr
        import winsdk.windows.graphics.imaging as imaging
        import winsdk.windows.storage as storage

        async def _do_ocr():
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                tmp_name = tf.name
                img.save(tmp_name, format="PNG")
            try:
                file = await storage.StorageFile.get_file_from_path_async(os.path.abspath(tmp_name))
                stream = await file.open_async(storage.FileAccessMode.READ)
                decoder = await imaging.BitmapDecoder.create_async(stream)
                bitmap = await decoder.get_software_bitmap_async()
                engine = ocr.OcrEngine.try_create_from_user_profile_languages()
                if engine is None:
                    from winsdk.windows.globalization import Language
                    engine = ocr.OcrEngine.try_create_from_language(Language("en-US"))
                if engine is None:
                    return []
                res = await engine.recognize_async(bitmap)
                lines = []
                for line in res.lines:
                    words = []
                    for w in line.words:
                        r = w.bounding_rect
                        words.append({
                            "text": w.text,
                            "rect": (int(r.x), int(r.y), int(r.width), int(r.height)),
                        })
                    if words:
                        min_x = min(w["rect"][0] for w in words)
                        min_y = min(w["rect"][1] for w in words)
                        max_x = max(w["rect"][0] + w["rect"][2] for w in words)
                        max_y = max(w["rect"][1] + w["rect"][3] for w in words)
                        lines.append({
                            "text": line.text,
                            "rect": (min_x, min_y, max_x - min_x, max_y - min_y),
                            "words": words,
                        })
                return lines
            finally:
                if os.path.exists(tmp_name):
                    try:
                        os.remove(tmp_name)
                    except Exception:
                        pass

        return _run_coro_sync(_do_ocr())
    except Exception as exc:
        logger.debug("Windows Media OCR failed: %s", exc)
        return []


def clean_target_text(query: str) -> str:
    """Normalize target text by stripping conversational prefixes/suffixes."""
    t = query.strip()
    t = re.sub(r"^(?:(?:click|tap)\s+)?(?:on\s+)?(?:the\s+)?(?:a\s+)?(?:button\s+for\s+|button\s+)?", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"\s+(?:on|in)?\s*(?:the\s+|my\s+)?screen$", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"\s+(?:button|video|card|link|tab|icon)$", "", t, flags=re.IGNORECASE).strip()
    return t.strip()


def locate_element_with_ai(query: str, img=None) -> tuple[bool, Optional[dict]]:
    """
    Ground an element or text spatially using Gemini Vision.
    Returns (found, bbox_dict).
    """
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        return False, None

    try:
        if img is None:
            import pyautogui
            img = pyautogui.screenshot()

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_bytes = buffer.getvalue()
        w, h = img.size

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_key)
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

        prompt = (
            f"You are a computer vision UI locator. Locate the element or text '{query}' on this screen.\n"
            f"The image resolution is {w}x{h}.\n"
            "Respond ONLY with a JSON object in this exact format:\n"
            "{\"found\": true, \"x\": <center_x_pixel>, \"y\": <center_y_pixel>}\n"
            "If the element is not found on screen, respond with:\n"
            "{\"found\": false}"
        )

        resp = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                prompt,
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=100,
            ),
        )
        txt = (resp.text or "").strip()
        m = re.search(r"\{[^{}]*\}", txt)
        if m:
            data = json.loads(m.group(0))
            if data.get("found") and "x" in data and "y" in data:
                cx = int(data["x"])
                cy = int(data["y"])
                return True, {
                    "left": max(0, cx - 15),
                    "top": max(0, cy - 15),
                    "width": 30,
                    "height": 30,
                    "x": cx,
                    "y": cy,
                    "text": query,
                }
    except Exception as exc:
        logger.debug("AI vision locate failed: %s", exc)

    return False, None


# ── OCR text reading ──────────────────────────────────────────────────────────

def read_screen_text(region: Optional[tuple] = None) -> str:
    """
    Extract all visible text from the screen (or a region).
    Primary: Native Windows 10/11 Media OCR (zero external dependencies).
    Fallback: pytesseract OCR.
    """
    import pyautogui
    try:
        img = pyautogui.screenshot(region=region)
    except Exception as exc:
        logger.error("Screenshot failed for read_screen_text: %s", exc)
        return ""

    # 1. Try Windows Media OCR
    lines = _run_windows_media_ocr(img)
    if lines:
        return "\n".join(l["text"].strip() for l in lines if l["text"].strip())

    # 2. Fallback to pytesseract
    try:
        import pytesseract
        default_tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default_tess):
            pytesseract.pytesseract.tesseract_cmd = default_tess
        text = pytesseract.image_to_string(img, config="--psm 6")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
    except Exception as exc:
        logger.debug("pytesseract fallback failed: %s", exc)
        return ""


def find_text_on_screen(query: str, region: Optional[tuple] = None, screenshot_img=None) -> tuple[bool, Optional[dict]]:
    """
    Search for a specific text string or UI element on screen.
    Returns (found: bool, bbox: dict | None) where bbox has keys
    left, top, width, height, x, y, text.

    Multi-tier resolution:
      1. Windows Media OCR (exact phrase, word-span bounding box, or rapidfuzz)
      2. Pytesseract OCR (fallback)
      3. AI Vision Grounding via Gemini (fallback for graphic logos/canvas)
    """
    clean_q = clean_target_text(query)
    if not clean_q:
        return False, None
    clean_q_lower = clean_q.lower()

    offset_x = region[0] if region else 0
    offset_y = region[1] if region else 0

    img = screenshot_img
    if img is None:
        try:
            import pyautogui
            img = pyautogui.screenshot(region=region)
        except Exception as exc:
            logger.error("find_text_on_screen screenshot failed: %s", exc)
            return False, None

    # ── Tier 1: Windows 10/11 Media OCR ──
    win_lines = _run_windows_media_ocr(img)
    if win_lines:
        best_candidate = None
        best_score = 0.0

        for line in win_lines:
            line_text = line["text"]
            line_text_lower = line_text.lower().strip()

            # Exact line match
            if line_text_lower == clean_q_lower:
                r = line["rect"]
                cx = r[0] + r[2] // 2 + offset_x
                cy = r[1] + r[3] // 2 + offset_y
                return True, {
                    "left": r[0] + offset_x,
                    "top": r[1] + offset_y,
                    "width": r[2],
                    "height": r[3],
                    "x": cx,
                    "y": cy,
                    "text": line_text,
                }

            # Substring match (e.g. "My Mix" inside "Mix - My Mix - ...")
            if clean_q_lower in line_text_lower:
                words = line.get("words", [])
                q_words = clean_q_lower.split()
                matched_words = []
                for i in range(len(words) - len(q_words) + 1):
                    span_text = " ".join(w["text"].lower().strip() for w in words[i:i+len(q_words)])
                    if clean_q_lower in span_text or span_text == clean_q_lower:
                        matched_words = words[i:i+len(q_words)]
                        break
                if not matched_words:
                    matched_words = words
                min_x = min(w["rect"][0] for w in matched_words)
                min_y = min(w["rect"][1] for w in matched_words)
                max_x = max(w["rect"][0] + w["rect"][2] for w in matched_words)
                max_y = max(w["rect"][1] + w["rect"][3] for w in matched_words)
                w_rect = (min_x, min_y, max_x - min_x, max_y - min_y)
                cx = w_rect[0] + w_rect[2] // 2 + offset_x
                cy = w_rect[1] + w_rect[3] // 2 + offset_y
                return True, {
                    "left": w_rect[0] + offset_x,
                    "top": w_rect[1] + offset_y,
                    "width": w_rect[2],
                    "height": w_rect[3],
                    "x": cx,
                    "y": cy,
                    "text": line_text,
                }

            # Fuzzy scoring with RapidFuzz
            try:
                from rapidfuzz import fuzz
                score = fuzz.token_set_ratio(clean_q_lower, line_text_lower)
                if score >= 80 and score > best_score:
                    best_score = score
                    best_candidate = line
            except Exception:
                pass

        if best_candidate and best_score >= 80:
            r = best_candidate["rect"]
            cx = r[0] + r[2] // 2 + offset_x
            cy = r[1] + r[3] // 2 + offset_y
            return True, {
                "left": r[0] + offset_x,
                "top": r[1] + offset_y,
                "width": r[2],
                "height": r[3],
                "x": cx,
                "y": cy,
                "text": best_candidate["text"],
            }

    # ── Tier 2: Pytesseract fallback ──
    try:
        import pytesseract
        default_tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default_tess):
            pytesseract.pytesseract.tesseract_cmd = default_tess
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        for i, word in enumerate(data.get("text", [])):
            if clean_q_lower in word.lower() and data.get("conf", [0])[i] > 30:
                l, t, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                return True, {
                    "left": l + offset_x,
                    "top": t + offset_y,
                    "width": w,
                    "height": h,
                    "x": l + w // 2 + offset_x,
                    "y": t + h // 2 + offset_y,
                    "text": word,
                }
    except Exception:
        pass

    # ── Tier 3: AI Vision Grounding (Gemini) ──
    ai_found, ai_bbox = locate_element_with_ai(clean_q, img)
    if ai_found and ai_bbox:
        return True, ai_bbox

    return False, None


# ── AI vision query ───────────────────────────────────────────────────────────

def get_active_window_title() -> str:
    """Return the title of the active foreground window."""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value or "Desktop"
    except Exception:
        return "Desktop"


def ask_vision(question: str, image_b64: str) -> Optional[str]:
    """
    Send a screenshot (base64 PNG) and a natural-language question
    to a vision-capable AI model or smart screen inspector.

    Returns the model's text answer, or None if no backend is available.
    Tiers: Gemini 2.0 Flash → OpenAI GPT-4o → LM Studio → Ollama LLaVA → OCR + Local LLM
    """
    gemini_key    = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key    = os.getenv("OPENAI_API_KEY", "").strip()
    lm_studio_url = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1").strip().rstrip("/")
    ollama_model  = os.getenv("OLLAMA_MODEL", "").strip()
    active_win    = get_active_window_title()

    try:
        from core.settings import get_language
        lang = get_language()
    except Exception:
        lang = "hindi"

    if lang == "english":
        _VOICE_INSTRUCTIONS = (
            "You are Shin — MJ's cool, sharp-witted female best friend. "
            "You are looking directly at his Windows laptop screen right now to assist and guide him. "
            f"The active window on his screen right now is: '{active_win}'.\n"
            "MJ has requested that you communicate 100% in English. "
            "Act like a true partner-in-crime and expert friend: if you see code, dialogs, or errors, explain them clearly and pinpoint what to do; "
            "if you see design, Blender, or games, give candid feedback; if he asks what's on screen, describe it accurately. "
            "Deliver in 1 to 2 natural spoken sentences for TTS. Strictly female persona. No markdown bullets or code blocks."
        )
    else:
        _VOICE_INSTRUCTIONS = (
            "You are Shin — MJ's cool, sharp-witted female best friend from Ichalkaranji, Maharashtra. "
            "You are looking directly at his Windows laptop screen right now to guide and help him. "
            f"The active window on his screen right now is: '{active_win}'.\n"
            "Act like a true partner-in-crime and expert friend: if you see code or errors, pinpoint what's wrong immediately; "
            "if you see Blender or design work, give your candid cool feedback; if he asks what is happening on screen, explain it clearly. "
            "Speak in your signature cool Hinglish + English tone (e.g. 'Ki tujhe nahi malum tha kya, aur kya MJ!', 'Dekh yahan screen pe...'). "
            "Deliver in 1 to 3 natural spoken sentences for TTS. Strictly female grammar (karti hoon, dekh rahi hoon, bataungi). No markdown bullets or code blocks."
        )

    # ── Tier 1: Gemini Vision (Highest quality & speed) ──────────────────────
    if gemini_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_key)
            img_bytes = base64.b64decode(image_b64)
            safety_settings = [
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                ),
            ]
            model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                    f"{_VOICE_INSTRUCTIONS}\n\nMJ asked: \"{question}\"",
                ],
                config=types.GenerateContentConfig(
                    safety_settings=safety_settings,
                    max_output_tokens=300,
                    temperature=0.3,
                ),
            )
            try:
                import token_tracker
                token_tracker.log_gemini_usage(model_name, response)
            except Exception:
                pass
            text = response.text.strip()
            if text:
                logger.info("Vision answered by Gemini (%s).", model_name)
                return text
        except Exception as exc:
            logger.warning("Gemini vision failed: %s", exc)

    # ── Tier 2: OpenAI GPT-4o Vision ─────────────────────────────────────────
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": _VOICE_INSTRUCTIONS},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}",
                                    "detail": "low",
                                },
                            },
                            {"type": "text", "text": f"MJ asked: \"{question}\""},
                        ],
                    },
                ],
                max_tokens=300,
                user="shin_user",
            )
            try:
                import token_tracker
                token_tracker.log_openai_usage("gpt-4o", response)
            except Exception:
                pass
            msg = response.choices[0].message
            if getattr(msg, "refusal", None):
                raise ValueError(f"OpenAI vision refused: {msg.refusal}")
            text = msg.content.strip()
            if text:
                logger.info("Vision answered by GPT-4o.")
                return text
        except Exception as exc:
            logger.warning("OpenAI vision failed: %s", exc)

    # ── Tier 3: Local LM Studio (Vision or OCR Smart Inspector) ──────────────
    if lm_studio_url:
        try:
            import requests as _req
            # Try image payload first if user loaded a multimodal model in LM Studio
            payload_vision = {
                "messages": [
                    {"role": "system", "content": _VOICE_INSTRUCTIONS},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"MJ asked: \"{question}\""},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
                        ]
                    }
                ],
                "temperature": 0.4,
                "max_tokens": 250,
                "stream": False
            }
            resp = _req.post(f"{lm_studio_url}/chat/completions", json=payload_vision, timeout=(1.5, 25.0))
            if resp.status_code == 200:
                answer = resp.json()["choices"][0]["message"]["content"].strip()
                if answer:
                    logger.info("Vision answered by local LM Studio multimodal model.")
                    return answer
        except Exception:
            pass

        # If multimodal failed or user has text model (like Qwen 2.5 7B), inspect screen via OCR & window context!
        try:
            ocr_text = read_screen_text()
            if ocr_text or active_win:
                logger.info("Using LM Studio with screen OCR inspector for question: %s", question)
                snippet = ocr_text[:1200] if ocr_text else "No visible text extracted."
                ocr_prompt = (
                    f"{_VOICE_INSTRUCTIONS}\n\n"
                    f"Active Window on screen: {active_win}\n"
                    f"Visible text extracted from screen:\n{snippet}\n\n"
                    f"MJ asked: \"{question}\""
                )
                import requests as _req
                resp = _req.post(
                    f"{lm_studio_url}/chat/completions",
                    json={
                        "messages": [
                            {"role": "system", "content": _VOICE_INSTRUCTIONS},
                            {"role": "user", "content": ocr_prompt}
                        ],
                        "temperature": 0.4,
                        "max_tokens": 250,
                        "stream": False
                    },
                    timeout=(1.5, 25.0)
                )
                if resp.status_code == 200:
                    answer = resp.json()["choices"][0]["message"]["content"].strip()
                    if answer:
                        logger.info("Screen answered by LM Studio OCR inspector.")
                        return answer
        except Exception as exc:
            logger.debug("LM Studio screen inspection failed: %s", exc)

    # ── Tier 4: Ollama local vision (llava / llama3.2-vision) ────────────────
    if ollama_model:
        vision_models = [
            m.strip() for m in ollama_model.split(",")
            if any(v in m.lower() for v in ("llava", "vision", "bakllava", "moondream"))
        ]
        for vmodel in vision_models:
            try:
                import requests as _req
                resp = _req.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": vmodel,
                        "prompt": f"{_VOICE_INSTRUCTIONS}\n\nUser asked: \"{question}\"",
                        "images": [image_b64],
                        "stream": False,
                    },
                    timeout=(2.0, 30.0),
                )
                if resp.status_code == 200:
                    text = resp.json().get("response", "").strip()
                    if text:
                        logger.info("Vision answered by Ollama %s.", vmodel)
                        return text
            except Exception as exc:
                logger.debug("Ollama vision (%s) failed: %s", vmodel, exc)

    return None


# ── Screen Activity & Workspace Inspector ─────────────────────────────────────

def get_active_process_name() -> str:
    """Return the executable name of the active foreground window process."""
    try:
        import ctypes
        import win32process
        import psutil
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return psutil.Process(pid).name().lower()
    except Exception:
        pass
    return "unknown"


def inspect_screen_activity() -> dict:
    """
    Examine the active window, running process, and screen content
    to determine what MJ is working on and if an error is present.
    """
    win_title = get_active_window_title()
    proc_name = get_active_process_name()
    title_lower = win_title.lower()

    activity = "multitasking"
    category = "General Desktop"

    if "code" in proc_name or "visual studio code" in title_lower:
        activity = "coding"
        category = "VS Code (Programming)"
    elif any(b in proc_name for b in ("chrome", "msedge", "firefox", "brave")):
        activity = "browsing"
        category = "Web Browser (Research / Browsing)"
    elif "blender" in proc_name or "blender" in title_lower:
        activity = "3d_modeling"
        category = "Blender (3D Modeling & Animation)"
    elif "powerpnt" in proc_name or "powerpoint" in title_lower:
        activity = "presentation"
        category = "PowerPoint (Presentation Design)"
    elif any(t in proc_name for t in ("cmd", "powershell", "wt", "windowsterminal")):
        activity = "terminal"
        category = "Terminal (Command Line Operations)"
    elif "whatsapp" in proc_name or "discord" in proc_name:
        activity = "communication"
        category = "Chat & Communication"
    elif "explorer" in proc_name:
        activity = "files"
        category = "File Explorer (File Management)"

    # Look for error patterns in title or screen text
    ocr_text = ""
    error_found = False
    error_detail = ""

    error_patterns = [
        r"Traceback \(most recent call last\):",
        r"SyntaxError:\s*.+",
        r"IndentationError:\s*.+",
        r"NameError:\s*.+",
        r"TypeError:\s*.+",
        r"ValueError:\s*.+",
        r"ModuleNotFoundError:\s*.+",
        r"ImportError:\s*.+",
        r"AttributeError:\s*.+",
        r"npm ERR!\s*.+",
        r"Build failed",
        r"Compilation error",
        r"Unhandled exception",
        r"404 Not Found",
        r"Windows cannot find\s+.+",
        r"Problem with Shortcut",
        r"The system cannot find the file specified",
        r"Application not found",
        r"Command failed",
    ]

    import re
    # Check title first
    for pat in error_patterns:
        m = re.search(pat, win_title, re.IGNORECASE)
        if m:
            error_found = True
            error_detail = m.group(0)
            break

    # If coding or terminal, perform quick OCR snippet check
    if not error_found and activity in ("coding", "terminal"):
        try:
            ocr_text = read_screen_text()
            if ocr_text:
                try:
                    import security_shield
                    ocr_text, flagged = security_shield.sanitize_untrusted_input(ocr_text, source="screen_ocr")
                except Exception:
                    pass
                for pat in error_patterns:
                    m = re.search(pat, ocr_text, re.IGNORECASE)
                    if m:
                        error_found = True
                        error_detail = m.group(0)
                        break
        except Exception:
            pass

    return {
        "window_title": win_title,
        "process_name": proc_name,
        "activity": activity,
        "category": category,
        "error_detected": error_found,
        "error_detail": error_detail,
        "ocr_snippet": ocr_text[:300] if ocr_text else "",
    }


def summarize_screen_activity() -> str:
    """
    Generate a spoken summary of what is happening on screen right now.
    """
    info = inspect_screen_activity()
    win_title = info["window_title"]
    category = info["category"]
    has_error = info["error_detected"]
    error_detail = info["error_detail"]

    try:
        from core.settings import get_language
        lang = get_language()
    except Exception:
        lang = "hindi"
    is_english = (lang == "english")

    # If an AI vision backend is available, ask vision for a rich description
    img_b64 = capture_active_window()
    if img_b64:
        q_prompt = (
            "Describe in 1-2 spoken English sentences what MJ is doing right now on this screen."
            if is_english else
            "Describe in 1-2 spoken sentences what MJ is doing right now on this screen."
        )
        ai_resp = ask_vision(q_prompt, img_b64)
        if ai_resp:
            return ai_resp

    # Fallback to rule-based screen report
    if is_english:
        if has_error:
            return (
                f"On screen right now is {category} — window title '{win_title}'. "
                f"And I noticed an error on screen: '{error_detail}'. "
                "Want me to help you debug it?"
            )
        return (
            f"Screen currently has {category} active! Window title is '{win_title}'. "
            "You look fully focused, MJ. Let me know if you need any help!"
        )

    if has_error:
        return (
            f"Screen pe abhi {category} khula hai — window title hai '{win_title}'. "
            f"Aur mujhe lagta hai screen pe error aaya hai: '{error_detail}'. "
            "Bol toh main isko debug karne mein help karun?"
        )

    return (
        f"Screen pe abhi {category} active hai! Window title hai '{win_title}'. "
        "Ekdum focused lag raha hai tu, bata kuch help chahiye isme?"
    )


def diagnose_screen_error() -> str:
    """
    Specifically scan the screen for programming or application errors and explain them.
    """
    info = inspect_screen_activity()
    img_b64 = capture_active_window()

    try:
        from core.settings import get_language
        lang = get_language()
    except Exception:
        lang = "hindi"
    is_english = (lang == "english")

    if img_b64:
        prompt = (
            "Look at this screenshot carefully. Is there an error, modal dialog, terminal traceback, "
            "or application warning visible? If yes, identify the exact bug and explain how to fix it in 2 spoken English sentences. "
            "If no error is visible, say that the screen looks clean."
            if is_english else
            "Look at this screenshot carefully. Is there a programming error, terminal traceback, "
            "or application warning visible? If yes, identify the exact bug and explain how to fix it in 2 spoken Hinglish sentences. "
            "If no error is visible, say that the screen looks clean."
        )
        ai_resp = ask_vision(prompt, img_b64)
        if ai_resp:
            return ai_resp

    if is_english:
        if info["error_detected"]:
            return (
                f"I detected '{info['error_detail']}' on screen! "
                "Looks like an application or syntax error. Copy the code or details to clipboard and I will help you fix it!"
            )
        return "I don't see any major errors or crashes on screen, MJ. Everything looks good!"

    if info["error_detected"]:
        return (
            f"Screen pe mujhe '{info['error_detail']}' dikha hai! "
            "Yeh syntax ya runtime error hai. Code ko save karke clipboard pe copy kar, main detailed fix bataungi!"
        )

    return "Screen pe koi major error ya crash mujhe dikh nahi raha MJ, sab theek lag raha hai!"

