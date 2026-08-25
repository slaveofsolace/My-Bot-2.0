import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import planner_ui  # noqa: E402


def valid_home_plan(**overrides) -> dict:
    plan = planner_ui.default_plan()
    plan.update(
        {
            "run.surface": "regular",
            "run.strategy": "home.collectors",
            "run.attack_script": "profile-current",
            "run.duration_minutes": 0,
            "run.max_battles": 0,
            "run.stop_on_star_bonus": False,
            "run.max_failures": 0,
            "run.heroes": [],
            "run.diagnostic_mode": True,
            "target.gold": 0,
            "target.elixir": 0,
            "target.dark_elixir": 0,
            "army.source": "recipe",
            "army.recipe_name": "",
            "army.recipe_digest": "",
            "army.max_queue_units": 0,
            "army.manage_training": False,
            "army.wait_for_full": False,
            "army.train_spells": False,
            "army.train_sieges": False,
            "search.min_gold": 0,
            "search.min_elixir": 0,
            "search.min_dark": 0,
            "search.max_seconds": 0,
            "search.town_hall_filter": "any",
            "donate.mode": "off",
            "donate.keep_army": True,
            "donate.max_per_run": 0,
            "donate.request_when_short": False,
            "events.clan_games": False,
            "events.clan_games_point_cap": 0,
            "events.laboratory": "off",
            "events.collect_resources": True,
            "events.collect_daily_reward": False,
            "events.collect_loot_cart": False,
            "events.collect_treasury": False,
            "upgrade.policy": "disabled",
            "account.queue": "",
            "notify.channel": "log-only",
            "runtime.emulator": "bluestacks5",
            "runtime.instance": "Pie64",
            "pacing.retry_attempts": 0,
        }
    )
    plan.update(overrides)
    return plan


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
                    mock.patch.object(
                        planner_ui,
                        "control_status",
                        return_value={"connected": True, "state": "idle", "recognition_available": True},
                    ):
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
            native_status = {
                "connected": True,
                "state": "idle",
                "engine_available": True,
                "recognition_available": True,
            }
            with mock.patch.object(planner_ui, "PLAN_PATH", plan_path), \
                    mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command_path), \
                    mock.patch.object(planner_ui, "control_status", return_value=native_status):
                payload, code = planner_ui.queue_control_command("start")
                self.assertEqual(code, 202)
                self.assertTrue(payload["accepted"])
                native_command = json.loads(command_path.read_text(encoding="utf-8"))
                self.assertEqual(native_command["run_mode"], "native-profile")
                self.assertEqual(native_command["plan_token"], planner_ui.PLAN_ABSENCE_TOKEN)

                command_path.unlink()
                plan_path.write_text(json.dumps(valid_home_plan()), encoding="utf-8")
                payload, code = planner_ui.queue_control_command("start")
                self.assertEqual(code, 202)
                planned_command = json.loads(command_path.read_text(encoding="utf-8"))
                self.assertEqual(planned_command["run_mode"], "planned")
                self.assertEqual(
                    planned_command["plan_token"],
                    f"sha256:{hashlib.sha256(plan_path.read_bytes()).hexdigest()}",
                )

    def test_web_start_refuses_native_profile_when_recognition_is_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            command_path = Path(folder) / "control-command.local.json"
            native_status = {
                "connected": True,
                "state": "idle",
                "engine_available": True,
                "emulator_attached": True,
                "window_attached": True,
                "adb_ready": True,
                "game_ready": True,
                "recognition_available": False,
                "recognition_error": "clean-room recognizer required",
            }
            with mock.patch.object(planner_ui, "PLAN_PATH", Path(folder) / "missing-plan.json"), \
                    mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command_path), \
                    mock.patch.object(planner_ui, "control_status", return_value=native_status):
                payload, code = planner_ui.queue_control_command("start")
            self.assertEqual(code, 409)
            self.assertFalse(payload["ok"])
            self.assertIn("clean-room recognizer required", payload["problems"])
            self.assertFalse(command_path.exists())

    def test_web_start_allows_native_profile_cold_bootstrap_before_recognition_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            command_path = Path(folder) / "control-command.local.json"
            native_status = {
                "connected": True,
                "state": "idle",
                "engine_available": True,
                "emulator_attached": False,
                "window_attached": False,
                "adb_ready": False,
                "game_ready": False,
                "recognition_available": False,
                "recognition_error": "no frame available yet",
            }
            with mock.patch.object(planner_ui, "PLAN_PATH", Path(folder) / "missing-plan.json"), \
                    mock.patch.object(planner_ui, "CONTROL_COMMAND_PATH", command_path), \
                    mock.patch.object(planner_ui, "control_status", return_value=native_status):
                payload, code = planner_ui.queue_control_command("start")
            self.assertEqual(code, 202)
            self.assertTrue(payload["accepted"])
            native_command = json.loads(command_path.read_text(encoding="utf-8"))
            self.assertEqual(native_command["run_mode"], "native-profile")
            self.assertEqual(native_command["plan_token"], planner_ui.PLAN_ABSENCE_TOKEN)

    def test_planned_transport_is_applied_before_any_emulator_or_managed_binding(self):
        execution = (ROOT / "COCBot" / "functions" / "Run" / "RunExecution.au3").read_text(
            encoding="utf-8-sig"
        )
        action = (ROOT / "COCBot" / "MBR GUI Action.au3").read_text(encoding="utf-8-sig")
        transport = execution[
            execution.index("Func _RunExecutionApplyTransportIntent("):
            execution.index("EndFunc", execution.index("Func _RunExecutionApplyTransportIntent("))
        ]
        reassert_transport = execution[
            execution.index("Func RunExecutionReassertPreparedTransport("):
            execution.index("EndFunc", execution.index("Func RunExecutionReassertPreparedTransport("))
        ]
        gameplay = execution[
            execution.index("Func _RunExecutionApplyIntent("):
            execution.index("EndFunc", execution.index("Func _RunExecutionApplyIntent("))
        ]
        self.assertIn("UpdateAndroidConfig(", transport)
        self.assertNotIn("UpdateAndroidConfig(", gameplay)
        self.assertIn("$g_bRunExecutionTransportApplied = True", transport)
        self.assertIn("$g_bRunExecutionGameplayApplied = True", gameplay)
        self.assertIn("$g_bRunExecutionTransportApplied = False", reassert_transport)
        self.assertIn("_RunExecutionApplyTransportIntent($sError)", reassert_transport)
        self.assertNotIn("_RunExecutionCaptureProfileSnapshot", reassert_transport)

        start = action[action.index("Func BotStart("):action.index("EndFunc", action.index("Func BotStart("))]
        slot = start.index("LockBotSlot(True)")
        apply_transport = start.index("RunExecutionApplyPreparedTransport($sStartError)")
        managed_probe = start.index("MBRFuncProbeEngine($sStartError)")
        launch_game = start.index("_BotEnsureConfiguredAndroidAndGame($sStartError)")
        managed_initialize = start.index("MBRFuncInitialize()")
        profile_reload = start.index("applyConfig(False)")
        reassert_transport_call = start.index("RunExecutionReassertPreparedTransport($sStartError)")
        apply_gameplay = start.index("RunExecutionApplyPrepared($sStartError)")
        self.assertLess(slot, apply_transport)
        self.assertLess(apply_transport, managed_probe)
        self.assertLess(apply_transport, launch_game)
        self.assertLess(apply_transport, managed_initialize)
        self.assertLess(profile_reload, reassert_transport_call)
        self.assertLess(reassert_transport_call, apply_gameplay)
        self.assertLess(managed_initialize, apply_gameplay)

    def test_general_start_owns_slot_before_runtime_work_and_releases_on_rejection(self):
        action = (ROOT / "COCBot" / "MBR GUI Action.au3").read_text(encoding="utf-8-sig")
        start = action[action.index("Func BotStart("):action.index("EndFunc", action.index("Func BotStart("))]
        reject = action[
            action.index("Func _BotStartReject("):
            action.index("EndFunc", action.index("Func _BotStartReject("))
        ]

        one_shot_last = start.index("ClanRequestRouteSelected($oPreparedIntent)")
        slot = start.index("LockBotSlot(True)")
        transport = start.index("RunExecutionApplyPreparedTransport($sStartError)")
        probe = start.index("MBRFuncProbeEngine($sStartError)")
        bootstrap = start.index("_BotEnsureConfiguredAndroidAndGame($sStartError)")
        initialize = start.index("MBRFuncInitialize()")
        self.assertEqual(start.count("LockBotSlot(True)"), 1)
        self.assertLess(one_shot_last, slot)
        self.assertEqual([slot, transport, probe, bootstrap, initialize], sorted((slot, transport, probe, bootstrap, initialize)))
        self.assertIn("Not $g_bBotLaunchOption_NoBotSlot And Not LockBotSlot(Default)", start)
        self.assertIn("LockBotSlot(False)", reject)
        self.assertLess(
            reject.index("LockBotSlot(False)"),
            reject.index("If $g_iBotAction <> $eBotClose Then btnStop()"),
        )

    def test_general_cold_bootstrap_dispatches_supported_configured_emulators_safely(self):
        action = (ROOT / "COCBot" / "MBR GUI Action.au3").read_text(encoding="utf-8-sig")
        start = action.index("Func _BotEnsureConfiguredAndroidAndGame(")
        helper = action[start:action.index("EndFunc", start)]

        self.assertIn('$g_sAndroidEmulator = "BlueStacks5"', helper)
        self.assertIn("_BotOpenHomeEnsureExactBlueStacks($sReason)", helper)
        self.assertIn('Case "MEmu", "LDPlayer9", "Mumu"', helper)
        self.assertNotIn('"Nox"', helper)
        self.assertIn("OpenAndroid(False, True)", helper)
        self.assertIn("ConnectAndroidAdb(False, True, 15000)", helper)
        self.assertIn('AndroidAdbSendShellCommand("am start -n "', helper)
        self.assertIn('AndroidAdbSendShellCommand("pidof " & $g_sAndroidGamePackage', helper)
        self.assertIn('StringRegExp($sGamePids, "^[0-9]+([ \\t]+[0-9]+)*$")', helper)
        self.assertIn("__TimerDiff($hGameTimer) <= 90000", helper)
        self.assertIn("RunControlStopRequested()", helper)
        self.assertNotIn("GetAndroidProcessPID(", helper)
        self.assertNotIn("RestartBOT(", helper)
        self.assertNotIn("StartAndroidCoC(", helper)
        self.assertNotIn("PushSharedPrefs", helper)

    def test_all_mutating_terminal_routes_hold_the_shared_slot_until_terminal_outcome(self):
        action = (ROOT / "COCBot" / "MBR GUI Action.au3").read_text(encoding="utf-8-sig")
        wrapper_start = action.index("Func _BotStartRunOneShot(")
        wrapper = action[wrapper_start:action.index("EndFunc", wrapper_start)]
        bot_start_index = action.index("Func BotStart(")
        bot_start = action[bot_start_index:action.index("EndFunc", bot_start_index)]

        acquire = wrapper.index("LockBotSlot(True)")
        dispatch = wrapper.index("Switch $iRoute")
        release = wrapper.rindex("LockBotSlot(False)")
        self.assertLess(acquire, dispatch)
        self.assertLess(dispatch, release)
        self.assertIn("Not $g_bBotLaunchOption_NoBotSlot And Not LockBotSlot(Default)", wrapper)
        for route in (
            "_BotStartOpenHomeCollectors",
            "_BotStartOpenHomeLootCart",
            "_BotStartOpenDailyReward",
            "_BotStartOpenHomeTreasury",
            "_BotStartOpenClanRequest",
        ):
            self.assertIn(f"$bResult = {route}($sStartError)", wrapper, route)
        self.assertNotIn("Return _BotStartOpen", wrapper)
        self.assertIn("_BotStartRunOneShot($iOpenCollectorsMode, $sStartError)", bot_start)
        self.assertIn("_BotStartRunOneShot(5, $sStartError)", bot_start)
        invalid = bot_start.index("$iOpenCollectorsMode = -1")
        clan = bot_start.index("ClanRequestRouteSelected($oPreparedIntent)")
        general_slot = bot_start.index("LockBotSlot(True)")
        self.assertLess(invalid, clan)
        self.assertLess(clan, general_slot)

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
                    mock.patch.object(
                        planner_ui,
                        "control_status",
                        return_value={"connected": True, "state": "idle", "recognition_available": True},
                    ):
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
        self.assertIn("selected native profile through current recognition and no-premium gates", javascript)
        self.assertNotIn("every enabled native profile setting", javascript)
        self.assertIn("$('controlNativeMode').onclick = activateNativeProfileMode;", javascript)
        self.assertIn("$('controlSafeHomeRoute').onclick = prepareVerifiedHomeRoute;", javascript)
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
        self.assertIn('command["plan_token"] = plan_token', server)
        self.assertIn('Start command is missing a valid run_mode', bridge)
        self.assertIn('Start command is missing a valid plan_token', bridge)
        self.assertIn('$g_sRunControlPendingStartMode = $sRunMode', bridge)
        self.assertIn('$g_sRunControlPendingStartPlanToken = $sPlanToken', bridge)
        self.assertIn('Func RunControlCurrentStartMode()', bridge)
        self.assertIn('Func RunControlCurrentStartPlanToken()', bridge)
        prepare = execution[
            execution.index("Func RunExecutionPrepareStart("):
            execution.index("EndFunc", execution.index("Func RunExecutionPrepareStart("))
        ]
        native_branch = prepare.index('$sRequestedMode = "native-profile"')
        stale_fallback = prepare.index('IsObj($g_oRunPlannerIntent)')
        self.assertLess(native_branch, stale_fallback)
        self.assertIn('$sRequestedMode = "" And IsObj($g_oRunPlannerIntent)', prepare)
        self.assertIn('selected planned mode, but the applied plan is missing', prepare)

    def test_stale_recognition_cannot_move_the_applied_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan_path = root / "run-plan.local.json"
            status_path = root / "control-status.local.json"
            original = b'{"run.strategy":"home.collectors"}\n'
            plan_path.write_bytes(original)
            planner_ui.write_json_atomic(
                {
                    "connected": True,
                    "state": "idle",
                    "engine_available": True,
                    "recognition_available": True,
                    "recognition_error": "",
                },
                status_path,
            )
            stale = status_path.stat().st_mtime - planner_ui.CONTROL_STATUS_MAX_AGE_SECONDS - 2
            os.utime(status_path, (stale, stale))
            with mock.patch.object(planner_ui, "PLAN_PATH", plan_path), mock.patch.object(
                planner_ui, "CONTROL_STATUS_PATH", status_path
            ):
                status = planner_ui.control_status()
                payload, code = planner_ui.activate_native_profile_mode()

            self.assertFalse(status["connected"])
            self.assertFalse(status["recognition_available"])
            self.assertIn("stale", status["recognition_error"])
            self.assertEqual(code, 409)
            self.assertFalse(payload["ok"])
            self.assertEqual(plan_path.read_bytes(), original)
            self.assertEqual(list(root.glob("run-plan.local.backup-*.json")), [])

    def test_plan_save_and_native_switch_share_one_linearization_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan_path = root / "run-plan.local.json"
            clean = {"run.strategy": "home.collectors"}
            writer_entered = threading.Event()
            release_writer = threading.Event()
            native_finished = threading.Event()
            original_writer = planner_ui.write_plan_atomic
            results = {}

            def blocked_writer(plan, path=None):
                writer_entered.set()
                if not release_writer.wait(2):
                    raise AssertionError("test writer was not released")
                original_writer(plan, path)

            def save_worker():
                results["save"] = planner_ui.save_plan(clean)

            def native_worker():
                results["native"] = planner_ui.activate_native_profile_mode()
                native_finished.set()

            status = {"connected": True, "state": "idle", "recognition_available": True}
            with mock.patch.object(planner_ui, "PLAN_PATH", plan_path), mock.patch.object(
                planner_ui, "validate_plan", return_value=(clean, [], [])
            ), mock.patch.object(planner_ui, "engine_preflight", return_value=[]), mock.patch.object(
                planner_ui, "control_status", return_value=status
            ), mock.patch.object(planner_ui, "write_plan_atomic", side_effect=blocked_writer):
                save_thread = threading.Thread(target=save_worker)
                native_thread = threading.Thread(target=native_worker)
                save_thread.start()
                self.assertTrue(writer_entered.wait(1))
                native_thread.start()
                self.assertFalse(native_finished.wait(0.05))
                release_writer.set()
                save_thread.join(2)
                native_thread.join(2)

            self.assertFalse(save_thread.is_alive())
            self.assertFalse(native_thread.is_alive())
            self.assertEqual(results["save"][1], 200)
            self.assertEqual(results["native"][1], 200)
            self.assertFalse(plan_path.exists())
            backups = list(root.glob("run-plan.local.backup-*.json"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(json.loads(backups[0].read_text(encoding="utf-8")), clean)

    def test_start_then_plan_replacement_is_bound_for_native_refusal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan_path = root / "run-plan.local.json"
            command_path = root / "control-command.local.json"
            original = json.dumps(valid_home_plan(), sort_keys=True).encode("utf-8") + b"\n"
            replacement = (
                json.dumps(
                    valid_home_plan(
                        **{
                            "events.collect_resources": False,
                            "events.collect_loot_cart": True,
                        }
                    ),
                    sort_keys=True,
                ).encode("utf-8")
                + b"\n"
            )
            plan_path.write_bytes(original)
            native_status = {
                "connected": True,
                "state": "idle",
                "engine_available": True,
                "recognition_available": True,
            }
            with mock.patch.object(planner_ui, "PLAN_PATH", plan_path), mock.patch.object(
                planner_ui, "CONTROL_COMMAND_PATH", command_path
            ), mock.patch.object(planner_ui, "control_status", return_value=native_status):
                payload, code = planner_ui.queue_control_command("start")
                command = json.loads(command_path.read_text(encoding="utf-8"))
                plan_path.write_bytes(replacement)
                replacement_token = planner_ui.plan_start_token("planned")

            self.assertEqual(code, 202)
            self.assertTrue(payload["accepted"])
            self.assertEqual(
                command["plan_token"], f"sha256:{hashlib.sha256(original).hexdigest()}"
            )
            self.assertNotEqual(replacement_token, command["plan_token"])

            execution = (ROOT / "COCBot" / "functions" / "Run" / "RunExecution.au3").read_text(
                encoding="utf-8-sig"
            )
            prepare = execution[
                execution.index("Func RunExecutionPrepareStart("):
                execution.index("EndFunc", execution.index("Func RunExecutionPrepareStart("))
            ]
            first_check = prepare.index("_RunExecutionRequirePlanToken(")
            load = prepare.index("RunPlanFileLoadIntent(")
            second_check = prepare.index("_RunExecutionRequirePlanToken(", first_check + 1)
            self.assertLess(first_check, load)
            self.assertLess(load, second_check)
            self.assertIn("changed after Start was accepted; Start was refused", execution)

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
        self.assertIn("OpenHomeInactivityReloadDialogReady()", ensure)
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

    def test_daily_reward_recovers_inactivity_popup_before_claim(self):
        action = (ROOT / "COCBot" / "MBR GUI Action.au3").read_text(encoding="utf-8-sig")
        body = action[
            action.index("Func _BotStartOpenDailyReward("):
            action.index("EndFunc", action.index("Func _BotStartOpenDailyReward("))
        ]
        self.assertIn("OpenHomeInactivityReloadIssue()", body)
        self.assertIn("OpenHomeStartupRecoveryWait()", body)
        self.assertIn("OpenHomeDailyRewardCaptureClaim($aClaim)", body)
        self.assertLess(body.index("OpenHomeInactivityReloadIssue()"), body.index("OpenHomeDailyRewardCaptureClaim($aClaim)"))
        self.assertIn("reload-rejected", body)
        self.assertIn("reload-unconfirmed", body)

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
            self.assertIn(f"$g_iCmbBoost{selector} = 0", restore)
            self.assertNotIn(
                f"$g_iCmbBoost{selector} = $g_iRunExecutionSnapshotCmbBoost{selector}",
                restore,
            )
        self.assertIn("$g_bChkSellRewards = False", restore)
        # The permanent no-premium selectors are the narrow exception. Ordinary owner profile
        # settings remain snapshot-restored and the overlay still never writes the profile INI.
        self.assertIn("$g_bChkCollect = $g_bRunExecutionSnapshotChkCollect", restore)

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
        self.assertIn("selected native profile through current recognition and no-premium gates", javascript)


if __name__ == "__main__":
    unittest.main()
