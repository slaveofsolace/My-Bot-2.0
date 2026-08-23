from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class RunPlannerPreviewTests(unittest.TestCase):
    def test_native_layout_has_no_clipping_or_geometry_findings(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/preview_run_planner.py"),
                "--fail-on-warnings",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual([], report["errors"])
        self.assertEqual([], report["warnings"])

    def test_ci_enforces_the_warning_free_layout(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn(
            "python tools/preview_run_planner.py --fail-on-warnings",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
