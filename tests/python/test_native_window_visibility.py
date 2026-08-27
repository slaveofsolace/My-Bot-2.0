import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
PLACEMENT = (ROOT / "COCBot" / "functions" / "GUI" / "WindowPlacement.au3").read_text(encoding="utf-8-sig")
ARRANGE = (ROOT / "COCBot" / "functions" / "Other" / "WindowsArrange.au3").read_text(encoding="utf-8-sig")
GLOBALS = (ROOT / "COCBot" / "MBR Global Variables.au3").read_text(encoding="utf-8-sig")
FULL_GUI = (ROOT / "COCBot" / "MBR GUI Design.au3").read_text(encoding="utf-8-sig")
MINI_GUI = (ROOT / "COCBot" / "MBR GUI Design Mini.au3").read_text(encoding="utf-8-sig")
MINI_ENTRY = (ROOT / "MyBot.run.MiniGui.au3").read_text(encoding="utf-8-sig")
BACKEND_ENTRY = (ROOT / "MyBot.run.au3").read_text(encoding="utf-8-sig")
LAUNCHER = (ROOT / "My Bot 2.0.au3").read_text(encoding="utf-8-sig")


class NativeWindowVisibilityTests(unittest.TestCase):
    def test_stale_coordinates_are_checked_against_real_monitors(self) -> None:
        self.assertIn('DllCall("user32.dll", "handle", "MonitorFromWindow", "hwnd", $hWindow, "dword", 0)', PLACEMENT)
        self.assertIn("WinMove($hWindow", PLACEMENT)
        self.assertIn("$iSavedX = $aMoved[0]", PLACEMENT)
        self.assertIn("$iSavedY = $aMoved[1]", PLACEMENT)

    def test_both_native_surfaces_apply_the_visibility_guard(self) -> None:
        for source in (FULL_GUI, MINI_GUI):
            self.assertIn('#include "functions\\GUI\\WindowPlacement.au3"', source)
            create = source.split("Func CreateMainGUI()", 1)[1].split("EndFunc", 1)[0]
            self.assertLess(create.index("GUICreate("), create.index("WindowPlacementEnsureVisible("))

    def test_managed_install_forces_initial_and_restored_surfaces_to_primary_display(self) -> None:
        self.assertIn("Global $g_bForcePrimaryWindow = False", GLOBALS)
        self.assertIn('Return $sProfile & " /nowatchdog /primarywindow"', LAUNCHER)
        for source in (MINI_ENTRY, BACKEND_ENTRY):
            self.assertIn('Case "/primarywindow"', source)
            self.assertIn("$g_bForcePrimaryWindow = True", source)
        self.assertIn("If $g_bForcePrimaryWindow Then", PLACEMENT)
        self.assertIn("WindowPlacementIntersectsPrimary($aWindow)", PLACEMENT)
        self.assertIn("If $g_bForcePrimaryWindow Then", ARRANGE)
        self.assertIn("WindowPlacementIntersectsPrimary($aWindow)", ARRANGE)
        self.assertIn("$p[0] = (@DesktopWidth", ARRANGE)

    def test_direct_native_launch_keeps_multi_monitor_placement_available(self) -> None:
        self.assertIn("Else", PLACEMENT)
        self.assertIn('MonitorFromWindow", "hwnd", $hWindow, "dword", 0', PLACEMENT)
        self.assertIn("If $monitorHandle <> 0 Then", ARRANGE)

    def test_installed_controller_launches_the_full_native_configuration_surface(self) -> None:
        self.assertIn("Func LaunchBotBackend($bNoGUI = False)", MINI_ENTRY)
        self.assertIn('$sParam & ($bNoGUI ? " /ng" : "")', MINI_ENTRY)

    def test_controller_recovers_one_idle_backend_without_replaying_start(self) -> None:
        recovery = MINI_ENTRY.split("Func _MiniEnsureBackendAvailable()", 1)[1].split("EndFunc", 1)[0]
        self.assertIn("ProcessExists($g_WatchOnlyClientPID)", recovery)
        self.assertIn("LaunchBotBackend()", recovery)
        self.assertIn("Start was not replayed", recovery)
        self.assertNotIn("BotStart()", recovery)

    def test_mini_controller_publishes_structured_lifecycle_receipts(self) -> None:
        self.assertIn("mini-supervisor-lifecycle-v1.json", MINI_ENTRY)
        writer = MINI_ENTRY.split("Func _MiniWriteLifecycleState(", 1)[1].split("EndFunc", 1)[0]
        for contract in (
            "my-bot-mini-supervisor-lifecycle-v1",
            "controller_pid",
            "controller_created",
            "backend_pid",
            "backend_created",
            "backend_alive",
            "backend_window_attached",
            "recovery_active",
            "start_replayed",
            "FileMove($sTemporary, $g_sMiniLifecycleReceiptPath, 1)",
        ):
            self.assertIn(contract, writer)
        self.assertIn("Local $bWritten = FileWrite($hFile, $sJson)", writer)

        recovery = MINI_ENTRY.split("Func _MiniEnsureBackendAvailable()", 1)[1].split("EndFunc", 1)[0]
        for state in (
            '"ready-idle", "backend process is alive"',
            '"recovering", "backend exited; waiting before one exact-path recovery generation"',
            '"recovering", "launching one exact-path recovery generation"',
            '"ready-idle", "backend recovered in Idle; Start was not replayed"',
            '"failed", "backend recovery did not become ready"',
        ):
            self.assertIn(state, recovery)
        self.assertNotIn("BotStart()", recovery)

        start = MINI_ENTRY.split("Func BotStart()", 1)[1].split("EndFunc", 1)[0]
        stop = MINI_ENTRY.split("Func BotStop()", 1)[1].split("EndFunc", 1)[0]
        close = MINI_ENTRY.split("Func BotClose(", 1)[1].split("EndFunc", 1)[0]
        self.assertIn('"running", "Start command forwarded to owned backend"', start)
        self.assertIn('"stopping", "Stop command forwarded to owned backend"', stop)
        self.assertIn('"stopping", "Mini controller is closing"', close)


if __name__ == "__main__":
    unittest.main()
