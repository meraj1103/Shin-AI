# Dispatch: Test Writer — Opaque-Box E2E Test Suite (Tiers 1-4)

## Mission
Design and implement a comprehensive, opaque-box E2E test suite in `Shin/tests/test_e2e_scenarios.py` and document the methodology in `TEST_INFRA.md` according to the Project Pattern dual-track methodology.

## Context
- Working Directory: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant`
- State Folder: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\test_writer_e2e`
- Original Request: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\ORIGINAL_REQUEST.md`
- Project Document: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\PROJECT.md`

## 4-Tier Test Requirements (Derived from Requirements R1-R4)
1. **Tier 1 — Feature Coverage**: Tests exercising core features in isolation:
   - Voice assistant command dispatch (volume, app launch, media, time, battery, system status)
   - NLP intent classification & regex routing
   - Real-time search tools (DuckDuckGo, Wikipedia, Yahoo Finance)
   - Dynamic tool synthesis & execution
   - Voice Studio catalog lookup and parameter changes
2. **Tier 2 — Boundary & Corner Cases**:
   - Empty queries, whitespace queries, extremely long queries (>1000 chars)
   - Offline network conditions (simulated network down for Edge TTS, DDG search, and cloud LLMs)
   - Unsupported or malformed tool arguments
   - Special characters and prompt injection attacks (CaMeL shield verification)
3. **Tier 3 — Cross-Feature Combinations**:
   - Multi-turn conversation followed by action command execution
   - Tool execution followed by conversational follow-up accessing prior action results
   - ReAct agent tool failure triggering auto-debug feedback loop
4. **Tier 4 — Real-World Application Scenarios**:
   - Full conversational workflow: user asks about stock price -> asks for explanation -> sets a reminder -> inspects workspace git status -> checks system performance.

## Output Requirements
- Create `TEST_INFRA.md` at project root documenting test architecture, methodology, and feature inventory mapping.
- Implement automated test suite in `Shin/tests/test_e2e_scenarios.py`.
- Run pytest to ensure all new tests execute and pass without breaking existing 266 tests.
- Publish `TEST_READY.md` once complete, write your handoff report to `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\test_writer_e2e\handoff.md`, and notify orchestrator.


## 2026-11-09T14:04:24Z
You are the E2E Test Writer for the Shin Voice Assistant project.
Working Directory: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant
State Folder: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\test_writer_e2e
Original Request: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\ORIGINAL_REQUEST.md
Project File: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\PROJECT.md
Dispatch File: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\test_writer_e2e\DISPATCH.md

Read ORIGINAL_REQUEST.md, PROJECT.md, and your DISPATCH.md.
Design and construct an opaque-box, requirement-driven E2E test suite in Shin/tests/test_e2e_scenarios.py and publish TEST_INFRA.md and TEST_READY.md according to the 4-tier methodology (Tier 1: Feature Coverage, Tier 2: Boundary/Corner Cases, Tier 3: Cross-Feature Combinations, Tier 4: Real-World Scenarios).
Execute pytest to ensure your new tests run cleanly alongside the legacy 266 unit tests.
Deliver your handoff report to m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\test_writer_e2e\handoff.md and notify the orchestrator.
