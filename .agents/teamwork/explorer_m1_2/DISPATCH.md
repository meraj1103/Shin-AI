# Dispatch: Explorer M1_2 — Voice Runtime & Audio Flow Defect Remediation

## Mission
Design precise, minimal, backward-compatible fix strategies for `Shin/assistant.py` audio, speech recognition, and TTS defects.

## Context
- Working Directory: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant`
- State Folder: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_m1_2`
- Original Request: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\ORIGINAL_REQUEST.md`
- Project Document: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\PROJECT.md`
- Survey 1 Report: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_survey_1\survey_report.md`

## Assigned Defects in `Shin/assistant.py`
1. `Shin/assistant.py:387-465`: `UnboundLocalError: cannot access local variable 'subprocess' where it is not associated with a value` in `_speak_edge_tts`. Investigate variable scoping, ensure `subprocess` is imported cleanly at module level, and audit all audio playback fallback paths.
2. `Shin/assistant.py:728-758`: Vosk offline fallback looks for `./languages/vosk-model-small-en-us-0.15` using relative path instead of `_ROOT_DIR / "languages" / ...`. Investigate path resolution so Vosk loads reliably regardless of working directory.
3. `Shin/assistant.py:483-545`: Kokoro TTS Cython serialization `__reduce_cython__` error & Hugging Face network check lag causing 60-second TTS queue watchdog stalls. Investigate how Kokoro worker is called and synthesize a clean, robust fallback.

## Output Requirements
Do NOT implement code changes directly.
Provide exact diff recommendations, line references, and verification commands in `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_m1_2\fix_strategy.md` and complete `handoff.md`.
