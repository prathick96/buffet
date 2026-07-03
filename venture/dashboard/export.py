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
