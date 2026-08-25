from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "COCBot" / "functions" / "Other" / "MBRFunc.au3"
ACTION = ROOT / "COCBot" / "MBR GUI Action.au3"
MAIN = ROOT / "MyBot.run.au3"
SLEEP = ROOT / "COCBot" / "functions" / "Other" / "_Sleep.au3"


def function_body(source: str, name: str) -> str:
    start = source.index(f"Func {name}(")
    return source[start : source.index("EndFunc", start)]


class EngineProbeLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parent = PARENT.read_text(encoding="utf-8-sig")
        cls.action = ACTION.read_text(encoding="utf-8-sig")
        cls.main = MAIN.read_text(encoding="utf-8-sig")
        cls.sleep = SLEEP.read_text(encoding="utf-8-sig")

    def test_supervisor_environment_is_consumed_before_backend_entrypoint(self) -> None:
        for env_name in (
            "MYBOT_ENGINE_INIT_TOKEN",
            "MYBOT_ENGINE_INIT_LAUNCHER_PID",
            "MYBOT_ENGINE_INIT_LAUNCHER_CREATED",
        ):
            self.assertIn(f'= "{env_name}"', self.parent)
        last_clear = self.parent.index('EnvSet($g_sMBRFuncEngineLauncherCreatedEnv, "")')
        self.assertLess(last_clear, self.parent.index("Func MBRFunc("))
        include = self.main.index('#include "COCBot\\functions\\Other\\MBRFunc.au3"')
        self.assertLess(include, self.main.index("InitializeBot()"))
        self.assertLess(include, self.main.index('_RunPlannerStartService('))
        self.assertIn('"^[0-9a-f]{64}$"', self.parent[: self.parent.index("Func MBRFunc(")])
        self.assertIn('"^[0-9a-f]{16}$"', self.parent[: self.parent.index("Func MBRFunc(")])

    def test_reviewed_mini_captures_then_clears_environment_for_scoped_forwarding(self) -> None:
        declarations = self.parent[: self.parent.index("Func MBRFunc(")]
        self.assertIn('^mybot\\.run(?:\\.minigui)?\\.(?:exe|au3)$', declarations)
        self.assertIn('StringLower(@ScriptName) = "mybot.run.exe"', declarations)
        self.assertIn('StringLower(@ScriptName) = "mybot.run.au3"', declarations)
        self.assertIn("If $g_bMBRFuncEngineContextHost Then", declarations)
        self.assertIn("$g_bMBRFuncEngineContextHost ? EnvGet", declarations)
        self.assertIn("$g_bMBRFuncEngineContextHost And StringRegExp", declarations)

    def test_managed_package_startup_skips_optional_outbound_version_check(self) -> None:
        managed = function_body(self.parent, "MBRFuncManagedLaunchBound")
        self.assertIn("$g_bMBRFuncBackendHost And $g_bMBRFuncEngineSupervisorValid", managed)
        gate = self.main.index("If MBRFuncManagedLaunchBound() Then")
        end = self.main.index("EndIf", gate)
        block = self.main[gate:end]
        self.assertIn("Managed local runtime skipped", block)
        self.assertIn("Else", block)
        self.assertEqual(1, block.count("CheckVersion()"))
        self.assertLess(block.index("Else"), block.index("CheckVersion()"))

    def test_static_probe_never_launches_helper_or_calls_managed_export(self) -> None:
        probe = function_body(self.parent, "MBRFuncProbeEngine")
        for forbidden in ("Run(", "DllCall(", "MyBot.run.EngineProbe.exe", "setProcessingPoolSize("):
            self.assertNotIn(forbidden, probe)
        self.assertIn("MBRFuncValidateEngineMarker", probe)
        self.assertIn("$g_bMBRFuncEngineSupervisorValid", probe)

    def test_packaged_helper_is_a_non_clr_integrity_canary(self) -> None:
        helper = (ROOT / "MyBot.run.EngineProbe.au3").read_text(encoding="utf-8-sig")
        self.assertIn('Global Const $ENGINE_PROBE_PROTOCOL = "engine-probe/v2"', helper)
        self.assertIn('"|static-ready"', helper)
        self.assertIn('FileGetSize($sMarkerPath) <> 0', helper)
        self.assertIn('FileGetSize($sLibraryPath) <= 0', helper)
        self.assertIn("Not $bFlushed", helper)
        for forbidden in ("DllOpen(", "DllCall(", "setProcessingPoolSize", "call-entered"):
            self.assertNotIn(forbidden, helper)

    def test_real_host_initialization_publishes_ordered_phases(self) -> None:
        initialize = function_body(self.parent, "MBRFuncInitialize")
        ordered = (
            '_MBRFuncPublishEngineReceipt("prepared")',
            '_MBRFuncPublishEngineReceipt("pool-entered")',
            "inherited processing-pool initialization skipped",
            '_MBRFuncPublishEngineReceipt("pool-returned")',
            '_MBRFuncPublishEngineReceipt("max-entered")',
            "inherited max-degree initialization skipped",
            '_MBRFuncPublishEngineReceipt("max-returned")',
            '_MBRFuncPublishEngineReceipt("android-entered")',
            "setAndroidPID(",
            '_MBRFuncPublishEngineReceipt("android-returned")',
            '_MBRFuncPublishEngineReceipt("gui-entered")',
            "SetBotGuiPID(",
            '_MBRFuncPublishEngineReceipt("initialized")',
        )
        offsets = [initialize.index(item) for item in ordered]
        self.assertEqual(offsets, sorted(offsets))
        self.assertEqual(initialize.count("setProcessingPoolSize("), 0)
        self.assertEqual(initialize.count("setMaxDegreeOfParallelism("), 0)
        self.assertLess(initialize.index("MBRFuncValidateEngineMarker("), offsets[0])
        self.assertLess(initialize.index("$g_bMBRFuncEngineSupervisorValid"), offsets[0])

    def test_automatic_processing_pool_uses_explicit_positive_processor_count(self) -> None:
        resolver = function_body(self.parent, "_MBRFuncAutomaticProcessingPoolSize")
        processing_pool = function_body(self.parent, "setProcessingPoolSize")
        self.assertIn('DllCall("kernel32.dll", "dword", "GetActiveProcessorCount", "word", 0xFFFF)', resolver)
        self.assertIn('EnvGet("NUMBER_OF_PROCESSORS")', resolver)
        self.assertIn("$iAutomaticPoolCap = 4", resolver)
        self.assertIn("$iActiveProcessors > $iAutomaticPoolCap ? $iAutomaticPoolCap : $iActiveProcessors", resolver)
        self.assertIn("$iEnvironmentProcessors > $iAutomaticPoolCap ? $iAutomaticPoolCap : $iEnvironmentProcessors", resolver)
        self.assertIn("Return 1", resolver)
        self.assertIn("_MBRFuncAutomaticProcessingPoolSize()", processing_pool)
        self.assertNotIn("$i = -1", processing_pool)
        self.assertIn('DllCall($g_hLibMyBot, "none", "setProcessingPoolSize", "int", $i)', processing_pool)

    def test_automatic_parallelism_uses_the_proven_managed_sentinel_after_warmup(self) -> None:
        parallelism = function_body(self.parent, "setMaxDegreeOfParallelism")
        sentinel = parallelism.index("If $i < 1 Then $i = -1")
        managed_call = parallelism.index('DllCall($g_hLibMyBot, "none", "setMaxDegreeOfParallelism", "int", $i)')
        self.assertLess(sentinel, managed_call)
        self.assertIn('SetDebugLog("Threading: Using " & $i & " threads for parallelism")', parallelism)

    def test_bluestacks5_exact_adb_surface_keeps_managed_player_binding_detached(self) -> None:
        binding = function_body(self.parent, "setAndroidPID")
        verifier = function_body(self.parent, "_MBRFuncExactDetachedAdbSurfaceAvailable")
        for required in (
            '$g_sAndroidEmulator = "BlueStacks5"',
            "$g_bAndroidAdbScreencap",
            "$g_bAndroidAdbClick",
            "_MBRFuncExactDetachedAdbSurfaceAvailable()",
            '$g_sMBRFuncAndroidBindingMode = "detached-adb"',
            "The exact detached ADB transport changed after managed initialization",
            "$pid = 0",
            "exact ADB surface owns player PID",
        ):
            self.assertIn(required, binding)
        self.assertLess(binding.index("$pid = 0"), binding.index('DllCall($g_hLibMyBot, "str", "setAndroidPID"'))
        self.assertLess(binding.index('Case "detached-adb"'), binding.index('DllCall($g_hLibMyBot, "str", "setAndroidPID"'))
        self.assertIn('"GetBlueStacks5ModernAdbSurface" & "Position"', verifier)
        self.assertIn("Call($sSurfaceVerifier)", verifier)
        self.assertIn("Local $iCallError = @error", verifier)
        self.assertNotIn("IsFunc(", verifier)
        self.assertNotIn("GetBlueStacks5ModernAdbSurfacePosition()", self.parent)

    def test_receipt_is_fixed_atomic_flushed_and_identity_bound(self) -> None:
        self.assertIn(
            'Global Const $g_sMBRFuncEngineReceiptPath = $g_sMBRFuncRuntimeLocalAppData & "\\My Bot 2.0\\engine-init-owner-v1.json"',
            self.parent,
        )
        publish = function_body(self.parent, "_MBRFuncPublishEngineReceipt")
        for field in (
            "schema",
            "token",
            "launcher_pid",
            "launcher_created",
            "controller_pid",
            "controller_created",
            "backend_pid",
            "backend_created",
            "parent_pid",
            "phase",
            "start_request_id",
            "sequence",
            "phase_history",
        ):
            self.assertIn(f'\\"{field}\\"', publish.replace('"', '\\"'))
        offsets = [publish.index(item) for item in ("FileOpen(", "FileWrite(", "FileFlush(", "FileClose(", "FileMove(", "FileRead(")]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("Not $bFlushed", publish)
        self.assertIn("_MBRFuncEngineReceiptPathSafe(False)", publish)
        self.assertIn("_MBRFuncEngineReceiptPathSafe(True)", publish)
        self.assertIn("$sLauncherCreated <> $g_sMBRFuncEngineLauncherCreated", publish)
        self.assertIn("$g_sMBRFuncEngineReceiptHistory = $sCandidateHistory", publish)
        self.assertLess(
            publish.index("FileRead($g_sMBRFuncEngineReceiptPath)"),
            publish.index("$g_sMBRFuncEngineReceiptHistory = $sCandidateHistory"),
        )
        safe = function_body(self.parent, "_MBRFuncEngineReceiptPathSafe")
        self.assertIn("BitAND($aParent[0], 0x400) <> 0", safe)
        self.assertIn("BitAND($aReceipt[0], 0x400) = 0", safe)

    def test_failures_are_sticky_and_publish_failed(self) -> None:
        failure = function_body(self.parent, "_MBRFuncInitializationFailed")
        self.assertLess(failure.index("MBRFuncMarkUnavailable"), failure.index('_MBRFuncPublishEngineReceipt("failed")'))
        mark = function_body(self.parent, "MBRFuncMarkUnavailable")
        self.assertIn("$g_bMBRFuncEngineAvailable = False", mark)
        self.assertIn('$g_sMBRFuncEngineProbeState = "failed"', mark)
        initialize = function_body(self.parent, "MBRFuncInitialize")
        self.assertIn('$g_sMBRFuncEngineProbeState = "running"', initialize)
        self.assertIn('$g_sMBRFuncEngineProbeState = "passed"', initialize)

    def test_start_launches_exact_game_before_managed_attachment(self) -> None:
        start = function_body(self.action, "BotStart")
        probe = start.index("MBRFuncProbeEngine(")
        launch = start.index("If Not _BotEnsureConfiguredAndroidAndGame(", probe)
        initialize = start.index("MBRFuncInitialize()", launch)
        authorization = start.index("ForumAuthentication()", initialize)
        resume = start.index("ResumeAndroid()", authorization)
        self.assertEqual(
            [probe, launch, initialize, authorization, resume],
            sorted((probe, launch, initialize, authorization, resume)),
        )
        pre_init = start[launch:initialize]
        self.assertIn("If Not _BotEnsureConfiguredAndroidAndGame($sStartError) Then", pre_init)
        self.assertIn("Return FuncReturn(_BotStartReject($sStartError))", pre_init)

    def test_start_request_id_callback_fails_closed_and_initialization_requires_it(self) -> None:
        request = function_body(self.parent, "_MBRFuncCurrentStartRequestId")
        self.assertNotIn("IsFunc($sCallback)", request)
        self.assertIn("Call($sCallback)", request)
        self.assertIn("Local $iCallError = @error", request)
        self.assertIn("Local $iCallExtended = @extended", request)
        self.assertIn("0xDEAD", request)
        self.assertIn("0xBEEF", request)
        self.assertNotIn('IsFunc($sCallback)', request)
        self.assertIn('"^[A-Za-z0-9._-]{1,80}$"', request)
        self.assertIn('Return ""', request)
        initialize = function_body(self.parent, "MBRFuncInitialize")
        required = initialize.index("Local $sStartRequestId = _MBRFuncCurrentStartRequestId()")
        prepared = initialize.index('_MBRFuncPublishEngineReceipt("prepared")')
        self.assertLess(required, prepared)

    def test_receipt_generation_captures_request_id_once_and_resets_monotonic_state(self) -> None:
        initialize = function_body(self.parent, "MBRFuncInitialize")
        publish = function_body(self.parent, "_MBRFuncPublishEngineReceipt")
        capture = initialize.index("Local $sStartRequestId = _MBRFuncCurrentStartRequestId()")
        bind = initialize.index("$g_sMBRFuncEngineReceiptStartRequestId = $sStartRequestId")
        reset_sequence = initialize.index("$g_iMBRFuncEngineReceiptSequence = 0")
        reset_history = initialize.index('$g_sMBRFuncEngineReceiptHistory = ""')
        prepared = initialize.index('_MBRFuncPublishEngineReceipt("prepared")')
        self.assertLess(capture, bind)
        self.assertLess(bind, reset_sequence)
        self.assertLess(reset_sequence, reset_history)
        self.assertLess(reset_history, prepared)
        self.assertIn("$g_sMBRFuncEngineReceiptStartRequestId", publish)
        self.assertNotIn("_MBRFuncCurrentStartRequestId()", publish)

    def test_optional_string_callbacks_use_call_instead_of_isfunc(self) -> None:
        unavailable = function_body(self.parent, "MBRFuncMarkUnavailable")
        self.assertNotIn("IsFunc($sEventCallback)", unavailable)
        self.assertIn("Call($sEventCallback", unavailable)
        self.assertNotIn('IsFunc("RunControlPoll")', self.sleep)
        self.assertIn('"RunControl" & "Poll"', self.sleep)
        self.assertIn("Call($sRunControlPollCallback)", self.sleep)


if __name__ == "__main__":
    unittest.main()
