"""
venture/rag/legends.py — the Trading Legends knowledge base (RAG seed).

Original summaries of publicly documented strategies from legendary investors
(ported from the legacy TRADING_LEGENDS_KB). Ingest into any KnowledgeStore so
the Analyst/brain can retrieve "what would Buffett/Dalio/PTJ do here?".

    from rag.legends import load_legends
    from rag.tfidf_store import TfidfKnowledgeStore
    kb = load_legends(TfidfKnowledgeStore())

License: original summaries (not copyrighted texts) -> commercial-clean.
"""
from __future__ import annotations

TRADING_LEGENDS = [
    {"legend": "Warren Buffett", "strategy": "Value Investing", "framework": (
        "Buy wonderful companies at fair prices. Focus on intrinsic value and future "
        "cash flows. Metrics: P/E below market, ROE > 15% consistently, low debt, strong "
        "moat. Be fearful when others are greedy and greedy when others are fearful. "
        "Signals: market crash > 20% = accumulate quality; market P/E > 30 = reduce.")},
    {"legend": "Jesse Livermore", "strategy": "Trend Following / Momentum", "framework": (
        "The trend is your friend until it ends. Never average down; cut losses fast; let "
        "winners run and pyramid. Volume confirms moves. Signals: break of 52-week high on "
        "volume = buy; three lower highs = trend reversal; news breakout on extreme volume "
        "= enter in the direction of the move.")},
    {"legend": "Paul Tudor Jones", "strategy": "Macro Trading", "framework": (
        "Risk <= 1-2% per trade; demand >= 5:1 reward:risk; play great defense. Be flexible. "
        "Signals: yield-curve inversion = reduce equity risk; Fed hiking = risk-off; strong "
        "dollar = bearish crypto/commodities; VIX > 30 = panic, consider tactical longs.")},
    {"legend": "Ray Dalio", "strategy": "All Weather / Risk Parity", "framework": (
        "Diversify across assets that react differently to growth/inflation regimes; balance "
        "risk, not capital. Signals: rising growth + rising inflation = commodities/TIPS; "
        "rising growth + falling inflation = equities; stagflation = gold/commodities; "
        "falling growth + falling inflation = bonds/cash.")},
    {"legend": "George Soros", "strategy": "Reflexivity / Macro Speculation", "framework": (
        "Reflexivity: biased perceptions move fundamentals in a feedback loop. Find the "
        "prevailing trend and its flaw; ride it until the flaw bites. When right, go big; "
        "when uncertain, cut size. A good position is profitable quickly.")},
    {"legend": "Peter Lynch", "strategy": "Growth at Reasonable Price (GARP)", "framework": (
        "Invest in what you know. PEG (P/E / growth) < 1.0 = undervalued growth. Look for "
        "ten-baggers in boring industries. Signals: insider buying = bullish; rising "
        "same-store sales = healthy growth; falling debt with rising earnings = compounder.")},
]


def legend_documents() -> list:
    """Return [(text, metadata)] ready to ingest into a KnowledgeStore."""
    docs = []
    for legend in TRADING_LEGENDS:
        text = (f"Trading legend {legend['legend']} — {legend['strategy']}. "
                f"{legend['framework']}")
        docs.append((text, {"legend": legend["legend"], "strategy": legend["strategy"],
                            "source": "trading_legends_kb"}))
    return docs


def load_legends(store):
    """Ingest all legend docs into `store` (any KnowledgeStore). Returns the store."""
    for text, meta in legend_documents():
        store.ingest(text, meta)
    return store
