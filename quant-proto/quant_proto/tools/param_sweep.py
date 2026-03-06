from __future__ import annotations

import argparse
import csv
import itertools
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from quant_proto.core.broker import BrokerConfig
from quant_proto.core.sim import SimConfig, run_sim
from quant_proto.core.strategy import TrendStrategyConfig
from quant_proto.core.universe import DEFAULT_UNIVERSE
from quant_proto.report import load_report
from quant_proto.utils.dates import parse_yyyy_mm_dd
from quant_proto.utils.io import ensure_dir, write_json


@dataclass(frozen=True)
class SweepRow:
    ma_fast: int
    ma_slow: int
    top_k: int
    status: str
    reject_reason: str
    train_cagr: float
    train_sharpe: float
    train_maxdd: float
    train_n_fills: int
    oos_cagr: float
    oos_sharpe: float
    oos_maxdd: float
    oos_n_fills: int


def _parse_int_list(s: str) -> list[int]:
    vals = []
    for p in s.split(","):
        p = p.strip()
        if not p:
            continue
        vals.append(int(p))
    if not vals:
        raise ValueError("empty integer list")
    return vals


def _validate_ranges(train_start, train_end, oos_start, oos_end) -> None:
    if train_start > train_end:
        raise ValueError("invalid range: train_start > train_end")
    if oos_start > oos_end:
        raise ValueError("invalid range: oos_start > oos_end")
    if oos_start <= train_end:
        raise ValueError("invalid range: train and oos overlap or touch; require oos_start > train_end")


def _score_key(row: dict, prefix: str) -> tuple:
    # Higher sharpe, then cagr, then lower maxdd, then fills.
    return (
        float(row[f"{prefix}_sharpe"]),
        float(row[f"{prefix}_cagr"]),
        -float(row[f"{prefix}_maxdd"]),
        float(row[f"{prefix}_n_fills"]),
        -int(row["ma_fast"]),
        -int(row["ma_slow"]),
        -int(row["top_k"]),
    )


def _rank_rows(rows: list[dict], prefix: str) -> dict[tuple[int, int, int], int]:
    valid = [r for r in rows if r["status"] == "ok"]
    valid_sorted = sorted(
        valid,
        key=lambda r: _score_key(r, prefix),
        reverse=True,
    )
    out: dict[tuple[int, int, int], int] = {}
    for i, r in enumerate(valid_sorted, start=1):
        out[(int(r["ma_fast"]), int(r["ma_slow"]), int(r["top_k"]))] = i
    return out


def _iter_grid(ma_fast: Iterable[int], ma_slow: Iterable[int], top_k: Iterable[int]):
    # Deterministic ordering.
    for f, s, k in itertools.product(sorted(set(ma_fast)), sorted(set(ma_slow)), sorted(set(top_k))):
        yield int(f), int(s), int(k)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quant_proto.tools.param_sweep", description="Parameter sweep with train/OOS splits")
    p.add_argument("--train-start", required=True, help="YYYY-MM-DD")
    p.add_argument("--train-end", required=True, help="YYYY-MM-DD")
    p.add_argument("--oos-start", required=True, help="YYYY-MM-DD")
    p.add_argument("--oos-end", required=True, help="YYYY-MM-DD")

    p.add_argument("--ma-fast-grid", default="10,20,30")
    p.add_argument("--ma-slow-grid", default="80,100,120")
    p.add_argument("--top-k-grid", default="2,3,4")

    p.add_argument("--symbols", default=",".join(DEFAULT_UNIVERSE), help="Comma-separated symbols")
    p.add_argument("--initial-cash", type=float, default=100_000.0)
    p.add_argument("--data-dir", default="data")
    p.add_argument("--out-dir", default=None, help="Output directory; default runs/sweeps/<timestamp>")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    train_start = parse_yyyy_mm_dd(args.train_start)
    train_end = parse_yyyy_mm_dd(args.train_end)
    oos_start = parse_yyyy_mm_dd(args.oos_start)
    oos_end = parse_yyyy_mm_dd(args.oos_end)

    try:
        _validate_ranges(train_start, train_end, oos_start, oos_end)
    except ValueError as exc:
        print(str(exc), file=__import__("sys").stderr)
        return 2

    symbols = tuple(s.strip().upper() for s in str(args.symbols).split(",") if s.strip())
    if not symbols:
        print("invalid symbols: empty", file=__import__("sys").stderr)
        return 2

    ma_fast_grid = _parse_int_list(args.ma_fast_grid)
    ma_slow_grid = _parse_int_list(args.ma_slow_grid)
    top_k_grid = _parse_int_list(args.top_k_grid)

    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = Path("runs") / "sweeps" / datetime.now().strftime("%Y-%m-%d-%H%M%S")
    ensure_dir(out_dir)
    runs_root = out_dir / "runs"
    ensure_dir(runs_root)

    rows: list[dict] = []
    for ma_fast, ma_slow, top_k in _iter_grid(ma_fast_grid, ma_slow_grid, top_k_grid):
        row = {
            "ma_fast": ma_fast,
            "ma_slow": ma_slow,
            "top_k": top_k,
            "status": "ok",
            "reject_reason": "",
            "train_cagr": 0.0,
            "train_sharpe": 0.0,
            "train_maxdd": 0.0,
            "train_n_fills": 0,
            "oos_cagr": 0.0,
            "oos_sharpe": 0.0,
            "oos_maxdd": 0.0,
            "oos_n_fills": 0,
        }

        if ma_fast >= ma_slow:
            row["status"] = "rejected"
            row["reject_reason"] = "ma_fast_must_be_lt_ma_slow"
            rows.append(row)
            continue
        if top_k < 1 or top_k > len(symbols):
            row["status"] = "rejected"
            row["reject_reason"] = "top_k_out_of_range"
            rows.append(row)
            continue

        cfg = SimConfig(
            start=train_start,
            end=train_end,
            initial_cash=float(args.initial_cash),
            universe=symbols,
            data_dir=str(args.data_dir),
            strategy=TrendStrategyConfig(ma_fast=ma_fast, ma_slow=ma_slow, top_k=top_k),
            broker=BrokerConfig(),
        )
        train_run_dir = run_sim(cfg=cfg, mode="backtest", run_base_dir=runs_root)
        train_rep, _ = load_report(run_dir=train_run_dir)
        row["train_cagr"] = train_rep.cagr
        row["train_sharpe"] = train_rep.sharpe
        row["train_maxdd"] = train_rep.max_drawdown
        row["train_n_fills"] = train_rep.n_fills

        cfg_oos = SimConfig(
            start=oos_start,
            end=oos_end,
            initial_cash=float(args.initial_cash),
            universe=symbols,
            data_dir=str(args.data_dir),
            strategy=TrendStrategyConfig(ma_fast=ma_fast, ma_slow=ma_slow, top_k=top_k),
            broker=BrokerConfig(),
        )
        oos_run_dir = run_sim(cfg=cfg_oos, mode="backtest", run_base_dir=runs_root)
        oos_rep, _ = load_report(run_dir=oos_run_dir)
        row["oos_cagr"] = oos_rep.cagr
        row["oos_sharpe"] = oos_rep.sharpe
        row["oos_maxdd"] = oos_rep.max_drawdown
        row["oos_n_fills"] = oos_rep.n_fills

        rows.append(row)

    rank_train = _rank_rows(rows, "train")
    rank_oos = _rank_rows(rows, "oos")

    for row in rows:
        key = (int(row["ma_fast"]), int(row["ma_slow"]), int(row["top_k"]))
        rt = rank_train.get(key, 0)
        ro = rank_oos.get(key, 0)
        row["rank_train"] = rt
        row["rank_oos"] = ro
        row["stability_score"] = 0.0 if (rt == 0 or ro == 0) else 1.0 / (1.0 + abs(rt - ro))

    rows = sorted(rows, key=lambda r: (r["rank_oos"] if r["rank_oos"] > 0 else 10**9, r["ma_fast"], r["ma_slow"], r["top_k"]))

    csv_path = out_dir / "sweep_results.csv"
    fields = [
        "ma_fast",
        "ma_slow",
        "top_k",
        "status",
        "reject_reason",
        "train_cagr",
        "train_sharpe",
        "train_maxdd",
        "train_n_fills",
        "oos_cagr",
        "oos_sharpe",
        "oos_maxdd",
        "oos_n_fills",
        "rank_train",
        "rank_oos",
        "stability_score",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    ok_rows = [r for r in rows if r["status"] == "ok"]
    recommended = ok_rows[0] if ok_rows else None

    summary = {
        "train": {"start": str(train_start), "end": str(train_end)},
        "oos": {"start": str(oos_start), "end": str(oos_end)},
        "grid": {
            "ma_fast": sorted(set(ma_fast_grid)),
            "ma_slow": sorted(set(ma_slow_grid)),
            "top_k": sorted(set(top_k_grid)),
        },
        "symbols": list(symbols),
        "n_total": len(rows),
        "n_ok": len(ok_rows),
        "n_rejected": len(rows) - len(ok_rows),
        "recommended": recommended,
        "oos_gate": {"min_sharpe": 0.0, "pass": bool(recommended and float(recommended["oos_sharpe"]) > 0.0)},
        "artifacts": {
            "sweep_results_csv": str(csv_path),
            "sweep_summary_json": str(out_dir / "sweep_summary.json"),
        },
    }
    write_json(out_dir / "sweep_summary.json", summary)

    print(f"Sweep out dir: {out_dir}")
    print(f"Rows: total={len(rows)} ok={len(ok_rows)} rejected={len(rows) - len(ok_rows)}")
    if recommended:
        print(
            "Top(OOS): "
            f"fast={recommended['ma_fast']} slow={recommended['ma_slow']} top_k={recommended['top_k']} "
            f"oos_sharpe={float(recommended['oos_sharpe']):.4f} stability={float(recommended['stability_score']):.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
