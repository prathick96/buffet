"""
venture/tests/test_guard.py — ported security guard (rate limiter / circuit breaker / validator).
Run:  python venture/tests/test_guard.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from security.guard import CircuitBreaker, RateLimiter, ResponseValidator  # noqa: E402


def test_circuit_breaker_daily_loss():
    cb = CircuitBreaker(daily_loss_limit_pct=5)
    assert cb.check(100.0)        # sets session start
    assert cb.check(96.0)         # -4% ok
    assert not cb.check(94.0)     # -6% -> trip
    assert cb.is_tripped
    print("PASS circuit_breaker_daily_loss")


def test_circuit_breaker_consecutive_and_reset():
    cb = CircuitBreaker(max_consecutive_losses=3)
    cb.check(100.0)
    for _ in range(3):
        cb.record_trade_result(-1.0)
    assert not cb.check(100.0)            # 3 in a row -> trip
    assert cb.manual_reset("RESET")
    assert cb.check(100.0)
    print("PASS circuit_breaker_consecutive_and_reset")


def test_circuit_breaker_volatility():
    cb = CircuitBreaker(volatility_halt_pct=10)
    cb.check(100.0)
    assert not cb.check(100.0, current_price=120, prev_price=100)   # +20% move
    print("PASS circuit_breaker_volatility")


def test_response_validator():
    v = ResponseValidator(clock=lambda: 1000.0)
    good = {"last": 100, "high": 101, "low": 99, "timestamp": 1000.0 * 1000}
    assert v.validate_ticker("BTC/USDT", good)
    assert not v.validate_ticker("BTC/USDT", {"last": 100})              # missing fields
    assert not v.validate_ticker("BTC/USDT",
                                 {"last": 300, "high": 101, "low": 99,
                                  "timestamp": 1000.0 * 1000})           # out of range
    assert v.validate_ohlcv("X", [0, 10, 12, 9, 11, 100])
    assert not v.validate_ohlcv("X", [0, 10, 8, 9, 11, 100])            # open>high
    print("PASS response_validator")


def test_rate_limiter_window_and_backoff():
    t = [1000.0]
    rl = RateLimiter("binance", clock=lambda: t[0], sleeper=lambda s: None, jitter=lambda: 0.0)
    for _ in range(20):                  # binance public limit = 20/s
        rl.wait_if_needed("public")
    assert rl.wait_if_needed("public") > 0      # 21st in same second must wait
    c1 = rl.report_rate_limit_error("order")
    c2 = rl.report_rate_limit_error("order")
    assert c1 == 60 and c2 == 120               # escalating backoff
    print("PASS rate_limiter_window_and_backoff")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} GUARD TESTS PASSED")
