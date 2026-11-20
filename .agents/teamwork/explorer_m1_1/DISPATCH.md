# Dispatch: Explorer M1_1 — UI & Vision Defect Remediation

## Mission
Design precise, minimal, backward-compatible fix strategies for the floating 3D orb window crash and MediaPipe gesture recognition crash.

## Context
- Working Directory: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant`
- State Folder: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_m1_1`
- Original Request: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\ORIGINAL_REQUEST.md`
- Project Document: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\PROJECT.md`
- Survey 1 Report: `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_survey_1\survey_report.md`

## Assigned Defects
1. `Shin/core/orb_window.py:204-210`: `pywebview` raises `ValueError: #00000000 is not a valid hex triplet color`. Investigate how `pywebview` handles transparent/frameless windows on Windows, identify the exact valid parameter (e.g. `background_color='#000000'`, `transparent=True` or parameter adjustments), and ensure the 3D orb window loads cleanly without crashing.
2. `Shin/core/gestures.py:141-145`: In MediaPipe 1.1.0, `module 'mediapipe' has no attribute 'solutions'`. Investigate how `Shin/core/gestures.py` imports and uses MediaPipe, design safe defensive initialization and graceful fallback/degradation so the gesture background loop never crashes if `mp.solutions` or camera is unavailable.

## Output Requirements
Do NOT implement code changes directly.
Provide exact diff recommendations, line references, and verification commands in `m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_m1_1\fix_strategy.md` and complete `handoff.md`.


## 2026-11-09T14:04:04Z
You are the UI & Vision Defect Explorer for Milestone 1.
Working Directory: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant
State Folder: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_m1_1
Original Request: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\ORIGINAL_REQUEST.md
Project File: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\PROJECT.md
Dispatch File: m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_m1_1\DISPATCH.md

Read ORIGINAL_REQUEST.md, PROJECT.md, and your DISPATCH.md.
Investigate and design precise fix strategies for:
1. Shin/core/orb_window.py: pywebview ValueError #00000000 invalid hex triplet crash
2. Shin/core/gestures.py: mediapipe 1.1.0 AttributeError mp.solutions crash
Do NOT implement code changes directly.
Write your recommendations to m:\MJ\projects coding\AI-Projects\Shin-Voice-Assistant\.agents\teamwork\explorer_m1_1\fix_strategy.md and complete handoff.md. Once done, message the orchestrator with your findings.
