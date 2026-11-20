"""
llm_router.py — Multi-Provider Autonomous Auto-Switching LLM Engine for Shin
=============================================================================
Manages a resilient cascade of AI providers with zero-loss context preservation:
  1. Google Gemini (gemini-3.8-flash / gemini-2.0-flash)
  2. Groq (qwen/qwen3.8-27b / ultra-low latency)
  3. OpenAI (gpt-4o-mini)
  4. Anthropic Claude (claude-3-5-sonnet-latest)
  5. TokenHarbor / OpenRouter
  6. Local LM Studio (offline / private)
  7. Local Ollama (RTX 3050 GPU / Ryzen 5600H)

When any provider hits a rate limit (HTTP 429), token exhaustion, credit limit,
or network timeout, it is placed on a 5-minute cooldown and execution
instantly cascades to the next active provider without losing any conversation
history or ongoing task state.
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

_SHIN_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_SHIN_DIR / ".env")

logger = logging.getLogger("shin.llm_router")

# Cooldown memory tracking: provider_name -> expiration_timestamp
_COOLDOWNS: Dict[str, float] = {}
_DEFAULT_COOLDOWN_SECONDS: float = 300.0  # 5 minutes

# Active preferred provider override (None = automatic cascade)
_PREFERRED_PROVIDER: Optional[str] = None


def set_preferred_provider(provider: Optional[str]) -> Tuple[bool, str]:
    """Set the user's preferred AI model/provider."""
    global _PREFERRED_PROVIDER
    if not provider or provider.lower().strip() in ("auto", "cascade", "default", "none", "automatic"):
        _PREFERRED_PROVIDER = None
        return True, "Auto Cascade (Online First)"

    p = provider.lower().strip()
    alias_map = {
        "gemini": "gemini",
        "google": "gemini",
        "google gemini": "gemini",
        "groq": "groq",
        "llama": "groq",
        "qwen": "groq",
        "fast": "groq",
        "deepseek": "tokenharbor",
        "deep seek": "tokenharbor",
        "tokenharbor": "tokenharbor",
        "token harbor": "tokenharbor",
        "free": "tokenharbor",
        "openai": "openai",
        "gpt": "openai",
        "chatgpt": "openai",
        "gpt-4o": "openai",
        "claude": "anthropic",
        "anthropic": "anthropic",
        "sonnet": "anthropic",
        "ollama": "ollama",
        "local": "ollama",
        "offline": "ollama",
        "lm studio": "lm_studio",
        "lmstudio": "lm_studio",
        "openjarvis": "openjarvis",
        "jarvis": "openjarvis",
        "open jarvis": "openjarvis",
        "omniroute": "omniroute",
    }
    resolved = alias_map.get(p, p)
    valid_providers = ("gemini", "groq", "openai", "anthropic", "tokenharbor", "lm_studio", "ollama", "openjarvis", "omniroute")
    if resolved in valid_providers:
        _PREFERRED_PROVIDER = resolved
        # Clear cooldown on manually selected provider so user can retry it
        _COOLDOWNS.pop(resolved, None)
        disp = resolved.title().replace("_", " ")
        logger.info("Preferred AI provider switched to: %s", disp)
        return True, disp
    return False, f"Unknown provider: {provider}"


def get_preferred_provider() -> Optional[str]:
    """Get the currently preferred AI provider (or None for auto)."""
    return _PREFERRED_PROVIDER


def is_provider_available(provider: str) -> bool:
    """Check if provider is not currently in cooldown."""
    cd_until = _COOLDOWNS.get(provider, 0.0)
    return time.time() >= cd_until


def mark_provider_cooldown(provider: str, seconds: float = _DEFAULT_COOLDOWN_SECONDS, reason: str = "") -> None:
    """Put a provider on cooldown after token limit, quota exhaustion, or error."""
    _COOLDOWNS[provider] = time.time() + seconds
    logger.warning("🔄 [LLM Router]: Provider '%s' cooldown for %ds (%s)", provider, int(seconds), reason)


_LOCAL_ENGINES_CACHE: Dict[str, bool] = {}
_LOCAL_ENGINES_LAST_CHECK: float = 0.0
_LOCAL_ENGINES_CACHE_TTL: float = 60.0  # Cache for 60 seconds to avoid query latency


def reset_cooldowns() -> None:
    """Clear all provider cooldowns."""
    _COOLDOWNS.clear()


class MultiProviderLLMRouter:
    """
    Unified router that handles conversational chats, intent parsing,
    and agent tool-calling with instant, context-preserving failover.
    """

    def __init__(self):
        self._load_config()

    def _load_config(self) -> None:
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
        self.groq_key = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
        self.openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.tokenharbor_key = os.getenv("TOKENHARBOR_API_KEY", "").strip()
        self.tokenharbor_url = os.getenv("TOKENHARBOR_BASE_URL", "https://tokenharbor.ai/v1").rstrip("/")
        self.tokenharbor_model = os.getenv("TOKENHARBOR_MODEL", "deepseek-v4-flash:free").strip()
        self.lm_studio_url = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1").rstrip("/")
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        self.ollama_models = [m.strip() for m in os.getenv("OLLAMA_MODEL", "qwen2.5:3b, llama3.2:3b").split(",") if m.strip()]
        self.openjarvis_url = os.getenv("OPENJARVIS_URL", "http://localhost:8000/v1").rstrip("/")
        self.openjarvis_model = os.getenv("OPENJARVIS_MODEL", "default").strip()
        self.omniroute_url = os.getenv("OMNIROUTE_URL", "http://localhost:20128/v1").rstrip("/")
        self.omniroute_model = os.getenv("OMNIROUTE_MODEL", "default").strip()

    def discover_local_engines(self, force: bool = False) -> Dict[str, bool]:
        """Probes local engine endpoints with cached, non-blocking concurrent checks (OpenJarvis-style)."""
        global _LOCAL_ENGINES_CACHE, _LOCAL_ENGINES_LAST_CHECK
        now = time.time()
        if not force and _LOCAL_ENGINES_CACHE and (now - _LOCAL_ENGINES_LAST_CHECK < _LOCAL_ENGINES_CACHE_TTL):
            return dict(_LOCAL_ENGINES_CACHE)

        import concurrent.futures

        endpoints = {
            "openjarvis": ("127.0.0.1", 8000),
            "omniroute": ("127.0.0.1", 20128),
            "ollama": ("127.0.0.1", 11434),
            "lm_studio": ("127.0.0.1", 1234),
        }
        discovered = {}

        def check_endpoint(item: Tuple[str, Tuple[str, int]]) -> Tuple[str, bool]:
            name, (host, port) = item
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.04)
                s.connect((host, port))
                s.close()
                return name, True
            except Exception:
                return name, False

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = executor.map(check_endpoint, list(endpoints.items()))
            for name, ok in results:
                discovered[name] = ok

        _LOCAL_ENGINES_CACHE = dict(discovered)
        _LOCAL_ENGINES_LAST_CHECK = now
        return discovered

    def is_online(self) -> bool:
        """Fast non-blocking connectivity check."""
        try:
            socket.setdefaulttimeout(1.2)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("1.1.1.1", 53))
            s.close()
            return True
        except Exception:
            return False

    def query(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        max_tokens: int = 300,
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Query AI cascade with automatic failover, preserving conversation context completely.
        Returns:
            {"role": "assistant", "content": "...", "provider": "...", "tool_calls": [...]}
        """
        self._load_config()
        online = self.is_online()

        # Build candidate providers in priority order (Groq & TokenHarbor prioritized for speed & free tier)
        providers = []
        if online:
            if self.groq_key and is_provider_available("groq"):
                providers.append("groq")
            if self.tokenharbor_key and is_provider_available("tokenharbor"):
                providers.append("tokenharbor")
            if self.gemini_key and is_provider_available("gemini"):
                providers.append("gemini")
            if self.openai_key and is_provider_available("openai"):
                providers.append("openai")
            if self.anthropic_key and is_provider_available("anthropic"):
                providers.append("anthropic")

        # Local engines discovered or available
        local_status = self.discover_local_engines()
        if local_status.get("openjarvis") and is_provider_available("openjarvis"):
            providers.append("openjarvis")
        if local_status.get("omniroute") and is_provider_available("omniroute"):
            providers.append("omniroute")
        if is_provider_available("lm_studio"):
            providers.append("lm_studio")
        if is_provider_available("ollama"):
            providers.append("ollama")

        # Honor user-preferred provider override by placing it first
        pref = get_preferred_provider()
        if pref:
            if pref in ("lm_studio", "ollama", "openjarvis", "omniroute") or (online and is_provider_available(pref)):
                providers = [pref] + [p for p in providers if p != pref]

        last_error = None
        for prov in providers:
            try:
                if prov == "gemini":
                    res = self._call_gemini(messages, system_prompt, max_tokens, temperature)
                    if res and res.get("content"):
                        res["provider"] = "gemini"
                        return res
                elif prov == "groq":
                    res = self._call_groq(messages, system_prompt, max_tokens, temperature)
                    if res and res.get("content"):
                        res["provider"] = "groq"
                        return res
                elif prov == "openai":
                    res = self._call_openai(messages, system_prompt, max_tokens, temperature)
                    if res and res.get("content"):
                        res["provider"] = "openai"
                        return res
                elif prov == "anthropic":
                    res = self._call_anthropic(messages, system_prompt, max_tokens, temperature)
                    if res and res.get("content"):
                        res["provider"] = "anthropic"
                        return res
                elif prov == "tokenharbor":
                    res = self._call_tokenharbor(messages, system_prompt, max_tokens, temperature)
                    if res and res.get("content"):
                        res["provider"] = "tokenharbor"
                        return res
                elif prov == "lm_studio":
                    res = self._call_lm_studio(messages, system_prompt, max_tokens, temperature)
                    if res and res.get("content"):
                        res["provider"] = "lm_studio"
                        return res
                elif prov == "ollama":
                    res = self._call_ollama(messages, system_prompt, max_tokens, temperature)
                    if res and res.get("content"):
                        res["provider"] = "ollama"
                        return res
                elif prov == "openjarvis":
                    res = self._call_openjarvis(messages, system_prompt, max_tokens, temperature)
                    if res and res.get("content"):
                        res["provider"] = "openjarvis"
                        return res
                elif prov == "omniroute":
                    res = self._call_omniroute(messages, system_prompt, max_tokens, temperature)
                    if res and res.get("content"):
                        res["provider"] = "omniroute"
                        return res
            except Exception as exc:
                err_str = str(exc).lower()
                last_error = exc
                is_balance_exhausted = any(k in err_str for k in ("no credits", "credit_balance_exhausted", "balance is too low", "no active plan", "insufficient_quota", "402", "credits remaining", "billing", "exceeded your current quota"))
                is_rate_limit = any(k in err_str for k in ("429", "quota", "resource_exhausted", "credits", "balance", "insufficient", "rate limit"))
                cd_time = 86400.0 if is_balance_exhausted else (300.0 if is_rate_limit else 60.0)
                mark_provider_cooldown(prov, seconds=cd_time, reason=str(exc)[:100])
                logger.info("Switching to next provider due to %s failure: %s", prov, exc)
                continue

        # If everything failed, return fallback
        logger.error("All AI providers in the cascade failed. Last error: %s", last_error)
        return {
            "role": "assistant",
            "content": "Arey yaar, abhi internet ya AI servers respond nahi kar rahe. Ek second ruko!",
            "provider": "offline_fallback",
            "tool_calls": []
        }

    def get_status_info(self) -> Dict[str, Any]:
        """Return information about active provider, preferred provider, and cooldowns."""
        self._load_config()
        pref = get_preferred_provider()
        online = self.is_online()
        active = pref if (pref and is_provider_available(pref)) else ("groq" if (online and self.groq_key) else ("gemini" if (online and self.gemini_key) else "local"))
        return {
            "online": online,
            "preferred": pref or "auto",
            "active": active,
            "local_engines": self.discover_local_engines(),
            "cooldowns": {k: max(0, int(v - time.time())) for k, v in _COOLDOWNS.items() if v > time.time()},
        }

    # ── 1. Google Gemini ───────────────────────────────────────────────────────
    def _call_gemini(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.gemini_key, http_options=types.HttpOptions(timeout=5.0))
            contents = []
            for msg in messages:
                role = "user" if msg.get("role") == "user" else "model"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part(text=msg.get("content", ""))]
                ))

            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                max_output_tokens=max_tokens,
                temperature=temperature,
            )

            for model_name in [self.gemini_model, "gemini-3.8-flash", "gemini-2.0-flash"]:
                try:
                    resp = client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=config,
                    )
                    txt = resp.text.strip() if resp and resp.text else ""
                    if txt:
                        return {"role": "assistant", "content": txt, "tool_calls": []}
                except Exception as e:
                    err = str(e)
                    if "404" in err or "not found" in err.lower():
                        continue
                    raise e
        except Exception:
            # Fallback to direct REST API if SDK fails or is not installed
            import requests
            model_target = self.gemini_model if self.gemini_model and not self.gemini_model.startswith("gemini-3") else "gemini-2.0-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_target}:generateContent?key={self.gemini_key}"
            payload = {
                "contents": [{"parts": [{"text": m.get("content", "")}]} for m in messages if m.get("content")]
            }
            if system_prompt:
                payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
            r = requests.post(url, json=payload, timeout=6.0)
            if r.status_code == 200:
                data = r.json()
                cand = data.get("candidates", [])
                if cand:
                    txt = cand[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if txt:
                        return {"role": "assistant", "content": txt.strip(), "tool_calls": []}
        raise RuntimeError("Gemini failed on all candidate models")

    # ── 2. Groq ───────────────────────────────────────────────────────────────
    def _call_groq(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        full_msgs = []
        if system_prompt:
            full_msgs.append({"role": "system", "content": system_prompt})
        full_msgs.extend(messages)

        try:
            from groq import Groq
            # max_retries=0 ensures instantaneous failover (<100ms) on rate-limits (429) to TokenHarbor/Gemini
            client = Groq(api_key=self.groq_key, max_retries=0)
            resp = client.chat.completions.create(
                model=self.groq_model,
                messages=full_msgs,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=5.0,
            )
            txt = resp.choices[0].message.content or ""
            return {"role": "assistant", "content": txt.strip(), "tool_calls": []}
        except Exception as exc:
            # Fallback to direct HTTP REST if Groq SDK is missing or fails
            try:
                import requests
                headers = {
                    "Authorization": f"Bearer {self.groq_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self.groq_model or "llama-3.3-70b-versatile",
                    "messages": full_msgs,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
                r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=6.0)
                if r.status_code == 200:
                    data = r.json()
                    txt = data["choices"][0]["message"]["content"] or ""
                    return {"role": "assistant", "content": txt.strip(), "tool_calls": []}
            except Exception:
                pass
            raise exc

    # ── 3. OpenAI ─────────────────────────────────────────────────────────────
    def _call_openai(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        from openai import OpenAI

        client = OpenAI(api_key=self.openai_key, max_retries=0)
        full_msgs = []
        if system_prompt:
            full_msgs.append({"role": "system", "content": system_prompt})
        full_msgs.extend(messages)

        resp = client.chat.completions.create(
            model=self.openai_model,
            messages=full_msgs,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=4.0,
        )
        txt = resp.choices[0].message.content or ""
        return {"role": "assistant", "content": txt.strip(), "tool_calls": []}

    # ── 4. Anthropic Claude ───────────────────────────────────────────────────
    def _call_anthropic(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        import anthropic

        client = anthropic.Anthropic(api_key=self.anthropic_key, timeout=4.0, max_retries=0)
        user_msgs = [m for m in messages if m.get("role") != "system"]

        resp = client.messages.create(
            model="claude-3-5-sonnet-latest",
            system=system_prompt if system_prompt else None,
            messages=user_msgs,
            max_tokens=max_tokens,
        )
        txt = resp.content[0].text if resp.content else ""
        return {"role": "assistant", "content": txt.strip(), "tool_calls": []}

    # ── 5. TokenHarbor ────────────────────────────────────────────────────────
    def _call_tokenharbor(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        from openai import OpenAI

        client = OpenAI(api_key=self.tokenharbor_key, base_url=self.tokenharbor_url, max_retries=0)
        full_msgs = []
        if system_prompt:
            full_msgs.append({"role": "system", "content": system_prompt})
        full_msgs.extend(messages)

        candidate_models = [self.tokenharbor_model, "deepseek-v4-flash:free", "mimo-v2.6-flash:free"]
        last_err = None
        for m in candidate_models:
            if not m:
                continue
            try:
                resp = client.chat.completions.create(
                    model=m,
                    messages=full_msgs,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=5.0,
                )
                txt = resp.choices[0].message.content or ""
                if txt:
                    return {"role": "assistant", "content": txt.strip(), "tool_calls": []}
            except Exception as e:
                last_err = e
                continue
        raise last_err or RuntimeError("TokenHarbor failed on all free candidate models")

    # ── 6. Local LM Studio ────────────────────────────────────────────────────
    def _call_lm_studio(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        import requests

        full_msgs = []
        if system_prompt:
            full_msgs.append({"role": "system", "content": system_prompt})
        full_msgs.extend(messages)

        resp = requests.post(
            f"{self.lm_studio_url}/chat/completions",
            json={
                "messages": full_msgs,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=8.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            txt = data["choices"][0]["message"]["content"]
            return {"role": "assistant", "content": txt.strip(), "tool_calls": []}
        raise RuntimeError(f"LM Studio returned status {resp.status_code}")

    # ── 7. Local Ollama ───────────────────────────────────────────────────────
    def _call_ollama(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        import requests

        full_msgs = []
        if system_prompt:
            full_msgs.append({"role": "system", "content": system_prompt})
        full_msgs.extend(messages)

        target_model = self.ollama_models[0] if self.ollama_models else "qwen2.5:3b"

        resp = requests.post(
            f"{self.ollama_host}/api/chat",
            json={
                "model": target_model,
                "messages": full_msgs,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
            timeout=15.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            txt = data.get("message", {}).get("content", "")
            return {"role": "assistant", "content": txt.strip(), "tool_calls": []}
        raise RuntimeError(f"Ollama returned status {resp.status_code}")

    # ── 8. OpenJarvis Local Engine (http://localhost:8000/v1) ─────────────────
    def _call_openjarvis(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        import requests

        full_msgs = []
        if system_prompt:
            full_msgs.append({"role": "system", "content": system_prompt})
        full_msgs.extend(messages)

        resp = requests.post(
            f"{self.openjarvis_url}/chat/completions",
            json={
                "model": self.openjarvis_model,
                "messages": full_msgs,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            txt = data["choices"][0]["message"]["content"]
            return {"role": "assistant", "content": txt.strip(), "tool_calls": []}
        raise RuntimeError(f"OpenJarvis returned status {resp.status_code}")

    # ── 9. OmniRoute Local Gateway (http://localhost:20128/v1) ───────────────
    def _call_omniroute(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        import requests

        full_msgs = []
        if system_prompt:
            full_msgs.append({"role": "system", "content": system_prompt})
        full_msgs.extend(messages)

        resp = requests.post(
            f"{self.omniroute_url}/chat/completions",
            json={
                "model": self.omniroute_model,
                "messages": full_msgs,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            txt = data["choices"][0]["message"]["content"]
            return {"role": "assistant", "content": txt.strip(), "tool_calls": []}
        raise RuntimeError(f"OmniRoute returned status {resp.status_code}")


# Singleton router instance for Shin runtime
_router_instance: Optional[MultiProviderLLMRouter] = None


def get_router() -> MultiProviderLLMRouter:
    """Return the global multi-provider router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = MultiProviderLLMRouter()
    return _router_instance


def get_status_info() -> Dict[str, Any]:
    """Return status dictionary of the active multi-provider router."""
    return get_router().get_status_info()


# Convenience alias for router class
LLMRouter = MultiProviderLLMRouter
