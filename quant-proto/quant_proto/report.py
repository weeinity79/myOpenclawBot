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
    start_nav: float
    end_nav: float
    n_days: int
    n_fills: int


def _latest_run_dir(runs_dir: Path) -> Path:
    if not runs_dir.exists():
        raise RuntimeError(f"Runs dir not found: {runs_dir}")
    dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    if not dirs:
        raise RuntimeError(f"No runs found in {runs_dir}")
    return sorted(dirs)[-1]


def load_report(run_dir: Optional[Path] = None, runs_dir: Path = Path("runs")) -> tuple[Report, Path]:
    if run_dir is None:
        run_dir = _latest_run_dir(runs_dir)

    eq = pd.read_csv(run_dir / "equity_curve.csv")
    if eq.empty:
        raise RuntimeError("Empty equity curve")

    eq["nav"] = pd.to_numeric(eq["nav"], errors="coerce")
    eq = eq.dropna(subset=["nav"]).reset_index(drop=True)

    nav = eq["nav"].values
    rets = nav[1:] / nav[:-1] - 1.0

    start_nav = float(nav[0])
    end_nav = float(nav[-1])
    total_return = end_nav / start_nav - 1.0

    n_days = len(eq)
    years = n_days / 252.0
    cagr = (end_nav / start_nav) ** (1.0 / years) - 1.0 if years > 0 else 0.0

    vol = float(np.std(rets, ddof=1) * np.sqrt(252.0)) if len(rets) > 2 else 0.0
    sharpe = float((np.mean(rets) * 252.0) / (np.std(rets, ddof=1) * np.sqrt(252.0))) if len(rets) > 10 and np.std(rets, ddof=1) > 0 else 0.0

    max_dd = float(pd.to_numeric(eq["drawdown"], errors="coerce").max())

    fills_path = run_dir / "fills.csv"
    n_fills = 0
    if fills_path.exists():
        fills = pd.read_csv(fills_path)
        n_fills = int(len(fills))

    rep = Report(
        total_return=total_return,
        cagr=cagr,
        vol=vol,
        sharpe=sharpe,
        max_drawdown=max_dd,
        start_nav=start_nav,
        end_nav=end_nav,
        n_days=n_days,
        n_fills=n_fills,
    )
    return rep, run_dir


def format_report(rep: Report) -> str:
    return (
        f"Run summary\n"
        f"- Days: {rep.n_days}\n"
        f"- Start NAV: {rep.start_nav:,.2f}\n"
        f"- End NAV: {rep.end_nav:,.2f}\n"
        f"- Total return: {rep.total_return*100:.2f}%\n"
        f"- CAGR (approx): {rep.cagr*100:.2f}%\n"
        f"- Vol (ann.): {rep.vol*100:.2f}%\n"
        f"- Sharpe (rf=0): {rep.sharpe:.2f}\n"
        f"- Max drawdown: {rep.max_drawdown*100:.2f}%\n"
        f"- Fills: {rep.n_fills}\n"
    )
