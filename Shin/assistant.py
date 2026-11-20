"""
assistant.py — Main runtime for Shin Voice Assistant
=======================================================

Usage:
    python assistant.py [--debug] [--no-wake]

Flags:
    --debug     Verbose logging to console
    --no-wake   Skip wake-word detection; listen continuously (useful for testing)

Wake word: "hey shin"  (configurable in .env → WAKE_WORD)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime

# Handle running in background (pythonw.exe) where stdout/stderr are None
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Ensure emojis print safely on Windows consoles (cp1252 → UTF-8)
if sys.platform == "win32":
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    try: sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pygame.*")

# ── Auto-reroute to supported virtual environment if started with Python >= 3.14 ──
if sys.version_info >= (3, 14):
    from pathlib import Path as _Path
    _candidates = [
        _Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "python.exe",
        _Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe",
    ]
    for _vpy in _candidates:
        if _vpy.exists():
            print(f"[Shin] Detected Python {sys.version.split()[0]} (PyAudio lacks 3.14 wheels). Rerouting to project virtualenv ({_vpy})...")
            try:
                import subprocess as _subp
                sys.exit(_subp.call([str(_vpy)] + sys.argv))
            except Exception:
                pass

# ── Self-healing dependency bootstrap ──────────────────────────────────────────
def _ensure_dependencies():
    """Ensure essential packages are installed with per-package error isolation."""
    from pathlib import Path
    import subprocess
    import sys

    if sys.version_info >= (3, 14):
        print(f"\n[Shin] Warning: Python {sys.version.split()[0]} detected.")
        print("[Shin] Core voice & AI libraries (PyAudio, PyTorch, Whisper, Vosk, MediaPipe) lack wheels for Python 3.14+.")
        print("[Shin] If you encounter wheel build errors, run Shin with Python 3.10 - 3.12 (Python 3.12 recommended).\n")

    req_file = Path(__file__).parent / "requirements.txt"
    critical = [
        ("schedule", "schedule"),
        ("speech_recognition", "SpeechRecognition"),
        ("colorama", "colorama"),
        ("dotenv", "python-dotenv"),
        ("psutil", "psutil"),
        ("pyautogui", "pyautogui"),
        ("requests", "requests"),
        ("edge_tts", "edge-tts"),
        ("comtypes", "comtypes"),
        ("pyttsx3", "pyttsx3"),
        ("websockets", "websockets"),
        ("pyperclip", "pyperclip"),
        ("pystray", "pystray"),
        ("PIL", "Pillow"),
        ("rapidfuzz", "rapidfuzz"),
        ("screen_brightness_control", "screen-brightness-control"),
        ("wikipedia", "wikipedia"),
        ("pyaudio", "PyAudio"),
    ]
    missing = []
    for mod_name, pkg_name in critical:
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pkg_name)

    if missing:
        print(f"\n[Shin] Missing required dependencies: {', '.join(missing)}")
        print(f"[Shin] Installing core packages into virtual environment ({sys.executable})...")
        for pkg in missing:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet"])
                print(f"[Shin] ✓ Installed {pkg}")
            except Exception as exc:
                print(f"[Shin] Notice: Could not install {pkg}: {exc}")

        # Install the remaining project dependencies from requirements.txt
        if req_file.exists():
            print("[Shin] Installing project dependencies from requirements.txt...")
            try:
                subprocess.call([sys.executable, "-m", "pip", "install", "-r", str(req_file)])
                print("[Shin] Dependencies installation complete!\n")
            except Exception as exc:
                print(f"[Shin] Requirements notice: {exc}")

_ensure_dependencies()

try:
    import schedule
except ImportError:
    schedule = None

import speech_recognition as sr
from colorama import Fore, Style, init as colorama_init
from dotenv import load_dotenv

load_dotenv()
colorama_init(autoreset=True)

# ── Project imports ────────────────────────────────────────────────────────────
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent
_CORE_DIR = _THIS_DIR / "core"

for _p in (str(_PROJECT_ROOT), str(_THIS_DIR), str(_CORE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import nlp as _nlp  # direct import for history tracking
from commands import dispatch, ConfirmationRequired, MissingArgument
import commands
import ui_server
import command_log as _cmd_log
import personality

logger = logging.getLogger("shin")

# LLM Router for fallback on unknown intents
try:
    try:
        from core.shin_agent import DualModeLLMRouter, HardwareProfile
    except ImportError:
        from shin_agent import DualModeLLMRouter, HardwareProfile
    _llm_router = DualModeLLMRouter(HardwareProfile())
except Exception as _e:
    logger.warning("Failed to init LLM router for fallback: %s", _e)
    _llm_router = None

# ═══════════════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════════════

WAKE_WORD:    str = os.getenv("WAKE_WORD", "hey shin").lower()
ASR_BACKEND:  str = os.getenv("ASR_BACKEND", "google").lower()   # "google" | "vosk" | "whisper"
TTS_BACKEND:  str = os.getenv("TTS_BACKEND", "edge").lower()        # "pyttsx3" | "edge" | "kokoro" | "lm_studio"
ASR_LANGUAGE: str = os.getenv("ASR_LANGUAGE", "en-IN")           # "en-IN" for Indian English/Hinglish, "hi-IN" for Hindi
EDGE_TTS_VOICE: str = os.getenv("EDGE_TTS_VOICE", "hi-IN-SwaraNeural") # Hindi female neural voice
EDGE_TTS_VOICE_EN: str = os.getenv("EDGE_TTS_VOICE_EN", "en-IN-NeerjaNeural") # Indian English female neural voice
EDGE_TTS_VOICE_MR: str = os.getenv("EDGE_TTS_VOICE_MR", "mr-IN-AarohiNeural") # Marathi female voice
KOKORO_VOICE: str = os.getenv("KOKORO_VOICE", "af_heart")        # Kokoro flagship smooth voice: af_heart, af_bella, af_nicole
LM_STUDIO_TTS_URL: str = os.getenv("LM_STUDIO_TTS_URL", "http://localhost:1234/v1")
LM_STUDIO_TTS_VOICE: str = os.getenv("LM_STUDIO_TTS_VOICE", "af_heart")
LM_STUDIO_TTS_MODEL: str = os.getenv("LM_STUDIO_TTS_MODEL", "kokoro-v1.0")
TTS_SPEED: float = float(os.getenv("TTS_SPEED", "1.0"))          # Smooth, natural conversational delivery
TTS_PITCH: str = os.getenv("TTS_PITCH", "+0Hz")                  # Balanced natural pitch (+0Hz for authentic native tone)
VOSK_MODEL:   str = os.getenv("VOSK_MODEL_PATH", "./vosk-model-small-en-us")
WHISPER_MODEL:str = os.getenv("WHISPER_MODEL", "base")
SR_ENERGY_THRESHOLD: int = int(os.getenv("SR_ENERGY_THRESHOLD", "0"))
USE_NOISE_REDUCTION: bool = os.getenv("USE_NOISE_REDUCTION", "true").lower() in ("true", "1", "t")

# Suppress noisy warnings from third-party libraries
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("phonemizer").setLevel(logging.ERROR)

# Caches for heavy libraries to avoid first-time lag in the listening loop
_nr_module = None
_np_module = None
_listening_paused = False
_bypass_wake_once = False
_recording_macro: dict | None = None
_active_training_session: dict | None = None

# ── Language State Persistence ────────────────────────────────────────────────
# User-set language preference: "english" | "hindi" | "hinglish" | "marathi"
try:
    from core.settings import get_language, set_language
except ImportError:
    from settings import get_language, set_language

def set_language_state(lang: str) -> None:
    """Update the persistent language preference used by TTS/LLM."""
    set_language(lang)

def get_language_state() -> str:
    """Get the current language preference."""
    return get_language()

# Kokoro TTS — pipeline cached globally so it's only loaded once
# Lock prevents concurrent calls from proactive chatter + command threads
_kokoro_pipeline = None
_kokoro_lock = threading.Lock()


def _pre_import_noise_reduction():
    """Import noisereduce and numpy in a background thread to prevent latency on first speech input."""
    global _nr_module, _np_module
    try:
        logger.debug("Pre-importing noise reduction libraries in background...")
        import numpy as np
        import noisereduce as nr
        _np_module = np
        _nr_module = nr
        logger.debug("Pre-import of noise reduction libraries completed successfully.")
    except Exception as exc:
        logger.warning("Failed to pre-import noise reduction dependencies: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════════
# TTS
# ═══════════════════════════════════════════════════════════════════════════════

_pyttsx3_voice_hindi = None
_pyttsx3_voice_english = None
_tts_queue = queue.Queue()

# Persistent thread pool for Google ASR — created once, reused every listen call
import concurrent.futures as _cf
_asr_executor = _cf.ThreadPoolExecutor(max_workers=1)


def _init_pyttsx3():
    global _pyttsx3_voice_hindi, _pyttsx3_voice_english
    if _pyttsx3_voice_english is None:
        import pyttsx3
        # Temporary engine instance to query system voices
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        
        pref_en = os.getenv("OFFLINE_VOICE_EN", "heera").strip().lower()
        pref_hi = os.getenv("OFFLINE_VOICE_HI", "kalpana").strip().lower()
        
        # ── 1. Find the Hindi Voice (Prefer Female) ──────────────────────────
        # Try preferred voice name first
        for v in voices:
            name_lower = v.name.lower()
            if pref_hi in name_lower:
                _pyttsx3_voice_hindi = v.id
                break

        # Try Kalpana first (female)
        if not _pyttsx3_voice_hindi:
            for v in voices:
                name_lower = v.name.lower()
                if "kalpana" in name_lower:
                    _pyttsx3_voice_hindi = v.id
                    break
                
        # Try any other Hindi voice except Hemant (to avoid male voice if another female is available)
        if not _pyttsx3_voice_hindi:
            for v in voices:
                name_lower = v.name.lower()
                is_hindi = "hindi" in name_lower
                is_english = "english" in name_lower or "heera" in name_lower or "ravi" in name_lower
                is_male = "hemant" in name_lower or "male" in name_lower
                if is_hindi and not is_english and not is_male:
                    _pyttsx3_voice_hindi = v.id
                    break
                    
        # Last resort: Hemant (male Hindi voice)
        if not _pyttsx3_voice_hindi:
            for v in voices:
                name_lower = v.name.lower()
                if "hemant" in name_lower:
                    _pyttsx3_voice_hindi = v.id
                    break

        # ── 2. Find the English Voice (Prefer Female Indian English first) ───
        # Try preferred voice name first
        for v in voices:
            name_lower = v.name.lower()
            if pref_en in name_lower:
                _pyttsx3_voice_english = v.id
                break

        # Try Heera first (female Indian English)
        if not _pyttsx3_voice_english:
            for v in voices:
                name_lower = v.name.lower()
                if "heera" in name_lower:
                    _pyttsx3_voice_english = v.id
                    break
                
        # Try any female en-IN voice except Ravi
        if not _pyttsx3_voice_english:
            for v in voices:
                name_lower = v.name.lower()
                if "en-in" in name_lower and "ravi" not in name_lower:
                    _pyttsx3_voice_english = v.id
                    break
                    
        # Try other standard female English voices (Zira, Hazel, Eva, etc.)
        if not _pyttsx3_voice_english:
            for v in voices:
                name_lower = v.name.lower()
                is_female = "zira" in name_lower or "hazel" in name_lower or "eva" in name_lower or "female" in name_lower
                is_hindi_like = "hindi" in name_lower or "kalpana" in name_lower or "hemant" in name_lower
                if is_female and not is_hindi_like:
                    _pyttsx3_voice_english = v.id
                    break
                    
        # Fallback to male Indian English (Ravi)
        if not _pyttsx3_voice_english:
            for v in voices:
                name_lower = v.name.lower()
                if "ravi" in name_lower:
                    _pyttsx3_voice_english = v.id
                    break

        # Fallback to other male English voices (David, George, Mark, etc.)
        if not _pyttsx3_voice_english:
            for v in voices:
                name_lower = v.name.lower()
                is_en = "english" in name_lower or "en-us" in name_lower or "david" in name_lower or "george" in name_lower or "mark" in name_lower
                is_hindi_like = "hindi" in name_lower or "kalpana" in name_lower or "hemant" in name_lower
                if is_en and not is_hindi_like:
                    _pyttsx3_voice_english = v.id
                    break
                    
            if not _pyttsx3_voice_english and voices:
                _pyttsx3_voice_english = voices[0].id
                
        if not _pyttsx3_voice_hindi:
            _pyttsx3_voice_hindi = _pyttsx3_voice_english

        # Log what was selected so offline fallback is transparent
        en_name = next((v.name for v in voices if v.id == _pyttsx3_voice_english), "unknown")
        hi_name = next((v.name for v in voices if v.id == _pyttsx3_voice_hindi), "unknown")
        logger.info("pyttsx3 voices selected — English (Hinglish): %s | Hindi (Native): %s", en_name, hi_name)


def is_text_hindi(text: str) -> bool:
    """Detect if the text contains actual Devanagari script (Hindi/Marathi).

    Only returns True for text written in Devanagari (e.g. "सुबह हो गई").
    Romanized Hinglish written in Latin letters (e.g. "Subah ho gayi") is
    intentionally treated as English so the English TTS voice reads it
    naturally instead of the Hindi voice mispronouncing Latin characters.
    """
    return any('\u0900' <= char <= '\u097f' for char in text)


def is_text_marathi(text: str) -> bool:
    """Detect if the text contains Devanagari Marathi.
    
    Only returns True if the text contains Devanagari characters and
    common Marathi words or the Marathi-specific character 'ळ'.
    """
    # First, must contain Devanagari
    if not any('\u0900' <= char <= '\u097f' for char in text):
        return False
        
    # Check for Marathi-specific letter 'ळ'
    if 'ळ' in text or 'ळी' in text or 'ळा' in text or 'ळे' in text:
        return True
        
    # Check for common Marathi Devanagari words
    marathi_words = {
        "आहे", "आहेत", "मी", "करू", "शकते", "झाली", "वाजले", "तारीख", 
        "तुमची", "तुमचे", "माझी", "माझे", "काय", "ते", "नमस्कार", "बोलेन", 
        "नको", "करा", "कसे", "कशी", "वार", "उघड"
    }
    # Check if any Marathi words exist in the text
    import re
    words = re.findall(r'[\u0900-\u097f]+', text)
    for word in words:
        if word in marathi_words:
            return True
            
    return False


def _speak_pyttsx3(text: str):
    import pyttsx3
    import comtypes
    
    # Initialize COM for the calling thread to prevent thread-safety errors
    comtypes.CoInitialize()
    try:
        _init_pyttsx3()
        engine = pyttsx3.init()
        
        # Load custom voice rate (scales with TTS_SPEED if not explicitly set)
        try:
            env_rate = os.getenv("OFFLINE_VOICE_RATE")
            if env_rate:
                rate = int(env_rate.strip())
            else:
                rate = int(150 * TTS_SPEED)
        except Exception:
            rate = int(150 * TTS_SPEED)
        engine.setProperty("rate", rate)
        
        # Respect user-set language preference
        lang = get_language_state()
        if lang in ("hindi", "marathi"):
            is_hindi = True
        elif lang == "english":
            is_hindi = False
        else:  # hinglish or default: auto-detect from script
            is_hindi = is_text_hindi(text)
        
        voice_id = _pyttsx3_voice_hindi if is_hindi else _pyttsx3_voice_english
        if voice_id:
            engine.setProperty("voice", voice_id)
        
        engine.say(text)
        engine.runAndWait()
        engine.stop()
        del engine
    finally:
        comtypes.CoUninitialize()


def _speak_edge(text: str):
    """Use Microsoft Edge TTS (online) via edge-tts library (async), played via pygame.
    
    Uses SSML prosody for more natural, warm delivery:
      - Slight pitch lift (+3Hz by default) adds warmth
      - Rate tuned to TTS_SPEED
      - Volume normalised so output is always consistent
    """
    try:
        try:
            import edge_tts
        except ImportError:
            logger.info("edge-tts library not found. Attempting to install edge-tts and pygame...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "edge-tts", "pygame", "--quiet"])
            import edge_tts

        import tempfile

        # Respect user-set language preference
        lang = get_language_state()
        if lang == "marathi":
            is_marathi = True
            is_hindi = False
            voice = EDGE_TTS_VOICE_MR
        elif lang == "hindi":
            is_marathi = False
            is_hindi = True
            voice = EDGE_TTS_VOICE
        elif lang == "english":
            is_marathi = False
            is_hindi = False
            voice = EDGE_TTS_VOICE_EN
        else:  # hinglish or default: auto-detect from script
            is_marathi = is_text_marathi(text)
            is_hindi = is_text_hindi(text) and not is_marathi
            if is_marathi:
                voice = EDGE_TTS_VOICE_MR
            else:
                # Default to Swara (native Indian Hindi/Hinglish) so Shin never sounds like a foreign accent
                voice = EDGE_TTS_VOICE

        async def _run():
            speed_percentage = int((TTS_SPEED - 1.0) * 100)
            rate_str = f"{'+' if speed_percentage >= 0 else ''}{speed_percentage}%"
            pitch_str = TTS_PITCH if TTS_PITCH else "+0Hz"

            async def _try_voice(v: str) -> str:
                communicate = edge_tts.Communicate(text, voice=v, rate=rate_str, pitch=pitch_str, volume="+0%")
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    p = f.name
                await asyncio.wait_for(communicate.save(p), timeout=15.0)
                return p

            try:
                return await _try_voice(voice)
            except Exception as _v_err:
                if voice != "en-IN-NeerjaNeural" and not is_hindi and not is_marathi:
                    logger.debug("Edge TTS voice '%s' failed, retrying with 'en-IN-NeerjaNeural': %s", voice, _v_err)
                    return await _try_voice("en-IN-NeerjaNeural")
                raise _v_err

        tmp_path = asyncio.run(_run())

        # Play with pygame — smooth buffer prevents audio starvation / stutter
        try:
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

                pygame.mixer.music.load(tmp_path)
                pygame.mixer.music.set_volume(1.0)
                pygame.mixer.music.play()
                # Wait for playback to finish
                while pygame.mixer.music.get_busy():
                    time.sleep(0.02)
                pygame.mixer.music.unload()
                played = True
            except Exception as _pyg_err:
                logger.debug("pygame audio playback failed: %s, falling back to MediaPlayer", _pyg_err)

            if not played:
                safe_path = tmp_path.replace("\\", "/")
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
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    except Exception as exc:
        logger.warning("edge-tts failed (%s), falling back to pyttsx3", exc)
        _speak_pyttsx3(text)


def _init_kokoro():
    """Load the Kokoro pipeline once and cache it globally. Must be called under _kokoro_lock."""
    global _kokoro_pipeline
    if _kokoro_pipeline is None:
        # ── RAM optimization: limit PyTorch threads ────────────────────────────
        # PyTorch defaults to 1 thread per CPU core, each consuming ~10-20MB.
        # Kokoro only needs 1-2 threads for real-time inference on a single voice.
        try:
            import torch
            torch.set_num_threads(2)
            torch.set_num_interop_threads(1)
        except Exception:
            pass

        from kokoro import KPipeline
        # Try loading offline first for maximum speed (prevents 20s Hugging Face check lag)
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        # Apply HF_TOKEN if set in .env to avoid unauthenticated rate-limit warnings
        hf_token = os.getenv("HF_TOKEN", "").strip()
        if hf_token:
            os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token
            os.environ["HF_TOKEN"] = hf_token
        try:
            # lang_code='a' = American English — reads Hinglish/Marathi (Latin script) naturally
            _kokoro_pipeline = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
        except Exception as offline_exc:
            logger.info("Local Kokoro cache not found or offline load failed (%s). Attempting online check...", offline_exc)
            os.environ["HF_HUB_OFFLINE"] = "0"
            _kokoro_pipeline = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
            os.environ["HF_HUB_OFFLINE"] = "1"
        logger.info("Kokoro TTS pipeline loaded (voice: %s)", KOKORO_VOICE)



def _speak_kokoro(text: str):
    """Synthesise speech with Kokoro TTS (offline, no API key needed) and play via pygame."""
    try:
        import soundfile as sf
        import tempfile
        import numpy as np
        import queue
        import threading
        import re

        # Split text into sentences to synthesize and play them sentence-by-sentence.
        # This dramatically reduces time-to-first-speech for long paragraphs.
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        if not sentences:
            return

        audio_queue = queue.Queue(maxsize=2)  # buffer up to 2 sentences

        def producer():
            global _kokoro_pipeline
            try:
                with _kokoro_lock:
                    _init_kokoro()
                    for sentence in sentences:
                        # Clean multiple hyphens while keeping commas and periods for natural speech pauses
                        clean_sentence = re.sub(r'[\-—]+', ' ', sentence).strip()
                        if not clean_sentence:
                            continue
                        
                        audio_chunks = []
                        for _, _, audio in _kokoro_pipeline(clean_sentence, voice=KOKORO_VOICE, speed=TTS_SPEED):
                            audio_chunks.append(audio)
                        
                        if audio_chunks:
                            full_audio = np.concatenate(audio_chunks) if len(audio_chunks) > 1 else audio_chunks[0]
                            audio_queue.put(full_audio)
            except Exception as e:
                logger.error("Kokoro background synthesis failed: %s", e)
                # Reset the pipeline so it can be re-initialized on next attempt
                _kokoro_pipeline = None
            finally:
                audio_queue.put(None)  # Sentinel to end playback loop

        # Start background generation thread
        threading.Thread(target=producer, daemon=True).start()

        # Initialize Pygame mixer once for this stream
        import pygame
        init_info = pygame.mixer.get_init()
        if init_info:
            if init_info[0] != 24000:
                pygame.mixer.quit()
                pygame.mixer.init(frequency=24000)
        else:
            pygame.mixer.init(frequency=24000)

        # Consume and play sentences as they are synthesized
        played_any = False
        while True:
            full_audio = audio_queue.get()
            if full_audio is None:
                break

            played_any = True
            # Write to a temp WAV file and play
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name
            try:
                sf.write(tmp_path, full_audio, 24000)
                pygame.mixer.music.load(tmp_path)
                pygame.mixer.music.set_volume(0.95)  # Consistent volume, matches edge-tts
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
                pygame.mixer.music.unload()
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        # If the producer crashed and produced nothing, fall back to edge TTS so
        # Shin never silently fails (e.g. Kokoro __reduce_cython__ error on startup)
        if not played_any:
            logger.warning("Kokoro produced no audio (pipeline error). Falling back to edge TTS.")
            _speak_edge(text)

    except Exception as exc:
        logger.warning("Kokoro TTS failed (%s), falling back to pyttsx3", exc)
        _speak_pyttsx3(text)


def _pre_warm_kokoro():
    """Pre-load the Kokoro pipeline in a background thread to avoid first-speak lag."""
    try:
        logger.info("Pre-warming Kokoro TTS pipeline in background...")
        _init_kokoro()
        logger.info("Kokoro TTS pipeline ready.")
    except Exception as exc:
        logger.warning("Failed to pre-warm Kokoro: %s", exc)


def _clean_text_for_speech(text: str) -> str:
    if not text:
        return ""
        
    # Strip markdown bold/italic/code syntax (*, _, `)
    text = re.sub(r'[\*\_\`]+', '', text)
    # Remove markdown headers and list bullets (e.g. # Header, • bullet, - item)
    text = re.sub(r'^[#•\-\*\+]\s+', '', text, flags=re.MULTILINE)
    # Strip web URLs (e.g. https://example.com)
    text = re.sub(r'https?://\S+', '', text)
    
    # Normalize speed/distance unit symbols before replacing slashes
    text = re.sub(r'(?<=\d)\s*(?:km/h|km/hr|kmh)\b', ' kilometers per hour', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:km/h|km/hr|kmh)\b', 'kilometers per hour', text, flags=re.IGNORECASE)
    
    # Normalize degree symbols and slash so they aren't read literally
    text = re.sub(r'\b(\d+)\s*°[Cc]\b', r'\1 degrees Celsius', text)
    text = re.sub(r'\b(\d+)\s*°\b', r'\1 degrees', text)
    text = text.replace("°C", " degrees Celsius").replace("°", " degrees")
    # Clean pipes, ampersands, and slash characters that cause TTS hesitation
    text = text.replace("|", ", ")
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = text.replace("\\", " ")

    # Clean numbers in parentheses like '(1172)' or browser badge numbers
    text = re.sub(r'\(\s*\d+\s*\)', '', text)
    text = re.sub(r'[\(\)\[\]\{\}]', ', ', text)
    text = re.sub(r'[\\_~^]', ' ', text)

    # Remove emojis (non-BMP characters like 😊, ❤️)
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    # Remove common BMP symbols and emoticons (e.g. hearts, smiley faces, arrows)
    text = re.sub(r'[\u2000-\u3300]', '', text)
    
    # Normalize multiple dots / hyphens / commas into natural pauses
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'\-{2,}', ', ', text)
    text = re.sub(r'\s*,\s*', ', ', text)
    text = re.sub(r'(?:,\s*)+,', ', ', text)
    
    # Enforce female grammar as safety net
    try:
        text = _nlp.enforce_female_grammar(text)
    except Exception:
        pass

    # Clean up extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _tts_worker():
    while True:
        text = _tts_queue.get()
        if text is None:
            break
        print(f"\n{Fore.CYAN}🤖 Shin:{Style.RESET_ALL} {text}")
        cleaned_text = _clean_text_for_speech(text)
        try:
            from Shin.core import island_bridge
            island_bridge.show_speaking(cleaned_text)
        except Exception:
            pass
        try:
            from Shin.core import mate_bridge
            mate_bridge.MateBridge.get().sync_speech(cleaned_text)
        except Exception:
            pass
        ui_server.UIBridge.send_state("speaking")
        try:
            # Check language state: LM Studio/Kokoro only support English voices
            # Fall back to Edge TTS for Hindi/Marathi which have native neural voices
            lang = get_language_state()
            if TTS_BACKEND in ("lm_studio", "kokoro") and lang in ("hindi", "marathi"):
                logger.debug("Language is %s but %s backend only has English voices; falling back to Edge TTS", lang, TTS_BACKEND)
                _speak_edge(cleaned_text)
            elif TTS_BACKEND == "lm_studio":
                # Import and use LM Studio TTS from core.tts
                from core.tts import speak_lm_studio
                speak_lm_studio(cleaned_text)
            elif TTS_BACKEND == "kokoro":
                _speak_kokoro(cleaned_text)
            elif TTS_BACKEND == "edge":
                _speak_edge(cleaned_text)
            else:
                _speak_pyttsx3(cleaned_text)
        except Exception as exc:
            logger.error("TTS error: %s", exc)
            ui_server.UIBridge.send_state("error")
            time.sleep(1.0)
        if _listening_paused:
            ui_server.UIBridge.send_state("standby")
            try:
                from Shin.core import mate_bridge
                mate_bridge.MateBridge.get().set_state("standby")
            except Exception:
                pass
        else:
            ui_server.UIBridge.send_state("idle")
            try:
                from Shin.core import mate_bridge
                mate_bridge.MateBridge.get().set_state("idle")
            except Exception:
                pass
        _tts_queue.task_done()

_thread_local_sink = threading.local()

def speak(text: str, wait: bool = True):
    """Queue text to be spoken. If wait is True, block until finished."""
    # Thread-safe capture hook for sub-workers
    sink = getattr(_thread_local_sink, "capture_fn", None)
    if sink is not None:
        try:
            sink(text)
        except Exception:
            pass
        return

    _tts_queue.put(text)
    if wait:
        # Use Queue.join() in a daemon thread so we can apply a 60-second watchdog
        # without blocking the listen loop indefinitely if TTS stalls.
        done_event = threading.Event()
        def _join_worker():
            _tts_queue.join()
            done_event.set()
        threading.Thread(target=_join_worker, daemon=True).start()
        if not done_event.wait(timeout=60):
            logger.warning("TTS watchdog: queue stalled beyond 60s, forcing unblock.")



# ═══════════════════════════════════════════════════════════════════════════════
# ASR
# ═══════════════════════════════════════════════════════════════════════════════

_vosk_model = None
_vosk_rec = None


def _init_vosk():
    global _vosk_model, _vosk_rec
    if _vosk_model is None:
        from vosk import Model, KaldiRecognizer
        
        # Determine model path dynamically based on ASR_LANGUAGE if it exists in the languages directory
        lang = ASR_LANGUAGE.lower()
        model_dir = None
        
        # Candidate lists (ordered by preference: small models first, then large ones)
        hi_candidates = ["./languages/vosk-model-small-hi-0.22", "./languages/vosk-model-hi-0.22"]
        en_in_candidates = ["./languages/vosk-model-small-en-in-0.4", "./languages/vosk-model-en-in-0.5"]
        en_candidates = ["./languages/vosk-model-small-en-us-0.15", "./languages/vosk-model-en-us-0.22"]
        
        if "hi" in lang:
            for p in hi_candidates:
                if os.path.isdir(p):
                    model_dir = p
                    break
        elif "en-in" in lang:
            for p in en_in_candidates:
                if os.path.isdir(p):
                    model_dir = p
                    break
        elif "en-us" in lang or "en" in lang:
            for p in en_candidates:
                if os.path.isdir(p):
                    model_dir = p
                    break
            
        if model_dir and os.path.isdir(model_dir):
            selected_model = model_dir
        else:
            selected_model = VOSK_MODEL

        if not os.path.isdir(selected_model):
            raise FileNotFoundError(
                f"Vosk model not found at '{selected_model}'.\n"
                "Download a model from https://alphacephei.com/vosk/models\n"
                "and set VOSK_MODEL_PATH in your .env file."
            )

        # Resolve double-nested Vosk models
        if not os.path.exists(os.path.join(selected_model, "am")) and not os.path.exists(os.path.join(selected_model, "conf")):
            try:
                subdirs = [os.path.join(selected_model, d) for d in os.listdir(selected_model) if os.path.isdir(os.path.join(selected_model, d))]
                for sd in subdirs:
                    if os.path.exists(os.path.join(sd, "am")) or os.path.exists(os.path.join(sd, "conf")):
                        selected_model = sd
                        break
            except Exception as exc:
                logger.warning("Error checking nested Vosk directory structure: %s", exc)

        _vosk_model = Model(selected_model)
        _vosk_rec = KaldiRecognizer(_vosk_model, 16000)


_whisper_model = None

def _init_whisper():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        _whisper_model = whisper.load_model(WHISPER_MODEL)


def _pre_load_vosk():
    """Load the Vosk model in a background thread to prevent first-time voice latency."""
    try:
        logger.info("Pre-loading Vosk model in background...")
        _init_vosk()
        logger.info("Vosk model pre-loaded successfully.")
    except Exception as exc:
        logger.warning("Failed to pre-load Vosk model: %s", exc)


def _pre_load_whisper():
    """Load the Whisper model in a background thread."""
    try:
        logger.info("Pre-loading Whisper model in background...")
        _init_whisper()
        logger.info("Whisper model pre-loaded successfully.")
    except Exception as exc:
        logger.warning("Failed to pre-load Whisper model: %s", exc)


_ollama_process = None

def _start_ollama():
    """Start the local Ollama API server in the background if a model is configured."""
    global _ollama_process
    ollama_model = os.getenv("OLLAMA_MODEL", "").strip()
    if ollama_model:
        try:
            import shutil
            import subprocess
            if not shutil.which("ollama"):
                logger.debug("Ollama executable not found in system PATH; skipping automatic server launch.")
                return
            logger.info("Starting Ollama background server...")
            # Set keep alive to 1 minute to free up memory quickly after use
            env = os.environ.copy()
            if "OLLAMA_KEEP_ALIVE" not in env:
                env["OLLAMA_KEEP_ALIVE"] = "1m"
            # CREATE_NO_WINDOW prevents a visible terminal window from spawning on Windows
            _ollama_process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            )
            # Warm up the model in the background: send a dummy request so the
            # first real voice command doesn't trigger a slow cold-model reload.
            def _warmup_ollama(model_str: str):
                first_model = model_str.split(",")[0].strip()
                if not first_model:
                    return
                import time as _time
                # Give the server a few seconds to be ready
                _time.sleep(5)
                try:
                    import requests as _warmup_req
                    _warmup_req.post(
                        "http://localhost:11434/api/generate",
                        json={"model": first_model, "prompt": "hi", "stream": False},
                        timeout=(3.0, 30.0),
                    )
                    logger.info("Ollama model '%s' warmed up successfully.", first_model)
                except Exception as warmup_exc:
                    logger.debug("Ollama warmup ping failed (non-critical): %s", warmup_exc)
            import threading as _threading
            _threading.Thread(
                target=_warmup_ollama,
                args=(ollama_model,),
                daemon=True,
                name="OllamaWarmup"
            ).start()
        except Exception as exc:
            logger.warning("Could not launch Ollama automatically: %s", exc)

def _stop_ollama():
    """Stop the background Ollama API server."""
    global _ollama_process
    if _ollama_process:
        try:
            import subprocess
            logger.info("Stopping Ollama background server...")
            _ollama_process.terminate()
            try:
                _ollama_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _ollama_process.kill()
        except Exception as exc:
            logger.warning("Error stopping Ollama server: %s", exc)

_recognizer = None
_ambient_calibrated = False

_DANGLING_COMMAND_PATTERNS = [
    re.compile(r"\b(?:can\s+you\s+|please\s+)?(?:open|launch|start)(?:\s+(?:the|a|an))?$", re.IGNORECASE),
    re.compile(r"\b(?:can\s+you\s+|please\s+)?(?:play)(?:\s+(?:the|a|an))?$", re.IGNORECASE),
    re.compile(r"\b(?:can\s+you\s+|please\s+)?(?:search|find)(?:\s+for)?(?:\s+(?:the|a|an))?$", re.IGNORECASE),
    re.compile(r"\b(?:can\s+you\s+|please\s+)?(?:go\s+to|navigate\s+to)(?:\s+the)?$", re.IGNORECASE),
    re.compile(r"\b(?:can\s+you\s+|please\s+)?(?:click|tap)(?:\s+on)?(?:\s+the)?$", re.IGNORECASE),
    re.compile(r"\b(?:tell\s+me|explain)(?:\s+about)?(?:\s+the)?$", re.IGNORECASE),
    re.compile(r"\b(?:what\s+is|what\'s)(?:\s+(?:the|a))?$", re.IGNORECASE),
    re.compile(r"\b(?:how\s+to)(?:\s+the)?$", re.IGNORECASE),
    re.compile(r"^(?:open|play|search|launch|start|find|go\s+to)$", re.IGNORECASE),
]


def is_dangling_utterance(text: str) -> bool:
    """Detect if the user spoke an incomplete command ending in an open verb or preposition."""
    t = text.strip()
    if not t:
        return False
    return any(pat.search(t) for pat in _DANGLING_COMMAND_PATTERNS)


def _normalize_recognized_name(text: str) -> str:
    """Normalize common ASR phonetic mishearings of the assistant's name 'Shin'.
    
    Google Speech Recognition (especially en-IN) frequently hears 'Shin' as:
      - 'singh', 'sin', 'seen', 'sheen', 'chin', 'sing', 'scene', 'in'
    We convert these to 'shin' when used as an address / wake word, while
    safely preserving real artist names (e.g. 'arijit singh') and verbs ('sing a song').
    """
    if not text:
        return text

    t = text.strip()

    # 1. Normalize leading 'in' when followed by a command verb:
    # e.g. "in close the youtube" -> "shin close the youtube"
    t = re.sub(
        r"^in\s+(?=(?:close|open|play|stop|volume|search|turn|set|karo|kar|batao|sunao|kholo|chaloo?)\b)",
        "shin ",
        t,
        flags=re.IGNORECASE
    )

    # 2. Normalize leading address variants:
    # e.g. "singh guitar open karo" -> "shin guitar open karo"
    # e.g. "sing koi gana lagao" -> "shin koi gana lagao"
    # e.g. "achcha seen aaj din kya hai" -> "achcha shin aaj din kya hai"
    # e.g. "hey seen", "hey sin", "hey singh" -> "hey shin"
    # e.g. "sin volume badhao" -> "shin volume badhao"
    if not re.match(r"^sing\s+(?:a\s+song|me\s+a\s+song|for\s+me|song)\b", t, re.IGNORECASE):
        prefix_pattern = (
            r"^(?:(?:ach+c?h*a|ac+h*c?h*a|arey?|oye|suno|sun|hey?|heyy|hello|hi|please|plz|ok|okay)?\s*)"
            r"\b(singh|sin|seen|sheen|chin|shing|sing|scene)\b"
        )
        def _replace_prefix(m):
            full_match = m.group(0)
            target = m.group(1)
            return full_match[:-len(target)] + "shin"

        t = re.sub(prefix_pattern, _replace_prefix, t, count=1, flags=re.IGNORECASE)

    # 3. Trailing address: e.g. "kya kar rahi ho singh" -> "kya kar rahi ho shin"
    if not re.search(r"\b(?:arijit|honey|mika|jagjit|ranveer|ranbir|daljit|diljit|amrinder|guru|chandan)\s+singh\b", t, re.IGNORECASE):
        t = re.sub(
            r"\b(singh|sin|seen|sheen|chin|shing)\s*$",
            "shin",
            t,
            flags=re.IGNORECASE
        )

    return t


def listen_once(timeout: int = 5, phrase_time_limit: int = 10, bypass_voice_auth: bool = False) -> str | None:
    """
    Record from the microphone and return recognised text (or None on failure).
    Uses the ASR backend configured in .env.
    """
    _tts_queue.join()  # Prevent listening while Shin is still speaking

    global _recognizer, _ambient_calibrated
    if _recognizer is None:
        _recognizer = sr.Recognizer()
        # 2.0s allows natural breathing pauses and thought-retrieval without cutting off half-sentence
        _recognizer.pause_threshold = 2.0
        # Responsive speech onset detection
        _recognizer.phrase_threshold = 0.2
        # Retain trailing audio so final word syllables (like '-tube' in 'youtube') are never clipped
        _recognizer.non_speaking_duration = 0.8
        # Gentle dynamic multiplier prevents vocal energy spikes from elevating threshold
        _recognizer.dynamic_energy_ratio = 1.15
        _recognizer.dynamic_energy_adjustment_damping = 0.2

    r = _recognizer

    # Noise-reduction & Energy Threshold configuration
    if SR_ENERGY_THRESHOLD > 0:
        # Use a fixed, user-defined threshold for noisy environments
        r.energy_threshold = SR_ENERGY_THRESHOLD
        r.dynamic_energy_threshold = False
        logger.debug("Using fixed energy threshold: %d", r.energy_threshold)
    else:
        # Use dynamic threshold adjustment
        r.dynamic_energy_threshold = True
        # Clamp dynamic threshold between 150 and 500 to guarantee that normal vocal speech
        # (300-1500 RMS) is always recognized as speech and never treated as silence
        if isinstance(r.energy_threshold, (int, float)):
            r.energy_threshold = min(max(r.energy_threshold, 150), 500)
        logger.debug("Using dynamic energy threshold: %s", r.energy_threshold)

    with sr.Microphone(sample_rate=16000) as source:
        if not _ambient_calibrated and SR_ENERGY_THRESHOLD == 0:
            try:
                r.adjust_for_ambient_noise(source, duration=0.3)
                if isinstance(r.energy_threshold, (int, float)):
                    r.energy_threshold = min(max(r.energy_threshold, 150), 500)
                _ambient_calibrated = True
            except Exception:
                pass

        try:
            audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            raw_audio = audio
        except sr.WaitTimeoutError:
            return None

    # ─── NEW: Noise Reduction Step ──────────────────────────────────────────────
    if USE_NOISE_REDUCTION:
        try:
            if _np_module is not None and _nr_module is not None:
                np = _np_module
                nr = _nr_module
            else:
                import numpy as np
                import noisereduce as nr


            # Convert raw audio data to numpy array
            samples = np.frombuffer(audio.get_raw_data(), dtype=np.int16)

            if len(samples) >= 1024:
                # Perform gentle noise reduction. Setting prop_decrease=0.3 preserves
                # soft vocal formants, consonants, and Hindi speech clarity (0.8 was too aggressive).
                reduced_noise_samples = nr.reduce_noise(y=samples, sr=audio.sample_rate, prop_decrease=0.3)

                # Convert back to raw bytes
                new_raw_data = reduced_noise_samples.astype(np.int16).tobytes()

                # Create a new AudioData object with the cleaned audio
                audio = sr.AudioData(new_raw_data, audio.sample_rate, audio.sample_width)
                logger.debug("Applied noise reduction to audio input.")

        except ImportError:
            logger.warning(
                "Noise reduction is enabled but dependencies are missing. "
                "Please run: pip install noisereduce scipy"
            )
        except Exception as exc:
            logger.warning("Noise reduction failed: %s", exc)

    result_text = None
    try:
        if ASR_BACKEND == "whisper":
            _init_whisper()
            import numpy as np
            raw_bytes = audio.get_raw_data(convert_rate=16000, convert_width=2)
            # Whisper expects float32 bounded to -1.0 to 1.0
            audio_np = np.frombuffer(raw_bytes, np.int16).astype(np.float32) / 32768.0
            if ASR_LANGUAGE.lower() == "auto":
                result = _whisper_model.transcribe(audio_np, fp16=False)  # Let Whisper auto-detect the language
            else:
                whisper_lang = ASR_LANGUAGE.split("-")[0] if ASR_LANGUAGE else "en"
                result = _whisper_model.transcribe(audio_np, language=whisper_lang, fp16=False)
            result_text = result.get("text", "").strip() or None
        elif ASR_BACKEND == "vosk":
            _init_vosk()
            import json as _json
            from vosk import KaldiRecognizer
            wav_data = audio.get_wav_data(convert_rate=16000, convert_width=2)
            _vosk_rec.AcceptWaveform(wav_data)
            raw_result = _vosk_rec.Result()
            if raw_result:
                result = _json.loads(raw_result)
                result_text = result.get("text", "").strip() or None
        else:  # "google" (default)
            try:
                def _run_google_asr():
                    lang = ASR_LANGUAGE if ASR_LANGUAGE and ASR_LANGUAGE.lower() != "auto" else "en-IN"
                    return r.recognize_google(audio, language=lang).lower()

                # Reuse the module-level executor — no per-call creation/teardown overhead
                future = _asr_executor.submit(_run_google_asr)
                result_text = future.result(timeout=15)
            except sr.UnknownValueError:
                # Google heard nothing / couldn't recognise speech — this is
                # NOT an offline error. Just return None, don't load Vosk.
                result_text = None
            except (sr.RequestError, TimeoutError, Exception) as google_exc:
                # RequestError  → network/API unavailable → fall back to Vosk
                # TimeoutError  → future timed out        → fall back to Vosk
                # Other unknown → fall back as safety net
                logger.warning("Google ASR failed (possibly offline). Falling back to offline Vosk: %s", google_exc)
                try:
                    _init_vosk()
                    import json as _json
                    wav_data = audio.get_wav_data(convert_rate=16000, convert_width=2)
                    _vosk_rec.AcceptWaveform(wav_data)
                    raw_result = _vosk_rec.Result()
                    if raw_result:
                        result = _json.loads(raw_result)
                        result_text = result.get("text", "").strip() or None
                except Exception as vosk_exc:
                    logger.error("Vosk offline fallback failed: %s", vosk_exc)
                    result_text = None

    except Exception as exc:
        logger.debug("ASR error: %s", exc)
        return None

    if result_text:
        result_text = _normalize_recognized_name(result_text)
        try:
            import voice_auth
            if voice_auth.is_enabled() and voice_auth.has_profile() and not bypass_voice_auth:
                # Strictly verify voice for all commands (including profile deletion)
                # to prevent strangers from spoofing or resetting the owner's voice fingerprint.
                if not voice_auth.verify_voice(raw_audio):
                    logger.info("Voice auth rejected speaker. Ignoring: '%s'", result_text)
                    return None
        except Exception as exc:
            logger.warning("Voice verification error: %s", exc)
            
    return result_text


# ═══════════════════════════════════════════════════════════════════════════════
# Wake-word detection
# ═══════════════════════════════════════════════════════════════════════════════

def wait_for_wake_word() -> bool:
    """
    Block until the wake word is heard (or Ctrl+C).
    Returns True when wake word detected.
    """
    print(
        f"{Fore.YELLOW}👂 Waiting for wake word: "
        f"{Fore.WHITE}\"{WAKE_WORD}\"{Style.RESET_ALL} ..."
    )
    while True:
        text = listen_once(timeout=8, phrase_time_limit=4, bypass_voice_auth=True)
        if text and WAKE_WORD in text.lower():
            logger.debug("Wake word detected in: %r", text)
            return True


# ═══════════════════════════════════════════════════════════════════════════════
# Confirmation flow
# ═══════════════════════════════════════════════════════════════════════════════

def ask_confirmation(prompt: str) -> bool:
    """
    Ask the user for verbal or keyboard confirmation.
    Returns True if the user says/types yes/confirm/proceed.
    """
    speak(f"{prompt} Say yes to confirm or no to cancel.")
    print(f"{Fore.YELLOW}  → {prompt} (yes/no){Style.RESET_ALL}")

    # Confirmations must be strictly verified when voice auth is active
    answer = listen_once(timeout=8, phrase_time_limit=4, bypass_voice_auth=False)
    if answer:
        answer = answer.lower().strip()
        if any(w in answer for w in ("yes", "confirm", "proceed", "sure", "do it", "yep", "yeah")):
            return True
        if any(w in answer for w in ("no", "cancel", "stop", "nope", "don't")):
            return False
    # Keyboard fallback
    try:
        key = input(f"  [Keyboard fallback] Confirm? (y/n): ").strip().lower()
        return key.startswith("y")
    except EOFError:
        return False
        
        
def ask_missing_argument(prompt: str) -> str | None:
    """
    Ask the user for missing information to complete a command.
    """
    speak(prompt)
    print(f"{Fore.YELLOW}  → {prompt}{Style.RESET_ALL}")

    answer = listen_once(timeout=10, phrase_time_limit=15)
    if answer:
        return answer.strip()
        
    # Keyboard fallback
    try:
        key = input(f"  [Keyboard fallback] {prompt} ").strip()
        return key if key else None
    except EOFError:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Scheduler thread
# ═══════════════════════════════════════════════════════════════════════════════

def _scheduler_thread():
    while True:
        if schedule is not None:
            try:
                schedule.run_pending()
            except Exception as exc:
                logger.debug("Scheduler execution error: %s", exc)
        time.sleep(0.5)


# Track startup time so the internet monitor ignores the first 60 seconds
_startup_time: float = time.monotonic()
_INTERNET_MONITOR_GRACE_SECONDS: float = 60.0


def _internet_monitor_thread():
    import socket

    def _is_online():
        try:
            socket.setdefaulttimeout(3)
            # Connect to a public DNS server
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("1.1.1.1", 53))
            s.close()
            return True
        except Exception:
            return False

    was_online = _is_online()
    logger.info("Internet monitor started. Initial state: %s", "online" if was_online else "offline")

    while True:
        time.sleep(10)
        is_now_online = _is_online()
        # Only trigger standby on offline→online transition, AND only after the
        # startup grace period has elapsed (prevents forcing standby on boot when
        # the machine is already connected to the internet).
        elapsed = time.monotonic() - _startup_time
        if is_now_online and not was_online and elapsed >= _INTERNET_MONITOR_GRACE_SECONDS:
            logger.info("Internet connection detected. Putting Shin in standby mode.")
            global _listening_paused
            _listening_paused = True
            try:
                # Update UI state to standby
                ui_server.UIBridge.send_state("standby")
            except Exception as exc:
                logger.error("Failed to update standby state: %s", exc)
        was_online = is_now_online


# ═══════════════════════════════════════════════════════════════════════════════
# System Tray & Windows Startup
# ═══════════════════════════════════════════════════════════════════════════════

def _get_startup_file_path() -> str:
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup\ShinAssistant.vbs")

def _is_in_startup() -> bool:
    return os.path.exists(_get_startup_file_path())

def _toggle_startup(icon, item):
    path = _get_startup_file_path()
    if _is_in_startup():
        try:
            os.remove(path)
            logger.info("Removed Shin from Windows Startup.")
        except OSError:
            pass
    else:
        try:
            # Find the pythonw.exe in the virtual environment if it exists, otherwise fall back to sys.executable
            script_path = os.path.abspath(__file__)
            work_dir = os.path.dirname(script_path)
            venv_pythonw = os.path.join(work_dir, ".venv", "Scripts", "pythonw.exe")
            if os.path.exists(venv_pythonw):
                python_exe = venv_pythonw
            else:
                python_exe = sys.executable.replace("python.exe", "pythonw.exe")
            vbs_content = (
                f'Set objShell = CreateObject("WScript.Shell")\n'
                f'objShell.CurrentDirectory = "{work_dir}"\n'
                f'objShell.Run """{python_exe}"" ""{script_path}""", 0, False\n'
            )
            with open(path, "w", encoding="utf-8") as f:
                f.write(vbs_content)
            logger.info("Added Shin to Windows Startup.")
        except Exception as exc:
            logger.error("Failed to add to startup: %s", exc)

def set_voice_pitch(pitch_val: str, label: str = "") -> str:
    """Dynamically update Shin's TTS voice pitch, persist to .env, and notify user."""
    global TTS_PITCH
    TTS_PITCH = pitch_val
    os.environ["TTS_PITCH"] = pitch_val
    try:
        from core import tts as _tts_mod
        _tts_mod.TTS_PITCH = pitch_val
    except Exception:
        pass
    try:
        env_file = Path(__file__).parent / ".env"
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
    return f"Voice pitch set to {spoken_desc}."


def _create_tray_icon():
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        logger.warning("pystray or Pillow not installed. System tray icon disabled.")
        return None

    # Create a simple cyan circle icon
    image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse((8, 8, 56, 56), fill=(0, 229, 255))

    def on_quit(icon, item):
        icon.stop()
        print(f"\n{Fore.RED}Shin offline (Closed from Tray).{Style.RESET_ALL}")
        _shutdown_assistant()
        os._exit(0)

    def on_toggle_pause(icon, item):
        global _listening_paused
        _listening_paused = not _listening_paused
        if _listening_paused:
            speak("Standing by.")
        else:
            speak("I am back online.")

    def on_toggle_orb(icon, item):
        try:
            import ui_server
            ui_server.UIBridge.set_orb_visibility(not ui_server.UIBridge.orb_visible)
        except Exception as exc:
            logger.error("Failed to toggle orb: %s", exc)

    def on_open_tokens(icon, item):
        try:
            import webbrowser
            import ui_server
            webbrowser.open(f"http://127.0.0.1:{ui_server.HTTP_PORT}/tokens.html")
        except Exception as exc:
            logger.error("Failed to open API Tokens dashboard: %s", exc)

    def on_toggle_gestures(icon, item):
        import gestures
        active = gestures.toggle_gesture_control()
        if active:
            icon.notify("Hand Gesture Control Enabled", "Shin Gestures")
        else:
            icon.notify("Hand Gesture Control Disabled", "Shin Gestures")

    def on_open_web_dashboard(icon, item):
        try:
            import webbrowser
            import ui_server
            webbrowser.open(f"http://127.0.0.1:{ui_server.HTTP_PORT}")
        except Exception as exc:
            logger.error("Failed to open Web Dashboard: %s", exc)

    def on_reset_voice(icon, item):
        try:
            import voice_auth
            msg = voice_auth.delete_profile()
            icon.notify(msg, "Shin Voice Profile")
        except Exception as exc:
            icon.notify(f"Failed to reset profile: {exc}", "Shin Voice Profile")

    def on_set_pitch(pitch_val: str, label: str, icon_ref=None):
        msg = set_voice_pitch(pitch_val, label)
        speak(msg, wait=False)
        try:
            if icon_ref:
                icon_ref.notify(msg, "Shin Voice Pitch")
        except Exception:
            pass

    def make_pitch_item(pitch_val: str, label: str):
        return pystray.MenuItem(
            label,
            lambda icon, item: on_set_pitch(pitch_val, label, icon_ref=icon),
            checked=lambda item: TTS_PITCH == pitch_val or (pitch_val == "+0Hz" and TTS_PITCH in ("+0Hz", "0Hz", "")),
            radio=True
        )

    pitch_submenu = pystray.Menu(
        make_pitch_item("+30Hz", "Very High (+30Hz)"),
        make_pitch_item("+15Hz", "High (+15Hz)"),
        make_pitch_item("+8Hz",  "Warm / Soft (+8Hz)"),
        make_pitch_item("+0Hz",  "Default / Natural (+0Hz)"),
        make_pitch_item("-10Hz", "Low (-10Hz)"),
        make_pitch_item("-20Hz", "Very Deep (-20Hz)"),
    )

    menu = pystray.Menu(
        pystray.MenuItem("Show 3D Orb", on_toggle_orb, checked=lambda item: ui_server.UIBridge.orb_visible, default=True),
        pystray.MenuItem("Open Web Dashboard", on_open_web_dashboard),
        pystray.MenuItem("Pause Listening", on_toggle_pause, checked=lambda item: _listening_paused),
        pystray.MenuItem("Voice Pitch", pitch_submenu),
        pystray.MenuItem("Hand Gesture Control", on_toggle_gestures, checked=lambda item: sys.modules.get("gestures") and sys.modules["gestures"].is_gesture_active()),
        pystray.MenuItem("Run on Startup", _toggle_startup, checked=lambda item: _is_in_startup()),
        pystray.MenuItem("API Tokens", on_open_tokens),
        pystray.MenuItem("Reset Voice Profile", on_reset_voice),
        pystray.MenuItem("Quit Shin", on_quit)
    )

    return pystray.Icon("Shin", image, "Shin Voice Assistant", menu)


# ═══════════════════════════════════════════════════════════════════════════════
# Main command loop
# ═══════════════════════════════════════════════════════════════════════════════

def handle_command(text: str) -> bool:
    """
    Parse and execute a recognised command.
    Returns False if the assistant should quit, True otherwise.
    """
    logger.debug("Handling command: %r", text)
    global _listening_paused, _bypass_wake_once

    global _recording_macro
    if _recording_macro is not None:
        cleaned = text.lower().strip()
        # Check for stop / cancel commands
        if any(w in cleaned for w in ("stop recording", "finish recording", "save shortcut", "save macro", "save routine")):
            import macros
            custom = macros._load_custom_macros()
            trigger = _recording_macro["trigger"]
            custom[trigger] = {
                "trigger": trigger,
                "commands": _recording_macro["commands"],
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            macros._save_custom_macros(custom)
            speak(f"Recording complete! Shortcut '{trigger}' has been saved with {len(_recording_macro['commands'])} commands.")
            _recording_macro = None
            return True

        if any(w in cleaned for w in ("cancel recording", "discard macro", "discard shortcut", "discard routine")):
            speak("Macro recording discarded.")
            _recording_macro = None
            return True

        # Record and run this command
        speak(f"Running: {text}")

        # Temporarily clear recording state to run it without recursively intercepting
        temp_macro = _recording_macro
        _recording_macro = None
        try:
            handle_command(text)
        except Exception as exc:
            logger.error("Error running recorded step: %s", exc)
        finally:
            _recording_macro = temp_macro

        _recording_macro["commands"].append(text)
        speak("Step recorded. Say next command, or say 'stop recording' to save.")
        return True

    # ── Hybrid Cloud Brain Delegation ─────────────────────────────────────────
    if os.getenv("SHIN_MODE", "standalone").lower() == "hybrid":
        try:
            try:
                from Shin.core.cloud_client import CloudBrainClient
            except ImportError:
                from core.cloud_client import CloudBrainClient
            client = CloudBrainClient()
            if client.is_available():
                brain_resp = client.process_utterance(text)
                spoken = brain_resp.get("spoken_text", "")
                if spoken:
                    speak(spoken)
                # Execute any local hardware commands commanded by the cloud
                local_out = client.execute_local_action_if_needed(brain_resp)
                if local_out and isinstance(local_out, str) and not spoken:
                    speak(local_out)
                return True
            else:
                logger.warning("Cloud Brain unavailable; falling back to local standalone execution.")
        except Exception as exc:
            logger.warning("Hybrid Cloud Brain error: %s; falling back to local standalone mode.", exc)

    # ── Mate Engine Avatar Voice Controls ─────────────────────────────────────
    cleaned_lower = text.lower().strip()
    if any(phrase in cleaned_lower for phrase in ("shin dance", "dance for me", "avatar dance", "chalo nacho", "naach ke dikhao")):
        try:
            from Shin.core import mate_bridge
            new_mode = mate_bridge.MateBridge.get().toggle_dance()
            ui_server.UIBridge.send_state("dance" if new_mode == "dance" else "idle")
            if new_mode == "dance":
                speak("Aye! Dance mode on! Let's groove!")
            else:
                speak("Dance off, back to work!")
            return True
        except Exception as _exc:
            logger.debug("Error toggling dance mode: %s", _exc)

    if any(phrase in cleaned_lower for phrase in ("hide avatar", "minimize avatar", "avatar chhupa do")):
        try:
            from Shin.core import mate_bridge
            mate_bridge.MateBridge.get().minimize()
            speak("Avatar minimize kar diya!")
            return True
        except Exception:
            pass

    if any(phrase in cleaned_lower for phrase in ("show avatar", "restore avatar", "avatar dikhao")):
        try:
            from Shin.core import mate_bridge
            mate_bridge.MateBridge.get().restore()
            speak("Avatar wapas aa gaya!")
            return True
        except Exception:
            pass
    
    # ── Interactive Training Session Interceptor ───────────────────────────────
    global _active_training_session, _bypass_wake_once
    if _active_training_session and _active_training_session.get("active"):
        cleaned = text.lower().strip()
        # Cancel / Stop
        if any(w in cleaned for w in ("cancel", "stop training", "exit training", "quit training", "band karo")):
            speak("Theek hai MJ, training yahan pe pause karte hain! Jitna tune bataya utna maine yaad rakh liya hai.")
            _active_training_session = None
            return True

        # Skip question
        q_idx = _active_training_session.get("q_index", 0)
        if any(w in cleaned for w in ("skip", "next question", "chhod do", "aage badho")):
            reply = dispatch({"intent": "train_shin", "args": {"mode": "skip", "q_index": q_idx}})
            _active_training_session["q_index"] = q_idx + 1
            if _active_training_session["q_index"] >= _active_training_session.get("total", 15) or "complete" in reply.lower():
                _active_training_session = None
            else:
                _bypass_wake_once = True
            speak(reply)
            return True

        # Answer question
        reply = dispatch({"intent": "train_shin", "args": {"mode": "answer", "q_index": q_idx, "answer": text}})
        _active_training_session["q_index"] = q_idx + 1
        if _active_training_session["q_index"] >= _active_training_session.get("total", 15) or "complete" in reply.lower():
            _active_training_session = None
        else:
            _bypass_wake_once = True
        speak(reply)
        return True

    # Only fire implicit memory extraction for conversational input
    # (not for action commands like "open chrome" or "volume up" which
    # would waste LLM tokens on meaningless system utterances).
    _CONVERSATIONAL_INTENTS = frozenset({
        "chat", "save_memory", "recall_memory", "forget_memory",
        "save_note", "web_search",
    })
    import memory
    # Peek at the intent before we have it — we'll do a lightweight pre-check
    # using a cheap heuristic: only trigger if the text looks like a sentence
    # (≥5 words) or contains a personal keyword.
    _personal_keywords = ("i ", "my ", "me ", "we ", "mera ", "meri ", "main ")
    _looks_conversational = (
        len(text.split()) >= 5
        or any(kw in text.lower() for kw in _personal_keywords)
    )
    if _looks_conversational:
        threading.Thread(
            target=memory.extract_and_store_implicit_knowledge,
            args=(text,),
            daemon=True
        ).start()

    # ── Chained Compound Commands (e.g. "mute volume and tell me the time") ──
    compound_parts = _nlp.split_compound_commands(text)
    if len(compound_parts) > 1:
        logger.info("Executing chained compound commands (%d steps): %r", len(compound_parts), compound_parts)
        for part in compound_parts:
            status = handle_command(part)
            if not status:
                return False
        return True

    res = _nlp.parse_intent(text)


    intent_name = res.get("intent", "unknown")
    args = res.get("args", {})
    confidence = res.get("_confidence", 1.0)
    logger.info("Intent: %s  |  Args: %s  |  Confidence: %.2f", intent_name, args, confidence)

    if intent_name == "pause_listening":
        _listening_paused = True
        speak("Standing by. Say 'start listening' to resume.")
        return True

    if intent_name == "resume_listening":
        _listening_paused = False
        _bypass_wake_once = True
        speak("I am back online.")
        return True


    if intent_name == "quit_assistant":
        speak("Goodbye! Have a great day.")
        return False


    if intent_name == "unknown" or confidence < 0.5:
        ui_server.UIBridge.send_state("error")
        # Fallback to LLM for unknown/low-confidence intents instead of canned response
        if _llm_router is not None:
            try:
                lang = get_language_state()
                try:
                    from Shin.core.conversation_flow import ConversationFlowManager
                    mem_ctx = memory.get_context_for_prompt() if hasattr(memory, "get_context_for_prompt") else ""
                    system_prompt = ConversationFlowManager.get().build_system_prompt(memory_context=mem_ctx, language=lang)
                except Exception:
                    system_prompt = f"You are Shin, MJ's AI voice assistant. Reply naturally in {lang}. Keep responses concise and conversational."
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ]
                llm_resp = _llm_router.call_llm(messages, tools=None)
                if llm_resp and llm_resp.get("content"):
                    speak(llm_resp["content"])
                    _nlp.add_to_history("user", text)
                    _nlp.add_to_history("assistant", llm_resp["content"])
                    return True
            except Exception as _e:
                logger.debug("LLM fallback failed: %s", _e)
        # Final fallback to canned confused response
        speak(personality.pick("confused"))
        return True

    if intent_name == "chat":
        chat_reply = args.get("response", "Arre yaar, mujhe samajh nahi aaya kya bola tune.")
        speak(chat_reply)
        _nlp.add_to_history("user", text)
        _nlp.add_to_history("assistant", chat_reply)
        try:
            entry = _cmd_log.log_command(text, "chat", chat_reply)
            ui_server.UIBridge.send_transcript(text, chat_reply)
            ui_server.UIBridge.send_history_entry(entry)
        except Exception:
            pass
        return True

    # Record the exchange in conversation memory
    _nlp.add_to_history("user", text)
    
    full_text = text
    current_callback = lambda: dispatch({"intent": intent_name, "args": args})

    while True:
        try:
            # ── Thinking out loud prefix (non-blocking) ───────────────────────
            # Speak a short phrase while the command is processing.
            # wait=False means it's queued but we don't block on it.
            prefix = personality.get_thinking_prefix(intent_name)
            if prefix:
                speak(prefix, wait=False)
            # ─────────────────────────────────────────────────────────────────
            response = current_callback()
            # Build final_response once so the spoken phrase and the transcript log
            # always match (previously personality.pick() was called twice, producing
            # two different random phrases when response was falsy).
            final_response = response if isinstance(response, str) else personality.pick("done")
            speak(final_response)

            _nlp.add_to_history("assistant", final_response)
            
            try:
                entry = _cmd_log.log_command(full_text, intent_name, final_response)
                ui_server.UIBridge.send_transcript(full_text, final_response)
                ui_server.UIBridge.send_history_entry(entry)
            except Exception:
                pass

            # Activate multi-turn interactive training session if started
            if intent_name == "train_shin" and args.get("mode", "start") == "start":
                _active_training_session = {"active": True, "q_index": 0, "total": 15}
                _bypass_wake_once = True

            break
        except MissingArgument as ma:
            ui_server.UIBridge.send_state("speaking")
            missing_val = ask_missing_argument(ma.prompt)
            if missing_val:
                ui_server.UIBridge.send_state("processing")
                full_text += f" + {missing_val}"
                # Safely rebind callback with the captured value
                def make_cb(cb, val):
                    return lambda: cb(val)
                current_callback = make_cb(ma.callback, missing_val)
            else:
                speak("Command cancelled.")
                break
        except ConfirmationRequired as cr:
            if ask_confirmation(cr.prompt):
                ui_server.UIBridge.send_state("processing")
                current_callback = cr.callback
            else:
                speak("Cancelled.")
                break
        except Exception as exc:
            logger.exception("Command execution error")
            ui_server.UIBridge.send_state("error")
            speak(f"Sorry, I ran into an error: {exc}")
            break

    return True


def _shutdown_assistant():
    """Clean up all background services, flush app usage stats, and terminate overlay process."""
    logger.info("Shutting down Shin assistant...")
    try:
        import alerts
        alerts.stop_alerts()
    except Exception as exc:
        logger.warning("Error stopping alerts monitor during shutdown: %s", exc)
    try:
        import app_tracker
        app_tracker.stop_tracking()
    except Exception as exc:
        logger.warning("Error stopping app tracker during shutdown: %s", exc)
    try:
        import ui_server
        ui_server.stop_ui_server()
    except Exception as exc:
        logger.warning("Error stopping UI server during shutdown: %s", exc)
    try:
        import gestures
        gestures.stop_gesture_control()
    except Exception as exc:
        logger.warning("Error stopping gesture control during shutdown: %s", exc)
    try:
        from Shin.core import mate_bridge
        mate_bridge.MateBridge.get().stop()
    except Exception as exc:
        logger.debug("Error stopping Mate Engine during shutdown: %s", exc)
    _stop_ollama()


def run(no_wake: bool = True):
    """Main assistant loop."""
    global _listening_paused, _bypass_wake_once

    # ── CRITICAL PATH: start TTS worker FIRST so speak() works ────────────
    tts_t = threading.Thread(target=_tts_worker, daemon=True)
    tts_t.start()

    # Pre-warm Kokoro TTS pipeline synchronously so the first speak() call never
    # triggers a cold-load under _kokoro_lock (which caused the 60s watchdog to fire).
    # We wait up to 90s in a background thread to keep the main thread responsive,
    # but the startup greeting is deferred until the pipeline is ready.
    _kokoro_ready_event = threading.Event()
    if TTS_BACKEND == "kokoro":
        def _prewarm():
            try:
                logger.info("Pre-warming Kokoro TTS pipeline...")
                _init_kokoro()
                logger.info("Kokoro TTS pipeline ready.")
            except Exception as exc:
                logger.warning("Failed to pre-warm Kokoro: %s", exc)
            finally:
                _kokoro_ready_event.set()
        threading.Thread(target=_prewarm, daemon=True, name="KokoroPrewarm").start()
    else:
        _kokoro_ready_event.set()  # No pre-warm needed for other backends

    if sys.platform == "win32":
        try:
            import win32api
            def _win_ctrl_handler(ctrl_type):
                # 0: CTRL_C_EVENT, 1: CTRL_BREAK_EVENT, 2: CTRL_CLOSE_EVENT
                if ctrl_type in (0, 1, 2):
                    print(f"\n{Fore.RED}Ctrl+C or terminal close detected. Shutting down...{Style.RESET_ALL}")
                    _shutdown_assistant()
                    os._exit(0)
                return False
            win32api.SetConsoleCtrlHandler(_win_ctrl_handler, True)
            logger.debug("Windows console control handler registered.")
        except Exception as exc:
            logger.warning("Failed to register Windows console control handler: %s", exc)

    # ── Start UI Server (needed before greeting so orb is visible) ─────────
    try:
        ui_server.start_ui_server()
        ui_server.UIBridge.send_state("idle")
    except Exception as exc:
        logger.error("Failed to start UI server: %s", exc)

    # ── Deferred background services (don't block the listen loop) ─────────
    def _deferred_services():
        """Start non-critical services in parallel after a brief delay."""
        # Initialize background system monitors (silent mode - no unsolicited auto-talk)
        try:
            import alerts
            alerts.init_alerts(None)
        except Exception as exc:
            logger.error("Failed to start alerts monitor: %s", exc)

        # Start background clipboard monitor
        try:
            import clipboard_history
            clipboard_history.start_monitoring()
        except Exception as exc:
            logger.error("Failed to start clipboard monitor: %s", exc)

        # Start system tray icon
        tray_icon = _create_tray_icon()
        if tray_icon:
            threading.Thread(target=tray_icon.run, daemon=True).start()

        # Start app usage tracker
        try:
            import app_tracker
            app_tracker.start_tracking()
        except Exception as exc:
            logger.warning("App tracker could not start: %s", exc)

        # Greet Dynamic Island via Named Pipe
        try:
            try:
                from Shin.core import island_bridge
            except ImportError:
                import island_bridge
            island_bridge.connect_and_greet()
        except Exception as exc:
            logger.debug("Dynamic Island greet notice: %s", exc)

        # Start Mate Engine Desktop Mascot (if enabled)
        try:
            try:
                from Shin.core import mate_bridge
            except ImportError:
                import mate_bridge
            mb = mate_bridge.MateBridge.get()
            if mb.enabled:
                ok = mb.start()
                if ok:
                    logger.info("Mate Engine desktop mascot active (PID: %s)", mb.pid)
                else:
                    logger.info("Mate Engine desktop mascot not started (check executable path)")
        except Exception as exc:
            logger.warning("Mate Engine auto-start error: %s", exc)

        # Pre-warm Neural intent classifier in background to eliminate runtime delay
        try:
            import neural_nlp
            neural_nlp.predict_intent("")
            logger.debug("Neural intent classifier pre-warmed.")
        except Exception:
            pass

        # Start DesktopFriends-inspired Heartbeat Scheduler (zero-cost 60s ticker)
        try:
            from Shin.core.timemap import HeartbeatScheduler, TimemapManager
            def _on_timemap_due(entry):
                logger.info("Timemap task due: %s at %s", entry.action, entry.time)
                try:
                    from Shin.core import island_bridge
                    island_bridge.show_timemap_due(entry.action)
                except Exception:
                    pass
                speak(f"MJ, scheduled reminder: {entry.action}")

            tm_manager = TimemapManager()
            heartbeat = HeartbeatScheduler(timemap_manager=tm_manager, on_trigger=_on_timemap_due, interval_seconds=60)
            heartbeat.start()
        except Exception as exc:
            logger.debug("Timemap Heartbeat scheduler: %s", exc)

    threading.Thread(target=_deferred_services, daemon=True, name="DeferredServices").start()

    # ── Start lightweight background threads immediately ──────────────────
    # Scheduler
    t = threading.Thread(target=_scheduler_thread, daemon=True)
    t.start()

    # Internet connectivity monitor
    threading.Thread(target=_internet_monitor_thread, daemon=True).start()

    # Pre-import noise reduction dependencies in background to prevent first-time lag
    if USE_NOISE_REDUCTION:
        threading.Thread(target=_pre_import_noise_reduction, daemon=True).start()

    # Pre-load Vosk in background if it's the configured ASR backend
    if ASR_BACKEND == "vosk":
        threading.Thread(target=_pre_load_vosk, daemon=True).start()

    if ASR_BACKEND == "whisper":
        threading.Thread(target=_pre_load_whisper, daemon=True).start()

    # ── Defer Ollama startup by 30 seconds ────────────────────────────────
    # Ollama loads an LLM into RAM (200-800MB). Deferring avoids competing
    # with critical-path startup and gives the OS time to settle.
    def _deferred_ollama():
        time.sleep(30)
        _start_ollama()
    threading.Thread(target=_deferred_ollama, daemon=True, name="DeferredOllama").start()


    try:
        while True:
            if _listening_paused:
                if ui_server.UIBridge.state != "standby":
                    ui_server.UIBridge.send_state("standby")
                # In standby mode: listen silently and ONLY respond if the user says "start listening"
                text = listen_once(timeout=8, phrase_time_limit=6, bypass_voice_auth=True)
                if text:
                    print(f"{Fore.MAGENTA}Heard in standby:{Style.RESET_ALL} {text}")
                    text_lower = text.lower().strip()

                    # ── Keyword fallback for resume (handles ASR misspellings / Hindi ASR misfire) ──
                    _RESUME_KEYWORDS = (
                        "start listening", "start listen",
                        "resume listening", "resume listen",
                        "continue listening", "continue listen",
                        "wake up", "get back online", "listen to me",
                        "unmute yourself", "unmute mic", "start responding",
                        # Common ASR variants / typos
                        "start listing", "start listning", "start listining",
                        "resume listing", "resume listning",
                    )
                    _resume_by_keyword = any(kw in text_lower for kw in _RESUME_KEYWORDS)

                    # Also run NLP intent check for robustness
                    res = _nlp.parse_intent(text)
                    intent_name = res.get("intent", "unknown")

                    if intent_name == "resume_listening" or _resume_by_keyword:
                        _listening_paused = False
                        _bypass_wake_once = True
                        speak("I am back online.")
                continue

            if not no_wake:
                if _bypass_wake_once:
                    _bypass_wake_once = False
                else:
                    ui_server.UIBridge.send_state("idle")
                    wake = wait_for_wake_word()
                    if not wake:
                        continue


            print(f"\n{Fore.GREEN}🎙️  Listening...{Style.RESET_ALL}")
            ui_server.UIBridge.send_state("listening")
            text = listen_once(timeout=8, phrase_time_limit=15)

            if not text:
                if not no_wake:
                    logger.debug("No speech detected after wake word.")
                ui_server.UIBridge.send_state("idle")
                continue

            # If user paused mid-phrase (e.g. 'can you open the...'), give them a continuation window
            if is_dangling_utterance(text):
                logger.info("Detected dangling utterance: %r. Listening for continuation...", text)
                print(f"{Fore.MAGENTA}Heard partial command:{Style.RESET_ALL} \"{text}\" ... (listening for rest)")
                ui_server.UIBridge.send_state("listening")
                continuation = listen_once(timeout=4, phrase_time_limit=8)
                if continuation:
                    text = f"{text} {continuation}".strip()
                    logger.info("Joined dangling utterance into: %r", text)

            print(f"{Fore.MAGENTA}You said:{Style.RESET_ALL} {text}")
            ui_server.UIBridge.send_state("processing")

            should_continue = handle_command(text)
            if not should_continue:
                break

            # ── Continuous Conversation Flow (ChatGPT / Gemini Live Follow-Up) ──
            try:
                from Shin.core.conversation_flow import ConversationFlowManager
                convo_flow = ConversationFlowManager.get()
                if convo_flow.is_enabled() and convo_flow.is_continuous_mode() and not no_wake:
                    convo_flow.start_session()
                    while convo_flow.is_in_active_session():
                        timeout = convo_flow.get_follow_up_timeout()
                        ui_server.UIBridge.send_state("conversation")
                        print(f"\n{Fore.CYAN}💬 In Conversation... (listening {int(timeout)}s, speak freely without wake word){Style.RESET_ALL}")
                        follow_up = listen_once(timeout=int(timeout), phrase_time_limit=15)
                        if not follow_up or not follow_up.strip():
                            convo_flow.end_session(reason="silence")
                            ui_server.UIBridge.send_state("idle")
                            break

                        if convo_flow.should_exit_conversation(follow_up):
                            convo_flow.end_session(reason="user exit phrase")
                            speak(personality.pick("done") if hasattr(personality, "pick") else "Theek hai, main standby pe hoon!")
                            ui_server.UIBridge.send_state("idle")
                            break

                        print(f"{Fore.MAGENTA}You said:{Style.RESET_ALL} {follow_up}")
                        ui_server.UIBridge.send_state("processing")
                        should_cont = handle_command(follow_up)
                        convo_flow.record_turn(follow_up, "")
                        if not should_cont:
                            should_continue = False
                            break
                    if not should_continue:
                        break
            except Exception as _convo_exc:
                logger.debug("Conversation flow follow-up error: %s", _convo_exc)

    except KeyboardInterrupt:
        speak("Shin shutting down. Goodbye!")
    finally:
        _shutdown_assistant()
        print(f"\n{Fore.RED}Shin offline.{Style.RESET_ALL}")


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shin Voice Assistant")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    parser.add_argument(
        "--wake",
        action="store_true",
        help="Enable wake-word detection (wait for wake word before listening)",
    )
    parser.add_argument(
        "--no-wake",
        action="store_true",
        help="Disable wake-word detection (listen continuously)",
    )
    parser.add_argument(
        "--reset-voice",
        action="store_true",
        help="Delete enrolled voice profile and reset speaker verification",
    )
    args = parser.parse_args()

    if args.reset_voice:
        try:
            import voice_auth
            print(voice_auth.delete_profile())
        except Exception as e:
            print(f"Failed to reset voice profile: {e}")
        sys.exit(0)

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("shin.log", encoding="utf-8"),
        ],
    )

    if args.no_wake:
        no_wake = True
    elif args.wake:
        no_wake = False
    else:
        # Default to the WAKE_WORD_ENABLED setting from .env (defaults to disabled)
        wake_enabled = os.getenv("WAKE_WORD_ENABLED", "false").lower() in ("true", "1", "t")
        no_wake = not wake_enabled

    run(no_wake=no_wake)
