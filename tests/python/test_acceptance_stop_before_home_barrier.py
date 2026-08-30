from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def function_body(document: str, name: str) -> str:
    start = document.index(f"Func {name}(")
    return document[start : document.index("EndFunc", start)]


class AcceptanceStopBeforeHomeBarrierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = source("COCBot/functions/Run/AcceptanceStopBeforeHome.au3")
        cls.android = source("COCBot/functions/Android/AndroidBluestacks5.au3")
        cls.action = source("COCBot/MBR GUI Action.au3")
        cls.bridge = source("COCBot/functions/Run/RunControlBridge.au3")
        cls.events = source("COCBot/functions/Run/RunEventLog.au3")
        cls.event_contract = source("COCBot/functions/Run/RunEvent.au3")
        cls.event_schema = json.loads(source("config/run-event.schema.json"))

    def test_contract_is_explicit_inert_and_exactly_token_bound(self) -> None:
        environment = function_body(self.contract, "AcceptanceStopBeforeHomeEnvironmentState")
        self.assertIn('MYBOT_ACCEPTANCE_STOP_BEFORE_HOME"', self.contract)
        self.assertIn('MYBOT_ACCEPTANCE_STOP_BEFORE_HOME_TOKEN"', self.contract)
        self.assertIn('If $sFlag = "" And $sToken = "" Then Return 0', environment)
        self.assertIn('If $sFlag <> "1" Then', environment)
        self.assertIn('^sha256:[0-9a-f]{64}$', environment)
        self.assertIn("Return -1", environment)
        self.assertIn("Return 1", environment)

    def test_contract_requires_exact_planned_pie64_generation(self) -> None:
        binding = function_body(self.contract, "AcceptanceStopBeforeHomeBindingValid")
        for required in (
            '"^(planned|native-profile)$"',
            '"^[A-Za-z0-9._-]{1,80}$"',
            '"^[A-Za-z0-9._-]{1,128}$"',
            '"^(0|[1-9][0-9]{0,18})$"',
            '"^sha256:[0-9a-f]{64}$"',
            '$sMode = "native-profile" And $sPlanToken = "absent"',
            '$sEmulator <> "BlueStacks5"',
            '$sInstance <> "Pie64"',
        ):
            self.assertIn(required, binding)

        production = function_body(self.android, "BlueStacks5AcceptanceStopBeforeHomeContract")
        for required in (
            "AcceptanceStopBeforeHomeEnvironmentState(",
            "RunControlCurrentStartMode()",
            "RunControlCurrentStartGeneration()",
            "RunExecutionSessionId()",
            "RunControlCurrentStartPlanRevision()",
            "RunControlCurrentStartPlanToken()",
            "$g_sProfileCurrentName",
            "$g_sAndroidEmulator",
            "$g_sAndroidInstance",
        ):
            self.assertIn(required, production)

    def test_existing_instance_is_rejected_before_any_recognition(self) -> None:
        ensure = function_body(self.action, "_BotOpenHomeEnsureExactBlueStacks")
        contract = ensure.index("BlueStacks5AcceptanceStopBeforeHomeContract(")
        attachment = ensure.index("_BotOpenHomeRequireExactBlueStacks(")
        reject = ensure.index("If $iAcceptanceMode = 1 Then")
        first_recognition = ensure.index("OpenHomeCollectorsProveHome()")
        self.assertLess(contract, attachment)
        self.assertLess(attachment, reject)
        self.assertLess(reject, first_recognition)
        self.assertIn("requires a fresh product-owned Pie64 launch", ensure)

    def test_barrier_sits_after_owned_dispatch_and_before_home(self) -> None:
        adapter = function_body(self.android, "LaunchBlueStacks5CoCOnly")
        owner = adapter.index("_BlueStacks5WriteLaunchOnlyOwnerReceipt($iOwnedPlayerPid)")
        dispatch = adapter.index('AndroidAdbSendShellCommand("am start -n "')
        adb_identity = adapter.index("Local $iOwnedAdbPid = Int($g_iAndroidAdbProcess[0])")
        barrier = adapter.index("_BlueStacks5AcceptanceStopBeforeHomeBarrier(")
        game_timer = adapter.index("Local $hGameTimer = __TimerInit()")
        first_home = adapter.index("OpenHomeCollectorsProveHome()")
        self.assertLess(owner, dispatch)
        self.assertLess(dispatch, adb_identity)
        self.assertLess(adb_identity, barrier)
        self.assertLess(barrier, game_timer)
        self.assertLess(game_timer, first_home)
        self.assertIn("Not $bStartedEmulator", adapter)
        self.assertIn("_MBRFuncParentPid($iOwnedAdbPid) <> @AutoItPID", adapter)
        self.assertEqual(adapter.count('AndroidAdbSendShellCommand("am start -n "'), 1)

    def test_barrier_accepts_only_generation_bound_stop_and_never_reaches_home(self) -> None:
        barrier = function_body(self.android, "_BlueStacks5AcceptanceStopBeforeHomeBarrier")
        for required in (
            "RunEventLogAcceptancePreHomeReady($sReadyDetail)",
            'AcceptanceStopBeforeHomeEnvironmentState("1", $sToken, $sBindingReason)',
            "AcceptanceStopBeforeHomeBindingValid($sMode, $sRunRequestId, $sSessionId",
            "RunControlCheckpoint()",
            "AcceptanceStopBeforeHomeGenerationMatches(",
            "RunControlAcceptedStopRequestId($sRunRequestId)",
            "RunEventLogAcceptancePreHomeStopped($sStoppedDetail)",
            "$ACCEPTANCE_STOP_BEFORE_HOME_TIMEOUT_MS",
            "timed out without an exact generation-bound Stop; Home recognition remains blocked",
            "Return False",
        ):
            self.assertIn(required, barrier)
        for forbidden in (
            "OpenHome",
            "checkMainScreen",
            "Click(",
            "NoPremiumPointClick",
            "AndroidAdbSendShellCommand",
            "Attack",
            "Train",
            "Donate",
            "Gem",
            "RunControlBeginStart",
        ):
            self.assertNotIn(forbidden, barrier)
        self.assertNotIn("Return True", barrier)

    def test_barrier_receipt_contains_exact_current_run_and_runtime_identity(self) -> None:
        detail = function_body(self.android, "_BlueStacks5AcceptanceBarrierDetail")
        for field in (
            "schema=",
            ";state=",
            ";runtime_sha256=",
            ";acceptance_token=",
            ";run_request_id=",
            ";session_id=",
            ";plan_revision=",
            ";plan_token=",
            ";profile=",
            ";emulator=BlueStacks5;instance=Pie64",
            ";adb_device=",
            ";adb_executable_sha256=",
            ";adb_pid=",
            ";adb_created=",
            ";player_pid=",
            ";player_created=",
            ";stop_request_id=",
        ):
            self.assertIn(field, detail)

    def test_stop_accessor_rejects_stale_or_unaccepted_stop(self) -> None:
        stop = function_body(self.bridge, "RunControlAcceptedStopRequestId")
        for required in (
            "$g_bRunControlStopRequested",
            "_RunControlCurrentStartGeneration(True) <> $sExpectedStartRequestId",
            '$g_sRunControlLastCommand <> "stop"',
            '$g_sRunControlLastOutcome <> "accepted"',
            '"^[A-Za-z0-9._-]{1,80}$"',
        ):
            self.assertIn(required, stop)

        consume = function_body(self.bridge, "_RunControlConsumeCommand")
        stop_case = consume.split('Case "stop"', 1)[1].split('Case "pause"', 1)[0]
        self.assertLess(stop_case.index("_RunControlCurrentStartGeneration(True)"), stop_case.index("$g_bRunControlStopRequested = True"))
        self.assertIn("$sCurrentStartRequestId <> $sExpectedStartRequestId", stop_case)

    def test_event_contract_and_schema_include_barrier_receipts(self) -> None:
        event_types = self.event_schema["properties"]["type"]["enum"]
        for event_type, helper in (
            ("acceptance.pre-home.ready", "RunEventLogAcceptancePreHomeReady"),
            ("acceptance.pre-home.stopped", "RunEventLogAcceptancePreHomeStopped"),
            ("acceptance.pre-home.failed", "RunEventLogAcceptancePreHomeFailed"),
        ):
            self.assertIn(event_type, event_types)
            self.assertIn(f'"{event_type}"', self.event_contract)
            self.assertIn(f"Func {helper}(", self.events)


if __name__ == "__main__":
    unittest.main()
