from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv" / "bin" / "python")


class DailyPipelineTests(unittest.TestCase):
    def test_happy_path(self) -> None:
        wd = Path(tempfile.mkdtemp(prefix="qp_pipe_"))
        p = subprocess.run(
            [
                PY,
                "-m",
                "quant_proto.tools.daily_pipeline",
                "--start",
                "2022-01-03",
                "--end",
                "2022-03-31",
                "--run-base-dir",
                str(wd),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(p.returncode, 0, msg=p.stdout + "\n" + p.stderr)
        self.assertIn("Run dir:", p.stdout)
        self.assertIn("Latest order day:", p.stdout)

    def test_no_orders_edge_case(self) -> None:
        wd = Path(tempfile.mkdtemp(prefix="qp_pipe_no_"))
        p = subprocess.run(
            [
                PY,
                "-m",
                "quant_proto.tools.daily_pipeline",
                "--start",
                "2022-01-03",
                "--end",
                "2022-01-05",
                "--run-base-dir",
                str(wd),
                "--initial-cash",
                "50000",
                "--min-trade-notional",
                "1000000000",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(p.returncode, 0, msg=p.stdout + "\n" + p.stderr)
        self.assertIn("No orders.", p.stdout)

    def test_invalid_date_param(self) -> None:
        p = subprocess.run(
            [
                PY,
                "-m",
                "quant_proto.tools.daily_pipeline",
                "--start",
                "2022-13-01",
                "--end",
                "2022-03-31",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(p.returncode, 2)
        self.assertIn("[PARAM_ERROR]", (p.stderr or "") + (p.stdout or ""))

    def test_unwritable_run_dir(self) -> None:
        p = subprocess.run(
            [
                PY,
                "-m",
                "quant_proto.tools.daily_pipeline",
                "--run-base-dir",
                "/proc/forbidden-openclaw",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("stage=paper_run", (p.stdout or "") + (p.stderr or ""))


if __name__ == "__main__":
    unittest.main()
