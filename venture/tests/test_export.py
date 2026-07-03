"""
venture/tests/test_export.py — dashboard JSON exporter.
Run:  python venture/tests/test_export.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dashboard.export import export  # noqa: E402
from eval.forward_test import ForwardTester  # noqa: E402


def test_export_produces_json():
    with tempfile.TemporaryDirectory() as d:
        fdb = os.path.join(d, "f.db")
        out = os.path.join(d, "data")
        ft = ForwardTester(fdb, horizon_sec=0)
        ft.capture("BTC/USDT", 100.0, "BUY", 0.7, "BULLISH", "etf inflows")
        ft.close()

        export(forward_db=fdb, journal_db=os.path.join(d, "none.db"), out_dir=out)

        for f in ("summary.json", "predictions.json", "agents.json", "logs.json"):
            assert os.path.exists(os.path.join(out, f)), f
        summ = json.load(open(os.path.join(out, "summary.json")))
        assert summ["goal"]["target"] == 250000.0 and summ["counts"]["predictions"] == 1
        preds = json.load(open(os.path.join(out, "predictions.json")))
        assert preds[0]["symbol"] == "BTC/USDT" and preds[0]["action"] == "BUY"
        agents = json.load(open(os.path.join(out, "agents.json")))
        assert len(agents["agents"]) == 9
        print("PASS export_produces_json")


def test_export_no_db_graceful():
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "data")
        s = export(forward_db=os.path.join(d, "none.db"),
                   journal_db=os.path.join(d, "none2.db"), out_dir=out)
        assert os.path.exists(os.path.join(out, "summary.json"))
        assert s["counts"]["predictions"] == 0
        print("PASS export_no_db_graceful")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} EXPORT TESTS PASSED")
