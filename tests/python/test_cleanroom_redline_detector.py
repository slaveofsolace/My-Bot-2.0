from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DETECTOR = ROOT / "COCBot" / "functions" / "Run" / "CleanRoomRedlineDetector.au3"
IMGLOC = ROOT / "COCBot" / "functions" / "Image Search" / "imglocAuxiliary.au3"
ENTRYPOINT = ROOT / "MyBot.run.au3"
CONTRACT = ROOT / "COCBot" / "functions" / "Run" / "RunExecutionContract.au3"
PLANNER = ROOT / "tools" / "planner_ui.py"
PLANNER_JS = ROOT / "ui" / "planner.js"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def function_body(source: str, name: str) -> str:
    match = re.search(rf"Func\s+{re.escape(name)}\b.*?\n(.*?)\nEndFunc", source, re.S | re.I)
    if not match:
        raise AssertionError(f"missing AutoIt function {name}")
    return match.group(1)


class CleanRoomRedlineDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = read(DETECTOR)

    def test_detector_is_narrow_current_frame_code(self) -> None:
        forbidden = (
            "DllCallMyBot",
            "DllCall(",
            "FindTile",
            "ShellExecute",
            "FileOpen(",
            "FileRead(",
            "FileWrite(",
            "WinActivate(",
            "Click(",
            "AndroidAdb",
            "HD-Player",
            "_CaptureRegion",
            "ForceCaptureRegion",
        )
        for token in forbidden:
            self.assertNotIn(token, self.detector)
        self.assertIn("_GetPixelColor($iX, $iY)", self.detector)
        self.assertIn("$CLEANROOM_REDLINE_MIN_POINTS = 50", self.detector)
        self.assertIn("$CLEANROOM_REDLINE_MAX_POINTS = 512", self.detector)

    def test_detector_fails_closed_before_battle_geometry_is_trusted(self) -> None:
        body = function_body(self.detector, "CleanRoomRedlineDetectCurrentFrame")
        self.assertIn("If $g_hBitmap = 0 Then Return SetError(1, 0, \"\")", body)
        self.assertIn("If $iBottom <= $iTop Or $iRight <= $iLeft Then Return SetError(3, 0, \"\")", body)
        self.assertIn("If $iCount < $iMinPoints Then Return SetError(4, $iCount, \"\")", body)
        self.assertIn("_CleanRoomRedlineNearDiamondEdge", body)
        self.assertIn("_CleanRoomRedlineColorLooksLikeNoDeployRed", body)

    def test_search_redlines_prefers_cleanroom_detector_before_disabled_legacy_path(self) -> None:
        body = function_body(read(IMGLOC), "SearchRedLines")
        cleanroom = body.index('Call("CleanRoomRedlineDetectCurrentFrame", $sCocDiamond)')
        legacy = body.index('DllCallMyBot("SearchRedLines"')
        self.assertLess(cleanroom, legacy)
        self.assertIn("SearchRedLines clean-room detector found", body)
        self.assertIn("falling back to disabled legacy path", body)

    def test_full_entrypoint_includes_detector_without_touching_protected_include(self) -> None:
        source = read(ENTRYPOINT)
        bridge = source.index('#include "COCBot\\functions\\Run\\CleanRoomRecognitionBridge.au3"')
        detector = source.index('#include "COCBot\\functions\\Run\\CleanRoomRedlineDetector.au3"')
        collector = source.index('#include "COCBot\\functions\\Run\\CollectorBubbleRecognizer.au3"')
        self.assertLess(bridge, detector)
        self.assertLess(detector, collector)
        protected = ROOT / "COCBot" / "MBR Functions.au3"
        self.assertNotIn("CleanRoomRedlineDetector", read(protected))

    def test_battle_gate_lifts_only_behind_detector_readiness(self) -> None:
        body = function_body(read(CONTRACT), "RunExecutionContractValidate")
        self.assertIn('Call("CleanRoomRedlineDetectorRuntimeReady")', body)
        self.assertIn("Battle routes require the current-frame clean-room red-line detector", body)
        self.assertNotIn("diagnostic mode cannot bypass this gate", body.lower())

        planner = read(PLANNER)
        planner_js = read(PLANNER_JS)
        self.assertNotIn("inherited ImgLoc runtime rejected exact-current supervised readiness", planner)
        self.assertNotIn("inherited ImgLoc runtime rejected exact-current supervised readiness", planner_js)
        self.assertIn("the acknowledged default inherited battle plan remains blocked", planner)


if __name__ == "__main__":
    unittest.main()
