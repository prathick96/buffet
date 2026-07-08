"""
venture/train/retrain.py — walk-forward GATED PPO retrain (scheduled adaptation).

The stable way to "retrain the model": never blindly overwrite a live policy.
First prove the approach still generalizes out-of-sample via rolling walk-forward,
and ONLY if it beats buy-and-hold on average AND on a majority of folds do we
retrain on the full recent window and deploy the new policy. Otherwise we keep
the incumbent — a failed gate is information, not a reason to ship noise.

Run:  python venture/train/retrain.py BTC/USDT
      python venture/train/retrain.py BTC/USDT 1500 600 150 150 8000
        (symbol limit train test step steps)

Schedule it (cron / GitHub Actions, weekly) alongside the hourly scout cycle.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)


def gate(agg: dict, min_edge_pct: float = 0.0) -> bool:
    """Deploy only if OOS edge clears the bar on average AND on a majority of
    folds. Pure -> unit-testable without torch."""
    return (agg.get("folds", 0) >= 1
            and agg.get("avg_edge_pct", 0.0) > min_edge_pct
            and agg.get("folds_beating_bh", 0) * 2 >= agg.get("folds", 0))


def retrain(symbol: str = "BTC/USDT", limit: int = 1500, train: int = 600,
            test: int = 150, step: int = 150, steps: int = 8000,
            min_edge_pct: float = 0.0, save: bool = True) -> dict:
    from data.providers import CCXTDataProvider
    from eval.walk_forward import run_folds, summarize
    from rl.features import make_env
    from stable_baselines3 import PPO

    print(f"Fetching {limit} x 1h bars for {symbol}...")
    closes = CCXTDataProvider(symbol, timeframe="1h", limit=limit)._closes  # resilient venue
    print(f"  {len(closes)} bars. Walk-forward gate: train={train} test={test} "
          f"step={step} steps={steps}\n")

    agg = summarize(run_folds(closes, train, test, step, steps, verbose=True))
    print(f"\n  OOS avg edge {agg['avg_edge_pct']:+.2f}%  | beating B&H "
          f"{agg['folds_beating_bh']}/{agg['folds']}")

    if not gate(agg, min_edge_pct):
        print("  Gate FAILED — keeping the incumbent policy (no deploy).")
        return {"deployed": False, **agg}

    print("  Gate PASSED — retraining on the full recent window and deploying.")
    model = PPO("MlpPolicy", make_env(closes), verbose=0)
    model.learn(total_timesteps=steps)
    path = os.path.join(_ROOT, "models", f"ppo_quant_{symbol.replace('/', '')}.zip")
    if save:
        os.makedirs(os.path.join(_ROOT, "models"), exist_ok=True)
        model.save(path)
        print(f"  Deployed -> {path}")
    return {"deployed": True, "path": path, **agg}


if __name__ == "__main__":
    a = sys.argv[1:]
    retrain(
        symbol=a[0] if len(a) > 0 else "BTC/USDT",
        limit=int(a[1]) if len(a) > 1 else 1500,
        train=int(a[2]) if len(a) > 2 else 600,
        test=int(a[3]) if len(a) > 3 else 150,
        step=int(a[4]) if len(a) > 4 else 150,
        steps=int(a[5]) if len(a) > 5 else 8000,
    )
