# Project: Shin Voice Assistant Upgrade & Stabilization

## Architecture
Shin Voice Assistant is a dual-paradigm voice AI assistant combining:
1. **Low-Latency Voice Interaction Loop** (`Shin/assistant.py`): Real-time ASR (Google/Vosk), NLP intent classification (`Shin/core/nlp.py`), Maharashtrian-Dakhni Hinglish persona (`Shin/core/personality.py`), and modular neural speech playback (`Shin/core/tts.py` with `edge-tts`, Kokoro-82M, pyttsx3, SAPI).
2. **Autonomous Tool & ReAct Engine** (`Shin/core/shin_agent.py`, `Shin/main.py`, `Shin/tool_manager.py`): Dual-mode LLM reasoning (Cloud Gemini/OpenAI vs Local Ollama), dynamic tool synthesis with AST validation and hot-reloading, zero-trust CaMeL prompt injection defense (`Shin/core/security_shield.py`), and live multi-platform reach (`agent_reach_query` for GitHub, Reddit, YouTube, Twitter).
3. **Conversational Memory & Context Subsystem** (`Shin/core/memory.py`, `Shin/data/conversation_history.json`): Dual-file persistent memory (`memory.json` & `memories.json`), atomic disk writes, instant NLP cache invalidation, and a rolling 10-turn (20 messages) conversation buffer.
4. **Predictive AI & Clipboard Engine** (`Shin/core/predictive_engine.py`): Automatic context analysis of clipboard data (code, URLs, percentage math, error tracebacks) with spoken Hinglish recommendations via `analyze_clipboard`.
5. **Voice Realism Subsystem** (`Shin/core/tts.py`): Indian English female neural voice (`en-IN-NeerjaExpressiveNeural` / `en-IN-NeerjaNeural`), `+8Hz` pitch tuning, automatic Devanagari Hindi/Marathi detection, and audio normalization.

---

## Feature Inventory
Every requirement and surveyed defect/opportunity mapped to a milestone:

| # | Feature | Description | Milestone | Source | Status |
|---|---------|-------------|-----------|--------|--------|
| 1 | Orb Window Hex Fix | Fix `#00000000` invalid hex triplet crash in `Shin/core/orb_window.py` | M1 | Survey 1 | DONE |
| 2 | Edge-TTS Subprocess Scoping Fix | Fix `UnboundLocalError: cannot access local variable 'subprocess'` in `assistant.py` | M1 | Survey 1 | DONE |
| 3 | MediaPipe 1.1.0 Gesture Compatibility | Fix `AttributeError: module 'mediapipe' has no attribute 'solutions'` in `gestures.py` | M1 | Survey 1 | DONE |
| 4 | Vosk Offline ASR Path Resolution | Fix relative `./languages/...` path failure when Shin runs from workspace root | M1 | Survey 1 | DONE |
| 5 | Kokoro Serialization & Watchdog Stabilization | Resolve `__reduce_cython__` error and prevent 60s TTS queue stalls | M1 | Survey 1 | DONE |
| 6 | Test Suite Disk Hygiene | Prevent `test_autonomous_loop.py` from mutating production `Shin/dynamic_tools.py` | M1 | Survey 1 | DONE |
| 7 | Phone Server Boot Non-Blocking | Prevent WhatsApp phone server from blocking voice assistant startup | M1 | Survey 1 | DONE |
| 8 | Multi-turn Action Context Retention | Retain action execution observations in `_CONVERSATION_HISTORY` and rolling 10-turn LLM buffer | M2 | Survey 2 & P6 | DONE |
| 9 | Personality & Filler De-noising | Remove robotic filler and English thinking prefixes; enforce consistent Hinglish persona | M2 | Survey 2 & P4 | DONE |
| 10 | Fast TTS Pre-Flight Probe | Implement <200ms network check for Edge TTS to avoid 15s freeze on offline fallback | M2 | Survey 2 | DONE |
| 11 | Interruptible Audio Playback (Barge-in) | Allow user wake-word/speech to interrupt active TTS playback cleanly | M2 | Survey 2 | DONE |
| 12 | Voice Realism & TTS Subsystem | Create `Shin/core/tts.py` for `en-IN-NeerjaExpressiveNeural`, `+8Hz` pitch, and Devanagari detection | M2 | P1 | DONE |
| 13 | Agent-Reach Multi-Platform Tools | Zero-API live intelligence tool `agent_reach_query` for GitHub, Reddit, YouTube, Twitter | M3 | P2 | DONE |
| 14 | Clipboard AI Execution | Add `analyze_clipboard` command calling `predictive_engine.predict_clipboard_action()` | M3 | P3 | DONE |
| 15 | CaMeL Web Percept Sanitization | Route all search results and scraped web text through `security_shield.sanitize_untrusted_input()` | M3 | Survey 3 | DONE |
| 16 | Workspace Repository Interaction | Upgrade git commands to workspace root and add path-traversal protection to file write tools | M3 | Survey 3 | DONE |
| 17 | Memory Persistence & Dual Sync | Dual-file persistence (`memory.json` & `memories.json`), atomic writes, cache invalidation | M3 | P5 | DONE |
| 18 | Automated Verification Test Suite | Added `Shin/tests/test_revival_priorities.py` and `Shin/tests/test_challenger_stress.py` | M4 | Survey & P1-P6 | DONE |
| 19 | Existing Unit Test Compatibility | Verify all baseline unit tests in `Shin/tests/` continue to pass without regression (351 passed) | M4 | R4 | DONE |
| 20 | Adversarial Stress & Forensic Audit | Perform boundary value stress tests and forensic integrity verification (Verdict: CLEAN, APPROVE) | M4 | Project Rule | DONE |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Defect Remediation & Flow Stability | Fix orb window, edge-tts subprocess scoping, mediapipe gesture crash, Vosk relative path, Kokoro serialization, test disk pollution, and phone server boot delay. | None | DONE |
| M2 | Conversational Realism & Voice Studio | Modular `core/tts.py`, `en-IN-NeerjaExpressiveNeural` / `+8Hz` pitch, Devanagari Hindi/Marathi detection, Hinglish persona de-noising, and multi-turn context retention. | M1 | DONE |
| M3 | Tool, Repo & Sandboxed Plugin Capabilities | Agent-Reach live data tools (`agent_reach_query`), Clipboard AI (`analyze_clipboard`), Shin Intelligence rules, and dual-file memory persistence. | M1 | DONE |
| M4 | E2E Automated Verification & Hardening | Full 351 unit tests passed (0 failures), adversarial stress testing (32 stress tests), and independent forensic integrity audit (CLEAN). | M1, M2, M3 | DONE |

---

## Interface Contracts

### 1. `Shin.core.tts`
```python
def speak_edge(text: str, voice: Optional[str] = None, pitch: Optional[str] = None) -> bool: ...
def clean_text_for_speech(text: str) -> str: ...
def is_text_hindi(text: str) -> bool: ...
def is_text_marathi(text: str) -> bool: ...
def set_voice_pitch(pitch_val: str, label: str = "") -> str: ...
```

### 2. `Shin.core.shin_agent.agent_reach_query`
```python
def agent_reach_query(platform: str, query: str = "", action: str = "search", limit: int = 5) -> str:
    """Zero-API live intelligence across GitHub, Reddit, YouTube, Twitter."""
    ...
```

### 3. `Shin.core.memory`
```python
def load_memories() -> list: ...
def save_memories(memories: list) -> None: ...
def add_memory(content: str) -> str: ...
```
