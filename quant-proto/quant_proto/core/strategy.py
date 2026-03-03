from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd

from quant_proto.core.indicators import sma


@dataclass(frozen=True)
class TrendStrategyConfig:
    ma_fast: int = 20
    ma_slow: int = 100
    top_k: Optional[int] = 3
    rebalance: str = "daily"  # prototype: daily only


def compute_signal_frame(df: pd.DataFrame, cfg: TrendStrategyConfig) -> pd.DataFrame:
    out = df.copy()
    out["ma_fast"] = sma(out["Close"], cfg.ma_fast)
    out["ma_slow"] = sma(out["Close"], cfg.ma_slow)
    out["trend"] = out["ma_fast"] > out["ma_slow"]
    out["trend_strength"] = (out["ma_fast"] / out["ma_slow"]).replace([pd.NA, pd.NaT], None)
    return out


def target_weights_for_date(
    signals_by_symbol: Dict[str, pd.DataFrame],
    asof_ts: pd.Timestamp,
    cfg: TrendStrategyConfig,
    max_gross: float = 1.0,
) -> Dict[str, float]:
    """Compute target weights using signals as-of close at asof_ts.

    Output weights sum to <= max_gross.
    """
    elig = []
    for sym, sdf in signals_by_symbol.items():
        row = sdf.loc[sdf["Date"] == asof_ts]
        if row.empty:
            continue
        r0 = row.iloc[0]
        if bool(r0.get("trend")):
            strength = float(r0.get("trend_strength")) if pd.notna(r0.get("trend_strength")) else 0.0
            elig.append((sym, strength))

    if not elig:
        return {}

    elig.sort(key=lambda x: x[1], reverse=True)
    if cfg.top_k is not None:
        elig = elig[: int(cfg.top_k)]

    n = len(elig)
    w = max_gross / n
    return {sym: w for sym, _ in elig}
