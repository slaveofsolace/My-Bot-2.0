import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import planner_ui  # noqa: E402


class EngineInitCancelBridgeTest(unittest.TestCase):
    TOKEN = "a" * 64
    START_ID = "start.request-1"

    def _receipt(self, path: pathlib.Path, *, phase: str = "pool-entered", sequence: int = 2):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema": "engine-init-supervisor-v1",
                    "token": self.TOKEN,
                    "start_request_id": self.START_ID,
                    "phase": phase,
                    "sequence": sequence,
                }
            ),
            encoding="utf-8",
        )

    def _paths(self, folder: str):
        root = pathlib.Path(folder)
        return (
            root / "control-command.json",
            root / "engine-init-cancel.json",
            root / "user-data" / "engine-init-owner-v1.json",
        )

    def test_offline_stop_bypasses_the_blocked_backend_only_with_a_valid_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            command, cancel, receipt = self._paths(folder)
            self._receipt(receipt)
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                mock.patch.object(planner_ui, "control_status", return_value={"connected": False}),
            ):
                payload, status = planner_ui.queue_control_command("stop", self.START_ID)

            self.assertEqual(status, 202)
            self.assertTrue(payload["native_command_queued"])
            self.assertEqual(payload["supervisor_cancel_status"], "queued")
            self.assertEqual(json.loads(command.read_text(encoding="utf-8"))["action"], "stop")
            mirrored = json.loads(cancel.read_text(encoding="utf-8"))
            self.assertEqual(mirrored["expected_start_request_id"], self.START_ID)
            self.assertNotIn(self.TOKEN, json.dumps(payload))

    def test_offline_stop_without_owned_initialization_still_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            command, cancel, receipt = self._paths(folder)
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                mock.patch.object(planner_ui, "control_status", return_value={"connected": False}),
            ):
                payload, status = planner_ui.queue_control_command("stop", self.START_ID)

            self.assertEqual(status, 409)
            self.assertFalse(payload["ok"])
            self.assertFalse(command.exists())
            self.assertFalse(cancel.exists())

    def test_pending_start_is_replaced_so_a_replacement_backend_cannot_replay_it(self):
        with tempfile.TemporaryDirectory() as folder:
            command, cancel, receipt = self._paths(folder)
            self._receipt(receipt)
            original = {"schema_version": 1, "request_id": self.START_ID, "action": "start"}
            planner_ui.write_json_atomic(original, command)
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                mock.patch.object(planner_ui, "control_status", return_value={"connected": False}),
            ):
                payload, status = planner_ui.queue_control_command("stop", self.START_ID)

            self.assertEqual(status, 202)
            self.assertTrue(payload["native_command_queued"])
            self.assertEqual(payload["supervisor_cancel_status"], "queued")
            replacement = json.loads(command.read_text(encoding="utf-8"))
            self.assertEqual(replacement["action"], "stop")
            self.assertEqual(replacement["expected_start_request_id"], self.START_ID)
            self.assertNotEqual(replacement["request_id"], original["request_id"])
            self.assertTrue(cancel.exists())

    def test_stale_tab_cannot_cancel_a_newer_launcher_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            command, cancel, receipt = self._paths(folder)
            self._receipt(receipt)
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                mock.patch.object(planner_ui, "control_status", return_value={"connected": False}),
            ):
                payload, status = planner_ui.queue_control_command("stop", "older-start")

            self.assertEqual(status, 409)
            self.assertFalse(payload["ok"])
            self.assertIn("no longer active", payload["problems"][0])
            self.assertFalse(command.exists())
            self.assertFalse(cancel.exists())

    def test_matching_pending_start_is_the_only_generation_replaced_before_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            command, cancel, receipt = self._paths(folder)
            planner_ui.write_json_atomic(
                {"schema_version": 1, "request_id": self.START_ID, "action": "start"},
                command,
            )
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                mock.patch.object(
                    planner_ui,
                    "control_status",
                    return_value={"connected": True, "state": "starting"},
                ),
                mock.patch.object(planner_ui, "schedule_engine_init_cancel") as schedule,
            ):
                payload, status = planner_ui.queue_control_command("stop", self.START_ID)

            self.assertEqual(status, 202)
            self.assertTrue(payload["native_command_queued"])
            replacement = json.loads(command.read_text(encoding="utf-8"))
            self.assertEqual(replacement["action"], "stop")
            self.assertEqual(replacement["expected_start_request_id"], self.START_ID)
            schedule.assert_called_once()

    def test_status_run_generation_rejects_a_stale_stop_after_pause_or_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            command, cancel, receipt = self._paths(folder)
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                mock.patch.object(
                    planner_ui,
                    "control_status",
                    return_value={
                        "connected": True,
                        "state": "paused",
                        "last_command": "pause",
                        "last_outcome": "paused",
                        "run_request_id": self.START_ID,
                    },
                ),
            ):
                payload, status = planner_ui.queue_control_command("stop", "older-start")

            self.assertEqual(status, 409)
            self.assertFalse(payload["ok"])
            self.assertFalse(command.exists())
            self.assertFalse(cancel.exists())

    def test_stop_requires_the_browser_observed_start_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            command, cancel, receipt = self._paths(folder)
            status_document = {
                "connected": True,
                "state": "running",
                "run_request_id": self.START_ID,
            }
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                mock.patch.object(planner_ui, "control_status", return_value=status_document),
            ):
                payload, status = planner_ui.queue_control_command("stop")

            self.assertEqual(status, 400)
            self.assertFalse(payload["ok"])
            self.assertIn("requires the active Start generation", payload["problems"][0])
            self.assertFalse(command.exists())

    def test_matching_running_generation_is_queued_for_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            command, cancel, receipt = self._paths(folder)
            status_document = {
                "connected": True,
                "state": "running",
                "run_request_id": self.START_ID,
            }
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                mock.patch.object(planner_ui, "control_status", return_value=status_document),
            ):
                payload, status = planner_ui.queue_control_command("stop", self.START_ID)

            self.assertEqual(status, 202)
            self.assertTrue(payload["native_command_queued"])
            queued = json.loads(command.read_text(encoding="utf-8"))
            self.assertEqual(queued["expected_start_request_id"], self.START_ID)

    def test_pause_and_resume_require_the_exact_active_generation(self):
        for action, state in (("pause", "running"), ("resume", "paused")):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as folder:
                command, cancel, receipt = self._paths(folder)
                status_document = {
                    "connected": True,
                    "state": state,
                    "run_request_id": self.START_ID,
                }
                with (
                    mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                    mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                    mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                    mock.patch.object(planner_ui, "control_status", return_value=status_document),
                ):
                    missing, missing_status = planner_ui.queue_control_command(action)
                    stale, stale_status = planner_ui.queue_control_command(action, "older-start")
                    accepted, accepted_status = planner_ui.queue_control_command(action, self.START_ID)

                self.assertEqual(missing_status, 400)
                self.assertIn("requires the active Start generation", missing["problems"][0])
                self.assertEqual(stale_status, 409)
                self.assertIn("no longer active", stale["problems"][0])
                self.assertEqual(accepted_status, 202)
                self.assertTrue(accepted["accepted"])
                queued = json.loads(command.read_text(encoding="utf-8"))
                self.assertEqual(queued["action"], action)
                self.assertEqual(queued["expected_start_request_id"], self.START_ID)

    def test_conflicting_receipt_and_pending_start_generations_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            command, cancel, receipt = self._paths(folder)
            self._receipt(receipt)
            planner_ui.write_json_atomic(
                {"schema_version": 1, "request_id": "newer-start", "action": "start"},
                command,
            )
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                mock.patch.object(
                    planner_ui,
                    "control_status",
                    return_value={"connected": True, "state": "starting"},
                ),
            ):
                payload, status = planner_ui.queue_control_command("stop", self.START_ID)

            self.assertEqual(status, 409)
            self.assertFalse(payload["ok"])
            self.assertEqual(
                json.loads(command.read_text(encoding="utf-8"))["request_id"],
                "newer-start",
            )
            self.assertFalse(cancel.exists())

    def test_supervisor_cancel_remains_authoritative_when_native_stop_write_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            command, cancel, receipt = self._paths(folder)
            self._receipt(receipt)
            real_writer = planner_ui.write_json_atomic

            def selective_writer(document, destination):
                if destination == command:
                    raise OSError("injected native command failure")
                return real_writer(document, destination)

            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                mock.patch.object(planner_ui, "control_status", return_value={"connected": False}),
                mock.patch.object(planner_ui, "write_json_atomic", side_effect=selective_writer),
            ):
                payload, status = planner_ui.queue_control_command("stop", self.START_ID)

            self.assertEqual(status, 202)
            self.assertFalse(payload["native_command_queued"])
            self.assertEqual(payload["supervisor_cancel_status"], "queued")
            self.assertFalse(command.exists())
            self.assertTrue(cancel.exists())

    def test_cancel_write_failure_does_not_lie_about_an_already_durable_native_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            command, cancel, receipt = self._paths(folder)
            self._receipt(receipt)
            real_writer = planner_ui.write_json_atomic

            def selective_writer(document, destination):
                if destination == cancel:
                    raise OSError("injected cancel failure")
                return real_writer(document, destination)

            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                mock.patch.object(planner_ui, "control_status", return_value={"connected": True}),
                mock.patch.object(planner_ui, "write_json_atomic", side_effect=selective_writer),
            ):
                payload, status = planner_ui.queue_control_command("stop", self.START_ID)

            self.assertEqual(status, 202)
            self.assertTrue(payload["native_command_queued"])
            self.assertEqual(payload["supervisor_cancel_status"], "unavailable")
            self.assertEqual(json.loads(command.read_text(encoding="utf-8"))["action"], "stop")
            self.assertNotIn(self.TOKEN, json.dumps(payload))

    def test_receipt_reader_rejects_wrong_phase_sequence_oversize_and_reparse(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, receipt = self._paths(folder)
            self._receipt(receipt, phase="pool-entered", sequence=1)
            with mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt):
                self.assertIsNone(planner_ui.engine_init_cancel_context())

            receipt.write_bytes(b"{" + b" " * planner_ui.ENGINE_INIT_RECEIPT_MAX_BYTES + b"}")
            with mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt):
                self.assertIsNone(planner_ui.engine_init_cancel_context())

            self._receipt(receipt)
            with (
                mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                mock.patch.object(planner_ui, "_path_is_reparse", return_value=True),
            ):
                self.assertIsNone(planner_ui.engine_init_cancel_context())

    def test_native_request_id_accessor_is_active_accepted_initialization_only(self):
        source = (ROOT / "COCBot/functions/Run/RunControlBridge.au3").read_text(encoding="utf-8-sig")
        accessor = source.split("Func RunControlCurrentCommandId()", 1)[1].split("EndFunc", 1)[0]
        self.assertIn("If Not $g_bRunControlStartInProgress Then Return", accessor)
        self.assertIn('$g_sRunControlLastCommand <> "start"', accessor)
        self.assertIn('$g_sRunControlLastCommand <> "check-engine"', accessor)
        self.assertIn('$g_sRunControlLastOutcome <> "accepted"', accessor)

    def test_native_run_mutations_revalidate_the_exact_generation_before_mutation(self):
        source = (ROOT / "COCBot/functions/Run/RunControlBridge.au3").read_text(encoding="utf-8-sig")
        consume = source.split("Func _RunControlConsumeCommand()", 1)[1].split(
            "EndFunc   ;==>_RunControlConsumeCommand", 1
        )[0]
        stop_case = consume.split('Case "stop"', 1)[1].split('Case "pause"', 1)[0]
        pause_case = consume.split('Case "pause"', 1)[1].split('Case "resume"', 1)[0]
        resume_case = consume.split('Case "resume"', 1)[1].split('Case Else', 1)[0]
        begin = source.split("Func RunControlBeginStart()", 1)[1].split(
            "EndFunc   ;==>RunControlBeginStart", 1
        )[0]
        status = source.split("Func RunControlWriteStatus(", 1)[1].split(
            "EndFunc   ;==>RunControlWriteStatus", 1
        )[0]

        self.assertIn('$oCommand.Exists("expected_start_request_id")', consume)
        self.assertIn('$bGenerationAction = StringRegExp($sAction, "^(stop|pause|resume)$") = 1', consume)
        self.assertIn('" command is missing expected_start_request_id"', consume)
        self.assertIn('_RunControlCurrentStartGeneration(True)', stop_case)
        self.assertIn('$sCurrentStartRequestId <> $sExpectedStartRequestId', stop_case)
        self.assertIn("Start generation that is no longer active", stop_case)
        self.assertLess(
            stop_case.index("Start generation that is no longer active"),
            stop_case.index('$g_sRunControlPendingStartRequestId = ""'),
        )
        self.assertIn('_RunControlCurrentStartGeneration(False) <> $sExpectedStartRequestId', pause_case)
        self.assertIn("Pause command targets a Start generation that is no longer active", pause_case)
        self.assertLess(
            pause_case.index("Pause command targets a Start generation that is no longer active"),
            pause_case.index("$g_bBotPaused = True"),
        )
        self.assertIn('_RunControlCurrentStartGeneration(False) <> $sExpectedStartRequestId', resume_case)
        self.assertIn("Resume command targets a Start generation that is no longer active", resume_case)
        self.assertLess(
            resume_case.index("Resume command targets a Start generation that is no longer active"),
            resume_case.index("$g_bBotPaused = False"),
        )
        self.assertIn(
            "$g_sRunControlRunRequestId = $g_sRunControlActiveStartRequestId",
            begin,
        )
        self.assertIn('"run_request_id"', status)
        for terminal in (
            "RunControlReportEngineCheckOutcome",
            "RunControlReportGameLaunchOutcome",
            "RunControlReportOneShotOutcome",
            "RunControlReportStopComplete",
            "RunControlShutdown",
        ):
            body = source.split(f"Func {terminal}(", 1)[1].split(
                f"EndFunc   ;==>{terminal}", 1
            )[0]
            self.assertIn('$g_sRunControlRunRequestId = ""', body, terminal)


if __name__ == "__main__":
    unittest.main()
