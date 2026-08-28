from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def function_body(text: str, name: str) -> str:
    match = re.search(
        rf"(?ims)^Func\s+{re.escape(name)}\s*\(.*?^EndFunc(?:\s*;[^\r\n]*)?",
        text,
    )
    if not match:
        raise AssertionError(f"missing AutoIt function: {name}")
    return match.group(0)


class CollectorCleanRoomRecognizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.recognizer = source("COCBot/functions/Run/CollectorBubbleRecognizer.au3")
        cls.collect = function_body(source("COCBot/functions/Village/Collect.au3"), "Collect")
        cls.mbr = function_body(source("COCBot/functions/Other/MBRFunc.au3"), "DllCallMyBot")
        cls.main_screen = function_body(
            source("COCBot/functions/Main Screen/checkMainScreen.au3"),
            "_checkMainScreenImage",
        )
        cls.readiness = function_body(
            source("COCBot/functions/Village/BotDetectFirstTime.au3"),
            "BotDetectFirstTime",
        )

    def test_collector_route_uses_only_clean_room_bubble_recognizer(self) -> None:
        self.assertIn("CollectorBubbleRecognize($g_hHBitmap2)", self.collect)
        self.assertNotIn("returnMultipleMatchesOwnVillage", self.collect)
        for token in ("DllCallMyBot", "FindTile", "SearchMultipleTiles", "ShellExecute", ".html"):
            self.assertNotIn(token, self.recognizer)

    def test_full_profile_inherited_wrapper_is_managed_while_bounded_collector_stays_clean_room(self) -> None:
        self.assertIn("Not MBRFuncRecognitionAvailable()", self.mbr)
        self.assertIn("_DllCallMyBot($sFunc", self.mbr)
        self.assertIn("Not MBRFuncManagedLaunchBound()", self.mbr)
        self.assertIn("SuspendAndroid", self.mbr)
        self.assertNotIn("DllCallMyBot", self.collect)
        self.assertNotIn("DllCallMyBot", self.recognizer)

    def test_bounded_home_proof_skips_protected_chat_template(self) -> None:
        self.assertIn("RunExecutionSkipPendingNotifications()", self.main_screen)
        self.assertRegex(
            self.main_screen,
            r"If\s+\$bLocated\s+And\s+Not\s+RunExecutionSkipPendingNotifications\(\)\s+Then\s+\$bLocated\s*=\s*checkChatTabPixel\(\)",
        )

    def test_bounded_profile_attestation_precedes_town_hall_template(self) -> None:
        attestation = self.readiness.index("RunVillageReadinessMarkMainScreenProfileAttested")
        template = self.readiness.index("imglocOwnVillageTownHallIdentity")
        self.assertLess(attestation, template)
        self.assertIn("without protected template recognition", self.readiness)

    def test_classifier_is_bounded_to_the_current_client_frame(self) -> None:
        for token in (
            "$iWidth < 760",
            "$iHeight < 620",
            "To _Min(600, $iHeight - 17) Step 4",
            'Call("RunControlStop" & "Requested")',
            "$aCount[0] >= 50",
            "$aCount[1] >= 120",
            "$aCount[2] >= 100",
            "$aCount[4] >= 80",
        ):
            self.assertIn(token, self.recognizer)


if __name__ == "__main__":
    unittest.main()
