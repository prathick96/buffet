"""
venture/tests/test_risk_engine.py
Run:  python venture/tests/test_risk_engine.py
Pure-stdlib smoke tests for the Phase 0 Risk Engine.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from risk_engine import RiskEngine, RiskConfig, RiskState  # noqa: E402


def approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


def test_fresh_state():
    e = RiskEngine()
    assert e.state == RiskState.ACTIVE
    assert not e.armed
    assert approx(e.effective_floor, 45.0)
    print("PASS fresh_state")


def test_high_conviction_sized_within_caps():
    e = RiskEngine()
    d = e.assess_trade(equity=50.0, conviction=1.0)
    assert d.approved
    assert d.size_pct <= e.config.max_position_pct + 1e-9
    assert d.size_pct <= e.config.max_total_exposure_pct - e.config.reserve_cash_pct + 1e-9
    print(f"PASS high_conviction_sized_within_caps (size_pct={d.size_pct})")


def test_low_conviction_deferred():
    e = RiskEngine()
    d = e.assess_trade(equity=50.0, conviction=0.40)
    assert not d.approved and "defer" in d.reason
    print("PASS low_conviction_deferred")


def test_per_trade_risk_cap_with_stop():
    e = RiskEngine()
    # price 100, stop 90 -> risk $10/unit. 2% of $50 = $1 -> 0.1 units -> $10 -> 20% of equity.
    d = e.assess_trade(equity=50.0, conviction=1.0, price=100.0, stop_price=90.0)
    assert d.approved
    assert approx(d.size_pct, 0.20), d.size_pct
    print(f"PASS per_trade_risk_cap_with_stop (size_pct={d.size_pct})")


def test_arming_and_back_out():
    e = RiskEngine()
    e.update_equity(60.0)                 # +20% -> back-out line arms at $50
    assert e.armed and approx(e.effective_floor, 50.0)
    e.update_equity(49.0)                 # fell back below $50 -> halt
    assert e.state == RiskState.HALTED
    d = e.assess_trade(equity=49.0, conviction=1.0)
    assert not d.approved and "HALTED" in d.reason
    print("PASS arming_and_back_out")


def test_hard_floor_before_arming():
    e = RiskEngine()
    e.update_equity(44.0)                 # below hard floor $45, never armed -> halt
    assert e.state == RiskState.HALTED and "floor" in e.halt_reason
    print("PASS hard_floor_before_arming")


def test_drawdown_halt():
    e = RiskEngine(RiskConfig(initial_capital=1000.0, hard_floor=10.0, back_out_level=10.0))
    e.update_equity(1000.0)
    e.update_equity(740.0)                # 26% drawdown from peak -> halt
    assert e.state == RiskState.HALTED and "Drawdown" in e.halt_reason
    print("PASS drawdown_halt")


def test_reserve_and_no_leverage():
    e = RiskEngine()
    d = e.assess_trade(equity=1000.0, conviction=1.0)
    assert d.size_pct <= e.config.max_total_exposure_pct - e.config.reserve_cash_pct + 1e-9
    print(f"PASS reserve_and_no_leverage (size_pct={d.size_pct})")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} RISK-ENGINE TESTS PASSED")
