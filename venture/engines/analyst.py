"""
venture/engines/analyst.py — the Analyst (quant + qualitative).

Single job: turn a MarketSnapshot into an AnalysisReport — a technical score, a
sentiment read, and a blended conviction. Rigorous + intelligent: weigh the
evidence, penalize disagreement between the numbers and the narrative.

The qualitative read is pluggable via `llm_brain` — a callable(snapshot) -> dict
that the local Claude Code brain (or FinGPT) fills in Phase 2/3. When absent, a
deterministic keyword sentiment keeps the loop fully offline + testable.
"""
from __future__ import annotations

import math

from contracts import AnalysisReport, MarketSnapshot
from engines.base import Engine

_POS = ("surge", "rally", "record", "beat", "bullish", "approval", "inflows", "soars", "tops")
_NEG = ("crash", "plunge", "ban", "hack", "lawsuit", "bearish", "selloff", "outflows", "probe")


class AnalystEngine(Engine):
    name = "analyst"

    def __init__(self, llm_brain=None, momentum_sensitivity: float = 100.0):
        self.llm_brain = llm_brain
        self.k = momentum_sensitivity

    def run(self, snap: MarketSnapshot) -> AnalysisReport:
        momentum = snap.indicators.get("momentum", 0.0) or 0.0
        technical_score = math.tanh(momentum * self.k)   # -1..1

        if self.llm_brain is not None:
            q = self.llm_brain(snap) or {}
            sentiment = q.get("sentiment", "NEUTRAL")
            s_score = float(q.get("score", 0.0))
            rationale = q.get("rationale", "")
            factors = list(q.get("key_factors", []))
        else:
            sentiment, s_score, rationale, factors = self._naive_sentiment(snap)

        conviction = self._blend(technical_score, s_score)

        if technical_score > 0 and s_score >= 0:
            action = "BUY"
        elif technical_score < 0:
            action = "SELL"
        else:
            action = "HOLD"

        return AnalysisReport(
            symbol=snap.symbol,
            technical_score=round(technical_score, 3),
            sentiment=sentiment,
            sentiment_score=round(s_score, 3),
            conviction=round(conviction, 3),
            suggested_action=action,
            stop_price=snap.indicators.get("sma"),
            rationale=rationale,
            key_factors=factors,
        )

    def _naive_sentiment(self, snap: MarketSnapshot):
        text = " ".join(n.get("title", "") for n in snap.news).lower()
        text += " " + " ".join(snap.retrieved_context).lower()
        pos = sum(w in text for w in _POS)
        neg = sum(w in text for w in _NEG)
        score = max(-1.0, min(1.0, (pos - neg) * 0.3))
        sentiment = "BULLISH" if score > 0.1 else "BEARISH" if score < -0.1 else "NEUTRAL"
        return sentiment, score, f"News tilt (pos={pos}, neg={neg})", []

    def _blend(self, technical: float, sentiment: float) -> float:
        agree = (technical >= 0) == (sentiment >= 0)
        conviction = 0.6 * abs(technical) + 0.3 * abs(sentiment) + (0.1 if agree else 0.0)
        return max(0.0, min(1.0, conviction))
