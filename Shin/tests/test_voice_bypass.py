"""
tests/test_voice_bypass.py — Unit tests for voice verification security and bypass logic.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Inject mock voice_auth into sys.modules before importing assistant
mock_voice_auth = MagicMock()
sys.modules["voice_auth"] = mock_voice_auth

import assistant

class DummyAudio:
    def get_wav_data(self, *args, **kwargs):
        return b"dummy wav"
    def get_raw_data(self, *args, **kwargs):
        return b"dummy raw"
    @property
    def sample_rate(self):
        return 16000
    @property
    def sample_width(self):
        return 2

@pytest.fixture(autouse=True)
def reset_mocks():
    mock_voice_auth.reset_mock()
    assistant._recognizer = None

@patch("assistant.sr")
def test_listen_once_rejects_unauthenticated_delete_intent(mock_sr):
    """Ensure an unauthenticated stranger CANNOT delete the owner's voice profile."""
    mock_rec = MagicMock()
    mock_sr.Recognizer.return_value = mock_rec
    mock_rec.listen.return_value = DummyAudio()

    assistant.ASR_BACKEND = "google"
    assistant.ASR_LANGUAGE = "en-US"

    mock_rec.recognize_google.return_value = "forget my voice"

    mock_voice_auth.is_enabled.return_value = True
    mock_voice_auth.has_profile.return_value = True

    # Unknown/unverified speaker
    mock_voice_auth.verify_voice.return_value = False

    res = assistant.listen_once(bypass_voice_auth=False)

    # Must be rejected (None) and verify_voice must be called
    assert res is None
    mock_voice_auth.verify_voice.assert_called_once()


@patch("assistant.sr")
def test_listen_once_allows_authenticated_delete_intent(mock_sr):
    """Ensure the verified owner CAN delete their voice profile via voice."""
    mock_rec = MagicMock()
    mock_sr.Recognizer.return_value = mock_rec
    mock_rec.listen.return_value = DummyAudio()

    assistant.ASR_BACKEND = "google"
    assistant.ASR_LANGUAGE = "en-US"

    mock_rec.recognize_google.return_value = "forget my voice"

    mock_voice_auth.is_enabled.return_value = True
    mock_voice_auth.has_profile.return_value = True

    # Verified owner
    mock_voice_auth.verify_voice.return_value = True

    res = assistant.listen_once(bypass_voice_auth=False)

    assert res == "forget my voice"
    mock_voice_auth.verify_voice.assert_called_once()


@patch("assistant.sr")
def test_listen_once_bypass_param(mock_sr):
    """Ensure programmatic bypass (e.g. during enrollment flow) works."""
    mock_rec = MagicMock()
    mock_sr.Recognizer.return_value = mock_rec
    mock_rec.listen.return_value = DummyAudio()

    assistant.ASR_BACKEND = "google"
    assistant.ASR_LANGUAGE = "en-US"

    mock_rec.recognize_google.return_value = "yes"

    mock_voice_auth.is_enabled.return_value = True
    mock_voice_auth.has_profile.return_value = True
    mock_voice_auth.verify_voice.return_value = False

    # When bypass_voice_auth=True is explicitly passed by internal flow, verify_voice should not be called
    res = assistant.listen_once(bypass_voice_auth=True)

    assert res == "yes"
    mock_voice_auth.verify_voice.assert_not_called()


@patch("assistant.sr")
def test_listen_once_no_bypass_other_intents(mock_sr):
    mock_rec = MagicMock()
    mock_sr.Recognizer.return_value = mock_rec
    mock_rec.listen.return_value = DummyAudio()

    assistant.ASR_BACKEND = "google"
    assistant.ASR_LANGUAGE = "en-US"

    mock_rec.recognize_google.return_value = "open chrome"

    mock_voice_auth.is_enabled.return_value = True
    mock_voice_auth.has_profile.return_value = True
    mock_voice_auth.verify_voice.return_value = False

    res = assistant.listen_once(bypass_voice_auth=False)

    assert res is None
    mock_voice_auth.verify_voice.assert_called_once()
