import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / "COCBot" / "functions" / "Attack" / "ReturnHome.au3"
IS_PAGE_SOURCE = ROOT / "COCBot" / "functions" / "Other" / "IsPage.au3"


class CurrentTreasureHuntContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8", errors="replace")
        cls.is_page_source = IS_PAGE_SOURCE.read_text(encoding="utf-8", errors="replace")

    def test_claim_reward_is_distinguished_and_clicked_before_chest_flow(self):
        helper = re.search(r"Func IsClaimRewardBattlePage\(\)(.*?)EndFunc", self.is_page_source, re.S)
        self.assertIsNotNone(helper)
        self.assertIn("IsPageLoop($aRewardButton, 1)", helper.group(1))
        self.assertIn("Return True", helper.group(1))

        return_home = re.search(r"Func ReturnHome\(.*?\)(.*?)EndFunc", self.source, re.S)
        self.assertIsNotNone(return_home)
        body = return_home.group(1)
        result_loop = body.index('SetDebugLog("Wait for End Fight Scene to appear #"')
        claim = body.index("If IsClaimRewardBattlePage() Then", result_loop)
        click = body.index("ClickP($aRewardButton", claim)
        special = body.index('SetDebugLog("Wait for Special windows to appear")', click)
        self.assertLess(result_loop, claim)
        self.assertLess(claim, click)
        self.assertLess(click, special)

    def test_current_chest_is_proved_before_input(self):
        helper = re.search(
            r"Func IsCurrentTreasureHuntTapScreen\(\)(.*?)EndFunc",
            self.source,
            re.S,
        )
        self.assertIsNotNone(helper)
        body = helper.group(1)
        self.assertIn("ForceCaptureRegion()", body)
        self.assertLess(body.index("ForceCaptureRegion()"), body.index("_CaptureRegion()"))
        self.assertEqual(body.count("_GetPixelColor("), 3)
        self.assertIn("Return $bLeftFrame And $bPedestal And $bWoodBelow", body)
        self.assertNotIn("Click(", body)
        self.assertNotIn("PureClick(", body)

    def test_current_chest_uses_exact_bounded_taps(self):
        treasure = re.search(r"Func TreasureHunt\(.*?\)(.*?)EndFunc", self.source, re.S)
        self.assertIsNotNone(treasure)
        body = treasure.group(1)
        proof = body.index("If IsCurrentTreasureHuntTapScreen() Then")
        loop = body.index("For $i = 1 To 3", proof)
        stop = body.index("If Not $g_bRunState Then Return False", loop)
        click = body.index("PureClick(430, 365", loop)
        done = body.index("Return True", click)
        legacy = body.index('SetLog("Opening Chest"', done)
        self.assertLess(proof, loop)
        self.assertLess(loop, stop)
        self.assertLess(stop, click)
        self.assertLess(click, done)
        self.assertLess(done, legacy)
        self.assertNotRegex(body[proof:done], r"(?m)^\s*Click\(430, 365")

    def test_current_reward_card_uses_fixed_proved_continue_button(self):
        treasure = re.search(r"Func TreasureHunt\(.*?\)(.*?)EndFunc", self.source, re.S)
        self.assertIsNotNone(treasure)
        body = treasure.group(1)
        current = body.index("If IsCurrentTreasureHuntContinueScreen() Then")
        legacy = body.index("If $counter > 0 Then", current)
        self.assertLess(current, legacy)
        self.assertIn("PureClick(445, 545", body[current:legacy])

        helper = re.search(r"Func IsCurrentTreasureHuntContinueScreen\(\)(.*?)EndFunc", self.source, re.S)
        self.assertIsNotNone(helper)
        proof = helper.group(1)
        self.assertIn("ForceCaptureRegion()", proof)
        self.assertIn("$bGreenEdge And $bBlackText And $bGreenFace", proof)
        self.assertNotIn("$g_iMidOffsetY", proof)

    def test_current_star_bonus_is_proved_and_closed_before_legacy_lookup(self):
        return_home = re.search(r"Func ReturnHome\(.*?\)(.*?)EndFunc", self.source, re.S)
        self.assertIsNotNone(return_home)
        body = return_home.group(1)
        current = body.index("If CurrentStarBonusReceived() Then")
        legacy = body.index("If StarBonus() Then", current)
        self.assertLess(current, legacy)

        helper = re.search(r"Func CurrentStarBonusReceived\(\)(.*?)EndFunc", self.source, re.S)
        self.assertIsNotNone(helper)
        proof = helper.group(1)
        self.assertIn("ForceCaptureRegion()", proof)
        self.assertEqual(proof.count("_GetPixelColor("), 4)
        self.assertLess(proof.index("If Not ($bPurpleTop"), proof.index("PureClick(435, 568"))
        self.assertNotIn("$g_iMidOffsetY", proof)


if __name__ == "__main__":
    unittest.main()
