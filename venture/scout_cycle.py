"""
venture/scout_cycle.py — the daily paper-trading cycle (Phase C driver).

One run = one evidence-gathering pass, PAPER ONLY (see venture/mode.py):
  1. For each watchlist symbol: fetch real data + live news, run the full
     LangGraph debate, and CAPTURE the timestamped signal into the forward-test DB.
  2. SCORE any previous predictions whose horizon has elapsed against realized
     prices (look-ahead-free by construction).
  3. Print the accumulating edge scorecard.

Run it daily/hourly (manually, cron, or n8n later):
    python venture/scout_cycle.py                       # default watchlist
    python venture/scout_cycle.py BTC/USDT AAPL TCS.NS  # custom symbols
"""
from __future__ import annotations

import sys

from data.providers import CCXTDataProvider, YFinanceDataProvider
from eval.forward_test import ForwardTester
from graph.debate import build_debate_runner
from markets.registry import format_money, resolve
from news.providers import RSSNewsProvider
from notify.telegram import TelegramNotifier, format_cycle_summary
from persistence.journal import Journal
from rag.legends import load_legends
from rag.tfidf_store import TfidfKnowledgeStore

DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "AAPL", "NVDA", "RELIANCE.BO", "TCS.NS"]
DB_PATH = "venture/forward_test.db"


def make_provider(symbol: str, news=None, limit: int = 200):
    m = resolve(symbol)
    if m.provider == "ccxt":
        return CCXTDataProvider(symbol, exchange=m.exchange.lower(),
                                timeframe="1h", limit=limit, news_provider=news)
    return YFinanceDataProvider(symbol, period="6mo", interval="1d",
                                news_provider=news)


def latest_price(symbol: str) -> float:
    """Fresh price fetch used to score matured predictions."""
    return make_provider(symbol, limit=10)._closes[-1]


def run_cycle(symbols=None, db_path: str = DB_PATH, horizon_hours: float = 24) -> None:
    symbols = symbols or DEFAULT_SYMBOLS
    ft = ForwardTester(db_path, horizon_sec=horizon_hours * 3600)
    news = RSSNewsProvider()

    print(f"SCOUT CYCLE — paper only — {len(symbols)} symbols, "
          f"horizon {horizon_hours:.0f}h\n")

    # 1) Capture today's signals.
    rows = []
    journal = Journal("venture/journal.db")
    for sym in symbols:
        m = resolve(sym)
        try:
            data = make_provider(sym, news)
            kb = load_legends(TfidfKnowledgeStore())          # legends + live news RAG
            runner = build_debate_runner(data, knowledge_store=kb)
            last = runner.run(sym)[-1]
            snap, report = last["snapshot"], last["report"]
            ft.capture_from_cycle(sym, snap, report)
            row = {"symbol": sym, "exchange": m.exchange, "currency": m.currency,
                   "price": snap.price, "action": report.suggested_action,
                   "conviction": round(last["judged_conviction"], 3),
                   "sentiment": report.sentiment}
            rows.append(row)
            journal.log("signal", sym, row)
            print(f"  {sym:12} [{m.exchange:6}] {format_money(snap.price, m):>14} "
                  f"-> {report.suggested_action:4} conv={last['judged_conviction']:.2f} "
                  f"({report.sentiment})")
        except Exception as e:
            journal.log("error", sym, {"error": f"{type(e).__name__}: {str(e)[:80]}"})
            print(f"  {sym:12} SKIPPED ({type(e).__name__}: {str(e)[:60]})")

    # 2) Score matured predictions against realized prices.
    scored = ft.score_due(price_fn=latest_price)
    print(f"\nScored {scored} matured prediction(s).")

    # 3) The accumulating verdict.
    verdict = ft.report()
    journal.log("cycle", "-", {"symbols": len(symbols), "captured": len(rows),
                               "scored": scored, "verdict": verdict.get("verdict", "")})
    print("\n" + ft.summary())
    ft.close()
    journal.close()

    # 4) Push a Telegram update (no-op unless TELEGRAM_* is configured).
    notifier = TelegramNotifier()
    if notifier.is_configured() and rows:
        footer = f"verdict: {verdict.get('verdict', '')} (scored {verdict.get('directional', 0)})"
        notifier.send(format_cycle_summary(rows, footer=footer))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run_cycle(args or None)
