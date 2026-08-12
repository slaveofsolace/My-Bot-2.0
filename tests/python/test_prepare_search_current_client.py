import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "COCBot" / "functions" / "Search" / "PrepareSearch.au3"


def function_body(source: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^Func\s+{re.escape(name)}\b.*?^EndFunc(?:\s*;[^\r\n]*)?$",
        source,
    )
    if not match:
        raise AssertionError(f"missing AutoIt function: {name}")
    return match.group(0)


class CurrentClientPrepareSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8-sig")

    def test_current_panel_proof_precedes_legacy_close_button_gate(self) -> None:
        prepare = function_body(self.source, "PrepareSearch")
        self.assertLess(
            prepare.index("_IsCurrentMultiplayerPanelOpen(True)"),
            prepare.index('IsWindowOpen($g_sImgGeneralCloseButton'),
        )
        self.assertIn('SetLog("Attack Window did not open!"', prepare)

    def test_current_panel_proof_is_observation_only_and_specific(self) -> None:
        proof = function_body(self.source, "_IsCurrentMultiplayerPanelOpen")
        self.assertEqual(proof.count("_CaptureRegion()"), 1)
        self.assertGreaterEqual(proof.count("_GetPixelColor("), 7)
        self.assertIn("$bButton", proof)
        self.assertIn("$bFindMatchLabel", proof)
        self.assertIn("Return $bFindMatchLabel", proof)
        self.assertNotIn("Click", proof)

    def test_exact_current_find_match_fallback_is_proof_gated(self) -> None:
        prepare = function_body(self.source, "PrepareSearch")
        fallback = prepare[prepare.index("Local $bCurrentClientMatchStarted") :]
        ordered = (
            "If _IsCurrentMultiplayerPanelOpen(True) Then",
            "Local $aCurrentFindMatch[2]",
            "PureClickP($aCurrentFindMatch",
            "_ClickCurrentArmyConfirmationIfPresent()",
            "$bCurrentClientMatchStarted = True",
            "If Not $bCurrentClientMatchStarted Then",
        )
        offsets = [fallback.index(fragment) for fragment in ordered]
        self.assertEqual(offsets, sorted(offsets))
        self.assertEqual(fallback.count("PureClickP($aCurrentFindMatch"), 1)
        self.assertNotIn("\n\t\t\t\tClickP($aCurrentFindMatch", fallback)
        self.assertIn("Current Multiplayer Battle panel: clicked Find a Match", fallback)

    def test_current_army_confirmation_is_bounded_proof_gated_and_exact(self) -> None:
        click = function_body(self.source, "_ClickCurrentArmyConfirmationIfPresent")
        proof = function_body(self.source, "_IsCurrentArmyConfirmationOpen")
        self.assertIn("For $iAttempt = 1 To 8", click)
        self.assertIn("If _IsCurrentArmyConfirmationOpen(True) Then", click)
        self.assertIn("Random(685, 790, 1)", click)
        self.assertIn("Random(500 + $g_iMidOffsetY, 515 + $g_iMidOffsetY, 1)", click)
        self.assertIn("Current My Army confirmation: clicked Attack", click)
        self.assertEqual(click.count("PureClickP($aCurrentArmyAttack"), 1)
        self.assertNotIn("\n\t\t\tClickP($aCurrentArmyAttack", click)
        self.assertLess(click.index("_IsCurrentArmyConfirmationOpen(True)"), click.index("PureClickP("))

        self.assertEqual(proof.count("_CaptureRegion()"), 1)
        self.assertEqual(proof.count("_GetPixelColor("), 4)
        self.assertIn("$bHighlight", proof)
        self.assertIn("$bBody", proof)
        self.assertNotIn("Click", proof)


if __name__ == "__main__":
    unittest.main()
