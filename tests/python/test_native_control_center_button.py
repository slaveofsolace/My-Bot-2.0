import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class NativeControlCenterButtonTests(unittest.TestCase):
    def test_visible_launcher_strip_has_explicit_browser_button(self):
        source = (ROOT / "My Bot 2.0.au3").read_text(encoding="utf-8-sig")
        self.assertIn('GUICtrlCreateButton("OPEN CONTROL CENTER"', source)
        self.assertIn('GUICtrlSetOnEvent($g_idOpenControlCenter, "_OpenControlCenter")', source)
        self.assertIn('BitOR($WS_POPUP, $WS_BORDER), 0, $hController)', source)
        self.assertNotIn('BitOR($WS_POPUP, $WS_BORDER), $WS_EX_TOOLWINDOW)', source)

    def test_click_handler_opens_only_local_control_center(self):
        source = (ROOT / "MyBot.run.MiniGui.au3").read_text(encoding="utf-8-sig")
        self.assertIn('ShellExecute("http://127.0.0.1:8765/")', source)
        self.assertIn('$g_hFrmBot_URL_PIC, $g_hFrmBot_URL_PIC2', source)

    def test_shipped_controller_remains_provenance_locked(self):
        source = (ROOT / "MyBot.run.MiniGui.au3").read_text(encoding="utf-8-sig")
        launcher = (ROOT / "My Bot 2.0.au3").read_text(encoding="utf-8-sig")
        self.assertIn('#pragma compile(Out, MyBot.run.MiniGui.dev.exe)', source)
        self.assertIn('Global Const $g_sControllerSha256 = "ae26c098', launcher)
        self.assertIn("Global Const $g_iControllerBytes = 1634304", launcher)

    def test_dock_target_comes_from_the_bound_controller_instance(self):
        launcher = (ROOT / "My Bot 2.0.au3").read_text(encoding="utf-8-sig")
        self.assertNotIn('Global Const $g_sBlueStacksTitle = "BlueStacks5-Pie64"', launcher)
        self.assertIn('Func _ControllerBlueStacksTitle($hController)', launcher)
        self.assertIn('Return "BlueStacks5-" & $aMatch[0]', launcher)
        self.assertIn('_FindBlueStacksWindow($hController)', launcher)

    def test_exact_dock_pair_minimizes_and_restores_as_one_background_unit(self):
        launcher = (ROOT / "My Bot 2.0.au3").read_text(encoding="utf-8-sig")
        self.assertIn("Func _SynchronizeDockPairVisibility($hController, $hBlueStacks)", launcher)
        self.assertIn("Global Const $g_iPairMinimizing", launcher)
        self.assertIn("$g_iPairMinimized", launcher)
        self.assertIn("Global Const $g_iPairRestoring", launcher)
        self.assertIn('WinSetState($hController, "", @SW_MINIMIZE)', launcher)
        self.assertIn('WinSetState($hBlueStacks, "", @SW_MINIMIZE)', launcher)
        self.assertIn('WinSetState($hController, "", @SW_RESTORE)', launcher)
        self.assertIn('WinSetState($hBlueStacks, "", @SW_RESTORE)', launcher)
        self.assertIn('WinSetState($g_hControlStrip, "", @SW_HIDE)', launcher)
        self.assertIn('WinSetState($g_hControlStrip, "", @SW_SHOW)', launcher)
        self.assertIn('GUICtrlCreateButton("MINIMIZE BOTH - BACKGROUND"', launcher)
        self.assertIn('GUICtrlSetOnEvent($g_idMinimizePair, "_MinimizeDockPair")', launcher)
        self.assertIn("Func _MinimizeDockPair()", launcher)
        self.assertIn('If _CommandLineHas("/background") Then Exit _SetDockPairMinimized() ? 0 : 7', launcher)
        self.assertIn('If _CommandLineHas("/foreground") Then Exit _SetDockPairRestored() ? 0 : 8', launcher)
        self.assertIn("Func _SetDockPairRestored()", launcher)
        self.assertIn("$g_iPairVisibilityState = $g_iPairMinimized", launcher)
        self.assertLess(
            launcher.index("_SynchronizeDockPairVisibility($hController, $hBlueStacks)"),
            launcher.index("_DockController($hController, $hBlueStacks, False)", launcher.index("Func _KeepDocked")),
        )

    def test_owned_control_strip_cannot_cancel_a_user_minimize(self):
        launcher = (ROOT / "My Bot 2.0.au3").read_text(encoding="utf-8-sig")
        keeper = launcher[launcher.index("Func _KeepDocked"):launcher.index("EndFunc   ;==>_KeepDocked")]
        synchronize = keeper.index("_SynchronizeDockPairVisibility($hController, $hBlueStacks)")
        self.assertNotIn("_DockControlStrip($hController)", keeper[:synchronize])

        strip = launcher[launcher.index("Func _DockControlStrip"):launcher.index("EndFunc   ;==>_DockControlStrip")]
        self.assertIn("If _WindowIsMinimized($hController) Then", strip)
        self.assertIn('WinSetState($g_hControlStrip, "", @SW_HIDE)', strip)
        self.assertLess(
            strip.index("If _WindowIsMinimized($hController) Then"),
            strip.index("WinGetPos($hController)"),
        )

        synchronize_body = launcher[
            launcher.index("Func _SynchronizeDockPairVisibility"):
            launcher.index("EndFunc   ;==>_SynchronizeDockPairVisibility")
        ]
        self.assertIn(
            "If _WindowIsMinimized($hController) And _WindowIsMinimized($hBlueStacks) Then",
            synchronize_body,
        )
        self.assertIn(
            "$g_iPairVisibilityState = $g_iPairMinimized",
            synchronize_body,
        )
        minimized_case = synchronize_body[synchronize_body.index("Case $g_iPairMinimized"):]
        self.assertIn("$g_iPairVisibilityState = $g_iPairVisible", minimized_case)


if __name__ == "__main__":
    unittest.main()
