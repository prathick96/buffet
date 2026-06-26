"""
venture/engines/scout.py — the Scout (intelligence desk).

Single job: gather the latest state of a symbol (price, history, indicators,
news), ingest the news into the shared KnowledgeStore (RAG), and attach the
retrieved context. Relentless + fast: catch the drift before it disappears.

Phase 1 swaps MockDataProvider -> ccxt/yfinance and adds crawl4ai / Firecrawl
API / NewsAPI / OpenBB feeds behind the same DataProvider interface.
"""
from __future__ import annotations

from statistics import mean

from contracts import MarketSnapshot
from engines.base import Engine


class ScoutEngine(Engine):
    name = "scout"

    def __init__(self, data_provider, knowledge_store, sma_window: int = 10):
        self.data = data_provider
        self.kb = knowledge_store
        self.window = sma_window

    def run(self, symbol: str) -> MarketSnapshot:
        price = self.data.current_price(symbol)
        history = self.data.history(symbol)
        news = self.data.news(symbol)

        # RAG ingest: every headline becomes retrievable context for the Analyst.
        for n in news:
            text = f"{n.get('title', '')} {n.get('summary', '')}".strip()
            self.kb.ingest(text, {"symbol": symbol, "source": n.get("source", "")})

        indicators = self._indicators(history, price)
        trend = "uptrend bullish" if indicators.get("above_sma") else "downtrend bearish"
        retrieved = self.kb.retrieve(f"{symbol} {trend}", k=3)

        return MarketSnapshot(
            symbol=symbol, price=price, history=history,
            indicators=indicators, news=news, retrieved_context=retrieved,
        )

    def _indicators(self, history: list, price: float) -> dict:
        if len(history) < self.window:
            return {"sma": None, "above_sma": False, "momentum": 0.0}
        sma = mean(history[-self.window:])
        momentum = (price - sma) / sma if sma else 0.0
        return {"sma": sma, "above_sma": price > sma, "momentum": momentum}
