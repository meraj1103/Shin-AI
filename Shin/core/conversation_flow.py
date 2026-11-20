"""conversation_flow.py — Advanced Conversational Flow Engine for Shin.
Provides ChatGPT / Gemini Live style fluid multi-turn voice interaction:
  • Continuous conversation sessions (follow-up listening window without wake word)
  • Real-time barge-in / interruptibility signals
  • Fully customizable persona, brevity levels, and system prompts via JSON config
  • Smart exit phrase detection ("that's all", "bye", "thanks", "bas")
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("shin.convo_flow")

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "conversation_flow.json"


class ConversationFlowManager:
    """Manages the real-time conversation state machine, follow-up windows,
    barge-in interruption signals, and customizable prompt generation.
    """

    _instance: Optional[ConversationFlowManager] = None

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or _CONFIG_PATH
        self.config: Dict[str, Any] = {}
        self.in_conversation: bool = False
        self.session_start_time: float = 0.0
        self.last_turn_time: float = 0.0
        self.turn_count: int = 0
        self._interrupted: bool = False

        self.load_config()

    @classmethod
    def get(cls) -> ConversationFlowManager:
        if cls._instance is None:
            cls._instance = ConversationFlowManager()
        return cls._instance

    def load_config(self) -> Dict[str, Any]:
        """Load or reload the conversation configuration from JSON."""
        defaults = {
            "enabled": True,
            "conversation_mode": "continuous",
            "follow_up_timeout_seconds": 6.0,
            "barge_in_enabled": True,
            "brevity_mode": "concise",
            "filler_words_enabled": True,
            "persona": {
                "assistant_name": "Shin",
                "user_name": "MJ",
                "primary_language": "hinglish",
                "tone": "authentic, sharp, warm, quick-witted, caring tomboy companion",
                "voice_speed": 1.0,
                "system_prompt_template": (
                    "You are {assistant_name}, {user_name}'s personal AI companion and voice assistant. "
                    "You speak natural, conversational {language}. You are authentic, quick-witted, and genuinely helpful. "
                    "Keep your spoken responses concise (1 to 2 sentences for casual chat) so it sounds like a real-time voice call. "
                    "{brevity_instruction}\nContext memories: {memories}"
                ),
            },
            "brevity_rules": {
                "concise": "Deliver direct, spoken-style punchy answers in 1-2 short sentences. Avoid bullet points or code blocks.",
                "detailed": "Explain thoughtfully with thorough context while maintaining a natural spoken tone.",
                "adaptive": "Match the depth of the user's question: short queries get quick answers, complex questions get step-by-step guidance.",
            },
            "exit_phrases": [
                "bye", "goodbye", "that's all", "that's it", "thanks", "thank you",
                "stop", "nevermind", "go to sleep", "standby", "chup", "bas", "baad mein", "alvida"
            ],
            "filler_words": ["Hmm...", "Haan...", "Well...", "Dekh...", "Alright..."],
        }

        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    defaults.update(loaded)
                    self.config = defaults
                    logger.debug("Loaded conversation flow configuration from %s", self.config_path)
                    return self.config
            except Exception as exc:
                logger.warning("Could not read conversation flow config: %s. Using defaults.", exc)

        self.config = defaults
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(defaults, f, indent=2)
        except Exception:
            pass
        return self.config

    def is_enabled(self) -> bool:
        return bool(self.config.get("enabled", True))

    def is_continuous_mode(self) -> bool:
        return self.config.get("conversation_mode", "continuous") == "continuous"

    def get_follow_up_timeout(self) -> float:
        return float(self.config.get("follow_up_timeout_seconds", 6.0))

    def is_barge_in_enabled(self) -> bool:
        return bool(self.config.get("barge_in_enabled", True))

    def start_session(self) -> None:
        """Begin or refresh an active multi-turn conversation session."""
        now = time.time()
        self.in_conversation = True
        self.session_start_time = now
        self.last_turn_time = now
        self.turn_count = 0
        self._interrupted = False
        logger.info("Conversational flow session started.")

    def end_session(self, reason: str = "timeout") -> None:
        """End the continuous conversation session and return to idle/wake-word state."""
        self.in_conversation = False
        self.turn_count = 0
        self._interrupted = False
        logger.info("Conversational flow session ended (reason: %s).", reason)

    def is_in_active_session(self) -> bool:
        """Check if an active multi-turn conversation session is alive and unexpired."""
        if not self.is_enabled() or not self.is_continuous_mode():
            return False
        if not self.in_conversation:
            return False

        timeout = self.get_follow_up_timeout()
        elapsed = time.time() - self.last_turn_time
        if elapsed > timeout:
            self.end_session(reason=f"timeout ({elapsed:.1f}s > {timeout:.1f}s)")
            return False
        return True

    def record_turn(self, user_text: str, assistant_reply: str) -> None:
        """Record an exchanged turn and reset the follow-up countdown."""
        now = time.time()
        self.in_conversation = True
        self.last_turn_time = now
        self.turn_count += 1
        logger.debug("Turn %d recorded. Follow-up countdown refreshed (%.1fs).", self.turn_count, self.get_follow_up_timeout())

    def should_exit_conversation(self, text: str) -> bool:
        """Check if the user spoken phrase is an intentional exit command."""
        if not text:
            return False
        clean = text.lower().strip()
        exit_phrases = self.config.get("exit_phrases", [])
        for phrase in exit_phrases:
            phrase_clean = phrase.lower().strip()
            # Exact match or starts/ends with phrase
            if clean == phrase_clean or clean.startswith(phrase_clean + " ") or clean.endswith(" " + phrase_clean):
                return True
        return False

    def request_barge_in(self) -> None:
        """Trigger an interruption event to stop current TTS output immediately."""
        if self.is_barge_in_enabled():
            self._interrupted = True
            logger.info("Barge-in requested. Cutting off active speech.")

    def reset_barge_in(self) -> None:
        self._interrupted = False

    def is_interrupted(self) -> bool:
        return self._interrupted

    def get_natural_filler(self) -> Optional[str]:
        """Return a natural conversational filler word if enabled."""
        if not self.config.get("filler_words_enabled", True):
            return None
        fillers = self.config.get("filler_words", ["Hmm...", "Haan..."])
        return random.choice(fillers) if fillers else None

    def build_system_prompt(self, memory_context: str = "", language: str = "Hinglish") -> str:
        """Construct a personalized, context-rich system prompt matching user settings."""
        persona = self.config.get("persona", {})
        template = persona.get(
            "system_prompt_template",
            "You are {assistant_name}, {user_name}'s companion. Reply in {language}. {brevity_instruction}\nContext: {memories}"
        )

        brevity_mode = self.config.get("brevity_mode", "concise")
        brevity_instruction = self.config.get("brevity_rules", {}).get(
            brevity_mode,
            "Keep responses conversational and concise."
        )

        assistant_name = persona.get("assistant_name", "Shin")
        user_name = persona.get("user_name", "MJ")

        prompt = template.format(
            assistant_name=assistant_name,
            user_name=user_name,
            language=language,
            brevity_instruction=brevity_instruction,
            memories=memory_context or "None recorded yet.",
        )
        return prompt
