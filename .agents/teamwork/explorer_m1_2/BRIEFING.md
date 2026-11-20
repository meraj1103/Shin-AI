# BRIEFING — 2026-11-09T14:05:00Z

## Mission
Investigate and design precise fix strategies for Shin/assistant.py defects: edge-tts subprocess UnboundLocalError, Vosk relative path failure, and Kokoro Cython serialization / 60s queue stall.

## 🔒 My Identity
- Archetype: explorer
- Roles: Voice Runtime Defect Explorer
- Working directory: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant
- State folder: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_m1_2
- Original parent: 433746e0-e35d-43cd-a302-d4bc2ec30e66
- Milestone: Milestone 1 (Defect Remediation & Flow Stability)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement code changes directly
- Strict backward compatibility with 266 unit tests in Shin/tests/
- Deliverables: fix_strategy.md and handoff.md in state folder
- Notify caller via send_message upon completion

## Current Parent
- Conversation ID: 433746e0-e35d-43cd-a302-d4bc2ec30e66
- Updated: not yet

## Investigation State
- **Explored paths**:
  - `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\ORIGINAL_REQUEST.md`
  - `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\PROJECT.md`
  - `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_survey_1\survey_report.md`
  - `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_m1_2\DISPATCH.md`
- **Key findings**:
  - Three assigned defects in `Shin/assistant.py` identified:
    1. `_speak_edge_tts` `subprocess` scoping (lines 387-465)
    2. Vosk offline model path resolution (lines 728-758)
    3. Kokoro Cython serialization `__reduce_cython__` and 60s TTS queue stalls (lines 483-545)
- **Unexplored areas**:
  - Deep-dive into `Shin/assistant.py` source lines 380-600 and 700-800
  - Examination of imports, multiprocessing vs threading in Kokoro, and fallback mechanisms
  - Exact diff construction and reproduction testing

## Key Decisions Made
- Proceed with line-by-line inspection of `Shin/assistant.py` to draft targeted minimal diffs for each defect.

## Artifact Index
- `.agents\teamwork\explorer_m1_2\BRIEFING.md` — persistent working memory
- `.agents\teamwork\explorer_m1_2\progress.md` — liveness heartbeat
- `.agents\teamwork\explorer_m1_2\fix_strategy.md` — detailed defect analysis and recommended diffs
- `.agents\teamwork\explorer_m1_2\handoff.md` — formal 5-component handoff report
