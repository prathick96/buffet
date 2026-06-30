"""
venture/tests/test_judge.py — tunable Judge logic.
Run:  python venture/tests/test_judge.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph.debate import ASSERTIVE_JUDGE, CONSERVATIVE_JUDGE, JudgeConfig  # noqa: E402


def test_assertive_gives_higher_conviction():
    base, bull, bear, quant = 0.6, 0.8, 0.1, 0.5
    cons, _ = CONSERVATIVE_JUDGE.evaluate(base, bull, bear, quant)
    asrt, _ = ASSERTIVE_JUDGE.evaluate(base, bull, bear, quant)
    assert asrt > cons
    print(f"PASS assertive_gives_higher_conviction (cons={cons:.3f}, assertive={asrt:.3f})")


def test_bear_veto_stands_down():
    judged, note = JudgeConfig().evaluate(0.7, bull=0.1, bear=0.7, quant=-0.5)
    assert judged == 0.0 and "stand down" in note
    print("PASS bear_veto_stands_down")


def test_quant_disagreement_lowers_conviction():
    base, bull, bear = 0.6, 0.7, 0.2
    with_q, _ = JudgeConfig().evaluate(base, bull, bear, quant=0.8)
    against_q, _ = JudgeConfig().evaluate(base, bull, bear, quant=-0.8)
    assert with_q > against_q
    print(f"PASS quant_disagreement_lowers_conviction (agree={with_q:.3f}, disagree={against_q:.3f})")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} JUDGE TESTS PASSED")
