"""
venture/portfolio.py — minimal, testable, multi-asset paper portfolio.

The clean-core counterpart to the notebook's PaperPortfolio (which is tied to
Supabase/uuid). This one is dependency-free so the engine workflow runs and
tests offline; a Supabase-syncing adapter can wrap it later.

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Portfolio:
    initial_capital: float = 50.0
    commission: float = 0.001

    def __post_init__(self) -> None:
        self.cash: float = self.initial_capital
        self.holdings: dict = {}   # symbol -> {"units": float, "avg_price": float}

    def equity(self, prices: dict) -> float:
        value = self.cash
        for sym, h in self.holdings.items():
            value += h["units"] * prices.get(sym, h["avg_price"])
        return value

    def position(self, symbol: str) -> dict | None:
        return self.holdings.get(symbol)

    def buy(self, symbol: str, price: float, dollars: float):
        """Spend `dollars` (capped by cash) on `symbol`. Returns (units, fee, spent)."""
        if dollars <= 0 or self.cash <= 0 or price <= 0:
            return 0.0, 0.0, 0.0
        if symbol in self.holdings and self.holdings[symbol]["units"] > 0:
            return 0.0, 0.0, 0.0          # no pyramiding (one position per symbol)
        spend = min(dollars, self.cash)
        fee = spend * self.commission
        units = (spend - fee) / price
        self.cash -= spend
        self.holdings[symbol] = {"units": units, "avg_price": price}
        return units, fee, spend

    def sell(self, symbol: str, price: float):
        """Liquidate the full position in `symbol`. Returns (units, fee, net_proceeds)."""
        h = self.holdings.get(symbol)
        if not h or h["units"] <= 0:
            return 0.0, 0.0, 0.0
        units = h["units"]
        proceeds = units * price
        fee = proceeds * self.commission
        net = proceeds - fee
        self.cash += net
        del self.holdings[symbol]
        return units, fee, net
