"""
live_search.py — Real-Time Internet Answers for Shin Voice Assistant
=====================================================================
Fetches live data from the internet and returns a spoken-ready string.
No browser is opened. No API keys required for most features.
"""

from __future__ import annotations
import logging
import re

logger = logging.getLogger(__name__)

_TIMEOUT = 8
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ======= Wikipedia (Using official wikipedia & wikipediaapi libraries) =======

def _clean_wiki_text(text: str, max_chars: int = 450) -> str:
    """Strip markdown headers like == Background == and clean whitespace for TTS."""
    if not text:
        return ""
    text = re.sub(r"==+[^=]+==+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(".", 1)[0] + "."
    return text


def wikipedia_summary(query: str, sentences: int = 3, lang: str = "en") -> str:
    """Return a short Wikipedia summary using wikipedia-api with wikipedia library fallback."""
    query = query.strip()
    if not query:
        return ""

    # Try modern WikipediaAPI first
    try:
        import wikipediaapi
        wiki_api = wikipediaapi.Wikipedia(
            user_agent="ShinVoiceAssistant/1.0 (https://github.com/shin-assistant)",
            language=lang
        )
        page = wiki_api.page(query)
        if page.exists() and page.summary:
            return _clean_wiki_text(page.summary)
    except Exception as exc:
        logger.debug("wikipediaapi primary lookup failed for %r: %s", query, exc)

    # Fallback to wikipedia package search
    try:
        import wikipedia as _wiki
        _wiki.set_lang(lang)
        results = _wiki.search(query, results=3)
        if not results:
            return ""
        for title in results:
            try:
                summary = _wiki.summary(title, sentences=sentences, auto_suggest=False)
                if summary:
                    return _clean_wiki_text(summary)
            except _wiki.DisambiguationError as e:
                if e.options:
                    try:
                        summary = _wiki.summary(e.options[0], sentences=sentences, auto_suggest=False)
                        if summary:
                            return _clean_wiki_text(summary)
                    except Exception:
                        continue
            except Exception:
                continue
        return ""
    except Exception as exc:
        logger.warning("Wikipedia lookup failed for %r: %s", query, exc)
        return ""



# ======= Stock / Share Market (Yahoo Finance — no API key required) =======

_STOCK_ALIASES: dict[str, str] = {
    # Indian indices
    "nifty": "^NSEI", "nifty 50": "^NSEI", "nse": "^NSEI",
    "sensex": "^BSESN", "bse": "^BSESN", "bse sensex": "^BSESN",
    "nifty bank": "^NSEBANK", "bank nifty": "^NSEBANK",
    "nifty it": "^CNXIT", "nifty midcap": "^NSEMDCP50",
    # Popular Indian stocks
    "reliance": "RELIANCE.NS", "tcs": "TCS.NS",
    "infosys": "INFY.NS", "infy": "INFY.NS",
    "hdfc": "HDFCBANK.NS", "hdfc bank": "HDFCBANK.NS",
    "icici": "ICICIBANK.NS", "icici bank": "ICICIBANK.NS",
    "wipro": "WIPRO.NS", "sbi": "SBIN.NS",
    "bajaj": "BAJFINANCE.NS", "bajaj finance": "BAJFINANCE.NS",
    "adani": "ADANIENT.NS",
    "tatamotors": "TATAMOTORS.NS", "tata motors": "TATAMOTORS.NS",
    "hcl": "HCLTECH.NS", "hcl tech": "HCLTECH.NS",
    "maruti": "MARUTI.NS", "airtel": "BHARTIARTL.NS",
    "bharti airtel": "BHARTIARTL.NS", "titan": "TITAN.NS",
    "asian paints": "ASIANPAINT.NS", "ultratech": "ULTRACEMCO.NS",
    "sun pharma": "SUNPHARMA.NS",
    # Global stocks
    "apple": "AAPL", "microsoft": "MSFT",
    "google": "GOOGL", "alphabet": "GOOGL",
    "amazon": "AMZN", "tesla": "TSLA",
    "nvidia": "NVDA", "meta": "META", "facebook": "META",
}


def _resolve_ticker(query: str) -> str:
    """Map a spoken name to a Yahoo Finance ticker symbol."""
    q = query.lower().strip()
    if q in _STOCK_ALIASES:
        return _STOCK_ALIASES[q]
    try:
        from rapidfuzz import process as fz
        result = fz.extractOne(q, _STOCK_ALIASES.keys(), score_cutoff=75)
        if result:
            return _STOCK_ALIASES[result[0]]
    except Exception:
        pass
    if re.match(r"^[A-Z0-9\.\^]{1,15}$", query.upper()):
        return query.upper()
    return query.upper() + ".NS"


def stock_price(query: str) -> str:
    """Fetch current price of a stock or index via Yahoo Finance. No key needed."""
    ticker = _resolve_ticker(query)
    try:
        import requests
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT,
                            params={"interval": "1d", "range": "1d"})
        resp.raise_for_status()
        data = resp.json()
        meta = data["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        currency = meta.get("currency", "USD")
        if price is None:
            return ""
        change_str = ""
        if prev and price != prev:
            change = price - prev
            pct = (change / prev) * 100
            arrow = "up" if change >= 0 else "down"
            change_str = f", {arrow} {abs(pct):.2f}% today"
        cur_sym = {"INR": "Rs.", "USD": "$", "EUR": "EUR ", "GBP": "GBP "}.get(currency, currency + " ")
        display = query.title()
        return f"{display} is currently at {cur_sym}{price:,.2f}{change_str}."
    except Exception as exc:
        logger.warning("Stock price fetch failed for %r (%s): %s", query, ticker, exc)
        return ""


# ======= Crypto (CoinGecko — no API key required) =======

_CRYPTO_ALIASES: dict[str, str] = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana",
    "bnb": "binancecoin", "binance": "binancecoin",
    "xrp": "ripple", "ripple": "ripple",
    "cardano": "cardano", "ada": "cardano",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "polkadot": "polkadot", "dot": "polkadot",
    "shiba": "shiba-inu", "shiba inu": "shiba-inu", "shib": "shiba-inu",
    "litecoin": "litecoin", "ltc": "litecoin",
    "avalanche": "avalanche-2", "avax": "avalanche-2",
    "polygon": "matic-network", "matic": "matic-network",
    "chainlink": "chainlink", "link": "chainlink",
    "tron": "tron", "trx": "tron",
    "usdt": "tether", "tether": "tether",
    "usdc": "usd-coin", "pepe": "pepe",
}


def _resolve_coin(query: str) -> str:
    q = query.lower().strip()
    if q in _CRYPTO_ALIASES:
        return _CRYPTO_ALIASES[q]
    try:
        from rapidfuzz import process as fz
        result = fz.extractOne(q, _CRYPTO_ALIASES.keys(), score_cutoff=70)
        if result:
            return _CRYPTO_ALIASES[result[0]]
    except Exception:
        pass
    return q.replace(" ", "-")


def crypto_price(query: str) -> str:
    """Fetch current crypto price in INR and USD from CoinGecko. No key needed."""
    coin_id = _resolve_coin(query)
    try:
        import requests
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coin_id, "vs_currencies": "inr,usd", "include_24hr_change": "true"},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if coin_id not in data:
            return ""
        info = data[coin_id]
        price_inr = info.get("inr")
        price_usd = info.get("usd")
        change_24h = info.get("inr_24h_change")
        display = query.title()
        parts = []
        if price_inr:
            parts.append(f"Rs.{price_inr:,.2f}")
        if price_usd:
            parts.append(f"${price_usd:,.2f}")
        price_str = " or ".join(parts) if parts else "unavailable"
        change_str = ""
        if change_24h is not None:
            arrow = "up" if change_24h >= 0 else "down"
            change_str = f", {arrow} {abs(change_24h):.2f}% in the last 24 hours"
        return f"{display} is currently priced at {price_str}{change_str}."
    except Exception as exc:
        logger.warning("Crypto price fetch failed for %r (%s): %s", query, coin_id, exc)
        return ""


# ======= DuckDuckGo Instant Answers (no API key required) =======

def duckduckgo_instant(query: str) -> str:
    """Query DuckDuckGo Instant Answer API. Returns factual snippet or empty string."""
    try:
        import requests
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("AbstractText", "").strip()
        if text:
            if len(text) > 450:
                text = text[:450].rsplit(".", 1)[0] + "."
            return text
        answer = data.get("Answer", "").strip()
        if answer:
            return answer
        for item in data.get("RelatedTopics", []):
            snippet = item.get("Text", "").strip()
            if snippet:
                if len(snippet) > 300:
                    snippet = snippet[:300].rsplit(".", 1)[0] + "."
                return snippet
        return ""
    except Exception as exc:
        logger.warning("DuckDuckGo instant answer failed for %r: %s", query, exc)
        return ""


# ======= Web Scraping & Deep Web Search =======

def fetch_url_text(url: str, max_chars: int = 500) -> str:
    """Fetch text content from a public webpage URL using BeautifulSoup."""
    try:
        import requests
        from bs4 import BeautifulSoup
        if not url.startswith("http"):
            url = "https://" + url
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Remove script, style, nav, and footer tags
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
            
        text = soup.get_text(separator=" ", strip=True)
        # Clean up whitespace
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(".", 1)[0] + "."
        return text if text else "Could not extract readable text from that webpage."
    except Exception as exc:
        logger.warning("Webpage fetch failed for %r: %s", url, exc)
        return f"Sorry, I couldn't reach that webpage right now: {exc}"


def search_web_snippets(query: str) -> str:
    """Scrape DuckDuckGo HTML search results for real-time web answers."""
    try:
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        snippets = []
        for result in soup.select(".result__snippet")[:3]:
            text = result.get_text(strip=True)
            if text:
                snippets.append(text)
        if snippets:
            combined = " ".join(snippets)
            if len(combined) > 450:
                combined = combined[:450].rsplit(".", 1)[0] + "."
            return combined
        return ""
    except Exception as exc:
        logger.warning("DuckDuckGo HTML search failed for %r: %s", query, exc)
        return ""


def explain_internet_usage() -> str:
    """Return a natural explanation of how Shin accesses and uses the internet."""
    explanation = (
        "Here is how I use the internet to assist you:\n"
        "1. Real-Time Data: I query APIs like Yahoo Finance for stock prices, CoinGecko for crypto, OpenWeather for weather, and WorldNews for breaking headlines.\n"
        "2. Web Search & Wikipedia: I search DuckDuckGo and Wikipedia directly to answer factual questions without needing a browser.\n"
        "3. Live Voice & Audio: I stream speech recognition via Google ASR and synthesize natural voice using Microsoft Edge Neural TTS in real time.\n"
        "4. Knowledge & Learning: I fetch real-time updates and documentation to keep our answers accurate and helpful.\n"
        "5. Direct Navigation: When requested, I open web pages and YouTube videos right in your desktop browser."
    )
    return explanation


# ======= Master Dispatcher =======

def smart_answer(query: str, hint: str = "auto") -> str:
    """
    Try to answer *query* from the internet without opening a browser.

    hint: "stock" | "crypto" | "wiki" | "ddg" | "auto" (default)
    Returns spoken-ready answer string, or "" if nothing found.
    """
    query = query.strip()
    if not query:
        return ""
    if hint == "stock":
        return stock_price(query)
    if hint == "crypto":
        return crypto_price(query)
    if hint == "wiki":
        return wikipedia_summary(query)
    if hint == "ddg":
        return duckduckgo_instant(query)
    # Auto: DuckDuckGo Instant first, then DuckDuckGo Web Snippets, then Wikipedia
    answer = duckduckgo_instant(query)
    if answer:
        logger.debug("smart_answer: DuckDuckGo Instant hit for %r", query)
        return answer
    answer = search_web_snippets(query)
    if answer:
        logger.debug("smart_answer: DuckDuckGo Web Snippets hit for %r", query)
        return answer
    # Do not fallback to Wikipedia for news/breaking/current event queries
    is_news = any(k in query.lower() for k in ("news", "latest", "headlines", "today", "update", "current", "breaking"))
    if not is_news:
        answer = wikipedia_summary(query)
        if answer:
            logger.debug("smart_answer: Wikipedia hit for %r", query)
            return answer
    logger.debug("smart_answer: no result for %r", query)
    return ""

