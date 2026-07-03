"""
venture/markets/watchlist.py — default watchlists per market.
Edit freely; the engines accept any symbol the registry can resolve.
"""
from __future__ import annotations

DEFAULT_WATCHLISTS = {
    "crypto": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
    "us":     ["AAPL", "NVDA", "MSFT", "TSLA"],
    "india":  ["RELIANCE.BO", "TCS.NS", "INFY.NS", "HDFCBANK.NS"],
}


def all_symbols() -> list:
    return [s for group in DEFAULT_WATCHLISTS.values() for s in group]
