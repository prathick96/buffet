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

import re
from typing import Protocol, runtime_checkable

_TF_UNIT_SEC = {"m": 60, "h": 3600, "d": 86400, "w": 604800}


def _timeframe_seconds(tf: str | None) -> float | None:
    """'1h'->3600, '1d'->86400, '15m'->900. None if unrecognized.

    Used so a matured prediction can be scored against a bar a *known* amount
    of time later, instead of comparing a price to itself.
    """
    if not tf:
        return None
    m = re.fullmatch(r"(\d+)\s*([mhdw])", tf.strip().lower())
    return int(m.group(1)) * _TF_UNIT_SEC[m.group(2)] if m else None


@runtime_checkable
class DataProvider(Protocol):
    def current_price(self, symbol: str) -> float: ...
    def history(self, symbol: str) -> list: ...
    def news(self, symbol: str) -> list: ...
    def has_next(self) -> bool: ...
    def advance(self) -> None: ...


class _ReplayBase:
    """Shared cursor logic for providers that replay a fixed list of closes."""

    def __init__(self, closes: list, news_provider=None, timestamps=None,
                 bar_seconds: float | None = None):
        self._closes = list(closes)
        self._timestamps = [float(t) for t in timestamps] if timestamps else []
        self.bar_seconds = bar_seconds
        self._news_provider = news_provider
        self.cursor = 0
        if len(self._closes) < 2:
            raise ValueError("need at least 2 bars of data")
        if self._timestamps and len(self._timestamps) != len(self._closes):
            raise ValueError("timestamps and closes length mismatch")

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

    # --- dated-scoring surface -------------------------------------------
    def bars(self, symbol: str | None = None) -> list:
        """All loaded (epoch_seconds_UTC, close) bars, ascending.

        Empty if this provider carries no timestamps — callers must handle that
        (never fall back to comparing a price to itself)."""
        return list(zip(self._timestamps, self._closes)) if self._timestamps else []

    def latest_bar_ts(self, symbol: str | None = None) -> float | None:
        """Epoch-seconds timestamp of the most recent bar (for capture/dedup)."""
        return self._timestamps[-1] if self._timestamps else None


class MockDataProvider:
    """Deterministic replay of preloaded series — the test/backtest data source."""

    def __init__(self, series: dict, news: dict | None = None, timestamps=None):
        self.series = {s: list(v) for s, v in series.items()}
        self._news = news or {}
        self._timestamps = list(timestamps) if timestamps else []
        self.bar_seconds = 86400.0
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

    def bars(self, symbol: str) -> list:
        closes = self.series[symbol][: self.cursor + 1]
        ts = (self._timestamps[: self.cursor + 1] if self._timestamps
              else [i * 86400.0 for i in range(len(closes))])  # synth daily stamps
        return list(zip(ts, closes))

    def latest_bar_ts(self, symbol: str) -> float | None:
        if self._timestamps:
            return self._timestamps[self.cursor]
        return float(self.cursor * 86400)


# Crypto venues tried in order. Binance is LAST because it geo-blocks some
# cloud runners (HTTP 451) — which is why crypto was silently dropping out of
# the forward test on GitHub Actions. Kraken/Coinbase/Bitstamp answer worldwide,
# so the 24/7 crypto feed (our cleanest scoring source) keeps flowing.
CRYPTO_EXCHANGES = ("kraken", "coinbase", "bitstamp", "binance")


class CCXTDataProvider(_ReplayBase):
    """Real crypto OHLCV via ccxt (public data, no API key).

    Resilient by design: tries several exchanges and symbol spellings until one
    returns bars, so a single venue being down or geo-blocked doesn't silently
    drop the symbol."""

    def __init__(self, symbol: str, exchange: str | None = None,
                 timeframe: str = "1h", limit: int = 200, news_provider=None,
                 exchanges=None):
        import ccxt  # lazy import so the package isn't required unless used
        venues = [exchange] if exchange else list(exchanges or CRYPTO_EXCHANGES)
        last_err = None
        for venue in venues:
            factory = getattr(ccxt, venue, None)
            if factory is None:
                continue
            for sym in self._symbol_variants(symbol):
                try:
                    ex = factory({"enableRateLimit": True})
                    ohlcv = ex.fetch_ohlcv(sym, timeframe=timeframe, limit=limit)
                except Exception as e:                 # geo-block / bad pair / venue down
                    last_err = e
                    continue
                if ohlcv:
                    self.symbol = symbol
                    self.source_exchange = venue
                    super().__init__(
                        [bar[4] for bar in ohlcv], news_provider,       # bar[4]=close
                        timestamps=[bar[0] / 1000.0 for bar in ohlcv],  # ms epoch UTC
                        bar_seconds=_timeframe_seconds(timeframe))
                    return
        raise RuntimeError(f"no OHLCV for {symbol} on any of {venues}: "
                           f"{type(last_err).__name__ if last_err else 'empty'}")

    @staticmethod
    def _symbol_variants(symbol: str):
        """Acceptable spellings across venues: exact, USDT->USD, BTC->XBT (Kraken)."""
        base, _, quote = symbol.partition("/")
        cands = [symbol]
        if quote == "USDT":
            cands.append(f"{base}/USD")            # USDT~USD, for USD-quoted venues
        if base == "BTC":
            cands.append(f"XBT/{quote}")           # Kraken lists bitcoin as XBT
            if quote == "USDT":
                cands.append("XBT/USD")
        seen = set()
        for c in cands:
            if c not in seen:
                seen.add(c)
                yield c


class YFinanceDataProvider(_ReplayBase):
    """Real equity/ETF OHLCV via yfinance."""

    def __init__(self, symbol: str, period: str = "6mo",
                 interval: str = "1d", news_provider=None):
        import yfinance as yf  # lazy import
        df = yf.Ticker(symbol).history(period=period, interval=interval)
        if df is None or df.empty or "Close" not in df:
            raise RuntimeError(f"no data returned for {symbol} from yfinance")
        self.symbol = symbol
        closes, stamps = [], []
        for idx, x in zip(df.index, df["Close"].tolist()):
            if x == x:                                   # drop NaN, keep bars aligned
                closes.append(float(x))
                stamps.append(idx.value / 1_000_000_000)  # pandas ns -> epoch s (UTC)
        super().__init__(closes, news_provider, timestamps=stamps,
                         bar_seconds=_timeframe_seconds(interval))
