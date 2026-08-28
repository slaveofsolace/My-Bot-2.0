from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import planner_ui  # noqa: E402


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def function_body(document: str, name: str) -> str:
    start = document.index(f"Func {name}(")
    return document[start : document.index("EndFunc", start)]


class EngineInitOnlyControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.action = source("COCBot/MBR GUI Action.au3")
        cls.bridge = source("COCBot/functions/Run/RunControlBridge.au3")
        cls.mbr = source("COCBot/functions/Other/MBRFunc.au3")
        cls.events = source("COCBot/functions/Run/RunEventLog.au3")
        cls.event_schema = json.loads(source("config/run-event.schema.json"))
        cls.capabilities = json.loads(source("config/current-client-capabilities.json"))
        cls.html = source("ui/planner.html")
        cls.javascript = source("ui/planner.js")

    def test_engine_check_branches_before_plan_and_never_reaches_game_work(self) -> None:
        start = function_body(self.action, "BotStart")
        self.assertLess(start.index("RunControlEngineCheckRequested()"), start.index("RunExecutionPrepareStart("))

        check = function_body(self.action, "_BotCheckManagedEngine")
        finish = function_body(self.action, "_BotEngineCheckFinish")
        self.assertLess(check.index("MBRFuncProbeEngine("), check.index("MBRFuncInitialize(False)"))
        self.assertGreaterEqual(check.count("RunControlStopRequested()"), 2)
        self.assertIn("RunControlReportEngineCheckOutcome", finish)
        for forbidden in (
            "RunExecutionPrepareStart",
            "ForumAuthentication",
            "ResumeAndroid",
            "AndroidBotStartEvent",
            "RunExecutionBegin",
            "BotStop",
            "btnStop",
            "MBRFunc(False)",
            "Click(",
            "PureClick",
            "ADB",
            "ZoomOut",
            "SaveConfig",
            "readConfig",
            "applyConfig",
        ):
            self.assertNotIn(forbidden, check)
        self.assertIn("no emulator or game action was attempted", check)

        initialize = function_body(self.mbr, "MBRFuncInitialize")
        self.assertIn("$bDiscoverAndroid", initialize)
        self.assertIn("If $bDiscoverAndroid Then", initialize)
        self.assertIn("setAndroidPID(0, True)", initialize)
        self.assertLess(
            initialize.index('_MBRFuncPublishEngineReceipt("initialized")'),
            initialize.index("If Not $bDiscoverAndroid Then $g_bLibMyBotInitialized = False"),
        )
        detached = initialize.split("Else", 1)[1].split("EndIf", 1)[0]
        for forbidden in ("GetAndroidPid", "WinGetAndroidHandle", "InitAndroid", "WinMove", "HideAndroidWindow"):
            self.assertNotIn(forbidden, detached)

        android_binding = function_body(self.mbr, "setAndroidPID")
        engine_only_gate = android_binding.index("$bEngineOnlyProbe")
        engine_only_record = android_binding.index('_MBRFuncRecordAndroidBinding("engine-only", 0)', engine_only_gate)
        engine_only_skip = android_binding.index("Managed Android PID export skipped during engine-only check", engine_only_record)
        managed_call = android_binding.index('DllCall($g_hLibMyBot, "str", "setAndroidPID"')
        self.assertLess(engine_only_gate, engine_only_record)
        self.assertLess(engine_only_record, engine_only_skip)
        self.assertLess(engine_only_skip, managed_call)

    def test_native_bridge_owns_check_request_and_returns_idle_terminal_status(self) -> None:
        accessor = function_body(self.bridge, "RunControlCurrentCommandId")
        self.assertIn('$g_sRunControlLastCommand <> "check-engine"', accessor)
        consume = function_body(self.bridge, "_RunControlConsumeCommand")
        case = consume.split('Case "check-engine"', 1)[1].split('Case "stop"', 1)[0]
        for required in (
            "$g_bRunControlEngineCheckRequested = True",
            "$g_sRunControlPendingStartRequestId = $sRequestId",
            "$g_iBotAction = $eBotStart",
            '"accepted"',
        ):
            self.assertIn(required, case)
        outcome = function_body(self.bridge, "RunControlReportEngineCheckOutcome")
        self.assertIn('$bPassed ? "passed" : "failed"', outcome)
        self.assertIn("$g_bRunControlEngineCheckRequested = False", outcome)
        self.assertIn("$g_bRunControlStopRequested = False", outcome)
        self.assertIn('$g_sRunControlActiveStartPlanRevision = ""', outcome)
        self.assertIn('$g_sRunControlPendingStartPlanRevision = ""', outcome)
        self.assertIn('$g_sRunControlActiveStartPlanToken = ""', outcome)
        self.assertIn('$g_sRunControlPendingStartPlanToken = ""', outcome)
        self.assertIn("$g_bRunState = False", outcome)
        self.assertIn("$g_iBotAction = $eBotNoAction", outcome)
        self.assertNotIn("$eBotStop", outcome)
        self.assertIn('$g_sRunControlLastOutcome = "stopped"', outcome)
        self.assertIn("RunControlWriteStatus(True)", outcome)
        self.assertLess(outcome.index("$g_iBotAction = $eBotNoAction"), outcome.index("RunControlWriteStatus(True)"))
        self.assertIn("resume|check-engine|launch-game", self.bridge)

        finish = function_body(self.action, "_BotEngineCheckFinish")
        self.assertLess(finish.index("RunControlReportEngineCheckOutcome"), finish.index("RunEventLogEngineCheckPassed"))
        self.assertIn("RunEventLogEngineCheckCancelled", finish)

    def test_loopback_service_queues_check_without_a_saved_plan(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            command = Path(folder) / "control-command.json"
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(
                    planner_ui,
                    "control_status",
                    return_value={"connected": True, "engine_available": True, "state": "idle"},
                ),
            ):
                payload, status = planner_ui.queue_control_command("check-engine")

            self.assertEqual(status, 202)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["action"], "check-engine")
            self.assertEqual(json.loads(command.read_text(encoding="utf-8"))["action"], "check-engine")

    def test_loopback_service_rejects_check_when_engine_is_sticky_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            command = Path(folder) / "control-command.json"
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(
                    planner_ui,
                    "control_status",
                    return_value={"connected": True, "engine_available": False, "message": "sticky failure"},
                ),
            ):
                payload, status = planner_ui.queue_control_command("check-engine")

            self.assertEqual(status, 409)
            self.assertEqual(payload["problems"], ["sticky failure"])
            self.assertFalse(command.exists())

    def test_immediate_stop_replaces_unconsumed_engine_check_without_a_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            command = root / "control-command.json"
            cancel = root / "engine-init-cancel.json"
            receipt = root / "engine-init-owner.json"
            planner_ui.write_json_atomic(
                {"schema_version": 1, "request_id": "pending-check", "action": "check-engine"},
                command,
            )
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                mock.patch.object(planner_ui, "control_status", return_value={"connected": True, "state": "idle"}),
            ):
                payload, status = planner_ui.queue_control_command("stop")

            self.assertEqual(status, 202)
            self.assertTrue(payload["native_command_queued"])
            self.assertEqual(payload["supervisor_cancel_status"], "not-active")
            self.assertEqual(json.loads(command.read_text(encoding="utf-8"))["action"], "stop")
            self.assertFalse(cancel.exists())

    def test_stop_rechecks_for_a_consumed_engine_check_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            command = root / "control-command.json"
            cancel = root / "engine-init-cancel.json"
            context = {"token": "a" * 64, "start_request_id": "accepted-check"}
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                mock.patch.object(
                    planner_ui,
                    "control_status",
                    return_value={"connected": True, "state": "starting"},
                ),
                mock.patch.object(planner_ui, "engine_init_cancel_context", return_value=None),
                mock.patch.object(planner_ui, "wait_for_engine_init_cancel_context", return_value=context) as wait,
            ):
                payload, status = planner_ui.queue_control_command("stop", "accepted-check")

            self.assertEqual(status, 202)
            wait.assert_called_once_with("accepted-check")
            self.assertEqual(payload["supervisor_cancel_status"], "queued")
            cancellation = json.loads(cancel.read_text(encoding="utf-8"))
            self.assertEqual(cancellation["expected_start_request_id"], "accepted-check")
            self.assertEqual(cancellation["token"], "a" * 64)

    def test_receipt_recheck_is_bounded_and_request_bound(self) -> None:
        context = {"token": "c" * 64, "start_request_id": "accepted-check"}
        with (
            mock.patch.object(planner_ui, "engine_init_cancel_context", side_effect=[None, context]),
            mock.patch.object(planner_ui.time, "monotonic", side_effect=[10.0, 10.0]),
            mock.patch.object(planner_ui.time, "sleep") as sleep,
        ):
            result = planner_ui.wait_for_engine_init_cancel_context("accepted-check")
        self.assertEqual(result, context)
        sleep.assert_called_once_with(planner_ui.ENGINE_INIT_CANCEL_CONTEXT_POLL_SECONDS)

        with mock.patch.object(planner_ui, "engine_init_cancel_context", return_value=context):
            self.assertIsNone(planner_ui.wait_for_engine_init_cancel_context("foreign-check"))

    def test_stale_heartbeat_surfaces_active_supervisor_cancellation(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            status_path = Path(folder) / "control-status.json"
            planner_ui.write_json_atomic({"state": "starting", "window_attached": False}, status_path)
            with (
                mock.patch.object(planner_ui, "CONTROL_STATUS_PATH", status_path),
                mock.patch.object(planner_ui, "CONTROL_STATUS_BUSY_MAX_AGE_SECONDS", -1.0),
                mock.patch.object(
                    planner_ui,
                    "engine_init_cancel_context",
                    return_value={"token": "b" * 64, "start_request_id": "accepted-check"},
                ),
            ):
                status = planner_ui.control_status()

            self.assertFalse(status["connected"])
            self.assertTrue(status["engine_init_cancellable"])

    def test_browser_exposes_check_separately_from_plan_start_and_keeps_stop_available(self) -> None:
        self.assertIn('id="controlEngineCheck"', self.html)
        self.assertIn("before emulator, ADB, or game work", self.html)
        self.assertIn("$('controlEngineCheck').onclick = () => sendControl('check-engine')", self.javascript)
        self.assertIn("['start', 'check-engine', 'launch-game'].includes(CONTROL_PENDING?.action)", self.javascript)
        self.assertIn("CONTROL.engine_init_cancellable === true", self.javascript)
        self.assertIn("(!connected && !managedInitCanBeStopped)", self.javascript)
        self.assertIn("if (CONTROL.engine_init_cancellable === true)", self.javascript)
        self.assertIn("expected_start_request_id: expectedStopRequestId", self.javascript)
        self.assertIn("action === 'start' &&", self.javascript)
        self.assertIn("CONTROL_TERMINAL_OUTCOMES = new Set(['completed', 'passed'", self.javascript)

    def test_diagnostic_events_are_schema_bound_and_truthful(self) -> None:
        event_types = self.event_schema["properties"]["type"]["enum"]
        for event_type in ("engine.check.started", "engine.check.passed", "engine.check.cancelled", "engine.check.failed"):
            self.assertIn(event_type, event_types)
            self.assertIn(f'RunEventLogWrite("{event_type}"', self.events)
        passed = function_body(self.events, "RunEventLogEngineCheckPassed")
        self.assertIn("without emulator or game input", passed)

    def test_engine_initialization_has_a_distinct_unproven_evidence_policy(self) -> None:
        capability_id = "orchestration.engine-initialization"
        entries = {item["id"]: item for item in self.capabilities["capabilities"]}
        self.assertEqual(entries[capability_id]["status"], "engine-added")
        self.assertEqual(entries[capability_id]["runtime_evidence"], "required")
        self.assertNotIn("fixture_status", entries[capability_id])
        policy = self.capabilities["runtime_evidence_policy"]["capabilities"][capability_id]
        self.assertEqual(
            policy["required_tests"],
            [{
                "test_type": "end-to-end",
                "required_checks": [
                    "check-engine.accepted",
                    "backend.identity-preserved",
                    "engine.initialized",
                    "idle.restored",
                    "supervisor.finalized",
                    "diagnostic-events.exact",
                    "game-input.absent",
                    "configuration.preserved",
                ],
            }],
        )


if __name__ == "__main__":
    unittest.main()
