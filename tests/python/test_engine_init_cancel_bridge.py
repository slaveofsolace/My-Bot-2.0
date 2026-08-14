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
                payload, status = planner_ui.queue_control_command("stop")

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
                payload, status = planner_ui.queue_control_command("stop")

            self.assertEqual(status, 409)
            self.assertFalse(payload["ok"])
            self.assertFalse(command.exists())
            self.assertFalse(cancel.exists())

    def test_pending_start_is_replaced_so_a_replacement_backend_cannot_replay_it(self):
        with tempfile.TemporaryDirectory() as folder:
            command, cancel, receipt = self._paths(folder)
            self._receipt(receipt)
            original = {"schema_version": 1, "request_id": "pending-start", "action": "start"}
            planner_ui.write_json_atomic(original, command)
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "ENGINE_INIT_CANCEL_PATH", cancel),
                mock.patch.object(planner_ui, "ENGINE_INIT_RECEIPT_PATH", receipt),
                mock.patch.object(planner_ui, "control_status", return_value={"connected": False}),
            ):
                payload, status = planner_ui.queue_control_command("stop")

            self.assertEqual(status, 202)
            self.assertTrue(payload["native_command_queued"])
            self.assertEqual(payload["supervisor_cancel_status"], "queued")
            replacement = json.loads(command.read_text(encoding="utf-8"))
            self.assertEqual(replacement["action"], "stop")
            self.assertNotEqual(replacement["request_id"], original["request_id"])
            self.assertTrue(cancel.exists())

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
                payload, status = planner_ui.queue_control_command("stop")

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
                payload, status = planner_ui.queue_control_command("stop")

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

    def test_native_request_id_accessor_is_active_accepted_start_only(self):
        source = (ROOT / "COCBot/functions/Run/RunControlBridge.au3").read_text(encoding="utf-8-sig")
        accessor = source.split("Func RunControlCurrentCommandId()", 1)[1].split("EndFunc", 1)[0]
        self.assertIn("If Not $g_bRunControlStartInProgress Then Return", accessor)
        self.assertIn('$g_sRunControlLastCommand <> "start"', accessor)
        self.assertIn('$g_sRunControlLastOutcome <> "accepted"', accessor)


if __name__ == "__main__":
    unittest.main()
