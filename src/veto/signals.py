"""Closed-bar SMA cross and ranking strength.

Fresh-cross only: BUY/SELL fire on the bar the averages cross, otherwise HOLD.
That is the same rule measured in the prior research note.
"""

from __future__ import annotations

import pandas as pd


def sma_cross_signal(values, fast: int = 10, slow: int = 30) -> str:
    """Return BUY/SELL only on a fresh SMA cross, otherwise HOLD."""
    close = pd.Series(values, dtype="float64")
    if len(close) < slow + 2:
        return "HOLD"
    fast_sma = close.rolling(fast).mean()
    slow_sma = close.rolling(slow).mean()
    up = fast_sma.iloc[-2] <= slow_sma.iloc[-2] and fast_sma.iloc[-1] > slow_sma.iloc[-1]
    down = fast_sma.iloc[-2] >= slow_sma.iloc[-2] and fast_sma.iloc[-1] < slow_sma.iloc[-1]
    return "BUY" if up else "SELL" if down else "HOLD"


def cross_strength(values, fast: int = 10, slow: int = 30) -> float:
    """Signed (fast - slow) / slow on the last bar. Higher ranks a BUY first.

    Same-day crosses are filled by this number, not by alphabet. NaN if the
    averages are not defined or the slow average is zero.
    """
    close = pd.Series(values, dtype="float64")
    if len(close) < slow:
        return float("nan")
    fast_sma = float(close.rolling(fast).mean().iloc[-1])
    slow_sma = float(close.rolling(slow).mean().iloc[-1])
    if slow_sma == 0 or pd.isna(fast_sma) or pd.isna(slow_sma):
        return float("nan")
    return (fast_sma - slow_sma) / slow_sma
