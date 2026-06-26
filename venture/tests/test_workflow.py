"""
venture/tests/test_workflow.py
Run:  python venture/tests/test_workflow.py
End-to-end test of the autonomous engine loop (Scout->Analyst->Decide->Exec->Learn).
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workflow import build_default_workflow  # noqa: E402
from risk_engine import RiskConfig, RiskState  # noqa: E402


def _trend(n, drift, noise, seed, start=100.0):
    rng = random.Random(seed)
    p, out = start, []
    for _ in range(n):
        p *= (1 + drift + rng.uniform(-noise, noise))
        out.append(round(p, 4))
    return out


def test_full_loop_runs_and_trades_on_uptrend():
    prices = _trend(120, drift=0.006, noise=0.008, seed=3)
    wf = build_default_workflow({"BTC/USDT": prices})
    results = wf.run("BTC/USDT")
    assert len(results) == len(prices)                       # one cycle per bar
    assert all(r.update.metrics["equity"] > 0 for r in results)
    executed = [r for r in results if r.fill.executed]
    assert len(executed) > 0, "uptrend should produce at least one executed trade"
    # Risk floor respected throughout: equity never below hard floor unless halted.
    cfg = RiskConfig()
    for r in results:
        if r.update.equity <= cfg.hard_floor:
            assert wf.decision.risk.state == RiskState.HALTED
    print(f"PASS full_loop_runs_and_trades_on_uptrend "
          f"(cycles={len(results)}, trades={len(executed)}, "
          f"final=${results[-1].update.equity})")


def test_rag_context_flows_scout_to_analyst():
    prices = _trend(40, drift=0.005, noise=0.005, seed=5)
    news = {"BTC/USDT": [{"title": "Bitcoin ETF inflows hit record as price rallies",
                          "source": "Reuters"}]}
    wf = build_default_workflow({"BTC/USDT": prices}, news=news)
    results = wf.run("BTC/USDT")
    # Scout should have ingested news and surfaced it as retrieved context.
    assert any(r.snapshot.retrieved_context for r in results), "RAG retrieval produced nothing"
    print("PASS rag_context_flows_scout_to_analyst")


def test_floor_halts_and_flattens_on_crash():
    # Ramp up so it buys, then a hard gap-down that pushes equity below the floor.
    prices = [100, 102, 104, 106, 108, 110, 112, 114] + [30] * 8
    # Strongly bullish news -> full-conviction (full-size) position, so the crash
    # actually drives equity through the floor and exercises the halt/flatten path.
    news = {"BTC/USDT": [{"title": "Bitcoin inflows surge to record; bullish "
                          "approval as price soars, tops and beats", "source": "Reuters"}]}
    wf = build_default_workflow({"BTC/USDT": prices}, news=news, sma_window=5)
    results = wf.run("BTC/USDT")
    assert wf.decision.risk.state == RiskState.HALTED, "crash should trip the floor"
    # A flatten SELL must have fired at/after the halt.
    assert any(r.fill.action == "SELL" and r.fill.executed for r in results)
    assert results[-1].update.equity > 0
    print(f"PASS floor_halts_and_flattens_on_crash "
          f"(final=${results[-1].update.equity}, reason='{wf.decision.risk.halt_reason}')")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} WORKFLOW TESTS PASSED")
