"""
voice_auth.py — Speaker Identification for Shin Voice Assistant
===============================================================
Uses resemblyzer to embed voice prints and verify speaker identity.

.env keys:
    VOICE_AUTH_ENABLED     — "true" / "false" (default: false)
    VOICE_AUTH_THRESHOLD   — cosine similarity threshold 0-1 (default: 0.75)

Usage:
    enroll_voice(audio_data_list)  — save embedding from multiple AudioData samples
    verify_voice(audio_data)       — return True if speaker matches profile
    has_profile()                  — True if a profile exists
    delete_profile()               — remove stored profile
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_PROFILE_PATH = Path(__file__).parent.parent / "data" / "voice_profile.npy"

# Migrate old voice profile from root or core/ if it exists
_OLD_PROFILE_DIR_CORE = Path(__file__).parent
_OLD_PROFILE_DIR_ROOT = _OLD_PROFILE_DIR_CORE.parent

for old_dir in (_OLD_PROFILE_DIR_CORE, _OLD_PROFILE_DIR_ROOT):
    old_file = old_dir / "voice_profile.npy"
    if old_file.exists() and old_file != _PROFILE_PATH:
        try:
            _PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(old_file, _PROFILE_PATH)
            old_file.unlink()
            logger.info("Migrated voice_profile.npy from %s to %s", old_file, _PROFILE_PATH)
        except Exception as exc:
            logger.warning("Failed to migrate voice_profile.npy from %s: %s", old_file, exc)
_THRESHOLD = float(os.getenv("VOICE_AUTH_THRESHOLD", "0.75"))
# Note: _ENABLED is NOT cached — read at call time so UI settings changes apply
# without a restart.


def is_enabled() -> bool:
    """Return True if voice auth is enabled in .env."""
    return os.getenv("VOICE_AUTH_ENABLED", "false").lower() in ("true", "1", "t")


def has_profile() -> bool:
    """Return True if a speaker profile has been enrolled."""
    return _PROFILE_PATH.exists()


def delete_profile() -> str:
    """Remove the stored voice profile."""
    if _PROFILE_PATH.exists():
        _PROFILE_PATH.unlink()
        return "Voice profile deleted. Anyone can now use Shin."
    return "No voice profile found to delete."


_encoder = None

def _get_encoder():
    """Lazy-load the resemblyzer VoiceEncoder and cache it globally."""
    global _encoder
    if _encoder is None:
        try:
            from resemblyzer import VoiceEncoder
            _encoder = VoiceEncoder()
        except ImportError:
            raise ImportError(
                "resemblyzer is not installed. Run: pip install resemblyzer"
            )
    return _encoder


def _audio_to_wav_array(audio_data) -> np.ndarray:
    """Convert speech_recognition.AudioData to float32 numpy array."""
    import speech_recognition as sr
    raw = audio_data.get_wav_data(convert_rate=16000, convert_width=2)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return samples


def enroll_voice(audio_samples: list) -> str:
    """
    Enroll speaker from a list of AudioData objects.
    Saves averaged embedding to voice_profile.npy.
    Requires at least 3 samples for a reliable embedding.
    """
    if len(audio_samples) < 3:
        return "I need at least 3 voice samples to build a reliable profile."

    try:
        encoder = _get_encoder()
    except ImportError as e:
        return str(e)

    try:
        from resemblyzer import preprocess_wav

        embeddings = []
        for sample in audio_samples:
            wav = _audio_to_wav_array(sample)
            preprocessed = preprocess_wav(wav, source_sr=16000)
            if len(preprocessed) < 1600:  # skip very short clips
                continue
            emb = encoder.embed_utterance(preprocessed)
            embeddings.append(emb)

        if not embeddings:
            return "None of the audio samples were long enough to process. Please speak for at least 2 seconds each."

        avg_embedding = np.mean(embeddings, axis=0)
        np.save(_PROFILE_PATH, avg_embedding)
        logger.info("Voice profile saved to %s", _PROFILE_PATH)
        return (
            f"Voice profile created from {len(embeddings)} samples. "
            "Shin will now only respond to your voice."
        )

    except Exception as exc:
        logger.exception("Voice enrollment failed")
        return f"Voice enrollment failed: {exc}"


def verify_voice(audio_data) -> bool:
    """
    Return True if *audio_data* matches the stored speaker profile.
    Returns True (pass) if auth is disabled or no profile exists.
    """
    if not is_enabled():
        return True
    if not has_profile():
        return True  # no profile enrolled → open access

    try:
        encoder = _get_encoder()
        from resemblyzer import preprocess_wav

        stored = np.load(_PROFILE_PATH)
        wav = _audio_to_wav_array(audio_data)
        preprocessed = preprocess_wav(wav, source_sr=16000)

        if len(preprocessed) < 800:
            return True  # too short to judge — allow through

        emb = encoder.embed_utterance(preprocessed)

        # Cosine similarity
        similarity = float(
            np.dot(stored, emb) / (np.linalg.norm(stored) * np.linalg.norm(emb) + 1e-9)
        )
        logger.debug("Voice similarity score: %.3f (threshold: %.3f)", similarity, _THRESHOLD)
        return similarity >= _THRESHOLD

    except Exception as exc:
        logger.warning("Voice verification failed (allowing through): %s", exc)
        return True  # fail-open so Shin doesn't lock up if library errors


def run_enrollment_flow(listen_fn, speak_fn) -> str:
    """
    Interactive enrollment: ask user to say 5 phrases, collect AudioData, enroll.
    `listen_fn` must return an AudioData or None.
    `speak_fn` is the TTS function.
    """
    phrases = [
        "Hey Shin, how are you doing today?",
        "Open Chrome and search for the weather.",
        "What time is it right now?",
        "Remind me to drink water in thirty minutes.",
        "Turn up the volume and play some music.",
    ]
    speak_fn("I will now record your voice profile. Please say each phrase I give you clearly.")
    samples = []

    for i, phrase in enumerate(phrases, 1):
        speak_fn(f"Phrase {i} of {len(phrases)}: {phrase}")
        import time
        time.sleep(0.5)
        audio = listen_fn(timeout=10, phrase_time_limit=8)
        if audio is not None:
            samples.append(audio)
            speak_fn("Got it.")
        else:
            speak_fn("I didn't catch that. Moving on.")

    return enroll_voice(samples)
