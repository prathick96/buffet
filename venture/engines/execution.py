"""
venture/engines/execution.py — the Execution engine (Trader).

Single job: realize a TradeDecision against the portfolio and report the Fill.
Phase 1+ swaps the paper Portfolio for ccxt/Alpaca/Freqtrade order routing
behind this same interface. Precise + slippage-aware (later).
"""
from __future__ import annotations

from contracts import Fill, TradeDecision
from engines.base import Engine


class ExecutionEngine(Engine):
    name = "execution"

    def __init__(self, portfolio):
        self.pf = portfolio

    def run(self, decision: TradeDecision, price: float) -> Fill:
        sym = decision.symbol

        if decision.action == "BUY" and decision.approved and decision.dollar_size > 0:
            units, fee, spent = self.pf.buy(sym, price, decision.dollar_size)
            if units > 0:
                return Fill(sym, "BUY", True, price, units, spent, fee, "Bought")
            return Fill(sym, "BUY", False, reason="Portfolio rejected (cash/position)")

        if decision.action == "SELL":
            units, fee, net = self.pf.sell(sym, price)
            if units > 0:
                return Fill(sym, "SELL", True, price, units, net, fee,
                            decision.reason or "Sold")
            return Fill(sym, "SELL", False, reason="No position to sell")

        return Fill(sym, "HOLD", False, reason=decision.reason)
