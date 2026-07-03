"""
venture/tests/test_anthropic_brain.py — cloud Anthropic brain (offline; no API calls).
Run:  python venture/tests/test_anthropic_brain.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from brain.anthropic_brain import AnthropicBrain  # noqa: E402
from contracts import MarketSnapshot  # noqa: E402
from security.secrets import _dotenv_cache  # noqa: E402


def _snap():
    return MarketSnapshot(symbol="BTC/USDT", price=60000,
                          indicators={"sma": 59000, "momentum": 0.01},
                          news=[{"title": "Bitcoin ETF inflows surge to record"}],
                          retrieved_context=["Buffett: buy quality at fair prices"])


def test_parse_robust():
    p = AnthropicBrain._parse
    assert p('{"sentiment":"BULLISH","score":0.7,"rationale":"x","key_factors":["a"]}')["sentiment"] == "BULLISH"
    assert p('```json\n{"sentiment":"BEARISH","score":-0.4}\n```')["sentiment"] == "BEARISH"
    assert p('Here is my read: {"sentiment":"NEUTRAL","score":0.0} done')["sentiment"] == "NEUTRAL"
    assert p('{"score":5}')["score"] == 1.0            # clamped to [-1,1]
    print("PASS parse_robust")


def test_prompt_building():
    b = AnthropicBrain(model="claude-opus-4-8", persona="test-persona")
    sysp = b._system()
    assert "JSON" in sysp and "sentiment" in sysp and "test-persona" in sysp
    usr = b._user(_snap())
    assert "BTC/USDT" in usr and "ETF inflows" in usr and "momentum" in usr
    print("PASS prompt_building")


def test_missing_key_degrades_to_neutral():
    old = os.environ.pop("ANTHROPIC_API_KEY", None)
    _dotenv_cache.clear()
    try:
        out = AnthropicBrain()(_snap())
        assert out["sentiment"] == "NEUTRAL" and "error" in out["key_factors"]
    finally:
        if old:
            os.environ["ANTHROPIC_API_KEY"] = old
    print("PASS missing_key_degrades_to_neutral")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} ANTHROPIC-BRAIN TESTS PASSED")
