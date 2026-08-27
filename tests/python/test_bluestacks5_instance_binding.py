from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "COCBot/functions/Android/AndroidBluestacks5.au3").read_text(
    encoding="utf-8-sig"
)
ANDROID_SOURCE = (ROOT / "COCBot/functions/Android/Android.au3").read_text(
    encoding="utf-8-sig"
)


def function_body(name: str) -> str:
    match = re.search(rf"(?ms)^Func {re.escape(name)}\([^\r\n]*\).*?^EndFunc", SOURCE)
    if match is None:
        raise AssertionError(f"missing {name}")
    return match.group(0)


class BlueStacks5InstanceBindingTests(unittest.TestCase):
    def test_vulkan_renderer_uses_the_proven_adb_screencap_mode(self) -> None:
        background = function_body("GetBlueStacks5BackgroundMode")
        self.assertIn('Case "vlcn"', background)
        self.assertIn(
            'SetDebugLog("BlueStacks5 Vulkan render mode uses ADB screencap for Background Mode")',
            background,
        )
        vulkan = background.split('Case "vlcn"', maxsplit=1)[1].split("Case Else", maxsplit=1)[0]
        self.assertIn("Return $g_iAndroidBackgroundModeOpenGL", vulkan)
        self.assertNotIn("$g_iAndroidBackgroundModeDirectX", vulkan)

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

    def test_exact_hung_instance_is_distinguished_without_process_mutation(self) -> None:
        hung = function_body("BlueStacks5ExactInstanceWindowHung")
        for required in (
            "_BlueStacks5ConfiguredAdbOwnerPid()",
            "_WinAPI_EnumWindows(False)",
            "_BlueStacks5ModernWindowMatchesInstance($hWindow, $iAdbOwnerPid)",
            'DllCall("user32.dll", "bool", "IsHungAppWindow", "hwnd", $hFound)',
            "$iFound <> 1",
        ):
            self.assertIn(required, hung)
        for forbidden in ("ProcessClose", "taskkill", "CloseBlueStacks5", "RebootAndroid", "OpenAndroid"):
            self.assertNotIn(forbidden, hung)

        action = (ROOT / "COCBot/MBR GUI Action.au3").read_text(encoding="utf-8-sig")
        gate_match = re.search(
            r"(?ms)^Func _BotOpenHomeRequireExactBlueStacks\([^\r\n]*\).*?^EndFunc",
            action,
        )
        self.assertIsNotNone(gate_match)
        gate = gate_match.group(0)
        self.assertLess(gate.index("BlueStacks5ExactInstanceWindowHung()"), gate.index("WinGetAndroidHandle()"))
        self.assertIn("is not responding; use Recovery", gate)
        self.assertNotIn("ProcessClose", gate)
        ensure_match = re.search(
            r"(?ms)^Func _BotOpenHomeEnsureExactBlueStacks\([^\r\n]*\).*?^EndFunc",
            action,
        )
        self.assertIsNotNone(ensure_match)
        ensure = ensure_match.group(0)
        self.assertIn("_BotOpenHomeRequireExactBlueStacks($sReason)", ensure)
        self.assertIn("LaunchBlueStacks5CoCOnly($sLaunchReason)", ensure)
        self.assertEqual(action.count("_BotOpenHomeEnsureExactBlueStacks($sAttachmentError)"), 10)

    def test_bound_adb_surface_never_enters_synchronous_qt_window_management(self) -> None:
        match = re.search(
            r"(?ms)^Func HideAndroidWindow\([^\r\n]*\).*?^EndFunc",
            ANDROID_SOURCE,
        )
        self.assertIsNotNone(match)
        body = match.group(0)
        guard = (
            '$g_sAndroidEmulator = "BlueStacks5" And '
            "IsArray(GetBlueStacks5ModernAdbSurfacePosition())"
        )
        self.assertIn(guard, body)
        self.assertIn(
            'SetDebugLog("BlueStacks5 modern ADB surface bound; preserving the Qt window state")',
            body,
        )
        self.assertLess(body.index(guard), body.index("ResumeAndroid()"))
        self.assertLess(body.index("Return SetError(0, 0, 1)"), body.index("ResumeAndroid()"))


if __name__ == "__main__":
    unittest.main()
