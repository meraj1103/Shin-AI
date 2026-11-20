"""
clipboard_ai.py — Clipboard read/write and AI text transformation
==================================================================
Reads the user's clipboard, applies an AI transformation
(rewrite, translate, summarize, grammar-fix), and writes the result
back to the clipboard.

Uses whichever AI backend key is present: Gemini → OpenAI → Ollama.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


# ── Clipboard I/O ──────────────────────────────────────────────────────────────

def get_clipboard() -> str:
    """Read the current clipboard content. Returns empty string on failure."""
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except Exception as exc:
        logger.warning("Failed to read clipboard: %s", exc)
        return ""


def set_clipboard(text: str) -> None:
    """Write text to the clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text)
    except Exception as exc:
        logger.warning("Failed to write clipboard: %s", exc)


# ── AI Transform ──────────────────────────────────────────────────────────────

def transform_clipboard(instruction: str) -> Optional[str]:
    """
    Read the clipboard, apply an AI transformation described by `instruction`,
    write the result back to the clipboard, and return the result string.

    Returns None if the clipboard is empty or no AI backend is available.
    """
    content = get_clipboard()
    if not content.strip():
        return None

    try:
        from core import security_shield
        sanitized_content, flagged = security_shield.sanitize_untrusted_input(content, source="clipboard")
        if flagged:
            logger.warning("CaMeL Shield: Blocked indirect prompt injection in clipboard.")
            return "Cannot process clipboard content: suspicious prompt injection detected."
        content = sanitized_content
    except Exception as exc:
        logger.debug("Clipboard sanitization skipped: %s", exc)

    prompt = (
        f"{instruction}\n\n"
        f"Text:\n{content}\n\n"
        "Respond with ONLY the transformed text, no explanation, no preamble."
    )

    result = _call_ai(prompt)
    if result:
        set_clipboard(result)
    return result


def _call_ai(prompt: str) -> Optional[str]:
    """Try each available AI backend and return the first successful response."""
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    ollama_model = os.getenv("OLLAMA_MODEL", "").strip()

    # ── Fast Online Cascade via LLM Router (Groq <450ms, Gemini, etc.) ────────
    if (gemini_key or openai_key or os.getenv("GROQ_API_KEY")):
        try:
            try:
                from core import llm_router
            except ImportError:
                import llm_router

            router = llm_router.get_router()
            if router.groq_key or router.gemini_key:
                res = router.query(
                    messages=[{"role": "user", "content": prompt}],
                    system_prompt="You are Shin, a clipboard assistant that transforms text according to user instructions. Return ONLY the transformed text.",
                    max_tokens=600,
                    temperature=0.3,
                )
                if res and res.get("content") and not res.get("content", "").startswith("Arey yaar"):
                    return res["content"].strip()
        except Exception as exc:
            logger.debug("Router clipboard transform skipped: %s", exc)

    # ── LM Studio (local OpenAI-compatible) ───────────────────────────────────
    lm_studio_url = os.getenv("LM_STUDIO_URL", "").strip().rstrip("/")
    if lm_studio_url:
        try:
            import requests as _req
            payload = {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are Shin, an AI assistant. Transform or process the text according to user instructions. Return ONLY the transformed text or result, without conversational preamble.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 600,
                "stream": False,
            }
            resp = _req.post(
                f"{lm_studio_url}/chat/completions",
                json=payload,
                timeout=(1.2, 30.0),
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if content:
                    return content
        except Exception as exc:
            logger.debug("LM Studio clipboard transform skipped or failed: %s", exc)

    # ── Ollama (local) ────────────────────────────────────────────────────────
    if ollama_model:
        models = [m.strip() for m in ollama_model.split(",") if m.strip()]
        import requests as _req
        for model in models:
            try:
                resp = _req.post(
                    "http://localhost:11434/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                    timeout=(2.0, 15.0),  # Connect timeout: 2s, Read timeout: 15s (was 60s)
                )
                if resp.status_code == 404:
                    logger.warning(
                        "Ollama model '%s' not found for clipboard transform. Trying next...",
                        model
                    )
                    continue
                resp.raise_for_status()
                return resp.json().get("response", "").strip()
            except (_req.exceptions.ConnectionError, _req.exceptions.Timeout) as exc:
                logger.warning("Ollama connection/timeout failed: %s. Skipping remaining local models.", exc)
                break
            except Exception as exc:
                logger.warning(
                    "Ollama model '%s' clipboard transform failed: %s. Trying next...",
                    model,
                    exc
                )

    return None


# ── Code Intelligence & Project Tools ─────────────────────────────────────────

def fix_errors(code_or_text: str) -> str:
    """
    Diagnose errors or bugs in code_or_text, write the fixed code to the clipboard,
    and return a spoken explanation in Hinglish.
    """
    if not code_or_text.strip():
        return "Clipboard pe koi code ya error text nahi hai MJ!"

    prompt = (
        "You are Shin, MJ's expert coding best friend. Analyze this error or code snippet:\n"
        f"{code_or_text}\n\n"
        "1. Identify the bug or root cause.\n"
        "2. Provide the corrected, working code.\n"
        "Format your answer as:\n"
        "EXPLANATION: [1-2 spoken Hinglish sentences explaining the bug]\n"
        "FIXED_CODE:\n[corrected code only]\n"
    )

    ai_resp = _call_ai(prompt)
    if not ai_resp:
        # Fallback offline heuristic fix analysis
        if "IndentationError" in code_or_text:
            return "Yeh IndentationError hai MJ! Python mein indentation inconsistent hai — tab aur spaces check kar!"
        if "SyntaxError" in code_or_text:
            return "SyntaxError mila hai! Bracket, colon ya quote close karna bhool gaya shayad."
        if "ModuleNotFoundError" in code_or_text:
            return "ModuleNotFoundError hai! Yeh library installed nahi hai, pip install run kar ke dekho."
        return "Maine clipboard error dekha par offline mode mein exact fix generate nahi ho paya."

    import re
    exp_match = re.search(r"EXPLANATION:\s*(.*?)(?=FIXED_CODE:|$)", ai_resp, re.DOTALL | re.IGNORECASE)
    code_match = re.search(r"FIXED_CODE:\s*(.*)", ai_resp, re.DOTALL | re.IGNORECASE)

    explanation = exp_match.group(1).strip() if exp_match else "Maine bug analyze kar liya aur code fix kar diya!"
    fixed_code = code_match.group(1).strip() if code_match else ai_resp.strip()

    # Clean markdown backticks if present in code
    fixed_code = re.sub(r"^```[a-zA-Z]*\n", "", fixed_code)
    fixed_code = re.sub(r"\n```$", "", fixed_code).strip()

    if fixed_code:
        set_clipboard(fixed_code)
        return f"{explanation} Fixed code tere clipboard pe copy kar diya hai, seedha Ctrl+V se paste kar le!"

    return explanation


def explain_code(code: str) -> str:
    """Explain a code snippet in 2-3 spoken Hinglish sentences."""
    if not code.strip():
        return "Clipboard pe koi code nahi hai explain karne ke liye!"

    prompt = (
        "You are Shin, MJ's tomboy coding partner. Explain what this code does in 2 concise, "
        "spoken Hinglish sentences for a voice assistant. Strictly female grammar:\n"
        f"{code}"
    )
    ai_resp = _call_ai(prompt)
    return ai_resp or "Yeh code logic perform karta hai par detailed explanation offline available nahi hai."


def generate_code(prompt_text: str, language: str = "python") -> str:
    """Generate production-ready code for a request and copy to clipboard."""
    if not prompt_text.strip():
        return "Bata toh sahi kaisa code likhna hai!"

    prompt = (
        f"You are Shin, an expert {language} developer. Write clean, production-grade {language} code for:\n"
        f"{prompt_text}\n\n"
        "Provide ONLY the code block, with brief comments. No conversational preamble."
    )
    ai_resp = _call_ai(prompt)
    if ai_resp:
        import re
        clean_code = re.sub(r"^```[a-zA-Z]*\n", "", ai_resp.strip())
        clean_code = re.sub(r"\n```$", "", clean_code).strip()
        set_clipboard(clean_code)
        return f"Maine {language} code likh ke clipboard pe copy kar diya MJ! VS Code mein paste kar le."
    return "Code generation ke liye internet ya AI backend active nahi hai."

