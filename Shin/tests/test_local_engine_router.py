"""Unit tests for Shin Local Engine Discovery and Router Enhancements."""

import pytest
from Shin.core.llm_router import (
    MultiProviderLLMRouter,
    set_preferred_provider,
    get_preferred_provider,
    get_router,
)


def test_openjarvis_preferred_provider_alias():
    """Verify OpenJarvis and OmniRoute aliases are recognized."""
    ok, name = set_preferred_provider("openjarvis")
    assert ok is True
    assert name == "Openjarvis"
    assert get_preferred_provider() == "openjarvis"

    ok, name = set_preferred_provider("jarvis")
    assert ok is True
    assert name == "Openjarvis"

    ok, name = set_preferred_provider("omniroute")
    assert ok is True
    assert name == "Omniroute"

    # Reset back to auto cascade
    set_preferred_provider("auto")
    assert get_preferred_provider() is None


def test_discover_local_engines():
    """Verify local engine probe returns dictionary with expected keys."""
    router = MultiProviderLLMRouter()
    status = router.discover_local_engines()

    assert isinstance(status, dict)
    assert "openjarvis" in status
    assert "omniroute" in status
    assert "ollama" in status
    assert "lm_studio" in status
    # Values should be booleans indicating reachable ports
    for k, v in status.items():
        assert isinstance(v, bool)
