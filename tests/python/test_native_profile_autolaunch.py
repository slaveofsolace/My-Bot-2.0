import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import planner_ui  # noqa: E402


class NativeProfileAutoLaunchTests(unittest.TestCase):
    def test_absent_plan_is_explicit_native_profile_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            plan_path = Path(folder) / "run-plan.local.json"
            with mock.patch.object(planner_ui, "PLAN_PATH", plan_path):
                self.assertEqual(planner_ui.plan_status()["mode"], "native-profile")
                self.assertFalse(planner_ui.plan_status()["exists"])

    def test_switch_backs_up_applied_plan_atomically_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            plan_path = Path(folder) / "run-plan.local.json"
            original = json.dumps({"run.strategy": "home.collectors"}, indent=2).encode("utf-8")
            plan_path.write_bytes(original)
            with mock.patch.object(planner_ui, "PLAN_PATH", plan_path), \
                    mock.patch.object(planner_ui, "control_status", return_value={"state": "idle"}):
                payload, code = planner_ui.activate_native_profile_mode()
                self.assertEqual(code, 200)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["mode"], "native-profile")
                self.assertFalse(plan_path.exists())
                backups = list(Path(folder).glob("run-plan.local.backup-*.json"))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_bytes(), original)

                second, second_code = planner_ui.activate_native_profile_mode()
                self.assertEqual(second_code, 200)
                self.assertTrue(second["ok"])
                self.assertIsNone(second["backup"])
                self.assertEqual(list(Path(folder).glob("run-plan.local.backup-*.json")), backups)

    def test_web_start_binds_the_server_observed_mode_into_the_native_command(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan_path = root / "run-plan.local.json"
            command_path = root / "control-command.local.json"
            native_status = {"connected": True, "state": "idle", "engine_available": True}
            with mock.patch.object(planner_ui, "PLAN_PATH", plan_path), \
                    mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command_path), \
                    mock.patch.object(planner_ui, "control_status", return_value=native_status):
                payload, code = planner_ui.queue_control_command("start")
                self.assertEqual(code, 202)
                self.assertTrue(payload["accepted"])
                self.assertEqual(json.loads(command_path.read_text(encoding="utf-8"))["run_mode"], "native-profile")

                command_path.unlink()
                plan_path.write_text(json.dumps({"run.strategy": "home.collectors"}), encoding="utf-8")
                payload, code = planner_ui.queue_control_command("start")
                self.assertEqual(code, 202)
                self.assertEqual(json.loads(command_path.read_text(encoding="utf-8"))["run_mode"], "planned")

    def test_busy_or_unreadable_plan_is_left_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            plan_path = Path(folder) / "run-plan.local.json"
            plan_path.write_text('{"run.strategy":"home.collectors"}', encoding="utf-8")
            with mock.patch.object(planner_ui, "PLAN_PATH", plan_path), \
                    mock.patch.object(planner_ui, "control_status", return_value={"state": "running"}):
                payload, code = planner_ui.activate_native_profile_mode()
            self.assertEqual(code, 409)
            self.assertFalse(payload["ok"])
            self.assertTrue(plan_path.exists())

            plan_path.write_text("not-json", encoding="utf-8")
            with mock.patch.object(planner_ui, "PLAN_PATH", plan_path), \
                    mock.patch.object(planner_ui, "control_status", return_value={"state": "idle"}):
                payload, code = planner_ui.activate_native_profile_mode()
            self.assertEqual(code, 409)
            self.assertFalse(payload["ok"])
            self.assertEqual(plan_path.read_text(encoding="utf-8"), "not-json")

    def test_ui_exposes_native_mode_without_weakening_home_route_attachment_gate(self):
        html = (ROOT / "ui" / "planner.html").read_text(encoding="utf-8")
        javascript = (ROOT / "ui" / "planner.js").read_text(encoding="utf-8")
        server = (ROOT / "tools" / "planner_ui.py").read_text(encoding="utf-8")
        action = (ROOT / "COCBot" / "MBR GUI Action.au3").read_text(encoding="utf-8-sig")

        self.assertIn('id="controlNativeMode"', html)
        self.assertIn("NATIVE_PROFILE_MODE", javascript)
        self.assertIn("fetch('/api/plan/native'", javascript)
        self.assertIn("Full profile automation active", javascript)
        self.assertIn("every enabled native profile setting", javascript)
        self.assertIn('"/api/plan/native"', server)
        native_mode = server[
            server.index("def activate_native_profile_mode("):
            server.index("def displayed_path(", server.index("def activate_native_profile_mode("))
        ]
        self.assertIn("os.replace(PLAN_PATH, backup)", native_mode)
        self.assertNotIn("PLAN_PATH.unlink", native_mode)

        bot_start = action[action.index("Func BotStart("):action.index("EndFunc", action.index("Func BotStart("))]
        self.assertIn("OpenAndroid(False)", bot_start)
        self.assertLess(bot_start.index("RunExecutionPrepareStart("), bot_start.index("OpenAndroid(False)"))
        exact_gate = action[
            action.index("Func _BotOpenHomeRequireExactBlueStacks("):
            action.index("EndFunc", action.index("Func _BotOpenHomeRequireExactBlueStacks("))
        ]
        self.assertNotIn("OpenAndroid", exact_gate)

    def test_native_process_uses_explicit_start_mode_instead_of_a_stale_cached_plan(self):
        bridge = (ROOT / "COCBot" / "functions" / "Run" / "RunControlBridge.au3").read_text(
            encoding="utf-8-sig"
        )
        execution = (ROOT / "COCBot" / "functions" / "Run" / "RunExecution.au3").read_text(
            encoding="utf-8-sig"
        )
        server = (ROOT / "tools" / "planner_ui.py").read_text(encoding="utf-8")
        self.assertIn('command["run_mode"] = run_mode', server)
        self.assertIn('Start command is missing a valid run_mode', bridge)
        self.assertIn('$g_sRunControlPendingStartMode = $sRunMode', bridge)
        self.assertIn('Func RunControlCurrentStartMode()', bridge)
        prepare = execution[
            execution.index("Func RunExecutionPrepareStart("):
            execution.index("EndFunc", execution.index("Func RunExecutionPrepareStart("))
        ]
        native_branch = prepare.index('$sRequestedMode = "native-profile"')
        stale_fallback = prepare.index('IsObj($g_oRunPlannerIntent)')
        self.assertLess(native_branch, stale_fallback)
        self.assertIn('$sRequestedMode = "" And IsObj($g_oRunPlannerIntent)', prepare)
        self.assertIn('selected planned mode, but the applied plan is missing', prepare)

    def test_one_shot_terminal_state_and_pause_latch_are_truthful(self):
        javascript = (ROOT / "ui" / "planner.js").read_text(encoding="utf-8")
        bridge = (ROOT / "COCBot" / "functions" / "Run" / "RunControlBridge.au3").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("new Set(['completed', 'passed'", javascript)
        self.assertNotIn("new Set(['started', 'passed'", javascript)
        self.assertIn("outcome === 'started' && CONTROL_PENDING.action === 'start'", javascript)
        self.assertIn("CONTROL_STARTED = { request_id: CONTROL_PENDING.request_id }", javascript)
        one_shot = bridge[
            bridge.index("Func RunControlReportOneShotOutcome("):
            bridge.index("EndFunc", bridge.index("Func RunControlReportOneShotOutcome("))
        ]
        begin = bridge[
            bridge.index("Func RunControlBeginStart("):
            bridge.index("EndFunc", bridge.index("Func RunControlBeginStart("))
        ]
        self.assertIn("$g_bBotPaused = False", one_shot)
        self.assertIn("$g_bBotPaused = False", begin)

    def test_every_terminal_home_route_auto_launches_from_start(self):
        action = (ROOT / "COCBot" / "MBR GUI Action.au3").read_text(encoding="utf-8-sig")
        ensure = action[
            action.index("Func _BotOpenHomeEnsureExactBlueStacks("):
            action.index("EndFunc", action.index("Func _BotOpenHomeEnsureExactBlueStacks("))
        ]
        self.assertIn("_BotOpenHomeRequireExactBlueStacks($sReason)", ensure)
        self.assertIn("OpenHomeCollectorsProveHome()", ensure)
        self.assertIn("OpenHomeDailyRewardOverlayReady()", ensure)
        self.assertIn("OpenHomeDailyRewardClaimedOverlayReady()", ensure)
        self.assertIn('ElseIf $sReason <> "The exact BlueStacks 5 instance is not already running" Then', ensure)
        self.assertIn("LaunchBlueStacks5CoCOnly($sLaunchReason)", ensure)
        self.assertIn("RunControlStopRequested()", ensure)
        self.assertLess(ensure.index("RunControlStopRequested()"), ensure.index("LaunchBlueStacks5CoCOnly($sLaunchReason)"))
        self.assertIn("RunEventLogGameLaunchStarted()", ensure)
        self.assertIn("RunEventLogGameLaunchPassed($sReason)", ensure)
        self.assertIn("RunEventLogGameLaunchFailed($sReason)", ensure)
        self.assertIn("RunEventLogGameLaunchCancelled($sReason)", ensure)

        for function_name in (
            "_BotStartOpenHomeCollectors",
            "_BotStartOpenHomeLootCart",
            "_BotStartOpenDailyReward",
            "_BotStartOpenHomeTreasury",
            "_BotStartOpenClanRequest",
        ):
            start = action.index(f"Func {function_name}(")
            body = action[start:action.index("EndFunc", start)]
            self.assertIn("RunExecutionApplyPrepared($sStartError)", body, function_name)
            self.assertIn("_BotOpenHomeEnsureExactBlueStacks($sAttachmentError)", body, function_name)
            self.assertLess(
                body.index("RunExecutionApplyPrepared($sStartError)"),
                body.index("_BotOpenHomeEnsureExactBlueStacks($sAttachmentError)"),
                function_name,
            )

    def test_full_profile_start_applies_and_restores_narrow_no_gem_overlay(self):
        execution = (ROOT / "COCBot" / "functions" / "Run" / "RunExecution.au3").read_text(
            encoding="utf-8-sig"
        )
        action = (ROOT / "COCBot" / "MBR GUI Action.au3").read_text(encoding="utf-8-sig")
        javascript = (ROOT / "ui" / "planner.js").read_text(encoding="utf-8")

        prepare = execution[
            execution.index("Func RunExecutionPrepareStart("):
            execution.index("EndFunc", execution.index("Func RunExecutionPrepareStart("))
        ]
        self.assertIn("$g_bRunExecutionFullProfileSafetyPending = True", prepare)

        apply_safety = execution[
            execution.index("Func _RunExecutionApplyFullProfileSafety("):
            execution.index("EndFunc", execution.index("Func _RunExecutionApplyFullProfileSafety("))
        ]
        selectors = (
            "Barracks",
            "SpellFactory",
            "Workshop",
            "BarbarianKing",
            "ArcherQueen",
            "MinionPrince",
            "Warden",
            "Champion",
            "Everything",
        )
        self.assertIn("_RunExecutionCaptureProfileSnapshot()", apply_safety)
        for selector in selectors:
            self.assertIn(f"$g_iCmbBoost{selector} = 0", apply_safety)
            self.assertIn(f"$g_iRunExecutionSnapshotCmbBoost{selector}", execution)
        self.assertIn("$g_bChkSellRewards = False", apply_safety)
        self.assertNotIn("$g_bChkCollect = False", apply_safety)
        self.assertNotIn("$g_bChkDonate = False", apply_safety)
        self.assertNotIn("$g_bAutoUpgradeEnabled = False", apply_safety)

        apply_prepared = execution[
            execution.index("Func RunExecutionApplyPrepared("):
            execution.index("EndFunc", execution.index("Func RunExecutionApplyPrepared("))
        ]
        self.assertIn("Return _RunExecutionApplyFullProfileSafety($sError)", apply_prepared)

        restore = execution[
            execution.index("Func _RunExecutionRestoreProfile("):
            execution.index("EndFunc", execution.index("Func _RunExecutionRestoreProfile("))
        ]
        for selector in selectors:
            self.assertIn(
                f"$g_iCmbBoost{selector} = $g_iRunExecutionSnapshotCmbBoost{selector}",
                restore,
            )

        complete = execution[
            execution.index("Func RunExecutionComplete("):
            execution.index("EndFunc", execution.index("Func RunExecutionComplete("))
        ]
        self.assertIn(
            "If Not $g_bRunExecutionPrepared Then Return _RunExecutionCompleteFullProfile()",
            complete,
        )
        full_profile_complete = execution[
            execution.index("Func _RunExecutionCompleteFullProfile("):
            execution.index("EndFunc", execution.index("Func _RunExecutionCompleteFullProfile("))
        ]
        self.assertIn("_RunExecutionRestoreProfile()", full_profile_complete)

        bot_start = action[action.index("Func BotStart("):action.index("EndFunc", action.index("Func BotStart("))]
        self.assertLess(bot_start.index("SaveConfig()"), bot_start.index("RunExecutionApplyPrepared($sStartError)"))
        self.assertIn("except gem boosts and reward-to-gem conversion", javascript)


if __name__ == "__main__":
    unittest.main()
