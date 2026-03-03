"""Full regression suite for quant-proto.

Runs full backtest + paper over a fixed window and performs basic invariants checks
on produced artifacts.

Usage:
  source .venv/bin/activate
  python -m quant_proto.tools.regression_full

Exit codes:
  0 = PASS
  1 = FAIL
  2 = usage/config error

Notes:
- This is intended to be invoked by QA after every SmartDev change.
- Keep it deterministic and conservative; prefer failing rather than guessing.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]  # quant_proto/
RUNS = ROOT / "runs"

WINDOW_START = "2022-01-01"
WINDOW_END = "2022-06-30"


@dataclass
class CheckResult:
    ok: bool
    msg: str


def _run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    return p.returncode, out


def latest_run_dir(before: set[Path]) -> Path | None:
    if not RUNS.exists():
        return None
    after = {p for p in RUNS.iterdir() if p.is_dir()}
    new = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)
    return new[0] if new else None


def require_files(run_dir: Path, names: list[str]) -> CheckResult:
    missing = [n for n in names if not (run_dir / n).exists()]
    if missing:
        return CheckResult(False, f"Missing artifacts: {missing}")
    return CheckResult(True, "Artifacts present")


def check_long_only_and_cash(run_dir: Path) -> CheckResult:
    # Reconstruct positions and ensure no negative qty; ensure settled_cash never negative.
    fills_path = run_dir / "fills.csv"
    eq_path = run_dir / "equity_curve.csv"

    # equity_curve settled_cash check
    with eq_path.open() as f:
        r = csv.DictReader(f)
        min_settled = None
        for row in r:
            sc = float(row.get("settled_cash", "nan"))
            min_settled = sc if min_settled is None else min(min_settled, sc)
        if min_settled is None:
            return CheckResult(False, "equity_curve.csv is empty")
        if min_settled < -1e-6:
            return CheckResult(False, f"settled_cash went negative: min={min_settled}")

    # position qty check
    pos: dict[str, int] = {}
    with fills_path.open() as f:
        r = csv.DictReader(f)
        for row in r:
            sym = row["symbol"]
            side = row["side"].upper()
            qty = int(float(row["qty"]))
            pos.setdefault(sym, 0)
            if side == "BUY":
                pos[sym] += qty
            elif side == "SELL":
                pos[sym] -= qty
            else:
                return CheckResult(False, f"Unknown fill side: {side}")
            if pos[sym] < 0:
                return CheckResult(False, f"Negative position (short) detected: {sym} qty={pos[sym]}")

    return CheckResult(True, "Long-only and non-negative settled cash")


def check_position_cap(run_dir: Path) -> CheckResult:
    cfg = json.loads((run_dir / "config.json").read_text())
    cap = float(cfg.get("position_cap", 0.2))

    fills = list(csv.DictReader((run_dir / "fills.csv").open()))
    eq = {row["day"]: row for row in csv.DictReader((run_dir / "equity_curve.csv").open())}

    # Track position value using close marks from equity_curve if present; otherwise skip.
    # This is a lightweight check: if equity_curve has per-symbol marks we could do better.
    # For now, enforce a weaker but still useful invariant: any single BUY notional should
    # not exceed cap * equity_on_day (approx) by a tolerance.

    tol = 0.0005  # 5 bps tolerance
    for row in fills:
        if row["side"].upper() != "BUY":
            continue
        day = row["day"]
        nav = float(eq[day]["equity"]) if day in eq and "equity" in eq[day] else None
        if nav is None:
            continue
        notional = float(row["qty"]) * float(row["price"])  # fill notional
        if notional > nav * cap * (1 + tol):
            return CheckResult(False, f"BUY notional exceeds cap: day={day} sym={row['symbol']} notional={notional:.2f} cap*nav={nav*cap:.2f}")

    return CheckResult(True, "No BUY notional cap breaches (approx)")


def main() -> int:
    if not (ROOT / "quant_proto").exists():
        print(f"Bad root: {ROOT}", file=sys.stderr)
        return 2

    before = {p for p in RUNS.iterdir()} if RUNS.exists() else set()

    # Run backtest
    rc, out = _run([sys.executable, "-m", "quant_proto", "backtest", "--start", WINDOW_START, "--end", WINDOW_END])
    if rc != 0:
        print(out)
        return 1

    # Run paper
    rc, out = _run([sys.executable, "-m", "quant_proto", "paper", "--start", WINDOW_START, "--end", WINDOW_END])
    if rc != 0:
        print(out)
        return 1

    run_dir = latest_run_dir(before)
    if not run_dir:
        print("Could not detect new run dir", file=sys.stderr)
        return 1

    print(f"Detected run: {run_dir}")

    checks = [
        require_files(run_dir, ["config.json", "universe_snapshot.json", "orders.csv", "fills.csv", "equity_curve.csv"]),
        check_long_only_and_cash(run_dir),
        check_position_cap(run_dir),
    ]

    failed = [c for c in checks if not c.ok]
    for c in checks:
        print(("PASS" if c.ok else "FAIL") + ": " + c.msg)

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
