from __future__ import annotations

import pandas as pd


def sma(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window=window, min_periods=window).mean()


def true_range(high: pd.Series, low: pd.Series, prev_close: pd.Series) -> pd.Series:
    a = (high - low).abs()
    b = (high - prev_close).abs()
    c = (low - prev_close).abs()
    return pd.concat([a, b, c], axis=1).max(axis=1)


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    prev_close = df["Close"].shift(1)
    tr = true_range(df["High"], df["Low"], prev_close)
    return tr.rolling(window=window, min_periods=window).mean()
