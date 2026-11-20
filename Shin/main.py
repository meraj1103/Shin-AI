"""
main.py — Autonomous Self-Improving AI Assistant Engine for "Shin"
==================================================================
Hardware Profile:
  - OS: Windows 11 (64-bit)
  - CPU: AMD Ryzen 5 5600H (6 Cores / 12 Threads)
  - RAM: 16 GB DDR4
  - GPU: NVIDIA GeForce RTX 3050 Laptop GPU (4 GB GDDR6 VRAM)
  - Engine: Dual-Mode (Online: Gemini 2.0 Flash / OpenAI | Offline: Local Ollama REST API)
  - Core Feature: Autonomous Self-Improvement, Dynamic Skill Generation & Self-Debugging

Usage:
  python main.py
"""

from __future__ import annotations

import collections
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from dotenv import load_dotenv

_ROOT_DIR = Path(__file__).resolve().parent
_CORE_DIR = _ROOT_DIR / "core"
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

load_dotenv(_ROOT_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("shin.main")

from core.shin_agent import (
    AVAILABLE_TOOLS as NATIVE_TOOLS,
    TOOL_SCHEMAS as NATIVE_SCHEMAS,
    DualModeLLMRouter,
    HardwareProfile,
    build_shin_system_prompt,
    inspect_active_app,
    os_operations,
    web_search_and_learn,
)
from tool_manager import ToolManager, get_tool_manager


class AutonomousShinEngine:
    """
    Shin's Autonomous Self-Improving ReAct Engine.
    Handles dynamic tool synthesis, hot-reloading, and recursive auto-debugging.
    """

    def __init__(self, hardware: Optional[HardwareProfile] = None):
        self.hw = hardware or HardwareProfile()
        self.router = DualModeLLMRouter(self.hw)
        self.tool_manager = get_tool_manager()
        self.system_prompt = self._build_natural_system_prompt()
        self.max_react_steps = 4
        self.max_debug_retries = 3
        self.history: collections.deque = collections.deque(maxlen=20)
        self._load_history()

    def _load_history(self):
        try:
            h_path = _ROOT_DIR / "data" / "conversation_history.json"
            if h_path.exists():
                with open(h_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for item in saved[-20:]:
                    if isinstance(item, dict) and "role" in item and "content" in item:
                        self.history.append(item)
        except Exception as exc:
            logger.debug("Could not load autonomous conversation history: %s", exc)

    def _persist_history(self):
        try:
            h_path = _ROOT_DIR / "data" / "conversation_history.json"
            h_path.parent.mkdir(parents=True, exist_ok=True)
            with open(h_path, "w", encoding="utf-8") as f:
                json.dump(list(self.history), f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.debug("Could not persist autonomous conversation history: %s", exc)

    def clear_context(self):
        """Wipe active conversation buffer."""
        self.history.clear()
        self._persist_history()

    def _build_natural_system_prompt(self) -> str:
        """Construct Shin's natural persona prompt addressing MJ."""
        base_prompt = build_shin_system_prompt()
        natural_extension = (
            "\n## Natural Persona & Voice Guidelines\n"
            "- Address the user ONLY as 'MJ'. Never call the user 'hero', 'Hero', 'sir', or 'boss' — strictly 'MJ'.\n"
            "- Speak naturally, directly, and with genuine technical confidence.\n"
            "- Zero sycophancy or filler: Cut 'Certainly!', 'I would be happy to', 'Great question!'.\n"
            "- If responding in Hinglish, STRICTLY preserve 100% female verb forms ('karti hoon', 'kar sakti hoon', 'bataungi', 'dekh rahi hoon').\n"
            "- When executing actions, sound like a capable best-friend partner working side-by-side on his laptop.\n"
            "- If a requested tool does not exist, you will autonomously write, hot-reload, and debug it.\n"
        )
        return base_prompt + natural_extension

    def get_all_tool_schemas(self) -> List[Dict[str, Any]]:
        """Combine native tool schemas with hot-reloaded dynamic tool schemas."""
        dynamic_schemas = self.tool_manager.get_tool_schemas()
        return NATIVE_SCHEMAS + dynamic_schemas

    def get_all_tools(self) -> Dict[str, Callable]:
        """Combine native tools with hot-reloaded dynamic tools."""
        dynamic_tools = self.tool_manager.get_registered_tools()
        combined = dict(NATIVE_TOOLS)
        combined.update(dynamic_tools)
        return combined

    def execute_tool_call(self, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, Any]:
        """
        Execute tool with auto-debugging. Native tools execute directly;
        dynamic tools execute through ToolManager's self-debugging feedback loop.
        """
        all_tools = self.get_all_tools()

        # If tool is native, execute with direct try/catch
        if tool_name in NATIVE_TOOLS:
            try:
                fn = NATIVE_TOOLS[tool_name]
                return True, fn(**args)
            except Exception as exc:
                return False, f"Native tool '{tool_name}' failed: {exc}"

        # If tool is dynamic, execute through autonomous self-debugging loop
        if tool_name in self.tool_manager.get_registered_tools():
            ok, res, attempts = self.tool_manager.execute_with_autodebug(
                tool_name=tool_name,
                args=args,
                llm_fix_fn=self._llm_fix_code,
                max_retries=self.max_debug_retries,
            )
            return ok, res

        return False, f"Tool '{tool_name}' not found."

    def _llm_fix_code(self, tool_name: str, failed_code: str, traceback_str: str) -> str:
        """
        Send failing code and traceback to LLM to generate an immediate syntax/logic fix.
        """
        fix_prompt = (
            f"Fix this Python tool function based on the error traceback.\n"
            f"Tool Name: {tool_name}\n\n"
            f"Traceback Error:\n{traceback_str}\n\n"
            f"Failing Code:\n```python\n{failed_code}\n```\n\n"
            f"Instructions:\n"
            f"1. Correct the error while preserving the function signature and docstring.\n"
            f"2. Ensure all required imports are included inside the function or file.\n"
            f"3. Return ONLY the valid Python code for the function, prefixed with @register_tool.\n"
            f"4. Output no conversational filler or markdown explanations outside the code block."
        )

        messages = [
            {"role": "system", "content": "You are a lead Python engineer repairing broken code. Output only clean, working Python code."},
            {"role": "user", "content": fix_prompt},
        ]

        logger.info("[AUTO-DEBUG] Requesting LLM code repair for '%s'...", tool_name)
        resp = self.router.call_llm(messages, tools=None)
        content = resp.get("content", "")
        clean_code = self.tool_manager._clean_llm_code_block(content)
        return clean_code

    def synthesize_missing_tool(self, user_prompt: str) -> Tuple[bool, str, str]:
        """
        Autonomously synthesize a new Python tool function when MJ requests
        a capability that does not yet exist.
        Returns: (success: bool, tool_name: str, message: str)
        """
        logger.info("[SYNTHESIZE] Autonomously designing new tool for: '%s'", user_prompt)

        # Step 1: Check if web search or OS inspection is needed for research
        research_context = ""
        if any(w in user_prompt.lower() for w in ("how to", "api", "library", "inspect", "scrape", "crypto", "hash")):
            try:
                research_context = web_search_and_learn(user_prompt, max_results=2, scrape_top=False)
            except Exception:
                pass

        # Step 2: Prompt LLM to design the tool
        design_prompt = (
            f"MJ requested a task that requires a new tool: \"{user_prompt}\"\n\n"
            f"Research Context (if applicable):\n{research_context[:800]}\n\n"
            f"Write a single, production-ready Python tool function to accomplish this task.\n"
            f"Requirements:\n"
            f"- Must have the decorator @register_tool above the definition.\n"
            f"- Must have clear type hints and a descriptive docstring.\n"
            f"- Must handle errors gracefully within a try/except and return a string result.\n"
            f"- Return ONLY the Python code snippet. No conversational commentary."
        )

        messages = [
            {"role": "system", "content": "You are a master Python systems architect. Write production-ready Python tools."},
            {"role": "user", "content": design_prompt},
        ]

        resp = self.router.call_llm(messages, tools=None)
        raw_code = resp.get("content", "")
        clean_code = self.tool_manager._clean_llm_code_block(raw_code)

        # Step 3: Add to dynamic_tools.py, validate AST, and hot-reload
        ok, msg = self.tool_manager.add_or_update_tool(clean_code)
        if not ok:
            logger.error("[SYNTHESIZE] Failed to register generated tool: %s", msg)
            return False, "", msg

        # Extract generated function name
        tools = self.tool_manager.get_registered_tools()
        # Find latest registered function
        new_tool_name = list(tools.keys())[-1] if tools else "unknown_tool"
        logger.info("[SYNTHESIZE] Successfully created and hot-reloaded tool: '%s'", new_tool_name)
        return True, new_tool_name, f"Synthesized and hot-reloaded tool '{new_tool_name}'."

    def run(self, user_prompt: str) -> str:
        """
        Execute prompt through autonomous ReAct loop with dynamic tool generation
        and automated debugging.
        """
        prompt = user_prompt.strip()
        if not prompt:
            return "Kaho MJ, kya karna hai?"

        # Step 1: Check if this is a request to create a new tool
        if any(trigger in prompt.lower() for trigger in ("create tool", "make a tool", "write a tool", "new skill")):
            ok, tool_name, msg = self.synthesize_missing_tool(prompt)
            if ok:
                return f"All set, MJ! Tool '{tool_name}' ban gaya aur hot-reload ho gaya. Ready to execute."
            return f"Tool creation failed: {msg}"

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
        ]
        messages.extend(list(self.history))
        messages.append({"role": "user", "content": prompt})

        for step in range(self.max_react_steps):
            schemas = self.get_all_tool_schemas()
            llm_resp = self.router.call_llm(messages, schemas)
            tool_calls = llm_resp.get("tool_calls", [])
            messages.append(llm_resp)

            # If no tool call needed, return final response
            if not tool_calls:
                content = llm_resp.get("content", "").strip() or "Task completed, MJ."
                self.history.append({"role": "user", "content": prompt})
                self.history.append({"role": "assistant", "content": content})
                self._persist_history()
                return content

            # Execute tool calls
            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args", {})

                # Check if tool exists
                if name not in self.get_all_tools():
                    # Dynamic tool synthesis trigger
                    logger.info("Tool '%s' not found. Triggering dynamic skill synthesis...", name)
                    syn_ok, syn_name, syn_msg = self.synthesize_missing_tool(f"Task: {prompt}. Missing tool: {name}")
                    if syn_ok:
                        name = syn_name

                # Execute with auto-debugging loop
                success, result = self.execute_tool_call(name, args)
                logger.info("[OBSERVE] Tool %s result: %s", name, str(result)[:120])

                messages.append({
                    "role": "tool",
                    "content": f"Observation for {name}: {result}",
                })

        # Final summary turn after tool execution
        final_resp = self.router.call_llm(messages, tools=None)
        ans = final_resp.get("content", "Done, MJ.")
        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": ans})
        self._persist_history()
        return ans


def main():
    """Interactive command-line execution interface for Shin with autonomous self-improvement."""
    engine = AutonomousShinEngine()
    mode, provider = engine.router.get_active_mode()
    tools_count = len(engine.get_all_tools())

    print("=" * 76)
    print(" SHIN AUTONOMOUS AI ASSISTANT — SELF-IMPROVEMENT & DYNAMIC SKILLS")
    print("=" * 76)
    print(f" Target User       : MJ (Meharaj Ansari)")
    print(f" Host OS           : Windows 11 (64-bit)")
    print(f" Hardware Engine   : AMD Ryzen 5 5600H (6C/12T) | 16GB RAM")
    print(f" GPU Engine        : NVIDIA GeForce RTX 3050 Laptop (4GB VRAM)")
    print(f" Active Mode       : [{mode.upper()}] {provider}")
    print(f" Active Skills     : {tools_count} tools loaded (Native + Hot-Reloaded)")
    print(f" Self-Improvement  : Auto-Tool Synthesis + 3x Recursive Debugging Loop")
    print("=" * 76)
    print("Type a command for Shin (or 'exit' to quit):\n")

    while True:
        try:
            prompt = input("MJ > ").strip()
            if not prompt:
                continue
            if prompt.lower() in ("exit", "quit", "q"):
                print("Shin: Chalti hoon MJ, milte hain!")
                break

            cur_mode, cur_prov = engine.router.get_active_mode()
            t0 = time.time()
            response = engine.run(prompt)
            dt = (time.time() - t0) * 1000

            print(f"\nShin: {response}")
            print(f"      [{cur_mode.upper()} | {dt:.1f}ms]\n")

        except KeyboardInterrupt:
            print("\nShin: Interrupted. Bye MJ!")
            break
        except Exception as exc:
            print(f"Shin: System error: {exc}\n")


if __name__ == "__main__":
    main()
