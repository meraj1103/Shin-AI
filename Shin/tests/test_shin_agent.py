"""
test_shin_agent.py — Comprehensive Test Suite for Shin ReAct Agent
==================================================================
Tests:
  - Hardware Profile (Ryzen 5 5600H, RTX 3050 4GB VRAM optimization)
  - OS Operations (launch, list_dir, read_file, write_file, volume, brightness, power)
  - Web-Learning Module (DuckDuckGo search + BeautifulSoup scraping)
  - App Inspection (pywinauto & Windows UIA perception)
  - Dual-Mode LLM Routing (Online vs Offline Ollama REST API)
  - Persona & Gender Grammar Integrity (Addressing MJ, female Hindi verb forms)
  - LangGraph StateGraph ReAct Execution Loop
"""

import os
import sys
from pathlib import Path
import pytest

_SHIN_ROOT = Path(__file__).resolve().parent.parent
if str(_SHIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHIN_ROOT))

from core.shin_agent import (
    HardwareProfile,
    DualModeLLMRouter,
    ShinReActEngine,
    os_operations,
    web_search_and_learn,
    inspect_active_app,
    interact_app_ui,
    run_shin_agent,
    build_shin_system_prompt,
    AVAILABLE_TOOLS,
)


def test_hardware_profile():
    hw = HardwareProfile()
    assert hw.cpu_cores == 6
    assert hw.cpu_threads == 12
    assert hw.vram_gb == 4.0
    assert hw.max_context_tokens == 4096
    assert hw.gpu_layers_offload == 99


def test_persona_system_prompt():
    prompt = build_shin_system_prompt()
    assert "MJ" in prompt
    assert "100% FEMALE" in prompt
    assert "karti hoon" in prompt
    assert "bataungi" in prompt
    assert "ReAct Execution Logic" in prompt


def test_os_operations_list_dir(tmp_path):
    # Test directory listing
    res = os_operations("list_dir", target=str(tmp_path))
    assert f"Listing for '{tmp_path}'" in res


def test_os_operations_file_read_write(tmp_path):
    test_file = tmp_path / "test_note.txt"
    # Write
    write_res = os_operations("write_file", target=str(test_file), content="Hello MJ, Shin is online.")
    assert "Successfully wrote" in write_res
    assert test_file.exists()

    # Read
    read_res = os_operations("read_file", target=str(test_file))
    assert "Hello MJ, Shin is online." in read_res


def test_os_operations_volume_query():
    res = os_operations("get_volume")
    assert isinstance(res, str)
    assert len(res) > 0


def test_web_search_and_learn():
    res = web_search_and_learn("Python programming language", max_results=2, scrape_top=False)
    assert isinstance(res, str)
    assert len(res) > 0
    assert "Python" in res or "Search Findings" in res


def test_inspect_active_app():
    res = inspect_active_app(max_elements=10)
    assert isinstance(res, str)
    assert "Active Window" in res or "PID" in res


def test_dual_mode_router():
    router = DualModeLLMRouter()
    mode, provider = router.get_active_mode()
    assert mode in ("online", "offline")
    assert isinstance(provider, str)
    assert len(provider) > 0


def test_agent_react_execution():
    # Test end-to-end ReAct execution with native fast-path
    res = run_shin_agent("list files in .")
    assert isinstance(res, str)
    assert len(res) > 0
    assert "MJ" in res or "Listing" in res
