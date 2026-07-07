"""
venture/eval/forward_test.py — live, look-ahead-free forward test of signals.

We can't backtest the news/catalyst signal (RSS only gives today's headlines), so
we accumulate evidence FORWARD: each run captures a timestamped prediction
(price + action + conviction from the Analyst/brain); a later run, once the
horizon has elapsed, scores it against the realized price. Aggregated over time
this answers honestly: does the signal have edge?

  ft = ForwardTester("venture/forward_test.db", horizon_sec=86400)
  ft.capture_from_cycle("BTC/USDT", snapshot, report, bar_ts=..., deadband=...)  # today
  ft.score_due(bars_fn=lambda s: provider.bars())                                # later
  print(ft.summary())

Scoring is DATED and TIE-AWARE (see the P0 fixes):
  * exit price is the close of a bar strictly AFTER the entry bar, at/after
    entry + horizon — never a price compared to itself (kills the "stale close
    on a closed market = 0.00% return counted as a loss" artifact);
  * a move inside a volatility-scaled dead-band is a TIE (excluded), not a
    directional miss — a flat tape is not a wrong call;
  * captures are de-duplicated per (symbol, bar) so an hourly cron on a daily
    bar records one prediction per bar, not eight identical copies.

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
import sqlite3


def deadband_from_closes(closes, horizon_sec: float, bar_seconds: float | None,
                         k: float = 0.25, floor: float = 0.001,
                         cap: float = 0.03) -> float:
    """Volatility-scaled flat-move threshold, as a relative fraction.

    A directional call should only score win/loss when the move is bigger than
    the market's own noise over the holding horizon. We estimate per-bar close
    volatility (sigma), scale it to the horizon (sigma * sqrt(bars_in_horizon)),
    and take k * that — clamped to [floor, cap]. Falls back to `floor` when
    volatility can't be estimated, so scoring is always well-defined.
    """
    try:
        cl = [c for c in closes if c and c == c]
        if len(cl) < 8 or not bar_seconds:
            return floor
        rets = [cl[i] / cl[i - 1] - 1 for i in range(1, len(cl))][-60:]
        n = len(rets)
        if n < 5:
            return floor
        mean = sum(rets) / n
        var = sum((r - mean) ** 2 for r in rets) / (n - 1)
        sigma_bar = math.sqrt(var)
        bars = max(1.0, horizon_sec / bar_seconds)
        sigma_h = sigma_bar * math.sqrt(bars)
        return max(floor, min(cap, k * sigma_h))
    except Exception:
        return floor


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
            "id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, bar_ts REAL, symbol TEXT, "
            "price REAL, action TEXT, conviction REAL, sentiment TEXT, rationale TEXT, "
            "horizon_sec REAL, deadband REAL DEFAULT 0, scored INTEGER DEFAULT 0, "
            "scored_ts REAL, exit_ts REAL, exit_price REAL, fwd_return REAL, correct INTEGER)")
        self.conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        """Add columns introduced after a DB was first created (idempotent).

        Lets an already-deployed forward_test.db upgrade in place on the next
        run instead of throwing 'no such column'."""
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(predictions)")}
        for col, decl in (("bar_ts", "REAL"), ("exit_ts", "REAL"),
                          ("deadband", "REAL DEFAULT 0")):
            if col not in cols:
                self.conn.execute(f"ALTER TABLE predictions ADD COLUMN {col} {decl}")
        self.conn.commit()

    # ---------------------------------------------------------------- capture
    def capture(self, symbol: str, price: float, action: str, conviction: float,
                sentiment: str = "", rationale: str = "", ts: float | None = None,
                horizon_sec: float | None = None, bar_ts: float | None = None,
                deadband: float = 0.0) -> int:
        cur = self.conn.execute(
            "INSERT INTO predictions(ts,bar_ts,symbol,price,action,conviction,sentiment,"
            "rationale,horizon_sec,deadband) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (ts if ts is not None else self._clock(), bar_ts, symbol, price, action,
             conviction, sentiment, (rationale or "")[:500],
             horizon_sec or self.horizon, deadband or 0.0))
        self.conn.commit()
        return cur.lastrowid

    def capture_from_cycle(self, symbol: str, snapshot, report,
                           bar_ts: float | None = None, deadband: float = 0.0,
                           ts: float | None = None, dedup: bool = True) -> int:
        """Capture one cycle's signal. Returns -1 (no insert) when this is the
        same bar we already captured for the symbol — so an hourly cron on a
        daily bar doesn't pile up identical, non-independent predictions."""
        if dedup and bar_ts is not None and self._last_bar_ts(symbol) == bar_ts:
            return -1
        return self.capture(symbol, snapshot.price, report.suggested_action,
                            report.conviction, getattr(report, "sentiment", ""),
                            getattr(report, "rationale", ""), ts=ts,
                            bar_ts=bar_ts, deadband=deadband)

    def _last_bar_ts(self, symbol: str):
        r = self.conn.execute(
            "SELECT bar_ts FROM predictions WHERE symbol=? ORDER BY id DESC LIMIT 1",
            (symbol,)).fetchone()
        return r[0] if r else None

    # ----------------------------------------------------------------- score
    def due(self, now: float | None = None) -> list:
        """Rows whose horizon has elapsed in wall-clock time (anchored to the
        entry bar when known). Whether a realized bar actually exists yet is
        decided in dated scoring."""
        now = now if now is not None else self._clock()
        rows = self.conn.execute(
            "SELECT id,ts,bar_ts,symbol,price,action,horizon_sec,deadband "
            "FROM predictions WHERE scored=0").fetchall()
        out = []
        for r in rows:
            anchor = r[2] if r[2] is not None else r[1]     # bar_ts or capture ts
            if now - anchor >= r[6]:
                out.append(r)
        return out

    def score_due(self, price_fn=None, bars_fn=None, now: float | None = None) -> int:
        """Score matured predictions.

        bars_fn(symbol) -> [(ts, close), ...] ascending  -> DATED scoring
            (preferred): exit is the first bar at/after entry+horizon and
            strictly after the entry bar. If no such bar exists yet (e.g. the
            market was closed the whole horizon), the prediction stays pending.
        price_fn(symbol) -> float  -> legacy point scoring (kept for tests and
            simple callers); still applies the dead-band.
        """
        now = now if now is not None else self._clock()
        if bars_fn is not None:
            return self._score_dated(bars_fn, now)
        return self._score_point(price_fn, now)

    def _score_dated(self, bars_fn, now: float) -> int:
        scored = 0
        cache: dict = {}
        for pid, ts, bar_ts, symbol, price, action, horizon, band in self.due(now):
            anchor = bar_ts if bar_ts is not None else ts
            target = anchor + horizon
            if symbol not in cache:
                try:
                    cache[symbol] = bars_fn(symbol) or []
                except Exception:
                    cache[symbol] = []
            exit_bar = next(((bts, bc) for bts, bc in cache[symbol]
                             if bts >= target and bts > anchor), None)
            if exit_bar is None:                 # no realized bar yet -> stay pending
                continue
            exit_ts, exit_price = exit_bar
            if not exit_price or not price:
                continue
            fwd = exit_price / price - 1
            self._record(pid, now, exit_ts, exit_price, fwd,
                         self._classify(action, fwd, band))
            scored += 1
        self.conn.commit()
        return scored

    def _score_point(self, price_fn, now: float) -> int:
        scored = 0
        for pid, ts, bar_ts, symbol, price, action, horizon, band in self.due(now):
            try:
                exit_price = price_fn(symbol)
            except Exception:
                continue
            if not exit_price or not price:
                continue
            fwd = exit_price / price - 1
            self._record(pid, now, None, exit_price, fwd,
                         self._classify(action, fwd, band))
            scored += 1
        self.conn.commit()
        return scored

    def _record(self, pid, scored_ts, exit_ts, exit_price, fwd, correct) -> None:
        self.conn.execute(
            "UPDATE predictions SET scored=1,scored_ts=?,exit_ts=?,exit_price=?,"
            "fwd_return=?,correct=? WHERE id=?",
            (scored_ts, exit_ts, exit_price, fwd,
             None if correct is None else int(correct), pid))

    @staticmethod
    def _classify(action: str, fwd: float, band: float = 0.0):
        """True=win, False=loss, None=not a directional win/loss.

        HOLD is never a directional bet. A move inside the dead-band is a TIE
        (flat tape) -> excluded, not a miss."""
        if action not in ("BUY", "SELL"):
            return None
        if abs(fwd) <= (band or 0.0):
            return None
        if action == "BUY":
            return fwd > 0
        return fwd < 0                           # SELL

    # ---------------------------------------------------------------- report
    def report(self, min_sample: int = 20) -> dict:
        rows = self.conn.execute(
            "SELECT action,fwd_return,correct FROM predictions WHERE scored=1").fetchall()
        directional = [(a, f, c) for a, f, c in rows if c is not None]
        ties = sum(1 for a, f, c in rows
                   if c is None and a in ("BUY", "SELL"))
        n = len(directional)
        pending = self.conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE scored=0").fetchone()[0]
        out = {"scored": len(rows), "directional": n, "ties": ties, "pending": pending}
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
                 f"  scored={r['scored']} directional={r['directional']} "
                 f"ties={r.get('ties', 0)} pending={r['pending']}"]
        if r.get("sample"):
            lines.append(f"  hit-rate={r['hit_rate']*100:.1f}%  "
                         f"avg signal return={r['avg_signal_return_pct']:+.3f}%  n={r['sample']}")
        lines.append(f"  verdict: {r['verdict']}")
        return "\n".join(lines)

    def close(self) -> None:
        self.conn.close()
