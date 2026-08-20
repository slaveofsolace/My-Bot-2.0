from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANDROID = (ROOT / "COCBot/functions/Android/Android.au3").read_text(encoding="utf-8-sig")
LDPLAYER = (ROOT / "COCBot/functions/Android/AndroidLDPlayer9.au3").read_text(encoding="utf-8-sig")
MUMU = (ROOT / "COCBot/functions/Android/AndroidMumu.au3").read_text(encoding="utf-8-sig")


class AdditionalEmulatorAdapterTests(unittest.TestCase):
    def test_ldplayer9_exact_instance_adb_and_display_contract(self) -> None:
        self.assertIn('Case "LDPlayer9"', ANDROID)
        self.assertIn("GetLDPlayer9AdbPath()", ANDROID)
        self.assertIn('StringReplace($g_sAndroidInstance, "leidian", "")', LDPLAYER)
        self.assertIn("5554 + (2 * _LDPlayer9InstanceIndex())", LDPLAYER)
        self.assertIn('$g_sAndroidAdbDevice = "emulator-" & $iPort', LDPLAYER)
        self.assertIn('GetVersionNormalized("9.0")', LDPLAYER)
        self.assertIn("StringInStr($sText, '\"width\": ' & $g_iGAME_WIDTH)", LDPLAYER)
        self.assertIn("StringInStr($sText, '\"height\": ' & $g_iGAME_HEIGHT)", LDPLAYER)
        self.assertIn("StringInStr($sText, '\"advancedSettings.resolutionDpi\": 160')", LDPLAYER)
        self.assertIn('modify --index " & $iIndex & " --resolution "', LDPLAYER)
        self.assertIn("$g_iGAME_WIDTH & \",\" & $g_iGAME_HEIGHT & \",160 --root 1\"", LDPLAYER)
        self.assertIn("If $__LDPlayer9_Path = \"\" Or Not FileExists($sProgram) Or Not FileExists($sConsole) Then", LDPLAYER)

    def test_mumu_exact_instance_adb_and_display_contract(self) -> None:
        self.assertIn('Case "MuMu"', ANDROID)
        self.assertIn("GetMumuAdbPath()", ANDROID)
        self.assertIn('StringReplace($g_sAndroidInstance, "MuMuPlayerGlobal-12.0-", "")', MUMU)
        self.assertIn('StringInStr($aLines[$i], "ADB_PORT_EX")', MUMU)
        self.assertIn("hostip=\"([^\"]+)\"\\s+hostport=\"(\\d+)\"", MUMU)
        self.assertIn('$g_sAndroidAdbDevice = $aDevice[0] & ":" & $aDevice[1]', MUMU)
        self.assertIn('GetVersionNormalized("5.0")', MUMU)
        self.assertIn("Local $bWidth = StringRegExp($sText, '\"width\"\\s*:\\s*\"?' & $g_iGAME_WIDTH", MUMU)
        self.assertIn("Local $bHeight = StringRegExp($sText, '\"height\"\\s*:\\s*\"?' & $g_iGAME_HEIGHT", MUMU)
        self.assertIn("Local $bDpi = StringRegExp($sText, '\"dpi\"\\s*:\\s*\"?160\"?'", MUMU)
        self.assertIn("resolution_width.custom", MUMU)
        self.assertIn("resolution_height.custom", MUMU)
        self.assertIn("resolution_dpi.custom", MUMU)
        self.assertIn("If $__Mumu_Path = \"\" Or Not FileExists($sProgram) Or Not FileExists($sManager) Then", MUMU)


if __name__ == "__main__":
    unittest.main()
