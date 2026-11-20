# Survey Report: Tool, Repository & Plugin Architecture
**Shin Voice Assistant — Explorer Survey 3**
**Author**: Explorer Agent (Survey 3)
**Date**: 2026-11-09T13:58:00Z
**Target Codebase**: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\Shin`

---

## 1. Executive Summary

This report delivers a thorough architectural investigation into the tool invocation subsystems, capability registration, schema definitions, dispatch mechanisms, external internet search pipelines, repository interaction facilities, and plugin lifecycle/sandboxing architecture in the Shin Voice Assistant codebase.

### Key Findings & Core Architectural Tension
The Shin codebase currently operates with **two parallel, un-unified execution subsystems** that were developed in separate stages and do not interoperate:

1. **The Voice Intent Dispatch Subsystem** (`assistant.py` → `core/nlp.py` → `core/commands.py`):
   - A battle-tested, voice-driven automation engine handling ~90 static capabilities (Windows OS actions, volume, Spotify, YouTube, smart home, reminders, macros, system power, etc.).
   - Driven by regex matching and LLM JSON-intent fallback in `nlp.py`.
   - Dispatches synchronously via `commands.dispatch()` using a flat dictionary mapping (`HANDLERS`).
   - Lacks formal JSON schemas; handlers expect loose `args: dict` dictionaries and manage confirmation or missing arguments via exceptions (`MissingArgument`, `ConfirmationRequired`).

2. **The Autonomous ReAct Agent & Dynamic Tool Subsystem** (`core/shin_agent.py`, `main.py`, `tool_manager.py`, `dynamic_tools.py`):
   - An advanced dual-mode agent architecture (Cloud Gemini 2.0 Flash / OpenAI vs Local Ollama on RTX 3050 & Ryzen 5 5600H) running LangGraph StateGraph or native ReAct loops.
   - Has only **4 native tools** registered (`os_operations`, `web_search_and_learn`, `inspect_active_app`, `interact_app_ui`).
   - Features a runtime self-improvement engine (`AutonomousShinEngine`) with AST validation, `importlib.reload` hot-reloading, and an automated 3-retry recursive debugging feedback loop (`ToolManager`).

### Critical Architectural Gaps
- **Subsystem Isolation**: `assistant.py` (the actual voice assistant entry point) has **no integration** with `AutonomousShinEngine` or dynamic tools. When users speak to Shin, the assistant cannot dynamically synthesize tools or invoke the ReAct autonomous loop.
- **NLP Intent Drift**: Neither `run_shin_agent`, `web_learn`, nor `inspect_active_app` are advertised in `nlp.py` (`_KNOWN_INTENTS`, `_INTENT_LIST`, or regex patterns), leaving them unreachable from standard voice commands.
- **Search Brittleness & Prompt Injection**: Web search relies on scraping DuckDuckGo HTML and deprecated Instant Answer endpoints without rate-limit protection or session pooling. Crucially, scraped web text and search results are **not passed through the CaMeL security shield** (`security_shield.py`), exposing the agent to indirect prompt injection.
- **Repository Interaction Limitations**: Git operations are limited to read-only `git status` and `git diff --stat` pointing to a hardcoded `Shin/` directory. Workspace file operations lack path traversal safeguards, syntax validation, and atomic diff previews.
- **Plugin Sandboxing Absence**: Dynamic tools in `dynamic_tools.py` are loaded directly into the host Python interpreter without process isolation, resource quotas, execution timeouts, or AST security policy checks. A malicious or looping tool can hang or crash the entire assistant process.

---

## 2. Current Tool Execution Subsystem & Dispatch Analysis

### 2.1 The Two Execution Paradigms

| Dimension | Voice Command Dispatcher (`commands.py`) | Autonomous ReAct Agent (`shin_agent.py` / `main.py`) |
|---|---|---|
| **Entry Point** | `assistant.py` via microphone/ASR | `main.py` / `shin_agent.py` via CLI REPL |
| **Routing / Planning** | `core/nlp.py` (Regex → LLM Intent JSON) | `DualModeLLMRouter` (LangGraph ReAct loop) |
| **Available Capabilities** | ~90 static automation intents | 4 native tools + dynamic tools in `dynamic_tools.py` |
| **Schema Definition** | Ad-hoc dictionary unpack (`args.get(...)`) | OpenAI-compliant JSON Schemas (`TOOL_SCHEMAS`) |
| **Execution Model** | Direct synchronous function call | Iterative Reason-Act-Observe-Synthesize loop |
| **Security Gates** | `security_shield.py` (CaMeL) + `check_command_safety()` | None on tool execution; only prompt guidelines |
| **Hot-Reloading** | None (static handlers in memory) | `ToolManager` with `importlib.reload` & AST validation |
| **Self-Debugging** | User prompted via `MissingArgument`/`Confirmation` | Automated recursive LLM fix loop (up to 3 retries) |

### 2.2 Capability Registration Mechanisms

Across the codebase, capability registration is fragmented into five separate locations:

1. **`Shin/core/commands.py: HANDLERS` (lines 4768–4948)**:
   - A static dictionary mapping string intent names to Python callable functions: `HANDLERS: Dict[str, Callable[[dict], str]]`.
   - Examples: `"open_app": open_app`, `"project_git_status": project_git_status`, `"web_search": web_search`.
2. **`Shin/core/shin_agent.py: AVAILABLE_TOOLS` (lines 674–679)**:
   - A dictionary mapping 4 tool names to functions: `os_operations`, `web_search_and_learn`, `inspect_active_app`, `interact_app_ui`.
3. **`Shin/dynamic_tools.py: DYNAMIC_REGISTRY` (lines 19–25)**:
   - A dynamic runtime dictionary populated via `@register_tool` decorator.
   - Manipulated directly by `ToolManager.add_or_update_tool()`.
4. **`Shin/core/mcp_server.py: TOOLS` (lines 19–78)**:
   - Static list of 6 MCP tools advertised to external MCP clients (Claude Desktop, Antigravity) via JSON-RPC 2.0.
5. **`Shin/core/api_manager.py: ACTION_INTENTS` (lines 89–131)**:
   - A hardcoded set of intent names used to classify whether an intent is actionable vs conversational chat.
   - **Out of sync**: Does not contain `project_git_status`, `review_code`, `calculate`, `web_learn`, `create_project_file`.

### 2.3 Schema Definitions Analysis

- **`shin_agent.py: TOOL_SCHEMAS` (lines 681–753)**:
  Uses the standard OpenAI function calling schema format:
  ```json
  {
    "type": "function",
    "function": {
      "name": "os_operations",
      "description": "Execute Windows OS tasks...",
      "parameters": {
        "type": "object",
        "properties": {
          "action": {"type": "string", "enum": [...]},
          "target": {"type": "string"},
          "content": {"type": "string"},
          "value": {"type": "integer"}
        },
        "required": ["action"]
      }
    }
  }
  ```
- **`tool_manager.py: get_tool_schemas()` (lines 229–275)**:
  Dynamically inspects Python functions in `dynamic_tools.py` using `inspect.getdoc()` and `inspect.signature()`. It derives property types from type annotations (`int` → `"integer"`, `float` → `"number"`, `bool` → `"boolean"`, `dict` → `"object"`, `list` → `"array"`, default → `"string"`) and sets `required` for parameters without default values.
- **Voice Handlers (`commands.py`)**:
  Have **no schema definitions**. Each function receives `args: dict` and must perform manual type conversions and defensive checks. For instance, `scroll_down` in `commands.py:5107` has to do:
  ```python
  try:
      lines = int(args.get("lines", 10))
  except (ValueError, TypeError):
      lines = 10
  ```

### 2.4 Self-Debugging & Dynamic Tool Hot-Reloading

`Shin/tool_manager.py` implements an innovative capability for autonomous skill synthesis:
1. **AST Validation (`validate_code_ast`)**: Before writing to disk, `ast.parse(code)` verifies that the code is syntactically sound. If a syntax error is detected, writing is aborted with line/column diagnosis.
2. **Dynamic In-Place Modification (`add_or_update_tool`)**: Uses regular expressions and AST walks to detect whether a function already exists in `dynamic_tools.py`. If found, it replaces the definition; if new, it appends with `@register_tool`. It performs a final combined AST audit on the entire file.
3. **Hot-Reloading (`reload`)**: Calls `importlib.reload(sys.modules["dynamic_tools"])` so new functions take effect in memory without restarting the Python process.
4. **Auto-Debugging Feedback Loop (`execute_with_autodebug`)**:
   - Catches runtime exceptions and captures the full `traceback.format_exc()`.
   - Calls `llm_fix_fn(tool_name, failing_code, traceback_str)`.
   - Applies the patch via `add_or_update_tool()`.
   - Hot-reloads and retries execution up to 3 times.

---

## 3. External Capability: Internet Search Execution & Result Processing

### 3.1 Audit of Existing Search Implementations

Shin accesses the internet through four different modules:

| Module | Function | Target / Protocol | Purpose |
|---|---|---|---|
| `core/live_search.py` | `smart_answer()` | DuckDuckGo Instant API → DDG HTML scraping → Wikipedia | Spoken real-time answers (no browser) |
| `core/live_search.py` | `stock_price()` | Yahoo Finance Chart API (`query1.finance.yahoo.com`) | Stock and index prices |
| `core/live_search.py` | `crypto_price()` | CoinGecko Simple Price API (`api.coingecko.com`) | Crypto prices (INR & USD) |
| `core/live_search.py` | `wikipedia_summary()` | `wikipediaapi` & `wikipedia` libraries | Factual topic summaries |
| `core/shin_agent.py` | `web_search_and_learn()` | `ddgs` library → DDG Instant API → DDG HTML scraper + BeautifulSoup | Deep research & webpage scraping for agent |
| `core/commands.py` | `web_search()` | `webbrowser.open(f"https://www.google.com/search?q={query}")` | Opens user desktop browser |
| `core/nlp.py` | `_get_live_web_context()` | `live_search.smart_answer()` / `search_web_snippets()` | Injects live web facts into LLM conversational prompt |

### 3.2 Result Processing & Scraping Pipelines

- **Web Snippet Processing (`live_search.py: search_web_snippets`)**:
  Sends HTTP GET to `https://html.duckduckgo.com/html/`, parses HTML with `BeautifulSoup`, extracts `.result__snippet` text, cleans whitespace, and caps length to 450 characters.
- **Deep Webpage Scraping (`shin_agent.py: web_search_and_learn`)**:
  When `scrape_top=True`, takes the top URL from search results, downloads HTML with a 5-second timeout, decomposes tags (`script`, `style`, `nav`, `footer`, `header`, `noscript`, `svg`), extracts clean text strings, and caps at 1,200 characters.

### 3.3 Identified Defects & Vulnerabilities in Internet Search

1. **Security Vulnerability: Prompt Injection in Web Percepts (CaMeL Violation)**:
   - `security_shield.py` contains `sanitize_untrusted_input()` specifically built to strip high-risk prompt injection directives (e.g. `ignore all previous instructions`, `<system>`, `new primary objective`).
   - However, **neither `web_search_and_learn()` nor `_get_live_web_context()` calls `sanitize_untrusted_input()`**.
   - If a search result or scraped webpage contains an injection payload, it is passed directly into the LLM context un-sanitized.
2. **API Deprecation & Blocking Risks**:
   - DuckDuckGo Instant Answer API (`api.duckduckgo.com`) no longer returns web search results for the vast majority of non-topic queries.
   - DuckDuckGo HTML endpoint (`html.duckduckgo.com`) frequently rate-limits or serves HTTP 202 / CAPTCHA pages when queried programmatically without proxy rotation or cookies.
   - No retry backoff, exponential backoff, or connection pooling is implemented.
3. **No Structured Response Format**:
   - Search results are converted directly to flattened strings. There is no structured object containing title, source URL, snippet, publication timestamp, and confidence score.
4. **Offline Blocking**:
   - When internet is disconnected, search requests block for 8 seconds before timing out, noticeably degrading speech responsiveness.

---

## 4. External Capability: Repository Interaction & Local Code Analysis

### 4.1 Existing Repository & Workspace Capabilities

| Command | File:Line | Capability |
|---|---|---|
| `project_git_status` | `commands.py:2649` | Runs `git status --porcelain=v1 -b`, parses staged/modified/untracked files, returns formatted Hinglish summary. |
| `git_diff_summary` | `commands.py:2698` | Runs `git diff --stat`, formats changed files, and copies stat summary to clipboard. |
| `create_project_file` | `commands.py:2727` | Creates a new text/code file in workspace; populates from argument or clipboard. |
| `review_code` | `commands.py:2813` | Runs AST scanner script from `.agents/skills/code-reviewer/scripts/scanner.py` to identify security vulnerabilities, anti-patterns, and style violations. |
| `run_python_code` | `commands.py:3677` | Runs Python code snippet via temporary file; passes through `check_command_safety()`. |
| `file_search` | `commands.py:4428` | Recursively searches files by name pattern across user workspace. |
| `os_operations` | `shin_agent.py:142` | Native agent tool supporting `list_dir`, `read_file`, `write_file`. |

### 4.2 Gaps & Risks in Repository Interaction

1. **Hardcoded Directory Scopes**:
   - In `commands.py`, `project_git_status` and `git_diff_summary` default to `Path(__file__).parent.parent.absolute()`, which points to `Shin/` rather than the workspace root `Shin-Voice-Assistant/`.
   - If `.git` is at the root or another project directory, relative status calculations produce inaccurate summaries.
2. **Missing Essential Git Operations**:
   - No branch management (`git branch`, `git checkout -b`).
   - No commit capability with diff review (`git commit -m`).
   - No commit history inspection (`git log -n 5 --oneline`).
   - No file-scoped diff inspection (`git diff <file>`).
3. **File System Safety Deficiencies**:
   - In `os_operations("write_file")`, there is **no path traversal protection** (`../`) and no restriction against overwriting protected files (`.env`, `voice_profile.pkl`, system DLLs).
   - In `create_project_file`, there is no AST syntax validation prior to writing Python/JS files, risking writing syntactically invalid files.
   - No atomic file backup or dry-run diff preview is provided before overwriting existing files.
4. **Code Intelligence Gaps**:
   - Code review only checks Python files using a basic AST script. It lacks language-server capabilities, symbol definition search, import tracing, or multi-file dependency graph analysis.

---

## 5. Plugin Architecture, Lifecycle & Sandboxing

### 5.1 Current Plugin & Dynamic Skill Mechanics

Shin currently has two concepts related to plugins:
1. **Dynamic Tools (`Shin/tool_manager.py` + `Shin/dynamic_tools.py`)**:
   - Synthesized at runtime by LLM.
   - Stored in a single file `dynamic_tools.py`.
   - Loaded into memory via `importlib.reload`.
2. **Agent Skills (`.agents/skills/`)**:
   - Directory-based skill specifications (e.g. `code-reviewer/SKILL.md` and `lookml-modeling-guidelines/SKILL.md`).
   - Currently invoked via **hardcoded path imports** in `commands.py:2846` (`importlib.util.spec_from_file_location(...)`).

### 5.2 Plugin Lifecycle Analysis

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Discovery   │ ──► │  Validation  │ ──► │ Loading /    │ ──► │  Execution   │
│ (Path / LLM) │     │  (AST Syntax)│     │ Hot-Reload   │     │  (In-Process)│
└──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                      │
                                                ┌─────────────────────┴───────────────┐
                                                ▼                                     ▼
                                       ┌─────────────────┐                   ┌────────────────┐
                                       │    Success      │                   │ Runtime Failure│
                                       │ (Return Result) │                   └────────┬───────┘
                                       └─────────────────┘                            │
                                                                                      ▼
                                                                             ┌────────────────┐
                                                                             │  Auto-Debug    │
                                                                             │ LLM Fix Loop   │
                                                                             │ (Max 3 retries)│
                                                                             └────────────────┘
```

### 5.3 Critical Sandboxing & Isolation Gaps

1. **Zero Process Isolation**:
   - Dynamic tools run in the **exact same Python process and memory space** as the voice assistant, Vosk speech recognizer, Pygame/Edge TTS, and WebSocket UI server.
   - If a dynamic tool calls `sys.exit()` or triggers a native C-level segfault, the entire voice assistant terminates instantly.
2. **No Execution Timeout Guard**:
   - Tools execute synchronously on the calling thread. If a tool initiates a hanging network connection or enters an infinite loop (`while True:`), Shin freezes permanently.
3. **No AST Security Auditing**:
   - `tool_manager.py: validate_code_ast()` only checks `ast.parse()` for syntax correctness.
   - It does **not inspect the AST** to block prohibited operations (e.g., `os.remove`, `ctypes`, `subprocess`, socket exfiltration, or accessing private environment variables).
4. **Monolithic Single File Failure Domain**:
   - All dynamic tools are stored in a single file (`dynamic_tools.py`).
   - If an automated fix corrupts the file or introduces an unhandled module-level import error, `importlib.reload` fails for **all** tools simultaneously.
5. **No Capability / Permission Manifest**:
   - Plugins have no declared permissions (e.g., `requires_internet: bool`, `filesystem_access: ["read", "write"]`, `requires_user_confirmation: bool`).

---

## 6. Target Architecture & Unified Interface Specifications

To resolve the architectural split and equip Shin with enterprise-grade tool execution, internet search, repository interaction, and sandboxed plugins, we specify the following unified architecture.

### 6.1 Unified `CapabilityRegistry` Architecture

The `CapabilityRegistry` bridges the Voice Intent Dispatcher, the ReAct Agent, the MCP Server, and External Plugins:

```
                          ┌────────────────────────┐
                          │   User Voice / Utter   │
                          └───────────┬────────────┘
                                      │
                                      ▼
                          ┌────────────────────────┐
                          │   Unified Router &     │
                          │   CaMeL Zero-Trust     │
                          └───────────┬────────────┘
                                      │
           ┌──────────────────────────┼──────────────────────────┐
           ▼                          ▼                          ▼
┌────────────────────┐     ┌────────────────────┐     ┌────────────────────┐
│ Voice Fast-Path    │     │ ReAct Agent Engine │     │ MCP Host Interface │
│ (Low latency <50ms)│     │ (Multi-step logic) │     │ (Claude / IDE host)│
└──────────┬─────────┘     └──────────┬─────────┘     └──────────┬─────────┘
           │                          │                          │
           └──────────────────────────┼──────────────────────────┘
                                      ▼
                       ┌─────────────────────────────┐
                       │     CapabilityRegistry      │
                       │  - Unified Tool Schemas     │
                       │  - Sandboxed Executor       │
                       │  - Hot-Reload & Health Check│
                       └──────────────┬──────────────┘
                                      │
     ┌─────────────────┬──────────────┴───────┬─────────────────┐
     ▼                 ▼                      ▼                 ▼
┌──────────────┐ ┌──────────────┐      ┌──────────────┐  ┌──────────────┐
│ Native Tools │ │ Search Engine│      │ Repo Engine  │  │ Plugin Engine│
│ (OS / Media) │ │ (DDG/Wiki)   │      │ (Git/AST/FS) │  │ (Sandboxed)  │
└──────────────┘ └──────────────┘      └──────────────┘  └──────────────┘
```

### 6.2 Standard Base Tool / Plugin Protocol

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class ToolPermission:
    allow_network: bool = False
    allow_filesystem_read: bool = False
    allow_filesystem_write: bool = False
    allow_process_spawn: bool = False
    requires_user_confirmation: bool = False

@dataclass
class ToolExecutionResult:
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    attempts_used: int = 1

class BaseTool(ABC):
    """Abstract Base Class for all Shin native tools and dynamic plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human- and LLM-readable purpose description."""
        pass

    @property
    @abstractmethod
    def permissions(self) -> ToolPermission:
        """Declared security permissions."""
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Return OpenAI/Ollama function calling JSON schema."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Execute tool logic."""
        pass

    def validate_args(self, kwargs: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate input arguments against schema."""
        return True, None
```

### 6.3 Sandboxed Execution Engine with Timeout & AST Auditing

```python
class SandboxedToolExecutor:
    """
    Executes tools and plugins with:
    1. Pre-execution AST security audit (rejecting dangerous imports).
    2. Execution timeout via ThreadPoolExecutor / ProcessPoolExecutor (preventing freeze).
    3. CaMeL prompt injection sanitization on all text outputs.
    4. Auto-debugging feedback loop for repairable errors.
    """
    def __init__(self, timeout_seconds: float = 15.0):
        self.timeout_seconds = timeout_seconds

    def audit_ast_security(self, code: str) -> Tuple[bool, Optional[str]]:
        """Verify code contains no forbidden imports or system-damaging calls."""
        # AST audit logic inspecting ast.Import, ast.ImportFrom, ast.Call
        pass

    def execute_with_timeout(self, tool: BaseTool, args: Dict[str, Any]) -> ToolExecutionResult:
        """Run tool in worker thread/process with strict timeout."""
        pass
```

### 6.4 Resilient Search Architecture

```
User Query ──► Connectivity Sentinel (15s cache)
                   │
                   ├── Offline ──► Return graceful offline notice immediately
                   │
                   └── Online ──► LRU Cache Check (15 min TTL)
                                      │
                                      ├── Cache Hit ──► Return cached structured summary
                                      └── Cache Miss ──► DDGS Primary
                                                            │
                                                            ├── Failed ──► DDG HTML Scraper Fallback
                                                            └── Failed ──► Wikipedia / Instant API
                                                            │
                                                            ▼
                                                  CaMeL Shield Sanitization
                                                  (Redact prompt injection strings)
                                                            │
                                                            ▼
                                                  Store in LRU Cache & Return
```

---

## 7. Implementation & Verification Roadmap

### Phase 1: Security Hardening & Guardrail Integration
- Pass all external search outputs and scraped web text through `security_shield.sanitize_untrusted_input()` before injecting into prompt or returning to the agent.
- Add path traversal validation (`Path.resolve()` check against allowed root workspace) and AST syntax verification to `os_operations("write_file")` and `create_project_file`.
- Add an AST security policy auditor to `tool_manager.py` that verifies generated code does not import forbidden modules (`subprocess`, `ctypes`, `os.system`).

### Phase 2: Unify Intent & Capability Registries
- Construct `CapabilityRegistry` in `Shin/core/capability_registry.py` that exports:
  - All native OS/audio/app tools with OpenAI function schemas.
  - Dynamically hot-reloaded tools from `dynamic_tools.py`.
  - Registered Agent Skills from `.agents/skills/`.
- Wire `CapabilityRegistry` into:
  - `assistant.py`: Enable the voice assistant to call ReAct and dynamic tools.
  - `core/nlp.py`: Ensure all active capabilities are included in `_KNOWN_INTENTS` and system prompts.
  - `core/mcp_server.py`: Automatically expose all registered capabilities via MCP.

### Phase 3: Modularize Dynamic Tools & Sandboxed Execution
- Transition `dynamic_tools.py` from a single monolithic file into a modular `dynamic_tools/` directory where each tool is an isolated file (`<tool_name>.py`).
- Implement execution timeout wrapper using `concurrent.futures.ThreadPoolExecutor` with a default 15-second cap.
- Enhance the auto-debugging loop in `ToolManager` to preserve modular tool files and manage per-tool rollback if auto-debug retries fail.

### Phase 4: Full Automated Test Suite Verification
- Verify that all 266 existing tests continue to pass without regressions.
- Add test suites for:
  - Sandboxed tool execution and timeout termination.
  - CaMeL prompt injection sanitization on web search results.
  - Path traversal blocking on file write operations.
  - Capability registration hot-reloading and schema extraction.
  - End-to-end voice intent execution calling dynamic tools.

---

*Survey complete. Analysis delivered to `.agents/teamwork/explorer_survey_3/survey_report.md`.*
