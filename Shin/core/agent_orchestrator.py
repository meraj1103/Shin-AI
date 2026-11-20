"""
agent_orchestrator.py — Multi-Agent Orchestration for Shin
===========================================================
Implements a supervisor pattern with specialized sub-agents:
- OSAgent: Windows operations, app control, system settings
- WebAgent: Search, scraping, API interactions
- CodeAgent: Code generation, debugging, tool synthesis
- MemoryAgent: Fact extraction, recall, summarization
- PredictiveAgent: Routine prediction, proactive suggestions
- VisionAgent: Screen OCR, UI inspection, bug diagnosis
- CommunicationAgent: WhatsApp, email, notifications

Uses LangGraph for workflow orchestration with native fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, TypedDict
from collections import deque

# Project imports
import sys
from pathlib import Path as P
_ROOT = P(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_CORE = _ROOT / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from core.shin_agent import (
    DualModeLLMRouter,
    HardwareProfile,
    build_shin_system_prompt,
    os_operations,
    web_search_and_learn,
    inspect_active_app,
    interact_app_ui,
    agent_reach_query,
    AVAILABLE_TOOLS as NATIVE_TOOLS,
    TOOL_SCHEMAS as NATIVE_SCHEMAS,
)
from tool_manager import ToolManager, get_tool_manager

logger = logging.getLogger("shin.agent_orchestrator")


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Types & Capabilities
# ═══════════════════════════════════════════════════════════════════════════════

class AgentType(Enum):
    OS = "os"
    WEB = "web"
    CODE = "code"
    MEMORY = "memory"
    PREDICTIVE = "predictive"
    VISION = "vision"
    COMMUNICATION = "communication"
    ORCHESTRATOR = "orchestrator"


@dataclass
class AgentCapability:
    """Describes what an agent can do."""
    name: str
    description: str
    tools: List[str]  # Tool names this agent can use
    keywords: List[str]  # Keywords that suggest this agent should handle the request
    priority: int = 1  # Higher = more likely to be chosen


@dataclass
class AgentContext:
    """Shared context passed between agents."""
    user_id: str = "MJ"
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    active_app: str = ""
    screen_content: str = ""
    clipboard_content: str = ""
    battery_status: Dict[str, Any] = field(default_factory=dict)
    time_of_day: str = ""
    pending_tasks: List[str] = field(default_factory=list)
    memories: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result from an agent execution."""
    success: bool
    content: str
    agent_type: AgentType
    tools_used: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Base Agent Class
# ═══════════════════════════════════════════════════════════════════════════════

class BaseAgent(ABC):
    """Base class for all specialized agents."""
    
    def __init__(
        self,
        agent_type: AgentType,
        router: DualModeLLMRouter,
        tool_manager: ToolManager,
        capabilities: List[AgentCapability],
    ):
        self.agent_type = agent_type
        self.router = router
        self.tool_manager = tool_manager
        self.capabilities = capabilities
        self.system_prompt = self._build_system_prompt()
    
    @abstractmethod
    def _build_system_prompt(self) -> str:
        """Build the agent-specific system prompt."""
        pass
    
    @abstractmethod
    async def execute(self, task: str, context: AgentContext) -> AgentResult:
        """Execute a task with the given context."""
        pass
    
    def get_available_tools(self) -> Dict[str, Callable]:
        """Get all tools available to this agent."""
        tool_names = set()
        for cap in self.capabilities:
            tool_names.update(cap.tools)
        
        all_tools = {**NATIVE_TOOLS}
        dynamic_tools = self.tool_manager.get_registered_tools()
        all_tools.update(dynamic_tools)
        
        return {k: v for k, v in all_tools.items() if k in tool_names}
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas for available tools."""
        tool_names = set()
        for cap in self.capabilities:
            tool_names.update(cap.tools)
        
        schemas = [s for s in NATIVE_SCHEMAS if s["function"]["name"] in tool_names]
        dynamic_schemas = self.tool_manager.get_tool_schemas()
        schemas.extend([s for s in dynamic_schemas if s["function"]["name"] in tool_names])
        
        return schemas
    
    def _call_llm(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call LLM with agent's tools."""
        return self.router.call_llm(messages, self.get_tool_schemas())
    
    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Execute a tool with auto-debugging for dynamic tools."""
        all_tools = self.get_available_tools()
        
        if tool_name in NATIVE_TOOLS:
            try:
                return NATIVE_TOOLS[tool_name](**args)
            except Exception as exc:
                raise Exception(f"Native tool '{tool_name}' failed: {exc}")
        
        if tool_name in self.tool_manager.get_registered_tools():
            ok, result, _ = self.tool_manager.execute_with_autodebug(
                tool_name=tool_name,
                args=args,
                llm_fix_fn=self._llm_fix_code,
                max_retries=3,
            )
            if not ok:
                raise Exception(result)
            return result
        
        raise Exception(f"Tool '{tool_name}' not available to {self.agent_type.value} agent")
    
    def _llm_fix_code(self, tool_name: str, failed_code: str, traceback_str: str) -> str:
        """Request LLM to fix broken tool code."""
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
        
        resp = self.router.call_llm(messages, tools=None)
        content = resp.get("content", "")
        return self.tool_manager._clean_llm_code_block(content)


# ═══════════════════════════════════════════════════════════════════════════════
# Specialized Agents
# ═══════════════════════════════════════════════════════════════════════════════

class OSAgent(BaseAgent):
    """Handles Windows OS operations, app control, system settings."""
    
    def _build_system_prompt(self) -> str:
        base = build_shin_system_prompt()
        return base + """
## OSAgent Specialization
You are the OS Operations Specialist for Shin. Handle:
- Launching/closing applications (Chrome, VS Code, Spotify, etc.)
- File operations (read, write, list directories)
- System controls (volume, brightness, power: lock, sleep, restart, shutdown)
- Window management (minimize, maximize, snap, scroll)

Always use the appropriate os_operations tool with correct action and parameters.
Be concise and confirm actions before executing destructive operations.
"""
    
    async def execute(self, task: str, context: AgentContext) -> AgentResult:
        start = time.time()
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Task: {task}\nContext: Active app: {context.active_app}"},
            ]
            
            resp = self._call_llm(messages)
            tool_calls = resp.get("tool_calls", [])
            content = resp.get("content", "")
            
            tools_used = []
            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args", {})
                try:
                    result = self._execute_tool(name, args)
                    content += f"\n[Tool {name}]: {result}"
                    tools_used.append(name)
                except Exception as exc:
                    content += f"\n[Tool {name} ERROR]: {exc}"
                    tools_used.append(name)
            
            return AgentResult(
                success=True,
                content=content or "OS operation completed.",
                agent_type=self.agent_type,
                tools_used=tools_used,
                execution_time_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            return AgentResult(
                success=False,
                content=f"OS Agent error: {exc}",
                agent_type=self.agent_type,
                error=str(exc),
                execution_time_ms=(time.time() - start) * 1000,
            )


class WebAgent(BaseAgent):
    """Handles web search, scraping, API interactions."""
    
    def _build_system_prompt(self) -> str:
        base = build_shin_system_prompt()
        return base + """
## WebAgent Specialization
You are the Web Intelligence Specialist for Shin. Handle:
- Web search via DuckDuckGo (web_search_and_learn)
- GitHub intelligence (trending repos, search) via agent_reach_query
- Reddit hot posts via agent_reach_query
- YouTube search via agent_reach_query
- Twitter/X search via agent_reach_query
- API interactions and documentation lookup

Always search for current, up-to-date information. Scrape top results for deep content.
Cite sources with URLs.
"""
    
    async def execute(self, task: str, context: AgentContext) -> AgentResult:
        start = time.time()
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Task: {task}"},
            ]
            
            resp = self._call_llm(messages)
            tool_calls = resp.get("tool_calls", [])
            content = resp.get("content", "")
            
            tools_used = []
            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args", {})
                try:
                    result = self._execute_tool(name, args)
                    content += f"\n[Tool {name}]: {result}"
                    tools_used.append(name)
                except Exception as exc:
                    content += f"\n[Tool {name} ERROR]: {exc}"
                    tools_used.append(name)
            
            return AgentResult(
                success=True,
                content=content or "Web search completed.",
                agent_type=self.agent_type,
                tools_used=tools_used,
                execution_time_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            return AgentResult(
                success=False,
                content=f"Web Agent error: {exc}",
                agent_type=self.agent_type,
                error=str(exc),
                execution_time_ms=(time.time() - start) * 1000,
            )


class CodeAgent(BaseAgent):
    """Handles code generation, debugging, tool synthesis."""
    
    def _build_system_prompt(self) -> str:
        base = build_shin_system_prompt()
        return base + """
## CodeAgent Specialization
You are the Code Generation & Debugging Specialist for Shin. Handle:
- Writing new Python tools/functions (dynamic tool synthesis)
- Debugging and fixing broken code
- Code review and security analysis
- Generating scripts for automation
- Explaining code concepts

When creating tools:
1. Use @register_tool decorator
2. Include type hints and docstrings
3. Handle errors gracefully with try/except
4. Return string results
5. Follow existing patterns in dynamic_tools.py
"""
    
    async def execute(self, task: str, context: AgentContext) -> AgentResult:
        start = time.time()
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Task: {task}"},
            ]
            
            resp = self._call_llm(messages)
            tool_calls = resp.get("tool_calls", [])
            content = resp.get("content", "")
            
            tools_used = []
            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args", {})
                try:
                    result = self._execute_tool(name, args)
                    content += f"\n[Tool {name}]: {result}"
                    tools_used.append(name)
                except Exception as exc:
                    content += f"\n[Tool {name} ERROR]: {exc}"
                    tools_used.append(name)
            
            return AgentResult(
                success=True,
                content=content or "Code task completed.",
                agent_type=self.agent_type,
                tools_used=tools_used,
                execution_time_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            return AgentResult(
                success=False,
                content=f"Code Agent error: {exc}",
                agent_type=self.agent_type,
                error=str(exc),
                execution_time_ms=(time.time() - start) * 1000,
            )


class MemoryAgent(BaseAgent):
    """Handles fact extraction, recall, summarization."""
    
    def _build_system_prompt(self) -> str:
        base = build_shin_system_prompt()
        return base + """
## MemoryAgent Specialization
You are the Memory & Knowledge Specialist for Shin. Handle:
- Storing personal facts and memories (save_memory)
- Recalling memories (recall_memory)
- Extracting implicit knowledge from conversations
- Summarizing conversation history
- Managing to-do items (todo_add, todo_list, todo_complete, todo_delete)

Always address MJ personally. Use female Hindi grammar.
Keep memories concise and organized.
"""
    
    async def execute(self, task: str, context: AgentContext) -> AgentResult:
        start = time.time()
        try:
            # Include relevant memories in context
            memory_context = ""
            if context.memories:
                memory_context = "\nRelevant Memories:\n" + "\n".join(
                    f"- {m.get('content', '')}" for m in context.memories[:10]
                )
            
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Task: {task}\n{memory_context}"},
            ]
            
            resp = self._call_llm(messages)
            tool_calls = resp.get("tool_calls", [])
            content = resp.get("content", "")
            
            tools_used = []
            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args", {})
                try:
                    result = self._execute_tool(name, args)
                    content += f"\n[Tool {name}]: {result}"
                    tools_used.append(name)
                except Exception as exc:
                    content += f"\n[Tool {name} ERROR]: {exc}"
                    tools_used.append(name)
            
            return AgentResult(
                success=True,
                content=content or "Memory operation completed.",
                agent_type=self.agent_type,
                tools_used=tools_used,
                execution_time_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            return AgentResult(
                success=False,
                content=f"Memory Agent error: {exc}",
                agent_type=self.agent_type,
                error=str(exc),
                execution_time_ms=(time.time() - start) * 1000,
            )


class PredictiveAgent(BaseAgent):
    """Handles routine prediction, proactive suggestions."""
    
    def _build_system_prompt(self) -> str:
        base = build_shin_system_prompt()
        return base + """
## PredictiveAgent Specialization
You are the Proactive Intelligence Specialist for Shin. Handle:
- Daily routine predictions (predict_daily_routine)
- Clipboard action predictions (predict_clipboard_action)
- App workflow predictions (predict_app_workflow)
- Power/battery event handling (handle_power_event)
- Natural time parsing for alarms/reminders
- Proactive suggestions based on context

Analyze time, active app, battery, and user patterns to predict next best actions.
Be proactive but not intrusive.
"""
    
    async def execute(self, task: str, context: AgentContext) -> AgentResult:
        start = time.time()
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Task: {task}\nContext: {context}"},
            ]
            
            resp = self._call_llm(messages)
            tool_calls = resp.get("tool_calls", [])
            content = resp.get("content", "")
            
            tools_used = []
            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args", {})
                try:
                    result = self._execute_tool(name, args)
                    content += f"\n[Tool {name}]: {result}"
                    tools_used.append(name)
                except Exception as exc:
                    content += f"\n[Tool {name} ERROR]: {exc}"
                    tools_used.append(name)
            
            return AgentResult(
                success=True,
                content=content or "Prediction completed.",
                agent_type=self.agent_type,
                tools_used=tools_used,
                execution_time_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            return AgentResult(
                success=False,
                content=f"Predictive Agent error: {exc}",
                agent_type=self.agent_type,
                error=str(exc),
                execution_time_ms=(time.time() - start) * 1000,
            )


class VisionAgent(BaseAgent):
    """Handles screen OCR, UI inspection, bug diagnosis."""
    
    def _build_system_prompt(self) -> str:
        base = build_shin_system_prompt()
        return base + """
## VisionAgent Specialization
You are the Screen Vision & UI Inspection Specialist for Shin. Handle:
- Inspecting active app UI (inspect_active_app)
- Interacting with UI elements (interact_app_ui: click, type, hotkey)
- Screen queries: read text, find text, describe screen, diagnose bugs
- Explaining code/errors visible on screen

Use inspect_active_app to understand the current window.
Use interact_app_ui for click/type/hotkey actions.
For screen queries, use appropriate screen_query modes.
"""
    
    async def execute(self, task: str, context: AgentContext) -> AgentResult:
        start = time.time()
        try:
            # Include screen content if available
            screen_context = ""
            if context.screen_content:
                screen_context = f"\nScreen Content: {context.screen_content[:2000]}"
            
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Task: {task}\nActive App: {context.active_app}{screen_context}"},
            ]
            
            resp = self._call_llm(messages)
            tool_calls = resp.get("tool_calls", [])
            content = resp.get("content", "")
            
            tools_used = []
            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args", {})
                try:
                    result = self._execute_tool(name, args)
                    content += f"\n[Tool {name}]: {result}"
                    tools_used.append(name)
                except Exception as exc:
                    content += f"\n[Tool {name} ERROR]: {exc}"
                    tools_used.append(name)
            
            return AgentResult(
                success=True,
                content=content or "Vision task completed.",
                agent_type=self.agent_type,
                tools_used=tools_used,
                execution_time_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            return AgentResult(
                success=False,
                content=f"Vision Agent error: {exc}",
                agent_type=self.agent_type,
                error=str(exc),
                execution_time_ms=(time.time() - start) * 1000,
            )


class CommunicationAgent(BaseAgent):
    """Handles WhatsApp, email, notifications."""
    
    def _build_system_prompt(self) -> str:
        base = build_shin_system_prompt()
        return base + """
## CommunicationAgent Specialization
You are the Communication Specialist for Shin. Handle:
- WhatsApp messages (send_whatsapp_message, whatsapp_call, send_whatsapp_location, send_whatsapp_file)
- WhatsApp contacts (add_whatsapp_contact, list_whatsapp_contacts, open_whatsapp_chat)
- Email operations (read_emails via gmail_ai)
- Notifications and alerts

Always confirm recipients before sending messages.
Handle both English and Hinglish contact names.
"""
    
    async def execute(self, task: str, context: AgentContext) -> AgentResult:
        start = time.time()
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Task: {task}"},
            ]
            
            resp = self._call_llm(messages)
            tool_calls = resp.get("tool_calls", [])
            content = resp.get("content", "")
            
            tools_used = []
            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args", {})
                try:
                    result = self._execute_tool(name, args)
                    content += f"\n[Tool {name}]: {result}"
                    tools_used.append(name)
                except Exception as exc:
                    content += f"\n[Tool {name} ERROR]: {exc}"
                    tools_used.append(name)
            
            return AgentResult(
                success=True,
                content=content or "Communication task completed.",
                agent_type=self.agent_type,
                tools_used=tools_used,
                execution_time_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            return AgentResult(
                success=False,
                content=f"Communication Agent error: {exc}",
                agent_type=self.agent_type,
                error=str(exc),
                execution_time_ms=(time.time() - start) * 1000,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

class AgentOrchestrator:
    """
    Multi-Agent Orchestrator using Supervisor Pattern.
    
    Routes tasks to appropriate specialized agents based on:
    - Keyword matching
    - Context analysis
    - LLM-based routing (for complex cases)
    """
    
    def __init__(self, hardware: Optional[HardwareProfile] = None):
        self.hardware = hardware or HardwareProfile()
        self.router = DualModeLLMRouter(self.hardware)
        self.tool_manager = get_tool_manager()
        
        # Initialize specialized agents
        self.agents: Dict[AgentType, BaseAgent] = {}
        self._init_agents()
        
        # Routing keywords for fast path
        self.routing_keywords = self._build_routing_keywords()
        
        # Execution history for learning
        self.execution_history: deque = deque(maxlen=100)
    
    def _init_agents(self):
        """Initialize all specialized agents with their capabilities."""
        
        # OS Agent
        os_caps = [
            AgentCapability(
                name="os_operations",
                description="Windows OS operations: launch apps, file ops, volume, brightness, power",
                tools=["os_operations"],
                keywords=["open", "launch", "close", "volume", "brightness", "lock", "sleep", "shutdown", "restart", "file", "folder", "directory", "app"],
                priority=10,
            ),
        ]
        self.agents[AgentType.OS] = OSAgent(AgentType.OS, self.router, self.tool_manager, os_caps)
        
        # Web Agent
        web_caps = [
            AgentCapability(
                name="web_search",
                description="Web search and learning",
                tools=["web_search_and_learn"],
                keywords=["search", "google", "learn", "find", "lookup", "internet", "web"],
                priority=8,
            ),
            AgentCapability(
                name="github_intel",
                description="GitHub trending and search",
                tools=["agent_reach_query"],
                keywords=["github", "repo", "repository", "trending"],
                priority=7,
            ),
            AgentCapability(
                name="reddit_intel",
                description="Reddit hot posts",
                tools=["agent_reach_query"],
                keywords=["reddit", "r/", "subreddit"],
                priority=7,
            ),
        ]
        self.agents[AgentType.WEB] = WebAgent(AgentType.WEB, self.router, self.tool_manager, web_caps)
        
        # Code Agent
        code_caps = [
            AgentCapability(
                name="tool_synthesis",
                description="Dynamic tool creation and debugging",
                tools=["synthesize_missing_tool"],  # This is handled by main engine
                keywords=["create tool", "write code", "generate", "script", "function", "debug", "fix code"],
                priority=9,
            ),
        ]
        self.agents[AgentType.CODE] = CodeAgent(AgentType.CODE, self.router, self.tool_manager, code_caps)
        
        # Memory Agent
        memory_caps = [
            AgentCapability(
                name="memory_ops",
                description="Memory save/recall and todo management",
                tools=["save_memory", "recall_memory", "delete_memories", "todo_add", "todo_list", "todo_complete", "todo_delete"],
                keywords=["remember", "memory", "forget", "todo", "task", "note", "save"],
                priority=8,
            ),
        ]
        self.agents[AgentType.MEMORY] = MemoryAgent(AgentType.MEMORY, self.router, self.tool_manager, memory_caps)
        
        # Predictive Agent
        pred_caps = [
            AgentCapability(
                name="predictions",
                description="Routine, clipboard, and app workflow predictions",
                tools=["predict_daily_routine", "predict_clipboard_action", "predict_app_workflow", "handle_power_event"],
                keywords=["predict", "routine", "next", "suggest", "clipboard", "battery", "power"],
                priority=6,
            ),
        ]
        self.agents[AgentType.PREDICTIVE] = PredictiveAgent(AgentType.PREDICTIVE, self.router, self.tool_manager, pred_caps)
        
        # Vision Agent
        vision_caps = [
            AgentCapability(
                name="screen_vision",
                description="Screen OCR, UI inspection, bug diagnosis",
                tools=["inspect_active_app", "interact_app_ui", "screen_query", "explain_screen_activity", "screen_diagnose_bug"],
                keywords=["screen", "window", "ui", "click", "type", "inspect", "read screen", "describe", "bug", "error"],
                priority=9,
            ),
        ]
        self.agents[AgentType.VISION] = VisionAgent(AgentType.VISION, self.router, self.tool_manager, vision_caps)
        
        # Communication Agent
        comm_caps = [
            AgentCapability(
                name="whatsapp",
                description="WhatsApp messaging and calls",
                tools=["send_whatsapp_message", "whatsapp_call", "send_whatsapp_location", "send_whatsapp_file", "add_whatsapp_contact", "list_whatsapp_contacts", "open_whatsapp_chat"],
                keywords=["whatsapp", "message", "text", "call", "contact"],
                priority=9,
            ),
        ]
        self.agents[AgentType.COMMUNICATION] = CommunicationAgent(AgentType.COMMUNICATION, self.router, self.tool_manager, comm_caps)
    
    def _build_routing_keywords(self) -> Dict[AgentType, List[str]]:
        """Build keyword-to-agent mapping for fast routing."""
        mapping = {}
        for agent_type, agent in self.agents.items():
            keywords = []
            for cap in agent.capabilities:
                keywords.extend(cap.keywords)
            mapping[agent_type] = list(set(keywords))
        return mapping
    
    def route_task(self, task: str, context: AgentContext) -> List[AgentType]:
        """
        Route a task to one or more agents based on keywords and context.
        Returns ordered list of agent types to try.
        """
        task_lower = task.lower()
        scores = {}
        
        # Score each agent based on keyword matches
        for agent_type, keywords in self.routing_keywords.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > 0:
                scores[agent_type] = score
        
        # Context-based scoring
        if context.active_app:
            if any(app in context.active_app.lower() for app in ["chrome", "edge", "firefox", "browser"]):
                scores[AgentType.WEB] = scores.get(AgentType.WEB, 0) + 2
            if any(app in context.active_app.lower() for app in ["code", "pycharm", "vscode", "visual studio"]):
                scores[AgentType.CODE] = scores.get(AgentType.CODE, 0) + 3
        
        if context.clipboard_content:
            scores[AgentType.PREDICTIVE] = scores.get(AgentType.PREDICTIVE, 0) + 1
        
        # Sort by score descending
        sorted_agents = sorted(scores.keys(), key=lambda a: scores[a], reverse=True)
        
        # Default to OS agent if no clear match
        if not sorted_agents:
            sorted_agents = [AgentType.OS]
        
        return sorted_agents
    
    async def execute(self, task: str, context: Optional[AgentContext] = None) -> AgentResult:
        """
        Execute a task by routing to appropriate agent(s).
        Tries agents in order until one succeeds.
        """
        if context is None:
            context = AgentContext()
        
        # Update context with current time
        context.time_of_day = datetime.now().strftime("%H:%M")
        
        # Route task
        agent_types = self.route_task(task, context)
        logger.info(f"Routing task to agents: {[a.value for a in agent_types]}")
        
        last_error = None
        for agent_type in agent_types:
            agent = self.agents.get(agent_type)
            if not agent:
                continue
            
            try:
                result = await agent.execute(task, context)
                if result.success:
                    # Record successful execution
                    self.execution_history.append({
                        "task": task,
                        "agent": agent_type.value,
                        "success": True,
                        "time": datetime.now().isoformat(),
                    })
                    return result
                else:
                    last_error = result.error
                    logger.warning(f"Agent {agent_type.value} failed: {last_error}")
            except Exception as exc:
                last_error = str(exc)
                logger.error(f"Agent {agent_type.value} exception: {exc}")
        
        # All agents failed
        return AgentResult(
            success=False,
            content=f"All agents failed. Last error: {last_error}",
            agent_type=AgentType.ORCHESTRATOR,
            error=last_error,
        )
    
    async def execute_parallel(self, task: str, context: Optional[AgentContext] = None) -> List[AgentResult]:
        """Execute task on multiple agents in parallel and return all results."""
        if context is None:
            context = AgentContext()
        
        agent_types = self.route_task(task, context)
        tasks = [self.agents[at].execute(task, context) for at in agent_types if at in self.agents]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, AgentResult):
                valid_results.append(result)
            elif isinstance(result, Exception):
                valid_results.append(AgentResult(
                    success=False,
                    content=f"Agent {agent_types[i].value} exception: {result}",
                    agent_type=agent_types[i],
                    error=str(result),
                ))
        
        return valid_results
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents."""
        return {
            "agents": {
                at.value: {
                    "capabilities": [c.name for c in agent.capabilities],
                    "tools": [c.tools for c in agent.capabilities],
                }
                for at, agent in self.agents.items()
            },
            "routing_keywords": {k.value: v for k, v in self.routing_keywords.items()},
            "history_count": len(self.execution_history),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance & Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

_GLOBAL_ORCHESTRATOR: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """Get or create the global orchestrator instance."""
    global _GLOBAL_ORCHESTRATOR
    if _GLOBAL_ORCHESTRATOR is None:
        _GLOBAL_ORCHESTRATOR = AgentOrchestrator()
    return _GLOBAL_ORCHESTRATOR


async def run_orchestrator(prompt: str, context: Optional[AgentContext] = None) -> str:
    """Entry point for running the multi-agent orchestrator."""
    orchestrator = get_orchestrator()
    result = await orchestrator.execute(prompt, context)
    return result.content


# ═══════════════════════════════════════════════════════════════════════════════
# Testing
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    async def test():
        orchestrator = AgentOrchestrator()
        
        # Test routing
        test_tasks = [
            "Open Chrome browser",
            "Search for Python async tutorial",
            "Set volume to 50",
            "Remember that I like dark mode",
            "What's on my screen?",
            "Send WhatsApp to Mom saying I'm home",
        ]
        
        for task in test_tasks:
            agents = orchestrator.route_task(task, AgentContext())
            print(f"Task: {task}")
            print(f"  Routed to: {[a.value for a in agents]}")
            print()
        
        # Test execution
        result = await orchestrator.execute("What time is it?")
        print(f"Result: {result.content}")
    
    asyncio.run(test())