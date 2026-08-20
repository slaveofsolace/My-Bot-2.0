from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "COCBot/functions/Run/HomeUpgradeOneRoute.au3"


class HomeUpgradeOneRouteContractTests(unittest.TestCase):
    def test_route_is_cost_reserve_builder_and_post_state_bounded(self) -> None:
        source = SOURCE.read_text(encoding="utf-8-sig")
        for required in (
            'Int($oCandidate.Item("cost")) > Int($iConfiguredCostCap)',
            'Int($oCandidate.Item("available")) - Int($oCandidate.Item("cost")) < Int($oCandidate.Item("reserve"))',
            '$oOutcome.Item("confirm_attempts") = 1',
            '_HomeUpgradeSameOffer',
            '_HomeUpgradePostProvesStart',
            'Passive no-gem guard blocked the upgrade confirmation',
        ):
            self.assertIn(required, source)
        for forbidden in ("AutoUpgrade(", "UpgradeBuilding(", "UpgradeWall(", "GemClick(", "DllCallMyBot", "Sleep("):
            self.assertNotIn(forbidden, source)
        for production in (ROOT / "MyBot.run.au3", ROOT / "COCBot/functions/Run/RunExecution.au3"):
            self.assertNotIn("HomeUpgradeOneRoute", production.read_text(encoding="utf-8-sig"))

    def test_catalog_stays_unavailable_until_specific_fixture_and_live_callbacks(self) -> None:
        catalog = json.loads((ROOT / "config/current-client-capabilities.json").read_text(encoding="utf-8-sig"))
        capability = next(item for item in catalog["capabilities"] if item["id"] == "village.upgrades-home")
        self.assertEqual("adapter-added", capability["status"])
        self.assertEqual("COCBot/functions/Run/HomeUpgradeOneRoute.au3", capability["implementation"])
        policy = catalog["runtime_evidence_policy"]["capabilities"]["village.upgrades-home"]["required_tests"]
        self.assertIn("upgrade-cost.confirmed", policy[0]["required_checks"])
        self.assertIn("upgrade.one-confirmation", policy[1]["required_checks"])
        self.assertIn("gems.untouched", policy[1]["required_checks"])


if __name__ == "__main__":
    unittest.main()
