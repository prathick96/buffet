"""
venture/news/providers.py — live news for the Scout (the information edge).

A NewsProvider is any callable(symbol) -> [{"title","summary","source","url"}].
Plug it into a DataProvider: `CCXTDataProvider(sym, news_provider=RSSNewsProvider())`.

  RSSNewsProvider   — LIVE, keyless, stdlib only (Cointelegraph/CoinDesk/Yahoo).
  NewsAPIProvider   — optional, needs a newsapi.org key.
  Crawl4AINewsProvider / FirecrawlNewsProvider — deeper scraping, wired later
                       (crawl4ai = Apache-2 EMBED; Firecrawl = AGPL -> API only).

Results are TTL-cached per symbol so a 200-bar backtest fetches once, not 200x.

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Protocol, runtime_checkable

_UA = {"User-Agent": "Mozilla/5.0 (venture-scout)"}
_TAG = re.compile(r"<[^>]+>")


@runtime_checkable
class NewsProvider(Protocol):
    def __call__(self, symbol: str) -> list: ...


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return _TAG.sub("", text).replace("&nbsp;", " ").replace("&amp;", "&").strip()


def parse_rss(xml_bytes: bytes, source: str = "") -> list:
    """Parse RSS 2.0 bytes into our news dict list (deterministic, unit-testable)."""
    root = ET.fromstring(xml_bytes)
    out = []
    for item in root.iter("item"):
        title = _clean(item.findtext("title"))
        if not title:
            continue
        out.append({
            "title": title,
            "summary": _clean(item.findtext("description"))[:300],
            "source": source,
            "url": (item.findtext("link") or "").strip(),
        })
    return out


class _TTLCache:
    def __init__(self, ttl: int):
        self.ttl = ttl
        self._d: dict = {}

    def get(self, key):
        v = self._d.get(key)
        if v and (time.time() - v[0]) < self.ttl:
            return v[1]
        return None

    def put(self, key, value):
        self._d[key] = (time.time(), value)


class RSSNewsProvider:
    CRYPTO_FEEDS = [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
    ]
    EQUITY_TMPL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    INDIA_FEEDS = [   # BSE/NSE (.BO/.NS) symbols route here
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "https://www.livemint.com/rss/markets",
    ]

    def __init__(self, crypto_feeds: list | None = None, equity_tmpl: str | None = None,
                 india_feeds: list | None = None,
                 max_items: int = 8, timeout: int = 12, ttl: int = 300):
        self.crypto_feeds = crypto_feeds or self.CRYPTO_FEEDS
        self.equity_tmpl = equity_tmpl or self.EQUITY_TMPL
        self.india_feeds = india_feeds or self.INDIA_FEEDS
        self.max_items = max_items
        self.timeout = timeout
        self._cache = _TTLCache(ttl)

    def __call__(self, symbol: str) -> list:
        cached = self._cache.get(symbol)
        if cached is not None:
            return cached
        items, seen = [], set()
        for url in self._feeds_for(symbol):
            for it in self._fetch(url):
                if it["title"] not in seen:
                    seen.add(it["title"])
                    items.append(it)
        items = items[: self.max_items]
        self._cache.put(symbol, items)
        return items

    def _feeds_for(self, symbol: str) -> list:
        s = symbol.upper()
        if "/" in s:                                       # crypto pair (BTC/USDT)
            return self.crypto_feeds
        if s.endswith(".BO") or s.endswith(".NS"):         # BSE / NSE (India)
            return self.india_feeds
        return [self.equity_tmpl.format(ticker=symbol)]    # US equity ticker (AAPL)

    @staticmethod
    def _host(url: str) -> str:
        m = re.search(r"https?://([^/]+)/", url)
        return m.group(1) if m else url

    def _fetch(self, url: str) -> list:
        try:
            req = urllib.request.Request(url, headers=_UA)
            data = urllib.request.urlopen(req, timeout=self.timeout).read()
            return parse_rss(data, source=self._host(url))
        except Exception:
            return []


class NewsAPIProvider:
    """Optional newsapi.org provider (needs a key). RSS is the keyless default."""

    def __init__(self, api_key: str, max_items: int = 8, timeout: int = 12, ttl: int = 300):
        self.api_key = api_key
        self.max_items = max_items
        self.timeout = timeout
        self._cache = _TTLCache(ttl)

    def __call__(self, symbol: str) -> list:
        import json
        cached = self._cache.get(symbol)
        if cached is not None:
            return cached
        q = symbol.split("/")[0]
        url = (f"https://newsapi.org/v2/everything?q={q}&sortBy=publishedAt"
               f"&pageSize={self.max_items}&language=en&apiKey={self.api_key}")
        items = []
        try:
            req = urllib.request.Request(url, headers=_UA)
            data = urllib.request.urlopen(req, timeout=self.timeout).read()
            for a in json.loads(data).get("articles", []):
                items.append({
                    "title": a.get("title", ""),
                    "summary": (a.get("description") or "")[:300],
                    "source": (a.get("source") or {}).get("name", ""),
                    "url": a.get("url", ""),
                })
        except Exception:
            items = []
        self._cache.put(symbol, items)
        return items


class Crawl4AINewsProvider:
    """Deep web scraping via crawl4ai (Apache-2, EMBED-safe). `pip install crawl4ai`."""
    def __init__(self, *a, **k):
        raise NotImplementedError("Wire crawl4ai (Apache-2) when deep scraping is needed.")


class FirecrawlNewsProvider:
    """Firecrawl HOSTED API client (engine is AGPL -> API only). Needs FIRECRAWL_API_KEY."""
    def __init__(self, *a, **k):
        raise NotImplementedError("Use the Firecrawl hosted API (firecrawl-py) as a client.")
