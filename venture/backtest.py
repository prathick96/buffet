"""
venture/backtest.py — Walk-forward backtest harness (Phase 0)

Scores a strategy on the "$50 -> $100k, never zero out" journey using the SAME
RiskEngine that will govern live decisions, so paper results reflect the real
risk rules (hard floor, back-out line, sizing, drawdown halt). Single-asset for
Phase 0 validation; multi-asset is a later extension.

The scorecard answers the only question that matters early: does the agent
*survive and compound*, or does it take amateur risks and trip the floor?

License: original code, standard library only -> commercial-clean. Python 3.10+.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import mean, pstdev
from typing import Callable, Optional, Sequence

from risk_engine import RiskConfig, RiskEngine, RiskState


@dataclass
class Bar:
    t: int
    price: float


@dataclass
class Signal:
    action: str = "HOLD"                 # "BUY" | "SELL" | "HOLD"
    conviction: float = 0.0              # 0..1
    stop_price: Optional[float] = None   # natural stop for risk-based sizing


# strategy(history_prices, current_bar, in_position) -> Signal
Strategy = Callable[[Sequence[float], Bar, bool], Signal]


@dataclass
class BacktestResult:
    initial_equity:   float
    final_equity:     float
    total_return_pct: float
    sharpe:           float
    sortino:          float
    max_drawdown_pct: float
    num_trades:       int
    hit_rate:         float
    survived:         bool        # never fell to the hard floor
    halted:           bool
    halt_reason:      str
    reached_target:   bool
    equity_curve:     list = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=" * 52,
            "BACKTEST SCORECARD",
            "=" * 52,
            f"  Initial equity   : ${self.initial_equity:,.2f}",
            f"  Final equity     : ${self.final_equity:,.2f}",
            f"  Total return     : {self.total_return_pct:+.2f}%",
            f"  Sharpe (annual)  : {self.sharpe:.2f}",
            f"  Sortino (annual) : {self.sortino:.2f}",
            f"  Max drawdown     : {self.max_drawdown_pct:.2f}%",
            f"  Trades / hit-rate: {self.num_trades} / {self.hit_rate*100:.1f}%",
            f"  Survived floor   : {'YES' if self.survived else 'NO'}",
            f"  Halted           : {self.halted}  {('('+self.halt_reason+')') if self.halted else ''}",
            f"  Reached target   : {'YES' if self.reached_target else 'no'}",
            "=" * 52,
        ]
        return "\n".join(lines)


def _max_drawdown_pct(curve: Sequence[float]) -> float:
    peak, worst = curve[0] if curve else 0.0, 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            worst = max(worst, (peak - v) / peak)
    return worst * 100


def _annualized_sharpe(returns: Sequence[float], periods_per_year: int) -> float:
    if len(returns) < 2:
        return 0.0
    sd = pstdev(returns)
    if sd == 0:
        return 0.0
    return (mean(returns) / sd) * math.sqrt(periods_per_year)


def _annualized_sortino(returns: Sequence[float], periods_per_year: int) -> float:
    if len(returns) < 2:
        return 0.0
    downside = [r for r in returns if r < 0]
    if not downside:
        return float("inf") if mean(returns) > 0 else 0.0
    dd = pstdev(downside) if len(downside) > 1 else abs(downside[0])
    if dd == 0:
        return 0.0
    return (mean(returns) / dd) * math.sqrt(periods_per_year)


def run_backtest(prices: Sequence[float], strategy: Strategy,
                 config: Optional[RiskConfig] = None,
                 commission: float = 0.001,
                 periods_per_year: int = 252,
                 target: float = 100_000.0) -> BacktestResult:
    """Run a single-asset, long-only walk through `prices` under the RiskEngine."""
    config = config or RiskConfig()
    engine = RiskEngine(config)

    cash = config.initial_capital
    units = 0.0
    entry_cost = 0.0          # cash spent to open the current position (incl. fees)
    equity_curve: list = []
    trade_pnls: list = []

    for i, price in enumerate(prices):
        in_position = units > 0
        equity = cash + units * price
        engine.update_equity(equity)

        # Floor / drawdown breached -> flatten and stop opening new risk.
        if engine.state == RiskState.HALTED:
            if in_position:
                proceeds = units * price * (1 - commission)
                trade_pnls.append(proceeds - entry_cost)
                cash += proceeds
                units = 0.0
            equity_curve.append(cash)
            continue

        sig = strategy(prices[:i + 1], Bar(i, price), in_position)

        if not in_position and sig.action == "BUY":
            decision = engine.assess_trade(equity, sig.conviction,
                                           price=price, stop_price=sig.stop_price)
            if decision.approved and decision.dollar_size > 0:
                spend = min(decision.dollar_size, cash)
                fee = spend * commission
                units = (spend - fee) / price
                cash -= spend
                entry_cost = spend
        elif in_position and sig.action == "SELL":
            proceeds = units * price * (1 - commission)
            trade_pnls.append(proceeds - entry_cost)
            cash += proceeds
            units = 0.0

        equity_curve.append(cash + units * price)

    final_equity = equity_curve[-1] if equity_curve else config.initial_capital
    rets = [equity_curve[k] / equity_curve[k - 1] - 1
            for k in range(1, len(equity_curve)) if equity_curve[k - 1] > 0]
    wins = sum(1 for p in trade_pnls if p > 0)

    return BacktestResult(
        initial_equity=config.initial_capital,
        final_equity=round(final_equity, 2),
        total_return_pct=round((final_equity / config.initial_capital - 1) * 100, 2),
        sharpe=round(_annualized_sharpe(rets, periods_per_year), 2),
        sortino=round(_annualized_sortino(rets, periods_per_year), 2),
        max_drawdown_pct=round(_max_drawdown_pct(equity_curve), 2),
        num_trades=len(trade_pnls),
        hit_rate=round(wins / len(trade_pnls), 4) if trade_pnls else 0.0,
        survived=final_equity > config.hard_floor,
        halted=engine.state == RiskState.HALTED,
        halt_reason=engine.halt_reason,
        reached_target=final_equity >= target,
        equity_curve=[round(v, 4) for v in equity_curve],
    )


def sma_momentum_strategy(window: int = 10):
    """Simple long-only momentum: long above the SMA, exit below. Stop = SMA."""
    def strat(history: Sequence[float], bar: Bar, in_position: bool) -> Signal:
        if len(history) < window:
            return Signal("HOLD")
        sma = mean(history[-window:])
        price = bar.price
        if price > sma:
            conviction = max(0.0, min(1.0, 0.6 + (price - sma) / sma * 10))
            return Signal("BUY", conviction=conviction, stop_price=sma)
        return Signal("SELL")
    return strat


if __name__ == "__main__":
    import random
    rng = random.Random(42)
    # Synthetic gently-trending series with noise.
    p, series = 100.0, []
    for _ in range(300):
        p *= (1 + 0.0015 + rng.uniform(-0.02, 0.02))
        series.append(round(p, 4))
    res = run_backtest(series, sma_momentum_strategy(10))
    print(res.summary())
