"""
venture/tests/test_rl_quant.py — RLQuantEngine graceful fallback (no torch needed).
Run:  python venture/tests/test_rl_quant.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from contracts import MarketSnapshot  # noqa: E402
from engines.rl_quant import RLQuantEngine  # noqa: E402


def _snap(prices):
    return MarketSnapshot(symbol="X", price=prices[-1], history=prices)


def test_falls_back_without_model():
    e = RLQuantEngine(model_path=None)
    up = [round(100 * (1.008 ** i), 4) for i in range(40)]
    v = e.run(_snap(up))
    assert v["source"] == "quant_stat" and v["score"] > 0
    print(f"PASS falls_back_without_model ({v['action']}, score={v['score']})")


def test_bad_model_path_falls_back():
    e = RLQuantEngine(model_path="venture/models/does_not_exist.zip")
    assert e.model is None and e.load_error is not None
    v = e.run(_snap([round(100 + i, 2) for i in range(40)]))
    assert v["action"] in ("BUY", "SELL", "HOLD")
    print("PASS bad_model_path_falls_back")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} RL-QUANT TESTS PASSED")
