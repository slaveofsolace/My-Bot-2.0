from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def autoit_function(text: str, name: str) -> str:
    match = re.search(rf"(?ims)^Func\s+{re.escape(name)}\s*\([^\r\n]*\).*?^EndFunc\b", text)
    if not match:
        raise AssertionError(f"AutoIt function not found: {name}")
    return match.group(0)


class AndroidDisplayMappingTest(unittest.TestCase):
    def test_modern_adb_background_start_does_not_require_foreground_focus(self) -> None:
        action = autoit_function(source("COCBot/MBR GUI Action.au3"), "BotStart")
        self.assertIn(
            "$bFocusIndependentControl = $g_bAndroidBackgroundLaunched Or "
            "IsArray(GetBlueStacks5ModernAdbSurfacePosition())",
            action,
        )
        self.assertIn("If Not $bFocusIndependentControl And $g_bNoFocusTampering", action)
        self.assertIn("($bFocusIndependentControl Or $hWndActive = $g_hAndroidWindow)", action)
        self.assertLess(
            action.index("$bFocusIndependentControl ="),
            action.index("WinActivate($g_hAndroidWindow)"),
        )

    def test_modern_bluestacks_screen_check_ignores_only_qt_presentation_height(self) -> None:
        android = source("COCBot/functions/Android/AndroidBluestacks5.au3")
        check = autoit_function(android, "CheckScreenBlueStacks5")
        self.assertIn("IsArray(GetBlueStacks5ModernAdbSurfacePosition())", check)
        self.assertIn("$abSettingFound[3] = True", check)
        self.assertIn("If $bModernAdbSurface And $iSearch = 3 Then ContinueLoop", check)
        self.assertIn("fb_width", check)
        self.assertIn("fb_height", check)
        self.assertIn("dpi", check)
        self.assertIn("display_name", check)
        self.assertIn("bst.enable_adb_access", check)

    def test_modern_bluestacks_close_targets_selected_player_instance(self) -> None:
        android = source("COCBot/functions/Android/AndroidBluestacks5.au3")
        close = autoit_function(android, "CloseBlueStacks5")
        self.assertIn(
            'ProcessExists2($__BlueStacks_Path & "HD-Player.exe", GetBlueStacks5ProgramParameter(), 1, 1)',
            close,
        )
        self.assertIn('Local $aFiles = ["HD-Frontend.exe", "HD-Plus-Service.exe", "HD-Service.exe"]', close)
        player = close.index('ProcessExists2($__BlueStacks_Path & "HD-Player.exe"')
        kill = close.index('taskkill.exe')
        fallback = close.index('ProcessExists2($sFile, $g_sAndroidInstance)')
        self.assertLess(player, kill)
        self.assertLess(kill, fallback)
        self.assertIn("failed to kill HD-Player.exe for instance", close)

    def test_modern_bluestacks_manual_viewport_uses_exact_render_child(self) -> None:
        android = source("COCBot/functions/Android/AndroidBluestacks5.au3")
        viewport = autoit_function(android, "GetBlueStacks5ModernManualViewportPosition")
        self.assertIn("GetBlueStacks5ModernAdbSurfacePosition()", viewport)
        self.assertIn("ManualViewportFindBlueStacks5Surface(", viewport)
        self.assertIn("Return 0", viewport)

        discovery = autoit_function(
            source("COCBot/functions/Other/ManualViewportMapping.au3"),
            "ManualViewportFindBlueStacks5Surface",
        )
        self.assertIn("_WinAPI_EnumChildWindows($hWindow, False)", discovery)
        self.assertIn('StringCompare(_WinAPI_GetClassName($hChild), "BlueStacksApp", 0)', discovery)
        self.assertIn("WinGetProcess($hChild) <> $iRootPid", discovery)
        self.assertIn("BitAND(WinGetState($hChild), 2) = 0", discovery)
        self.assertIn("WinGetPos($hWindow)", discovery)
        self.assertIn("Abs(($aCandidate[2] / $aCandidate[3]) - $fExpectedRatio) > 0.01", discovery)
        self.assertIn("If $iFound <> 1 Then Return 0", discovery)

        find_pos = autoit_function(source("COCBot/functions/Other/FindPos.au3"), "FindPos")
        self.assertLess(
            find_pos.index("GetBlueStacks5ModernManualViewportPosition()"),
            find_pos.index("MouseGetPos()"),
        )
        self.assertIn("Return SetError(1, 0, $aInvalidPos)", find_pos)
        self.assertIn("$g_aiBSpos[0] = $aModernViewport[0]", find_pos)
        self.assertIn("ManualViewportMapToFramebuffer(", find_pos)
        self.assertLess(find_pos.index("ManualViewportMapToFramebuffer("), find_pos.index("ConvertFromVillagePos("))

        mapping = autoit_function(source("COCBot/functions/Other/ManualViewportMapping.au3"), "ManualViewportMapToFramebuffer")
        self.assertIn("$iViewportX < 0 Or $iViewportY < 0", mapping)
        self.assertIn("$iViewportX >= $aViewport[2]", mapping)
        self.assertIn("(($iViewportX + 0.5) * $iFramebufferWidth) / $aViewport[2]", mapping)
        self.assertIn("(($iViewportY + 0.5) * $iFramebufferHeight) / $aViewport[3]", mapping)

    def test_pet_house_imgloc_is_converted_once_before_storage_use(self) -> None:
        pet_house = autoit_function(
            source("COCBot/functions/Village/LocatePetHouse.au3"), "ImgLocatePetHouse"
        )
        decode = pet_house.index("decodeSingleCoord(")
        convert = pet_house.index("ConvertFromVillagePos(")
        validate = pet_house.index("isInsideDiamond(")
        success = pet_house.index("Return True")
        self.assertLess(decode, convert)
        self.assertLess(convert, validate)
        self.assertLess(validate, success)
        self.assertEqual(pet_house.count("ConvertFromVillagePos("), 1)

    def test_manual_building_identity_checks_fail_closed(self) -> None:
        town_hall = autoit_function(
            source("COCBot/functions/Village/GetTownHallLevel.au3"), "GetTownHallLevel"
        )
        self.assertIn("If Not IsArray($aTHInfo) Or UBound($aTHInfo) < 3 Then", town_hall)
        self.assertLess(town_hall.index("If Not IsArray($aTHInfo)"), town_hall.index("$aTHInfo[0]="))

        pet_house = autoit_function(
            source("COCBot/functions/Village/LocatePetHouse.au3"), "_LocatePetHouse"
        )
        self.assertIn("If Not IsArray($sPetHouseInfo) Or UBound($sPetHouseInfo) < 3 Then", pet_house)
        self.assertNotIn("go ahead with it", pet_house)
        self.assertIn("Pet House identity was not verified; location was not accepted", pet_house)

        treasury = autoit_function(
            source("COCBot/functions/Village/TreasuryCollect.au3"), "TreasuryCollect"
        )
        self.assertIn("Not isInsideDiamond($g_aiClanCastlePos)", treasury)
        click = treasury.index("BuildingClick($g_aiClanCastlePos[0]")
        identity = treasury.index("$aClanCastleInfo = BuildingInfo(")
        treasury_button = treasury.index('findButton("Treasury"')
        self.assertLess(click, identity)
        self.assertLess(identity, treasury_button)
        self.assertIn('StringInStr($aClanCastleInfo[1], "clan") = 0', treasury)


if __name__ == "__main__":
    unittest.main()
