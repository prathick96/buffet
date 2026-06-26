"""
venture/engines/learning.py — the Learning engine.

Single job: record every cycle, track the equity curve + running metrics, and
serve as the hook where adaptation lands — RL (PPO) retraining, strategy
hyper-tuning, and LoRA sentiment fine-tuning (Phase 3). For now it maintains an
honest live scorecard so we can see whether the agents are compounding or
drifting toward the floor.
"""
from __future__ import annotations

from contracts import Fill, LearningUpdate
from engines.base import Engine


class LearningEngine(Engine):
    name = "learning"

    def __init__(self):
        self.equity_curve: list = []
        self.fills: list = []
        self.cycle: int = 0

    def run(self, equity: float, fill: Fill) -> LearningUpdate:
        self.cycle += 1
        self.equity_curve.append(equity)
        if fill.executed:
            self.fills.append(fill)

        start = self.equity_curve[0]
        peak = max(self.equity_curve)
        drawdown = (peak - equity) / peak * 100 if peak > 0 else 0.0
        ret = (equity / start - 1) * 100 if start > 0 else 0.0

        metrics = {
            "cycle": self.cycle,
            "equity": round(equity, 2),
            "return_pct": round(ret, 2),
            "drawdown_pct": round(drawdown, 2),
            "peak_equity": round(peak, 2),
            "executed_trades": len(self.fills),
        }
        return LearningUpdate(cycle=self.cycle, equity=round(equity, 2),
                              metrics=metrics, notes=fill.reason)
