import json
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import planner_ui  # noqa: E402
from evaluate_support_readiness import evaluate_readiness  # noqa: E402


class PlannerEvidenceReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        planner_ui._EVIDENCE_READINESS_CACHE = None

    def tearDown(self) -> None:
        planner_ui._EVIDENCE_READINESS_CACHE = None

    def test_summary_matches_authoritative_evaluator_and_fixture_manifest(self) -> None:
        summary = planner_ui.evidence_readiness_summary()
        report = evaluate_readiness(root=ROOT)
        manifest = json.loads(planner_ui.FIXTURE_MANIFEST.read_text(encoding="utf-8"))
        entries = manifest["required_fixtures"]
        self.assertTrue(summary["valid"])
        self.assertEqual(summary["capabilities"], report["capabilities"])
        self.assertEqual(summary["historical_ready_for_review"], report["ready"])
        self.assertEqual(summary["exact_current_ready_for_review"], report["current_binary_ready"])
        self.assertEqual(summary["exact_current_evidence_records"], report["exact_current_binary_records"])
        self.assertEqual(summary["fixture_inventory"]["total"], len(entries))
        for status in ("verified", "redacted", "missing"):
            self.assertEqual(
                summary["fixture_inventory"][status],
                sum(entry["status"] == status for entry in entries),
            )

    def test_evaluator_error_zeroes_readiness_and_fails_closed(self) -> None:
        report = {
            "capabilities": 61,
            "ready": 9,
            "current_binary_ready": 7,
            "exact_current_binary_records": 7,
            "errors": ["integrity mismatch"],
        }
        with mock.patch.object(planner_ui, "evaluate_readiness", return_value=report):
            summary = planner_ui.evidence_readiness_summary()
        self.assertFalse(summary["valid"])
        self.assertEqual(summary["historical_ready_for_review"], 0)
        self.assertEqual(summary["exact_current_ready_for_review"], 0)
        self.assertEqual(summary["exact_current_evidence_records"], 0)
        self.assertEqual(summary["error_count"], 1)

    def test_packaged_runtime_without_repository_evaluator_starts_fail_closed(self) -> None:
        with mock.patch.object(planner_ui, "evaluate_readiness", None):
            summary = planner_ui.evidence_readiness_summary()
        self.assertFalse(summary["valid"])
        self.assertEqual(summary["capabilities"], 61)
        self.assertEqual(summary["historical_ready_for_review"], 0)
        self.assertEqual(summary["exact_current_ready_for_review"], 0)
        self.assertEqual(summary["exact_current_evidence_records"], 0)
        self.assertGreaterEqual(summary["error_count"], 1)


if __name__ == "__main__":
    unittest.main()
