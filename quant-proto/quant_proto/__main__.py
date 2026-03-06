from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
from typing import List

from quant_proto.core.sim import SimConfig, run_sim
from quant_proto.core.universe import DEFAULT_UNIVERSE
from quant_proto.report import format_comparison_report, format_report, load_comparison_report, load_report
from quant_proto.utils.dates import parse_yyyy_mm_dd


def _parse_symbols(s: str | None) -> tuple[str, ...]:
    if not s:
        return tuple(DEFAULT_UNIVERSE)
    parts = [p.strip().upper() for p in s.split(",") if p.strip()]
    return tuple(parts)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quant_proto", description="US ETF-only daily quant prototype (educational)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--start", required=True, help="YYYY-MM-DD")
        sp.add_argument("--end", required=True, help="YYYY-MM-DD")
        sp.add_argument("--symbols", default=None, help="Comma-separated ETF symbols (default small allowlist)")
        sp.add_argument("--initial-cash", type=float, default=100_000.0)
        sp.add_argument("--slippage-bps", type=float, default=5.0)
        sp.add_argument("--commission-bps", type=float, default=1.0)
        sp.add_argument("--force-refresh-data", action="store_true")

    bt = sub.add_parser("backtest", help="Run backtest and write artifacts to runs/")
    add_common(bt)

    paper = sub.add_parser("paper", help="Run paper sim (same engine) and write artifacts")
    add_common(paper)

    rep = sub.add_parser("report", help="Summarize latest run (or a given run dir)")
    rep.add_argument("--run-dir", default=None, help="Path to a run directory under runs/")
    rep.add_argument("--benchmark", default="SPY", help="Benchmark symbol (default: SPY)")

    return p


def main(argv: List[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.cmd in {"backtest", "paper"}:
        start = parse_yyyy_mm_dd(args.start)
        end = parse_yyyy_mm_dd(args.end)
        symbols = _parse_symbols(args.symbols)

        cfg = SimConfig(
            start=start,
            end=end,
            initial_cash=float(args.initial_cash),
            universe=symbols,
            data_dir="data",
        )
        # override broker params
        cfg = SimConfig(
            start=cfg.start,
            end=cfg.end,
            initial_cash=cfg.initial_cash,
            universe=cfg.universe,
            data_dir=cfg.data_dir,
            strategy=cfg.strategy,
            broker=cfg.broker.__class__(
                slippage_bps=float(args.slippage_bps),
                commission_bps=float(args.commission_bps),
                t_plus_1=True,
            ),
            risk=cfg.risk,
        )

        run_dir = run_sim(
            cfg=cfg,
            mode=args.cmd,
            run_base_dir=Path("runs"),
            force_refresh_data=bool(args.force_refresh_data),
        )
        rep, _ = load_report(run_dir=run_dir)
        print(f"Run dir: {run_dir}")
        print(format_report(rep))
        return

    if args.cmd == "report":
        run_dir = Path(args.run_dir) if args.run_dir else None
        try:
            comp, resolved = load_comparison_report(run_dir=run_dir, benchmark_symbol=str(args.benchmark))
        except RuntimeError as exc:
            print(str(exc), file=__import__("sys").stderr)
            raise SystemExit(1)
        print(f"Run dir: {resolved}")
        print(format_comparison_report(comp, benchmark_symbol=str(args.benchmark)))
        return


if __name__ == "__main__":
    main()
