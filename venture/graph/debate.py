"""
venture/graph/debate.py — LangGraph multi-agent debate over the engines.

A trading desk: the Analyst frames a thesis, a Quant gives a math-first vote, a
Bull and a Bear argue, a Judge weighs all three into a final conviction, then
Decision (RiskEngine-gated) / Execution / Learning act.

  Scout ─▶ Analyst ─▶ Quant ─▶ Bull ─▶ Bear ─▶ Judge ─▶ Decision ─▶ Execution ─▶ Learning

Bull/Bear are heuristic by default (offline + fast) but each accepts a ClaudeBrain
persona for real LLM debate. The Judge weighs Quant + Bull − Bear into conviction;
the RiskEngine floor still overrides everything.

License: original code (LangGraph is MIT) -> commercial-clean.
"""
from __future__ import annotations

import os as _os
import sys as _sys
# Make `venture/` importable whether this file is imported or run directly.
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from dataclasses import replace as dc_replace
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from contracts import AnalysisReport
from data.providers import MockDataProvider
from engines.analyst import AnalystEngine
from engines.decision import DecisionEngine
from engines.execution import ExecutionEngine
from engines.learning import LearningEngine
from engines.quant import QuantEngine
from engines.scout import ScoutEngine
from portfolio import Portfolio
from rag.store import InMemoryKnowledgeStore
from risk_engine import RiskConfig, RiskEngine


class DebateState(TypedDict, total=False):
    symbol: str
    snapshot: Any
    report: Any
    quant: dict
    bull: dict
    bear: dict
    judged_conviction: float
    judge_note: str
    decision: Any
    fill: Any
    update: Any


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def build_debate_graph(scout, analyst, quant, decision, execution, learning, portfolio,
                       bull_brain=None, bear_brain=None):
    """Compile the debate graph. Engines are captured by the node closures."""

    def scout_node(state: DebateState) -> DebateState:
        return {"snapshot": scout.run(state["symbol"])}

    def analyst_node(state: DebateState) -> DebateState:
        return {"report": analyst.run(state["snapshot"])}

    def quant_node(state: DebateState) -> DebateState:
        return {"quant": quant.run(state["snapshot"])}

    def bull_node(state: DebateState) -> DebateState:
        rep = state["report"]
        if bull_brain is not None:
            d = bull_brain(state["snapshot"])
            score, arg = max(0.0, d.get("score", 0.0)), d.get("rationale", "")
        else:
            score = _clamp(max(0.0, rep.technical_score) * 0.6
                           + max(0.0, rep.sentiment_score) * 0.4 + 0.1)
            arg = f"Long case: technical={rep.technical_score}, sentiment={rep.sentiment_score}"
        return {"bull": {"score": round(score, 3), "argument": arg}}

    def bear_node(state: DebateState) -> DebateState:
        rep = state["report"]
        if bear_brain is not None:
            d = bear_brain(state["snapshot"])
            score, arg = max(0.0, -d.get("score", 0.0)), d.get("rationale", "")
        else:
            score = _clamp(max(0.0, -rep.technical_score) * 0.6
                           + max(0.0, -rep.sentiment_score) * 0.4 + 0.05)
            arg = f"Short case: technical={rep.technical_score}, sentiment={rep.sentiment_score}"
        return {"bear": {"score": round(score, 3), "argument": arg}}

    def judge_node(state: DebateState) -> DebateState:
        rep = state["report"]
        bull, bear = state["bull"]["score"], state["bear"]["score"]
        quant_score = state.get("quant", {}).get("score", 0.0)
        net = bull - bear
        # Quant confirms or contradicts the debate's lean.
        quant_align = quant_score if net >= 0 else -quant_score
        if bear - bull >= 0.4 and quant_score <= 0:
            judged = 0.0
            note = f"Bear wins (bull={bull}, bear={bear}, quant={quant_score}) -> stand down"
        else:
            judged = _clamp(rep.conviction * (1 + 0.3 * net + 0.2 * quant_align))
            note = (f"bull={bull}, bear={bear}, quant={quant_score}, "
                    f"net={net:+.2f} -> conviction {rep.conviction}->{judged:.3f}")
        return {"judged_conviction": round(judged, 3), "judge_note": note}

    def decision_node(state: DebateState) -> DebateState:
        rep: AnalysisReport = state["report"]
        snap = state["snapshot"]
        judged = state.get("judged_conviction", rep.conviction)
        rep2 = dc_replace(rep, conviction=judged)
        equity = portfolio.equity({state["symbol"]: snap.price})
        pos = portfolio.position(state["symbol"])
        in_position = bool(pos and pos["units"] > 0)
        return {"decision": decision.run(rep2, equity, snap.price, in_position)}

    def execution_node(state: DebateState) -> DebateState:
        return {"fill": execution.run(state["decision"], state["snapshot"].price)}

    def learning_node(state: DebateState) -> DebateState:
        snap = state["snapshot"]
        equity = portfolio.equity({state["symbol"]: snap.price})
        return {"update": learning.run(equity, state["fill"])}

    g = StateGraph(DebateState)
    for name, fn in [("scout", scout_node), ("analyst", analyst_node), ("quant", quant_node),
                     ("bull", bull_node), ("bear", bear_node), ("judge", judge_node),
                     ("decision", decision_node), ("execution", execution_node),
                     ("learning", learning_node)]:
        g.add_node(name, fn)
    g.add_edge(START, "scout")
    for a, b in [("scout", "analyst"), ("analyst", "quant"), ("quant", "bull"),
                 ("bull", "bear"), ("bear", "judge"), ("judge", "decision"),
                 ("decision", "execution"), ("execution", "learning")]:
        g.add_edge(a, b)
    g.add_edge("learning", END)
    return g.compile()


class DebateRunner:
    """Loops the compiled debate graph over the data feed (engines stay stateful)."""

    def __init__(self, app, data, risk, portfolio, learning, knowledge):
        self.app = app
        self.data = data
        self.risk = risk
        self.pf = portfolio
        self.learning = learning
        self.knowledge = knowledge

    def run(self, symbol: str, max_cycles: int | None = None) -> list:
        results: list = []
        while True:
            results.append(self.app.invoke({"symbol": symbol}))
            if not self.data.has_next() or (max_cycles and len(results) >= max_cycles):
                break
            self.data.advance()
        return results


def build_debate_runner(data_provider, knowledge_store=None, config: RiskConfig | None = None,
                        sma_window: int = 10, llm_brain=None,
                        bull_brain=None, bear_brain=None) -> DebateRunner:
    """Wire a debate runner around ANY DataProvider (Mock, CCXT, YFinance)."""
    cfg = config or RiskConfig()
    kb = knowledge_store or InMemoryKnowledgeStore()
    pf = Portfolio(initial_capital=cfg.initial_capital)
    risk = RiskEngine(cfg)
    learning = LearningEngine()
    app = build_debate_graph(
        scout=ScoutEngine(data_provider, kb, sma_window),
        analyst=AnalystEngine(llm_brain=llm_brain),
        quant=QuantEngine(),
        decision=DecisionEngine(risk),
        execution=ExecutionEngine(pf),
        learning=learning,
        portfolio=pf,
        bull_brain=bull_brain, bear_brain=bear_brain,
    )
    return DebateRunner(app, data_provider, risk, pf, learning, kb)


def build_default_debate(series: dict, news: dict | None = None,
                         config: RiskConfig | None = None, sma_window: int = 10,
                         knowledge_store=None, llm_brain=None,
                         bull_brain=None, bear_brain=None) -> DebateRunner:
    data = MockDataProvider(series, news)
    return build_debate_runner(data, knowledge_store, config, sma_window,
                               llm_brain, bull_brain, bear_brain)


if __name__ == "__main__":
    import random
    rng = random.Random(13)
    p, prices = 100.0, []
    for _ in range(60):
        p *= (1 + 0.006 + rng.uniform(-0.01, 0.01))
        prices.append(round(p, 4))
    runner = build_default_debate({"BTC/USDT": prices})
    results = runner.run("BTC/USDT")
    trades = sum(1 for r in results if r["fill"].executed)
    print(f"Debate cycles: {len(results)} | trades: {trades} | "
          f"final equity: ${results[-1]['update'].equity}")
    print("Last quant vote:", results[-1]["quant"])
    print("Last judge note:", results[-1]["judge_note"])
