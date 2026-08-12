import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OBSTACLES = (ROOT / "COCBot" / "functions" / "Main Screen" / "checkObstacles.au3").read_text(
    encoding="utf-8-sig"
)


class CompletedBattleRecoveryTests(unittest.TestCase):
    def test_current_return_home_template_is_packaged(self):
        template = ROOT / "imgxml" / "imglocbuttons" / "attackwindow" / "ReturnHome_0_96.xml"
        self.assertTrue(template.is_file())
        self.assertGreater(template.stat().st_size, 0)

    def test_main_screen_recovery_handles_completed_battle_without_old_chrome_gate(self):
        detect = 'findButton("ReturnHome", Default, 1, True, False, False)'
        click = 'ClickP($aCompletedBattleReturn, 1, 120, "#0138")'
        old_gate = "If _CheckPixel($aNoCloudsAttack, $g_bCapturePixel) Then"
        self.assertIn(detect, OBSTACLES)
        self.assertIn(click, OBSTACLES)
        self.assertLess(OBSTACLES.index(detect), OBSTACLES.index(click))
        self.assertLess(OBSTACLES.index(click), OBSTACLES.index(old_gate))

    def test_recovery_requires_an_exact_image_match_and_waits_before_retrying(self):
        start = OBSTACLES.index('Local $aCompletedBattleReturn = findButton("ReturnHome"')
        end = OBSTACLES.index("If _CheckPixel($aNoCloudsAttack", start)
        body = OBSTACLES[start:end]
        self.assertIn("IsArray($aCompletedBattleReturn)", body)
        self.assertIn("UBound($aCompletedBattleReturn) >= 2", body)
        self.assertIn("$DELAYCHECKOBSTACLES2", body)
        self.assertNotIn("PureClick(", body)


if __name__ == "__main__":
    unittest.main()
