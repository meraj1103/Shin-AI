"""
news.py — Country & World News integration for Shin Voice Assistant
====================================================================
Fetches top headlines for India, America, Russia, or global/topic news.
Uses World News API with a reliable Google News RSS fallback (zero API key needed).
"""

from __future__ import annotations

import logging
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.worldnewsapi.com"

# Country name mapping -> ISO code
_COUNTRY_MAP = {
    "india": "in",
    "bharat": "in",
    "indian": "in",
    "in": "in",
    "america": "us",
    "usa": "us",
    "us": "us",
    "united states": "us",
    "american": "us",
    "russia": "ru",
    "russian": "ru",
    "ru": "ru",
}

_COUNTRY_LABELS = {
    "in": "India",
    "us": "America",
    "ru": "Russia",
}


def resolve_country_code(country_str: Optional[str]) -> Optional[str]:
    """Resolve a country name or alias to an ISO 2-letter country code."""
    if not country_str:
        return None
    c_clean = country_str.lower().strip()
    return _COUNTRY_MAP.get(c_clean) or (c_clean if len(c_clean) == 2 else None)


def get_top_headlines(country: Optional[str] = None, count: int = 6) -> list[dict]:
    """
    Fetch top news headlines.
    If country is provided ('in', 'us', 'ru' or name), fetches for that country.
    If country is None, fetches top headlines from India, America, and Russia combined.
    """
    c_code = resolve_country_code(country)
    if c_code:
        return _fetch_country_headlines(c_code, count=count)
    else:
        # Fetch combined headlines for India, America, and Russia
        return get_multi_country_headlines(["in", "us", "ru"], per_country=2)


def get_multi_country_headlines(countries: list[str] = None, per_country: int = 2) -> list[dict]:
    """
    Fetch headlines from multiple countries (India, America, Russia)
    and tag each article with its country code.
    """
    if countries is None:
        countries = ["in", "us", "ru"]
    all_articles = []
    for c in countries:
        c_code = resolve_country_code(c) or c
        arts = _fetch_country_headlines(c_code, count=per_country)
        all_articles.extend(arts)
    return all_articles


def _fetch_country_headlines(country_code: str, count: int = 5) -> list[dict]:
    """Fetch headlines for a single country code (in, us, ru)."""
    api_key = os.getenv("WORLD_NEWS_API_KEY", "").strip()
    articles = []

    # 1. Try World News API
    if api_key:
        try:
            import requests

            resp = requests.get(
                f"{_BASE_URL}/top-news",
                params={
                    "source-country": country_code,
                    "language":        "en",
                    "api-key":         api_key,
                },
                timeout=6,
            )
            if resp.status_code == 200:
                data = resp.json()
                for group in data.get("top_news", []):
                    for article in group.get("news", []):
                        title = article.get("title")
                        if title:
                            articles.append({
                                "title":   title,
                                "text":    article.get("text", ""),
                                "country": country_code,
                            })
                        if len(articles) >= count:
                            break
                    if len(articles) >= count:
                        break
        except Exception as exc:
            logger.debug("World News API fetch failed for %s: %s", country_code, exc)

    # 2. Fallback to Google News RSS
    if not articles:
        articles = _fetch_google_news_rss(country_code=country_code, count=count)

    return articles[:count]


def search_news(topic: str, country: Optional[str] = None, count: int = 3) -> list[dict]:
    """
    Search for news articles about a specific topic, optionally filtered by country.
    """
    api_key = os.getenv("WORLD_NEWS_API_KEY", "").strip()
    c_code = resolve_country_code(country)
    articles = []

    if api_key:
        try:
            import requests

            params = {
                "text":     topic,
                "language": "en",
                "number":   count,
                "api-key":  api_key,
            }
            if c_code:
                params["source-countries"] = c_code

            resp = requests.get(f"{_BASE_URL}/search-news", params=params, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("news", []):
                    if item.get("title"):
                        articles.append({
                            "title":   item.get("title"),
                            "text":    item.get("text", ""),
                            "country": c_code or "world",
                        })
        except Exception as exc:
            logger.debug("World News API search failed for %r: %s", topic, exc)

    if not articles:
        articles = _fetch_google_news_rss(topic=topic, country_code=c_code, count=count)

    return articles[:count]


def _fetch_google_news_rss(topic: Optional[str] = None, country_code: Optional[str] = None, count: int = 5) -> list[dict]:
    """Fetch news from Google News RSS feeds without needing any API key."""
    if topic:
        q = f"{topic} {country_code.upper()}" if country_code else topic
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-US&gl=US&ceid=US:en"
    elif country_code == "in":
        url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
    elif country_code == "us":
        url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
    elif country_code == "ru":
        url = "https://news.google.com/rss/search?q=Russia&hl=en-US&gl=US&ceid=US:en"
    else:
        url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        articles = []
        for item in root.findall(".//item"):
            title = item.find("title")
            if title is not None and title.text:
                # Strip source suffix like '- The Hindu' or '- BBC News'
                clean_title = re.sub(r"\s*-\s*[^-]+$", "", title.text).strip()
                articles.append({
                    "title":   clean_title or title.text,
                    "text":    "",
                    "country": country_code or "world",
                })
            if len(articles) >= count:
                break
        return articles
    except Exception as exc:
        logger.warning("Google News RSS fallback failed for %s: %s", country_code, exc)
        return []


def format_headlines_for_speech(articles: list[dict], max_articles: int = 6) -> str:
    """
    Convert a list of articles into a clean spoken summary.
    Groups articles by country (India, America, Russia) when multi-country news is fetched.
    """
    if not articles:
        return "I couldn't fetch any news right now."

    # Group by country
    country_groups: dict[str, list[str]] = {}
    for art in articles[:max_articles]:
        c = art.get("country", "")
        title = art.get("title", "").strip()
        if not title:
            continue
        if len(title) > 110:
            title = title[:110].rsplit(" ", 1)[0] + "…"
        country_groups.setdefault(c, []).append(title)

    if not country_groups:
        return "No news headlines were found."

    # Single country or general topic
    if len(country_groups) == 1:
        c_code = list(country_groups.keys())[0]
        c_label = _COUNTRY_LABELS.get(c_code, "")
        titles = list(country_groups.values())[0]
        if c_label:
            header = f"Here are the top stories from {c_label}: "
        else:
            header = f"Here are the top news stories: "
        story_list = " ".join(f"Story {i+1}: {t}." for i, t in enumerate(titles))
        return header + story_list

    # Multi-country news (India, America, Russia)
    speech_parts = ["Here are top headlines from India, America, and Russia."]
    for c_code, label in [("in", "India"), ("us", "America"), ("ru", "Russia")]:
        titles = country_groups.get(c_code, [])
        if titles:
            part = f" From {label}: " + " ".join(f"{t}." for t in titles)
            speech_parts.append(part)

    return " ".join(speech_parts)
