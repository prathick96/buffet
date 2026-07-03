"""
venture/markets/registry.py — first-class symbol metadata (crypto + US + BSE/NSE).

`resolve(symbol)` returns a Market describing exchange, asset class, currency,
which DataProvider to use, and trading hours — so the rest of the system treats
a BSE stock (₹, 09:15-15:30 IST) as a first-class citizen alongside crypto/US.

  BTC/USDT     -> crypto, binance, USD, ccxt, 24/7
  AAPL         -> equity, NASDAQ, USD, yfinance, 09:30-16:00 ET
  RELIANCE.BO  -> equity, BSE,    INR, yfinance, 09:15-15:30 IST
  TCS.NS       -> equity, NSE,    INR, yfinance, 09:15-15:30 IST

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

_CURRENCY_SYMBOL = {"USD": "$", "INR": "₹"}


@dataclass(frozen=True)
class Market:
    symbol: str
    asset_class: str          # "crypto" | "equity"
    exchange: str             # "binance" | "NASDAQ" | "BSE" | "NSE"
    currency: str             # "USD" | "INR"
    provider: str             # "ccxt" | "yfinance"
    tz: str | None            # IANA tz for equities, None for 24/7 crypto
    open_t: tuple | None      # (hour, minute)
    close_t: tuple | None

    @property
    def currency_symbol(self) -> str:
        return _CURRENCY_SYMBOL.get(self.currency, "")


def resolve(symbol: str) -> Market:
    s = symbol.upper()
    if "/" in s:                                   # crypto pair
        return Market(symbol, "crypto", "binance", "USD", "ccxt", None, None, None)
    if s.endswith(".BO"):                          # Bombay Stock Exchange
        return Market(symbol, "equity", "BSE", "INR", "yfinance",
                      "Asia/Kolkata", (9, 15), (15, 30))
    if s.endswith(".NS"):                          # National Stock Exchange (India)
        return Market(symbol, "equity", "NSE", "INR", "yfinance",
                      "Asia/Kolkata", (9, 15), (15, 30))
    return Market(symbol, "equity", "NASDAQ", "USD", "yfinance",   # default: US equity
                  "America/New_York", (9, 30), (16, 0))


def is_market_open(market: Market, now: datetime | None = None) -> bool:
    """True if the market is currently open (crypto is always open)."""
    if market.asset_class == "crypto":
        return True
    from zoneinfo import ZoneInfo
    now = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(market.tz))
    if now.weekday() >= 5:                          # Sat/Sun
        return False
    mins = now.hour * 60 + now.minute
    return market.open_t[0] * 60 + market.open_t[1] <= mins <= \
        market.close_t[0] * 60 + market.close_t[1]


def format_money(amount: float, market: Market) -> str:
    return f"{market.currency_symbol}{amount:,.2f}"
