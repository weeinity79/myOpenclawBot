"""Daily paper-trading pipeline.

One command to run:
1) paper simulation
2) latest-day order ticket generation
3) concise summary for cron/logging

Exit codes:
  0 success
  1 runtime failure
  2 parameter error
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from quant_proto.utils.dates import parse_yyyy_mm_dd


def _extract_run_dir(text: str) -> str | None:
    m = re.search(r"Run dir:\s*(.+)", text)
    return m.group(1).strip() if m else None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quant_proto.tools.daily_pipeline", description="Run paper + generate latest ticket")
    p.add_argument("--start", default=None, help="YYYY-MM-DD")
    p.add_argument("--end", default=None, help="YYYY-MM-DD")
    p.add_argument("--run-base-dir", default="runs", help="Directory to write run folders")
    p.add_argument("--initial-cash", type=float, default=None)
    p.add_argument("--min-trade-notional", type=float, default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Parameter validation
    try:
        if args.start:
            parse_yyyy_mm_dd(args.start)
        if args.end:
            parse_yyyy_mm_dd(args.end)
    except Exception as exc:
        print(f"[PARAM_ERROR] {exc}", file=sys.stderr)
        return 2

    if args.start and args.end:
        if parse_yyyy_mm_dd(args.start) > parse_yyyy_mm_dd(args.end):
            print("[PARAM_ERROR] start must be <= end", file=sys.stderr)
            return 2

    run_base_dir = Path(args.run_base_dir)
    try:
        run_base_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        print(f"[PIPELINE_ERROR] stage=paper_run rc=1")
        print(f"run_base_dir not writable: {run_base_dir} ({exc})")
        return 1

    py = sys.executable
    paper_cmd = [py, "-m", "quant_proto", "paper"]
    if args.start:
        paper_cmd += ["--start", args.start]
    if args.end:
        paper_cmd += ["--end", args.end]
    if args.initial_cash is not None:
        paper_cmd += ["--initial-cash", str(float(args.initial_cash))]
    if args.min_trade_notional is not None:
        paper_cmd += ["--min-trade-notional", str(float(args.min_trade_notional))]
    paper_cmd += ["--run-base-dir", str(run_base_dir)]

    # paper_run
    p = subprocess.run(paper_cmd, capture_output=True, text=True)
    paper_out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    if p.returncode != 0:
        print(f"[PIPELINE_ERROR] stage=paper_run rc={p.returncode}")
        print(paper_out.strip())
        return 1

    run_dir = _extract_run_dir(paper_out)
    if not run_dir:
        print("[PIPELINE_ERROR] stage=report_gen rc=1")
        print("Could not parse run dir from paper output")
        return 1

    run_dir_path = Path(run_dir)

    # ticket_gen
    t = subprocess.run([py, "-m", "quant_proto.tools.daily_orders", str(run_dir_path)], capture_output=True, text=True)
    ticket_out = (t.stdout or "") + ("\n" + t.stderr if t.stderr else "")
    if t.returncode != 0:
        print(f"[PIPELINE_ERROR] stage=ticket_gen rc={t.returncode}")
        print(ticket_out.strip())
        return 1

    # summary
    print(f"Run dir: {run_dir_path}")
    lines = [ln.strip() for ln in ticket_out.splitlines() if ln.strip()]
    latest = next((ln for ln in lines if ln.startswith("Latest order day:")), "Latest order day: N/A")
    buy = next((ln for ln in lines if ln.startswith("BUY:")), None)
    sell = next((ln for ln in lines if ln.startswith("SELL:")), None)
    no_orders = any(ln == "No orders." for ln in lines)

    print(latest)
    if no_orders:
        print("No orders.")
    else:
        if sell:
            print(sell)
        if buy:
            print(buy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
