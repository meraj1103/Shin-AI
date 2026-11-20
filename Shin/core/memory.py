import json
import os
import time
from datetime import datetime
import logging

logger = logging.getLogger("shin.memory")
_ollama_offline_until: float = 0.0
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MEMORY_FILE = os.path.join(_DATA_DIR, "memory.json")
ALT_MEMORY_FILE = os.path.join(_DATA_DIR, "memories.json")

# Migrate old memory.json if it exists in core/ or root
_OLD_MEMORY_DIR_CORE = os.path.dirname(os.path.abspath(__file__))
_OLD_MEMORY_DIR_ROOT = os.path.dirname(_OLD_MEMORY_DIR_CORE)

for old_dir in (_OLD_MEMORY_DIR_CORE, _OLD_MEMORY_DIR_ROOT):
    old_file = os.path.join(old_dir, "memory.json")
    if os.path.exists(old_file) and old_file != MEMORY_FILE:
        try:
            os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
            import shutil
            shutil.copy2(old_file, MEMORY_FILE)
            os.remove(old_file)
            logger.info("Migrated memory.json from %s to %s", old_file, MEMORY_FILE)
        except Exception as exc:
            logger.warning("Failed to migrate memory.json from %s: %s", old_file, exc)


def _invalidate_nlp_cache():
    """Trigger immediate invalidation of NLP memory context cache."""
    try:
        import nlp
        nlp.invalidate_memory_cache()
    except Exception:
        try:
            from core import nlp
            nlp.invalidate_memory_cache()
        except Exception:
            pass


def load_memories() -> list:
    """Load memories from memory.json (or memories.json fallback)."""
    target = MEMORY_FILE if os.path.exists(MEMORY_FILE) else (ALT_MEMORY_FILE if os.path.exists(ALT_MEMORY_FILE) else MEMORY_FILE)
    if not os.path.exists(target):
        return []
    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []
            return [m for m in data if isinstance(m, dict) and "content" in m]
    except Exception as exc:
        logger.error("Failed to load memory file (%s): %s", target, exc)
        return []

def save_memories(memories: list):
    """Save memories to the local memory.json file and mirror to memories.json (atomic write)."""
    tmp_file = MEMORY_FILE + ".tmp"
    try:
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(memories, f, indent=4, ensure_ascii=False)
        os.replace(tmp_file, MEMORY_FILE)

        # Mirror to memories.json for dual-filename persistence
        try:
            with open(ALT_MEMORY_FILE, "w", encoding="utf-8") as f2:
                json.dump(memories, f2, indent=4, ensure_ascii=False)
        except Exception as exc2:
            logger.debug("Failed to mirror memories to memories.json: %s", exc2)

        _invalidate_nlp_cache()
    except Exception as exc:
        logger.error("Failed to save memories: %s", exc)
        try:
            os.remove(tmp_file)
        except OSError:
            pass

def add_memory(content: str) -> str:
    """Add a new memory with a timestamp."""
    content = content.strip()
    if not content:
        return "I can't remember empty information."
    
    memories = load_memories()
    # Check if this exact memory already exists to avoid duplicates
    for mem in memories:
        if isinstance(mem, dict) and mem.get("content", "").lower() == content.lower():
            return "I already remember that."
            
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    memories.append({
        "timestamp": timestamp,
        "content": content
    })
    save_memories(memories)
    return f"I've committed that to memory: '{content}'"

def search_memories(query: str = None) -> list:
    """Search memories by keyword. Returns all if query is None."""
    memories = load_memories()
    if not query:
        return memories
        
    query_words = query.lower().split()
    results = []
    for mem in memories:
        if not isinstance(mem, dict):
            continue
        content_lower = mem.get("content", "").lower()
        # Simple match score based on how many query words are found
        score = sum(1 for word in query_words if word in content_lower)
        if score > 0:
            results.append((score, mem))
            
    # Sort by score (highest first)
    results.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in results]

def delete_memories(query: str = None) -> tuple[int, str]:
    """Delete memories matching query. If query is None or 'all', deletes all."""
    memories = load_memories()
    if not memories:
        return 0, "Your memory is already empty."
        
    if not query or query.lower().strip() in ("all", "everything"):
        save_memories([])
        return len(memories), "I have cleared all memories."
        
    query_words = query.lower().split()
    remaining = []
    deleted_count = 0
    for mem in memories:
        if not isinstance(mem, dict):
            continue
        content_lower = mem.get("content", "").lower()
        # If any query word matches, we mark it for deletion
        if any(word in content_lower for word in query_words):
            deleted_count += 1
        else:
            remaining.append(mem)
            
    if deleted_count > 0:
        save_memories(remaining)
        return deleted_count, f"Deleted {deleted_count} matching memory entries."
    else:
        return 0, f"I couldn't find any memories matching '{query}' to delete."

def build_memories_prompt_context() -> str:
    """Format stored memories as context for the AI prompt."""
    memories = load_memories()
    if not memories:
        return ""
    
    lines = ["\nUser's saved personal facts & memories (Shin's persistent memory):"]
    for i, mem in enumerate(memories, 1):
        if not isinstance(mem, dict):
            continue
        ts = mem.get("timestamp", "unknown")
        cnt = mem.get("content", "")
        lines.append(f"  {i}. [{ts}] {cnt}")
    lines.append("Use this memory context to answer any questions about the user's past, tasks, details, preferences, or belongings.\n")
    return "\n".join(lines)

def extract_and_store_implicit_knowledge(text: str) -> None:
    """
    Background task to analyze user utterances for new personal facts
    or tasks, and automatically remember them.
    """
    lm_studio_url = os.getenv("LM_STUDIO_URL", "").strip().rstrip("/")
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    ollama_model = os.getenv("OLLAMA_MODEL", "").strip()

    if not (lm_studio_url or gemini_key or openai_key or groq_key or ollama_model):
        return

    prompt = (
        "Analyze the following user utterance. If the user states a personal fact, preference, "
        "or relationship about themselves (e.g., 'I am allergic to peanuts', 'My sister is Jane'), "
        "OR if they state an implicit task they need to do (e.g., 'I need to buy milk', 'I should finish the report'), "
        "extract it as a concise statement.\n\n"
        "Rules:\n"
        "1. If it is a personal fact, output exactly: FACT: [the fact]. (e.g., FACT: The user is allergic to peanuts)\n"
        "2. If it is a task, output exactly: TASK: [the task]. (e.g., TASK: Buy milk)\n"
        "3. If it is just a general command, question, or neither of the above, output exactly: NONE\n"
        "4. Only output the single most important line.\n\n"
        f"Utterance: \"{text}\""
    )

    response_text = ""
    try:
        # Check LM Studio local endpoint first
        if lm_studio_url:
            try:
                import requests as _req
                payload: dict = {
                    "messages": [
                        {"role": "system", "content": "You are a concise assistant that extracts personal facts and tasks from user statements."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 50,
                    "temperature": 0.1,
                    "stream": False,
                }
                lm_model = os.getenv("LM_STUDIO_MODEL", "").strip()
                if lm_model:
                    payload["model"] = lm_model
                resp = _req.post(
                    f"{lm_studio_url}/chat/completions",
                    json=payload,
                    timeout=(1.0, 5.0),
                )
                if resp.status_code == 200:
                    response_text = resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as _lm_err:
                logger.debug("LM Studio memory extraction skipped: %s", _lm_err)

        # Route through LLM Router for fast online providers (Groq / Gemini)
        if not response_text and (groq_key or gemini_key or openai_key):
            try:
                try:
                    from core import llm_router
                except ImportError:
                    import llm_router

                router = llm_router.get_router()
                res = router.query(
                    messages=[{"role": "user", "content": prompt}],
                    system_prompt="You are a concise assistant that extracts personal facts and tasks from user statements.",
                    max_tokens=50,
                    temperature=0.1,
                )
                if res and res.get("content") and not res.get("content", "").startswith("Arey yaar"):
                    response_text = res["content"].strip()
            except Exception as _router_err:
                logger.debug("Router memory extraction skipped: %s", _router_err)

        # Fallback to Ollama if no online response
        if not response_text and ollama_model:
            global _ollama_offline_until
            if time.time() >= _ollama_offline_until:
                models = [m.strip() for m in ollama_model.split(",") if m.strip()]
                import requests as _req
                for model in models:
                    try:
                        resp = _req.post(
                            "http://localhost:11434/api/generate",
                            json={"model": model, "prompt": prompt, "stream": False},
                            timeout=(1.5, 10.0),
                        )
                        if resp.status_code == 404:
                            logger.debug("Ollama model '%s' not found for memory extraction.", model)
                            continue
                        resp.raise_for_status()
                        response_text = resp.json().get("response", "").strip()
                        break
                    except (_req.exceptions.ConnectionError, _req.exceptions.Timeout) as exc:
                        _ollama_offline_until = time.time() + 120.0
                        logger.debug("Ollama is offline or unreachable: %s. Pausing memory extraction checks for 2 minutes.", exc)
                        break
                    except Exception as exc:
                        logger.debug("Ollama model '%s' memory extraction failed: %s", model, exc)
    except Exception as exc:
        logger.debug("Implicit memory extraction failed: %s", exc)
        return

    if not response_text or response_text == "NONE":
        return

    if response_text.startswith("FACT:"):
        fact = response_text[5:].strip()
        add_memory(fact)
    elif response_text.startswith("TASK:"):
        task = response_text[5:].strip()
        try:
            import todo
            todo.add_todo(task)
        except Exception as e:
            logger.debug("Failed to auto-add task: %s", e)


def get_memory_summary(max_items: int = 5) -> str:
    """Return a short, prompt-ready summary of the most recent memories.

    Used by proactive chatter and any context builder that needs a quick
    snapshot of what Shin knows about MJ without loading the full list.

    Parameters
    ----------
    max_items : int
        Maximum number of recent memories to include (default 5).

    Returns
    -------
    str
        Multi-line string ready for injection into an AI prompt, or empty
        string if no memories are stored.
    """
    memories = load_memories()
    if not memories:
        return ""
    recent = memories[-max_items:]
    lines = [f"  - {m['content']}" for m in recent]
    return "Things Shin knows about MJ:\n" + "\n".join(lines)
