from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
TRAIN_SYSTEM = ROOT / "COCBot/functions/CreateArmy/TrainSystem.au3"
OPEN_OVERVIEW = ROOT / "COCBot/functions/CreateArmy/openArmyOverview.au3"
READINESS = ROOT / "COCBot/functions/CreateArmy/PassiveCurrentArmyReadiness.au3"


def _function_body(source: str, name: str) -> str:
    match = re.search(
        rf"(?ims)^Func\s+{re.escape(name)}\b.*?^EndFunc\b.*?$", source
    )
    assert match, f"missing AutoIt function {name}"
    return match.group(0)


class PassiveCurrentArmyReadinessContract(unittest.TestCase):
    def test_passive_branch_uses_dedicated_observer_before_training_paths(self):
        source = TRAIN_SYSTEM.read_text(encoding="utf-8")
        train_system = _function_body(source, "TrainSystem")
        passive_call = train_system.index("CheckPassiveCurrentArmyReady()")
        first_training_call = train_system.index("BoostSuperTroop()")

        self.assertLess(passive_call, first_training_call)
        self.assertNotIn("CheckIfArmyIsReady(True, False)", train_system)

    def test_passive_observer_has_no_legacy_locator_mutator_or_profile_fallback(self):
        source = TRAIN_SYSTEM.read_text(encoding="utf-8")
        observer = _function_body(source, "CheckPassiveCurrentArmyReady")
        forbidden = (
            "CheckArmyCamp(",
            "CheckIfArmyIsReady(",
            "getArmyTroopCapacity(",
            "CheckHeroOrder(",
            "HeroHallValuesCheck(",
            "ImgLocate",
            "ZoomOut(",
            "SearchZoomOut(",
            "GetVillageSize(",
            "RemoveExtraTroops(",
            "QuickTrain(",
            "TrainCustomArmy(",
            "TrainSiege(",
            "IniWrite(",
            "$g_iTotalCampSpace",
            "$g_iTotalCampForcedValue",
        )

        for token in forbidden:
            self.assertNotIn(token, observer, f"passive observer contains forbidden path: {token}")

        self.assertIn('OpenArmyOverview(False, "CheckPassiveCurrentArmyReady()", False)', observer)
        self.assertIn("getArmyCampCap($aArmyCampSize[0], $aArmyCampSize[1], True)", observer)
        self.assertIn("PassiveCurrentArmyCapacityProof(", observer)
        self.assertLess(
            observer.index("$g_bIsFullArmywithHeroesAndSpells = False"),
            observer.index("$g_bIsFullArmywithHeroesAndSpells = True"),
        )

    def test_army_overview_can_skip_only_hero_order_inspection(self):
        source = OPEN_OVERVIEW.read_text(encoding="utf-8")
        overview = _function_body(source, "OpenArmyOverview")

        self.assertIn("$bCheckHeroOrder = True", overview)
        self.assertIn("ElseIf $bCheckHeroOrder Then", overview)
        self.assertIn("CheckHeroOrder()", overview)
        self.assertIn(
            "If Not WaitforPixel(23, 505 + $g_iBottomOffsetY, 53, 507 + $g_iBottomOffsetY",
            overview,
        )
        missing_button = overview.index("Army button was not detected")
        click = overview.index("ClickP($aArmyTrainButton, 1, 120")
        wait_for_window = overview.index("_Sleep($DELAYRUNBOT6)")
        self.assertLess(missing_button, click)
        self.assertLess(click, wait_for_window)

    def test_capacity_contract_requires_two_matching_fresh_full_reads(self):
        source = READINESS.read_text(encoding="utf-8")
        proof = _function_body(source, "PassiveCurrentArmyCapacityProof")
        ready = _function_body(source, "PassiveCurrentArmyCapacityReady")

        self.assertEqual(proof.count("PassiveCurrentArmyCapacityParse("), 2)
        self.assertIn("$iFirstCurrent <> $iCurrent Or $iFirstTotal <> $iTotal", proof)
        self.assertIn("$iCurrent <= 0 Or $iCurrent < $iTotal", ready)
        self.assertIn("Mod($iTotal, 5) <> 0", ready)


if __name__ == "__main__":
    unittest.main()
