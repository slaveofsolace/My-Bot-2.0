import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LANGUAGE_SOURCE = ROOT / "COCBot" / "functions" / "Other" / "TestLanguage.au3"
COORDINATE_SOURCE = ROOT / "COCBot" / "functions" / "Config" / "ScreenCoordinates.au3"


def function_body(source: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^Func\s+{re.escape(name)}\b.*?^EndFunc(?:\s*;[^\r\n]*)?$",
        source,
    )
    if not match:
        raise AssertionError(f"missing AutoIt function: {name}")
    return match.group(0)


class CurrentClientLanguageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = LANGUAGE_SOURCE.read_text(encoding="utf-8-sig")
        cls.coordinates = COORDINATE_SOURCE.read_text(encoding="utf-8-sig")

    def test_legacy_ocr_remains_first_and_failure_stops(self) -> None:
        body = function_body(self.source, "TestLanguage")
        self.assertLess(body.index("getOcrLanguage("), body.index("ChangeLanguage()"))
        self.assertIn("ElseIf Not ChangeLanguage() Then", body)
        self.assertIn("btnStop()", body)

    def test_settings_english_proof_precedes_any_language_change(self) -> None:
        body = function_body(self.source, "ChangeLanguage")
        self.assertLess(
            body.index("_IsSettingsLanguageEnglish(False)"),
            body.index("Click($aButtonLanguage[0]"),
        )
        self.assertIn('SetLog("Settings explicitly reports English: Correct."', body)
        self.assertIn('Click(786, 79 + $g_iMidOffsetY', body)
        self.assertIn("Return IsMainPage()", body)

    def test_current_client_signature_is_word_specific_and_capture_bounded(self) -> None:
        body = function_body(self.source, "_IsSettingsLanguageEnglish")
        self.assertEqual(body.count("_CaptureRegion()"), 1)
        self.assertGreaterEqual(body.count("_GetPixelColor("), 9)
        self.assertIn("$bLanguageButton", body)
        self.assertIn("$bEnglishLight", body)
        self.assertIn("$bEnglishOutline", body)
        self.assertIn("Return $bEnglishLight And $bEnglishOutline", body)
        self.assertNotIn("Click(", body)

    def test_current_language_controls_use_mapped_860x732_coordinates(self) -> None:
        self.assertIn(
            "Global $aButtonLanguage[2] = [425, 372 + $g_iMidOffsetY]",
            self.coordinates,
        )
        self.assertIn(
            "Global $aButtonLanguageCheck[4] = [360, 372 + $g_iMidOffsetY, 0xA9D556, 30]",
            self.coordinates,
        )
        self.assertIn(
            "Global $aEnglishLanguage[2] = [160, 147 + $g_iMidOffsetY]",
            self.coordinates,
        )
        self.assertNotIn("ClickDrag(", function_body(self.source, "ChangeLanguage"))


if __name__ == "__main__":
    unittest.main()
