# TradingAgent → Wealth-Management Venture — BLUEPRINT

> Living document. Conclusion of the end-to-end analysis requested 2026-06-26.
> Supersedes ad-hoc notes; update it as decisions change.

---

## 1. Mission & operative goal

Build a **tested, well-trained, multi-agent trading system** for equities + crypto that
watches markets like a hawk, reasons like a quant desk, and compounds a tiny stake on
**paper** with disciplined risk control. If it proves edge on paper, it may become a
**commercial venture** — so license-cleanliness is a hard constraint from day one.

**Operative target (updated 2026-07-02):** the **chessboard ladder** — $20 → $250,000
over ~5 years (equivalently $50 → $625k; both ≈ **12,500× ≈ 13.6 doublings**). One square
= one doubling, **earned by proven edge before advancing**, ≈ one doubling per ~4.4 months
if on schedule. Floor rule unchanged: back out at the initial-capital floor; never zero out.
Honest math: 12,500×/5yr ≈ +17%/month sustained — beyond any documented track record
(Medallion ≈ 39–66%/yr). We treat the ladder as the *training structure* and the floor as
law; the venture's commercial value is the proven infrastructure + verified track record,
whatever multiplier is actually achieved. After ~5 years of personal training/trading, the
goal is to market the app commercially as a trustworthy AI-trading venture.

**Honest KPI.** $50 → $100k is ~**2,000×**. No system guarantees that, and "guaranteed
revenue" does not exist. The real success metric is **demonstrable, risk-adjusted edge +
survival on paper** — Sharpe, max drawdown, hit-rate, and staying above the floor — *not*
hitting a dollar number on a deadline. We chase the ceiling; we enforce the floor.
Realistic skilled-operator returns are ~1–3%/month with 5–10% drawdowns (per the user's
own research). Treat $100k as a stretch ceiling reached only by compounding + reinvestment
over a long horizon.

---

## 2. Governing constraint: commercial license compatibility

Because this may become a venture, we only **vendor** (copy/embed/fork into our product)
code under **permissive** licenses (MIT / Apache-2.0 / BSD). **Copyleft** code (AGPL/GPL,
and LGPL with conditions) is used only **as an external service/API client** or **for
internal research** — never embedded into the closed product.

### Verified license audit (web-checked 2026-06)

| Repo | License | Vendor into product? | Verdict / how we use it |
|---|---|---|---|
| **crawl4ai** (unclecode) | Apache-2.0 (+attribution) | ✅ Yes | **Primary scraper** — self-host, embed freely |
| **TradingAgents** (TauricResearch) | **Apache-2.0** ✓ | ✅ Yes | ⚠️ See §3 — *commercial use IS allowed* |
| **Firecrawl** | **AGPL-3.0** core (SDK MIT) | ❌ No (engine) | Use **hosted API as a client** only; do not embed engine |
| **OpenBB Platform** | **AGPL-3.0** (commercial lic. avail.) | ❌ No | **Internal research** only, or buy commercial license |
| Freqtrade | MIT | ✅ Yes | Execution + backtest + FreqAI (crypto) |
| FinRL | MIT | ✅ Yes | Deep-RL trading envs |
| CCXT | MIT | ✅ Yes | Exchange layer (already in use) |
| gs-quant (Goldman) | Apache-2.0 | ✅ Yes | Institutional risk/quant reference |
| PyPortfolioOpt | MIT | ✅ Yes | Portfolio optimization |
| Riskfolio-Lib | BSD-3 | ✅ Yes | Risk parity / advanced risk |
| LangGraph | MIT | ✅ Yes | **Agent orchestration core** |
| pandas-ta / TA-Lib | MIT / BSD-2 | ✅ Yes | Indicators (already in use) |
| Nautilus Trader | **LGPL-3.0** | ⚠️ Conditional | Optional later; modifications to *it* must be shared |
| FinGPT / FinRobot (AI4Finance) | MIT* | ✅ Yes | Finance LLM / sentiment (*re-verify at wire-in) |
| Wealthfolio (afadil) | MIT* | ✅ Yes | Portfolio-tracker UI (*re-verify at wire-in) |

\* Permissive licenses not personally web-verified yet are re-checked at integration time.

---

## 3. Correction on Tauric / TradingAgents

You asked to drop Tauric because "we can't commercialize anything built around it."
**The license check says the opposite:** TradingAgents is **Apache-2.0** — one of the most
commercial-friendly licenses there is (same family as gs-quant). The "for research / not
financial advice" line in its README is a **liability disclaimer**, present in virtually
every trading repo (including ones we keep) — it does **not** restrict commercialization.

It is also *exactly* your multi-agent vision: fundamental/sentiment/technical analysts +
**bull vs. bear debate** + a **risk-management team** + a trader, all built on **LangGraph**
(which we already chose). **DECIDED: Tauric is KEPT** — used as the architecture reference
for our trader + portfolio-tracker agent graph, and as a dependency where useful.

---

## 4. Conclusive tech stack (decided)

| Layer | Choice | License posture |
|---|---|---|
| **Agent orchestration** | **LangGraph** (debate graph) | MIT ✅ |
| **Automation/scheduling** | n8n (parked — wire later) | — |
| **LLM brain** | **Hybrid:** local **Claude Code CLI** (reasoning) + RAG (legends KB + live news) + small **LoRA fine-tune** for sentiment/scoring | clean |
| **Reasoning model** | Claude (local CLI, no API key/billing) — already wired in `LLMSignalAgent` | clean |
| **RL brain** | PPO (stable-baselines3) → **FinRL** envs | MIT ✅ |
| **Execution + backtest (crypto)** | **Freqtrade** (+ FreqAI), CCXT | MIT ✅ |
| **Execution (equity)** | Alpaca SDK (already in use) | clean |
| **Backtesting/analytics** | Freqtrade backtester + vectorbt | MIT/Apache ✅ |
| **Indicators** | pandas-ta / TA-Lib | MIT/BSD ✅ |
| **Risk & sizing** | **`venture/risk_engine.py`** (ours) + PyPortfolioOpt / Riskfolio-Lib | original/MIT/BSD ✅ |
| **Web/news ingestion** | **crawl4ai** (self-host) + Firecrawl **API** + NewsAPI + CoinGecko | Apache ✅ / API |
| **Financial data (research)** | OpenBB (internal only) + yfinance | AGPL-internal / clean |
| **Sentiment LLM** | FinGPT / FinRobot | MIT ✅ |
| **Portfolio tracking UI** | Wealthfolio (optional) or Streamlit/Dash | MIT ✅ |
| **Persistence** | Supabase (already in use) | clean |

> We are **not** pip-installing the heavy frameworks yet — they're staged per phase (§6) to
> avoid bloating the environment before each is actually needed.

---

## 5. Agent roster (functional roles + the values you asked for)

The personalities you described are translated into **professional, value-driven roles**
(role = function, not stereotype). Each agent embodies an elite competency and they work
as one desk, coordinated by LangGraph.

**Product DNA (the three trait-pairs that govern every agent):**
**vicious + smart** · **robust + intelligent** · **ruthless + money-hungry** — meaning
relentless and opportunistic in *finding* edge, rigorous and resilient in *validating* it,
and singularly focused on compounding capital — all inside the risk floor and legal lines.

| Agent | Mandate | Embodied values / "superpower" | Tools |
|---|---|---|---|
| **Scout** (Intelligence desk) | Scan markets + news on a schedule; catch the drift early | Relentless curiosity, speed — *catch it before it disappears* | crawl4ai, Firecrawl API, NewsAPI, CoinGecko |
| **Quant** (Analyst) | Statistical signal generation, hypothesis testing, backtests | Nobel-grade mathematical rigor; evidence over headlines | FinRL, Freqtrade/vectorbt, pandas-ta, gs-quant |
| **Analyst (Fundamental/Sentiment)** | Read the "why" — fundamentals, narrative, sentiment | Contextual judgment | Claude brain + RAG, FinGPT |
| **Bull vs. Bear** (debate pair) | Argue both sides of every thesis to stress-test it | Adversarial truth-seeking | LangGraph debate |
| **Controller** (Risk & Accounting) | Enforce the **$50 floor**, sizing, drawdown, exposure, exact P&L ledger | Meticulous discipline; capital preservation; *never zero out* | `risk_engine.py`, PyPortfolioOpt, existing SecurityAgent |
| **Portfolio Manager** (the decider) | Arbitrate the debate, size conviction, own the P&L | Decisive, bold-but-bounded ownership | evolved FusionEngine |
| **Execution** (Trader) | Best execution, slippage-aware order placement | Precision, speed | Freqtrade, CCXT, Alpaca |
| **Compliance guard** | Keep every action inside legal lines | Integrity, non-negotiable | rules layer |

Ruthless = **disciplined and relentless**, not reckless or fraudulent. Belfort/Mehta are
cautionary tales, not templates — the conviction goes into precision, the lines stay legal.

---

## 6. Phased roadmap

**Phase 0 — Harden the foundation (IN PROGRESS, chosen first).**
- [x] LLM brain → local Claude Code CLI (done, tested).
- [x] **Risk Engine** with $50-floor model + tests (done — `venture/risk_engine.py`, 8/8).
- [x] Walk-forward **backtest harness** with Sharpe/Sortino/maxDD/hit-rate/survival metrics,
      wired through the RiskEngine (done — `venture/backtest.py`, 3/3 tests).
- [x] Dependency manifest for the approved stack (`venture/requirements.txt`).
- [ ] Wire Risk Engine into the orchestrator's decision path (before `PaperPortfolio.buy`).
- [ ] Feed real OHLCV (ccxt/yfinance) into the harness + benchmark vs. buy-and-hold.

**Phase 1 — Information edge.**
- [x] Real market data live: `CCXTDataProvider` (Binance) + `YFinanceDataProvider` —
      validated on 200×1h BTC/USDT (engine -0.05% vs buy-and-hold -8.11%: capital preserved).
- [x] Local Claude brain live in the Analyst seam (`brain/claude_brain.py`) — real
      qualitative read on live data; cached per (symbol, hour).
- [x] News/web ingestion LIVE via keyless **RSS** (Cointelegraph/CoinDesk/Yahoo) → RAG;
      NewsAPI optional; crawl4ai/Firecrawl/OpenBB stubs for deeper sources. Verified: the
      Claude brain reasons over scraped headlines (cited BitGo layoffs, options hedging…).
- [x] RAG upgraded to **TF-IDF cosine** (stdlib) AND **FAISS semantic (MiniLM) LIVE**
      (`rag/faiss_store.py`) — verified semantic match ("ETF" ⇄ "exchange-traded fund").

**Phase 2 — Multi-agent debate.**
- [x] LangGraph debate live: Scout→Analyst→**Quant→Bull→Bear→Judge**→Decision→Execution
      →Learning (`graph/debate.py`). Quant = statistical voice (`engines/quant.py`); Bull/Bear
      pluggable to Claude personas. RiskEngine floor still overrides. Tests 2/2.
- [x] Tunable **Judge** (`JudgeConfig`, conservative/assertive presets) — testable.
- [x] Claude **Bull/Bear personas** wired (`bull_brain()`/`bear_brain()`, `--debate-llm`).
- [x] `RLQuantEngine` (graceful fallback) + `train/train_rl.py` PPO pipeline.
- [x] **PPO TRAINED** on 1000h real BTC/USDT (`models/ppo_quant_BTCUSDT.zip`) and LIVE as the
      Quant (`source=rl_ppo`). A/B (`compare_quants.py`): PPO -0.53% vs stat -0.72% vs B&H -10.69%.
- [ ] Scale RL (more steps/features/symbols); add Controller as an explicit debate node.

**Phase 3 — Train & tune.** FinRL/PPO retraining; LoRA sentiment fine-tune; walk-forward
validation; paper-trade the $50 journey and measure edge.

**Phase 4 — Scale & (optional) productize.** Equity + crypto multi-strategy; Wealthfolio/
dashboard; only then consider the venture/SaaS path on the permissive-license core.

---

## 7. The $50-floor risk model (as built)

`venture/risk_engine.py` implements two protective lines because you cannot both *start at
$50* and *never dip below $50*:

- **hard_floor = $45** — "don't zero out." Hard liquidation + halt.
- **back_out_level = $50** — arms only after **+20% ($60)**, then trails to lock in the
  original stake; falling back to $50 halts trading.
- Plus: 25% max drawdown halt, ≤2% risk/trade (with stop), ≤25% per position, no leverage,
  5% permanent cash reserve, conviction-gated entries (defer below 0.55).

All configurable via `RiskConfig`. **8/8 tests pass.** ⚠️ *Confirm the $45/$50/+20% numbers
match your intent (see §8).*

---

## 8. Decisions (resolved 2026-06-26)

1. **Tauric/TradingAgents** — ✅ KEPT (Apache-2.0). Architecture reference for the trader +
   portfolio tracker, and a dependency where useful.
2. **Floor params** — ✅ LOCKED: hard_floor $45 / back_out $50 / arm at +20%.
3. **Scraping/data posture** — ✅ crawl4ai (embed) + Firecrawl (API) + OpenBB (research-only)
   + NewsAPI + CoinGecko; commercial-clean core preserved.
4. **Full toolbelt approved** — FinRL, vectorbt, pandas-ta, nautilus_trader, FinGPT, FinRobot,
   local Claude brain, TradingAgents, LangGraph, CrewAI/AutoGen, PyPortfolioOpt, Riskfolio-Lib,
   ccxt, freqtrade, Alpaca, gs-quant, Wealthfolio, yfinance — staged per phase (§6).
5. **Pending** — starred-chat extra context (fold in when pasted).

---

## 9. Engine architecture (implemented — `venture/`)

The 6,443-line notebook is being decomposed into **single-responsibility engines**
that pass typed messages (`venture/contracts.py`) and form an autonomous loop. The
notebook stays untouched; logic is ported into engines over the phases.

```
            ┌──────────── shared RAG store (venture/rag) ───────────┐
            │                                                        │
  bar ─▶ ScoutEngine ─▶ AnalystEngine ─▶ DecisionEngine ─▶ ExecutionEngine ─▶ LearningEngine ─┐
            (gather       (quant +         (fuse + RiskEngine   (paper/live      (metrics +     │
             + RAG)        sentiment)       gating/sizing,        order)          adaptation)    │
                                            floor overrides)                                     │
            └───────────────────────────── next bar ◀────────────────────────────────────────┘
```

| Engine | File | One job | Contract out |
|---|---|---|---|
| Scout | `engines/scout.py` | gather price/news + RAG ingest/retrieve | `MarketSnapshot` |
| Analyst | `engines/analyst.py` | technical + sentiment → conviction (LLM-pluggable) | `AnalysisReport` |
| Decision | `engines/decision.py` | fuse + RiskEngine gate/size; **floor overrides all** | `TradeDecision` |
| Quant | `engines/quant.py` | math-first vote: trend + mean-reversion z-score | vote dict |
| Execution | `engines/execution.py` | realize the (paper) order | `Fill` |
| Learning | `engines/learning.py` | running scorecard + adaptation hook | `LearningUpdate` |

Supporting: `contracts.py` (messages), `portfolio.py` (clean paper portfolio),
`data/providers.py` (Mock + **CCXT/Binance + yfinance, live**), `news/providers.py`
(**RSS live + keyless**; NewsAPI; crawl4ai/Firecrawl stubs), `rag/` (`store.py` keyword,
**`tfidf_store.py` cosine (default)**, `faiss_store.py` lazy semantic), `brain/claude_brain.py`
(local Claude reasoning), `workflow.py` (simple loop), `graph/debate.py` (LangGraph debate),
`live_demo.py`. **Status: 53/53 tests pass** (+ guard 5, indicators 2, legends 2, journal 2, markets 4).

**Phase C LIVE (forward-test):** `venture/mode.py` — paper-only gate; live trading raises
`LiveTradingBlocked` with the rotate-keys reminder unless `VENTURE_LIVE_TRADING=true`.
`eval/forward_test.py` — timestamped prediction capture + horizon scoring vs realized
prices (look-ahead-free). `scout_cycle.py` — the daily driver: full debate on the
multi-market watchlist → capture → score matured → scorecard (`venture/forward_test.db`).
First live cycle captured 6 predictions across binance/NASDAQ/BSE/NSE. Run it daily;
edge verdict forms at n≥20 scored directional predictions. **60/60 tests.**

**BSE/NSE first-class (Phase B core):** `markets/registry.py` (resolve symbol -> exchange/
currency ₹|$ / market-hours / provider), `markets/watchlist.py`, Indian RSS feeds (Economic
Times / LiveMint) routed for `.BO`/`.NS`, currency-aware live demo. Verified live on RELIANCE.BO.
Open refinement: cross-currency portfolio (₹ journey vs the USD $50 floor) — needs FX or
per-market journeys.

**Legacy fully migrated + deleted.** `tradingagent.py` + `TradingAgent_week1.ipynb` ported into
`venture/` and removed (in git history as backup). See `COVERAGE.md` for the component matrix.
Ported gaps: `security/guard.py` (rate limiter / circuit breaker / response validator),
`features/indicators.py` (RSI/MACD/BB/EMA/ATR, pure pandas), `rag/legends.py` (Trading Legends
KB), `persistence/journal.py` (local SQLite, replaces Supabase logging).

Added: `engines/rl_quant.py` (`RLQuantEngine` — PPO policy with graceful fallback to the
stat quant), `train/train_rl.py` (PPO training on real ccxt data), tunable `JudgeConfig`
(`CONSERVATIVE_JUDGE`/`ASSERTIVE_JUDGE`), and Claude `bull_brain()`/`bear_brain()` personas
(`live_demo.py --debate-llm`).

Engines are decoupled, so **LangGraph drives these exact nodes** without changing them.
**FULLY LIVE:** real data (ccxt/yfinance) · RSS news · FAISS semantic RAG · PPO quant ·
Claude brain · tunable Judge · LLM Bull/Bear personas. One command runs the whole stack:
`python venture/live_demo.py BTC/USDT --rl --faiss --debate-llm`.
Open: scale RL training, explicit Controller node, crawl4ai deep scraping, n8n scheduling (parked).

---

## 10. Validation findings (honest)

`eval/walk_forward.py` does rolling train→OOS-test folds — the real test for edge vs
overfitting. Shared RL feature/observation contract lives in `rl/features.py` (train and
inference import the same `build_observation`, so they can't drift).

**First result (BTC/USDT, 5 folds, 1h bars, 8k steps): NO out-of-sample edge.**
Avg OOS strategy −4.49% vs buy-hold −1.26% (edge −3.23%; 1/5 folds beat B&H). The harness
correctly refuses to flatter a weak policy.

**Strategic implication (important):** pure price-action RL on 1h bars is near-efficient-
market territory and rarely yields durable edge — more steps mostly overfit the train
window. So the venture's edge thesis should NOT rest on price-only RL. The likely edge:
the **information layer** (live news/catalysts via Scout + FAISS RAG + the Claude brain) and
**disciplined risk** (the floor / capital preservation already proven: ~flat vs −7…−11% B&H).
RL is best used as a **risk-aware position-sizer**, not the primary alpha. Validate every
new signal through walk-forward before trusting it.

---

## 11. Security — the Vault (Phase A, done)

**Incident:** live secrets (Alpaca key+secret, master password, NewsAPI/Supabase keys) were
committed to the PUBLIC repo `github.com/prathick96/buffet`. See `SECURITY.md`.

**Built (code side):**
- `.gitignore` (secrets/.env/*.enc/models/caches) + 29 artifact files untracked from the index.
- `venture/security/vault.py` — hardened vault: **scrypt + random salt**, master password from
  `$VENTURE_MASTER_PASSWORD` (never in code), vault file outside repo (`~/.venture/`, chmod 600).
- `venture/security/secrets.py` — unified loader, precedence **env → .env → vault**;
  `require_secret()` for fail-fast.
- `venture/security/scan.py` + `.githooks/pre-commit` (activated via `core.hooksPath`) — blocks
  commits containing likely secrets. ASCII-safe on Windows.
- Legacy `tradingagent.py` + notebook secret literals **purged to `""`** (scanner-clean).
- `SECURITY.md` runbook; `.env.example` template. **Tests 7/7.**

**Still required (human-only):** rotate/revoke Alpaca + Supabase + NewsAPI keys + master
password at the providers, and flip the repo to **private**. Code can't un-expose history.

**Decisions (locked):** repo → make-private + .gitignore · secrets → .env + hardened vault ·
edge → forward-test live (no historical-news backtest).

---

## 12. Going online (hosting · cloud brain · n8n · Telegram · dashboard)

**Feasibility (all possible, with honest caveats):**
- ✅ **Cloud brain** — `brain/anthropic_brain.py` (Anthropic API, drop-in for local ClaudeBrain;
  key via `.env`/vault; `ANTHROPIC_MODEL` overr., default `claude-opus-4-8`). Done, tested.
- ✅ **Telegram updates** — `notify/telegram.py`, wired into `scout_cycle.py` (no-op unless
  `TELEGRAM_*` set). Done, tested.
- ⚠️ **Free hosting** — a persistent free server that runs n8n 24/7 is the hard part (free web
  hosts sleep). **Recommended free architecture:** GitHub Actions **cron** runs `scout_cycle.py`
  on schedule (2000 free min/mo) → commits the journal/forward-test JSON + pushes Telegram →
  a **static dashboard** on GitHub Pages reads the committed JSON. No always-on server, keys stay
  in Actions **secrets** (never in the public/Pages layer). n8n can drive it too when self-hosted.
- ✅ **n8n** — usable via n8n Cloud (limited free tier) or self-host; for *free reliable* cron,
  GitHub Actions is the pragmatic pick. Offer both.
- ✅ **Dashboard** — neumorphism/minimalist/responsive. `ui-ux-pro-max` (design-intelligence
  CLI) + the `dataviz` method guide the look; `ui-neumorphism` (React) is the component lib if we
  go React. Simplest: static HTML/CSS neumorphic shell + charts built via the dataviz validator,
  reading `forward_test.db`/`journal.db` exported to JSON. Pages: equity/progress-to-goal, trade
  log, agent status, live logs.

**Built (2026-07-03, 68/68 tests, 21 suites):**
- [x] (A) `dashboard/export.py` — DBs → `docs/data/*.json` (summary/predictions/agents/logs). Tested.
- [x] (B) `.github/workflows/scout.yml` — cron (weekdays 21:30 UTC) + manual dispatch: runs
      `scout_cycle.py`, exports JSON, commits `forward_test.db`+`journal.db`+`docs/data` back
      (evidence persists serverlessly); secrets from Actions. `requirements-cloud.txt` (no torch/faiss).
- [x] (C) `docs/index.html` — self-contained neumorphic dashboard (4 tabs: Overview/Trades/
      Agents/Logs), dark+light, responsive, reads `./data/*.json` (or inline `window.__DATA__`).
- [x] `scout_cycle.py` logs to `journal.db` + Telegram push wired.
- [ ] (D) wire AnthropicBrain into the *hosted* debate (currently heuristic bull/bear for speed/cost).

**Deploy (user):** Settings → Pages → source = `main` /docs. Add repo Actions **secrets**:
`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. **Cost:** Opus-4.8
API on a $50 book ≈ $3–4/mo daily; set `ANTHROPIC_MODEL=claude-haiku-4-5` to slash it. **Free-host
note:** GitHub Actions (not n8n) is the reliable free scheduler; n8n → self-host/cloud-free-tier later.
