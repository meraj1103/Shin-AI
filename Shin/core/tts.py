"""
tts.py — Modular, High-Fidelity Neural Text-to-Speech Engine for Shin
====================================================================
Integrates Microsoft Edge Neural TTS with Expressive Indian English
(en-IN-NeerjaExpressiveNeural with en-IN-NeerjaNeural fallback),
Devanagari Hindi/Marathi detection, pitch tuning (+8Hz default), and
graceful pyttsx3 offline fallback.
"""
import asyncio
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("shin.tts")

# ═══════════════════════════════════════════════════════════════════════════════
# Voice Configuration & Defaults
# ═══════════════════════════════════════════════════════════════════════════════

EDGE_TTS_VOICE_EN = os.getenv("EDGE_TTS_VOICE_EN", "en-IN-NeerjaNeural")
EDGE_TTS_VOICE_FALLBACK_EN = "en-IN-NeerjaNeural"
EDGE_TTS_VOICE_HI = os.getenv("EDGE_TTS_VOICE", "hi-IN-SwaraNeural")
EDGE_TTS_VOICE_MR = os.getenv("EDGE_TTS_VOICE_MR", "mr-IN-AarohiNeural")
TTS_SPEED = float(os.getenv("TTS_SPEED", "1.0"))
TTS_PITCH = os.getenv("TTS_PITCH", "+0Hz")

# LM Studio (Voice Studio) TTS Configuration
LM_STUDIO_TTS_URL = os.getenv("LM_STUDIO_TTS_URL", "http://localhost:1234/v1")
LM_STUDIO_TTS_VOICE = os.getenv("LM_STUDIO_TTS_VOICE", "af_heart")
LM_STUDIO_TTS_MODEL = os.getenv("LM_STUDIO_TTS_MODEL", "kokoro-v1.0")

_tts_lock = threading.Lock()


def is_text_hindi(text: str) -> bool:
    """Detect if the text contains Devanagari script (Hindi or Marathi)."""
    return any('\u0900' <= char <= '\u097f' for char in text)


def is_text_marathi(text: str) -> bool:
    """Detect if the text contains Devanagari Marathi."""
    if not is_text_hindi(text):
        return False
    if any(c in text for c in ('ळ', 'ळी', 'ळा', 'ळे')):
        return True
    marathi_words = {
        "आहे", "आहेत", "मी", "करू", "शकते", "झाली", "वाजले", "तारीख",
        "तुमची", "तुमचे", "माझी", "माझे", "काय", "ते", "नमस्कार", "बोलेन",
        "नको", "करा", "कसे", "कशी", "वार", "उघड"
    }
    words = set(re.findall(r'[\u0900-\u097f]+', text))
    return bool(words & marathi_words)


def clean_text_for_speech(text: str) -> str:
    """Normalize text into clean, human-like speech output without formatting noise."""
    if not text:
        return ""

    # Strip markdown bold/italic/code syntax (*, _, `)
    text = re.sub(r'[\*\_\`]+', '', text)
    # Remove markdown headers and list bullets (e.g. # Header, • bullet, - item)
    text = re.sub(r'^[#•\-\*\+]+\s+', '', text, flags=re.MULTILINE)
    # Strip web URLs
    text = re.sub(r'https?://\S+', '', text)

    # Normalize speed/distance unit symbols
    text = re.sub(r'(?<=\d)\s*(?:km/h|km/hr|kmh)\b', ' kilometers per hour', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:km/h|km/hr|kmh)\b', 'kilometers per hour', text, flags=re.IGNORECASE)

    # Normalize degree symbols and slash
    text = re.sub(r'\b(\d+)\s*°[Cc]\b', r'\1 degrees Celsius', text)
    text = re.sub(r'\b(\d+)\s*°\b', r'\1 degrees', text)
    text = text.replace("°C", " degrees Celsius").replace("°", " degrees")
    text = text.replace("|", ", ")
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = text.replace("\\", " ")

    # Clean numbers in parentheses
    text = re.sub(r'\(\s*\d+\s*\)', '', text)
    text = re.sub(r'[\(\)\[\]\{\}]', ', ', text)
    text = re.sub(r'[\\_~^]', ' ', text)

    # Remove emojis & non-BMP symbols
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    text = re.sub(r'[\u2000-\u3300]', '', text)

    # Normalize multiple punctuation into natural pauses
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'\-{2,}', ', ', text)
    text = re.sub(r'\s*,\s*', ', ', text)
    text = re.sub(r'(?:,\s*)+,', ', ', text)

    # Female grammar normalization
    try:
        from core import nlp
        text = nlp.enforce_female_grammar(text)
    except Exception:
        try:
            import nlp
            text = nlp.enforce_female_grammar(text)
        except Exception:
            pass

    return re.sub(r'\s+', ' ', text).strip()


def synthesize_edge_audio(
    text: str,
    voice: Optional[str] = None,
    pitch: Optional[str] = None,
    speed: Optional[float] = None,
) -> Optional[str]:
    """
    Synthesize speech audio using Microsoft Edge Neural TTS.
    Returns path to temporary .mp3 file, or None if failed.
    """
    try:
        import edge_tts
    except ImportError:
        logger.debug("edge-tts library not installed.")
        return None

    active_pitch = pitch or TTS_PITCH or "+0Hz"
    active_speed = speed if speed is not None else TTS_SPEED
    speed_pct = int((active_speed - 1.0) * 100)
    rate_str = f"{'+' if speed_pct >= 0 else ''}{speed_pct}%"

    if not voice:
        try:
            from core.settings import get_language
            current_lang = get_language()
        except Exception:
            try:
                from settings import get_language
                current_lang = get_language()
            except Exception:
                current_lang = "hindi"

        if current_lang == "english" and not is_text_hindi(text):
            chosen_voice = EDGE_TTS_VOICE_EN
        elif is_text_marathi(text) or current_lang == "marathi":
            chosen_voice = EDGE_TTS_VOICE_MR
        elif is_text_hindi(text) or current_lang == "hindi":
            chosen_voice = EDGE_TTS_VOICE_HI
        else:
            chosen_voice = EDGE_TTS_VOICE_EN if not is_text_hindi(text) else EDGE_TTS_VOICE_HI
    else:
        chosen_voice = voice

    async def _generate(v: str) -> str:
        communicate = edge_tts.Communicate(
            text,
            voice=v,
            rate=rate_str,
            pitch=active_pitch,
            volume="+0%",
        )
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name
        await asyncio.wait_for(communicate.save(tmp_path), timeout=12.0)
        return tmp_path

    # Try selected voice first
    try:
        return asyncio.run(_generate(chosen_voice))
    except Exception as exc:
        logger.debug("Edge TTS with voice '%s' failed: %s", chosen_voice, exc)
        # If expressive voice failed, retry once with standard NeerjaNeural
        if (chosen_voice == "en-IN-NeerjaExpressiveNeural" or chosen_voice == EDGE_TTS_VOICE_EN) and chosen_voice != EDGE_TTS_VOICE_FALLBACK_EN:
            try:
                logger.debug("Retrying with fallback voice '%s'...", EDGE_TTS_VOICE_FALLBACK_EN)
                return asyncio.run(_generate(EDGE_TTS_VOICE_FALLBACK_EN))
            except Exception as exc2:
                logger.debug("Fallback voice '%s' also failed: %s", EDGE_TTS_VOICE_FALLBACK_EN, exc2)
        return None


def play_audio_file(mp3_path: str) -> bool:
    """Play an audio file using pygame or Windows MediaPlayer fallback."""
    if not mp3_path or not os.path.exists(mp3_path):
        return False

    played = False
    try:
        import pygame
        init_info = pygame.mixer.get_init()
        if init_info:
            if init_info[0] != 24000:
                pygame.mixer.quit()
                pygame.mixer.init(frequency=24000, size=-16, channels=2, buffer=4096)
        else:
            pygame.mixer.init(frequency=24000, size=-16, channels=2, buffer=4096)

        pygame.mixer.music.load(mp3_path)
        pygame.mixer.music.set_volume(1.0)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.02)
        pygame.mixer.music.unload()
        played = True
    except Exception as exc:
        logger.debug("pygame audio playback failed: %s", exc)

    if not played:
        try:
            safe_path = mp3_path.replace("\\", "/")
            ps_cmd = (
                'Add-Type -AssemblyName presentationCore; '
                f'$m = New-Object System.Windows.Media.MediaPlayer; '
                f'$m.Open([System.Uri]"{safe_path}"); '
                'Start-Sleep -Milliseconds 400; '
                '$m.Play(); '
                'Start-Sleep -Seconds 4; '
                '$m.Close()'
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            played = True
        except Exception as exc:
            logger.debug("Windows media player fallback failed: %s", exc)

    return played


def speak_edge(text: str) -> bool:
    """Synthesize and play speech via Edge TTS with pyttsx3 fallback."""
    cleaned = clean_text_for_speech(text)
    if not cleaned:
        return False

    tmp_path = synthesize_edge_audio(cleaned)
    if tmp_path:
        try:
            return play_audio_file(tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    # Fallback to offline pyttsx3 if edge-tts fails
    try:
        from assistant import _speak_pyttsx3
        _speak_pyttsx3(cleaned)
        return True
    except Exception as exc:
        logger.debug("Offline pyttsx3 fallback failed: %s", exc)
        return False


def synthesize_lm_studio_audio(
    text: str,
    voice: Optional[str] = None,
    speed: Optional[float] = None,
) -> Optional[str]:
    """
    Synthesize speech audio using LM Studio (Voice Studio) TTS API.
    Returns path to temporary .wav file, or None if failed.
    
    LM Studio TTS typically uses OpenAI-compatible /audio/speech endpoint
    or a custom /tts endpoint.
    """
    try:
        import requests
    except ImportError:
        logger.debug("requests library not installed.")
        return None

    active_speed = speed if speed is not None else TTS_SPEED
    chosen_voice = voice or LM_STUDIO_TTS_VOICE
    
    # Prepare request payload (OpenAI-compatible format)
    payload = {
        "model": LM_STUDIO_TTS_MODEL,
        "input": text,
        "voice": chosen_voice,
        "response_format": "wav",
        "speed": active_speed,
    }

    try:
        # Try OpenAI-compatible /audio/speech endpoint first
        url = f"{LM_STUDIO_TTS_URL}/audio/speech"
        logger.debug("Requesting LM Studio TTS at %s with voice %s", url, chosen_voice)
        
        response = requests.post(
            url,
            json=payload,
            timeout=30.0,
            stream=True
        )
        
        if response.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
            return tmp_path
        else:
            logger.debug("LM Studio TTS /audio/speech failed with status %d: %s", 
                        response.status_code, response.text)
            
    except Exception as exc:
        logger.debug("LM Studio TTS /audio/speech endpoint failed: %s", exc)

    # Try alternative /tts endpoint (some LM Studio TTS implementations)
    try:
        url = f"{LM_STUDIO_TTS_URL}/tts"
        payload_alt = {
            "text": text,
            "voice": chosen_voice,
            "speed": active_speed,
        }
        response = requests.post(url, json=payload_alt, timeout=30.0)
        
        if response.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name
            f.write(response.content)
            return tmp_path
        else:
            logger.debug("LM Studio TTS /tts failed with status %d: %s", 
                        response.status_code, response.text)
            
    except Exception as exc:
        logger.debug("LM Studio TTS /tts endpoint failed: %s", exc)

    return None


def speak_lm_studio(text: str) -> bool:
    """Synthesize and play speech via LM Studio (Voice Studio) TTS with fallback."""
    cleaned = clean_text_for_speech(text)
    if not cleaned:
        return False

    tmp_path = synthesize_lm_studio_audio(cleaned)
    if tmp_path:
        try:
            return play_audio_file(tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    # Fallback to Edge TTS if LM Studio fails
    logger.warning("LM Studio TTS failed, falling back to Edge TTS")
    return speak_edge(cleaned)


def set_voice_pitch(pitch_val: str, label: str = "") -> str:
    """Dynamically update Shin's TTS voice pitch, persist to .env, and notify user."""
    global TTS_PITCH
    TTS_PITCH = pitch_val
    os.environ["TTS_PITCH"] = pitch_val

    try:
        env_file = Path(__file__).resolve().parent.parent / ".env"
        if env_file.exists():
            text = env_file.read_text(encoding="utf-8")
            if re.search(r"^TTS_PITCH=.*$", text, flags=re.MULTILINE):
                text = re.sub(r"^TTS_PITCH=.*$", f"TTS_PITCH={pitch_val}", text, flags=re.MULTILINE)
            else:
                text += f"\nTTS_PITCH={pitch_val}\n"
            env_file.write_text(text, encoding="utf-8")
    except Exception as exc:
        logger.debug("Failed to persist TTS_PITCH to .env: %s", exc)

    spoken_desc = label or pitch_val
    logger.info("Voice pitch set to %s (%s)", pitch_val, spoken_desc)
    return f"Voice pitch updated to {spoken_desc}."


def speak(text: str, wait: bool = True):
    """Entry point for speech synthesis dispatch."""
    try:
        import assistant
        assistant.speak(text, wait=wait)
    except Exception as exc:
        logger.debug("assistant.speak unavailable, delegating to speak_edge: %s", exc)
        speak_edge(text)
