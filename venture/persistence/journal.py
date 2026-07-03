"""
venture/persistence/journal.py — local SQLite journal.

Replaces the legacy Supabase logging with a dependency-free local store, and is
the backbone of Phase C (live forward-test): we timestamp and persist each
cycle's snapshot/analysis/decision so we can later score predictions against
realized prices.

    j = Journal("venture/journal.db")
    j.log("decision", "BTC/USDT", {"action": "BUY", "conviction": 0.7})
    j.recent("decision")

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class Journal:
    def __init__(self, path: str = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS events("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, symbol TEXT, payload TEXT)")
        self.conn.commit()

    def log(self, kind: str, symbol: str, payload: dict, ts: float | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO events(ts, kind, symbol, payload) VALUES(?,?,?,?)",
            (ts if ts is not None else time.time(), kind, symbol, json.dumps(payload)))
        self.conn.commit()
        return cur.lastrowid

    def recent(self, kind: str | None = None, symbol: str | None = None, limit: int = 50) -> list:
        q = "SELECT id, ts, kind, symbol, payload FROM events"
        clauses, args = [], []
        if kind:
            clauses.append("kind = ?")
            args.append(kind)
        if symbol:
            clauses.append("symbol = ?")
            args.append(symbol)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [
            {"id": r[0], "ts": r[1], "kind": r[2], "symbol": r[3], "payload": json.loads(r[4])}
            for r in self.conn.execute(q, args)
        ]

    def count(self, kind: str | None = None) -> int:
        if kind:
            return self.conn.execute("SELECT COUNT(*) FROM events WHERE kind=?", (kind,)).fetchone()[0]
        return self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def close(self) -> None:
        self.conn.close()
