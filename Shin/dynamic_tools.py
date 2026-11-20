"""
dynamic_tools.py — Dynamically Generated & Hot-Reloadable Skills for Shin
========================================================================
This file is autonomously modified and hot-reloaded by Shin's Tool Manager.
New tools generated at runtime are written here, validated via AST, and
immediately made available to Shin's ReAct execution engine without restarting.
"""

from __future__ import annotations

import math
import os
import sys
import json
import time
from typing import Any, Dict, List, Optional

# Dynamic registry mapping function names to callable functions
DYNAMIC_REGISTRY: Dict[str, Any] = {}


def register_tool(func):
    """Decorator to register a tool in DYNAMIC_REGISTRY."""
    DYNAMIC_REGISTRY[func.__name__] = func
    return func


# ── Dynamically Generated Skills Below ──────────────────────────────────────

@register_tool
def calculate_expression(expression: str) -> str:
    """Evaluate a mathematical expression safely using python math module."""
    try:
        allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
        allowed_names.update({"abs": abs, "round": round, "min": min, "max": max})
        # Evaluate safely without builtins
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return f"Result: {result}"
    except Exception as exc:
        return f"Calculation error: {exc}"


@register_tool
def sample_multiplier(x: int, y: int) -> str:
    """Multiply two integers and return formatted result."""
    return f"Product: {x * y}"
@register_tool
def buggy_division(a: int, b: int) -> str:
    """Fixed division function."""
    if b == 0:
        return "Division by zero is undefined"
    return f"Division: {a / b}"
@register_tool
def test_greeting(name: str) -> str:
    """Say hello to someone."""
    return "Hello, " + name + "!"
