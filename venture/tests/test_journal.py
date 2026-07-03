"""
venture/tests/test_journal.py — local SQLite journal (replaces Supabase logging).
Run:  python venture/tests/test_journal.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from persistence.journal import Journal  # noqa: E402


def test_journal_roundtrip_and_filters():
    j = Journal(":memory:")
    j.log("decision", "BTC/USDT", {"action": "BUY", "conviction": 0.7})
    j.log("decision", "ETH/USDT", {"action": "HOLD"})
    j.log("news", "BTC/USDT", {"title": "x"})
    assert j.count() == 3 and j.count("decision") == 2
    recent = j.recent("decision", symbol="BTC/USDT")
    assert recent and recent[0]["payload"]["action"] == "BUY"
    j.close()
    print("PASS journal_roundtrip_and_filters")


def test_journal_creates_file_path():
    with tempfile.TemporaryDirectory() as d:
        j = Journal(os.path.join(d, "sub", "j.db"))   # nested dir auto-created
        j.log("trade", "X", {"pnl": 1.0})
        assert j.count() == 1
        j.close()
    print("PASS journal_creates_file_path")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} JOURNAL TESTS PASSED")
