# Deploying the hourly scout cycle (online, paper trading)

Two hosting options. Both run `venture/scout_cycle.py` **hourly**; the script itself
gates the **Opus LLM to equity symbols during their market hours** (never crypto) and
enforces a **monthly API budget**. Cost target: **~$5–7/mo** on Opus (see BLUEPRINT §12).

## Decision: n8n?

**Not worth configuring for this.** n8n is a heavyweight visual-workflow tool that needs
its own 24/7 server. Our job is "run one Python script hourly" — a **crontab** (Oracle VM)
or **GitHub Actions cron** does it with far less to maintain, more reliably, for free.
Add n8n only later if you want a visual ops console with Telegram-command control.

---

## Option A — GitHub Actions (zero server, ~$0–1.3/mo)

Already configured in `.github/workflows/scout.yml` (`cron: "0 * * * *"`). It runs the
cycle, commits the DBs + `docs/data/*.json` back, and the dashboard on GitHub Pages reads them.

1. **Pages:** Settings → Pages → source = `main`, folder `/docs`.
2. **Secrets:** Settings → Secrets and variables → Actions → add:
   - `ANTHROPIC_API_KEY` (`sk-ant-...`)
   - `ANTHROPIC_MODEL` = `claude-opus-4-8`
   - `ANTHROPIC_MONTHLY_BUDGET` = `20`
   - `ANTHROPIC_ADMIN_KEY` *(optional, `sk-ant-admin...` — shows the console's own $ on the dashboard)*
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` *(optional)*
3. Run once manually: Actions → scout-cycle → **Run workflow**.

Hourly 24/7 ≈ 1,400 min/mo (near the 2,000 free tier). To stay free, narrow the cron to
market hours (commented example in the workflow), or use Option B.

---

## Option B — Oracle Cloud Always-Free VM (true 24/7, $0, recommended for real cadence)

An Always-Free `VM.Standard.A1.Flex` (Arm, up to 4 OCPU / 24 GB) runs forever at no cost —
no Actions-minute cap, and it can also host n8n later.

**One-time setup:**
```bash
# on the VM (Ubuntu 22.04)
sudo apt update && sudo apt install -y python3.11 python3.11-venv git
git clone <your-private-repo> venture-app && cd venture-app
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r venture/requirements-cloud.txt

# secrets: create .env at repo root (gitignored) — see .env.example
cat > .env <<'EOF'
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-opus-4-8
ANTHROPIC_MONTHLY_BUDGET=20
# ANTHROPIC_ADMIN_KEY=sk-ant-admin-...   # optional console cost reconcile
# TELEGRAM_BOT_TOKEN=...  TELEGRAM_CHAT_ID=...
EOF
```

**Hourly crontab** (`crontab -e`) — the script reads `.env` via the secrets layer:
```cron
0 * * * * cd /home/ubuntu/venture-app && . .venv/bin/activate && \
  python venture/scout_cycle.py >> venture/scout.log 2>&1 && \
  python venture/dashboard/export.py >> venture/scout.log 2>&1
```

**Serve the dashboard** (choose one):
- Commit `docs/data` back and let GitHub Pages serve it (add a `git commit && git push` to the cron), **or**
- Serve `docs/` locally: `python -m http.server 8080 --directory docs` behind the VM's firewall.

**Security:** keep `.env` at `chmod 600`, use a **paper / no-withdrawal** Alpaca key, and never
commit `.env`. Live trading stays hard-blocked (`venture/mode.py`) until you opt in explicitly.

---

## Cost controls (built in)
- **No LLM for crypto**, and **no LLM when a market is closed** → most cycles cost $0.
- **`ANTHROPIC_MONTHLY_BUDGET`**: once month-to-date spend hits the cap, the brain degrades to
  the free heuristic (logged as a `budget` fallback) — a hard ceiling, like the $ floor for the portfolio.
- **Dashboard billing card**: live month-to-date $, calls, tokens, budget bar (self-tracked from
  each call's `response.usage`; reconciled with the console when `ANTHROPIC_ADMIN_KEY` is set).
