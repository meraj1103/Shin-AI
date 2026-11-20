"""
test_autonomous_loop.py — Automated Test Suite for Autonomous Self-Improvement Loop
===================================================================================
Tests:
  - Dynamic tool code writing & AST syntax validation.
  - Hot-reloading of dynamic_tools.py without process restart.
  - JSON schema extraction for dynamic functions.
  - Automated recursive debugging loop (error capture, code patching, retry).
"""

import sys
from pathlib import Path
import pytest

_SHIN_ROOT = Path(__file__).resolve().parent.parent
if str(_SHIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHIN_ROOT))

from tool_manager import ToolManager, get_tool_manager
from main import AutonomousShinEngine


def test_tool_manager_ast_validation():
    tm = ToolManager()
    # Valid syntax
    valid_code = "@register_tool\ndef test_add(a: int, b: int) -> int:\n    return a + b\n"
    is_valid, err = tm.validate_code_ast(valid_code)
    assert is_valid is True
    assert err is None

    # Invalid syntax
    invalid_code = "def broken_func(:\n    return"
    is_valid, err = tm.validate_code_ast(invalid_code)
    assert is_valid is False
    assert "SyntaxError" in err


def test_tool_manager_add_and_hot_reload():
    tm = ToolManager()
    new_tool_code = """
@register_tool
def sample_multiplier(x: int, y: int) -> str:
    \"\"\"Multiply two integers and return formatted result.\"\"\"
    return f"Product: {x * y}"
"""
    ok, msg = tm.add_or_update_tool(new_tool_code)
    assert ok is True
    assert "sample_multiplier" in msg

    # Verify tool is now registered in-memory without restart
    tools = tm.get_registered_tools()
    assert "sample_multiplier" in tools
    res = tools["sample_multiplier"](4, 5)
    assert res == "Product: 20"


def test_dynamic_tool_schema_generation():
    tm = ToolManager()
    schemas = tm.get_tool_schemas()
    assert isinstance(schemas, list)
    schema_names = [s["function"]["name"] for s in schemas]
    assert "sample_multiplier" in schema_names or "calculate_expression" in schema_names


def test_automated_debugging_loop():
    tm = ToolManager()

    # Step 1: Add a tool with a deliberate error
    broken_tool_code = """
@register_tool
def buggy_division(a: int, b: int) -> str:
    \"\"\"Buggy division function.\"\"\"
    # Deliberate ZeroDivisionError on call with 0
    return f"Division: {a / b}"
"""
    ok, msg = tm.add_or_update_tool(broken_tool_code)
    assert ok is True

    # Step 2: Define mock LLM fixer that fixes the division by zero
    def mock_llm_fixer(tool_name: str, failed_code: str, traceback_str: str) -> str:
        assert tool_name == "buggy_division"
        assert "ZeroDivisionError" in traceback_str
        # Return corrected code
        return """
@register_tool
def buggy_division(a: int, b: int) -> str:
    \"\"\"Fixed division function.\"\"\"
    if b == 0:
        return "Division by zero is undefined"
    return f"Division: {a / b}"
"""

    # Step 3: Execute with autodebug loop
    success, result, attempts = tm.execute_with_autodebug(
        tool_name="buggy_division",
        args={"a": 10, "b": 0},
        llm_fix_fn=mock_llm_fixer,
        max_retries=3,
    )

    # Must succeed after automatic self-repair
    assert success is True
    assert result == "Division by zero is undefined"
    assert attempts >= 1  # Verify at least 1 self-repair attempt was triggered


def test_autonomous_shin_engine_initialization():
    engine = AutonomousShinEngine()
    tools = engine.get_all_tools()
    # Check that native tools and dynamic tools are merged
    assert "os_operations" in tools
    assert "web_search_and_learn" in tools
    assert "inspect_active_app" in tools
    schemas = engine.get_all_tool_schemas()
    assert len(schemas) >= 4
