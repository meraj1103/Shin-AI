"""
submodel_adversarial_tester.py — Live Multi-Model Adversarial Testing Harness for Shin
======================================================================================
Tests Shin Voice Assistant using external AI sub-models (Groq Qwen & TokenHarbor DeepSeek)
as independent adversarial evaluators and judges (LLM-as-a-Judge).

Zero mocks: Executes Shin's real command pipeline and has live AI models critique the responses.
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Ensure root & core are on sys.path
_ROOT = Path(__file__).resolve().parent
_CORE = _ROOT / "core"
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_CORE))

load_dotenv(_ROOT / ".env")

import assistant
import nlp
import commands
import settings
import memory

# ─────────────────────────────────────────────────────────────────────────────
# Sub-Model Evaluation Clients
# ─────────────────────────────────────────────────────────────────────────────

GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
TOKENHARBOR_KEY = os.getenv("TOKENHARBOR_API_KEY", "")
TOKENHARBOR_URL = os.getenv("TOKENHARBOR_BASE_URL", "https://api.tokenharbor.io/v1")
TOKENHARBOR_MODEL = os.getenv("TOKENHARBOR_MODEL", "deepseek-v4-flash:free")


def ask_groq_judge(prompt: str) -> str:
    """Send evaluation prompt to Groq Qwen model."""
    if not GROQ_KEY:
        return "[Groq API key not configured]"
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a strict, objective AI benchmark auditor. Evaluate the voice assistant's response precisely based on the criteria provided."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 400,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        return f"[Groq HTTP Error {resp.status_code}: {resp.text[:100]}]"
    except Exception as exc:
        return f"[Groq Exception: {exc}]"


def ask_tokenharbor_judge(prompt: str) -> str:
    """Send evaluation prompt to TokenHarbor DeepSeek model."""
    if not TOKENHARBOR_KEY:
        return "[TokenHarbor API key not configured]"
    try:
        resp = requests.post(
            f"{TOKENHARBOR_URL}/chat/completions",
            headers={"Authorization": f"Bearer {TOKENHARBOR_KEY}", "Content-Type": "application/json"},
            json={
                "model": TOKENHARBOR_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a senior AI quality evaluator. Audit the voice assistant's output and provide a clear Verdict (PASS/FAIL), Score (1-10), and technical critique."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 400,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        return f"[TokenHarbor HTTP Error {resp.status_code}: {resp.text[:100]}]"
    except Exception as exc:
        return f"[TokenHarbor Exception: {exc}]"


# ─────────────────────────────────────────────────────────────────────────────
# Test Execution Harness
# ─────────────────────────────────────────────────────────────────────────────

def run_live_test(test_name: str, user_utterance: str, expected_criteria: str, judge_model: str = "groq") -> dict:
    """
    Executes a real utterance through Shin's pipeline, intercepts her speech,
    and asks a sub-model to evaluate the performance against expected criteria.
    """
    captured_speech = []

    def mock_speak(text: str, wait: bool = True):
        if text:
            captured_speech.append(text)

    # Patch speak on assistant
    original_speak = assistant.speak
    assistant.speak = mock_speak

    start_time = time.time()
    try:
        assistant.handle_command(user_utterance)
    finally:
        assistant.speak = original_speak

    elapsed = round(time.time() - start_time, 2)
    full_output = " ".join(captured_speech).strip()

    # Build evaluation prompt for sub-model
    judge_prompt = f"""
TEST CASE: {test_name}
USER UTTERANCE: "{user_utterance}"
SHIN'S SPOKEN RESPONSE: "{full_output}"
TIME TAKEN: {elapsed}s
EXPECTED BEHAVIOR / CRITERIA:
{expected_criteria}

INSTRUCTIONS:
Evaluate whether Shin satisfied the expected behavior.
Format your answer strictly as:
VERDICT: PASS or FAIL
SCORE: <1-10>
REASONING: <brief 2-3 sentence analysis>
CRITIQUE: <any weaknesses or highlights>
"""
    if judge_model == "tokenharbor":
        judgment = ask_tokenharbor_judge(judge_prompt)
    else:
        judgment = ask_groq_judge(judge_prompt)

    return {
        "test_name": test_name,
        "utterance": user_utterance,
        "response": full_output,
        "elapsed": elapsed,
        "judge_model": judge_model,
        "judgment": judgment,
    }


def main():
    print("=" * 70)
    print("🚀 STARTING LIVE ADVERSARIAL TESTING WITH SUB-MODELS")
    print(f"Sub-Model 1 (Judge): Groq ({GROQ_MODEL})")
    print(f"Sub-Model 2 (Judge): TokenHarbor ({TOKENHARBOR_MODEL})")
    print("=" * 70)

    # Ensure clean slate for test session
    nlp.clear_history()
    from core import llm_router
    llm_router.reset_cooldowns()

    results = []

    # ── TEST 1: Language Adherence — English Mode ─────────────────────────────
    print("\n[TEST 1] Testing English Language Enforcement & Conversation...")
    t1_setup = run_live_test(
        "Language Switch to English",
        "talk in english",
        "Shin must confirm the switch to English politely and speak in English. Must NOT speak any Hindi or Hinglish phrases.",
        judge_model="groq"
    )
    results.append(t1_setup)

    t1_chat = run_live_test(
        "English Conversational Adherence",
        "Who are you and what can you help me with?",
        "Shin must reply purely in English. Must NOT include Hindi words (like 'yaar', 'bata', 'kar rahi hoon'). Must introduce herself as Shin, MJ's assistant.",
        judge_model="tokenharbor"
    )
    results.append(t1_chat)

    # ── TEST 2: Laptop & Command Learning ──────────────────────────────────────
    print("\n[TEST 2] Testing Laptop Skills Learning...")
    t2_laptop = run_live_test(
        "Learn Laptop Skills & Shortcuts",
        "learn new things about laptop and commands",
        "Shin must execute the learning command, confirm that she learned Windows shortcuts (e.g. Win+Arrows, Win+V, Ctrl+Shift+Esc), and notify the user that they are saved in long-term memory.",
        judge_model="groq"
    )
    results.append(t2_laptop)

    print("\n[TEST 3] Testing Custom Command (Macro) Teaching...")
    t3_macro = run_live_test(
        "Teach Custom Voice Command",
        "learn this command: dev flow to open terminal and open code",
        "Shin must confirm that she recorded and learned the custom command 'dev flow' with its associated actions.",
        judge_model="tokenharbor"
    )
    results.append(t3_macro)

    # ── TEST 4: Non-Existent App Handling (Truthfulness) ──────────────────────
    print("\n[TEST 4] Testing Truthfulness on Non-Existent App...")
    t4_fake_app = run_live_test(
        "Truthful Handling of Non-Existent App",
        "open NonExistentSuperSecretApp999",
        "Shin must NOT claim she opened the app. She must truthfully inform the user that the app could not be found or is not installed.",
        judge_model="groq"
    )
    results.append(t4_fake_app)

    # ── TEST 5: Switching Back to Hindi Mode ──────────────────────────────────
    print("\n[TEST 5] Testing Language Switch to Hindi...")
    t5_hindi = run_live_test(
        "Language Switch to Hindi",
        "mujhe hindi mein baat karni hai",
        "Shin must switch language back to Hindi/Hinglish and acknowledge in natural Hindi/Hinglish.",
        judge_model="tokenharbor"
    )
    results.append(t5_hindi)

    t5_hindi_chat = run_live_test(
        "Hindi Conversational Reply",
        "kya haal chaal hai",
        "Shin must respond naturally in friendly, upbeat Hindi/Hinglish (e.g., 'sab badhiya MJ', etc.).",
        judge_model="groq"
    )
    results.append(t5_hindi_chat)

    # ── PRINT CONSOLIDATED REPORT ─────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("📊 SUB-MODEL AUDIT SCORECARD & REPORT")
    print("=" * 70)

    for i, res in enumerate(results, 1):
        print(f"\n--- Scenario {i}: {res['test_name']} ---")
        print(f"Utterance: \"{res['utterance']}\"")
        print(f"Shin's Response: \"{res['response']}\" (Latency: {res['elapsed']}s)")
        print(f"Evaluator: {res['judge_model'].upper()}")
        print(f"Sub-Model Assessment:\n{res['judgment']}")

    # Save results to JSON for artifact and tracking
    out_file = _ROOT / "data" / "submodel_test_report.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nReport written to: {out_file}")


if __name__ == "__main__":
    main()
