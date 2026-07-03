"""
venture/billing/console.py — authoritative month-to-date cost from the Anthropic
Console (Admin Usage & Cost API). Optional reconciliation on top of self-tracking.

Needs an ADMIN key (`sk-ant-admin...`, created by an org admin) in
`ANTHROPIC_ADMIN_KEY`. Endpoint: GET /v1/organizations/cost_report
(`amount` is in cents -> /100 = USD). Fully graceful: returns None if no admin
key or on any error, so the dashboard falls back to self-tracked cost.

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from security.secrets import get_secret

_URL = "https://api.anthropic.com/v1/organizations/cost_report"


def console_month_to_date_usd(admin_key: str | None = None,
                              now: datetime | None = None, timeout: int = 15):
    """Authoritative month-to-date USD cost from the console, or None if unavailable."""
    admin_key = admin_key or get_secret("ANTHROPIC_ADMIN_KEY")
    if not admin_key:
        return None
    now = now or datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    query = urllib.parse.urlencode({
        "starting_at": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bucket_width": "1d",
        "limit": 62,
    })
    req = urllib.request.Request(
        f"{_URL}?{query}",
        headers={"Authorization": f"Bearer {admin_key}",
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read())
    except Exception:
        return None

    cents = 0.0
    for bucket in payload.get("data", []):
        for item in bucket.get("results", []):
            try:
                cents += float(item.get("amount", "0"))     # amount is in cents
            except (TypeError, ValueError):
                continue
    return round(cents / 100.0, 4)
