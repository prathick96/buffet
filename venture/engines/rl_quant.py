"""
venture/engines/rl_quant.py — RL/PPO quant voice.

Same interface as QuantEngine (`run(snapshot) -> vote dict`), so it drops into
the debate's Quant node. Loads a trained stable-baselines3 PPO policy if given;
otherwise (no model / SB3 not installed / bad obs) it GRACEFULLY FALLS BACK to
the statistical QuantEngine — so the system never breaks waiting on training.

Observation contract (must match venture/train/train_rl.py): the last `window`
per-bar returns. Actions: 0=flat/HOLD, 1=long/BUY, 2=short/SELL.

License: original code (stable-baselines3 is MIT) -> commercial-clean.
"""
from __future__ import annotations

from engines.base import Engine
from engines.quant import QuantEngine


class RLQuantEngine(Engine):
    name = "quant"

    def __init__(self, model_path: str | None = None, window: int = 20, fallback=None):
        self.window = window
        self.fallback = fallback or QuantEngine()
        self.model = None
        self.load_error: str | None = None
        if model_path:
            try:
                from stable_baselines3 import PPO  # lazy/heavy
                self.model = PPO.load(model_path)
            except Exception as e:
                self.load_error = str(e)

    def run(self, snap) -> dict:
        if self.model is None:
            return self._fallback(snap)
        obs = self._obs(snap)
        if obs is None:
            return self._fallback(snap)
        try:
            action, _ = self.model.predict(obs, deterministic=True)
            a = int(action)
        except Exception:
            return self._fallback(snap)
        act, score = {0: ("HOLD", 0.0), 1: ("BUY", 0.6), 2: ("SELL", -0.6)}.get(a, ("HOLD", 0.0))
        return {"action": act, "score": score, "rationale": f"PPO policy -> action {a}",
                "factors": ["ppo_policy"], "source": "rl_ppo"}

    def _fallback(self, snap) -> dict:
        v = self.fallback.run(snap)
        v["source"] = "quant_stat"
        return v

    def _obs(self, snap):
        from rl.features import build_observation  # shared train/inference contract
        return build_observation(snap.history or [], self.window)
