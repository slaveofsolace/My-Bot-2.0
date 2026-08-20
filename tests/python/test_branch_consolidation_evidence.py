from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/evidence/system/branch-consolidation.20260820.json"


class BranchConsolidationEvidenceTests(unittest.TestCase):
    def test_superseded_branches_are_reconciled_without_protected_imports(self) -> None:
        document = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(1, document["schema_version"])
        pull_requests = {item["number"]: item for item in document["pull_requests"]}
        self.assertEqual("superseded", pull_requests[7]["classification"])
        self.assertEqual(["HANDOFF.md"], pull_requests[7]["files"])
        self.assertEqual("authoritative-integration", pull_requests[8]["classification"])

        branch = document["branches"][0]
        counts = Counter(item["classification"] for item in branch["files"])
        self.assertEqual(branch["classification_counts"], dict(counts))
        self.assertEqual(29, len(branch["files"]))
        protected = [item for item in branch["files"] if item["classification"] == "protected-excluded"]
        self.assertEqual(["Languages/English.ini"], [item["path"] for item in protected])
        self.assertTrue(branch["counterpart_is_ancestor_of_authoritative_head"])


if __name__ == "__main__":
    unittest.main()
