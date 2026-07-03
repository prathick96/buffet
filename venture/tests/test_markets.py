"""
venture/tests/test_markets.py — BSE/NSE/US/crypto symbol registry.
Run:  python venture/tests/test_markets.py
"""
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from markets.registry import format_money, is_market_open, resolve  # noqa: E402
from markets.watchlist import DEFAULT_WATCHLISTS, all_symbols  # noqa: E402


def test_resolve_routing():
    assert resolve("BTC/USDT").asset_class == "crypto"
    assert resolve("AAPL").exchange == "NASDAQ" and resolve("AAPL").currency == "USD"
    r = resolve("RELIANCE.BO")
    assert r.exchange == "BSE" and r.currency == "INR" and r.provider == "yfinance"
    n = resolve("TCS.NS")
    assert n.exchange == "NSE" and n.currency_symbol == "₹"
    print("PASS resolve_routing")


def test_crypto_always_open():
    assert is_market_open(resolve("ETH/USDT"))
    print("PASS crypto_always_open")


def test_india_market_hours():
    mon10 = datetime(2026, 6, 29, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)
    sun10 = datetime(2026, 6, 28, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)
    pre = datetime(2026, 6, 29, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)
    assert is_market_open(resolve("TCS.NS"), mon10)         # Monday 10:00 IST -> open
    assert not is_market_open(resolve("TCS.NS"), sun10)     # Sunday -> closed
    assert not is_market_open(resolve("RELIANCE.BO"), pre)  # 08:00 IST -> before open
    print("PASS india_market_hours")


def test_format_and_watchlist():
    assert format_money(1318.25, resolve("RELIANCE.BO")).startswith("₹")
    assert "RELIANCE.BO" in DEFAULT_WATCHLISTS["india"] and len(all_symbols()) >= 10
    print("PASS format_and_watchlist")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} MARKETS TESTS PASSED")
