# SECURITY — the Vault

## ⚠️ Active incident (do this FIRST — only you can)

Secrets were committed to the **public** repo `github.com/prathick96/buffet` and are in
git history. Treat them as compromised. **Rotate/revoke now:**

- [ ] **Alpaca** — regenerate API key + secret (dashboard → API keys). Use a **paper** key
      and/or one with **no withdrawal** rights.
- [ ] **Supabase** — rotate the project API key.
- [ ] **NewsAPI** — regenerate the key.
- [ ] **Master password** — choose a new strong passphrase (the old `Apples80@@` is public).
- [ ] **Make the repo private** (Settings → Danger Zone → Change visibility).

Rotation is mandatory because nothing un-publishes git history. Making the repo private
stops *new* exposure; the old keys must die by rotation.

## How secrets work now (never hardcode again)

Resolution order (`venture/security/secrets.py`): **env var → `.env` → encrypted vault**.

```python
from security.secrets import require_secret
alpaca = require_secret("ALPACA_API_KEY")   # raises clearly if missing
```

1. **`.env`** (gitignored) — copy `.env.example` → `.env`, fill values. For config + dev keys.
2. **Encrypted vault** (`venture/security/vault.py`) — for the sensitive trading keys:
   ```python
   from security.vault import Vault          # master pw from $VENTURE_MASTER_PASSWORD
   v = Vault()
   v.set("ALPACA_API_KEY", "…"); v.set("ALPACA_SECRET_KEY", "…")
   ```
   - scrypt KDF + random per-vault salt (not bare SHA-256).
   - Master password from `$VENTURE_MASTER_PASSWORD` (or passed in) — **never in code**.
   - Vault file lives outside the repo (`~/.venture/vault.enc`, chmod 600).

## Recurrence guard (secret scanner)

A pre-commit hook blocks commits containing likely secrets. Activate once:

```bash
git config core.hooksPath .githooks
```

Run manually anytime: `python venture/security/scan.py --staged`

## Posture / principles

- **No custody:** prefer **read-only / no-withdrawal** API keys so a breach can't move funds.
- **Local-first:** the LLM brain runs on the local Claude CLI (no key leaves the machine).
- **`.gitignore`** covers `.env`, `*.enc`, `~/.venture/`, models, caches.
- The legacy `tradingagent.py` / notebook secret literals have been purged to `""` — set
  real values via `.env`/vault when running them.
