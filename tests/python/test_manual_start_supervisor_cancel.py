from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUN_CONTROL = ROOT / "COCBot" / "functions" / "Run" / "RunControlBridge.au3"
GUI_ACTION = ROOT / "COCBot" / "MBR GUI Action.au3"
MINI = ROOT / "MyBot.run.MiniGui.au3"
MBR_FUNC = ROOT / "COCBot" / "functions" / "Other" / "MBRFunc.au3"


def function(source: str, name: str) -> str:
    match = re.search(
        rf"Func {re.escape(name)}\([^\r\n]*\)(.*?)EndFunc\s*;==>{re.escape(name)}",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"{name} was not found")
    return match.group(1)


class ManualStartRequestIdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bridge = RUN_CONTROL.read_text(encoding="utf-8")
        cls.gui_action = GUI_ACTION.read_text(encoding="utf-8")

    def test_each_start_has_one_active_grammar_safe_request_id(self) -> None:
        begin = function(self.bridge, "RunControlBeginStart")
        current = function(self.bridge, "RunControlCurrentCommandId")
        generator = function(self.bridge, "_RunControlNewLocalStartRequestId")

        self.assertIn("$g_sRunControlPendingStartRequestId", begin)
        self.assertIn("$g_sRunControlActiveStartRequestId = $g_sRunControlPendingStartRequestId", begin)
        self.assertIn("$g_sRunControlActiveStartRequestId = _RunControlNewLocalStartRequestId()", begin)
        self.assertLess(begin.index("$g_sRunControlActiveStartRequestId"), begin.index("$g_bRunControlStartInProgress = True"))
        self.assertIn('"local-start-"', generator)
        self.assertIn('"^[A-Za-z0-9._-]{1,80}$"', generator)
        self.assertIn("If Not $g_bRunControlStartInProgress Then Return \"\"", current)
        self.assertIn("Return $g_sRunControlActiveStartRequestId", current)

    def test_remote_start_id_is_staged_exactly_and_terminal_paths_clear_active_id(self) -> None:
        consume = function(self.bridge, "_RunControlConsumeCommand")
        start_case = consume[consume.index('Case "start"') : consume.index('Case "stop"')]
        self.assertIn("$g_sRunControlPendingStartRequestId = $sRequestId", start_case)
        self.assertNotIn("StringLower($sRequestId)", start_case)
        self.assertNotIn("StringReplace($sRequestId", start_case)

        for terminal in (
            "RunControlReportStartOutcome",
            "RunControlReportRunFailure",
            "RunControlReportStopComplete",
            "RunControlShutdown",
        ):
            body = function(self.bridge, terminal)
            self.assertIn('$g_sRunControlActiveStartRequestId = ""', body)

    def test_start_id_exists_before_first_managed_export(self) -> None:
        bot_start = function(self.gui_action, "BotStart")
        begin = bot_start.index("RunControlBeginStart()")
        first_export_boundary = min(
            bot_start.index("MBRFuncProbeEngine("),
            bot_start.index("MBRFuncInitialize()"),
        )
        self.assertLess(begin, first_export_boundary)


class MiniSupervisorCancelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mini = MINI.read_text(encoding="utf-8")
        cls.mbr_func = MBR_FUNC.read_text(encoding="utf-8")

    def test_cancel_validates_fixed_bounded_receipt_and_exact_process_chain(self) -> None:
        validate = function(self.mini, "_MiniEngineReceiptMatches")
        write = function(self.mini, "_MiniTryWriteEngineInitCancel")

        self.assertIn('@LocalAppDataDir & "\\My Bot 2.0\\engine-init-owner-v1.json"', self.mbr_func)
        self.assertIn("$g_sMBRFuncEngineReceiptPath", write)
        self.assertIn("_MBRFuncEngineReceiptPathSafe(True)", write)
        self.assertIn("$g_iMiniEngineInitReceiptMaxBytes", write)
        for field in (
            '"schema"',
            '"token"',
            '"launcher_pid"',
            '"launcher_created"',
            '"controller_pid"',
            '"controller_created"',
            '"backend_pid"',
            '"backend_created"',
            '"parent_pid"',
            '"phase"',
            '"sequence"',
            '"start_request_id"',
        ):
            self.assertIn(field, validate)
        self.assertIn("_MBRFuncParentPid(@AutoItPID) <> $iLauncherPid", validate)
        self.assertIn("_MBRFuncParentPid($iBackendPid) <> @AutoItPID", validate)
        self.assertIn("WinGetProcess($g_hFrmBotBackend) <> $iBackendPid", validate)
        self.assertIn("prepared|pool-entered|pool-returned", validate)
        self.assertNotIn("|initialized", validate)
        self.assertNotIn("|failed", validate)

    def test_cancel_write_is_nonce_bound_atomic_flushed_and_read_back(self) -> None:
        write = function(self.mini, "_MiniTryWriteEngineInitCancel")
        ordered = (
            "_MiniEngineReceiptMatches($sReceipt, $sStartRequestId)",
            "_MiniEngineNewStopRequestId()",
            '"expected_start_request_id"',
            '"stop_request_id"',
            "FileOpen($sTemporary, 10)",
            "FileWrite($hCancel, $sCancel)",
            "FileFlush($hCancel)",
            "FileClose($hCancel)",
            "FileMove($sTemporary, $g_sMiniEngineInitCancelPath, 1)",
            "FileRead($g_sMiniEngineInitCancelPath) = $sCancel",
        )
        offsets = [write.index(item) for item in ordered]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn('$g_sMiniEngineInitCancelPath = @ScriptDir & "\\config\\engine-init-cancel.local.json"', self.mini)

    def test_stop_always_posts_even_if_cancel_cannot_be_written(self) -> None:
        stop = function(self.mini, "BotStop")
        cancel = stop.index("_MiniTryWriteEngineInitCancel()")
        post = stop.index("_WinAPI_PostMessage(")
        self.assertLess(cancel, post)
        self.assertNotRegex(stop[cancel:post], r"\bReturn\b")
        self.assertNotIn("If _MiniTryWriteEngineInitCancel()", stop)

    def test_secret_never_enters_argv_or_logs(self) -> None:
        launch = function(self.mini, "LaunchBotBackend")
        for line in launch.splitlines():
            if "$g_sMBRFuncEngineSupervisorToken" in line:
                self.assertIn("EnvSet(", line)
                self.assertNotIn("$cmd", line)
                self.assertNotIn("$sParam", line)
        for line in self.mini.splitlines():
            if "SetLog(" in line or "SetDebugLog(" in line:
                self.assertNotIn("$g_sMBRFuncEngineSupervisorToken", line)


if __name__ == "__main__":
    unittest.main()
