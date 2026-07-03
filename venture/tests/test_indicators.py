"""
venture/tests/test_indicators.py — ported technical indicators.
Run:  python venture/tests/test_indicators.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd  # noqa: E402
from features.indicators import add_indicators, rsi  # noqa: E402


def test_add_indicators_columns_and_ranges():
    n = 60
    close = pd.Series([100 * (1.002 ** i) for i in range(n)])
    df = pd.DataFrame({"open": close * 0.99, "high": close * 1.01,
                       "low": close * 0.98, "close": close, "volume": [1000] * n})
    out = add_indicators(df)
    for col in ("rsi_14", "macd", "macd_signal", "bb_pct", "ema_50",
                "ema_200", "atr_14", "volume_ratio", "return_1d"):
        assert col in out.columns, col
    r = out["rsi_14"].dropna()
    assert ((r >= 0) & (r <= 100)).all()
    print("PASS add_indicators_columns_and_ranges")


def test_rsi_high_in_uptrend():
    close = pd.Series([100 + i for i in range(40)])
    assert rsi(close).dropna().iloc[-1] > 70
    print("PASS rsi_high_in_uptrend")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} INDICATOR TESTS PASSED")
