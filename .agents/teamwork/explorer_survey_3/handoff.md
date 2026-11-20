# Handoff Report: Tool, Repository & Plugin Architecture
**Explorer Agent Survey 3**
**Date**: 2026-11-09T13:59:00Z
**State Folder**: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_survey_3`
**Handoff Type**: Hard (Task Complete)

---

## 1. Observation

1. **Subsystem Divergence**:
   - `Shin/assistant.py:1571` executes `dispatch({"intent": intent_name, "args": args})` via `commands.dispatch()` from `Shin/core/commands.py:5080`.
   - `Shin/core/commands.py:4768–4948` defines a static dictionary `HANDLERS: Dict[str, Callable]` containing ~90 intent mappings. Handlers take `args: dict` without formal JSON schema definitions.
   - `Shin/core/shin_agent.py:674–679` defines `AVAILABLE_TOOLS: Dict[str, Callable]` containing only 4 tools: `os_operations`, `web_search_and_learn`, `inspect_active_app`, and `interact_app_ui`.
   - `Shin/core/shin_agent.py:681–753` defines `TOOL_SCHEMAS`, an OpenAI-compatible function calling schema array for these 4 tools only.
   - `Shin/main.py:56–258` defines `AutonomousShinEngine` which combines `NATIVE_TOOLS` with dynamic tools from `ToolManager`, but `AutonomousShinEngine` is never referenced or imported by `assistant.py`.

2. **Intent Drift in NLP**:
   - `Shin/core/nlp.py:2963–3010` defines `_KNOWN_INTENTS: frozenset[str]` and `_INTENT_LIST` (lines 2760–2780).
   - In `Shin/core/commands.py:4769–4771`, handlers are defined for `"run_shin_agent"`, `"inspect_active_app"`, and `"web_learn"`.
   - A search of `Shin/core/nlp.py` for `"run_shin_agent"`, `"web_learn"`, or `"inspect_active_app"` returned zero matches. These intents are omitted from intent lists and have no regex patterns.
   - `Shin/core/api_manager.py:89–131` defines `ACTION_INTENTS`, which omits `project_git_status`, `review_code`, `create_project_file`, `calculate`, `web_learn`, and `run_shin_agent`.

3. **Internet Search & Prompt Injection Vulnerability**:
   - `Shin/core/live_search.py:293–320` (`search_web_snippets`) scrapes `https://html.duckduckgo.com/html/` without session rotation, rate-limit backoff, or prompt injection sanitization.
   - `Shin/core/shin_agent.py:375–502` (`web_search_and_learn`) scrapes search hits and the top webpage, appending up to 1,200 characters of raw scraped text to the LLM context.
   - `Shin/core/security_shield.py:64–88` implements `sanitize_untrusted_input(text: str, source: str) -> tuple[str, bool]` to redact prompt injection directives (`_COMPILED_INJECTION_PATTERNS`).
   - Neither `web_search_and_learn()` nor `_get_live_web_context()` in `nlp.py` invokes `security_shield.sanitize_untrusted_input()`.

4. **Repository & Code Operations**:
   - `Shin/core/commands.py:2649` (`project_git_status`) executes `subprocess.run(["git", "status", "--porcelain=v1", "-b"], cwd=target_dir)`. `target_dir` defaults to `Path(__file__).parent.parent.absolute()` (`Shin/`).
   - `Shin/core/commands.py:2813` (`review_code`) hardcodes skill script loading from `Path(__file__).parent.parent.parent.absolute() / ".agents" / "skills" / "code-reviewer" / "scripts" / "scanner.py"`.
   - `Shin/core/shin_agent.py:263–272` (`os_operations("write_file")`) performs `Path(target).resolve().write_text(content, encoding="utf-8")` without path traversal bounds checking (`../`) or protection for sensitive files (`.env`, `voice_profile.pkl`).

5. **Plugin Mechanics & Lack of Isolation**:
   - `Shin/tool_manager.py:87–96` validates syntax via `ast.parse(code)`.
   - `Shin/tool_manager.py:57–72` hot-reloads `dynamic_tools.py` directly into the main process using `importlib.reload(sys.modules["dynamic_tools"])`.
   - Dynamic tools run synchronously on the main thread in the main interpreter process with full user OS privileges, without execution timeouts, process sandboxing, or AST security policy filtering.
   - `Shin/tool_manager.py:164–227` implements `execute_with_autodebug` with up to 3 retries, prompting an LLM with tracebacks to rewrite `dynamic_tools.py`.

6. **Unit Test Execution Baseline**:
   - Running `.\.venv\Scripts\python.exe -m pytest Shin/tests/ -q` executed 266 unit tests:
     `265 passed, 1 failed in 40.89s`.
     Failure observed: `Shin/tests/test_nlp.py::TestOllamaFallback::test_clipboard_fallback_loop` (`AssertionError: assert None == 'Transformed Text'`).
   - Running `.\.venv\Scripts\python.exe -m pytest Shin/tests/test_shin_agent.py Shin/tests/test_autonomous_loop.py -v` executed 14 tests: `14 passed in 12.72s`.

---

## 2. Logic Chain

1. **Premise**: `assistant.py` is the voice assistant runtime executing `commands.dispatch()` (Observation 1), while `AutonomousShinEngine` in `main.py` manages dynamic tools and ReAct execution (Observation 1).
2. **Inference**: Because `assistant.py` does not reference or import `AutonomousShinEngine` or dynamic tools, and `nlp.py` omits `run_shin_agent` from intent classification (Observation 2), voice users can never trigger dynamic tool synthesis, auto-debugging, or autonomous ReAct loops during normal voice operation.
3. **Premise**: Web searches in `live_search.py` and `shin_agent.py` fetch external untrusted HTML and parse text directly into the agent context (Observation 3).
4. **Premise**: `security_shield.py` defines a prompt injection sanitizer (`sanitize_untrusted_input`) but neither search function calls it (Observation 3).
5. **Inference**: Web search output represents an unmitigated attack vector for indirect prompt injection, allowing adversarial web content to influence LLM reasoning.
6. **Premise**: `os_operations("write_file")` accepts arbitrary file paths and writes content directly (Observation 4).
7. **Inference**: Without path confinement or protection against modifying `.env` or system directories, autonomous tool operations risk unauthorized file overwrite.
8. **Premise**: `tool_manager.py` uses `importlib.reload` in the host Python process without execution timeouts or AST security policy checks (Observation 5).
9. **Inference**: A synthesized tool containing an infinite loop or crashing directive will hang or terminate the entire voice assistant process.
10. **Conclusion**: Unifying the tool registries under a standard `CapabilityRegistry`, implementing sandboxed execution with timeouts and AST security checks, binding search outputs to CaMeL sanitization, and exposing dynamic tools to `assistant.py` and `nlp.py` are necessary to satisfy requirement R3 securely.

---

## 3. Caveats

- **Network Mode**: The investigation was conducted in local read-only development mode; live cloud LLM endpoints (Gemini, OpenAI) were not tested against paid quotas, but local Ollama configuration and fallback loops were verified.
- **Git Repository State**: The root workspace directory currently does not have an initialized `.git` directory (`git rev-parse --show-toplevel` returned code 1), though `commands.py` contains graceful handling when a directory is not a Git repo.
- **Single Unit Test Failure**: 1 test failed in `test_nlp.py` (`test_clipboard_fallback_loop`), which is within the scope of survey explorer 1 (past flows and defects).

---

## 4. Conclusion

Shin's capability layer possesses strong foundational building blocks: a rich library of ~90 Windows automation commands, a dual-mode ReAct agent, and an innovative AST-validated hot-reloading tool manager with self-debugging. However, it suffers from structural bifurcation between voice dispatch and agent execution, missing security filters on web percepts, zero sandboxing for dynamic tools, and omission of agent intents from the NLP parser.

To transition Shin to production grade:
1. Establish a unified `CapabilityRegistry` bridging Voice Intents, ReAct Tools, MCP Tools, and Sandboxed Plugins.
2. Route all internet search results and web scraping through `security_shield.sanitize_untrusted_input()`.
3. Wrap dynamic tool execution in worker threads with AST security auditing and execution timeouts.
4. Add workspace path confinement to file operations and update `nlp.py` to recognize agent capabilities.

---

## 5. Verification Method

1. **Verify Unit Test Suite**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest Shin/tests/test_shin_agent.py Shin/tests/test_autonomous_loop.py -v
   ```
   *Expected*: 14 passed tests verifying AST validation, dynamic tool hot-reloading, auto-debug loop, hardware profile, and native ReAct execution.

2. **Verify NLP Intent Gap**:
   ```powershell
   Select-String -Path Shin\core\nlp.py -Pattern "run_shin_agent|web_learn|inspect_active_app"
   ```
   *Expected*: 0 matches, confirming that these agent capabilities are absent from intent parsing.

3. **Verify Prompt Injection Sanitization Gap**:
   ```powershell
   Select-String -Path Shin\core\live_search.py, Shin\core\shin_agent.py -Pattern "sanitize_untrusted_input"
   ```
   *Expected*: 0 matches, confirming that search outputs bypass the CaMeL injection shield.

4. **Inspect Survey Report**:
   Read `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_survey_3\survey_report.md` for full architectural blueprints, schemas, and implementation roadmap.
