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
    risk = cfg.get("risk") or {}
    cap = float(risk.get("position_cap", 0.20))

    fills = list(csv.DictReader((run_dir / "fills.csv").open()))
    eq_rows = list(csv.DictReader((run_dir / "equity_curve.csv").open()))
    if not eq_rows:
        return CheckResult(False, "equity_curve.csv is empty")

    # The simulator generates orders after the close of day t and executes them
    # at the open of day t+1. Sizing uses nav(t) and exposure_factor(t). To
    # match simulator logic deterministically, validate BUY fills on day t+1
    # against cap * nav(t) * exposure_factor(t).
    day_to_idx = {row["day"]: i for i, row in enumerate(eq_rows)}

    pos_qty: dict[str, int] = {}
    eps = 1e-12

    # Fills are written in execution order; enforce invariant sequentially.
    for row in fills:
        side = row["side"].upper()
        sym = row["symbol"]
        qty = int(float(row["qty"]))
        day = row["day"]
        price = float(row["price"])

        pos_qty.setdefault(sym, 0)

        if side == "SELL":
            pos_qty[sym] -= qty
            continue

        if side != "BUY":
            return CheckResult(False, f"Unknown fill side: {side}")

        # Find previous trading day's nav/exposure.
        if day not in day_to_idx:
            pos_qty[sym] += qty
            continue
        i = day_to_idx[day]
        if i <= 0:
            pos_qty[sym] += qty
            continue
        prev = eq_rows[i - 1]
        nav_prev = float(prev["nav"])
        expo_prev = float(prev.get("exposure_factor", "1.0"))

        max_notional = nav_prev * cap * expo_prev

        pos_qty[sym] += qty
        pos_notional_at_fill = pos_qty[sym] * price

        if pos_notional_at_fill > max_notional + eps:
            return CheckResult(
                False,
                (
                    f"Position cap breach after BUY fill: day={day} sym={sym} "
                    f"pos_qty={pos_qty[sym]} px={price:.6f} pos_notional={pos_notional_at_fill:.2f} "
                    f"max_notional={max_notional:.2f} (cap={cap:.3f}, nav_prev={nav_prev:.2f}, expo_prev={expo_prev:.3f})"
                ),
            )

    return CheckResult(True, "No position-cap breaches (strict, execution-price checked)")


def check_per_trade_risk(run_dir: Path) -> CheckResult:
    """Verify T1.2: each BUY fill's stop-risk <= per_trade_risk * NAV(prev day).

    Sizing code uses risk_budget = nav(t) * per_trade_risk, where t is the
    signal day (prior close) and the order executes on day t+1.
    """
    cfg = json.loads((run_dir / "config.json").read_text())
    risk = cfg.get("risk") or {}
    per_trade_risk = float(risk.get("per_trade_risk", 0.005))

    fills = list(csv.DictReader((run_dir / "fills.csv").open()))
    eq_rows = list(csv.DictReader((run_dir / "equity_curve.csv").open()))
    if not eq_rows:
        return CheckResult(False, "equity_curve.csv is empty")

    day_to_idx = {row["day"]: i for i, row in enumerate(eq_rows)}

    eps = 1e-9

    for row in fills:
        side = row["side"].upper()
        if side != "BUY":
            continue

        day = row["day"]
        qty = int(float(row["qty"]))
        stop_dist = float(row.get("stop_distance", "0") or 0.0)
        sym = row["symbol"]

        if day not in day_to_idx:
            continue
        i = day_to_idx[day]
        if i <= 0:
            continue

        nav_prev = float(eq_rows[i - 1]["nav"])
        risk_budget = nav_prev * per_trade_risk
        worst_loss = qty * stop_dist

        if stop_dist <= 0:
            return CheckResult(False, f"Missing/invalid stop_distance on BUY fill: day={day} sym={sym} qty={qty} stop_distance={stop_dist}")

        if worst_loss > risk_budget + eps:
            return CheckResult(
                False,
                (
                    f"Per-trade risk breach: day={day} sym={sym} qty={qty} stop_dist={stop_dist:.6f} "
                    f"worst_loss={worst_loss:.2f} risk_budget={risk_budget:.2f} (per_trade_risk={per_trade_risk:.4f}, nav_prev={nav_prev:.2f})"
                ),
            )

    return CheckResult(True, "No per-trade risk breaches (strict, qty * stop_dist <= per_trade_risk * nav_prev)")


def check_sizing_audit_present(run_dir: Path) -> CheckResult:
    p = run_dir / "sizing_audit.csv"
    if not p.exists():
        return CheckResult(False, "Missing sizing_audit.csv")
    # Sanity: non-empty
    with p.open() as f:
        r = csv.DictReader(f)
        for _ in r:
            return CheckResult(True, "Sizing audit present")
    return CheckResult(False, "sizing_audit.csv is empty")


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
        require_files(run_dir, ["config.json", "universe_snapshot.json", "orders.csv", "fills.csv", "equity_curve.csv", "sizing_audit.csv"]),
        check_long_only_and_cash(run_dir),
        check_position_cap(run_dir),
        check_sizing_audit_present(run_dir),
        check_per_trade_risk(run_dir),
    ]

    failed = [c for c in checks if not c.ok]
    for c in checks:
        print(("PASS" if c.ok else "FAIL") + ": " + c.msg)

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
