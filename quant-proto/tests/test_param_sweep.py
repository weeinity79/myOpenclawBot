from __future__ import annotations

import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv" / "bin" / "python")


class ParamSweepTests(unittest.TestCase):
    def test_happy_path_and_outputs(self) -> None:
        out = Path(tempfile.mkdtemp(prefix="qp_sweep_"))
        cmd = [
            PY,
            "-m",
            "quant_proto.tools.param_sweep",
            "--train-start",
            "2022-01-03",
            "--train-end",
            "2022-03-31",
            "--oos-start",
            "2022-04-01",
            "--oos-end",
            "2022-06-30",
            "--ma-fast-grid",
            "10,20",
            "--ma-slow-grid",
            "60,80,100",
            "--top-k-grid",
            "2,3",
            "--out-dir",
            str(out),
        ]
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, msg=p.stdout + "\n" + p.stderr)

        csv_path = out / "sweep_results.csv"
        json_path = out / "sweep_summary.json"
        self.assertTrue(csv_path.exists())
        self.assertTrue(json_path.exists())

        rows = list(csv.DictReader(csv_path.open()))
        self.assertGreaterEqual(len(rows), 12)
        required_cols = {
            "ma_fast",
            "ma_slow",
            "top_k",
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
        }
        self.assertTrue(required_cols.issubset(set(rows[0].keys())))

    def test_rejected_rows_and_deterministic(self) -> None:
        out1 = Path(tempfile.mkdtemp(prefix="qp_sweep1_"))
        out2 = Path(tempfile.mkdtemp(prefix="qp_sweep2_"))
        base = [
            PY,
            "-m",
            "quant_proto.tools.param_sweep",
            "--train-start",
            "2022-01-03",
            "--train-end",
            "2022-02-28",
            "--oos-start",
            "2022-03-01",
            "--oos-end",
            "2022-04-29",
            "--ma-fast-grid",
            "20,100",
            "--ma-slow-grid",
            "60,100",
            "--top-k-grid",
            "1,20",
        ]

        p1 = subprocess.run(base + ["--out-dir", str(out1)], cwd=str(ROOT), capture_output=True, text=True)
        p2 = subprocess.run(base + ["--out-dir", str(out2)], cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(p1.returncode, 0, msg=p1.stdout + "\n" + p1.stderr)
        self.assertEqual(p2.returncode, 0, msg=p2.stdout + "\n" + p2.stderr)

        rows1 = list(csv.DictReader((out1 / "sweep_results.csv").open()))
        rows2 = list(csv.DictReader((out2 / "sweep_results.csv").open()))
        self.assertEqual(rows1, rows2)

        self.assertTrue(any(r["status"] == "rejected" and r["reject_reason"] for r in rows1))

    def test_invalid_date_ranges(self) -> None:
        p = subprocess.run(
            [
                PY,
                "-m",
                "quant_proto.tools.param_sweep",
                "--train-start",
                "2022-01-03",
                "--train-end",
                "2022-03-31",
                "--oos-start",
                "2022-03-31",
                "--oos-end",
                "2022-06-30",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(p.returncode, 2)
        self.assertIn("overlap", (p.stderr or "").lower())


if __name__ == "__main__":
    unittest.main()
