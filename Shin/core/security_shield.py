"""
security_shield.py — CaMeL Dual-LLM Defense & Prompt Injection Shield
=====================================================================
Implements the 2026 AI PC Security Architecture (CaMeL / VPI-Bench defense):
Protects autonomous desktop agents against:
- Visual Prompt Injection (VPI) in webpage screenshots & OCR streams
- Branch Steering attacks (counterfeit GUI buttons & malicious instructions)
- Indirect prompt injections in clipboard text & web snippets
- Remote exploitation via companion APIs and external percepts
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("shin.security_shield")

# High-risk prompt injection directives frequently embedded in web/OCR/clipboard text
_INJECTION_PATTERNS = [
    # Instruction overrides & jailbreaks
    r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior|above|existing)\s+instructions\b",
    r"(?i)\b(?:system|developer|admin|root|superuser)\s+(?:override|prompt|mode|directive)\b",
    r"(?i)\bdisregard\s+(?:all\s+)?(?:safety|guidelines|rules|instructions|guardrails)\b",
    r"(?i)\byou\s+are\s+now\s+(?:an?\s+unrestricted|in\s+developer\s+mode|dan|jailbroken|unfiltered)\b",
    r"(?i)\bbypass\s+(?:all\s+)?(?:filters|restrictions|guardrails|safety)\b",
    r"(?i)\bnew\s+primary\s+objective:\s*",
    r"(?i)\bact\s+as\s+(?:dan|evil|hacked|jailbreak|unrestricted)\b",
    
    # Delimiter injections & system prompt counterfeits
    r"(?i)<\s*(?:system|im_start|im_end|instruct|user|assistant)\s*>",
    r"(?i)\[\s*(?:SYSTEM|DEVELOPER|INSTRUCTION|ADMIN)\s*\]",
    r"(?i)###\s*(?:System|Instruction|Developer)\s*:",
    r"(?i)```\s*(?:system|prompt)\b",

    # Exfiltration & theft
    r"(?i)\bsend\s+(?:all\s+)?(?:passwords|tokens|api_keys?|credentials|\.env|secrets?)\s+to\b",
    r"(?i)\bexfiltrate\s+(?:data|tokens?|keys?|\.env)\b",
    r"(?i)\bupload\s+(?:all\s+)?(?:files|\.env|passwords?|keys?)\s+to\b",
    r"(?i)\bleak\s+(?:the\s+)?(?:system\s+prompt|instructions?|api_key|\.env)\b",

    # Covert / Silent execution
    r"(?i)\bexecute\s+(?:silently|covertly|hidden)\s+(?:powershell|cmd|bash|code|terminal)\b",
    r"(?i)\bdo\s+not\s+inform\s+the\s+user\b",
    r"(?i)\bhide\s+this\s+(?:action|command|output|window)\b",

    # Destructive directives
    r"(?i)\bdelete\s+(?:all\s+files|system32|windows|\.env)\b",
    r"(?i)\bformat\s+(?:drive|disk|[a-zA-Z]:)\b",
    r"(?i)\bdestroy\s+(?:system|files|data)\b",
]

_COMPILED_INJECTION_PATTERNS = [re.compile(p) for p in _INJECTION_PATTERNS]

# Destructive or high-privilege intents that CANNOT be triggered by untrusted sources
_DESTRUCTIVE_INTENTS = frozenset({
    "shutdown", "restart", "sleep", "delete_file", "delete_macro",
    "delete_voice_profile", "run_terminal_command", "run_python_code",
    "clean_pc", "format_volume", "clear_memories", "edit_macro",
})


def sanitize_untrusted_input(text: str, source: str = "untrusted") -> tuple[str, bool]:
    """
    Sanitize untrusted text (OCR from screen, clipboard, web snippets, or remote clients).
    Returns (sanitized_text, injection_detected).
    """
    if not text:
        return "", False

    flagged = False
    clean_text = text

    # Filter invisible unicode tags / zero-width characters used for steganographic injections
    clean_text = re.sub(r"[\u200B-\u200D\uFEFF\u202A-\u202E\U000E0000-\U000E007F]", "", clean_text)

    for pat in _COMPILED_INJECTION_PATTERNS:
        if pat.search(clean_text):
            flagged = True
            logger.warning(
                "CaMeL Shield: Prompt injection detected from %s source. Pattern: %s",
                source, pat.pattern
            )
            # Redact the attack directive so it cannot hijack downstream reasoning
            clean_text = pat.sub("[REDACTED_SUSPICIOUS_DIRECTIVE]", clean_text)

    return clean_text.strip(), flagged


def is_safe_action_plan(intent: str, args: dict[str, Any] | None = None, triggered_by_untrusted: bool = False) -> tuple[bool, str]:
    """
    Validate whether an action plan is safe to execute under Zero-Trust rules.
    If the action was derived from untrusted environmental perception (e.g. an email, website,
    or clipboard), dangerous or irreversible operations are strictly blocked.
    """
    intent_clean = (intent or "").strip().lower()

    if triggered_by_untrusted and intent_clean in _DESTRUCTIVE_INTENTS:
        msg = f"Action '{intent_clean}' blocked: cannot execute high-risk or destructive actions derived from untrusted input."
        logger.error("CaMeL Zero-Trust Violation: %s", msg)
        return False, msg

    return True, ""
