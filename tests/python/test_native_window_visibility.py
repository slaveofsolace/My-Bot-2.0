import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
PLACEMENT = (ROOT / "COCBot" / "functions" / "GUI" / "WindowPlacement.au3").read_text(encoding="utf-8-sig")
FULL_GUI = (ROOT / "COCBot" / "MBR GUI Design.au3").read_text(encoding="utf-8-sig")
MINI_GUI = (ROOT / "COCBot" / "MBR GUI Design Mini.au3").read_text(encoding="utf-8-sig")
MINI_ENTRY = (ROOT / "MyBot.run.MiniGui.au3").read_text(encoding="utf-8-sig")


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

    def test_installed_controller_launches_the_full_native_configuration_surface(self) -> None:
        self.assertIn("Func LaunchBotBackend($bNoGUI = False)", MINI_ENTRY)
        self.assertIn('$sParam & ($bNoGUI ? " /ng" : "")', MINI_ENTRY)

    def test_controller_recovers_one_idle_backend_without_replaying_start(self) -> None:
        recovery = MINI_ENTRY.split("Func _MiniEnsureBackendAvailable()", 1)[1].split("EndFunc", 1)[0]
        self.assertIn("ProcessExists($g_WatchOnlyClientPID)", recovery)
        self.assertIn("LaunchBotBackend()", recovery)
        self.assertIn("Start was not replayed", recovery)
        self.assertNotIn("BotStart()", recovery)


if __name__ == "__main__":
    unittest.main()
