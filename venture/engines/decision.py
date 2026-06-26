"""
venture/engines/decision.py — the Decision engine (Portfolio Manager + Controller).

Single job: turn an AnalysisReport into a risk-gated TradeDecision. Fuses the
Analyst's call with an optional RL action, then runs the RiskEngine for the
final approve/size — including the non-negotiable floor: if the account has
breached its floor/drawdown, this engine flattens and stops opening risk.

Ruthless + disciplined: bold conviction, but the floor always wins.
"""
from __future__ import annotations

from contracts import AnalysisReport, TradeDecision
from engines.base import Engine
from risk_engine import RiskEngine, RiskState


class DecisionEngine(Engine):
    name = "decision"

    def __init__(self, risk_engine: RiskEngine):
        self.risk = risk_engine

    def run(self, report: AnalysisReport, equity: float, price: float,
            in_position: bool, rl_action: str | None = None) -> TradeDecision:
        # Floor check first — it overrides any signal.
        self.risk.update_equity(equity)
        if self.risk.state == RiskState.HALTED:
            if in_position:
                return self._mk(report, "SELL", True, 0.0, 0.0,
                                f"HALTED — flatten: {self.risk.halt_reason}", "HALTED")
            return self._mk(report, "HOLD", False, 0.0, 0.0,
                            f"HALTED: {self.risk.halt_reason}", "HALTED")

        action = self._fuse(report.suggested_action, rl_action)

        if action == "BUY" and not in_position:
            d = self.risk.assess_trade(equity, report.conviction,
                                       price=price, stop_price=report.stop_price)
            return self._mk(report, "BUY" if d.approved else "HOLD", d.approved,
                            d.size_pct, d.dollar_size, d.reason, d.state.value)

        if action == "SELL" and in_position:
            return self._mk(report, "SELL", True, 0.0, 0.0, "Exit signal",
                            self.risk.state.value)

        return self._mk(report, "HOLD", False, 0.0, 0.0, "No actionable signal",
                        self.risk.state.value)

    @staticmethod
    def _fuse(llm_action: str, rl_action: str | None) -> str:
        if rl_action is None or llm_action == rl_action:
            return llm_action
        # One side neutral -> follow the other; genuine conflict -> stand down.
        if rl_action == "HOLD":
            return llm_action
        if llm_action == "HOLD":
            return rl_action
        return "HOLD"

    def _mk(self, report: AnalysisReport, action: str, approved: bool,
            size_pct: float, dollar_size: float, reason: str, risk_state: str) -> TradeDecision:
        return TradeDecision(
            symbol=report.symbol, action=action, approved=approved,
            size_pct=size_pct, dollar_size=dollar_size, conviction=report.conviction,
            reason=reason, risk_state=risk_state, stop_price=report.stop_price,
        )
