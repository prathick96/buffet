"""
venture/dashboard/export.py — export the DBs to static JSON for the dashboard.

Reads the forward-test DB (predictions + scorecard) and the journal (activity
log), and writes docs/data/*.json that the static neumorphic dashboard fetches.
Serverless-friendly: run it in CI after each scout cycle and commit the JSON.

    python venture/dashboard/export.py

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

import json
import math
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

# Chessboard ladder: $20 -> $250,000.
GOAL = {"start": 20.0, "target": 250000.0}

AGENTS = [
    {"name": "Scout", "role": "gather price + live news, RAG ingest/retrieve"},
    {"name": "Analyst", "role": "technical + sentiment -> conviction"},
    {"name": "Quant", "role": "trend + mean-reversion z-score (PPO seam)"},
    {"name": "Bull", "role": "long-side advocate"},
    {"name": "Bear", "role": "short-side skeptic"},
    {"name": "Judge", "role": "weigh the debate -> final conviction"},
    {"name": "Risk", "role": "$ floor / position sizing / drawdown halt"},
    {"name": "Execution", "role": "paper orders"},
    {"name": "Learning", "role": "running scorecard + adaptation"},
]


def _iso(ts) -> str | None:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds") if ts else None


def _write(out_dir: str, name: str, obj) -> None:
    (Path(out_dir) / name).write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _predictions(conn) -> list:
    rows = conn.execute(
        "SELECT id,ts,symbol,price,action,conviction,sentiment,scored,exit_price,"
        "fwd_return,correct FROM predictions ORDER BY id DESC LIMIT 200").fetchall()
    out = []
    for r in rows:
        out.append({
            "id": r[0], "time": _iso(r[1]), "symbol": r[2], "price": r[3],
            "action": r[4], "conviction": r[5], "sentiment": r[6],
            "scored": bool(r[7]), "exit_price": r[8],
            "fwd_return_pct": round(r[9] * 100, 3) if r[9] is not None else None,
            "correct": None if r[10] is None else bool(r[10]),
        })
    return out


def _logs(journal_db: str) -> list:
    if not Path(journal_db).exists():
        return []
    conn = sqlite3.connect(journal_db)
    try:
        rows = conn.execute(
            "SELECT ts,kind,symbol,payload FROM events ORDER BY id DESC LIMIT 200").fetchall()
    except Exception:
        return []
    finally:
        conn.close()
    out = []
    for ts, kind, symbol, payload in rows:
        try:
            detail = json.loads(payload)
        except Exception:
            detail = {}
        out.append({"time": _iso(ts), "kind": kind, "symbol": symbol, "detail": detail})
    return out


def _billing(journal_db: str) -> dict:
    """Month-to-date API spend for the dashboard (self-tracked + optional console)."""
    from billing.tracker import month_to_date
    from persistence.journal import Journal
    from security.secrets import get_secret

    cap = float(get_secret("ANTHROPIC_MONTHLY_BUDGET", default="20") or 20)
    model = get_secret("ANTHROPIC_MODEL", default="claude-opus-4-8")
    mtd = {"month": None, "calls": 0, "cost_usd": 0.0,
           "input_tokens": 0, "output_tokens": 0}
    if Path(journal_db).exists():
        j = Journal(journal_db)
        try:
            mtd = month_to_date(j)
        finally:
            j.close()
    out = {"model": model, "budget_usd": cap, "month": mtd["month"],
           "cost_usd": mtd["cost_usd"], "calls": mtd["calls"],
           "input_tokens": mtd["input_tokens"], "output_tokens": mtd["output_tokens"],
           "remaining_usd": round(max(0.0, cap - mtd["cost_usd"]), 4) if cap > 0 else None,
           "pct_used": round(mtd["cost_usd"] / cap * 100, 1) if cap > 0 else None}
    try:  # authoritative console figure if an admin key is configured
        from billing.console import console_month_to_date_usd
        out["console_cost_usd"] = console_month_to_date_usd()
    except Exception:
        out["console_cost_usd"] = None
    return out


def export(forward_db: str = "venture/forward_test.db",
           journal_db: str = "venture/journal.db",
           out_dir: str = "docs/data") -> dict:
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    preds: list = []
    report = {"scored": 0, "directional": 0, "pending": 0, "verdict": "no data yet"}
    if Path(forward_db).exists():
        from eval.forward_test import ForwardTester
        ft = ForwardTester(forward_db)
        report = ft.report()
        preds = _predictions(ft.conn)
        ft.close()

    summary = {
        "updated": _iso(time.time()),
        "mode": "paper",
        "goal": {**GOAL,
                 "doublings_total": round(math.log2(GOAL["target"] / GOAL["start"]), 1),
                 "current_square": 0,
                 "current_capital": GOAL["start"]},
        "forward_test": report,
        "counts": {"predictions": len(preds),
                   "scored": report.get("scored", 0),
                   "pending": report.get("pending", 0)},
        "billing": _billing(journal_db),
    }

    _write(out_dir, "summary.json", summary)
    _write(out_dir, "predictions.json", preds)
    _write(out_dir, "agents.json", {"updated": summary["updated"], "agents": AGENTS})
    _write(out_dir, "logs.json", _logs(journal_db))
    return summary


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    s = export()
    print(f"Exported {s['counts']['predictions']} predictions -> docs/data/*.json")
    print(f"Forward-test: {s['forward_test'].get('verdict')}")
