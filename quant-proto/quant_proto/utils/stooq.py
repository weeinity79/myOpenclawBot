from __future__ import annotations

import io
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class StooqConfig:
    base_url: str = "https://stooq.com/q/d/l/"
    # stooq supports: ?s=spy.us&i=d


def stooq_symbol(etf_symbol: str) -> str:
    # Stooq uses lowercase and a market suffix for US tickers.
    return f"{etf_symbol.lower()}.us"


def fetch_daily_ohlcv_from_stooq(symbol: str, cfg: StooqConfig = StooqConfig()) -> pd.DataFrame:
    """Fetch daily OHLCV from Stooq.

    Returns a DataFrame with columns: Date, Open, High, Low, Close, Volume.
    Date is datetime64[ns] (naive), sorted ascending.

    Notes:
    - Stooq data is not always perfectly 'unadjusted' depending on the instrument.
      For this prototype we treat it as raw tradable OHLCV.
    """
    sym = stooq_symbol(symbol)
    url = f"{cfg.base_url}?s={sym}&i=d"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to fetch {symbol} from Stooq: {e}")

    df = pd.read_csv(io.BytesIO(data))
    if df.empty:
        raise RuntimeError(f"No data returned for {symbol} ({url})")

    # Standardize columns
    df.columns = [c.strip().title() for c in df.columns]
    if "Date" not in df.columns:
        raise RuntimeError(f"Unexpected columns for {symbol}: {list(df.columns)}")

    df["Date"] = pd.to_datetime(df["Date"], utc=False)
    df = df.sort_values("Date").reset_index(drop=True)

    # Ensure float columns
    for c in ["Open", "High", "Low", "Close"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "Volume" in df.columns:
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype(int)

    df = df.dropna(subset=["Open", "High", "Low", "Close"]).copy()
    return df[["Date", "Open", "High", "Low", "Close", "Volume"]]


def cache_path(data_dir: Path, symbol: str) -> Path:
    return data_dir / "stooq" / f"{symbol.upper()}.csv"


def load_cached(data_dir: Path, symbol: str) -> pd.DataFrame | None:
    p = cache_path(data_dir, symbol)
    if not p.exists():
        return None
    df = pd.read_csv(p)
    df["Date"] = pd.to_datetime(df["Date"], utc=False)
    return df


def save_cached(data_dir: Path, symbol: str, df: pd.DataFrame) -> Path:
    p = cache_path(data_dir, symbol)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False)
    return p


def ensure_data(data_dir: Path, symbol: str, force: bool = False) -> pd.DataFrame:
    """Load cached Stooq data or fetch and cache."""
    if not force:
        cached = load_cached(data_dir, symbol)
        if cached is not None and len(cached) > 100:
            return cached

    df = fetch_daily_ohlcv_from_stooq(symbol)
    save_cached(data_dir, symbol, df)
    return df


def data_freshness_utc(df: pd.DataFrame) -> str:
    if df.empty:
        return "unknown"
    d = pd.to_datetime(df["Date"].max()).to_pydatetime()
    if d.tzinfo is None:
        # treat as local naive
        return d.strftime("%Y-%m-%d")
    return d.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d")
