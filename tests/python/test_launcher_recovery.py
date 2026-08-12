import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
LAUNCHER = (ROOT / "My Bot 2.0.au3").read_text(encoding="utf-8-sig")


class LauncherRecoveryContractTests(unittest.TestCase):
    def test_recovery_is_explicit_and_runs_before_install_validation(self):
        recovery_gate = 'If _CommandLineHas("/recover") Or _CommandLineHas("/repair") Then'
        self.assertIn(recovery_gate, LAUNCHER)
        self.assertLess(LAUNCHER.index(recovery_gate), LAUNCHER.index("If Not _ValidateInstallation()"))

    def test_only_exact_checkout_process_paths_are_closed(self):
        self.assertIn('StringLower(_ProcessImagePath($iPid)) <> StringLower($sExpectedPath)', LAUNCHER)
        self.assertIn('_CloseExactPathProcesses("MyBot.run.MiniGui.exe", $g_sControllerPath)', LAUNCHER)
        self.assertIn('_CloseExactPathProcesses("MyBot.run.exe", $g_sHostPath)', LAUNCHER)
        self.assertIn('_CloseExactPathProcesses("My Bot 2.0.exe", @ScriptFullPath, @AutoItPID)', LAUNCHER)

    def test_owned_autoit_errors_are_logged_before_close(self):
        start = LAUNCHER.index("Func _CloseOwnedAutoItErrorDialogs()")
        end = LAUNCHER.index("EndFunc   ;==>_CloseOwnedAutoItErrorDialogs", start)
        body = LAUNCHER[start:end]
        self.assertIn('WinList("AutoIt Error")', body)
        self.assertIn("@ScriptDir", body)
        self.assertLess(body.index('_RecoveryLog("closing owned AutoIt error'), body.index("WinClose($hDialog)"))

    def test_recovery_never_targets_bluestacks(self):
        start = LAUNCHER.index("Func _RecoverBotStack()")
        end = LAUNCHER.index("EndFunc   ;==>_RecoverBotStack", start)
        body = LAUNCHER[start:end]
        self.assertNotIn("BlueStacks", body)
        self.assertNotIn("HD-Player", body)

    def test_recovery_closes_only_a_verified_checkout_planner_service(self):
        self.assertIn('Global Const $g_sPlannerServiceName = "my-bot-control-center"', LAUNCHER)
        start = LAUNCHER.index("Func _CloseOwnedPlannerService()")
        end = LAUNCHER.index("EndFunc   ;==>_CloseOwnedPlannerService", start)
        body = LAUNCHER[start:end]
        for proof in (
            "$g_sPlannerServiceName",
            '"repo_root"',
            '"build_sha256"',
            '"service_pid"',
            "_FileSha256($g_sPlannerScriptPath)",
            "_ProcessImagePath($iPid)",
            '"\\\\pythonw\\.exe$"',
        ):
            self.assertIn(proof, body)
        self.assertLess(body.index("_ProcessImagePath($iPid)"), body.index("ProcessClose($iPid)"))
        recovery = LAUNCHER[LAUNCHER.index("Func _RecoverBotStack()"):LAUNCHER.index("EndFunc   ;==>_RecoverBotStack")]
        self.assertIn("Local $bPlannerClosed = _CloseOwnedPlannerService()", recovery)
        self.assertIn("And $bPlannerClosed", recovery)

    def test_launcher_errors_are_logged_and_bounded_without_topmost_focus(self):
        start = LAUNCHER.index("Func _ShowError($sMessage)")
        end = LAUNCHER.index("EndFunc   ;==>_ShowError", start)
        body = LAUNCHER[start:end]
        self.assertIn('launcher error; pid=', body)
        self.assertIn("@ScriptFullPath", body)
        self.assertNotIn("$MB_TOPMOST", body)
        self.assertIn("$g_iLauncherErrorTimeoutSec", body)
        self.assertLess(body.index('_RecoveryLog("launcher error;'), body.index("MsgBox("))

    def test_launcher_owns_a_visible_control_center_strip(self):
        self.assertIn('GUICreate("My Bot 2.0 Control"', LAUNCHER)
        self.assertIn('GUICtrlCreateButton("OPEN CONTROL CENTER"', LAUNCHER)
        self.assertIn('GUICtrlSetOnEvent($g_idOpenControlCenter, "_OpenControlCenter")', LAUNCHER)
        self.assertNotIn("$WS_EX_TOPMOST", LAUNCHER)
        self.assertLess(LAUNCHER.index("_ShowControlStrip($hController)"), LAUNCHER.index("_DockWhenReady($hController"))


if __name__ == "__main__":
    unittest.main()
