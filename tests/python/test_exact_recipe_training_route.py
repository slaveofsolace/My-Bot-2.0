from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "COCBot/functions/Run/ExactRecipeTrainingRoute.au3"


class ExactRecipeTrainingRouteContractTests(unittest.TestCase):
    def test_route_is_one_action_exact_digest_and_no_fallback(self) -> None:
        source = SOURCE.read_text(encoding="utf-8-sig")
        for required in (
            '$oOutcome.Item("queue_attempts") = 1',
            'String($oAfter.Item("queue_digest")) <> $sRecipeDigest',
            'Int($oAfter.Item("queued_units")) <> Int($oBefore.Item("missing_units"))',
            '$oObservation.Item("boost_active")',
            '$oObservation.Item("gem_surface")',
            '$oObservation.Item("delete_required")',
        ):
            self.assertIn(required, source)
        for forbidden in (
            "TrainSystem(", "BoostSuperTroop(", "QuickTrain(", "Delete(", "Remove(", "GemClick(", "DllCallMyBot", "Sleep("
        ):
            self.assertNotIn(forbidden, source)
        for production in (ROOT / "MyBot.run.au3", ROOT / "COCBot/functions/Run/RunExecution.au3"):
            self.assertNotIn("ExactRecipeTrainingRoute", production.read_text(encoding="utf-8-sig"))

    def test_catalog_and_saved_recipe_fixture_remain_fail_closed(self) -> None:
        catalog = json.loads((ROOT / "config/current-client-capabilities.json").read_text(encoding="utf-8-sig"))
        capability = next(item for item in catalog["capabilities"] if item["id"] == "army.training")
        self.assertEqual("adapter-added", capability["status"])
        self.assertEqual("COCBot/functions/Run/ExactRecipeTrainingRoute.au3", capability["implementation"])
        policy = catalog["runtime_evidence_policy"]["capabilities"]["army.training"]["required_tests"]
        self.assertIn("saved-recipe.digest-confirmed", policy[0]["required_checks"])
        self.assertIn("training.one-queue-attempt", policy[1]["required_checks"])
        self.assertIn("gems.untouched", policy[1]["required_checks"])
        manifest = json.loads((ROOT / "tests/fixtures/current-client/manifest.json").read_text(encoding="utf-8-sig"))
        fixture = next(item for item in manifest["required_fixtures"] if item["id"] == "army.training.saved-recipe")
        self.assertEqual("missing", fixture["status"])


if __name__ == "__main__":
    unittest.main()
