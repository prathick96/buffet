"""
venture/learn/calibration.py — turn realized forward-test outcomes into a stable,
capital-preserving position-size multiplier per symbol.

This is the honest "learning" loop you asked about. It reads the multi-horizon
scores the forward test accumulates and nudges a symbol's exposure by
DEMONSTRATED edge, with three guardrails so it calibrates instead of gambling:

  * Bayesian shrinkage — a Beta-Binomial posterior centered at 0.5 (no edge), so a
    lucky 5/5 small sample can't inflate size; the estimate only leaves chance as
    real evidence accrues.
  * Sample gate — below `min_sample` (default 30 independent scored predictions)
    the multiplier stays at a cautious `unproven` default; it does not react to noise.
  * Bounded + one-directional — the multiplier lives in [floor, 1.0], so calibration
    can only THROTTLE unproven/weak symbols; it can never push size past the risk
    engine's caps. Recomputed on a schedule (frozen between evals), not per tick.

Persists to a `calibration` table so the value is stable and auditable.

License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

import time


def shrunk_hit_rate(wins: int, n: int, prior: float = 6.0) -> float:
    """Beta-Binomial posterior mean with a symmetric prior centered at 0.5.

    prior=6 => ~12 pseudo-observations pulling a small sample toward chance."""
    a = wins + prior
    b = (n - wins) + prior
    return a / (a + b)


def size_multiplier_from(hit_shrunk: float, avg_signed_return_pct: float, n: int,
                         min_sample: int = 30, floor: float = 0.25,
                         unproven: float = 0.5) -> float:
    """Map evidence -> a [floor, 1.0] position-size multiplier.

      n < min_sample              -> `unproven` (trade smaller until edge is shown)
      proven, shrunk hit >= 0.60  -> up to 1.0 (full base sizing)
      proven, ~chance or negative -> throttled toward `floor`
    A negative realized signed return docks the multiplier even if the hit-rate
    looks acceptable (you can be 'right' often yet lose money on the tails)."""
    if n < min_sample:
        return unproven
    base = 0.5 + (hit_shrunk - 0.5) * 5.0        # 0.50->0.5, 0.60->1.0, 0.40->0.0
    if avg_signed_return_pct <= 0:
        base -= 0.25
    return round(max(floor, min(1.0, base)), 4)


class Calibrator:
    def __init__(self, conn, min_sample: int = 30, prior: float = 6.0,
                 floor: float = 0.25, unproven: float = 0.5,
                 sizing_horizon_sec: float = 86400.0, clock=time.time):
        self.conn = conn
        self.min_sample = min_sample
        self.prior = prior
        self.floor = floor
        self.unproven = unproven
        self.sizing_horizon = sizing_horizon_sec
        self._clock = clock
        conn.execute(
            "CREATE TABLE IF NOT EXISTS calibration("
            "symbol TEXT, horizon_sec REAL, n INTEGER, wins INTEGER, hit_shrunk REAL, "
            "avg_signed_return_pct REAL, multiplier REAL, computed_at REAL, "
            "PRIMARY KEY(symbol, horizon_sec))")
        conn.commit()

    def recompute(self, now: float | None = None) -> dict:
        """Re-derive every (symbol, horizon) multiplier from realized scores and
        persist it. Returns a per-symbol summary at the sizing horizon."""
        now = now if now is not None else self._clock()
        rows = self.conn.execute(
            "SELECT p.symbol, hs.horizon_sec, hs.correct, hs.fwd_return, p.action "
            "FROM horizon_scores hs JOIN predictions p ON p.id=hs.pred_id "
            "WHERE hs.correct IS NOT NULL").fetchall()
        agg: dict = {}                     # (symbol, horizon) -> [wins, n, sum_signed]
        for sym, h, correct, fwd, action in rows:
            w, n, s = agg.get((sym, h), (0, 0, 0.0))
            signed = fwd if action == "BUY" else -fwd
            agg[(sym, h)] = (w + (1 if correct else 0), n + 1, s + signed)
        summary: dict = {}
        for (sym, h), (w, n, s) in agg.items():
            hit = shrunk_hit_rate(w, n, self.prior)
            avg_signed = (s / n * 100) if n else 0.0
            mult = size_multiplier_from(hit, avg_signed, n, self.min_sample,
                                        self.floor, self.unproven)
            self.conn.execute(
                "INSERT OR REPLACE INTO calibration(symbol,horizon_sec,n,wins,hit_shrunk,"
                "avg_signed_return_pct,multiplier,computed_at) VALUES(?,?,?,?,?,?,?,?)",
                (sym, h, n, w, round(hit, 4), round(avg_signed, 3), mult, now))
            if h == self.sizing_horizon:
                summary[sym] = {"n": n, "hit_shrunk": round(hit, 4),
                                "avg_signed_return_pct": round(avg_signed, 3),
                                "multiplier": mult}
        self.conn.commit()
        return summary

    def size_multiplier(self, symbol: str, horizon_sec: float | None = None) -> float:
        """The learned multiplier for a symbol (the `unproven` default if we have
        no calibration row for it yet)."""
        h = horizon_sec or self.sizing_horizon
        r = self.conn.execute(
            "SELECT multiplier FROM calibration WHERE symbol=? AND horizon_sec=?",
            (symbol, h)).fetchone()
        return r[0] if r else self.unproven

    def table(self, sizing_only: bool = False) -> list:
        q = ("SELECT symbol,horizon_sec,n,wins,hit_shrunk,avg_signed_return_pct,multiplier "
             "FROM calibration")
        params: tuple = ()
        if sizing_only:
            q += " WHERE horizon_sec=?"
            params = (self.sizing_horizon,)
        q += " ORDER BY symbol, horizon_sec"
        return [{"symbol": s, "horizon_days": round(h / 86400, 2), "n": n, "wins": w,
                 "hit_shrunk": hs, "avg_signed_return_pct": ar, "multiplier": m}
                for s, h, n, w, hs, ar, m in self.conn.execute(q, params)]
