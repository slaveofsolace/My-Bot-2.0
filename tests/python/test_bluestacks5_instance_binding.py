from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "COCBot/functions/Android/AndroidBluestacks5.au3").read_text(
    encoding="utf-8-sig"
)


def function_body(name: str) -> str:
    match = re.search(rf"(?ms)^Func {re.escape(name)}\([^\r\n]*\).*?^EndFunc", SOURCE)
    if match is None:
        raise AssertionError(f"missing {name}")
    return match.group(0)


class BlueStacks5InstanceBindingTests(unittest.TestCase):
    def test_blank_title_requires_exact_instance_adb_listener_owner(self) -> None:
        owner = function_body("_BlueStacks5ConfiguredAdbOwnerPid")
        for required in (
            r'"^127\.0\.0\.1:([0-9]{1,5})$"',
            "_CV_GetExtendedTcpTable()",
            '$aTcp[$i][5] <> "LISTENING"',
            'StringLower(String($aTcp[$i][0])) <> "hd-player.exe"',
            'String($aTcp[$i][1]) <> "localhost (127.0.0.1)"',
            "ProcessExists2($iCandidatePid) <> $iCandidatePid",
            "$iOwnerPid <> $iCandidatePid",
        ):
            self.assertIn(required, owner)

        matcher = function_body("_BlueStacks5ModernWindowMatchesInstance")
        self.assertIn("WinGetProcess($hWindow) <> $iAdbOwnerPid", matcher)
        self.assertIn('"^Qt[0-9]+QWindowIcon$"', matcher)
        self.assertIn('$sTitle = ""', matcher)
        self.assertIn('StringCompare($sTitle, "BlueStacks5-" & $g_sAndroidInstance, 0) = 0', matcher)

    def test_discovery_and_adb_surface_share_the_same_binding(self) -> None:
        discovery = function_body("FindBlueStacks5WindowFallback")
        surface = function_body("GetBlueStacks5ModernAdbSurfacePosition")
        self.assertIn("Local $iAdbOwnerPid = _BlueStacks5ConfiguredAdbOwnerPid()", discovery)
        self.assertIn("_BlueStacks5ModernWindowMatchesInstance($hWindow, $iAdbOwnerPid)", discovery)
        self.assertIn(
            "_BlueStacks5ModernWindowMatchesInstance($hWindow, _BlueStacks5ConfiguredAdbOwnerPid())",
            surface,
        )
        self.assertNotIn('WinGetTitle($hWindow) = ""', surface)


if __name__ == "__main__":
    unittest.main()
