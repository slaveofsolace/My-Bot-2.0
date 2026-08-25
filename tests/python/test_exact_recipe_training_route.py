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
        self.assertIn("$EXACT_TRAINING_ROUTE_STRATEGY = \"army.exact-recipe\"", source)
        self.assertIn("ExactRecipeTrainingRouteValidate", source)
        self.assertIn("Exact saved-recipe training requires a safe recipe id", source)
        self.assertIn("Exact saved-recipe training requires a 64-character recipe digest", source)
        self.assertIn("Exact saved-recipe training requires a max queue cap from 1 to 500 units", source)

    def test_route_is_wired_but_terminal_and_no_input_until_recognizer_exists(self) -> None:
        run_bot = (ROOT / "MyBot.run.au3").read_text(encoding="utf-8-sig")
        execution = (ROOT / "COCBot/functions/Run/RunExecution.au3").read_text(encoding="utf-8-sig")
        gui_action = (ROOT / "COCBot/MBR GUI Action.au3").read_text(encoding="utf-8-sig")

        self.assertIn("If ExactRecipeTrainingRouteActive() Then", run_bot)
        route_branch = run_bot[
            run_bot.index("If ExactRecipeTrainingRouteActive() Then") :
            run_bot.index("EndIf", run_bot.index("If ExactRecipeTrainingRouteActive() Then"))
        ]
        self.assertIn("RunExecutionComplete(\"army-exact-recipe-no-loop-dispatch\")", route_branch)
        self.assertIn("Return", route_branch)
        for forbidden in ("TrainSystem", "QuickTrain", "DonateCC", "AttackMain", "InitiateSwitchAcc"):
            self.assertNotIn(forbidden, route_branch)

        self.assertIn("Func ExactRecipeTrainingRouteActive()", execution)
        self.assertIn("ExactRecipeTrainingRouteAccountMatches($oIntent, $sActiveProfile)", execution)
        self.assertIn("If ExactRecipeTrainingRouteSelected($oPreparedIntent) Then Return FuncReturn(_BotStartRunOneShot(6, $sStartError))", gui_action)
        self.assertIn("ExactRecipeTrainingRouteRunAdapter($sRecipeId, $sRecipeDigest, $iMaxQueueUnits", gui_action)
        self.assertIn("Func _ExactTrainingLiveDetect($sPhase)", gui_action)
        self.assertIn("Return ExactRecipeTrainingObservationCreate($EXACT_TRAINING_STATE_UNAVAILABLE)", gui_action)
        self.assertIn("Func _ExactTrainingLiveIssueQueue($iX, $iY)", gui_action)
        self.assertIn("Return SetError(1, 0, False)", gui_action)
        self.assertIn("Exact saved-recipe training unavailable; no queue input was issued", gui_action)

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
