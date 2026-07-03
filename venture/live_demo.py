"""
venture/live_demo.py — full LIVE integration:
  1) real Binance OHLCV (ccxt) replayed through the LangGraph debate,
  2) live RSS news (keyless) ingested into a TF-IDF RAG store,
  3) a statistical Quant vote + Bull/Bear/Judge debate per bar,
  4) a buy-and-hold benchmark, and
  5) ONE local-Claude-brain qualitative read on the latest bar.

Run:  python venture/live_demo.py                 (BTC/USDT 1h, with brain)
      python venture/live_demo.py --no-brain ETH/USDT
      python venture/live_demo.py AAPL             (equity via yfinance)
"""
from __future__ import annotations

import os
import sys

from brain.claude_brain import ClaudeBrain
from data.providers import CCXTDataProvider, YFinanceDataProvider
from engines.rl_quant import RLQuantEngine
from graph.debate import build_debate_runner
from news.providers import RSSNewsProvider
from rag.tfidf_store import TfidfKnowledgeStore

_ROOT = os.path.dirname(os.path.abspath(__file__))


def _make_provider(symbol: str, news):
    if "/" in symbol:                      # crypto pair -> ccxt/Binance
        return CCXTDataProvider(symbol, exchange="binance", timeframe="1h",
                                limit=200, news_provider=news)
    return YFinanceDataProvider(symbol, period="6mo", interval="1d",
                                news_provider=news)        # equity -> yfinance


def main(symbol: str = "BTC/USDT", use_brain: bool = True, debate_llm: bool = False,
         use_rl: bool = False, use_faiss: bool = False) -> None:
    news = RSSNewsProvider()
    headlines = news(symbol)
    print(f"Live news for {symbol}: {len(headlines)} headlines"
          + (f'  e.g. "{headlines[0]["title"]}"' if headlines else ""))

    from markets.registry import resolve
    cur = resolve(symbol).currency_symbol or "$"
    print(f"Fetching market data for {symbol} [{resolve(symbol).exchange}]...")
    data = _make_provider(symbol, news)
    closes = data._closes
    print(f"  {len(closes)} bars (latest {cur}{closes[-1]:,.2f})")

    # Optional upgrades: semantic FAISS RAG and the trained PPO quant.
    if use_faiss:
        from rag.faiss_store import FaissKnowledgeStore
        knowledge = FaissKnowledgeStore()
        print("  RAG: FAISS semantic (MiniLM)")
    else:
        knowledge = TfidfKnowledgeStore()
        print("  RAG: TF-IDF")

    quant = None
    if use_rl:
        mp = os.path.join(_ROOT, "models", f"ppo_quant_{symbol.replace('/', '')}.zip")
        quant = RLQuantEngine(model_path=mp)
        print(f"  Quant: PPO ({'loaded' if quant.model else 'fallback-stat'})")

    runner = build_debate_runner(data, knowledge_store=knowledge, quant_engine=quant)
    results = runner.run(symbol)
    m = results[-1]["update"].metrics
    trades = sum(1 for r in results if r["fill"].executed)
    bh = (closes[-1] / closes[0] - 1) * 100

    print("\n" + "=" * 56)
    print(f"LIVE DEBATE RUN - {symbol}")
    print("=" * 56)
    print(f"  Bars / trades    : {len(results)} / {trades}")
    print(f"  Strategy return  : {m['return_pct']:+.2f}%   (equity {cur}{m['equity']})")
    print(f"  Buy & hold       : {bh:+.2f}%")
    print(f"  Max drawdown     : {m['drawdown_pct']:.2f}%")
    print(f"  Risk state       : {runner.risk.state.value} "
          f"(armed={runner.risk.armed}, floor=${runner.risk.effective_floor})")
    print(f"  RAG docs ingested: {len(runner.knowledge)}")
    print(f"  Latest quant vote: {results[-1]['quant']}")
    print(f"  Latest judge     : {results[-1]['judge_note']}")
    print("=" * 56)

    if use_brain:
        print("\nLocal Claude brain read on the latest bar (~30s, no API key)...")
        read = ClaudeBrain()(results[-1]["snapshot"])
        print(f"  Sentiment : {read['sentiment']}  (score {read['score']:+.2f})")
        print(f"  Rationale : {read['rationale']}")
        if read.get("key_factors"):
            print(f"  Factors   : {', '.join(read['key_factors'])}")

    if debate_llm:
        from brain.claude_brain import bear_brain, bull_brain
        from graph.debate import JudgeConfig
        snap = results[-1]["snapshot"]
        print("\nLLM Bull vs Bear debate on the latest bar (~60s, two personas)...")
        b = bull_brain()(snap)
        r = bear_brain()(snap)
        print(f"  BULL ({b['score']:+.2f}): {b['rationale']}")
        print(f"  BEAR ({r['score']:+.2f}): {r['rationale']}")
        judged, note = JudgeConfig().evaluate(
            results[-1]["report"].conviction, max(0.0, b["score"]),
            max(0.0, -r["score"]), results[-1]["quant"]["score"])
        print(f"  JUDGE: {note}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # ₹ / — safe on Windows
    except Exception:
        pass
    args = sys.argv[1:]
    use_brain = "--no-brain" not in args
    debate_llm = "--debate-llm" in args
    syms = [a for a in args if not a.startswith("--")]
    main(symbol=syms[0] if syms else "BTC/USDT", use_brain=use_brain, debate_llm=debate_llm,
         use_rl="--rl" in args, use_faiss="--faiss" in args)
