"""
token_tracker.py — Tracks LLM token usage, calculates costs, and manages budget limits.
"""

import json
import os
import threading
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("shin.token_tracker")

USAGE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "token_usage.json")

# Migrate old token_usage.json from root or core/ if it exists
_OLD_USAGE_DIR_CORE = os.path.dirname(os.path.abspath(__file__))
_OLD_USAGE_DIR_ROOT = os.path.dirname(_OLD_USAGE_DIR_CORE)

for old_dir in (_OLD_USAGE_DIR_CORE, _OLD_USAGE_DIR_ROOT):
    old_file = os.path.join(old_dir, "token_usage.json")
    if os.path.exists(old_file) and old_file != USAGE_FILE:
        try:
            os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
            import shutil
            shutil.copy2(old_file, USAGE_FILE)
            os.remove(old_file)
            logger.info("Migrated token_usage.json from %s to %s", old_file, USAGE_FILE)
        except Exception as exc:
            logger.warning("Failed to migrate token_usage.json from %s: %s", old_file, exc)
_db_lock = threading.Lock()

# Pricing in USD per 1,000,000 tokens
MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "default": {"input": 0.15, "output": 0.60}
}


def _load_data() -> dict:
    """Load token usage database with thread-safety."""
    if not os.path.exists(USAGE_FILE):
        return {"monthly_limit_usd": 5.0, "logs": []}
    try:
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "logs" not in data:
                data["logs"] = []
            if "monthly_limit_usd" not in data:
                data["monthly_limit_usd"] = 5.0
            return data
    except Exception as exc:
        logger.error("Failed to load token usage database: %s", exc)
        return {"monthly_limit_usd": 5.0, "logs": []}


def _save_data(data: dict) -> None:
    """Save token usage database with thread-safety and log pruning."""
    try:
        # Prune logs older than 60 days to keep the database lightweight
        cutoff = (datetime.now() - timedelta(days=60)).isoformat()
        data["logs"] = [
            log for log in data.get("logs", [])
            if log.get("timestamp", "") >= cutoff
        ]
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as exc:
        logger.error("Failed to save token usage database: %s", exc)


def log_usage(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Log token usage event and return the estimated USD cost.
    """
    if prompt_tokens <= 0 and completion_tokens <= 0:
        return 0.0

    # Clean model name to find pricing
    model_key = model.lower()
    pricing = MODEL_PRICING.get("default")
    for key in MODEL_PRICING:
        if key in model_key:
            pricing = MODEL_PRICING[key]
            break

    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    total_cost = input_cost + output_cost

    with _db_lock:
        data = _load_data()
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider.lower(),
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": total_cost
        }
        data["logs"].append(log_entry)
        _save_data(data)

    logger.debug(
        "Logged usage for %s (%s): In=%d, Out=%d, Cost=$%.6f",
        provider, model, prompt_tokens, completion_tokens, total_cost
    )
    return total_cost


def log_openai_usage(model: str, response) -> float:
    """
    Log token usage from an OpenAI ChatCompletion response object safely.
    """
    try:
        if not response or not hasattr(response, "usage") or not response.usage:
            return 0.0
        prompt_tokens = getattr(response.usage, "prompt_tokens", 0)
        completion_tokens = getattr(response.usage, "completion_tokens", 0)
        return log_usage("openai", model, prompt_tokens, completion_tokens)
    except Exception as exc:
        logger.warning("Failed to extract OpenAI token usage: %s", exc)
        return 0.0


def log_gemini_usage(model: str, response) -> float:
    """
    Log token usage from a Gemini GenerateContentResponse response object safely.
    """
    try:
        if not response or not hasattr(response, "usage_metadata") or not response.usage_metadata:
            return 0.0
        prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0)
        completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0)
        return log_usage("gemini", model, prompt_tokens, completion_tokens)
    except Exception as exc:
        logger.warning("Failed to extract Gemini token usage: %s", exc)
        return 0.0


def set_monthly_limit(limit_usd: float) -> None:
    """Set the monthly spending limit in USD."""
    with _db_lock:
        data = _load_data()
        data["monthly_limit_usd"] = max(0.1, float(limit_usd))
        _save_data(data)


def get_usage_stats() -> dict:
    """
    Calculate and aggregate token statistics.
    Returns details for today, current month, lifetime, and the last 7 days history.
    """
    with _db_lock:
        data = _load_data()

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    current_month_str = now.strftime("%Y-%m")

    # Stats initialization
    stats = {
        "today": {"tokens": 0, "cost": 0.0, "calls": 0},
        "monthly": {"tokens": 0, "cost": 0.0, "calls": 0},
        "lifetime": {"tokens": 0, "cost": 0.0, "calls": 0},
        "by_provider": {
            "openai": {"tokens": 0, "cost": 0.0, "calls": 0},
            "gemini": {"tokens": 0, "cost": 0.0, "calls": 0}
        },
        "monthly_limit_usd": data.get("monthly_limit_usd", 5.0),
        "keys_status": {
            "openai": bool(os.getenv("OPENAI_API_KEY", "").strip()),
            "gemini": bool(os.getenv("GEMINI_API_KEY", "").strip())
        },
        "history_7d": []
    }

    # Helper for last 7 days mapping
    history_days = {}
    for i in range(7):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        history_days[day] = {"date": day, "cost": 0.0, "tokens": 0, "calls": 0}

    for log in data.get("logs", []):
        ts = log.get("timestamp", "")
        if not ts:
            continue
        try:
            log_date = ts.split("T")[0]
            log_month = log_date[:7]
        except Exception:
            continue

        cost = log.get("cost", 0.0)
        tokens = log.get("prompt_tokens", 0) + log.get("completion_tokens", 0)
        prov = log.get("provider", "")

        # Lifetime
        stats["lifetime"]["tokens"] += tokens
        stats["lifetime"]["cost"] += cost
        stats["lifetime"]["calls"] += 1

        # Provider
        if prov in stats["by_provider"]:
            stats["by_provider"][prov]["tokens"] += tokens
            stats["by_provider"][prov]["cost"] += cost
            stats["by_provider"][prov]["calls"] += 1

        # Today
        if log_date == today_str:
            stats["today"]["tokens"] += tokens
            stats["today"]["cost"] += cost
            stats["today"]["calls"] += 1

        # Monthly
        if log_month == current_month_str:
            stats["monthly"]["tokens"] += tokens
            stats["monthly"]["cost"] += cost
            stats["monthly"]["calls"] += 1

        # Last 7 days history
        if log_date in history_days:
            history_days[log_date]["cost"] += cost
            history_days[log_date]["tokens"] += tokens
            history_days[log_date]["calls"] += 1

    # Format 7d history ordered chronologically
    sorted_days = sorted(history_days.keys())
    stats["history_7d"] = [history_days[d] for d in sorted_days]

    return stats
