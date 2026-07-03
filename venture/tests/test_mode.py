"""
venture/tests/test_mode.py — paper-only gate (live trading hard-blocked).
Run:  python venture/tests/test_mode.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mode import LIVE_ENV, LiveTradingBlocked, assert_live_allowed, is_live_enabled  # noqa: E402


def test_blocked_by_default():
    os.environ.pop(LIVE_ENV, None)
    assert not is_live_enabled()
    try:
        assert_live_allowed()
        assert False, "should have raised"
    except LiveTradingBlocked as e:
        assert "ROTATE" in str(e)          # the reminder is baked into the error
    print("PASS blocked_by_default")


def test_explicit_enable():
    os.environ[LIVE_ENV] = "true"
    try:
        assert_live_allowed()              # no raise
        assert is_live_enabled()
    finally:
        del os.environ[LIVE_ENV]
    print("PASS explicit_enable")


def test_junk_values_stay_blocked():
    for junk in ("0", "false", "no", "", "maybe"):
        os.environ[LIVE_ENV] = junk
        assert not is_live_enabled(), junk
    del os.environ[LIVE_ENV]
    print("PASS junk_values_stay_blocked")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} MODE TESTS PASSED")
