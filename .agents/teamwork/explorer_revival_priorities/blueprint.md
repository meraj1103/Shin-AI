# Technical Blueprint: Shin Voice Assistant Production-Level Revival

**Project**: Shin Voice Assistant  
**Date**: 2026-11-09  
**Target Environment**: Windows 11 (64-bit), AMD Ryzen 5 5600H, RTX 3050 Laptop (4GB VRAM)  
**Baseline Test Status**: **297 passed**, 3 warnings in 31.49s (`pytest Shin\tests\ -q`)  
**Persona Target**: Warm, loyal, spunky female best-friend Hinglish persona (100% female verb forms: *karti hoon*, *bataungi*, *samajh gayi*, addressing MJ)

---

## Executive Summary of the 6 Priorities

| Priority | Area | Current Status | Planned Upgrade | Target Files |
|---|---|---|---|---|
| **1** | **Voice Realism** | TTS in `assistant.py`; `.env` has `en-IN-NeerjaNeural`, `TTS_PITCH=+8Hz` | Introduce modular `Shin/core/tts.py` to eliminate circular imports; support `en-IN-NeerjaExpressiveNeural` / `en-IN-NeerjaNeural` with pitch tuning (`+4Hz` to `+8Hz`) | `Shin/.env`, `Shin/core/tts.py`, `Shin/assistant.py` |
| **2** | **Agent-Reach Integration** | `shin_agent.py` lacks live platform intelligence; queries fall back to generic search | Integrate `agent_reach_query` ReAct tool with zero-API fallback scrapers (GitHub trending/repos, YouTube transcripts/search, Reddit hot JSON, Twitter/X) | `Shin/core/shin_agent.py`, `Shin/core/nlp.py`, `Shin/main.py` |
| **3** | **Clipboard AI** | `predictive_engine.predict_clipboard_action()` fully implemented but unmapped in NLP | Add intent `analyze_clipboard` in `nlp.py` and handler `analyze_clipboard` in `commands.py` | `Shin/core/nlp.py`, `Shin/core/commands.py` |
| **4** | **Shin Intelligence** | `missed_intents.log` contains unhandled user utterances | Add regex rules for language switching, polite dismissals, casual best-friend greetings, and typo resilience | `Shin/core/nlp.py` |
| **5** | **Memory Persistence** | `Shin/data/memory.json` stores memories; no alias for `memories.json` | Add dual-filename support (`memory.json` & `memories.json`), explicit relationship persistence methods, and instant NLP memory cache invalidation | `Shin/core/memory.py`, `Shin/core/commands.py` |
| **6** | **Conversation Context** | `shin_agent.py` and `main.py` rebuild single-turn messages every query | Implement a rolling 10-turn (20 messages) conversation buffer in `ShinReActEngine` and `AutonomousShinEngine` persisted to disk | `Shin/core/shin_agent.py`, `Shin/main.py`, `Shin/data/conversation_history.json` |

---

## Priority 1: Voice Realism

### 1. Current State & Direct Observations
- In `Shin/.env`:
  ```ini
  TTS_BACKEND=edge
  TTS_SPEED=1.0
  EDGE_TTS_VOICE=hi-IN-SwaraNeural
  EDGE_TTS_VOICE_EN=en-IN-NeerjaNeural
  TTS_PITCH=+8Hz
  ```
- In `Shin/assistant.py`:
  - TTS functions are defined at lines 379–467 (`_speak_edge`), 469–595 (`_speak_kokoro`), 345–377 (`_speak_pyttsx3`), and 606–678 (`speak`).
  - Lines 136–141 define defaults, but line 141 defaults `TTS_PITCH` to `"+0Hz"` when unset.
  - In `Shin/core/macros.py:139`, comment notes: `"The TTS function from assistant.py — injected to avoid circular imports."`
- Microsoft Edge TTS voices queried live via `edge-tts.list_voices()`:
  - `en-IN-NeerjaExpressiveNeural` (Female, Indian English) — Microsoft's conversational, expressive neural model.
  - `en-IN-NeerjaNeural` (Female, Indian English) — Standard natural conversational model.
  - `hi-IN-SwaraNeural` (Female, Hindi) — Native Hindi voice used when Devanagari text is detected.
  - `mr-IN-AarohiNeural` (Female, Marathi) — Native Marathi voice.

### 2. Architecture & Design Blueprint
To provide modularity, eliminate circular dependencies, and preserve full backward compatibility:
1. Create `Shin/core/tts.py`:
   - Expose `speak(text: str)`, `speak_edge(text: str)`, `set_voice_pitch(pitch: str, label: str)`, `is_text_hindi(text: str)`, and `is_text_marathi(text: str)`.
   - Voice routing:
     - Devanagari text (Marathi characters or words) -> `mr-IN-AarohiNeural`
     - Devanagari text (Hindi) -> `hi-IN-SwaraNeural`
     - Latin text (Hinglish/English) -> `en-IN-NeerjaExpressiveNeural` (with automatic fallback to `en-IN-NeerjaNeural`)
   - Natural prosody:
     - Pitch: `+4Hz` to `+8Hz` (adds warm, feminine, youthful brightness without chipmunk distortion).
     - Speed: `1.0` (smooth natural cadence).
     - Volume: Normalised `+0%` or `+15%` to prevent audio clipping.
2. In `Shin/assistant.py`:
   - Delegate TTS calls to `Shin/core/tts.py` or import them, ensuring all existing functions (`speak`, `_speak_edge`, `set_voice_pitch`) remain 100% accessible to existing callers.

### 3. Implementation Specification
```python
# Shin/core/tts.py
"""
tts.py — Modular, High-Fidelity Neural Text-to-Speech Engine for Shin
====================================================================
Integrates Microsoft Edge Neural TTS with Expressive Indian English,
Devanagari Hindi/Marathi detection, pitch tuning, and smooth audio playback.
"""
import asyncio
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("shin.tts")

EDGE_TTS_VOICE_EN = os.getenv("EDGE_TTS_VOICE_EN", "en-IN-NeerjaNeural")
EDGE_TTS_VOICE_HI = os.getenv("EDGE_TTS_VOICE", "hi-IN-SwaraNeural")
EDGE_TTS_VOICE_MR = os.getenv("EDGE_TTS_VOICE_MR", "mr-IN-AarohiNeural")
TTS_SPEED = float(os.getenv("TTS_SPEED", "1.0"))
TTS_PITCH = os.getenv("TTS_PITCH", "+8Hz")

def is_text_hindi(text: str) -> bool:
    return any('\u0900' <= char <= '\u097f' for char in text)

def is_text_marathi(text: str) -> bool:
    if not is_text_hindi(text):
        return False
    if any(c in text for c in ('ळ', 'ळी', 'ळा', 'ळे')):
        return True
    marathi_words = {"आहे", "आहेत", "मी", "करू", "शकते", "झाली", "वाजले", "तुमची", "माझी", "काय"}
    words = set(re.findall(r'[\u0900-\u097f]+', text))
    return bool(words & marathi_words)

def synthesize_edge_audio(text: str, voice: Optional[str] = None, pitch: Optional[str] = None) -> Optional[str]:
    import edge_tts
    if not voice:
        if is_text_marathi(text):
            voice = EDGE_TTS_VOICE_MR
        elif is_text_hindi(text):
            voice = EDGE_TTS_VOICE_HI
        else:
            voice = EDGE_TTS_VOICE_EN

    speed_pct = int((TTS_SPEED - 1.0) * 100)
    rate_str = f"{'+' if speed_pct >= 0 else ''}{speed_pct}%"
    pitch_str = pitch or TTS_PITCH

    async def _generate():
        comm = edge_tts.Communicate(text, voice=voice, rate=rate_str, pitch=pitch_str, volume="+0%")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name
        await asyncio.wait_for(comm.save(tmp_path), timeout=15.0)
        return tmp_path

    try:
        return asyncio.run(_generate())
    except Exception as exc:
        logger.warning("edge-tts synthesis failed for voice %s: %s", voice, exc)
        return None
```

---

## Priority 2: Agent-Reach Integration

### 1. Current State & Direct Observations
- `agent-reach` skill (`C:\Users\Mehar\.gemini\config\skills\agent-reach\SKILL.md`) specifies zero-API live data reach across Twitter/X, Reddit, YouTube, GitHub, and RSS.
- In `Shin/core/shin_agent.py`:
  - `AVAILABLE_TOOLS` has 4 tools: `os_operations`, `web_search_and_learn`, `inspect_active_app`, `interact_app_ui`.
  - When asked "What is trending on GitHub today?", `nlp.parse_intent()` falls back to `chat` or generic web search without fetching live repo cards, descriptions, stars, or trends.
  - The local virtual environment does not have `agent_reach` installed as a Python package.

### 2. Architecture & Design Blueprint
Implement a robust, production-grade ReAct tool: `agent_reach_query(platform: str, query: str = "", topic: str = "", limit: int = 5) -> str`
- **Two-Tier Resilient Engine**:
  1. **Tier 1 (CLI execution)**: If `agent_reach` module is found or callable via `subprocess.run([sys.executable, "-m", "agent_reach", ...])`, execute it.
  2. **Tier 2 (Zero-API Native Live Scrapers & Endpoints)**:
     - **GitHub**:
       - Trending: Scrape `https://github.com/trending` or query GitHub Public REST API `https://api.github.com/search/repositories?q=stars:>1000&sort=stars&order=desc` without credentials. Returns top repositories, descriptions, star counts, and primary language.
       - Repos: Inspect repo details via `https://api.github.com/repos/{owner}/{repo}`.
     - **YouTube**:
       - Search videos or fetch transcripts using `youtube-transcript-api` (if installed) or clean HTML metadata scraper from `https://www.youtube.com/results?search_query={query}`.
     - **Reddit**:
       - Fetch `https://www.reddit.com/r/{subreddit}/hot.json` or `https://www.reddit.com/search.json?q={query}` using a custom User-Agent (`ShinVoiceAssistant/2.0`). Extracts top posts, scores, and comment counts without API keys.
     - **Twitter / X & Deep Web**:
       - Query via Jina Reader (`https://r.jina.ai/https://twitter.com/search?q={query}`) or DuckDuckGo clean search.
- Register `agent_reach_query` into:
  - `AVAILABLE_TOOLS` in `Shin/core/shin_agent.py`
  - `TOOL_SCHEMAS` in `Shin/core/shin_agent.py`
  - Fast-path heuristic in `ShinReActEngine._extract_heuristic_tool_call`
  - `nlp.py` intent routing for `"trending on github"`, `"trending repos"`, `"reddit search"`.

### 3. Implementation Specification
```python
# In Shin/core/shin_agent.py

def agent_reach_query(
    platform: str,
    query: str = "",
    action: str = "search",
    limit: int = 5,
) -> str:
    """
    Live zero-API data extraction across GitHub, Reddit, YouTube, and Twitter.
    
    Args:
        platform: One of "github", "reddit", "youtube", "twitter", "web".
        query: Search term, repo name, subreddit, or URL.
        action: "trending", "search", "transcript", or "get_post".
        limit: Max results to return (1-10).
    """
    plat = platform.lower().strip()
    act = action.lower().strip()
    limit = max(1, min(10, int(limit)))

    # Try agent-reach CLI first if available
    try:
        import importlib.util
        if importlib.util.find_spec("agent_reach"):
            cmd = [sys.executable, "-m", "agent_reach", "run", plat, act]
            if query:
                cmd.extend(["--query", query])
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
    except Exception:
        pass

    # Native Zero-API Fallbacks
    import requests

    headers = {"User-Agent": "ShinVoiceAssistant/2.0 (Windows NT 10.0; Win64; x64)"}

    # 1. GitHub Live Intelligence
    if plat == "github":
        try:
            if act == "trending" or "trend" in query.lower() or not query:
                url = "https://api.github.com/search/repositories?q=stars:>500&sort=stars&order=desc"
                resp = requests.get(url, headers=headers, timeout=6).json()
                items = resp.get("items", [])[:limit]
                if not items:
                    return "GitHub trending repos currently unavailable."
                lines = [f"=== Trending GitHub Repositories Today (Top {len(items)}) ==="]
                for idx, r in enumerate(items, 1):
                    lines.append(f"[{idx}] {r['full_name']} (⭐ {r['stargazers_count']:,})")
                    lines.append(f"    Desc: {r.get('description') or 'No description provided.'}")
                    lines.append(f"    Lang: {r.get('language') or 'N/A'} | Link: {r['html_url']}")
                return "\n".join(lines)
            else:
                url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&sort=stars"
                resp = requests.get(url, headers=headers, timeout=6).json()
                items = resp.get("items", [])[:limit]
                lines = [f"=== GitHub Search Results for '{query}' ==="]
                for idx, r in enumerate(items, 1):
                    lines.append(f"[{idx}] {r['full_name']} (⭐ {r['stargazers_count']:,}): {r.get('description', '')}")
                return "\n".join(lines)
        except Exception as exc:
            return f"GitHub query failed: {exc}"

    # 2. Reddit Live Intelligence
    elif plat == "reddit":
        try:
            sub = query.replace("r/", "").strip() if query else "technology"
            url = f"https://www.reddit.com/r/{urllib.parse.quote(sub)}/hot.json?limit={limit}"
            resp = requests.get(url, headers=headers, timeout=6).json()
            posts = resp.get("data", {}).get("children", [])
            if not posts:
                return f"No posts found in r/{sub}."
            lines = [f"=== Top Hot Posts in r/{sub} ==="]
            for idx, p in enumerate(posts[:limit], 1):
                pdata = p.get("data", {})
                lines.append(f"[{idx}] {pdata.get('title')} (Upvotes: {pdata.get('score', 0)})")
                lines.append(f"    Comments: {pdata.get('num_comments', 0)} | URL: https://reddit.com{pdata.get('permalink')}")
            return "\n".join(lines)
        except Exception as exc:
            return f"Reddit query failed: {exc}"

    # 3. YouTube Intelligence
    elif plat == "youtube":
        return web_search_and_learn(f"site:youtube.com {query}", max_results=limit, scrape_top=False)

    return f"Platform '{platform}' not supported."
```

---

## Priority 3: Clipboard AI

### 1. Current State & Direct Observations
- `Shin/core/predictive_engine.py`:
  - `predict_clipboard_action(clipboard_text=None)` is implemented and verified by 4 existing unit tests (`test_predict_clipboard_error_traceback`, `test_predict_clipboard_github_url`, `test_predict_clipboard_youtube_url`, `test_predict_clipboard_math_expression`).
  - Correctly categorizes errors, GitHub repos, YouTube URLs, math calculations, web URLs, and code snippets, returning a Hinglish prediction string.
- `Shin/core/nlp.py`:
  - Currently tests for `"read my clipboard"` -> `read_clipboard`, `"summarize my clipboard"` -> `clipboard_summarize`.
  - Does NOT test for `"analyze my clipboard"` or `"check my clipboard"` — both fall back to generic `chat`.
- `Shin/core/commands.py`:
  - Lacks an `analyze_clipboard` function in `HANDLERS`.

### 2. Architecture & Design Blueprint
1. In `Shin/core/commands.py`:
   - Implement `analyze_clipboard(args: dict) -> str`:
     - Calls `predictive_engine.predict_clipboard_action()`.
     - Returns `prediction_data.get("prediction")`.
   - Register `"analyze_clipboard"` in `HANDLERS` dictionary.
2. In `Shin/core/nlp.py`:
   - Add regex pattern under Clipboard Actions (line ~1448):
     ```python
     (
         r"\b(?:analyze|analyse|check|inspect|examine|predict)\s+(?:my\s+)?clipboard\b"
         r"|\b(?:clipboard\s+(?:analyze|analyse|check|inspect|karo|batao|dekho))\b",
         lambda m: {"intent": "analyze_clipboard", "args": {}},
     ),
     ```
   - Add `"analyze_clipboard"` to supported intent sets and documentation.

### 3. Implementation Specification
```python
# Shin/core/commands.py
def analyze_clipboard(args: dict) -> str:
    """Analyze clipboard content using predictive engine and return smart recommendation."""
    try:
        try:
            from predictive_engine import predictive_engine
            engine = predictive_engine
        except ImportError:
            from core.predictive_engine import predictive_engine
            engine = predictive_engine

        res = engine.predict_clipboard_action()
        return res.get("prediction", "Clipboard analyze kar liya MJ, par koi specific action detect nahi hui.")
    except Exception as exc:
        logger.error("Failed to analyze clipboard: %s", exc)
        return f"Clipboard analyze karne mein dikkat aayi: {exc}"

# Add to HANDLERS dictionary in Shin/core/commands.py:
HANDLERS = {
    ...
    "analyze_clipboard": analyze_clipboard,
    ...
}
```

---

## Priority 4: Shin Intelligence Improvements

### 1. Current State & Direct Observations
From inspecting `Shin/data/missed_intents.log`, we identified real user utterances that fell through or were misrouted:
- `han english mein baat karo` / `english mein bolo` / `hindi mein bolo`:
  - Direct user instruction to switch communication language. Fell back to generic `chat`!
- `aur bhai fir` / `aur batao` / `aur bhai kya chal raha`:
  - Casual Hinglish greeting from MJ to his best-friend assistant. Fell back to slow search or generic conversational fallback.
- `what ise your name`:
  - ASR / typing typo ("ise" instead of "is"). Fell back to Wikipedia search for "what ise your name" which failed with a JSON decode error!
- `aur kuchh nahin` / `kuch nahi` / `bas itna hi`:
  - User indicating completion of interaction. Needs a quick, warm dismissal acknowledgment ("Theek hai MJ, main yahin hoon jab bhi zaroorat ho!") rather than querying external web search.

### 2. Architecture & Design Blueprint
Add specialized rules into `Shin/core/nlp.py`:
1. **Language Switching Intent (`set_language`)**:
   ```python
   (
       r"\b(?:han\s+)?(?:ab\s+)?(english|hindi|marathi|hinglish)\s+mein\s+(?:baat\s+karo|bolo|speak)\b"
       r"|\b(?:speak|talk)\s+in\s+(english|hindi|marathi|hinglish)\b",
       lambda m: {"intent": "set_language", "args": {"language": (m.group(1) or m.group(2)).lower()}},
   ),
   ```
2. **Best-Friend Casual Greetings (`casual_greeting`)**:
   ```python
   (
       r"\b(?:aur\s+bhai(?:\s+fir)?|aur\s+bhai\s+kya\s+chal\s+raha|aur\s+batao|kya\s+scene\s+hai)\b",
       lambda m: {"intent": "chat", "args": {"response": "Aur bhai! Sab badhiya ekdum, tu bata kya scene hai?"}},
   ),
   ```
3. **Conversational Dismissal / Done (`user_done`)**:
   ```python
   (
       r"\b(?:aur\s+kuchh?\s+nahin|kuch\s+nahi\s+chahiye|bas\s+itna\s+hi|nothing\s+else|that'?s\s+all)\b",
       lambda m: {"intent": "chat", "args": {"response": "Theek hai MJ! Main yahin hoon, jab bhi zaroorat ho awaaz dena."}},
   ),
   ```
4. **Typo-Tolerant Identity Query**:
   ```python
   (
       r"\bwhat\s+(?:is|ise)\s+your\s+name\b",
       lambda m: {"intent": "who_are_you", "args": {}},
   ),
   ```

---

## Priority 5: Memory Persistence

### 1. Current State & Direct Observations
- `Shin/core/memory.py`:
  - Stores memories persistently at `Shin/data/memory.json`.
  - Implements atomic writes (`memory.json.tmp` -> `os.replace`).
  - Contains MJ's key background facts (full name, student at D.Y. Patil College, ENTC engineering, Kolhapur/Ichalkaranji hometown, Shin relationship).
  - In `Shin/core/nlp.py`, `_memory_ctx_cache` caches memory context for 60 seconds (`_MEMORY_CTX_TTL = 60.0`), with an existing `invalidate_memory_cache()` function.
- Verification gaps:
  - If external scripts or callers look for `memories.json` (plural), it wasn't aliased.
  - When `store_relationship` saves a memory via `memory.add_memory()`, `invalidate_memory_cache()` was not consistently triggered, leading to up to a 60-second delay before the LLM prompt reflected the new relation.

### 2. Architecture & Design Blueprint
1. **Dual-File Compatibility**:
   - In `Shin/core/memory.py`, define both `MEMORY_FILE` (`data/memory.json`) and `ALT_MEMORY_FILE` (`data/memories.json`).
   - On load: if `memory.json` does not exist but `memories.json` does, load `memories.json`.
   - On save: save atomically to `memory.json`, and mirror or symlink to `memories.json`.
2. **Instant Cache Invalidation**:
   - Inside `memory.add_memory()` and `commands.store_relationship()`, invoke `nlp.invalidate_memory_cache()` so newly stored facts are instantly injected into the conversation prompt.
3. **Structured Relationship Extraction**:
   - Store relationship objects with metadata (`type: "relationship"`, `subject`, `relation`, `timestamp`) allowing both structured lookups and clean natural-language summarization.

### 3. Implementation Specification
```python
# Shin/core/memory.py updates:
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MEMORY_FILE = str(_DATA_DIR / "memory.json")
ALT_MEMORY_FILE = str(_DATA_DIR / "memories.json")

def load_memories() -> list:
    target = MEMORY_FILE if os.path.exists(MEMORY_FILE) else (ALT_MEMORY_FILE if os.path.exists(ALT_MEMORY_FILE) else MEMORY_FILE)
    if not os.path.exists(target):
        return []
    try:
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load memory file: %s", exc)
        return []

def save_memories(memories: list):
    tmp_file = MEMORY_FILE + ".tmp"
    try:
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(memories, f, indent=4, ensure_ascii=False)
        os.replace(tmp_file, MEMORY_FILE)
        # Mirror to memories.json for complete resilience
        try:
            with open(ALT_MEMORY_FILE, "w", encoding="utf-8") as f2:
                json.dump(memories, f2, indent=4, ensure_ascii=False)
        except Exception:
            pass
        # Invalidate NLP memory context cache
        try:
            import nlp
            nlp.invalidate_memory_cache()
        except Exception:
            pass
    except Exception as exc:
        logger.error("Failed to save memories: %s", exc)
```

---

## Priority 6: Conversation Context

### 1. Current State & Direct Observations
- In `Shin/core/shin_agent.py`:
  - `ShinReActEngine.run(prompt)` reconstructs `initial_state["messages"]` containing ONLY system prompt and current user prompt.
  - Multi-turn context is completely forgotten between separate invocations.
- In `Shin/main.py`:
  - `AutonomousShinEngine.run(user_prompt)` similarly creates `messages = [{"role": "system", ...}, {"role": "user", ...}]` from scratch on each turn.
- In `Shin/core/nlp.py`:
  - An existing `_CONVERSATION_HISTORY = collections.deque(maxlen=20)` exists, with `_load_conversation_history()` and `_persist_conversation_history()` reading/writing `Shin/data/conversation_history.json`.

### 2. Architecture & Design Blueprint
1. **Rolling 10-Turn (20 Messages) Buffer**:
   - Maintain `self.conversation_buffer: collections.deque = collections.deque(maxlen=20)` inside `ShinReActEngine` and `AutonomousShinEngine`.
   - On startup, load existing history from `Shin/data/conversation_history.json`.
   - When building messages for the LLM:
     1. `system` message (Persona, guidelines, tool schemas)
     2. `self.conversation_buffer` items (historical `user` and `assistant` messages)
     3. current `user` message
   - Upon completing the turn:
     - Append `{"role": "user", "content": prompt}`
     - Append `{"role": "assistant", "content": final_answer}`
     - Persist buffer to `Shin/data/conversation_history.json`.
2. **Buffer Management & Safety**:
   - Add `reset_conversation()` / `clear_history()` method to clear the buffer.
   - Buffer serialization caps individual turn content to prevent context window overflow on small models (Ollama 4096-token limit on 4GB VRAM RTX 3050).

### 3. Implementation Specification
```python
# Shin/core/shin_agent.py updates:
import collections

_HISTORY_PATH = _SHIN_ROOT / "data" / "conversation_history.json"

class ShinReActEngine:
    def __init__(self, hardware: Optional[HardwareProfile] = None):
        self.router = DualModeLLMRouter(hardware)
        self.system_prompt = build_shin_system_prompt()
        self.max_iterations = 4
        self.graph = self._build_langgraph()
        self.history: collections.deque = collections.deque(maxlen=20)
        self._load_history()

    def _load_history(self):
        try:
            if _HISTORY_PATH.exists():
                with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for item in saved[-20:]:
                    if isinstance(item, dict) and "role" in item and "content" in item:
                        self.history.append(item)
        except Exception as exc:
            logger.debug("Could not load agent conversation history: %s", exc)

    def _persist_history(self):
        try:
            _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(list(self.history), f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.debug("Could not persist agent conversation history: %s", exc)

    def clear_context(self):
        """Wipe active conversation buffer."""
        self.history.clear()
        self._persist_history()

    def run(self, prompt: str) -> str:
        # Assemble messages including rolling conversation buffer
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(list(self.history))
        messages.append({"role": "user", "content": prompt.strip()})

        initial_state: AgentState = {
            "messages": messages,
            "mj_prompt": prompt.strip(),
            "iteration": 0,
            "tool_calls": [],
            "final_answer": "",
        }

        # Run ReAct
        final_answer = ""
        if self.graph is not None:
            try:
                final_state = self.graph.invoke(initial_state)
                final_answer = final_state.get("final_answer", "")
            except Exception:
                pass

        if not final_answer:
            final_answer = self._run_native_react_with_messages(messages)

        # Update rolling 10-turn history
        self.history.append({"role": "user", "content": prompt.strip()})
        self.history.append({"role": "assistant", "content": final_answer})
        self._persist_history()

        return final_answer
```

---

## Verification Plan & Regression Matrix

1. **Unit Test Baseline**:
   - `.\.venv\Scripts\pytest Shin\tests\ -q` must report **297+ passed** (0 failures).
2. **New Test Suite (`Shin/tests/test_revival_priorities.py`)**:
   - `test_voice_realism_config`: Assert `en-IN-NeerjaExpressiveNeural` / `en-IN-NeerjaNeural` and pitch settings.
   - `test_agent_reach_github_trending`: Test `agent_reach_query("github", action="trending")` returns formatted trending repos without crashing.
   - `test_agent_reach_reddit`: Test `agent_reach_query("reddit", "technology")` returns hot reddit posts.
   - `test_clipboard_ai_analyze_command`: Test `commands.dispatch({"intent": "analyze_clipboard", "args": {}})` calls predictive engine and returns prediction.
   - `test_nlp_analyze_clipboard`: Test `nlp.parse_intent("analyze my clipboard")["intent"] == "analyze_clipboard"`.
   - `test_missed_intents_new_rules`: Test `set_language`, `casual_greeting`, `user_done`, and typo-tolerant `who_are_you`.
   - `test_memory_persistence_dual_file`: Test `memory.py` saves and synchronizes `memory.json` and `memories.json`.
   - `test_conversation_context_rolling_buffer`: Test `ShinReActEngine` remembers prior turn context in multi-turn sequence and maintains maximum 20 messages.
