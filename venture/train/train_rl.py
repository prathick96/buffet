"""
venture/train/train_rl.py — train a PPO quant policy on REAL ccxt data.

Uses the shared env/observation from venture/rl/features.py, so the trained
policy's inputs match RLQuantEngine's inference inputs exactly.

Run:  python venture/train/train_rl.py BTC/USDT 50000
Saves venture/models/ppo_quant_<SYM>.zip  ->  RLQuantEngine(model_path=...).
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)


def main(symbol: str = "BTC/USDT", steps: int = 50000, limit: int = 1000):
    from data.providers import CCXTDataProvider
    from rl.features import DEFAULT_WINDOW, make_env
    from stable_baselines3 import PPO

    print(f"Fetching {limit} x 1h bars for {symbol}...")
    closes = CCXTDataProvider(symbol, exchange="binance", timeframe="1h", limit=limit)._closes
    print(f"  {len(closes)} bars. Training PPO for {steps} steps (window={DEFAULT_WINDOW})...")

    model = PPO("MlpPolicy", make_env(closes), verbose=0)
    model.learn(total_timesteps=steps)

    os.makedirs(os.path.join(_ROOT, "models"), exist_ok=True)
    path = os.path.join(_ROOT, "models", f"ppo_quant_{symbol.replace('/', '')}.zip")
    model.save(path)
    print(f"Saved policy -> {path}")
    return path


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT"
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 50000
    main(sym, steps)
