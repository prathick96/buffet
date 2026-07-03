"""
venture/mode.py — trading mode gate. PAPER ONLY by default.

Any real-money execution path MUST call assert_live_allowed() first. It raises
unless live trading is explicitly enabled via VENTURE_LIVE_TRADING=true, and the
error doubles as the "before you go live" reminder (rotate keys, no-withdrawal).

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

import os

LIVE_ENV = "VENTURE_LIVE_TRADING"


class LiveTradingBlocked(RuntimeError):
    """Raised when real-money trading is attempted while paper-only is in effect."""


def is_live_enabled() -> bool:
    return os.environ.get(LIVE_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def assert_live_allowed() -> None:
    """Call before ANY real-money order. Blocks (with a reminder) unless enabled."""
    if not is_live_enabled():
        raise LiveTradingBlocked(
            "LIVE TRADING IS DISABLED (paper-only).\n"
            "Before going live: (1) ROTATE the exposed Alpaca/Supabase/NewsAPI keys, "
            "(2) use read-only / no-withdrawal keys, (3) set "
            f"{LIVE_ENV}=true to confirm you understand the risk.\n"
            "** This is your pre-live reminder. **")
