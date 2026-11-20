# BRIEFING — 2026-11-09T14:02:00Z

## Mission
Investigate Shin's conversational engine, memory/dialog management, prompt engineering/personality, conversational naturalness, and speech/TTS/Voice Studio architecture.

## 🔒 My Identity
- Archetype: explorer
- Roles: Conversational and Voice Explorer
- Working directory: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant
- State folder: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_survey_2
- Original parent: 433746e0-e35d-43cd-a302-d4bc2ec30e66
- Milestone: survey_and_architecture

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Produce comprehensive survey_report.md and handoff.md in state folder
- Strictly adhere to teamwork communication & handoff protocol

## Current Parent
- Conversation ID: 433746e0-e35d-43cd-a302-d4bc2ec30e66
- Updated: not yet

## Investigation State
- **Explored paths**:
  - `Shin/assistant.py` (ASR/TTS loops, speech cleaning, queueing, fallback, pitch tuning, event loop)
  - `Shin/core/personality.py` (mood state, response pools, anti-repeat, thinking prefixes, greetings, banter)
  - `Shin/core/memory.py` (explicit & implicit persistent memory, keyword search, prompt context formatting)
  - `Shin/core/nlp.py` (multi-tier intent parsing, rolling conversation history, situational context, female grammar)
  - `Shin/core/shin_agent.py` & `Shin/main.py` (LangGraph ReAct loop, tool schemas, dual-mode LLM router)
  - `Shin/core/shin_knowledge.py` (knowledge encyclopedia, female Hinglish styling)
  - `Shin/test_voice_pitch.py`, `Shin/test_kokoro.py`, `Shin/register_voices.py` (voice audition studio, pitch ladder)
  - `Shin/tests/` (ran test suite: all 266 unit tests passed in 41.65s)
- **Key findings**:
  - Voice loop (`assistant.py`) and ReAct engine (`shin_agent.py`) are disconnected.
  - Multi-turn conversational context is lost on action commands (logs generic "Ho gaya!" rather than actual command outputs).
  - Anaphora and coreference resolution are absent in rule parsing.
  - English thinking prefixes clash with Maharashtrian-Dakhni Hinglish persona; micro-actions produce chatter fatigue.
  - Edge TTS hangs for 15s when offline before falling back; playback lacks barge-in / cancellation mechanism.
  - Voice Studio prototype exists in `test_voice_pitch.py` but is isolated from runtime and agent tools.
- **Unexplored areas**: None within the scope of this investigation.

## Key Decisions Made
- Completed in-depth survey of conversational pipelines, prompt engineering, TTS engines, and voice studio architecture.
- Authored comprehensive `survey_report.md` and complete 5-component `handoff.md`.

## Artifact Index
- `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_survey_2\DISPATCH.md` — Incoming task instructions
- `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_survey_2\survey_report.md` — Comprehensive survey report
- `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_survey_2\handoff.md` — 5-component handoff report
- `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_survey_2\progress.md` — Progress heartbeat
