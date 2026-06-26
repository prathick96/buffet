"""
venture/tests/test_debate.py
Run:  python venture/tests/test_debate.py
Offline test of the LangGraph bull/bear/judge debate over the engines.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph.debate import build_default_debate  # noqa: E402
from risk_engine import RiskConfig, RiskState  # noqa: E402


def _trend(n, drift, noise, seed, start=100.0):
    rng = random.Random(seed)
    p, out = start, []
    for _ in range(n):
        p *= (1 + drift + rng.uniform(-noise, noise))
        out.append(round(p, 4))
    return out


def test_debate_graph_runs_and_trades():
    prices = _trend(80, drift=0.006, noise=0.008, seed=3)
    runner = build_default_debate({"BTC/USDT": prices})
    results = runner.run("BTC/USDT")
    assert len(results) == len(prices)
    assert all("decision" in r and "judge_note" in r for r in results)
    assert all("quant" in r and "bull" in r and "bear" in r for r in results)  # full debate
    trades = sum(1 for r in results if r["fill"].executed)
    assert trades > 0
    cfg = RiskConfig()
    for r in results:
        if r["update"].equity <= cfg.hard_floor:
            assert runner.risk.state == RiskState.HALTED
    print(f"PASS debate_graph_runs_and_trades "
          f"(cycles={len(results)}, trades={trades}, final=${results[-1]['update'].equity})")


def test_debate_no_blind_longs_in_downtrend():
    prices = _trend(60, drift=-0.01, noise=0.005, seed=9)
    runner = build_default_debate({"BTC/USDT": prices})
    results = runner.run("BTC/USDT")
    longs = sum(1 for r in results if r["fill"].action == "BUY" and r["fill"].executed)
    assert longs == 0, f"expected no longs in a downtrend, got {longs}"
    print(f"PASS debate_no_blind_longs_in_downtrend (longs={longs})")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} DEBATE TESTS PASSED")
