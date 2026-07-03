"""
venture/tests/test_notify.py — Telegram notifier (offline; no network).
Run:  python venture/tests/test_notify.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notify.telegram import TelegramNotifier, format_cycle_summary  # noqa: E402


def test_not_configured_is_noop():
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        os.environ.pop(k, None)
    n = TelegramNotifier(token=None, chat_id=None)
    assert not n.is_configured()
    assert n.send("hello") is False           # no-op, never raises
    print("PASS not_configured_is_noop")


def test_configured_flag():
    assert TelegramNotifier(token="abc", chat_id="123").is_configured()
    print("PASS configured_flag")


def test_format_summary():
    rows = [{"symbol": "BTC/USDT", "action": "BUY", "conviction": 0.6, "sentiment": "BULLISH"},
            {"symbol": "AAPL", "action": "HOLD", "conviction": 0.1, "sentiment": "NEUTRAL"}]
    txt = format_cycle_summary(rows, footer="equity $50.00")
    assert "BTC/USDT" in txt and "AAPL" in txt and "equity $50.00" in txt
    print("PASS format_summary")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} NOTIFY TESTS PASSED")
