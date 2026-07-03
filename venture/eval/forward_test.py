"""
venture/eval/forward_test.py — live, look-ahead-free forward test of signals.

We can't backtest the news/catalyst signal (RSS only gives today's headlines), so
we accumulate evidence FORWARD: each run captures a timestamped prediction
(price + action + conviction from the Analyst/brain); a later run, once the
horizon has elapsed, scores it against the realized price. Aggregated over time
this answers honestly: does the signal have edge?

  ft = ForwardTester("venture/forward_test.db", horizon_sec=86400)
  ft.capture_from_cycle("BTC/USDT", snapshot, report)        # today
  ft.score_due(price_fn=lambda s: latest_price(s))           # tomorrow
  print(ft.summary())

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

import time
from pathlib import Path
import sqlite3


class ForwardTester:
    def __init__(self, path: str = "venture/forward_test.db",
                 horizon_sec: float = 86400, clock=time.time):
        self.horizon = horizon_sec
        self._clock = clock
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS predictions("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, symbol TEXT, price REAL, "
            "action TEXT, conviction REAL, sentiment TEXT, rationale TEXT, horizon_sec REAL, "
            "scored INTEGER DEFAULT 0, scored_ts REAL, exit_price REAL, fwd_return REAL, "
            "correct INTEGER)")
        self.conn.commit()

    # ---------------------------------------------------------------- capture
    def capture(self, symbol: str, price: float, action: str, conviction: float,
                sentiment: str = "", rationale: str = "", ts: float | None = None,
                horizon_sec: float | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO predictions(ts,symbol,price,action,conviction,sentiment,"
            "rationale,horizon_sec) VALUES(?,?,?,?,?,?,?,?)",
            (ts if ts is not None else self._clock(), symbol, price, action, conviction,
             sentiment, (rationale or "")[:500], horizon_sec or self.horizon))
        self.conn.commit()
        return cur.lastrowid

    def capture_from_cycle(self, symbol: str, snapshot, report, ts: float | None = None) -> int:
        return self.capture(symbol, snapshot.price, report.suggested_action,
                            report.conviction, getattr(report, "sentiment", ""),
                            getattr(report, "rationale", ""), ts)

    # ----------------------------------------------------------------- score
    def due(self, now: float | None = None) -> list:
        now = now if now is not None else self._clock()
        rows = self.conn.execute(
            "SELECT id,ts,symbol,price,action,horizon_sec FROM predictions WHERE scored=0"
        ).fetchall()
        return [r for r in rows if now - r[1] >= r[5]]

    def score_due(self, price_fn, now: float | None = None) -> int:
        now = now if now is not None else self._clock()
        scored = 0
        for pid, _ts, symbol, price, action, _h in self.due(now):
            try:
                exit_price = price_fn(symbol)
            except Exception:
                continue
            if not exit_price or not price:
                continue
            fwd = exit_price / price - 1
            correct = self._is_correct(action, fwd)
            self.conn.execute(
                "UPDATE predictions SET scored=1,scored_ts=?,exit_price=?,fwd_return=?,"
                "correct=? WHERE id=?",
                (now, exit_price, fwd, None if correct is None else int(correct), pid))
            scored += 1
        self.conn.commit()
        return scored

    @staticmethod
    def _is_correct(action: str, fwd: float):
        if action == "BUY":
            return fwd > 0
        if action == "SELL":
            return fwd < 0
        return None   # HOLD is not a directional bet -> not scored win/loss

    # ---------------------------------------------------------------- report
    def report(self, min_sample: int = 20) -> dict:
        rows = self.conn.execute(
            "SELECT action,fwd_return,correct FROM predictions WHERE scored=1").fetchall()
        directional = [(a, f, c) for a, f, c in rows if c is not None]
        n = len(directional)
        pending = self.conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE scored=0").fetchone()[0]
        out = {"scored": len(rows), "directional": n, "pending": pending}
        if n == 0:
            out["verdict"] = "no scored directional predictions yet — let it run"
            return out
        wins = sum(1 for _, _, c in directional if c)
        # Signed return = return you'd get following the signal (BUY:+fwd, SELL:-fwd).
        signed = [f if a == "BUY" else -f for a, f, _ in directional]
        out.update({
            "hit_rate": round(wins / n, 3),
            "avg_signal_return_pct": round(sum(signed) / len(signed) * 100, 3),
            "sample": n,
        })
        if n < min_sample:
            out["verdict"] = f"insufficient sample ({n}/{min_sample}) — keep accumulating"
        elif out["hit_rate"] > 0.5 and out["avg_signal_return_pct"] > 0:
            out["verdict"] = "EDGE FORMING — hit-rate > 50% and positive signal return"
        else:
            out["verdict"] = "no edge yet — signal not beating chance"
        return out

    def summary(self) -> str:
        r = self.report()
        lines = ["FORWARD-TEST SCORECARD",
                 f"  scored={r['scored']} directional={r['directional']} pending={r['pending']}"]
        if r.get("sample"):
            lines.append(f"  hit-rate={r['hit_rate']*100:.1f}%  "
                         f"avg signal return={r['avg_signal_return_pct']:+.3f}%  n={r['sample']}")
        lines.append(f"  verdict: {r['verdict']}")
        return "\n".join(lines)

    def close(self) -> None:
        self.conn.close()
