"""Offline checks of the published summary contract (no network, standard library only).

runs/latest.json is the public summary that Legal Eye surfaces and release tooling consume. It must
be exactly what build_latest.py derives from the raw run it names; only generated_at may differ.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LATEST = ROOT / "runs" / "latest.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestLatestContract(unittest.TestCase):
    def test_latest_is_rebuilt_exactly_from_its_run(self) -> None:
        latest = load(LATEST)
        run = ROOT / latest["run_file"]
        self.assertTrue(run.is_file(), f"{latest['run_file']} named by runs/latest.json is missing")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "latest.json"
            subprocess.run(
                [sys.executable, str(ROOT / "build_latest.py"), str(run), "--out", str(out)],
                cwd=ROOT, check=True, capture_output=True,
            )
            rebuilt = load(out)
        latest.pop("generated_at", None)
        rebuilt.pop("generated_at", None)
        self.assertEqual(rebuilt, latest)

    def test_rescore_reads_the_latest_run(self) -> None:
        run_file = load(LATEST)["run_file"]
        result = subprocess.run(
            [sys.executable, str(ROOT / "eval_rescore.py"), str(ROOT / run_file)],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
