"""
venture/risk_engine.py — Portfolio-level Risk Engine (Phase 0 cornerstone)

The single most important safety component of the venture. It sits ABOVE the
existing per-trade SecurityAgent / circuit-breaker and the RL/LLM signal layer,
and owns capital preservation for the whole portfolio.

Core mandate (straight from the project brief):
  - Start at $50, grow toward $100,000 on paper.
  - "I don't want to zero out."          -> a HARD liquidation floor (default $45).
  - "Back out when it drops back to $50." -> a trailing back-out line that ARMS
    only after the account has grown +X% (default +20% = $60), so the engine can
    actually start trading from $50 without instantly tripping its own floor.
  - "Steady, well thought-out actions, not amateur risks." -> conviction-scaled,
    risk-capped position sizing with no leverage and a permanent cash reserve.

Why two lines (hard_floor $45 vs back_out $50)? You cannot both start AT $50 and
refuse to ever dip below $50 — growing $50 -> $100k requires risking some of the
initial stake. So: while climbing the first leg ($50 -> $60) only the hard floor
($45) protects you; once you've banked +20% the back-out line arms at $50 and
locks in the original stake. Both levels are config — tune to taste.

License: original code, standard library only -> safe to commercialize. Runs on
any Python 3.10+.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RiskState(str, Enum):
    ACTIVE = "ACTIVE"   # trading allowed
    HALTED = "HALTED"   # floor / drawdown breached -> flatten & stop opening risk


@dataclass
class RiskConfig:
    initial_capital:        float = 50.0
    hard_floor:             float = 45.0   # never-zero-out hard liquidation line
    back_out_level:         float = 50.0   # trailing "back to $50 -> stop" line
    arming_gain_pct:        float = 0.20   # back_out arms after +20% (-> $60)
    max_drawdown_pct:       float = 0.25   # halt if equity falls 25% from peak
    max_risk_per_trade_pct: float = 0.02   # risk <= 2% of equity per trade (w/ stop)
    max_position_pct:       float = 0.25   # no single new position > 25% of equity
    max_total_exposure_pct: float = 1.00   # no leverage in paper trading
    min_conviction:         float = 0.55   # below this -> defer (no trade)
    reserve_cash_pct:       float = 0.05   # always keep >= 5% in cash


@dataclass
class RiskDecision:
    approved:    bool
    size_pct:    float      # fraction of equity to deploy (0..1)
    dollar_size: float
    reason:      str
    state:       RiskState


@dataclass
class RiskEngine:
    config: RiskConfig = field(default_factory=RiskConfig)

    def __post_init__(self) -> None:
        self.peak_equity: float = self.config.initial_capital
        self.armed: bool = False        # has the back-out line engaged?
        self.state: RiskState = RiskState.ACTIVE
        self.halt_reason: str = ""

    # ------------------------------------------------------------------ floor
    @property
    def effective_floor(self) -> float:
        """Active stop-out line: hard floor until the back-out line arms."""
        if self.armed:
            return max(self.config.hard_floor, self.config.back_out_level)
        return self.config.hard_floor

    def update_equity(self, equity: float) -> dict:
        """Call every cycle with the current total portfolio value."""
        c = self.config
        if equity > self.peak_equity:
            self.peak_equity = equity
        # Arm the back-out line once we've grown past the arming threshold.
        if not self.armed and equity >= c.back_out_level * (1 + c.arming_gain_pct):
            self.armed = True
        # Hard stop-out checks (only while still active).
        if self.state == RiskState.ACTIVE:
            if equity <= self.effective_floor:
                self._halt(f"Equity ${equity:.2f} hit floor ${self.effective_floor:.2f}")
            elif self.peak_equity > 0 and \
                    (self.peak_equity - equity) / self.peak_equity >= c.max_drawdown_pct:
                dd = (self.peak_equity - equity) / self.peak_equity * 100
                self._halt(f"Drawdown {dd:.1f}% >= {c.max_drawdown_pct * 100:.0f}% "
                           f"from peak ${self.peak_equity:.2f}")
        return self.status(equity)

    def _halt(self, reason: str) -> None:
        self.state = RiskState.HALTED
        self.halt_reason = reason

    def reset_halt(self) -> None:
        """Manual re-arm after a human review (kept explicit on purpose)."""
        self.state = RiskState.ACTIVE
        self.halt_reason = ""

    # --------------------------------------------------------------- sizing
    def assess_trade(self, equity: float, conviction: float,
                     price: Optional[float] = None,
                     stop_price: Optional[float] = None,
                     edge_multiplier: float = 1.0) -> RiskDecision:
        """
        Decide whether to open a new long position and how big.

        conviction: 0..1 blended confidence from the agent debate.
        price/stop_price: if both given (long), size is additionally capped so the
                          stop-loss can lose at most `max_risk_per_trade_pct` of equity.
        edge_multiplier: learned, DEMONSTRATED-edge scaler from the calibrator
                         (venture/learn/calibration.py). Clamped to [0, 1] so it can
                         only throttle unproven/weak symbols — it can never enlarge a
                         position past the caps below (capital preservation first).
        """
        c = self.config
        self.update_equity(equity)  # refresh state against the latest equity first

        if self.state == RiskState.HALTED:
            return RiskDecision(False, 0.0, 0.0, f"HALTED: {self.halt_reason}", self.state)

        if conviction < c.min_conviction:
            return RiskDecision(False, 0.0, 0.0,
                                f"Conviction {conviction:.2f} < min {c.min_conviction:.2f} — defer",
                                self.state)

        # Conviction-scaled base fraction (min_conviction..1 -> 0..1).
        span = max(1e-9, 1.0 - c.min_conviction)
        conv_norm = min(1.0, max(0.0, (conviction - c.min_conviction) / span))
        size_pct = c.max_position_pct * conv_norm

        # Learned edge multiplier — throttle only (never amplify past the caps).
        em = max(0.0, min(1.0, edge_multiplier))
        size_pct *= em

        # Risk-based cap using the stop distance, if provided.
        if price and stop_price and price > stop_price > 0 and equity > 0:
            risk_per_unit = price - stop_price
            max_risk_dollars = c.max_risk_per_trade_pct * equity
            units = max_risk_dollars / risk_per_unit
            risk_size_pct = (units * price) / equity
            size_pct = min(size_pct, risk_size_pct)

        # Hard caps: position cap and the permanent cash reserve.
        size_pct = min(size_pct, c.max_position_pct, c.max_total_exposure_pct - c.reserve_cash_pct)
        size_pct = max(0.0, size_pct)
        dollar_size = size_pct * equity

        if dollar_size <= 0:
            return RiskDecision(False, 0.0, 0.0, "Sized to zero", self.state)
        reason = "Approved" if em >= 1.0 else f"Approved (edge x{em:.2f})"
        return RiskDecision(True, round(size_pct, 4), round(dollar_size, 2),
                            reason, self.state)

    # -------------------------------------------------------------- reporting
    def status(self, equity: float) -> dict:
        dd = ((self.peak_equity - equity) / self.peak_equity * 100
              if self.peak_equity > 0 else 0.0)
        return {
            "state":           self.state.value,
            "equity":          round(equity, 2),
            "peak_equity":     round(self.peak_equity, 2),
            "effective_floor": round(self.effective_floor, 2),
            "armed":           self.armed,
            "drawdown_pct":    round(dd, 2),
            "halt_reason":     self.halt_reason,
        }
