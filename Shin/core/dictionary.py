"""
dictionary.py — Word lookup for Shin Voice Assistant
=====================================================
Uses the free DictionaryAPI.dev REST API (no API key required).
Supports define, synonyms, and antonyms modes.
Falls back gracefully when offline.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("shin.dictionary")

_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"


def lookup_word(word: str, mode: str = "define") -> str:
    """
    Look up a word using the Free Dictionary API.

    Parameters
    ----------
    word : the word to look up
    mode : "define" | "synonyms" | "antonyms"

    Returns
    -------
    A concise spoken string ready for TTS.
    """
    import requests

    word = word.strip().lower()
    if not word:
        return "Please tell me which word you'd like me to look up."

    try:
        resp = requests.get(_API_URL.format(word=word), timeout=6)

        if resp.status_code == 404:
            return (
                f"I couldn't find '{word}' in the dictionary. "
                "It might be a proper noun or a very uncommon word."
            )
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, list) or not data:
            return f"No results found for '{word}'."

        entry = data[0]
        meanings = entry.get("meanings", [])
        if not meanings:
            return f"No information found for '{word}'."

        # ── Define ────────────────────────────────────────────────────────────
        if mode == "define":
            first = meanings[0]
            part_of_speech = first.get("partOfSpeech", "")
            defs = first.get("definitions", [])
            if not defs:
                return f"No definition found for '{word}'."

            defn_text = defs[0].get("definition", "")
            example   = defs[0].get("example", "")
            phonetic  = entry.get("phonetic", "")

            parts = [word.capitalize()]
            if part_of_speech:
                parts[0] += f", {part_of_speech}"
            if phonetic:
                parts.append(f"Pronounced: {phonetic}.")
            parts.append(defn_text)
            if example:
                parts.append(f"Example: {example}")

            # Add a second meaning if short enough for variety
            if len(meanings) > 1:
                second_defs = meanings[1].get("definitions", [])
                if second_defs:
                    second_pos  = meanings[1].get("partOfSpeech", "")
                    second_defn = second_defs[0].get("definition", "")
                    if second_defn:
                        pos_label = f"As a {second_pos}: " if second_pos else "Also: "
                        parts.append(pos_label + second_defn)

            return " ".join(parts)

        # ── Synonyms ──────────────────────────────────────────────────────────
        if mode == "synonyms":
            synonyms: list[str] = []
            for meaning in meanings:
                synonyms.extend(meaning.get("synonyms", []))
                for d in meaning.get("definitions", []):
                    synonyms.extend(d.get("synonyms", []))
            # Deduplicate while preserving order, cap at 8
            seen: set[str] = set()
            unique = [s for s in synonyms if not (s in seen or seen.add(s))][:8]
            if not unique:
                return (
                    f"I couldn't find synonyms for '{word}' in the dictionary. "
                    "Try asking me to web search for it."
                )
            return f"Synonyms for '{word}': {', '.join(unique)}."

        # ── Antonyms ──────────────────────────────────────────────────────────
        if mode == "antonyms":
            antonyms: list[str] = []
            for meaning in meanings:
                antonyms.extend(meaning.get("antonyms", []))
                for d in meaning.get("definitions", []):
                    antonyms.extend(d.get("antonyms", []))
            seen2: set[str] = set()
            unique2 = [a for a in antonyms if not (a in seen2 or seen2.add(a))][:8]
            if not unique2:
                return (
                    f"I couldn't find antonyms for '{word}' in the dictionary."
                )
            return f"Antonyms of '{word}': {', '.join(unique2)}."

        return f"Unknown lookup mode: {mode}"

    except requests.exceptions.Timeout:
        logger.warning("Dictionary lookup timed out for %r", word)
        return "Dictionary lookup timed out. Please check your internet connection."
    except Exception as exc:
        logger.warning("Dictionary lookup failed for %r: %s", word, exc)
        return f"Sorry, I couldn't look up '{word}' right now."
