"""
tool_manager.py — Autonomous Tool Manager, Hot-Reloader & Self-Debugging Engine
================================================================================
Manages dynamic skill lifecycle for Shin:
- Safe AST syntax verification before code write.
- Runtime hot-reloading of dynamic_tools.py via importlib.reload.
- JSON schema generation for dynamic tools.
- Automated recursive debugging loop catching exceptions, feeding tracebacks
  back to the LLM, overwriting fixes, hot-reloading, and retrying up to 3 times.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import logging
import re
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("shin.tool_manager")

_ROOT_DIR = Path(__file__).resolve().parent
_DYNAMIC_TOOLS_PATH = _ROOT_DIR / "dynamic_tools.py"


class ToolManager:
    """Manages creation, validation, hot-reloading, and auto-debugging of dynamic tools."""

    def __init__(self, tools_path: Optional[Path] = None):
        self.tools_path = tools_path or _DYNAMIC_TOOLS_PATH
        self.module_name = "dynamic_tools"
        self._ensure_tools_file_exists()
        self.dynamic_module = self._load_or_reload_module()

    def _ensure_tools_file_exists(self) -> None:
        """Create dynamic_tools.py with standard header if it does not exist."""
        if not self.tools_path.exists():
            default_content = '''"""
dynamic_tools.py — Dynamically Generated & Hot-Reloadable Skills for Shin
"""
from __future__ import annotations
import math, os, sys, json, time
from typing import Any, Dict, List, Optional

DYNAMIC_REGISTRY: Dict[str, Any] = {}

def register_tool(func):
    DYNAMIC_REGISTRY[func.__name__] = func
    return func
'''
            self.tools_path.write_text(default_content, encoding="utf-8")

    def _load_or_reload_module(self):
        """Import or hot-reload the dynamic_tools module in sys.modules."""
        try:
            if self.module_name in sys.modules:
                mod = importlib.reload(sys.modules[self.module_name])
            else:
                mod = importlib.import_module(self.module_name)
            return mod
        except Exception as exc:
            logger.error("Failed to load/reload %s: %s", self.module_name, exc)
            return sys.modules.get(self.module_name)

    def reload(self) -> bool:
        """Explicitly hot-reload dynamic_tools without restarting the host process."""
        self.dynamic_module = self._load_or_reload_module()
        return self.dynamic_module is not None

    def get_registered_tools(self) -> Dict[str, Callable]:
        """Return dict of all registered dynamic tools in dynamic_tools.py."""
        self.reload()
        if self.dynamic_module and hasattr(self.dynamic_module, "DYNAMIC_REGISTRY"):
            return dict(self.dynamic_module.DYNAMIC_REGISTRY)
        return {}

    def read_code(self) -> str:
        """Read current source code of dynamic_tools.py."""
        if self.tools_path.exists():
            return self.tools_path.read_text(encoding="utf-8", errors="replace")
        return ""

    def validate_code_ast(self, code: str) -> Tuple[bool, Optional[str]]:
        """Validate Python code string syntax using Abstract Syntax Tree (AST)."""
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as syn_err:
            return False, f"SyntaxError at line {syn_err.lineno}, col {syn_err.offset}: {syn_err.msg}"
        except Exception as exc:
            return False, f"AST parsing error: {exc}"

    def get_function_source(self, func_name: str) -> Optional[str]:
        """Extract the exact source code of a specific function from dynamic_tools.py."""
        code = self.read_code()
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == func_name:
                    lines = code.splitlines()
                    start = node.lineno - 1
                    end = node.end_lineno
                    return "\n".join(lines[start:end])
        except Exception as exc:
            logger.debug("Failed to extract function source for %s: %s", func_name, exc)
        return None

    def add_or_update_tool(self, code_snippet: str) -> Tuple[bool, str]:
        """
        Validate new tool function code, append/replace in dynamic_tools.py,
        and hot-reload in memory immediately.
        """
        clean_code = self._clean_llm_code_block(code_snippet)

        # Validate syntax
        is_valid, err = self.validate_code_ast(clean_code)
        if not is_valid:
            return False, f"Code failed AST validation: {err}"

        # Ensure @register_tool decorator exists on top of function definitions
        tree = ast.parse(clean_code)
        func_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        if not func_names:
            return False, "Code snippet does not contain any function definitions."

        target_func_name = func_names[0]

        # Read current content
        current_content = self.read_code()

        # If function already exists in file, replace it cleanly; otherwise append
        pattern = rf"@register_tool\s+def\s+{re.escape(target_func_name)}\b.*?(?=\n@register_tool|\Z)"
        if re.search(pattern, current_content, flags=re.DOTALL):
            new_content = re.sub(pattern, clean_code.strip(), current_content, flags=re.DOTALL)
        elif f"def {target_func_name}(" in current_content:
            simple_pattern = rf"def\s+{re.escape(target_func_name)}\b.*?(?=\ndef\s+|\Z)"
            new_content = re.sub(simple_pattern, clean_code.strip(), current_content, flags=re.DOTALL)
        else:
            # Append decorator if missing
            if "@register_tool" not in clean_code:
                clean_code = f"@register_tool\n{clean_code}"
            new_content = current_content.rstrip() + f"\n\n\n{clean_code.strip()}\n"

        # Final AST audit of combined file
        is_comb_valid, comb_err = self.validate_code_ast(new_content)
        if not is_comb_valid:
            return False, f"Combined dynamic_tools.py failed AST audit: {comb_err}"

        # Overwrite file
        self.tools_path.write_text(new_content, encoding="utf-8")

        # Hot-reload into sys.modules
        reloaded = self.reload()
        if not reloaded:
            return False, "Hot-reload failed after writing code to dynamic_tools.py."

        logger.info("Successfully added/updated and hot-reloaded tool: %s", target_func_name)
        return True, f"Tool '{target_func_name}' dynamically registered and hot-reloaded."

    def execute_with_autodebug(
        self,
        tool_name: str,
        args: Dict[str, Any],
        llm_fix_fn: Callable[[str, str, str], str],
        max_retries: int = 3,
    ) -> Tuple[bool, Any, int]:
        """
        Execute a tool function with an automated debugging feedback loop.
        Catches tracebacks, prompts LLM for code fix, rewrites dynamic_tools.py,
        hot-reloads, and retries execution up to max_retries.

        Args:
            tool_name: Name of tool to execute.
            args: Parameter dictionary for tool.
            llm_fix_fn: Callback function(tool_name, failed_code, traceback_str) -> fixed_code.
            max_retries: Max self-debugging attempts (default: 3).

        Returns:
            Tuple of (success: bool, result_or_error: Any, attempts_used: int).
        """
        attempts = 0
        last_error = ""

        while attempts <= max_retries:
            tools = self.get_registered_tools()
            func = tools.get(tool_name)

            if not func:
                return False, f"Tool '{tool_name}' not found in dynamic registry.", attempts

            try:
                # Attempt execution
                logger.info("[EXECUTE] Calling dynamic tool '%s' (Attempt %d/%d)", tool_name, attempts + 1, max_retries + 1)
                result = func(**args)
                return True, result, attempts

            except Exception as exc:
                attempts += 1
                tb = traceback.format_exc()
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "[AUTO-DEBUG] Tool '%s' failed on attempt %d: %s\n%s",
                    tool_name, attempts, last_error, tb
                )

                if attempts > max_retries:
                    break

                # Extract failing code
                failing_code = self.get_function_source(tool_name) or self.read_code()

                # Request fix from LLM
                try:
                    fixed_code = llm_fix_fn(tool_name, failing_code, tb)
                    ok, msg = self.add_or_update_tool(fixed_code)
                    if not ok:
                        logger.error("[AUTO-DEBUG] Patch failed to apply: %s", msg)
                    else:
                        logger.info("[AUTO-DEBUG] Hot-reloaded patched code for '%s'. Retrying...", tool_name)
                except Exception as fix_exc:
                    logger.error("[AUTO-DEBUG] LLM fix generation failed: %s", fix_exc)

        return False, f"Tool '{tool_name}' failed after {max_retries} auto-debug retries. Last error: {last_error}", attempts

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Generate OpenAI/Ollama function calling schemas for all registered dynamic tools."""
        schemas = []
        tools = self.get_registered_tools()

        for name, fn in tools.items():
            doc = inspect.getdoc(fn) or f"Execute dynamic tool {name}."
            sig = inspect.signature(fn)
            properties = {}
            required = []

            for p_name, param in sig.parameters.items():
                if p_name in ("self", "cls"):
                    continue
                p_type = "string"
                if param.annotation == int:
                    p_type = "integer"
                elif param.annotation == float:
                    p_type = "number"
                elif param.annotation == bool:
                    p_type = "boolean"
                elif param.annotation in (dict, Dict):
                    p_type = "object"
                elif param.annotation in (list, List):
                    p_type = "array"

                properties[p_name] = {
                    "type": p_type,
                    "description": f"Parameter {p_name}"
                }
                if param.default == inspect.Parameter.empty:
                    required.append(p_name)

            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": doc.split("\n")[0],
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    }
                }
            })

        return schemas

    def _clean_llm_code_block(self, raw_code: str) -> str:
        """Strip markdown fences (```python ... ```) and leading/trailing whitespace."""
        text = raw_code.strip()
        # Remove markdown code fences
        text = re.sub(r"^```(?:python)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
        return text.strip()


_GLOBAL_TOOL_MANAGER: Optional[ToolManager] = None


def get_tool_manager() -> ToolManager:
    """Acquire singleton ToolManager instance."""
    global _GLOBAL_TOOL_MANAGER
    if _GLOBAL_TOOL_MANAGER is None:
        _GLOBAL_TOOL_MANAGER = ToolManager()
    return _GLOBAL_TOOL_MANAGER
