from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "COCBot/functions/Run/ClanDonationOneRoute.au3"


class ClanDonationOneRouteContractTests(unittest.TestCase):
    def test_route_is_structured_one_unit_and_unwired(self) -> None:
        source = SOURCE.read_text(encoding="utf-8-sig")
        self.assertIn('"structured-icon"', source)
        self.assertIn('"free_text_used"', source)
        self.assertIn('$oOutcome.Item("attempts") = 1', source)
        self.assertIn('_ClanDonationPostProvesOne', source)
        self.assertIn('Int($oBefore.Item("source_available")) <= Int($oBefore.Item("source_reserve"))', source)
        for forbidden in ("DonateCC(", "DllCallMyBot", "OCR", "Click(", "Sleep("):
            self.assertNotIn(forbidden, source.replace("no OCR", ""))
        for production in (ROOT / "MyBot.run.au3", ROOT / "COCBot/functions/Run/RunExecution.au3"):
            self.assertNotIn("ClanDonationOneRoute", production.read_text(encoding="utf-8-sig"))

    def test_catalog_and_fixture_fail_closed_until_live_integration(self) -> None:
        catalog = json.loads((ROOT / "config/current-client-capabilities.json").read_text(encoding="utf-8-sig"))
        capability = next(item for item in catalog["capabilities"] if item["id"] == "village.donations")
        self.assertEqual("adapter-added", capability["status"])
        self.assertEqual("COCBot/functions/Run/ClanDonationOneRoute.au3", capability["implementation"])
        policy = catalog["runtime_evidence_policy"]["capabilities"]["village.donations"]["required_tests"]
        self.assertIn("request-icon.confirmed", policy[0]["required_checks"])
        self.assertIn("free-text.unused", policy[0]["required_checks"])
        self.assertIn("donation.one-unit-confirmed", policy[1]["required_checks"])

        manifest = json.loads((ROOT / "tests/fixtures/current-client/manifest.json").read_text(encoding="utf-8-sig"))
        fixture = next(item for item in manifest["required_fixtures"] if item["id"] == "clan.donation.structured-request")
        self.assertEqual("missing", fixture["status"])
        self.assertEqual(["village.donations"], fixture["capability_ids"])


if __name__ == "__main__":
    unittest.main()
