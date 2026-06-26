"""
venture/engines/quant.py — the Quant (statistical voice in the debate).

Single job: an independent, math-first read on a symbol — trend-following blended
with mean-reversion (z-score) — producing a vote the Judge weighs alongside the
Bull and Bear. Nobel-mathematician energy: signals from statistics, not headlines.

This is the seam for the notebook's PPO/RL model: a `RLQuantEngine` can implement
the same `run(snapshot) -> vote` interface (vote = {"action","score","rationale"})
and slot straight into the debate as the Quant node.

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

import math
from statistics import mean, pstdev

from engines.base import Engine


class QuantEngine(Engine):
    name = "quant"

    def __init__(self, fast: int = 10, slow: int = 30, momentum_sensitivity: float = 80.0,
                 trend_weight: float = 0.6):
        self.fast = fast
        self.slow = slow
        self.k = momentum_sensitivity
        self.trend_weight = trend_weight

    def run(self, snap) -> dict:
        hist = snap.history or []
        price = snap.price
        if len(hist) < self.slow:
            return {"action": "HOLD", "score": 0.0,
                    "rationale": "insufficient history", "factors": []}

        fast_ma = mean(hist[-self.fast:])
        slow_ma = mean(hist[-self.slow:])
        sd = pstdev(hist[-self.slow:]) or 1e-9

        trend = math.tanh((price - fast_ma) / fast_ma * self.k)   # -1..1
        z = (price - slow_ma) / sd                                # std devs from mean
        mean_rev = -math.tanh(z / 2.0)                            # overbought -> negative

        score = max(-1.0, min(1.0, self.trend_weight * trend
                              + (1 - self.trend_weight) * mean_rev))
        action = "BUY" if score > 0.2 else "SELL" if score < -0.2 else "HOLD"
        regime = "overbought" if z > 1 else "oversold" if z < -1 else "neutral"
        return {
            "action": action,
            "score": round(score, 3),
            "rationale": f"trend={trend:+.2f}, z-score={z:+.2f} ({regime})",
            "factors": [f"fast{self.fast}MA", f"slow{self.slow}MA", "z-score"],
        }
