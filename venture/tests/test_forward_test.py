"""
venture/tests/test_forward_test.py — live forward-tester (deterministic fake clock).
Covers legacy point scoring AND the P0 fixes: dated scoring, dead-band ties,
per-bar de-duplication, and the volatility-scaled band helper.
Run:  python venture/tests/test_forward_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from eval.forward_test import ForwardTester, deadband_from_closes  # noqa: E402


def _ft(horizon=100):
    t = {"now": 1000.0}
    ft = ForwardTester(":memory:", horizon_sec=horizon, clock=lambda: t["now"])
    return ft, t


class _Snap:
    def __init__(self, price):
        self.price = price


class _Rep:
    def __init__(self, action, conviction=0.7, sentiment="BULLISH", rationale="x"):
        self.suggested_action = action
        self.conviction = conviction
        self.sentiment = sentiment
        self.rationale = rationale


# ----------------------------------------------------------------- legacy path
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


# ------------------------------------------------------------- P0: dated scoring
def test_dated_scoring_uses_a_bar_after_the_entry_not_itself():
    ft, t = _ft(horizon=100)
    ft.capture("A", 100.0, "BUY", 0.8, ts=1000.0, bar_ts=1000.0)
    bars = [(1000.0, 100.0), (1050.0, 100.0), (1100.0, 110.0), (1200.0, 120.0)]
    t["now"] = 1300.0
    n = ft.score_due(bars_fn=lambda s: bars)
    assert n == 1
    row = ft.conn.execute(
        "SELECT exit_price,exit_ts,fwd_return,correct FROM predictions").fetchone()
    assert row[0] == 110.0 and row[1] == 1100.0   # first bar at/after 1100, NOT the 100 self
    assert abs(row[2] - 0.10) < 1e-9 and row[3] == 1
    print("PASS dated_scoring_uses_a_bar_after_the_entry_not_itself")


def test_dated_scoring_stays_pending_when_market_was_closed():
    # horizon elapses in wall-clock, but no realized bar exists after it
    # (e.g. captured Fri, "due" Sat, market shut all weekend) -> stay pending.
    ft, t = _ft(horizon=100)
    ft.capture("A", 100.0, "SELL", 0.8, ts=1000.0, bar_ts=1000.0)
    bars = [(1000.0, 100.0), (1050.0, 105.0)]      # nothing at/after 1100
    t["now"] = 1300.0
    assert ft.score_due(bars_fn=lambda s: bars) == 0
    assert ft.report()["pending"] == 1
    print("PASS dated_scoring_stays_pending_when_market_was_closed")


# ---------------------------------------------------------------- P0: dead-band
def test_deadband_marks_flat_move_as_tie_not_loss():
    ft, t = _ft(horizon=100)
    ft.capture("FLAT", 100.0, "BUY", 0.8, ts=1000.0, bar_ts=1000.0, deadband=0.02)  # 2%
    ft.capture("REAL", 100.0, "BUY", 0.8, ts=1000.0, bar_ts=1000.0, deadband=0.02)
    t["now"] = 1300.0
    # FLAT exits +1% (inside band -> tie); REAL exits +3% (outside -> win)
    ft.score_due(bars_fn=lambda s: [(1000.0, 100.0),
                                    (1200.0, 101.0 if s == "FLAT" else 103.0)])
    r = ft.report(min_sample=1)
    assert r["scored"] == 2 and r["directional"] == 1 and r["ties"] == 1
    assert r["hit_rate"] == 1.0                  # the one real directional call won
    print("PASS deadband_marks_flat_move_as_tie_not_loss")


# ------------------------------------------------------------------- P0: dedup
def test_dedup_skips_same_bar():
    ft, _ = _ft(horizon=100)
    snap, rep = _Snap(100.0), _Rep("BUY")
    assert ft.capture_from_cycle("A", snap, rep, bar_ts=1000.0) > 0
    assert ft.capture_from_cycle("A", snap, rep, bar_ts=1000.0) == -1   # same bar -> skip
    assert ft.capture_from_cycle("A", snap, rep, bar_ts=2000.0) > 0     # new bar -> keep
    cnt = ft.conn.execute("SELECT COUNT(*) FROM predictions WHERE symbol='A'").fetchone()[0]
    assert cnt == 2
    print("PASS dedup_skips_same_bar")


# --------------------------------------------------------- P0: vol-scaled band
def test_deadband_from_closes_helper():
    flat = [100.0] * 20
    assert deadband_from_closes(flat, 86400, 86400) == 0.001          # floor
    assert deadband_from_closes([100, 101], 86400, None) == 0.001     # no bar_seconds -> floor
    volatile = [100.0 * (1.01 ** i if i % 2 else 0.99 ** i) for i in range(30)]
    band = deadband_from_closes(volatile, 86400, 86400)
    assert 0.001 < band <= 0.03                                        # scales with vol, capped
    print("PASS deadband_from_closes_helper")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} FORWARD-TEST TESTS PASSED")
