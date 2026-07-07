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

from billing.tracker import BudgetGuard, UsageTracker, month_to_date
from brain.anthropic_brain import AnthropicBrain
from data.providers import CCXTDataProvider, YFinanceDataProvider
from eval.forward_test import ForwardTester, deadband_from_closes
from graph.debate import build_debate_runner
from markets.registry import format_money, is_market_open, resolve
from news.providers import RSSNewsProvider
from notify.telegram import TelegramNotifier, format_cycle_summary
from persistence.journal import Journal
from rag.legends import load_legends
from rag.tfidf_store import TfidfKnowledgeStore
from security.secrets import get_secret, get_secret_clean

DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "AAPL", "NVDA", "RELIANCE.BO", "TCS.NS"]
DB_PATH = "venture/forward_test.db"


def make_provider(symbol: str, news=None, limit: int = 200):
    m = resolve(symbol)
    if m.provider == "ccxt":
        # No forced exchange -> CCXTDataProvider falls back across venues
        # (Kraken/Coinbase/... before geo-blocked Binance).
        return CCXTDataProvider(symbol, timeframe="1h", limit=limit, news_provider=news)
    return YFinanceDataProvider(symbol, period="6mo", interval="1d",
                                news_provider=news)


def recent_bars(symbol: str) -> list:
    """Fresh (timestamp, close) bars used to score matured predictions on a
    DATED basis — the exit is a bar strictly after the entry bar, never the
    entry price compared to itself."""
    return make_provider(symbol, limit=200).bars()


def run_cycle(symbols=None, db_path: str = DB_PATH, horizon_hours: float = 24) -> None:
    symbols = symbols or DEFAULT_SYMBOLS
    ft = ForwardTester(db_path, horizon_sec=horizon_hours * 3600)
    news = RSSNewsProvider()

    print(f"SCOUT CYCLE — paper only — {len(symbols)} symbols, "
          f"horizon {horizon_hours:.0f}h\n")

    # 1) Capture today's signals.
    rows = []
    journal = Journal("venture/journal.db")

    # Cost policy: Opus LLM brain only for EQUITIES while their market is OPEN;
    # never for crypto (noisy 24/7, poor $/signal). Hard monthly budget cap.
    api_key = get_secret("ANTHROPIC_API_KEY")
    model = get_secret_clean("ANTHROPIC_MODEL", default="claude-opus-4-8") \
        or "claude-opus-4-8"
    try:
        budget_cap = float(get_secret_clean("ANTHROPIC_MONTHLY_BUDGET", default="20") or 20)
    except (TypeError, ValueError):
        budget_cap = 20.0
    tracker = UsageTracker(journal)
    budget = BudgetGuard(journal, budget_cap)
    llm_symbols = 0
    dups = 0

    for sym in symbols:
        m = resolve(sym)
        use_llm = bool(api_key) and m.asset_class == "equity" and is_market_open(m) \
            and budget.allow()
        try:
            data = make_provider(sym, news)
            kb = load_legends(TfidfKnowledgeStore())          # legends + live news RAG
            brain = AnthropicBrain(model=model, tracker=tracker, budget=budget) \
                if use_llm else None
            llm_symbols += 1 if use_llm else 0
            runner = build_debate_runner(data, knowledge_store=kb, llm_brain=brain)
            last = runner.run(sym)[-1]
            snap, report = last["snapshot"], last["report"]
            # Anchor the prediction to the bar the desk actually saw, and set a
            # volatility-scaled dead-band so a flat tape isn't scored as a miss.
            bar_ts = data.latest_bar_ts()
            band = deadband_from_closes(getattr(data, "_closes", []), ft.horizon,
                                        getattr(data, "bar_seconds", None))
            pid = ft.capture_from_cycle(sym, snap, report, bar_ts=bar_ts, deadband=band)
            captured = pid != -1
            dups += 0 if captured else 1
            venue = getattr(data, "source_exchange", m.exchange)   # actual crypto venue
            row = {"symbol": sym, "exchange": venue, "currency": m.currency,
                   "price": snap.price, "action": report.suggested_action,
                   "conviction": round(last["judged_conviction"], 3),
                   "sentiment": report.sentiment, "brain": model if use_llm else "heuristic",
                   "captured": captured}
            if captured:
                rows.append(row)
            journal.log("signal", sym, row)
            mark = "[LLM]" if use_llm else "[heuristic]"
            mark += "" if captured else " [dup-skip]"
            print(f"  {sym:12} [{venue:8}] {format_money(snap.price, m):>14} "
                  f"-> {report.suggested_action:4} conv={last['judged_conviction']:.2f} "
                  f"({report.sentiment}) band={band*100:.2f}%  {mark}")
        except Exception as e:
            journal.log("error", sym, {"error": f"{type(e).__name__}: {str(e)[:80]}"})
            print(f"  {sym:12} SKIPPED ({type(e).__name__}: {str(e)[:60]})")

    # 2) Score matured predictions against realized DATED bars (look-ahead-free).
    scored = ft.score_due(bars_fn=recent_bars)
    print(f"\nCaptured {len(rows)} new signal(s) ({dups} dup-skip), "
          f"scored {scored} matured prediction(s).")

    # 3) The accumulating verdict.
    verdict = ft.report()
    journal.log("cycle", "-", {"symbols": len(symbols), "captured": len(rows),
                               "dups": dups, "scored": scored,
                               "verdict": verdict.get("verdict", ""),
                               "llm_symbols": llm_symbols, "model": model})
    print("\n" + ft.summary())

    # Billing readout (month-to-date, self-tracked from response.usage).
    mtd = month_to_date(journal)
    cap_str = f"${budget_cap:.2f}" if budget_cap > 0 else "unlimited"
    print(f"\nAPI spend (MTD {mtd['month']}): ${mtd['cost_usd']:.4f} / {cap_str} "
          f"| {mtd['calls']} calls | {llm_symbols} LLM symbol(s) this cycle "
          f"| model {model}")

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
