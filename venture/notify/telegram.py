"""
venture/notify/telegram.py — Telegram updates for daily scout-cycle runs.

Keyless-in-code: reads TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID via the secrets layer
(env -> .env -> vault). If not configured, send() is a no-op returning False — the
cycle never breaks because notifications aren't set up.

Setup: message @BotFather to create a bot (get the token); message your bot once,
then read your chat id from https://api.telegram.org/bot<token>/getUpdates.

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

import urllib.parse
import urllib.request

from security.secrets import get_secret

_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None, timeout: int = 12):
        self.token = token or get_secret("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or get_secret("TELEGRAM_CHAT_ID")
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str) -> bool:
        if not self.is_configured():
            return False
        data = urllib.parse.urlencode({
            "chat_id": self.chat_id,
            "text": text[:4000],
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        try:
            req = urllib.request.Request(_API.format(token=self.token), data=data)
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.status == 200
        except Exception:
            return False


def format_cycle_summary(rows: list, footer: str = "") -> str:
    """rows: [{symbol, exchange, price, action, conviction, sentiment}] -> HTML text."""
    lines = ["<b>🛰 Scout cycle</b> — paper trading"]
    for r in rows:
        cur = r.get("currency", "")
        lines.append(
            f"<code>{r['symbol']:<12}</code> {r['action']:<4} "
            f"conv={r.get('conviction', 0):.2f} ({r.get('sentiment', '?')})")
    if footer:
        lines.append("")
        lines.append(footer)
    return "\n".join(lines)
