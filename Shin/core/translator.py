"""
translator.py — Real-time voice translation for Shin Voice Assistant
=====================================================================
Uses the MyMemory free translation API (no key required, 5 000 chars/day).
Supports 30+ languages by name (Hindi, French, Japanese, etc.).
"""

from __future__ import annotations

import logging

logger = logging.getLogger("shin.translator")

# ── Language name → ISO 639-1 code ──────────────────────────────────────────

LANGUAGE_CODES: dict[str, str] = {
    "afrikaans": "af", "arabic": "ar", "bengali": "bn", "bulgarian": "bg",
    "chinese": "zh", "mandarin": "zh", "cantonese": "zh",
    "croatian": "hr", "czech": "cs", "danish": "da", "dutch": "nl",
    "english": "en", "estonian": "et", "finnish": "fi", "french": "fr",
    "german": "de", "greek": "el", "gujarati": "gu", "hebrew": "he",
    "hindi": "hi", "hungarian": "hu", "indonesian": "id", "italian": "it",
    "japanese": "ja", "kannada": "kn", "korean": "ko", "latvian": "lv",
    "lithuanian": "lt", "malay": "ms", "malayalam": "ml", "marathi": "mr",
    "nepali": "ne", "norwegian": "no", "persian": "fa", "farsi": "fa",
    "polish": "pl", "portuguese": "pt", "punjabi": "pa", "romanian": "ro",
    "russian": "ru", "serbian": "sr", "sinhalese": "si", "slovak": "sk",
    "slovenian": "sl", "spanish": "es", "swahili": "sw", "swedish": "sv",
    "tamil": "ta", "telugu": "te", "thai": "th", "turkish": "tr",
    "ukrainian": "uk", "urdu": "ur", "vietnamese": "vi", "welsh": "cy",
}


def get_language_code(lang: str) -> str:
    """Convert a language name or code to its ISO 639-1 code."""
    lang = lang.strip().lower()
    # Already a code?
    if len(lang) == 2:
        return lang
    return LANGUAGE_CODES.get(lang, lang[:2])


def translate(text: str, target_lang: str, source_lang: str = "en") -> str:
    """
    Translate *text* to *target_lang* using the MyMemory API.

    Parameters
    ----------
    text        : the text to translate (max 500 chars per call)
    target_lang : language name ("Hindi") or ISO code ("hi")
    source_lang : source language ISO code (default "en")

    Returns
    -------
    Translated string, or an empty string on failure.
    """
    import requests

    text = text.strip()
    if not text:
        return ""

    target_code = get_language_code(target_lang)
    lang_pair   = f"{source_lang}|{target_code}"

    try:
        resp = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text[:500], "langpair": lang_pair},
            timeout=7,
        )
        resp.raise_for_status()
        data = resp.json()

        status = data.get("responseStatus", 0)
        translated = data.get("responseData", {}).get("translatedText", "").strip()

        if status == 200 and translated and translated.upper() != text.upper():
            return translated
        if status == 429:
            return "__RATE_LIMITED__"

        # API returned something but it looks wrong — try fallback
        return ""

    except requests.exceptions.Timeout:
        logger.warning("Translation timed out for %r → %s", text[:30], target_lang)
        return "__TIMEOUT__"
    except Exception as exc:
        logger.warning("Translation API error: %s", exc)
        return ""
