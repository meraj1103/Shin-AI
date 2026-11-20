# Dispatch: Worker — Surgical Remediation for 5 Challenger Edge-Case Findings

## Mission
Apply the 5 surgical edge-case fixes identified by Challenger 2, update tests in `Shin/tests/test_revival_priorities.py` to assert against these edge cases, and run the full test suite to verify 100% pass rate.

## Context & Inputs
- Working Directory: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant`
- State Folder: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\worker_remediation_1`
- Original Request: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\ORIGINAL_REQUEST.md`
- Challenger 2 Handoff: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\challenger_revival_2\handoff.md`

## 🔒 MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Detailed Tasks to Implement
1. **TTS Markdown Header Cleaning (`Shin/core/tts.py:65`)**:
   - Change regex from `re.sub(r'^[#•\-\*\+]\s+', '', text, flags=re.MULTILINE)` to `re.sub(r'^[#•\-\*\+]+\s+', '', text, flags=re.MULTILINE)`.
   - Ensures headers like `### Heading` or `## Subheading` are stripped to `'Heading'` rather than vocalizing "hash hash hash".
2. **Predictive Engine Percentage Math (`Shin/core/predictive_engine.py:181`)**:
   - In `predict_clipboard_action()`, before calling `calculator.evaluate_expression(cleaned)`, pre-process percentage expressions:
     Convert patterns like `(\d+(?:\.\d+)?)\s*%\s*` to `(\1/100)` or compute percentage math cleanly.
   - Verify that `predict_clipboard_action('250 * 20%')` evaluates to `'50'` (or `'50.0'`) instead of an error message.
3. **NLP Dismissal Regex Expansion (`Shin/core/nlp.py:2514`)**:
   - Change `nahin` to `nahin?` in the dismissal regex so both `aur kuchh nahin` and `aur kuch nahi` match the conversational dismissal intent.
4. **Memory Schema Conformance (`Shin/core/memory.py:49` & `add_memory`)**:
   - In `load_memories()`, ensure the loaded object is a list, and filter out any items that are not dicts or lack a `"content"` key:
     `memories = [m for m in memories if isinstance(m, dict) and "content" in m]`
   - In `add_memory()`, ensure defensive check `isinstance(mem, dict) and mem.get("content", "").lower() == content.lower()`.
5. **Conversation Buffer Null Content Guard (`Shin/core/shin_agent.py:1149`)**:
   - Change `last_user_msg = m.get("content", "").strip()` to `last_user_msg = (m.get("content") or "").strip()`.
6. **Verification**:
   - Add/update unit tests in `Shin/tests/test_revival_priorities.py` covering all 5 edge cases.
   - Run `.\.venv\Scripts\pytest Shin\tests\ -q` to verify that all tests pass (0 failures).

## Output Requirements
Deliver your handoff report to `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\worker_remediation_1\handoff.md` with complete pytest output, and notify the orchestrator.


## 2026-11-09T15:20:33Z
You are the Remediation Worker for Shin Voice Assistant.
Working Directory: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant
State Folder: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\worker_remediation_1
Original Request: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\ORIGINAL_REQUEST.md
Challenger Handoff: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\challenger_revival_2\handoff.md
Dispatch File: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\worker_remediation_1\DISPATCH.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Apply the 5 surgical edge-case fixes detailed in DISPATCH.md:
1. Shin/core/tts.py:65: Fix markdown header regex to r'^[#•\-\*\+]+\s+'.
2. Shin/core/predictive_engine.py:181: Pre-process percentage math expressions before calling calculator so 250 * 20% evaluates correctly.
3. Shin/core/nlp.py:2514: Change nahin to nahin? in dismissal regex.
4. Shin/core/memory.py: Defensive checks in load_memories and add_memory to filter non-dict items and missing 'content'.
5. Shin/core/shin_agent.py:1149: Guard against content=None with (m.get('content') or '').strip().
6. Update Shin/tests/test_revival_priorities.py to verify these 5 edge cases.
7. Run .\.venv\Scripts\pytest Shin\tests\ -q to verify all tests pass.

Deliver your handoff report to m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\worker_remediation_1\handoff.md and notify the orchestrator.
