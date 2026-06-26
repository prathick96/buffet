"""
venture/tests/test_quant.py — statistical Quant voice.
Run:  python venture/tests/test_quant.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from contracts import MarketSnapshot  # noqa: E402
from engines.quant import QuantEngine  # noqa: E402


def _snap(prices):
    return MarketSnapshot(symbol="X", price=prices[-1], history=prices)


def test_uptrend_is_not_bearish():
    prices = [round(100 * (1.008 ** i), 4) for i in range(40)]
    v = QuantEngine().run(_snap(prices))
    assert v["score"] > 0 and v["action"] in ("BUY", "HOLD")
    print(f"PASS uptrend_is_not_bearish ({v['action']}, score={v['score']})")


def test_downtrend_is_not_bullish():
    prices = [round(100 * (0.99 ** i), 4) for i in range(40)]
    v = QuantEngine().run(_snap(prices))
    assert v["score"] < 0 and v["action"] in ("SELL", "HOLD")
    print(f"PASS downtrend_is_not_bullish ({v['action']}, score={v['score']})")


def test_insufficient_history_holds():
    v = QuantEngine().run(_snap([100, 101, 102]))
    assert v["action"] == "HOLD" and v["score"] == 0.0
    print("PASS insufficient_history_holds")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} QUANT TESTS PASSED")
