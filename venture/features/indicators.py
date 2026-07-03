"""
venture/features/indicators.py — technical indicators (ported from the legacy
add_indicators, reimplemented in pure pandas so there's no pandas-ta dependency).

RSI, MACD, Bollinger Bands, EMA(50/200), ATR, volume ratio, 1-bar return.
Feeds the Analyst/Quant richer features than raw price.

License: original code (pandas/numpy are BSD) -> commercial-clean.
"""
from __future__ import annotations

import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / down.replace(0, 1e-9)
    return 100 - 100 / (1 + rs)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return line, sig, line - sig


def bollinger(close: pd.Series, n: int = 20, std: float = 2.0):
    mid = sma(close, n)
    sd = close.rolling(n).std()
    upper, lower = mid + std * sd, mid - std * sd
    pct = (close - lower) / (upper - lower).replace(0, 1e-9)
    return upper, mid, lower, pct


def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    prev = close.shift(1)
    tr = pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add the full indicator set to an OHLCV frame (needs at least a 'close' col)."""
    df = df.copy()
    for c in ("open", "high", "low", "close", "volume"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    close = df["close"]
    df["rsi_14"] = rsi(close)
    df["macd"], df["macd_signal"], df["macd_hist"] = macd(close)
    df["bb_upper"], df["bb_middle"], df["bb_lower"], df["bb_pct"] = bollinger(close)
    df["ema_50"], df["ema_200"] = ema(close, 50), ema(close, 200)
    if {"high", "low"} <= set(df.columns):
        df["atr_14"] = atr(df["high"], df["low"], close)
    if "volume" in df:
        df["volume_sma_20"] = sma(df["volume"], 20)
        df["volume_ratio"] = df["volume"] / df["volume_sma_20"].replace(0, 1e-9)
    df["return_1d"] = close.pct_change() * 100
    return df
