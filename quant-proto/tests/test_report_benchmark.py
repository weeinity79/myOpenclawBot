from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from quant_proto.report import load_comparison_report


class ReportBenchmarkTests(unittest.TestCase):
    def _mk_run(self, root: Path, days: list[str]) -> Path:
        run_dir = root / "runs" / "2026-03-06-000000"
        run_dir.mkdir(parents=True, exist_ok=True)

        eq = pd.DataFrame(
            {
                "day": days,
                "nav": [100000.0, 100500.0, 100200.0, 101000.0, 101400.0][: len(days)],
                "drawdown": [0.0, 0.0, 0.0029850746, 0.0, 0.0][: len(days)],
            }
        )
        eq.to_csv(run_dir / "equity_curve.csv", index=False)

        fills = pd.DataFrame(
            {
                "day": [days[1], days[2], days[3]],
                "symbol": ["QQQ", "QQQ", "SPY"],
                "side": ["BUY", "SELL", "BUY"],
                "qty": [10, 10, 5],
                "price": [100.0, 101.0, 200.0],
                "notional": [1000.0, 1010.0, 1000.0],
            }
        )
        fills.to_csv(run_dir / "fills.csv", index=False)

        (run_dir / "config.json").write_text(json.dumps({"data_dir": str(root / "data")}))
        return run_dir

    def _mk_benchmark(self, root: Path, rows: list[tuple[str, float]]) -> Path:
        p = root / "data" / "stooq"
        p.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame({"Date": [d for d, _ in rows], "Close": [c for _, c in rows]})
        out = p / "SPY.csv"
        df.to_csv(out, index=False)
        return out

    def test_happy_path_strategy_benchmark_delta(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            days = ["2022-01-03", "2022-01-04", "2022-01-05", "2022-01-06", "2022-01-07"]
            run_dir = self._mk_run(root, days)
            self._mk_benchmark(root, [(d, c) for d, c in zip(days, [100.0, 101.0, 100.5, 102.0, 103.0])])

            comp, _ = load_comparison_report(run_dir=run_dir, benchmark_symbol="SPY")
            self.assertGreater(comp.strategy.total_return, 0)
            self.assertGreater(comp.benchmark.total_return, 0)
            self.assertAlmostEqual(comp.delta.total_return, comp.strategy.total_return - comp.benchmark.total_return, places=10)

    def test_short_sample_degrades_vol_sharpe_to_zero(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            days = ["2022-01-03", "2022-01-04", "2022-01-05", "2022-01-06", "2022-01-07"]
            run_dir = self._mk_run(root, days)
            self._mk_benchmark(root, [(d, c) for d, c in zip(days, [100.0, 99.0, 99.5, 98.0, 99.0])])

            comp, _ = load_comparison_report(run_dir=run_dir, benchmark_symbol="SPY")
            self.assertEqual(comp.strategy.vol, 0.0)
            self.assertEqual(comp.strategy.sharpe, 0.0)
            self.assertEqual(comp.benchmark.vol, 0.0)
            self.assertEqual(comp.benchmark.sharpe, 0.0)

    def test_missing_benchmark_dates_raises_with_range(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            days = ["2022-01-03", "2022-01-04", "2022-01-05", "2022-01-06", "2022-01-07"]
            run_dir = self._mk_run(root, days)
            # Gap: 2022-01-05 missing
            self._mk_benchmark(root, [("2022-01-03", 100.0), ("2022-01-04", 101.0), ("2022-01-06", 102.0), ("2022-01-07", 103.0)])

            with self.assertRaises(RuntimeError) as cm:
                load_comparison_report(run_dir=run_dir, benchmark_symbol="SPY")
            msg = str(cm.exception).lower()
            self.assertIn("benchmark", msg)
            self.assertIn("missing_dates", msg)

    def test_negative_cases_missing_close_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            days = ["2022-01-03", "2022-01-04", "2022-01-05", "2022-01-06", "2022-01-07"]
            run_dir = self._mk_run(root, days)
            stooq = root / "data" / "stooq"
            stooq.mkdir(parents=True, exist_ok=True)

            # missing file
            with self.assertRaises(RuntimeError) as cm_missing:
                load_comparison_report(run_dir=run_dir, benchmark_symbol="SPY")
            self.assertIn("benchmark", str(cm_missing.exception).lower())

            # missing Close
            pd.DataFrame({"Date": days, "Open": [1, 2, 3, 4, 5]}).to_csv(stooq / "SPY.csv", index=False)
            with self.assertRaises(RuntimeError) as cm_close:
                load_comparison_report(run_dir=run_dir, benchmark_symbol="SPY")
            self.assertIn("columns", str(cm_close.exception).lower())

            # empty file
            pd.DataFrame(columns=["Date", "Close"]).to_csv(stooq / "SPY.csv", index=False)
            with self.assertRaises(RuntimeError) as cm_empty:
                load_comparison_report(run_dir=run_dir, benchmark_symbol="SPY")
            self.assertIn("empty", str(cm_empty.exception).lower())


if __name__ == "__main__":
    unittest.main()
