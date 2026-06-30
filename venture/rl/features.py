"""
venture/rl/features.py — the ONE place that defines the RL observation.

Both training (`train/train_rl.py`) and inference (`engines/rl_quant.py`) import
`build_observation` here, so the feature contract can never drift between them.

Observation (market-only, position-agnostic so train==inference):
    [ last `window` returns ...,  z-score(price vs window),  fast-MA momentum ]
    -> dim = window + 2
Actions: 0 = flat, 1 = long, 2 = short. Reward = position * next_return - tx fee.

License: original code (gymnasium/SB3 are MIT) -> commercial-clean.
"""
from __future__ import annotations

from statistics import mean, pstdev

import numpy as np

DEFAULT_WINDOW = 20
DEFAULT_FAST = 10
OBS_DIM = DEFAULT_WINDOW + 2


def build_observation(history, window: int = DEFAULT_WINDOW, fast: int = DEFAULT_FAST):
    """Return the float32 observation for the latest bar, or None if too short."""
    if history is None or len(history) < window + 1:
        return None
    lb = [float(x) for x in history[-(window + 1):]]      # window+1 closes
    rets = [lb[i] / lb[i - 1] - 1 for i in range(1, len(lb))]  # window returns
    m = mean(lb)
    sd = pstdev(lb) or 1e-9
    z = (lb[-1] - m) / sd
    fb = lb[-(fast + 1):] if len(lb) >= fast + 1 else lb
    fm = mean(fb)
    mom = (lb[-1] - fm) / fm if fm else 0.0
    return np.array(rets + [z, mom], dtype=np.float32)


def make_env(closes, window: int = DEFAULT_WINDOW, fast: int = DEFAULT_FAST,
             fee: float = 0.001):
    """A minimal gymnasium trading env over `closes` using build_observation."""
    import gymnasium as gym
    from gymnasium import spaces

    closes = [float(x) for x in closes]

    class ReturnsTradingEnv(gym.Env):
        metadata: dict = {}

        def __init__(self):
            self.action_space = spaces.Discrete(3)
            self.observation_space = spaces.Box(-np.inf, np.inf, (window + 2,),
                                                dtype=np.float32)

        def _obs(self):
            return build_observation(closes[: self.i + 1], window, fast)

        def reset(self, *, seed=None, options=None):
            super().reset(seed=seed)
            self.i = window
            self.pos = 0
            return self._obs(), {}

        def step(self, action):
            target = {0: 0, 1: 1, 2: -1}[int(action)]
            nxt = closes[self.i + 1] / closes[self.i] - 1
            cost = fee * abs(target - self.pos)
            reward = float(target * nxt - cost)
            self.pos = target
            self.i += 1
            done = self.i >= len(closes) - 1
            return self._obs(), reward, done, False, {}

    return ReturnsTradingEnv()


def evaluate_policy(model, closes, window: int = DEFAULT_WINDOW,
                    fast: int = DEFAULT_FAST, fee: float = 0.001) -> dict:
    """Run a trained policy over `closes` (out-of-sample) and score it."""
    closes = [float(x) for x in closes]
    pos, equity, peak, max_dd, trades = 0, 1.0, 1.0, 0.0, 0
    for i in range(window, len(closes) - 1):
        obs = build_observation(closes[: i + 1], window, fast)
        action, _ = model.predict(obs, deterministic=True)
        target = {0: 0, 1: 1, 2: -1}[int(action)]
        if target != pos:
            trades += 1
        nxt = closes[i + 1] / closes[i] - 1
        equity *= (1 + target * nxt - fee * abs(target - pos))
        pos = target
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
    return {
        "strategy_return_pct": round((equity - 1) * 100, 2),
        "buyhold_pct": round((closes[-1] / closes[window] - 1) * 100, 2),
        "trades": trades,
        "max_dd_pct": round(max_dd * 100, 2),
    }
