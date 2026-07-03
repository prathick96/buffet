# Legacy → venture/ Coverage Matrix

Proof that every functional component of `tradingagent.py` + `TradingAgent_week1.ipynb`
is reproduced in `venture/` (or intentionally deferred) **before deleting the legacy files**.
The originals remain in **git history** (private repo) as a safety net.

Legend: ✅ covered (often improved) · 🔁 superseded by a cleaner design · ⏸ deferred (reason).

## Data & indicators (Week 1)
| Legacy component | venture/ home | |
|---|---|---|
| `calculate_position_size` | `risk_engine.RiskEngine.assess_trade` (conviction + risk caps) | ✅ |
| `TradingAccount` (toy) | `portfolio.Portfolio` | 🔁 |
| ccxt/KuCoin fetch, `fetch_ohlcv`, `fetch_full_history` | `data/providers.CCXTDataProvider` | ✅ |
| `fetch_stock_data`, `fetch_stock_history` | `data/providers.YFinanceDataProvider` | ✅ |
| `get_market_snapshot` | `engines/scout.ScoutEngine` | ✅ |
| `build_dataframe`, `build_unified_dataset` | data providers + `features/indicators.add_indicators` | ✅ |
| `add_indicators` (RSI/MACD/BB/EMA/ATR…) | `features/indicators.py` (pure pandas, no pandas-ta) | ✅ |
| `insert_ohlcv_to_supabase`, `load_ohlcv` (Supabase) | `persistence/journal.py` (local SQLite) | 🔁 |
| `incremental_update_*`, `daily_data_refresh`, scheduler | — | ⏸ scheduling = n8n/cron later; providers fetch fresh now |
| `plot_analysis_chart`, plotting | — | ⏸ dashboards optional (Phase later) |
| `generate_signal_summary` | `graph/debate` + `engines/analyst` output | ✅ |
| Alpaca paper setup | `portfolio.Portfolio` (paper); live Alpaca = Phase B | ✅/⏸ |

## RL + Security (Week 2)
| Legacy component | venture/ home | |
|---|---|---|
| `TradingEnv` | `rl/features.make_env` (ReturnsTradingEnv) | ✅ |
| `MultiAssetTradingEnv` | — | ⏸ single-asset now; multi-asset later |
| `make_env` (vectorized), PPO training | `train/train_rl.py` + `eval/walk_forward.py` | ✅ |
| `PortfolioTrackingCallback` | — | ⏸ SB3 built-in logging suffices |
| `run_backtest`, `run_buy_hold_benchmark` | `backtest.py` + `eval/walk_forward.py` | ✅ |
| `SecureKeyStore` | `security/vault.py` (scrypt+salt, env master pw) | 🔁 hardened |
| `RateLimitManager` | `security/guard.RateLimiter` | ✅ |
| `CircuitBreaker` | `security/guard.CircuitBreaker` | ✅ |
| `ResponseValidator` | `security/guard.ResponseValidator` | ✅ |
| `SecurityAgent` | `security/guard.TradingGuard` + `security/vault.py` | ✅ |
| `SecurityWatchdog` (thread) | — | ⏸ guard covers the checks; monitor thread later |

## LLM, Fusion, Orchestration, Persistence (Week 2)
| Legacy component | venture/ home | |
|---|---|---|
| Trading Legends KB | `rag/legends.py` | ✅ |
| `NewsFetcher` (NewsAPI) | `news/providers.NewsAPIProvider` (+ `RSSNewsProvider` live) | ✅ |
| `LLMSignalAgent` (Claude) | `engines/analyst.py` + `brain/claude_brain.py` (local CLI) | 🔁 |
| `FusionEngine` | `engines/decision.py` + `graph/debate.py` (Bull/Bear/Judge) | 🔁 improved |
| `PaperPortfolio` (Supabase) | `portfolio.py` + `persistence/journal.py` | 🔁 |
| `DailyTradingCycle` | `workflow.py` + `graph/debate.DebateRunner` | 🔁 |
| Supabase schema/logging | `persistence/journal.py` (local SQLite) | 🔁 |
| GitHub Actions automation | — | ⏸ CI/n8n scheduling later |
| Performance dashboard (Plotly) | — | ⏸ optional viz later |

## Deferred (none block the venture)
Schedulers/incremental-refresh · plotting/dashboards · multi-asset RL env · GitHub Actions ·
SecurityWatchdog thread · live Alpaca execution (Phase B). Each is superseded by a cleaner
approach or is future/optional — captured in BLUEPRINT.md roadmap.

**Verdict:** all functional capabilities covered or deliberately deferred. Safe to delete the
two legacy files (recoverable from git history). `venture/` has zero imports from them.
**Tests: 49/49.**
