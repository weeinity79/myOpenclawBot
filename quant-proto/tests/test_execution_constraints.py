from __future__ import annotations

import csv
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path

from quant_proto.core.broker import BrokerConfig
from quant_proto.core.sim import SimConfig, run_sim


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


class ExecutionConstraintsTests(unittest.TestCase):
    def _run(self, broker: BrokerConfig, initial_cash: float = 100_000.0) -> Path:
        td = tempfile.mkdtemp(prefix="qp_t14_")
        run_dir = run_sim(
            SimConfig(
                start=date(2022, 1, 3),
                end=date(2022, 3, 31),
                initial_cash=initial_cash,
                data_dir=str(DATA_DIR),
                broker=broker,
            ),
            mode="backtest",
            run_base_dir=Path(td),
        )
        return run_dir

    def test_lot_size_and_turnover_enforced(self) -> None:
        run_dir = self._run(BrokerConfig(lot_size=10, max_daily_turnover=0.03))

        with (run_dir / "fills.csv").open() as f:
            fills = list(csv.DictReader(f))
        for f in fills:
            if f["side"].upper() == "BUY":
                self.assertEqual(int(float(f["qty"])) % 10, 0)

        with (run_dir / "orders.csv").open() as f:
            orders = list(csv.DictReader(f))
        self.assertTrue(any(o["reason"] == "rounded_lot" for o in orders))
        self.assertTrue(any(o["reason"] == "blocked_turnover" for o in orders))

        with (run_dir / "equity_curve.csv").open() as f:
            eq = list(csv.DictReader(f))
        nav_by_day = {r["day"]: float(r["nav"]) for r in eq}
        days = [r["day"] for r in eq]
        prev_nav = {days[i]: float(eq[i - 1]["nav"]) for i in range(1, len(days))}

        buy_notional_by_day: dict[str, float] = {}
        for f in fills:
            if f["side"].upper() == "BUY":
                buy_notional_by_day.setdefault(f["day"], 0.0)
                buy_notional_by_day[f["day"]] += float(f["notional"])

        for d, notional in buy_notional_by_day.items():
            if d in prev_nav and prev_nav[d] > 0:
                self.assertLessEqual(notional / prev_nav[d], 0.03 + 1e-9)

    def test_gap_block_and_min_notional_reasons_traceable(self) -> None:
        run_gap = self._run(BrokerConfig(gap_block_threshold=0.0))
        with (run_gap / "orders.csv").open() as f:
            orders_gap = list(csv.DictReader(f))
        self.assertTrue(any(o["reason"] == "blocked_gap" for o in orders_gap))

        run_min = self._run(BrokerConfig(min_trade_notional=1_000_000.0), initial_cash=50_000.0)
        with (run_min / "orders.csv").open() as f:
            orders_min = list(csv.DictReader(f))
        self.assertTrue(any(o["reason"] == "below_min_notional" for o in orders_min))

    def test_invalid_params_exit_code_2(self) -> None:
        py = str(ROOT / ".venv" / "bin" / "python")
        base = [py, "-m", "quant_proto", "backtest", "--start", "2022-01-03", "--end", "2022-03-31"]

        cases = [
            (["--lot-size", "0"], "lot_size"),
            (["--max-daily-turnover", "-0.1"], "max_daily_turnover"),
            (["--max-daily-turnover", "1.1"], "max_daily_turnover"),
            (["--gap-block-threshold", "-0.1"], "gap_block_threshold"),
        ]
        for extra, key in cases:
            p = subprocess.run(base + extra, cwd=str(ROOT), capture_output=True, text=True)
            self.assertEqual(p.returncode, 2)
            self.assertIn(key, (p.stderr or "").lower())


if __name__ == "__main__":
    unittest.main()
