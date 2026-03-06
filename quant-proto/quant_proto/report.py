from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Report:
    total_return: float
    cagr: float
    vol: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    turnover: float
    start_nav: float
    end_nav: float
    n_days: int
    n_fills: int


@dataclass(frozen=True)
class ComparisonReport:
    strategy: Report
    benchmark: Report
    delta: Report


def _latest_run_dir(runs_dir: Path) -> Path:
    if not runs_dir.exists():
        raise RuntimeError(f"Runs dir not found: {runs_dir}")
    dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    if not dirs:
        raise RuntimeError(f"No runs found in {runs_dir}")
    return sorted(dirs)[-1]


def _load_equity_curve(run_dir: Path) -> pd.DataFrame:
    eq = pd.read_csv(run_dir / "equity_curve.csv")
    if eq.empty:
        raise RuntimeError("Empty equity curve")
    if "day" not in eq.columns or "nav" not in eq.columns:
        raise RuntimeError("equity_curve.csv must include day/nav")

    eq["day"] = pd.to_datetime(eq["day"], errors="coerce")
    eq["nav"] = pd.to_numeric(eq["nav"], errors="coerce")
    eq = eq.dropna(subset=["day", "nav"]).sort_values("day").reset_index(drop=True)
    if eq.empty:
        raise RuntimeError("Empty equity curve after day/nav normalization")
    return eq


def _load_fills(run_dir: Path) -> pd.DataFrame:
    fills_path = run_dir / "fills.csv"
    if not fills_path.exists():
        return pd.DataFrame(columns=["day", "notional"])
    fills = pd.read_csv(fills_path)
    if fills.empty:
        return pd.DataFrame(columns=["day", "notional"])

    required = {"day", "notional"}
    if not required.issubset(set(fills.columns)):
        raise RuntimeError("fills.csv must include day/notional")

    fills["day"] = pd.to_datetime(fills["day"], errors="coerce")
    fills["notional"] = pd.to_numeric(fills["notional"], errors="coerce").abs()
    fills = fills.dropna(subset=["day", "notional"]).reset_index(drop=True)
    return fills


def _calc_metrics(nav: pd.Series, n_fills: int, turnover: pd.Series | None = None) -> Report:
    nav = pd.to_numeric(nav, errors="coerce").dropna().astype(float)
    if nav.empty:
        raise RuntimeError("Empty NAV series")

    rets = nav.pct_change().dropna()

    start_nav = float(nav.iloc[0])
    end_nav = float(nav.iloc[-1])
    total_return = end_nav / start_nav - 1.0 if start_nav != 0 else 0.0

    n_days = int(len(nav))
    years = n_days / 252.0
    cagr = (end_nav / start_nav) ** (1.0 / years) - 1.0 if years > 0 and start_nav > 0 and end_nav > 0 else 0.0

    # Edge-case policy: short samples (<20 trading days) degrade vol/sharpe to 0.
    if len(rets) >= 20:
        stdev = float(np.std(rets.values, ddof=1))
        vol = stdev * np.sqrt(252.0) if stdev > 0 else 0.0
        sharpe = ((float(np.mean(rets.values)) * 252.0) / (stdev * np.sqrt(252.0))) if stdev > 0 else 0.0
    else:
        vol = 0.0
        sharpe = 0.0

    running_max = nav.cummax()
    drawdown = 1.0 - nav / running_max
    max_dd = float(drawdown.max()) if len(drawdown) else 0.0

    win_rate = float((rets > 0).mean()) if len(rets) else 0.0

    if turnover is None or turnover.empty:
        turnover_val = 0.0
    else:
        turnover_val = float(pd.to_numeric(turnover, errors="coerce").fillna(0.0).mean())

    return Report(
        total_return=total_return,
        cagr=cagr,
        vol=vol,
        sharpe=sharpe,
        max_drawdown=max_dd,
        win_rate=win_rate,
        turnover=turnover_val,
        start_nav=start_nav,
        end_nav=end_nav,
        n_days=n_days,
        n_fills=n_fills,
    )


def _resolve_data_dir(run_dir: Path) -> Path:
    cfg_path = run_dir / "config.json"
    if cfg_path.exists():
        cfg = pd.read_json(cfg_path, typ="series")
        data_dir = Path(str(cfg.get("data_dir", "data")))
    else:
        data_dir = Path("data")

    if data_dir.is_absolute():
        return data_dir

    # Typical structure: quant-proto/runs/<run-id>/
    candidate = run_dir.parent.parent / data_dir
    return candidate if candidate.exists() else data_dir


def _load_benchmark_nav(
    run_dir: Path,
    benchmark_symbol: str,
    strategy_days: pd.DatetimeIndex,
    strategy_start_nav: float,
) -> pd.Series:
    symbol = benchmark_symbol.upper()
    csv_path = _resolve_data_dir(run_dir) / "stooq" / f"{symbol}.csv"
    if not csv_path.exists():
        raise RuntimeError(f"benchmark missing file for symbol={symbol}: {csv_path}")

    try:
        bench = pd.read_csv(csv_path)
    except Exception as exc:
        raise RuntimeError(f"benchmark read error for symbol={symbol}: {exc}") from exc

    if bench.empty:
        raise RuntimeError(f"benchmark empty file for symbol={symbol}: {csv_path}")
    required_cols = {"Date", "Close"}
    if not required_cols.issubset(set(bench.columns)):
        raise RuntimeError(f"benchmark missing required columns for symbol={symbol}: required={sorted(required_cols)}")

    bench["Date"] = pd.to_datetime(bench["Date"], errors="coerce")
    bench["Close"] = pd.to_numeric(bench["Close"], errors="coerce")
    bench = bench.dropna(subset=["Date", "Close"]).sort_values("Date")
    if bench.empty:
        raise RuntimeError(f"benchmark has no valid Date/Close rows for symbol={symbol}")

    bench = bench.drop_duplicates(subset=["Date"], keep="last").set_index("Date")
    reindexed = bench.reindex(strategy_days)

    missing_days = reindexed.index[reindexed["Close"].isna()]
    if len(missing_days) > 0:
        rng_start = strategy_days.min().date()
        rng_end = strategy_days.max().date()
        first_missing = missing_days.min().date()
        last_missing = missing_days.max().date()
        raise RuntimeError(
            "benchmark date alignment failed "
            f"for symbol={symbol}: strategy_range={rng_start}..{rng_end}, "
            f"missing_dates={first_missing}..{last_missing}, missing_count={len(missing_days)}"
        )

    closes = reindexed["Close"].astype(float)
    bench_nav = closes / float(closes.iloc[0]) * float(strategy_start_nav)
    bench_nav.index = strategy_days
    return bench_nav


def load_report(run_dir: Optional[Path] = None, runs_dir: Path = Path("runs")) -> tuple[Report, Path]:
    if run_dir is None:
        run_dir = _latest_run_dir(runs_dir)

    eq = _load_equity_curve(run_dir)
    fills = _load_fills(run_dir)

    turnover = pd.Series(0.0, index=eq["day"])  # daily turnover proxy
    if not fills.empty:
        daily_notional = fills.groupby("day")["notional"].sum()
        daily = pd.DataFrame({"day": eq["day"], "nav": eq["nav"]}).set_index("day")
        daily = daily.join(daily_notional.rename("notional"), how="left").fillna(0.0)
        turnover = (daily["notional"] / daily["nav"].replace(0.0, np.nan)).fillna(0.0)

    rep = _calc_metrics(nav=eq["nav"], n_fills=int(len(fills)), turnover=turnover)
    return rep, run_dir


def load_comparison_report(
    run_dir: Optional[Path] = None,
    runs_dir: Path = Path("runs"),
    benchmark_symbol: str = "SPY",
) -> tuple[ComparisonReport, Path]:
    strategy, resolved = load_report(run_dir=run_dir, runs_dir=runs_dir)
    eq = _load_equity_curve(resolved)
    days = pd.DatetimeIndex(eq["day"])  # already normalized in _load_equity_curve

    benchmark_nav = _load_benchmark_nav(
        run_dir=resolved,
        benchmark_symbol=benchmark_symbol,
        strategy_days=days,
        strategy_start_nav=strategy.start_nav,
    )
    benchmark = _calc_metrics(nav=benchmark_nav, n_fills=0, turnover=pd.Series(0.0, index=benchmark_nav.index))

    delta = Report(
        total_return=strategy.total_return - benchmark.total_return,
        cagr=strategy.cagr - benchmark.cagr,
        vol=strategy.vol - benchmark.vol,
        sharpe=strategy.sharpe - benchmark.sharpe,
        max_drawdown=strategy.max_drawdown - benchmark.max_drawdown,
        win_rate=strategy.win_rate - benchmark.win_rate,
        turnover=strategy.turnover - benchmark.turnover,
        start_nav=strategy.start_nav - benchmark.start_nav,
        end_nav=strategy.end_nav - benchmark.end_nav,
        n_days=strategy.n_days - benchmark.n_days,
        n_fills=strategy.n_fills - benchmark.n_fills,
    )

    return ComparisonReport(strategy=strategy, benchmark=benchmark, delta=delta), resolved


def _format_section(title: str, rep: Report) -> str:
    return (
        f"{title}\n"
        f"- Total Return: {rep.total_return*100:.2f}%\n"
        f"- CAGR: {rep.cagr*100:.2f}%\n"
        f"- Volatility(ann): {rep.vol*100:.2f}%\n"
        f"- Sharpe(rf=0): {rep.sharpe:.4f}\n"
        f"- Max Drawdown: {rep.max_drawdown*100:.2f}%\n"
        f"- Win Rate: {rep.win_rate*100:.2f}%\n"
        f"- Turnover: {rep.turnover*100:.2f}%\n"
    )


def format_report(rep: Report) -> str:
    return (
        f"Run summary\n"
        f"- Days: {rep.n_days}\n"
        f"- Start NAV: {rep.start_nav:,.2f}\n"
        f"- End NAV: {rep.end_nav:,.2f}\n"
        f"- Total Return: {rep.total_return*100:.2f}%\n"
        f"- CAGR: {rep.cagr*100:.2f}%\n"
        f"- Volatility(ann): {rep.vol*100:.2f}%\n"
        f"- Sharpe(rf=0): {rep.sharpe:.4f}\n"
        f"- Max Drawdown: {rep.max_drawdown*100:.2f}%\n"
        f"- Win Rate: {rep.win_rate*100:.2f}%\n"
        f"- Turnover: {rep.turnover*100:.2f}%\n"
        f"- Fills: {rep.n_fills}\n"
    )


def format_comparison_report(comp: ComparisonReport, benchmark_symbol: str = "SPY") -> str:
    return (
        _format_section("Strategy", comp.strategy)
        + "\n"
        + _format_section(f"Benchmark({benchmark_symbol.upper()})", comp.benchmark)
        + "\n"
        + _format_section("Delta(Strategy-Benchmark)", comp.delta)
    )
