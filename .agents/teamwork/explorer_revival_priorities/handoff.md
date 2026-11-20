# Handoff Report: Revival Priorities Technical Investigation

**Author**: Revival Priorities Explorer  
**Task**: Technical Investigation & Architecture Blueprint for 6 User-Directed Revival Priorities  
**Working Directory**: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant`  
**State Folder**: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_revival_priorities`  
**Date**: 2026-11-09  

---

## 1. Observation

### Observation 1.1: Baseline Test Suite Status
Executed `.\.venv\Scripts\pytest Shin\tests\ -q`:
- **Tool Result**: `297 passed, 3 warnings in 31.49s`.
- Specific breakdown:
  - `Shin\tests\test_nlp.py`: 204 passed
  - `Shin\tests\test_real_life_scenarios.py`: 31 passed
  - `Shin\tests\test_shin_agent.py`: 10 passed
  - `Shin\tests\test_advanced_logic_and_personality.py`: 29 passed
  - `Shin\tests\test_autonomous_loop.py`: 5 passed
  - `Shin\tests\test_gestures.py`: 8 passed
  - `Shin\tests\test_security_hardening.py`: 8 passed
  - `Shin\tests\test_voice_bypass.py`: 2 passed

### Observation 1.2: Priority 1 (Voice Realism & TTS Architecture)
- `Shin/.env`:
  - Line 44: `TTS_BACKEND=edge`
  - Line 46: `TTS_SPEED=1.0`
  - Line 49: `EDGE_TTS_VOICE=hi-IN-SwaraNeural`
  - Line 50: `EDGE_TTS_VOICE_EN=en-IN-NeerjaNeural`
  - Line 52: `TTS_PITCH=+8Hz`
- `Shin/assistant.py`:
  - Lines 136–141: `EDGE_TTS_VOICE: str = os.getenv("EDGE_TTS_VOICE", "hi-IN-SwaraNeural")`, `EDGE_TTS_VOICE_EN: str = os.getenv("EDGE_TTS_VOICE_EN", "en-IN-NeerjaNeural")`, `TTS_PITCH: str = os.getenv("TTS_PITCH", "+0Hz")`.
  - Lines 379–467: `_speak_edge(text: str)` uses `edge-tts.Communicate(text, voice=voice, rate=rate_str, pitch=pitch_str, volume="+0%")`.
  - Line 1243: `set_voice_pitch(pitch_val: str, label: str = "") -> str` dynamically updates pitch and writes to `.env`.
  - In `Shin/core/macros.py:139`: Explicit note: `"The TTS function from assistant.py — injected to avoid circular imports."`
- Microsoft Edge TTS Voice API:
  - Executed `edge_tts.list_voices()`: Confirmed `en-IN-NeerjaExpressiveNeural` (Female, en-IN) and `en-IN-NeerjaNeural` (Female, en-IN) are live and available.

### Observation 1.3: Priority 2 (Agent-Reach Integration)
- `C:\Users\Mehar\.gemini\config\skills\agent-reach\SKILL.md`: Defines zero-API live data extraction across Twitter, Reddit, YouTube, GitHub, and RSS via `python -m agent_reach run <platform> <action>`.
- In `.venv`: Running `python -m agent_reach` returns `No module named agent_reach`.
- `Shin/core/shin_agent.py`:
  - Lines 674–679: `AVAILABLE_TOOLS = {"os_operations": os_operations, "web_search_and_learn": web_search_and_learn, "inspect_active_app": inspect_active_app, "interact_app_ui": interact_app_ui}`.
  - Querying "What is trending on GitHub today?" in `nlp.parse_intent()` returned `{'intent': 'chat', ...}` (unhandled fallback).

### Observation 1.4: Priority 3 (Clipboard AI)
- `Shin/core/predictive_engine.py:122`: `predict_clipboard_action(self, clipboard_text: Optional[str] = None) -> Dict[str, Any]` is fully implemented and tested.
- `Shin/core/nlp.py:1412–1448`: Contains intents for `clipboard_translate`, `clipboard_rewrite`, `clipboard_summarize`, `clipboard_fix`, `clipboard_history`, `read_clipboard`.
- Testing `nlp.parse_intent('analyze my clipboard')` and `'check my clipboard'` returned `{'intent': 'chat', ...}`.
- `Shin/core/commands.py:4964–5160`: `HANDLERS` dictionary lacks any `analyze_clipboard` entry.

### Observation 1.5: Priority 4 (Shin Intelligence & Missed Intents)
- `Shin/data/missed_intents.log`:
  - Line 36: `han english mein baat karo` -> falls back to `chat`.
  - Line 108: `aur bhai fir` -> falls back to `chat`.
  - Line 115: `what ise your name` -> falls back to Wikipedia search which fails.
  - Line 265: `aur kuchh nahin` -> falls back to `chat`.

### Observation 1.6: Priority 5 (Memory Persistence)
- `Shin/core/memory.py`:
  - Line 9: `MEMORY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "memory.json")`.
  - Lines 27–52: `load_memories()` and atomic `save_memories()`.
  - `Shin/data/memory.json` exists on disk with 42 lines containing user profile facts.
  - No file named `memories.json` exists, and no synchronization exists if an external caller targets `memories.json`.
  - `commands.py:1118`: `store_relationship(args)` calls `memory.add_memory()`.

### Observation 1.7: Priority 6 (Conversation Context)
- `Shin/core/shin_agent.py:1232–1241` & `1256–1261`: Both `ShinReActEngine.run(prompt)` and `_run_native_react(prompt)` initialize `messages` as `[{"role": "system", ...}, {"role": "user", "content": prompt}]`. Context from previous turns is discarded.
- `Shin/main.py:216–219`: `AutonomousShinEngine.run(user_prompt)` initializes `messages` as `[{"role": "system", ...}, {"role": "user", ...}]`. Context from previous turns is discarded.
- `Shin/core/nlp.py:188 & 217`: `_CONVERSATION_HISTORY = collections.deque(maxlen=20)` and `_HISTORY_FILE = Path(...) / "data" / "conversation_history.json"` exist in `nlp.py`, demonstrating the established 20-message / 10-turn pattern.

---

## 2. Logic Chain

1. **Test Stability (from Obs 1.1)**:
   - 297 unit tests are currently passing across all test files.
   - Any modifications across the 6 priorities must maintain zero regressions on these 297 tests.

2. **Voice Architecture (from Obs 1.2)**:
   - Microsoft Edge TTS is configured in `.env` and `assistant.py`.
   - `assistant.py` currently houses the entire TTS implementation, creating circular import hazards for core modules (noted in `macros.py:139`).
   - Extracting TTS logic into `Shin/core/tts.py` while keeping `assistant.py` as a backward-compatible wrapper modularizes the system.
   - Adding `en-IN-NeerjaExpressiveNeural` (with fallback to `en-IN-NeerjaNeural`) and maintaining `+4Hz` to `+8Hz` pitch gives Shin an authentic, youthful Indian female voice.

3. **Agent-Reach Design (from Obs 1.3)**:
   - Because `agent_reach` CLI is not pre-installed in the virtual environment, relying solely on `python -m agent_reach` would fail in production.
   - Therefore, a dual-layer tool `agent_reach_query` is necessary:
     - Layer 1: Invokes CLI if installed.
     - Layer 2: Directly executes zero-API scrapers / public JSON APIs (GitHub public search API for trending repos, Reddit `.json` public endpoints, YouTube DuckDuckGo scrape, Jina Reader for Twitter).
   - Registering `agent_reach_query` into `shin_agent.py`'s `AVAILABLE_TOOLS` and `TOOL_SCHEMAS` enables both LLM tool calling and fast-path regex execution.

4. **Clipboard AI Integration (from Obs 1.4)**:
   - `predictive_engine.predict_clipboard_action()` is already functional and tested.
   - Adding an intent rule in `Shin/core/nlp.py` (`r"\b(?:analyze|analyse|check|inspect|examine|predict)\s+(?:my\s+)?clipboard\b"`) routes clipboard requests to a new handler `analyze_clipboard` in `Shin/core/commands.py`.
   - The handler simply queries `predictive_engine.predict_clipboard_action()` and speaks the result.

5. **Missed Intents & NLP Tuning (from Obs 1.5)**:
   - Real-life logs prove that user interactions fail on:
     - Language switching ("han english mein baat karo") -> should route to `set_language`.
     - Casual greetings ("aur bhai fir") -> should return friendly chat response without web search.
     - Dismissals ("aur kuchh nahin") -> should politely acknowledge end-of-turn.
     - Common typos ("what ise your name") -> should resolve to identity query.
   - Adding these targeted regex patterns directly solves the failure modes documented in `missed_intents.log`.

6. **Memory Persistence Resilience (from Obs 1.6)**:
   - Relationships are saved to `Shin/data/memory.json`.
   - To prevent errors when callers look for `memories.json` vs `memory.json`, `memory.py` should load from either file and save to both.
   - In addition, calling `nlp.invalidate_memory_cache()` on save ensures newly added memories are immediately visible to prompt construction.

7. **Multi-Turn Conversation Memory (from Obs 1.7)**:
   - Both `shin_agent.py` and `main.py` forget conversation turns because they recreate message lists from scratch.
   - Adding a 10-turn rolling buffer (`collections.deque(maxlen=20)`) in `ShinReActEngine` and `AutonomousShinEngine`, persisted to `Shin/data/conversation_history.json`, enables full multi-turn conversational context for LLM calls while preventing context overflow.

---

## 3. Caveats

- **No Caveats on Core Functionality**: All 6 priority areas were directly investigated with concrete source files and live tests.
- **Network Dependency for Live Agent-Reach & Edge-TTS**:
  - Live Edge-TTS and live GitHub trending require active internet connectivity. In offline environments, the existing `_speak_pyttsx3` / `_speak_kokoro` fallback chain and local cached knowledge handle execution gracefully.
- **Read-Only Investigation Scope**: Per instructions, no production code has been modified during this exploration phase. All proposed edits are documented in detail in `blueprint.md`.

---

## 4. Conclusion

The Shin Voice Assistant is in a stable state (297/297 passing tests), and the roadmap for all 6 revival priorities is clear:
1. **Voice Realism**: Create `Shin/core/tts.py` supporting `en-IN-NeerjaExpressiveNeural` / `en-IN-NeerjaNeural` with `+8Hz` pitch and clean exports.
2. **Agent-Reach**: Implement `agent_reach_query` in `Shin/core/shin_agent.py` with zero-API fallbacks for GitHub, Reddit, YouTube, and Twitter.
3. **Clipboard AI**: Connect `analyze_clipboard` in `nlp.py` and `commands.py` to `predictive_engine.predict_clipboard_action()`.
4. **Shin Intelligence**: Add regex rules in `nlp.py` for language switching, polite dismissals, casual greetings, and typo tolerance.
5. **Memory Persistence**: Implement dual-file synchronization (`memory.json` / `memories.json`) and immediate cache invalidation in `memory.py`.
6. **Conversation Context**: Implement a rolling 10-turn (20 message) buffer in `ShinReActEngine` and `AutonomousShinEngine` persisted to disk.

All specifications, code blocks, and integration points are fully documented in `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_revival_priorities\blueprint.md`.

---

## 5. Verification Method

To independently verify this investigation:
1. **Run Baseline Test Suite**:
   ```powershell
   .\.venv\Scripts\pytest Shin\tests\ -q
   ```
   *Expected outcome*: 297 passed, 3 warnings in ~31s.
2. **Verify Edge-TTS Voices**:
   ```powershell
   .\.venv\Scripts\python -c "import asyncio, edge_tts; voices = asyncio.run(edge_tts.list_voices()); print([v['ShortName'] for v in voices if 'en-IN' in v['Locale']])"
   ```
   *Expected outcome*: `['en-IN-NeerjaExpressiveNeural', 'en-IN-NeerjaNeural', 'en-IN-PrabhatNeural']`.
3. **Verify Clipboard Predictive Engine**:
   ```powershell
   .\.venv\Scripts\pytest Shin\tests\test_real_life_scenarios.py -k "clipboard" -q
   ```
   *Expected outcome*: 4 passed.
4. **Inspect Blueprint and Reports**:
   - `Shin/.agents/teamwork/explorer_revival_priorities/blueprint.md`
   - `Shin/.agents/teamwork/explorer_revival_priorities/handoff.md`
