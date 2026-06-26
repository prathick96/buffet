"""
venture/data/providers.py — data sources feeding the Scout.

`DataProvider` is the interface; every provider replays a history window
bar-by-bar so the same engine loop works for backtest AND live polling (in live
use, refresh + advance to the latest bar each cycle).

  MockDataProvider      — deterministic replay (tests/backtests, offline)
  CCXTDataProvider      — real crypto OHLCV via ccxt (e.g. Binance)
  YFinanceDataProvider  — real equity OHLCV via yfinance

All ignore the `symbol` argument on the per-bar methods (single-symbol
instances) but accept it so they're drop-in interchangeable.

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class DataProvider(Protocol):
    def current_price(self, symbol: str) -> float: ...
    def history(self, symbol: str) -> list: ...
    def news(self, symbol: str) -> list: ...
    def has_next(self) -> bool: ...
    def advance(self) -> None: ...


class _ReplayBase:
    """Shared cursor logic for providers that replay a fixed list of closes."""

    def __init__(self, closes: list, news_provider=None):
        self._closes = list(closes)
        self._news_provider = news_provider
        self.cursor = 0
        if len(self._closes) < 2:
            raise ValueError("need at least 2 bars of data")

    def current_price(self, symbol: str) -> float:
        return self._closes[self.cursor]

    def history(self, symbol: str) -> list:
        return self._closes[: self.cursor + 1]

    def news(self, symbol: str) -> list:
        return self._news_provider(symbol) if self._news_provider else []

    def has_next(self) -> bool:
        return self.cursor < len(self._closes) - 1

    def advance(self) -> None:
        self.cursor += 1

    def __len__(self) -> int:
        return len(self._closes)


class MockDataProvider:
    """Deterministic replay of preloaded series — the test/backtest data source."""

    def __init__(self, series: dict, news: dict | None = None):
        self.series = {s: list(v) for s, v in series.items()}
        self._news = news or {}
        self.cursor = 0
        self._n = min((len(v) for v in self.series.values()), default=0)

    def current_price(self, symbol: str) -> float:
        return self.series[symbol][self.cursor]

    def history(self, symbol: str) -> list:
        return self.series[symbol][: self.cursor + 1]

    def news(self, symbol: str) -> list:
        items = self._news.get(symbol, [])
        if items and isinstance(items[0], list):
            return items[self.cursor] if self.cursor < len(items) else []
        return items

    def has_next(self) -> bool:
        return self.cursor < self._n - 1

    def advance(self) -> None:
        self.cursor += 1

    def __len__(self) -> int:
        return self._n


class CCXTDataProvider(_ReplayBase):
    """Real crypto OHLCV via ccxt. Public data — no API key needed."""

    def __init__(self, symbol: str, exchange: str = "binance",
                 timeframe: str = "1h", limit: int = 200, news_provider=None):
        import ccxt  # lazy import so the package isn't required unless used
        ex = getattr(ccxt, exchange)({"enableRateLimit": True})
        ohlcv = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not ohlcv:
            raise RuntimeError(f"no OHLCV returned for {symbol} on {exchange}")
        self.symbol = symbol
        super().__init__([bar[4] for bar in ohlcv], news_provider)  # bar[4] = close


class YFinanceDataProvider(_ReplayBase):
    """Real equity/ETF OHLCV via yfinance."""

    def __init__(self, symbol: str, period: str = "6mo",
                 interval: str = "1d", news_provider=None):
        import yfinance as yf  # lazy import
        df = yf.Ticker(symbol).history(period=period, interval=interval)
        if df is None or df.empty or "Close" not in df:
            raise RuntimeError(f"no data returned for {symbol} from yfinance")
        self.symbol = symbol
        closes = [float(x) for x in df["Close"].tolist() if x == x]  # drop NaN
        super().__init__(closes, news_provider)
