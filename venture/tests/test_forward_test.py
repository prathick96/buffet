"""
venture/tests/test_forward_test.py — live forward-tester (deterministic fake clock).
Run:  python venture/tests/test_forward_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from eval.forward_test import ForwardTester  # noqa: E402


def _ft(horizon=100):
    t = {"now": 1000.0}
    ft = ForwardTester(":memory:", horizon_sec=horizon, clock=lambda: t["now"])
    return ft, t


def test_capture_and_due_only_after_horizon():
    ft, t = _ft(horizon=100)
    ft.capture("BTC/USDT", 100.0, "BUY", 0.8)
    assert ft.due() == []                       # too early
    t["now"] += 101
    assert len(ft.due()) == 1                   # horizon elapsed
    print("PASS capture_and_due_only_after_horizon")


def test_scoring_buy_sell_hold():
    ft, t = _ft(horizon=10)
    ft.capture("A", 100.0, "BUY", 0.8)          # price -> 110 = correct
    ft.capture("B", 100.0, "SELL", 0.7)         # price -> 110 = wrong
    ft.capture("C", 100.0, "HOLD", 0.5)         # not directional
    t["now"] += 11
    n = ft.score_due(price_fn=lambda s: 110.0)
    assert n == 3
    r = ft.report(min_sample=1)
    assert r["directional"] == 2 and r["hit_rate"] == 0.5
    # signed: BUY +10%, SELL -10% -> avg 0
    assert abs(r["avg_signal_return_pct"]) < 1e-9
    print("PASS scoring_buy_sell_hold")


def test_verdicts():
    ft, t = _ft(horizon=10)
    for i in range(3):
        ft.capture("A", 100.0, "BUY", 0.9, ts=t["now"])
    t["now"] += 11
    ft.score_due(price_fn=lambda s: 120.0)      # all BUYs correct
    r = ft.report(min_sample=20)
    assert "insufficient sample" in r["verdict"]
    r2 = ft.report(min_sample=3)
    assert r2["verdict"].startswith("EDGE FORMING")
    print("PASS verdicts")


def test_price_fn_failure_leaves_pending():
    ft, t = _ft(horizon=10)
    ft.capture("A", 100.0, "BUY", 0.9)
    t["now"] += 11
    def boom(sym):
        raise RuntimeError("feed down")
    assert ft.score_due(price_fn=boom) == 0
    assert ft.report()["pending"] == 1          # still pending, not lost
    print("PASS price_fn_failure_leaves_pending")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} FORWARD-TEST TESTS PASSED")
