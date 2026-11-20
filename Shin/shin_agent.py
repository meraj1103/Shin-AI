"""
shin_agent.py — Direct CLI and Integration Entry Point for Shin Agent
====================================================================
Execute via:
    python shin_agent.py
"""

from __future__ import annotations
import sys
from pathlib import Path

# Add current directory and core to sys.path
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_CORE = _ROOT / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from core.shin_agent import (
    main,
    run_shin_agent,
    get_agent_engine,
    HardwareProfile,
    DualModeLLMRouter,
    AVAILABLE_TOOLS,
    TOOL_SCHEMAS,
    ShinReActEngine,
    agent_reach_query,
)

if __name__ == "__main__":
    main()
