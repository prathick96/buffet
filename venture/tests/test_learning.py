"""
venture/tests/test_learning.py — P2 adaptation layer:
multi-horizon scoring, the Bayesian calibrator, the risk-engine edge throttle,
and the walk-forward retrain gate. All torch-free (fast, deterministic).
Run:  python venture/tests/test_learning.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from eval.forward_test import ForwardTester  # noqa: E402
from learn.calibration import (Calibrator, shrunk_hit_rate,  # noqa: E402
                               size_multiplier_from)
from risk_engine import RiskConfig, RiskEngine  # noqa: E402
from train.retrain import gate  # noqa: E402


def _ft(horizons=(100, 300)):
    t = {"now": 1000.0}
    ft = ForwardTester(":memory:", horizon_sec=100, clock=lambda: t["now"], horizons=horizons)
    return ft, t


# ---------------------------------------------------------- multi-horizon
def test_score_horizons_and_report():
    ft, t = _ft()
    ft.capture("A", 100.0, "BUY", 0.8, ts=1000.0, bar_ts=1000.0)
    bars = [(1000.0, 100.0), (1100.0, 110.0), (1300.0, 90.0)]   # +10% @100, -10% @300
    t["now"] = 2000.0
    assert ft.score_horizons(bars_fn=lambda s: bars) == 2
    rep = ft.report_by_horizon()
    assert rep["100"]["hit_rate"] == 1.0     # BUY +10% -> win
    assert rep["300"]["hit_rate"] == 0.0     # BUY -10% -> loss
    print("PASS score_horizons_and_report")


def test_score_horizons_idempotent_and_pending():
    ft, t = _ft()
    ft.capture("A", 100.0, "BUY", 0.8, ts=1000.0, bar_ts=1000.0)
    bars = [(1000.0, 100.0), (1100.0, 110.0)]   # only the 100s horizon has a bar
    t["now"] = 2000.0
    assert ft.score_horizons(bars_fn=lambda s: bars) == 1   # 300s stays pending
    assert ft.score_horizons(bars_fn=lambda s: bars) == 0   # idempotent re-run
    print("PASS score_horizons_idempotent_and_pending")


# --------------------------------------------------------- calibrator math
def test_shrunk_hit_rate_pulls_small_samples_to_chance():
    assert 0.60 < shrunk_hit_rate(5, 5, prior=6) < 0.70     # 5/5 shrinks toward 0.5
    assert abs(shrunk_hit_rate(50, 100, prior=6) - 0.5) < 0.02
    assert shrunk_hit_rate(80, 100, prior=6) > 0.65
    print("PASS shrunk_hit_rate_pulls_small_samples_to_chance")


def test_size_multiplier_mapping():
    assert size_multiplier_from(0.90, 5.0, n=10, min_sample=30) == 0.5    # unproven gate
    assert size_multiplier_from(0.62, 2.0, n=50) == 1.0                   # strong proven edge
    assert abs(size_multiplier_from(0.50, 1.0, n=50) - 0.5) < 1e-9        # chance -> neutral
    assert size_multiplier_from(0.55, -1.0, n=50) == 0.5                  # neg $ docks it
    assert size_multiplier_from(0.40, -1.0, n=50) == 0.25                 # weak -> floor
    print("PASS size_multiplier_mapping")


def test_calibrator_recompute_persists_and_serves_multiplier():
    ft, t = _ft()
    for i in range(40):
        ft.capture("A", 100.0, "BUY", 0.8, ts=1000.0 + i, bar_ts=1000.0 + i)
    bars = [(1000.0 + i, 100.0) for i in range(40)] + [(3000.0, 120.0)]  # every win +20%
    t["now"] = 9000.0
    ft.score_horizons(bars_fn=lambda s: bars)
    cal = Calibrator(ft.conn, min_sample=30, sizing_horizon_sec=100)
    summary = cal.recompute(now=9000.0)
    assert summary["A"]["n"] == 40 and summary["A"]["multiplier"] == 1.0
    assert cal.size_multiplier("A", horizon_sec=100) == 1.0
    assert cal.size_multiplier("UNKNOWN") == 0.5          # unproven default
    assert any(r["symbol"] == "A" for r in cal.table())   # persisted
    print("PASS calibrator_recompute_persists_and_serves_multiplier")


# ---------------------------------------------------------- risk throttle
def test_edge_multiplier_throttles_but_never_amplifies():
    eng = RiskEngine(RiskConfig(initial_capital=1000.0, min_conviction=0.5))
    full = eng.assess_trade(1000.0, 0.9, edge_multiplier=1.0)
    half = eng.assess_trade(1000.0, 0.9, edge_multiplier=0.5)
    over = eng.assess_trade(1000.0, 0.9, edge_multiplier=5.0)   # clamps to 1.0
    assert full.approved and half.approved
    assert abs(half.size_pct - full.size_pct * 0.5) < 1e-9
    assert abs(over.size_pct - full.size_pct) < 1e-9
    print("PASS edge_multiplier_throttles_but_never_amplifies")


# ------------------------------------------------------------ retrain gate
def test_retrain_gate():
    assert gate({"folds": 4, "avg_edge_pct": 1.2, "folds_beating_bh": 3})
    assert not gate({"folds": 4, "avg_edge_pct": -0.5, "folds_beating_bh": 3})  # neg edge
    assert not gate({"folds": 4, "avg_edge_pct": 1.0, "folds_beating_bh": 1})   # minority
    assert not gate({"folds": 0})
    print("PASS retrain_gate")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} LEARNING TESTS PASSED")
