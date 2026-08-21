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


class GameLaunchOnlyControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.action = source("COCBot/MBR GUI Action.au3")
        cls.android = source("COCBot/functions/Android/AndroidBluestacks5.au3")
        cls.bridge = source("COCBot/functions/Run/RunControlBridge.au3")
        cls.events = source("COCBot/functions/Run/RunEventLog.au3")
        cls.event_schema = json.loads(source("config/run-event.schema.json"))
        cls.actuators = json.loads(source("config/actuator-registry.json"))
        cls.html = source("ui/planner.html")
        cls.javascript = source("ui/planner.js")

    def test_launch_action_branches_before_plan_and_managed_engine_work(self) -> None:
        start = function_body(self.action, "BotStart")
        branch = "RunControlGameLaunchRequested()"
        self.assertLess(start.index(branch), start.index("RunExecutionPrepareStart("))
        self.assertLess(start.index(branch), start.index("MBRFuncProbeEngine("))

        launch = function_body(self.action, "_BotLaunchGameOnly")
        self.assertIn("LaunchBlueStacks5CoCOnly", launch)
        self.assertIn("RunControlStopRequested()", launch)
        for forbidden in (
            "RunExecution",
            "MBRFunc",
            "ForumAuthentication",
            "SaveConfig",
            "readConfig",
            "applyConfig",
            "Initiate",
            "runBot",
            "BotStop",
            "btnStop",
        ):
            self.assertNotIn(forbidden, launch)

    def test_adapter_allows_only_exact_instance_start_activity_and_passive_game_ready_proof(self) -> None:
        adapter = function_body(self.android, "LaunchBlueStacks5CoCOnly")
        for required in (
            '$g_sAndroidEmulator <> "BlueStacks5"',
            "GetAndroidProgramParameter()",
            "LaunchAndroid(",
            "ConnectAndroidAdb(False, 3000)",
            "WaitForAndroidBootCompleted(",
            'AndroidAdbSendShellCommand("am start -n "',
            "GetAndroidProcessPID(Default, False)",
            "OpenHomeCollectorsProveHome()",
            "OpenHomeDailyRewardOverlayReady()",
            "OpenHomeDailyRewardClaimedOverlayReady()",
            "RunControlStopRequested()",
        ):
            self.assertIn(required, adapter)
        self.assertEqual(adapter.count('AndroidAdbSendShellCommand("am start -n "'), 1)
        for forbidden in (
            "RestartAndroidCoC",
            "OpenAndroid(",
            "CloseAndroid",
            "RebootAndroid",
            "AndroidHomeButton",
            "ZoomOut",
            "checkObstacles",
            "CheckObstacles",
            "Click(",
            "GemClick",
            "PushSharedPrefs",
            "btnStop",
            "train",
            "Donate",
            "Attack",
        ):
            self.assertNotIn(forbidden, adapter)

    def test_native_bridge_owns_launch_request_and_returns_idle(self) -> None:
        consume = function_body(self.bridge, "_RunControlConsumeCommand")
        case = consume.split('Case "launch-game"', 1)[1].split('Case "stop"', 1)[0]
        for required in (
            "$g_bRunControlGameLaunchRequested = True",
            "$g_sRunControlPendingStartRequestId = $sRequestId",
            "$g_iBotAction = $eBotStart",
            '"accepted"',
        ):
            self.assertIn(required, case)

        outcome = function_body(self.bridge, "RunControlReportGameLaunchOutcome")
        self.assertIn('$bPassed ? "passed" : "failed"', outcome)
        self.assertIn("$g_bRunControlGameLaunchRequested = False", outcome)
        self.assertIn("$g_bRunControlStopRequested = False", outcome)
        self.assertIn("$g_bRunState = False", outcome)
        self.assertIn("$g_iBotAction = $eBotNoAction", outcome)
        self.assertNotIn("$eBotStop", outcome)
        self.assertLess(outcome.index("$g_iBotAction = $eBotNoAction"), outcome.index("RunControlWriteStatus(True)"))

    def test_loopback_queues_launch_even_when_managed_engine_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            command = Path(folder) / "control-command.json"
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(
                    planner_ui,
                    "control_status",
                    return_value={"connected": True, "engine_available": False, "state": "idle"},
                ),
            ):
                payload, status = planner_ui.queue_control_command("launch-game")

            self.assertEqual(202, status)
            self.assertTrue(payload["ok"])
            self.assertEqual("launch-game", payload["action"])
            self.assertEqual("launch-game", json.loads(command.read_text(encoding="utf-8"))["action"])

    def test_stop_replaces_an_unconsumed_launch_request(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            command = Path(folder) / "control-command.json"
            planner_ui.write_json_atomic(
                {"schema_version": 1, "request_id": "pending-launch", "action": "launch-game"},
                command,
            )
            with (
                mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command),
                mock.patch.object(planner_ui, "control_status", return_value={"connected": True, "state": "idle"}),
            ):
                payload, status = planner_ui.queue_control_command("stop", "pending-launch")

            self.assertEqual(202, status)
            self.assertTrue(payload["native_command_queued"])
            self.assertEqual("stop", json.loads(command.read_text(encoding="utf-8"))["action"])

    def test_browser_exposes_launch_only_and_retains_stop_during_stale_heartbeat(self) -> None:
        self.assertIn('id="controlGameLaunch"', self.html)
        self.assertIn("Return idle after passive game-ready proof", self.html)
        self.assertIn("recognizes Home or a verified Daily Reward startup overlay", self.html)
        self.assertIn("never clicks it", self.html)
        self.assertIn("$('controlGameLaunch').onclick = () => sendControl('launch-game')", self.javascript)
        self.assertIn("['start', 'check-engine', 'launch-game'].includes(CONTROL_PENDING?.action)", self.javascript)
        self.assertIn("(!connected && !managedInitCanBeStopped)", self.javascript)
        self.assertIn("expected_start_request_id: previousPending.request_id", self.javascript)

    def test_launch_receipts_are_schema_bound_and_capability_owned(self) -> None:
        event_types = self.event_schema["properties"]["type"]["enum"]
        for event_type in (
            "emulator.launch.started",
            "emulator.launch.passed",
            "emulator.launch.cancelled",
            "emulator.launch.failed",
        ):
            self.assertIn(event_type, event_types)
            self.assertIn(f'RunEventLogWrite("{event_type}"', self.events)

        mapping = next(item for item in self.actuators["mappings"] if item["id"] == "infra.bot-start")
        self.assertIn("emulator.bluestacks5", mapping["capability_ids"])


if __name__ == "__main__":
    unittest.main()
