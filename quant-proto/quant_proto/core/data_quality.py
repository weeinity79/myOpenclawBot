from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List

import pandas as pd


REQUIRED_COLS = ("Date", "Open", "High", "Low", "Close", "Volume")


@dataclass(frozen=True)
class DataQualityConfig:
    min_coverage: float = 0.95


@dataclass
class DataIssue:
    level: str  # warning|error
    symbol: str
    day: str
    rule: str
    detail: str = ""

    def fmt(self) -> str:
        return f"[DATA_ERROR] symbol={self.symbol} day={self.day} rule={self.rule}" + (f" detail={self.detail}" if self.detail else "")


@dataclass
class DataQualityReport:
    passed: bool
    config: dict
    total_symbols: int
    warnings: List[dict]
    errors: List[dict]


def _issue(level: str, symbol: str, day: str, rule: str, detail: str = "") -> DataIssue:
    return DataIssue(level=level, symbol=symbol, day=day, rule=rule, detail=detail)


def validate_data(
    data_by_symbol: Dict[str, pd.DataFrame],
    *,
    start: date,
    end: date,
    cfg: DataQualityConfig,
) -> DataQualityReport:
    warnings: List[DataIssue] = []
    errors: List[DataIssue] = []

    # coverage baseline = max in-window rows among symbols
    in_window_counts: dict[str, int] = {}
    for sym, df in data_by_symbol.items():
        d = pd.to_datetime(df.get("Date"), errors="coerce") if "Date" in df.columns else pd.Series(dtype="datetime64[ns]")
        n = int(((d.dt.date >= start) & (d.dt.date <= end)).sum()) if len(d) else 0
        in_window_counts[sym] = n
    baseline = max(in_window_counts.values()) if in_window_counts else 0

    for sym, df in data_by_symbol.items():
        # required columns
        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            errors.append(_issue("error", sym, "NA", "missing_required_columns", ",".join(missing)))
            continue

        t = df.copy()
        t["Date"] = pd.to_datetime(t["Date"], errors="coerce")
        bad_date = t["Date"].isna()
        if bad_date.any():
            i = int(bad_date.idxmax())
            errors.append(_issue("error", sym, "NA", "invalid_date", f"row={i}"))

        # monotonic + duplicate dates
        if not t["Date"].is_monotonic_increasing:
            errors.append(_issue("error", sym, "NA", "date_not_monotonic"))
        dup = t["Date"].duplicated(keep=False)
        if dup.any():
            d0 = str(pd.to_datetime(t.loc[dup, "Date"].iloc[0]).date())
            errors.append(_issue("error", sym, d0, "date_duplicated"))

        # numeric + positive checks
        for c in ("Open", "High", "Low", "Close"):
            t[c] = pd.to_numeric(t[c], errors="coerce")
            non_num = t[c].isna()
            if non_num.any():
                d0 = str(pd.to_datetime(t.loc[non_num, "Date"].iloc[0]).date()) if t.loc[non_num, "Date"].notna().any() else "NA"
                errors.append(_issue("error", sym, d0, "non_numeric_price", c))
            non_pos = t[c] <= 0
            if non_pos.any():
                d0 = str(pd.to_datetime(t.loc[non_pos, "Date"].iloc[0]).date())
                errors.append(_issue("error", sym, d0, "non_positive_price", c))

        # high/low consistency
        bad_high = t["High"] < t[["Open", "Close"]].max(axis=1)
        if bad_high.any():
            d0 = str(pd.to_datetime(t.loc[bad_high, "Date"].iloc[0]).date())
            errors.append(_issue("error", sym, d0, "high_lt_max_open_close"))

        bad_low = t["Low"] > t[["Open", "Close"]].min(axis=1)
        if bad_low.any():
            d0 = str(pd.to_datetime(t.loc[bad_low, "Date"].iloc[0]).date())
            errors.append(_issue("error", sym, d0, "low_gt_min_open_close"))

        bad_hl = t["High"] < t["Low"]
        if bad_hl.any():
            d0 = str(pd.to_datetime(t.loc[bad_hl, "Date"].iloc[0]).date())
            errors.append(_issue("error", sym, d0, "high_lt_low"))

        # coverage check
        if baseline > 0:
            cov = float(in_window_counts[sym]) / float(baseline)
            if cov < cfg.min_coverage:
                warnings.append(_issue("warning", sym, "NA", "low_coverage", f"coverage={cov:.4f}<min={cfg.min_coverage:.4f}"))

    return DataQualityReport(
        passed=(len(errors) == 0),
        config={"min_coverage": cfg.min_coverage},
        total_symbols=len(data_by_symbol),
        warnings=[vars(x) for x in warnings],
        errors=[vars(x) for x in errors],
    )
