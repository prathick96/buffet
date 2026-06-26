"""
venture/workflow.py — the autonomous agentic loop.

Composes the engines into one cycle:

    Scout ──▶ Analyst ──▶ Decision ──▶ Execution ──▶ Learning
      ▲ (RAG store)                                     │
      └──────────────── next bar ◀──────────────────────┘

The engines are decoupled via typed contracts, so a LangGraph graph (Phase 2)
can drive these exact nodes — including the bull/bear debate — without changing
them. This pure-Python runner keeps the core commercial-clean and testable.

License: original code, stdlib only -> commercial-clean. Python 3.10+.
"""
from __future__ import annotations

from dataclasses import dataclass

from contracts import AnalysisReport, Fill, LearningUpdate, MarketSnapshot, TradeDecision
from data.providers import MockDataProvider
from engines.analyst import AnalystEngine
from engines.decision import DecisionEngine
from engines.execution import ExecutionEngine
from engines.learning import LearningEngine
from engines.scout import ScoutEngine
from portfolio import Portfolio
from rag.store import InMemoryKnowledgeStore
from risk_engine import RiskConfig, RiskEngine


@dataclass
class CycleResult:
    snapshot: MarketSnapshot
    report: AnalysisReport
    decision: TradeDecision
    fill: Fill
    update: LearningUpdate


class TradingWorkflow:
    def __init__(self, scout, analyst, decision, execution, learning,
                 portfolio, data_provider):
        self.scout = scout
        self.analyst = analyst
        self.decision = decision
        self.execution = execution
        self.learning = learning
        self.pf = portfolio
        self.data = data_provider

    def run_cycle(self, symbol: str) -> CycleResult:
        snap = self.scout.run(symbol)
        report = self.analyst.run(snap)

        prices = {symbol: snap.price}
        equity = self.pf.equity(prices)
        pos = self.pf.position(symbol)
        in_position = bool(pos and pos["units"] > 0)

        decision = self.decision.run(report, equity, snap.price, in_position, rl_action=None)
        fill = self.execution.run(decision, snap.price)
        equity_after = self.pf.equity({symbol: snap.price})
        update = self.learning.run(equity_after, fill)
        return CycleResult(snap, report, decision, fill, update)

    def run(self, symbol: str, max_cycles: int | None = None) -> list:
        results: list = []
        while True:
            results.append(self.run_cycle(symbol))
            if not self.data.has_next() or (max_cycles and len(results) >= max_cycles):
                break
            self.data.advance()
        return results


def build_default_workflow(series: dict, news: dict | None = None,
                           config: RiskConfig | None = None,
                           sma_window: int = 10, llm_brain=None) -> TradingWorkflow:
    """Wire a full offline workflow from a price series — used by tests/backtests."""
    cfg = config or RiskConfig()
    data = MockDataProvider(series, news)
    kb = InMemoryKnowledgeStore()
    pf = Portfolio(initial_capital=cfg.initial_capital)
    risk = RiskEngine(cfg)
    return TradingWorkflow(
        scout=ScoutEngine(data, kb, sma_window),
        analyst=AnalystEngine(llm_brain=llm_brain),
        decision=DecisionEngine(risk),
        execution=ExecutionEngine(pf),
        learning=LearningEngine(),
        portfolio=pf,
        data_provider=data,
    )


if __name__ == "__main__":
    import random
    rng = random.Random(11)
    p, prices = 100.0, []
    for _ in range(120):
        p *= (1 + 0.006 + rng.uniform(-0.01, 0.01))
        prices.append(round(p, 4))
    wf = build_default_workflow({"BTC/USDT": prices})
    results = wf.run("BTC/USDT")
    last = results[-1].update.metrics
    trades = sum(1 for r in results if r.fill.executed)
    print(f"Cycles: {len(results)} | executed trades: {trades}")
    print(f"Final: {last}")
    print(f"Risk state: {wf.decision.risk.state.value} "
          f"(armed={wf.decision.risk.armed}, floor=${wf.decision.risk.effective_floor})")
