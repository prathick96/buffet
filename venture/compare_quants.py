"""
venture/compare_quants.py — statistical Quant vs trained PPO Quant, same debate.

Fetches real ccxt data once, then runs the LangGraph debate twice (identical
except the Quant node) and prints both scorecards vs buy-and-hold. Honest A/B of
whether the RL policy actually helps.

Run:  python venture/compare_quants.py BTC/USDT
(needs a trained model: python venture/train/train_rl.py BTC/USDT)
"""
from __future__ import annotations

import os
import sys

from data.providers import CCXTDataProvider, MockDataProvider
from engines.quant import QuantEngine
from engines.rl_quant import RLQuantEngine
from graph.debate import ASSERTIVE_JUDGE, build_debate_runner
from rag.tfidf_store import TfidfKnowledgeStore

_ROOT = os.path.dirname(os.path.abspath(__file__))


def _run(closes, symbol, quant, label):
    data = MockDataProvider({symbol: closes})
    runner = build_debate_runner(data, knowledge_store=TfidfKnowledgeStore(),
                                 quant_engine=quant, judge_config=ASSERTIVE_JUDGE)
    results = runner.run(symbol)
    m = results[-1]["update"].metrics
    trades = sum(1 for r in results if r["fill"].executed)
    src = results[-1]["quant"].get("source", "?")
    print(f"  {label:10} return {m['return_pct']:+6.2f}%  | trades {trades:3d} "
          f"| maxDD {m['drawdown_pct']:4.2f}% | quant={src} | risk={runner.risk.state.value}")
    return m["return_pct"]


def main(symbol: str = "BTC/USDT", limit: int = 300):
    print(f"Fetching {limit} x 1h bars for {symbol} from Binance...")
    closes = CCXTDataProvider(symbol, exchange="binance", timeframe="1h", limit=limit)._closes
    bh = (closes[-1] / closes[0] - 1) * 100
    model_path = os.path.join(_ROOT, "models", f"ppo_quant_{symbol.replace('/', '')}.zip")

    print(f"\nA/B over {len(closes)} bars (assertive judge):")
    _run(closes, symbol, QuantEngine(), "STAT quant")
    rl = RLQuantEngine(model_path=model_path)
    print(f"  (PPO model loaded: {rl.model is not None})")
    _run(closes, symbol, rl, "PPO quant")
    print(f"  {'BUY & HOLD':10} return {bh:+6.2f}%")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT")
