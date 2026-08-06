"""
Tiny pure-numpy replacements for the three TA-Lib indicators the app uses:
SMA, Bollinger Bands, and the slow Stochastic Oscillator.

Kept as leading-NaN arrays so the output length equals the input length,
matching TA-Lib's convention and letting callers index with [-1], [-3:], etc.
"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def _rolling(a: np.ndarray, window: int) -> np.ndarray:
    return sliding_window_view(a, window)


def sma(values, period: int) -> np.ndarray:
    """Simple moving average. Leading (period-1) values are NaN."""
    v = np.asarray(values, dtype=float)
    out = np.full(v.shape, np.nan)
    if len(v) >= period:
        out[period - 1:] = _rolling(v, period).mean(axis=1)
    return out


def bbands(values, period: int, nbdev: float = 2.0):
    """Bollinger Bands using population stddev (ddof=0), matching TA-Lib.

    Returns (upper, middle, lower)."""
    v = np.asarray(values, dtype=float)
    mid = sma(v, period)
    std = np.full(v.shape, np.nan)
    if len(v) >= period:
        std[period - 1:] = _rolling(v, period).std(axis=1, ddof=0)
    return mid + nbdev * std, mid, mid - nbdev * std


def stoch(high, low, close,
          fastk_period: int = 5,
          slowk_period: int = 3,
          slowd_period: int = 3):
    """Slow Stochastic Oscillator (SMA smoothing for both K and D).

    Returns (slowK, slowD). Matches TA-Lib defaults: fastk period configurable,
    both smoothing periods = 3 with SMA (matype=0)."""
    h = np.asarray(high, dtype=float)
    l = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    n = len(c)

    fastk = np.full(n, np.nan)
    if n >= fastk_period:
        h_win = _rolling(h, fastk_period).max(axis=1)
        l_win = _rolling(l, fastk_period).min(axis=1)
        denom = h_win - l_win
        with np.errstate(divide="ignore", invalid="ignore"):
            k_raw = np.where(
                denom == 0,
                0.0,
                100.0 * (c[fastk_period - 1:] - l_win) / denom,
            )
        fastk[fastk_period - 1:] = k_raw

    slowk = sma(fastk, slowk_period)
    slowd = sma(slowk, slowd_period)
    return slowk, slowd
