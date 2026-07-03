"""
venture/security/guard.py — operational safety guard (ported from the legacy
SecurityAgent: RateLimitManager + CircuitBreaker + ResponseValidator).

Complements the RiskEngine (which owns the $50 floor + position sizing):
  - RateLimiter      : prevents exchange bans (sliding window + escalating backoff)
  - CircuitBreaker   : halts on daily/weekly/consecutive-loss/volatility trip-wires
  - ResponseValidator: rejects stale / outlier / malformed market data
  - TradingGuard     : single gate the trading loop calls before acting

Clocks/sleepers are injectable so the logic is deterministic in tests.
License: original code, stdlib only -> commercial-clean.
"""
from __future__ import annotations

import random
import threading
import time
from collections import deque
from dataclasses import dataclass


class RateLimiter:
    EXCHANGE_LIMITS = {
        "kucoin":  {"public": 30, "private": 10, "order": 5},
        "binance": {"public": 20, "private": 10, "order": 5},
        "alpaca":  {"public": 10, "private": 5, "order": 3},
        "zerodha": {"public": 10, "private": 5, "order": 2},   # NSE/BSE broker
    }

    def __init__(self, exchange: str, clock=time.monotonic, sleeper=time.sleep,
                 jitter=lambda: random.uniform(0.05, 0.20)):
        self.exchange = exchange.lower()
        self.limits = self.EXCHANGE_LIMITS.get(self.exchange,
                                               {"public": 5, "private": 3, "order": 2})
        self._clock, self._sleep, self._jitter = clock, sleeper, jitter
        self._windows: dict = {}
        self._cooldowns: dict = {}
        self._backoff: dict = {}
        self._lock = threading.Lock()
        self.request_count = 0

    def wait_if_needed(self, endpoint_type: str = "public") -> float:
        """Block until safe to call the endpoint. Returns seconds waited."""
        with self._lock:
            waited = 0.0
            now = self._clock()
            cd = self._cooldowns.get(endpoint_type, 0.0)
            if cd > now:
                waited += cd - now
                self._sleep(cd - now)
                now = self._clock()
            limit = self.limits.get(endpoint_type, 5)
            w = self._windows.setdefault(endpoint_type, deque())
            while w and now - w[0] > 1.0:
                w.popleft()
            if len(w) >= limit:
                gap = 1.0 - (now - w[0])
                if gap > 0:
                    waited += gap
                    self._sleep(gap)
                    now = self._clock()
            j = self._jitter()
            if j > 0:
                self._sleep(j)
                waited += j
            w.append(self._clock())
            self.request_count += 1
            return waited

    def report_rate_limit_error(self, endpoint_type: str = "public") -> float:
        """On a 429: set an escalating cooldown (60s, doubling, capped 32x)."""
        mult = self._backoff.get(endpoint_type, 1)
        cooldown = 60 * mult
        self._cooldowns[endpoint_type] = self._clock() + cooldown
        self._backoff[endpoint_type] = min(mult * 2, 32)
        return cooldown

    def reset_backoff(self, endpoint_type: str = "public") -> None:
        self._backoff[endpoint_type] = 1


@dataclass
class CircuitBreaker:
    daily_loss_limit_pct: float = 5.0
    weekly_loss_limit_pct: float = 15.0
    max_consecutive_losses: int = 5
    volatility_halt_pct: float = 10.0

    def __post_init__(self):
        self.is_tripped = False
        self.trip_reason = None
        self._consec = 0
        self._daily_start = None
        self._weekly_start = None

    def set_session_start(self, value: float) -> None:
        if self._daily_start is None:
            self._daily_start = value
        if self._weekly_start is None:
            self._weekly_start = value

    def check(self, value: float, current_price=None, prev_price=None) -> bool:
        """True if trading allowed, False if halted."""
        if self.is_tripped:
            return False
        if self._daily_start is None:
            self.set_session_start(value)
            return True
        if (self._daily_start - value) / self._daily_start >= self.daily_loss_limit_pct / 100:
            return self._trip(f"daily loss limit {self.daily_loss_limit_pct}%")
        if self._weekly_start and \
                (self._weekly_start - value) / self._weekly_start >= self.weekly_loss_limit_pct / 100:
            return self._trip(f"weekly loss limit {self.weekly_loss_limit_pct}%")
        if self._consec >= self.max_consecutive_losses:
            return self._trip(f"{self._consec} consecutive losses")
        if current_price and prev_price and prev_price > 0:
            if abs(current_price - prev_price) / prev_price >= self.volatility_halt_pct / 100:
                return self._trip(f"volatility halt > {self.volatility_halt_pct}%")
        return True

    def record_trade_result(self, pnl: float) -> None:
        self._consec = self._consec + 1 if pnl < 0 else 0

    def _trip(self, reason: str) -> bool:
        self.is_tripped = True
        self.trip_reason = reason
        return False

    def manual_reset(self, confirmation: str) -> bool:
        if confirmation != "RESET":
            return False
        self.is_tripped = False
        self.trip_reason = None
        self._consec = 0
        self._daily_start = None
        return True


class ResponseValidator:
    MAX_DAILY_MOVE_PCT = {
        "BTC/USDT": 30, "ETH/USDT": 40, "SOL/USDT": 60, "BNB/USDT": 40,
        "AAPL": 20, "NVDA": 25, "TSLA": 30, "RELIANCE.BO": 20, "TCS.NS": 20,
        "default": 50,
    }

    def __init__(self, max_data_age_seconds: int = 60, clock=time.time):
        self.max_age = max_data_age_seconds
        self._clock = clock
        self._price_history: dict = {}
        self.anomaly_count: dict = {}

    def validate_ticker(self, symbol: str, ticker: dict) -> bool:
        issues = []
        for field in ("last", "high", "low", "timestamp"):
            if ticker.get(field) is None:
                issues.append(f"missing {field}")
        if issues:
            return self._fail(symbol, issues)
        price, high, low = float(ticker["last"]), float(ticker["high"]), float(ticker["low"])
        if not (low <= price <= high):
            issues.append(f"price {price} outside [{low},{high}]")
        if price <= 0:
            issues.append("non-positive price")
        ts = ticker.get("timestamp")
        if ts:
            age = self._clock() * 1000 - ts
            if age / 1000 > self.max_age:
                issues.append(f"stale {age/1000:.0f}s")
        hist = self._price_history.get(symbol)
        if hist:
            move = abs(price - hist[-1]) / hist[-1] * 100 if hist[-1] else 0
            cap = self.MAX_DAILY_MOVE_PCT.get(symbol, self.MAX_DAILY_MOVE_PCT["default"])
            if move > cap:
                issues.append(f"outlier {move:.1f}% > {cap}%")
        if issues:
            return self._fail(symbol, issues)
        self._price_history.setdefault(symbol, deque(maxlen=100)).append(price)
        return True

    def validate_ohlcv(self, symbol: str, candle: list) -> bool:
        if len(candle) < 6:
            return self._fail(symbol, ["short candle"])
        _ts, o, h, low_, c, v = candle[:6]
        issues = []
        if not (low_ <= o <= h):
            issues.append("open out of range")
        if not (low_ <= c <= h):
            issues.append("close out of range")
        if low_ > h:
            issues.append("low > high")
        if v < 0:
            issues.append("negative volume")
        if c <= 0 or o <= 0:
            issues.append("non-positive price")
        return True if not issues else self._fail(symbol, issues)

    def _fail(self, symbol: str, issues: list) -> bool:
        self.anomaly_count[symbol] = self.anomaly_count.get(symbol, 0) + 1
        return False


class TradingGuard:
    """One gate the trading loop calls before acting (complements RiskEngine)."""

    def __init__(self, exchange: str = "binance", circuit=None, validator=None):
        self.rate = RateLimiter(exchange)
        self.circuit = circuit or CircuitBreaker()
        self.validator = validator or ResponseValidator()

    def can_trade(self, portfolio_value: float, current_price=None, prev_price=None) -> bool:
        return self.circuit.check(portfolio_value, current_price, prev_price)

    def record_trade(self, pnl: float) -> None:
        self.circuit.record_trade_result(pnl)
