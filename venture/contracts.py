"""
venture/contracts.py — typed messages passed between engines.

The engines are decoupled: each one is a pure(ish) function of these dataclasses.
That makes every engine independently testable and lets a LangGraph graph drive
the same nodes later without changing them. (Agentic RAG = engines + a shared
KnowledgeStore they read/write — see venture/rag/.)

License: original code, stdlib only -> commercial-clean. Python 3.10+.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MarketSnapshot:
    """Produced by the Scout: the state of one symbol + retrieved RAG context."""
    symbol: str
    price: float
    history: list = field(default_factory=list)            # recent prices
    indicators: dict = field(default_factory=dict)         # sma, momentum, ...
    news: list = field(default_factory=list)               # [{title, summary, source}]
    retrieved_context: list = field(default_factory=list)  # RAG hits (strings)
    timestamp: str = field(default_factory=_now)


@dataclass
class AnalysisReport:
    """Produced by the Analyst: quantitative + qualitative read on the snapshot."""
    symbol: str
    technical_score: float          # -1..1 (bearish..bullish)
    sentiment: str                  # BULLISH | BEARISH | NEUTRAL
    sentiment_score: float          # -1..1
    conviction: float               # 0..1 (blended confidence)
    suggested_action: str           # BUY | SELL | HOLD
    stop_price: Optional[float] = None
    rationale: str = ""
    key_factors: list = field(default_factory=list)
    timestamp: str = field(default_factory=_now)


@dataclass
class TradeDecision:
    """Produced by the Decision engine after RiskEngine gating/sizing."""
    symbol: str
    action: str                     # BUY | SELL | HOLD
    approved: bool
    size_pct: float
    dollar_size: float
    conviction: float
    reason: str
    risk_state: str                 # ACTIVE | HALTED
    stop_price: Optional[float] = None
    timestamp: str = field(default_factory=_now)


@dataclass
class Fill:
    """Produced by the Execution engine: the realized (paper) order."""
    symbol: str
    action: str
    executed: bool
    price: float = 0.0
    units: float = 0.0
    dollar: float = 0.0
    fee: float = 0.0
    reason: str = ""
    timestamp: str = field(default_factory=_now)


@dataclass
class LearningUpdate:
    """Produced by the Learning engine: running metrics + adaptation notes."""
    cycle: int
    equity: float
    metrics: dict = field(default_factory=dict)
    notes: str = ""
    timestamp: str = field(default_factory=_now)
