"""
venture/billing/tracker.py — per-call usage tracking + monthly budget guard.

UsageTracker logs every API call (tokens + USD) to the journal as `api_usage`
events. BudgetGuard reads the current-UTC-month total from the journal and
enforces a hard cap — the API brain refuses further calls (degrading to the free
heuristic) once the month's spend hits the ceiling. This gives the same
"never blow the budget" control the RiskEngine gives the portfolio.

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

from datetime import datetime, timezone

from billing.pricing import usage_to_cost

USAGE_KIND = "api_usage"


class UsageTracker:
    def __init__(self, journal):
        self.journal = journal

    def record(self, model: str, usage, symbol: str = "-", purpose: str = "analyst") -> float:
        tokens, cost = usage_to_cost(model, usage)
        if self.journal is not None:
            self.journal.log(USAGE_KIND, symbol,
                             {"model": model, "cost_usd": round(cost, 6),
                              "purpose": purpose, **tokens})
        return cost


def _month(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def month_to_date(journal, now: datetime | None = None) -> dict:
    """Aggregate this-UTC-month `api_usage` events from the journal."""
    target = _month(now)
    calls = inp = out = 0
    cost = 0.0
    for ev in journal.recent(kind=USAGE_KIND, limit=1_000_000):
        ts = ev.get("ts")
        if ts is None:
            continue
        if datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m") != target:
            continue
        p = ev.get("payload", {})
        calls += 1
        cost += float(p.get("cost_usd", 0) or 0)
        inp += int(p.get("input_tokens", 0) or 0)
        out += int(p.get("output_tokens", 0) or 0)
    return {"month": target, "calls": calls, "cost_usd": round(cost, 4),
            "input_tokens": inp, "output_tokens": out}


class BudgetGuard:
    """Monthly spend cap. cap <= 0 means DISABLED (unlimited)."""

    def __init__(self, journal, monthly_cap_usd: float):
        self.journal = journal
        self.cap = float(monthly_cap_usd)

    def spent(self, now: datetime | None = None) -> float:
        return month_to_date(self.journal, now)["cost_usd"]

    def remaining(self, now: datetime | None = None) -> float:
        if self.cap <= 0:
            return float("inf")
        return max(0.0, self.cap - self.spent(now))

    def allow(self, now: datetime | None = None) -> bool:
        return self.cap <= 0 or self.spent(now) < self.cap
