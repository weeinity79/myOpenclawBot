from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from quant_proto.core.data_quality import DataQualityConfig, validate_data
from quant_proto.core.sim import SimConfig, run_sim


class DataQualityTests(unittest.TestCase):
    def _ok_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "Date": pd.to_datetime(["2022-01-03", "2022-01-04", "2022-01-05"]),
                "Open": [100, 101, 102],
                "High": [101, 102, 103],
                "Low": [99, 100, 101],
                "Close": [100.5, 101.5, 102.5],
                "Volume": [1000, 1200, 1100],
            }
        )

    def test_happy_path_pass(self) -> None:
        rep = validate_data({"SPY": self._ok_df()}, start=date(2022, 1, 3), end=date(2022, 1, 5), cfg=DataQualityConfig())
        self.assertTrue(rep.passed)
        self.assertEqual(len(rep.errors), 0)

    def test_negative_cases_detected(self) -> None:
        df = self._ok_df().copy()
        df.loc[1, "High"] = 90  # high < max(open, close)
        df.loc[2, "Low"] = 200  # low > min(open, close)
        df.loc[0, "Open"] = -1  # non-positive price
        rep = validate_data({"SPY": df}, start=date(2022, 1, 3), end=date(2022, 1, 5), cfg=DataQualityConfig())
        self.assertFalse(rep.passed)
        rules = {e["rule"] for e in rep.errors}
        self.assertIn("high_lt_max_open_close", rules)
        self.assertIn("low_gt_min_open_close", rules)
        self.assertIn("non_positive_price", rules)

    def test_duplicate_and_non_monotonic(self) -> None:
        df = self._ok_df().copy()
        df = df.iloc[[1, 0, 2]].reset_index(drop=True)  # non-monotonic
        df.loc[2, "Date"] = df.loc[1, "Date"]  # duplicate
        rep = validate_data({"SPY": df}, start=date(2022, 1, 3), end=date(2022, 1, 5), cfg=DataQualityConfig())
        self.assertFalse(rep.passed)
        rules = {e["rule"] for e in rep.errors}
        self.assertIn("date_not_monotonic", rules)
        self.assertIn("date_duplicated", rules)

    def test_run_sim_fail_fast_and_report(self) -> None:
        td = Path(tempfile.mkdtemp(prefix="qp_dq_"))
        data_dir = td / "data" / "stooq"
        data_dir.mkdir(parents=True, exist_ok=True)

        # Missing required column Volume + malformed prices
        dates = pd.date_range("2021-08-01", periods=120, freq="B")
        bad = pd.DataFrame(
            {
                "Date": dates.strftime("%Y-%m-%d"),
                "Open": ["100.0"] * 120,
                "High": [101.0] * 120,
                "Low": [99.0] * 120,
                "Close": [100.5] * 120,
            }
        )
        bad.loc[1, "Open"] = "x"
        bad.to_csv(data_dir / "SPY.csv", index=False)

        cfg = SimConfig(
            start=date(2022, 1, 3),
            end=date(2022, 1, 5),
            universe=("SPY",),
            data_dir=str(td / "data"),
        )

        with self.assertRaises(ValueError) as ctx:
            run_sim(cfg=cfg, mode="backtest", run_base_dir=td / "runs")
        self.assertIn("[DATA_ERROR]", str(ctx.exception))

        # report should still be written in latest run dir
        runs = sorted((td / "runs").iterdir())
        self.assertTrue(runs)
        report_path = runs[-1] / "data_quality_report.json"
        self.assertTrue(report_path.exists())
        rep = json.loads(report_path.read_text())
        self.assertFalse(rep["passed"])
        self.assertTrue(len(rep["errors"]) > 0)


if __name__ == "__main__":
    unittest.main()
