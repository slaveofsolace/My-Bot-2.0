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


if __name__ == "__main__":
    unittest.main()
