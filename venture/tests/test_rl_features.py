"""
venture/tests/test_rl_features.py — shared RL observation contract (no torch/gym).
Run:  python venture/tests/test_rl_features.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rl.features import OBS_DIM, build_observation  # noqa: E402


def test_obs_dim_and_finite():
    closes = [round(100 * (1.001 ** i), 4) for i in range(60)]
    obs = build_observation(closes)
    assert obs is not None and len(obs) == OBS_DIM
    assert all(math.isfinite(float(x)) for x in obs)
    print(f"PASS obs_dim_and_finite (dim={len(obs)})")


def test_insufficient_history_returns_none():
    assert build_observation([100, 101, 102]) is None
    print("PASS insufficient_history_returns_none")


def test_uptrend_has_positive_momentum_feature():
    closes = [round(100 * (1.01 ** i), 4) for i in range(40)]
    obs = build_observation(closes)
    assert obs[-1] > 0   # fast-MA momentum feature positive in an uptrend
    print(f"PASS uptrend_has_positive_momentum_feature (mom={float(obs[-1]):.4f})")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"\nALL {len(tests)} RL-FEATURES TESTS PASSED")
