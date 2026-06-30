"""
venture/eval/walk_forward.py — the honest edge test.

Rolling walk-forward: for each fold, train PPO on a TRAIN window and evaluate the
policy on the NEXT, unseen TEST window. Aggregates out-of-sample (OOS) return vs
buy-and-hold across folds. This is what separates real edge from overfitting.

Run:  python venture/eval/walk_forward.py BTC/USDT
      python venture/eval/walk_forward.py BTC/USDT 1000 400 120 120 8000
        (symbol limit train test step steps)
"""
from __future__ import annotations

import os
import sys
from statistics import mean

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)


def main(symbol: str = "BTC/USDT", limit: int = 1000, train: int = 400,
         test: int = 120, step: int = 120, steps: int = 8000):
    from data.providers import CCXTDataProvider
    from rl.features import DEFAULT_WINDOW as W
    from rl.features import evaluate_policy, make_env
    from stable_baselines3 import PPO

    print(f"Fetching {limit} x 1h bars for {symbol}...")
    closes = CCXTDataProvider(symbol, exchange="binance", timeframe="1h", limit=limit)._closes
    print(f"  {len(closes)} bars. Walk-forward: train={train} test={test} step={step} "
          f"steps={steps}\n")
    print(f"  {'fold':>4} {'OOS strat':>10} {'buy&hold':>9} {'edge':>8} "
          f"{'trades':>7} {'maxDD':>7}")

    folds, start = [], 0
    while start + train + test <= len(closes):
        tr = closes[start: start + train]
        te = closes[start + train - W: start + train + test]   # window lead-in for obs
        model = PPO("MlpPolicy", make_env(tr), verbose=0)
        model.learn(total_timesteps=steps)
        r = evaluate_policy(model, te)
        edge = round(r["strategy_return_pct"] - r["buyhold_pct"], 2)
        folds.append({**r, "edge": edge})
        print(f"  {len(folds):>4} {r['strategy_return_pct']:>9.2f}% {r['buyhold_pct']:>8.2f}% "
              f"{edge:>+7.2f}% {r['trades']:>7} {r['max_dd_pct']:>6.2f}%")
        start += step

    if not folds:
        print("Not enough data for a fold.")
        return
    avg_s = mean(f["strategy_return_pct"] for f in folds)
    avg_b = mean(f["buyhold_pct"] for f in folds)
    avg_e = mean(f["edge"] for f in folds)
    win = sum(1 for f in folds if f["edge"] > 0)
    print("\n" + "-" * 52)
    print(f"  Folds: {len(folds)} | avg OOS strat {avg_s:+.2f}% | avg buy&hold {avg_b:+.2f}%")
    print(f"  Avg edge vs B&H: {avg_e:+.2f}%  | folds beating B&H: {win}/{len(folds)}")
    print("-" * 52)
    verdict = ("EDGE: beats B&H on average" if avg_e > 0 and win * 2 >= len(folds)
               else "NO CLEAR EDGE yet — iterate (more steps/features/data)")
    print(f"  Verdict: {verdict}")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(
        symbol=a[0] if len(a) > 0 else "BTC/USDT",
        limit=int(a[1]) if len(a) > 1 else 1000,
        train=int(a[2]) if len(a) > 2 else 400,
        test=int(a[3]) if len(a) > 3 else 120,
        step=int(a[4]) if len(a) > 4 else 120,
        steps=int(a[5]) if len(a) > 5 else 8000,
    )
