"""
venture/tests/test_backtest.py
Run:  python venture/tests/test_backtest.py
Validates the harness mechanics and that the RiskEngine floor is enforced.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest import run_backtest, sma_momentum_strategy, Signal  # noqa: E402
from risk_engine import RiskConfig  # noqa: E402


def test_runs_and_scores_on_uptrend():
    rng = random.Random(7)
    p, series = 100.0, []
    for _ in range(300):
        p *= (1 + 0.002 + rng.uniform(-0.015, 0.015))
        series.append(p)
    res = run_backtest(series, sma_momentum_strategy(10))
    assert len(res.equity_curve) == len(series)
    assert res.num_trades > 0
    assert res.final_equity > 0
    assert res.survived                      # an uptrend must not trip the floor
    assert math_is_finite(res.sharpe)
    print(f"PASS runs_and_scores_on_uptrend "
          f"(ret={res.total_return_pct}%, trades={res.num_trades}, sharpe={res.sharpe})")


def test_floor_halts_on_crash():
    # Buy-and-hold strategy into a gap-down: equity must cross the hard floor -> halt.
    def buy_and_hold(history, bar, in_position):
        return Signal("HOLD") if in_position else Signal("BUY", conviction=0.9)
    prices = [100, 101, 102, 103, 104] + [40] * 10   # gap down
    res = run_backtest(prices, buy_and_hold, RiskConfig())
    assert res.halted, "expected a floor/drawdown halt"
    assert "floor" in res.halt_reason.lower() or "drawdown" in res.halt_reason.lower()
    assert not res.survived
    print(f"PASS floor_halts_on_crash (final=${res.final_equity}, reason='{res.halt_reason}')")


def test_no_trades_when_flat_data():
    prices = [100.0] * 50            # SMA == price, never strictly above -> sells/holds only
    res = run_backtest(prices, sma_momentum_strategy(10))
    assert res.num_trades == 0
    assert res.final_equity == res.initial_equity
    print("PASS no_trades_when_flat_data")


def math_is_finite(x: float) -> bool:
    import math
    return math.isfinite(x)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} BACKTEST TESTS PASSED")
