"""
settings.py — Centralized Persistent Settings Manager for Shin
==============================================================
Manages runtime and persistent settings (Language preference, Active AI Model/Provider)
with JSON persistence in Shin/data/settings.json.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("shin.settings")

_SETTINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "settings.json"

_DEFAULT_SETTINGS: Dict[str, Any] = {
    "language": "hinglish",       # "english" | "hindi" | "hinglish" | "marathi"
    "ai_provider": "auto",        # "auto" | "gemini" | "groq" | "openai" | "anthropic" | "tokenharbor" | "ollama" | "lm_studio"
    "voice_speed": 1.0,
    "voice_pitch": "+0Hz",
}

_CACHE: Optional[Dict[str, Any]] = None


def _load_settings() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    settings = dict(_DEFAULT_SETTINGS)
    if _SETTINGS_FILE.exists():
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    settings.update(saved)
        except Exception as exc:
            logger.warning("Failed to load settings from %s: %s", _SETTINGS_FILE, exc)

    _CACHE = settings
    return _CACHE


def _save_settings() -> None:
    if _CACHE is None:
        return
    try:
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(_CACHE, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Failed to save settings to %s: %s", _SETTINGS_FILE, exc)


def get_language() -> str:
    """Return active language: 'english', 'hindi', 'hinglish', or 'marathi'."""
    settings = _load_settings()
    return settings.get("language", "hinglish").lower().strip()


def set_language(lang: str) -> str:
    """Set and persist active language."""
    settings = _load_settings()
    cleaned = lang.lower().strip()
    if "eng" in cleaned:
        final_lang = "english"
    elif "marathi" in cleaned:
        final_lang = "marathi"
    elif "hindi" in cleaned:
        final_lang = "hindi"
    else:
        final_lang = "hinglish"

    settings["language"] = final_lang
    _save_settings()
    # Synchronize across any duplicate module instances in sys.modules
    for mod_name in ("settings", "core.settings"):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, "_CACHE") and mod._CACHE is not None:
            mod._CACHE["language"] = final_lang
    logger.info("Language updated and persisted: %s", final_lang)
    return final_lang


def get_ai_provider() -> str:
    """Return active preferred AI provider name (e.g. 'auto', 'gemini', 'groq')."""
    settings = _load_settings()
    return settings.get("ai_provider", "auto").lower().strip()


def set_ai_provider(provider: str) -> tuple[bool, str]:
    """Set and persist preferred AI provider."""
    try:
        from core.llm_router import set_preferred_provider
    except ImportError:
        from llm_router import set_preferred_provider

    ok, disp = set_preferred_provider(provider)
    if ok:
        settings = _load_settings()
        settings["ai_provider"] = provider.lower().strip()
        _save_settings()
        logger.info("AI provider updated and persisted: %s", disp)
    return ok, disp


def get_setting(key: str, default: Any = None) -> Any:
    """Get any arbitrary setting key."""
    settings = _load_settings()
    return settings.get(key, default)


def set_setting(key: str, value: Any) -> None:
    """Set and persist any arbitrary setting key."""
    settings = _load_settings()
    settings[key] = value
    _save_settings()

