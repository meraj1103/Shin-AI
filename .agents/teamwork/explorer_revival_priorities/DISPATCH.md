# Dispatch: Explorer — Revival Priorities Technical Investigation

## Mission
Investigate the current codebase for the 6 user-directed priority upgrades, analyze implementation details, run pytest to verify baseline tests, and formulate an exact, minimal-diff implementation blueprint.

## Context
- Working Directory: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant`
- State Folder: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_revival_priorities`
- Original Request: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\ORIGINAL_REQUEST.md`
- Agent-Reach Skill: `C:\Users\Mehar\.gemini\config\skills\agent-reach\SKILL.md`

## The 6 Priorities to Investigate
1. **Voice Realism**:
   - Inspect `Shin/.env`, `Shin/core/tts.py`, and `Shin/assistant.py` for `EDGE_TTS_VOICE_EN`, `TTS_PITCH`, and default voice configuration.
   - Verify available female Indian English voices in edge-tts (e.g. `en-IN-NeerjaNeural`, `en-IN-AnanyaNeural`).
   - Define exact configuration to ensure a warm, spunky, natural female Hinglish best-friend voice.
2. **Agent-Reach Integration**:
   - Read `C:\Users\Mehar\.gemini\config\skills\agent-reach\SKILL.md`.
   - Inspect `Shin/core/shin_agent.py` (`AVAILABLE_TOOLS`, `TOOL_SCHEMAS`, `ShinReActEngine`).
   - Design tool(s) for live multi-platform data extraction (GitHub trending/repos, YouTube search/transcripts, Reddit, Twitter/X) with resilient zero-API fallback mechanisms so Shin can answer questions like "What's trending on GitHub today?" live.
3. **Clipboard AI**:
   - Inspect `Shin/core/predictive_engine.py` for `predict_clipboard_action()`.
   - Inspect `Shin/core/nlp.py` and `Shin/core/commands.py` for existing clipboard commands.
   - Design new command `"analyze my clipboard"` / `"check clipboard"` that calls `predictive_engine.predict_clipboard_action()` and speaks the result in Shin's Hinglish voice.
4. **Shin Intelligence Improvements**:
   - Inspect `Shin/data/missed_intents.log`.
   - Extract any unhandled user query patterns and design regex rules / intent mappings for `nlp.py`.
5. **Memory Persistence**:
   - Inspect `Shin/core/memory.py` to check how relationship memories are stored and whether they persist across process restarts (e.g. `Shin/data/memories.json`).
   - Design persistent save/load mechanisms if missing.
6. **Conversation Context**:
   - Inspect `Shin/core/shin_agent.py` and `Shin/main.py` message handling.
   - Design a rolling 10-turn conversation buffer passed into LLM calls so Shin maintains multi-turn context without forgetting.

## Baseline Test Verification
- Run `.\.venv\Scripts\pytest Shin\tests\ -q` to confirm the 293+ tests baseline.

## Output Requirements
Do NOT edit production source code.
Write your detailed blueprint and findings to `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_revival_priorities\blueprint.md` and complete `handoff.md`. Notify the orchestrator upon completion.


## 2026-11-09T14:21:27Z
Sender: 433746e0-e35d-43cd-a302-d4bc2ec30e66
You are the Revival Priorities Explorer for the Shin Voice Assistant project.
Working Directory: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant
State Folder: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_revival_priorities
Original Request: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\ORIGINAL_REQUEST.md
Dispatch File: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_revival_priorities\DISPATCH.md
Agent-Reach Skill: C:\Users\Mehar\.gemini\config\skills\agent-reach\SKILL.md

Read ORIGINAL_REQUEST.md and DISPATCH.md first.
1. Run .\.venv\Scripts\pytest Shin\tests\ -q to establish the baseline test results (confirming 293+ passing tests).
2. Deep-dive into all 6 user-directed priorities:
   - Priority 1: Voice Realism (Shin/.env, Shin/core/tts.py, edge-tts Indian female voices like en-IN-NeerjaNeural, pitch tuning)
   - Priority 2: Agent-Reach Integration (read agent-reach SKILL.md, design live data extraction tools for GitHub, YouTube, Reddit, Twitter in Shin/core/shin_agent.py)
   - Priority 3: Clipboard AI (predictive_engine.predict_clipboard_action(), add 'analyze my clipboard' in nlp.py and commands.py)
   - Priority 4: Shin Intelligence (review Shin/data/missed_intents.log, identify unhandled patterns, formulate regex rules in nlp.py)
   - Priority 5: Memory Persistence (verify Shin/core/memory.py saves memories persistently to disk e.g. Shin/data/memories.json, formulate fix if needed)
   - Priority 6: Conversation Context (design a rolling 10-turn conversation buffer in shin_agent.py / main.py passed to LLM calls)
Do NOT modify production source code directly.
Deliver your comprehensive blueprint to m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_revival_priorities\blueprint.md and your handoff.md, then message the orchestrator.
