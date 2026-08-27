from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
AUTOIT = Path(r"C:\Program Files (x86)\AutoIt3\AutoIt3.exe")
sys.path.insert(0, str(ROOT / "tools"))

import planner_ui  # noqa: E402


def read_source(relative_path: str, *, encoding: str = "utf-8-sig") -> str:
    return (ROOT / relative_path).read_text(encoding=encoding)


def expected_start_identity(payload: dict) -> dict:
    return {
        "expected_run_mode": payload["run_mode"],
        "expected_plan_revision": payload["plan_revision"],
        "expected_plan_token": payload["plan_token"],
    }


def autoit_function(source: str, name: str) -> str:
    start = source.index(f"Func {name}(")
    end = source.index(f"EndFunc   ;==>{name}", start)
    return source[start:end] + f"EndFunc   ;==>{name}\n"


class RuntimeBoundaryRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.apply_config = read_source("COCBot/functions/Config/applyConfig.au3")
        cls.mbr_func = read_source("COCBot/functions/Other/MBRFunc.au3")
        cls.control_bridge = read_source("COCBot/functions/Run/RunControlBridge.au3")
        cls.launcher = read_source("My Bot 2.0.au3")
        cls.backend = read_source("MyBot.run.au3")
        cls.gui_action = read_source("COCBot/MBR GUI Action.au3")
        cls.android = read_source("COCBot/functions/Android/Android.au3")
        cls.android_selector = read_source("COCBot/GUI/MBR GUI Control Android.au3")
        cls.synchronization = read_source("COCBot/functions/Other/Synchronization.au3")
        cls.planner_js = read_source("ui/planner.js", encoding="utf-8")

    def test_apply_config_cannot_reenter_supervised_threading_exports(self) -> None:
        # Every ApplyConfig_* callback lives in this source file. Strip comments so even a later
        # redraw/helper callback cannot quietly become an unsupervised managed-export caller.
        executable_lines = [line.split(";", 1)[0] for line in self.apply_config.splitlines()]
        executable = "\n".join(executable_lines)
        for export in ("setMaxDegreeOfParallelism", "setProcessingPoolSize"):
            self.assertIsNone(
                re.search(rf"\b{export}\s*\(", executable),
                f"{export} must not be called from ApplyConfig callbacks",
            )

        initialize = autoit_function(self.mbr_func, "MBRFuncInitialize")
        self.assertEqual(initialize.count("setMaxDegreeOfParallelism("), 0)
        self.assertEqual(initialize.count("setProcessingPoolSize("), 0)
        self.assertIn("inherited max-degree initialization skipped", initialize)
        self.assertIn("inherited processing-pool initialization skipped", initialize)

    def test_native_status_and_web_controls_publish_recognition_truth(self) -> None:
        recognition_available = autoit_function(self.mbr_func, "MBRFuncRecognitionAvailable")
        recognition_error = autoit_function(self.mbr_func, "MBRFuncRecognitionError")
        self.assertIn("Return False", recognition_available)
        self.assertIn("clean-room replacement", recognition_error)
        self.assertIn("verified bounded Home route", recognition_error)

        status = autoit_function(self.control_bridge, "RunControlWriteStatus")
        self.assertIn('"recognition_available"', status)
        self.assertIn("MBRFuncRecognitionAvailable()", status)
        self.assertIn('"recognition_error"', status)
        self.assertIn("MBRFuncRecognitionError()", status)

        self.assertTrue(
            {"recognition_available", "recognition_error"}.issubset(planner_ui.DIAGNOSTIC_ENGINE_FIELDS)
        )
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(
            planner_ui, "CONTROL_STATUS_PATH", Path(folder) / "missing-status.json"
        ):
            offline = planner_ui.control_status()
        self.assertFalse(offline["recognition_available"])
        self.assertIn("offline", offline["recognition_error"])

        for contract in (
            "const nativeProfileBlocked = NATIVE_PROFILE_MODE && !recognitionAvailable;",
            "const primaryLaunchOnly = nativeProfileBlocked;",
            "$('controlStart').textContent = primaryLaunchOnly ? 'Launch game safely' : 'Start run';",
            "(!primaryLaunchOnly && !engineAvailable)",
            "Launch game safely or use a bounded route",
            "let safeHomeReason = 'Load Home collection settings for review. Nothing is applied or started.';",
            "$('controlSafeHomeRoute').disabled = !BOOT_READY || busy || !connected || state !== 'idle';",
            "|| !recognitionAvailable || NATIVE_PROFILE_MODE;",
            "The primary action is launch-only; apply a verified bounded route before bot actions.",
        ):
            self.assertIn(contract, self.planner_js)

        safe_cta = self.planner_js[
            self.planner_js.index("function prepareVerifiedHomeRoute()") : self.planner_js.index(
                "$('controlStart').onclick", self.planner_js.index("function prepareVerifiedHomeRoute()")
            )
        ]
        self.assertIn("applyStrategySafetyPatch('home.collectors')", safe_cta)
        self.assertIn("setView('planner'", safe_cta)
        self.assertIn("Apply plan, then Start remains a separate action.", safe_cta)
        for forbidden in ("fetch(", "sendControl(", "activateNativeProfileMode("):
            self.assertNotIn(forbidden, safe_cta)

        click_handler = self.planner_js[
            self.planner_js.index("$('controlNativeMode').onclick") : self.planner_js.index(
                "function capabilityLabel", self.planner_js.index("$('controlNativeMode').onclick")
            )
        ]
        self.assertIn("$('controlStart').onclick = () => sendControl(primaryControlAction());", self.planner_js)
        self.assertIn("function primaryControlAction()", self.planner_js)
        self.assertIn("return NATIVE_PROFILE_MODE && CONTROL.recognition_available !== true ? 'launch-game' : 'start';", self.planner_js)
        self.assertIn("$('controlNativeMode').onclick = activateNativeProfileMode;", click_handler)
        self.assertIn("$('controlSafeHomeRoute').onclick = prepareVerifiedHomeRoute;", click_handler)
        self.assertNotIn("else prepareVerifiedHomeRoute()", click_handler)

    def test_dead_native_pid_fails_busy_status_without_erasing_terminal_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            status_path = root / "control-status.local.json"
            command_path = root / "control-command.local.json"
            starting = {
                "state": "starting",
                "message": "Preparing the run",
                "bot_pid": 424242,
                "engine_available": True,
                "last_command": "start",
                "last_outcome": "accepted",
                "last_command_id": "dead-start",
            }
            with mock.patch.object(planner_ui, "CONTROL_STATUS_PATH", status_path), mock.patch.object(
                planner_ui, "CONTROL_COMMAND_PATH", command_path
            ), mock.patch.object(planner_ui, "native_bot_process_alive", return_value=False):
                planner_ui.write_json_atomic(starting, status_path)
                payload = planner_ui.control_status()
                self.assertFalse(payload["connected"])
                self.assertEqual(payload["state"], "offline")
                self.assertEqual(payload["last_outcome"], "failed")
                self.assertIn("process exited", payload["last_command_message"])
                self.assertFalse(payload["engine_available"])
                self.assertFalse(payload["recognition_available"])

                start_payload, start_code = planner_ui.queue_control_command(
                    "start",
                    expected_run_mode="planned",
                    expected_plan_revision=1,
                    expected_plan_token="sha256:" + "0" * 64,
                )
                self.assertEqual(start_code, 409)
                self.assertFalse(start_payload["ok"])
                self.assertIn("native engine is offline", start_payload["problems"])
                self.assertFalse(command_path.exists())

                planner_ui.write_json_atomic(
                    {
                        "state": "idle",
                        "message": "Template-free Home collectors completed; collector_clicks=1",
                        "bot_pid": 424242,
                        "engine_available": True,
                        "last_command": "start",
                        "last_outcome": "completed",
                        "last_command_id": "completed-route",
                    },
                    status_path,
                )
                terminal = planner_ui.control_status()
                self.assertTrue(terminal["connected"])
                self.assertEqual(terminal["state"], "idle")
                self.assertEqual(terminal["last_outcome"], "completed")
                self.assertEqual(
                    terminal["message"],
                    "Template-free Home collectors completed; collector_clicks=1",
                )

    def test_rights_gate_rejects_full_profile_without_writing_a_command(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            command_path = root / "control-command.local.json"
            receipt_path = root / "run-plan.receipt.local.json"
            status = {
                "connected": True,
                "state": "idle",
                "engine_available": True,
                "emulator_attached": True,
                "window_attached": True,
                "adb_ready": True,
                "game_ready": True,
                "recognition_available": False,
                "recognition_error": "licensed inherited recognition or a clean-room replacement is required",
            }
            with mock.patch.object(planner_ui, "PLAN_PATH", root / "missing-plan.json"), mock.patch.object(
                planner_ui, "PLAN_RECEIPT_PATH", receipt_path
            ), mock.patch.object(
                planner_ui, "CONTROL_COMMAND_PATH", command_path
            ), mock.patch.object(planner_ui, "control_status", return_value=status):
                receipt = planner_ui.accepted_plan_receipt("native-profile", planner_ui.new_attempt_id(), 1, planner_ui.PLAN_ABSENCE_TOKEN)
                planner_ui.write_plan_receipt_atomic(receipt)
                payload, code = planner_ui.queue_control_command(
                    "start",
                    expected_run_mode="native-profile",
                    expected_plan_revision=receipt["plan_revision"],
                    expected_plan_token=receipt["plan_token"],
                )

            self.assertEqual(code, 409)
            self.assertFalse(payload["ok"])
            self.assertIn("clean-room replacement", payload["problems"][0])
            self.assertFalse(command_path.exists())

    def test_rights_gate_preserves_bounded_plan_when_native_mode_is_requested(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan_path = root / "run-plan.local.json"
            original = json.dumps({"run.strategy": "home.collectors"}, indent=2).encode("utf-8")
            plan_path.write_bytes(original)
            status = {
                "connected": True,
                "state": "idle",
                "emulator_attached": True,
                "window_attached": True,
                "adb_ready": True,
                "game_ready": True,
                "recognition_available": False,
                "recognition_error": "licensed inherited recognition or a clean-room replacement is required",
            }
            with mock.patch.object(planner_ui, "PLAN_PATH", plan_path), mock.patch.object(
                planner_ui, "control_status", return_value=status
            ):
                payload, code = planner_ui.activate_native_profile_mode()

            self.assertEqual(code, 409)
            self.assertFalse(payload["ok"])
            self.assertIn("clean-room replacement", payload["problems"][0])
            self.assertEqual(plan_path.read_bytes(), original)
            self.assertEqual(list(root.glob("run-plan.local.backup-*.json")), [])

    def test_rights_gate_does_not_disable_a_saved_clean_room_plan(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan_path = root / "run-plan.local.json"
            receipt_path = root / "run-plan.receipt.local.json"
            command_path = root / "control-command.local.json"
            clean_room_plan = planner_ui.default_plan()
            clean_room_plan.update(
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
            status = {
                "connected": True,
                "state": "idle",
                "engine_available": True,
                "recognition_available": False,
                "recognition_error": "full-profile recognition is unavailable",
            }
            with mock.patch.object(planner_ui, "PLAN_PATH", plan_path), mock.patch.object(
                planner_ui, "PLAN_RECEIPT_PATH", receipt_path
            ), mock.patch.object(
                planner_ui, "CONTROL_COMMAND_PATH", command_path
            ), mock.patch.object(planner_ui, "control_status", return_value=status):
                save_payload, save_code = planner_ui.save_plan(clean_room_plan)
                self.assertEqual(save_code, 200)
                payload, code = planner_ui.queue_control_command("start", **expected_start_identity(save_payload))

            self.assertEqual(code, 202)
            self.assertTrue(payload["accepted"])
            command = json.loads(command_path.read_text(encoding="utf-8"))
            self.assertEqual(command["run_mode"], "planned")

    def test_start_refuses_saved_plan_that_fails_server_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan_path = root / "run-plan.local.json"
            receipt_path = root / "run-plan.receipt.local.json"
            command_path = root / "control-command.local.json"
            bad_plan = planner_ui.default_plan()
            bad_plan.update(
                {
                    "run.surface": "builder",
                    "run.strategy": "legacy.standard",
                    "run.max_battles": 1,
                    "army.wait_for_full": True,
                    "donate.keep_army": True,
                    "runtime.emulator": "bluestacks5",
                    "runtime.instance": "Pie64",
                }
            )
            plan_path.write_text(json.dumps(bad_plan), encoding="utf-8")
            status = {
                "connected": True,
                "state": "idle",
                "engine_available": True,
                "recognition_available": False,
                "recognition_error": "full-profile recognition is unavailable",
            }
            with mock.patch.object(planner_ui, "PLAN_PATH", plan_path), mock.patch.object(
                planner_ui, "PLAN_RECEIPT_PATH", receipt_path
            ), mock.patch.object(
                planner_ui, "CONTROL_COMMAND_PATH", command_path
            ), mock.patch.object(planner_ui, "control_status", return_value=status):
                token = planner_ui.plan_start_token("planned")
                receipt = planner_ui.accepted_plan_receipt("planned", planner_ui.new_attempt_id(), 1, token)
                planner_ui.write_plan_receipt_atomic(receipt)
                payload, code = planner_ui.queue_control_command(
                    "start",
                    expected_run_mode="planned",
                    expected_plan_revision=receipt["plan_revision"],
                    expected_plan_token=receipt["plan_token"],
                )

            self.assertEqual(code, 409)
            self.assertFalse(payload["ok"])
            self.assertTrue(any("Builder Base Battles" in item or "Regular Battles" in item for item in payload["problems"]))
            self.assertFalse(command_path.exists())

    def test_latched_android_binding_loss_fails_closed_before_any_dll_call(self) -> None:
        binding = autoit_function(self.mbr_func, "setAndroidPID")
        dll_call = binding.index('DllCall($g_hLibMyBot, "str", "setAndroidPID"')
        initialized = binding.index("If $g_bLibMyBotInitialized Then")
        detached = binding[binding.index('Case "detached-adb"', initialized) : binding.index('Case "player"', initialized)]
        player = binding[binding.index('Case "player"', initialized) : binding.index("Case Else", initialized)]
        missing = binding[binding.index("Case Else", initialized) : binding.index("EndSwitch", initialized)]

        self.assertLess(initialized, dll_call)
        for proof in (
            "$iRequestedPid <= 0",
            "$g_sAndroidEmulator <> $g_sMBRFuncAndroidBindingEmulator",
            "$g_sAndroidInstance <> $g_sMBRFuncAndroidBindingInstance",
            "Not _MBRFuncExactDetachedAdbSurfaceAvailable()",
            "MBRFuncMarkUnavailable(",
            "Return False",
        ):
            self.assertIn(proof, detached)
        self.assertNotIn("DllCall(", detached)

        for proof in (
            "$iRequestedPid = $g_iMBRFuncAndroidBindingPid",
            "$g_sAndroidEmulator = $g_sMBRFuncAndroidBindingEmulator",
            "$g_sAndroidInstance = $g_sMBRFuncAndroidBindingInstance",
            "MBRFuncMarkUnavailable(",
            "Return False",
        ):
            self.assertIn(proof, player)
        self.assertNotIn("DllCall(", player)
        self.assertIn("MBRFuncMarkUnavailable(", missing)
        self.assertIn("Return False", missing)

        for owner in ("MBRFunc", "MBRFuncInitialize", "_MBRFuncInitializationFailed"):
            self.assertIn("_MBRFuncResetAndroidBinding()", autoit_function(self.mbr_func, owner))

    def test_controller_exit_uses_exact_recovery_order_before_success(self) -> None:
        controller_identity = self.launcher.index(
            "Local $sLauncherOwnedControllerCreated = $g_sEngineSupervisorControllerCreated"
        )
        keep = self.launcher.index("_KeepDocked($hController, $iControllerPid)")
        recover_call = self.launcher.index("_RecoverExitedOwnedControllerStack($iControllerPid", keep)
        disarm = self.launcher.index('_EngineSupervisorDisarm("owned controller exited")', recover_call)
        incomplete = self.launcher.index('Exit 12', disarm)
        success = self.launcher.index("Exit 0", incomplete)
        self.assertEqual(
            [controller_identity, keep, recover_call, disarm, incomplete, success],
            sorted((controller_identity, keep, recover_call, disarm, incomplete, success)),
        )

        recovery = autoit_function(self.launcher, "_RecoverExitedOwnedControllerStack")
        self.assertIn("If $g_bLauncherOwnedBackendAmbiguous Then Return False", recovery)
        adb_prune = recovery.index("_PruneLauncherOwnedAdbChildren()")
        adb_ambiguity = recovery.index("_HasUncapturedAdbChildForRecordedBackend($iBackendPid)")
        adb_copy = recovery.index("Local $aOwnedAdbChildren = $g_aLauncherOwnedAdbChildren")
        planner = recovery.index("_CloseOwnedPlannerService($iBackendPid, $sBackendCreated)")
        backend = recovery.index("_CloseVerifiedLauncherBackend($iControllerPid, $iBackendPid, $sBackendCreated)")
        adb_children = recovery.index("_CloseVerifiedAdbChildren($aOwnedAdbChildren)")
        self.assertEqual(
            [adb_prune, adb_ambiguity, adb_copy, planner, backend, adb_children],
            sorted((adb_prune, adb_ambiguity, adb_copy, planner, backend, adb_children)),
        )
        self.assertNotIn("_CloseExactPathProcesses", recovery)
        for foreign_target in ("HD-Player", "BlueStacks", "kill-server"):
            self.assertNotIn(foreign_target, recovery)

        refresh = autoit_function(self.launcher, "_RefreshLauncherOwnedBackend")
        self.assertIn("If $g_bLauncherOwnedBackendAmbiguous Then Return False", refresh)
        self.assertIn("refused ambiguous owned backend capture", refresh)
        self.assertIn("refused overlapping launcher-owned backend generations", refresh)
        self.assertIn("_RefreshLauncherOwnedAdbChildren($iMatchPid, $sMatchCreated)", refresh)
        self.assertNotIn("$g_iLauncherOwnedBackendPid = 0", refresh)

        orphan_detector = autoit_function(self.launcher, "_HasUncapturedAdbChildForRecordedBackend")
        self.assertIn("_ProcessParentPid($iPid) <> $iBackendPid", orphan_detector)
        self.assertIn("_ProcessCreationId($iPid)", orphan_detector)
        self.assertNotIn("_RememberLauncherOwnedAdbChildren", orphan_detector)
        self.assertNotIn("ProcessClose", orphan_detector)

        validate_installation = autoit_function(self.launcher, "_ValidateInstallation")
        foreign_backend = autoit_function(self.launcher, "_FindForeignBackendConflict")
        conflict_error = autoit_function(self.launcher, "_LaunchConflictError")
        self.assertLess(
            validate_installation.index("_FindForeignBackendConflict($sForeignBackend)"),
            validate_installation.index("_InstalledProfilesJunctionMatches()"),
        )
        self.assertIn("A different MyBot.run.exe is already running outside this installation.", validate_installation)
        self.assertIn("Close that old MyBot backend from Task Manager", validate_installation)
        self.assertIn('ProcessList("MyBot.run.exe")', foreign_backend)
        self.assertIn("StringLower($sPath) <> StringLower($g_sHostPath)", foreign_backend)
        self.assertIn("path=<unreadable>", foreign_backend)
        self.assertIn("foreign backend conflict", foreign_backend)
        self.assertIn("_ShowError($sMessage)", conflict_error)
        self.assertNotIn("ProcessClose", foreign_backend)

    def test_native_process_and_every_run_start_hold_the_exact_instance_mutex(self) -> None:
        general = autoit_function(self.gui_action, "BotStart")
        one_shot = autoit_function(self.gui_action, "_BotStartRunOneShot")
        launch_only = autoit_function(self.gui_action, "_BotLaunchGameOnly")
        reject = autoit_function(self.gui_action, "_BotStartReject")
        stop = autoit_function(self.gui_action, "BotStop")

        acquire = "AcquireExactAndroidInstanceLock($g_sAndroidEmulator, $g_sAndroidInstance, $sStartError)"
        self.assertLess(general.index(acquire), general.index("_BotEnsureConfiguredAndroidAndGame"))
        self.assertLess(one_shot.index(acquire), one_shot.index("Switch $iRoute"))
        self.assertLess(
            launch_only.index("AcquireExactAndroidInstanceLock"),
            launch_only.index("LaunchBlueStacks5CoCOnly"),
        )
        self.assertIn("ReleaseExactAndroidInstanceLock()", reject)
        self.assertIn("ReleaseExactAndroidInstanceLock()", one_shot)
        self.assertLess(stop.index("RunExecutionComplete"), stop.index("ReleaseExactAndroidInstanceLock()"))

        initialize = autoit_function(self.backend, "InitializeBot")
        config_loaded = initialize.index("readConfig()")
        reserve = initialize.index("If Not _ReserveConfiguredAndroidInstanceForProcess() Then Exit 13")
        register_exit = initialize.index('OnAutoItExitRegister("_ReleaseConfiguredAndroidInstanceForProcess")')
        exposed_boundaries = (
            initialize.index("InitializeMBR("),
            initialize.index("CreateMainGUI()"),
            initialize.index("LaunchWatchdog()"),
            initialize.index("ShowMainGUI()"),
            initialize.index("AndroidEmbed(True)"),
        )
        self.assertLess(config_loaded, reserve)
        self.assertLess(reserve, register_exit)
        for boundary in exposed_boundaries:
            self.assertLess(register_exit, boundary)
        self.assertIn("ReserveConfiguredAndroidInstanceLock", self.backend)
        self.assertIn("ReleaseConfiguredAndroidInstanceLock", self.backend)

        update_config = autoit_function(self.android, "UpdateAndroidConfig")
        emulator_selector = autoit_function(self.android_selector, "cmbAndroidEmulator")
        instance_selector = autoit_function(self.android_selector, "cmbAndroidInstance")
        self.assertIn("RebindConfiguredAndroidInstanceLock", update_config)
        transport_teardown = update_config.index("AndroidAdbTerminateShellInstance()")
        window_invalidation = update_config.index("UpdateHWnD(0, False)")
        invalidate_init_cache = update_config.index("$g_bInitAndroid = True")
        invalidate_transport = update_config.index("$g_bAndroidInitialized = False")
        publish_adapter = update_config.index("$g_iAndroidConfig = $iRequestedAndroidConfig")
        rebind_transport = update_config.index("RebindConfiguredAndroidInstanceLock", publish_adapter)
        self.assertLess(rebind_transport, update_config.index("InitAndroid(False, False)"))
        self.assertEqual(
            [
                transport_teardown,
                window_invalidation,
                invalidate_init_cache,
                invalidate_transport,
                publish_adapter,
                rebind_transport,
            ],
            sorted(
                (
                    transport_teardown,
                    window_invalidation,
                    invalidate_init_cache,
                    invalidate_transport,
                    publish_adapter,
                    rebind_transport,
                )
            ),
        )
        rollback = update_config[update_config.index("If Not RebindConfiguredAndroidInstanceLock", publish_adapter) :]
        self.assertLess(rollback.index("InitAndroidConfig(False)"), rollback.index("$g_sAndroidInstance = $sPreviousAndroidInstance"))
        for selector in (emulator_selector, instance_selector):
            self.assertIn("UpdateAndroidConfig", selector)
            self.assertNotIn("RebindConfiguredAndroidInstanceLock", selector)
            self.assertIn("selected instance is reserved, but its Android transport is unavailable", selector)

        rebind = autoit_function(self.synchronization, "RebindConfiguredAndroidInstanceLock")
        reserve = autoit_function(self.synchronization, "ReserveConfiguredAndroidInstanceLock")
        action_acquire = autoit_function(self.synchronization, "AcquireExactAndroidInstanceLock")
        self.assertIn("Local $hNewMutex = CreateMutex($sIdentity)", rebind)
        self.assertNotIn("_AcquireExactAndroidInstanceMutexHandle($sIdentity, 1", rebind)
        self.assertNotIn("$g_hConfiguredAndroidInstanceMutex And", action_acquire)
        self.assertIn("_AcquireExactAndroidInstanceMutexHandle($sIdentity, $iTimeoutMs, $bStopAware)", action_acquire)
        self.assertIn("_ConfiguredAndroidInstanceMutexName($sEmulator, $sInstance)", reserve)
        self.assertIn("_ConfiguredAndroidInstanceMutexName($sEmulator, $sInstance)", rebind)
        self.assertIn("_ExactAndroidInstanceMutexName($sEmulator, $sInstance)", action_acquire)

        restore = autoit_function(read_source("COCBot/functions/Run/RunExecution.au3"), "_RunExecutionRestoreProfile")
        failed_rebind = restore[restore.index("If Not UpdateAndroidConfig") :]
        guarded_selectors = failed_rebind.index("If $bTransportRestored Then")
        self.assertLess(failed_rebind.index("$bTransportRestored = False"), guarded_selectors)
        self.assertLess(guarded_selectors, failed_rebind.index("$g_iAndroidConfig = $g_iRunExecutionSnapshotAndroidConfig"))
        self.assertIn("$g_bRunState = False", restore)
        self.assertIn("$g_bRunExecutionProfileSnapshotCaptured = False", restore[guarded_selectors:])

        mutex_name = autoit_function(self.synchronization, "_ExactAndroidInstanceMutexName")
        configured_mutex_name = autoit_function(self.synchronization, "_ConfiguredAndroidInstanceMutexName")
        canonical = autoit_function(self.synchronization, "_CanonicalExactAndroidInstanceIdentity")
        self.assertIn('"Global\\MyBot.run.AndroidInstance.v1."', mutex_name)
        self.assertIn('"Global\\MyBot.run.ConfiguredAndroidReservation.v1."', configured_mutex_name)
        self.assertIn("$sNormalizedEmulator", mutex_name)
        self.assertIn("$sNormalizedInstance", mutex_name)
        self.assertIn("$sNormalizedEmulator", configured_mutex_name)
        self.assertIn("$sNormalizedInstance", configured_mutex_name)
        self.assertIn("StringLen($sNormalizedEmulator)", mutex_name)
        self.assertIn("StringLen($sNormalizedInstance)", mutex_name)
        self.assertIn("StringLen($sNormalizedEmulator)", configured_mutex_name)
        self.assertIn("StringLen($sNormalizedInstance)", configured_mutex_name)
        self.assertIn('Case "ldplayer9"', canonical)
        self.assertIn('StringReplace($sNormalizedInstance, "leidian", "")', canonical)
        self.assertIn('Case "mumu"', canonical)
        self.assertIn('StringReplace($sNormalizedInstance, "mumuplayerglobal-12.0-", "")', canonical)
        self.assertIn('Case "nox"', canonical)
        self.assertIn('$sNormalizedInstance = "nox_0"', canonical)
        self.assertIn('"^[a-z0-9._ -]{0,64}$"', canonical)

    @unittest.skipUnless(AUTOIT.is_file(), "AutoIt runtime is required for the Android transition test")
    def test_instance_change_invalidates_cache_and_rebuilds_the_exact_transport(self) -> None:
        update_config = autoit_function(self.android, "UpdateAndroidConfig")
        harness = "\n".join(
            (
                'Opt("MustDeclareVars", 1)',
                'Global Const $COLOR_RED = 0, $COLOR_ERROR = 0',
                'Global $g_iAndroidConfig = 0',
                'Global $g_sAndroidEmulator = "BlueStacks5"',
                'Global $g_sMode = $CmdLine[1]',
                'Global $g_sAndroidInstance = ($g_sMode = "same" ? "CloneB" : "CloneA")',
                'Global $g_avAndroidAppConfig[1][16]',
                '$g_avAndroidAppConfig[0][0] = "BlueStacks5"',
                '$g_avAndroidAppConfig[0][1] = "Default"',
                'Global $g_bInitAndroid = False',
                'Global $g_bAndroidInitialized = True',
                'Global $g_sAndroidAdbDevice = ($g_sMode = "same" ? "127.0.0.1:6666" : "127.0.0.1:5555")',
                'Global $g_sLockIdentity = ($g_sMode = "same" ? "CloneB" : "CloneA")',
                'Global $g_iAndroidSecureFlags = 0',
                'Global $g_sAndroidPicturesHostFolder = ""',
                'Global $g_sEvents = ""',
                'Global $g_sLastLog = ""',
                'Global $g_bInitShouldFail = ($CmdLine[1] = "fail")',
                'Func FuncEnter($vName)',
                'EndFunc',
                'Func FuncReturn($vResult = Default)',
                '\tReturn $vResult',
                'EndFunc',
                'Func SetDebugLog($sMessage)',
                'EndFunc',
                'Func SetLog($sMessage, $iColor = 0)',
                '\t$g_sLastLog = $sMessage',
                'EndFunc',
                'Func AndroidAdbTerminateShellInstance()',
                '\tIf $g_sAndroidInstance <> "CloneA" Or $g_sLockIdentity <> "CloneA" Then Exit 31',
                '\tIf $g_sAndroidAdbDevice <> "127.0.0.1:5555" Then Exit 32',
                '\t$g_sEvents &= "terminate|"',
                'EndFunc',
                'Func UpdateHWnD($hWnd, $bRestart = True)',
                '\tIf $hWnd <> 0 Or $bRestart Then Exit 33',
                '\t$g_sEvents &= "window|"',
                '\tReturn False',
                'EndFunc',
                'Func InitAndroidConfig($bRestart = False)',
                '\t$g_sAndroidEmulator = $g_avAndroidAppConfig[$g_iAndroidConfig][0]',
                '\t$g_sAndroidInstance = $g_avAndroidAppConfig[$g_iAndroidConfig][1]',
                '\t$g_sAndroidAdbDevice = "127.0.0.1:5555"',
                '\t$g_sEvents &= "adapter-default|"',
                'EndFunc',
                'Func RebindConfiguredAndroidInstanceLock($sEmulator, $sInstance, ByRef $sReason)',
                '\tIf $g_sMode = "same" Then',
                '\t\tIf $g_bInitAndroid Or Not $g_bAndroidInitialized Then Exit 41',
                '\t\tIf $g_sAndroidAdbDevice <> "127.0.0.1:6666" Or $g_sLockIdentity <> "CloneB" Then Exit 42',
                '\t\t$g_sEvents &= "same-rebind|"',
                '\t\tReturn True',
                '\tEndIf',
                '\tIf Not $g_bInitAndroid Or $g_bAndroidInitialized Then Exit 34',
                '\tIf $sEmulator <> "BlueStacks5" Or $sInstance <> "CloneB" Then Exit 35',
                '\tIf $g_sAndroidAdbDevice <> "127.0.0.1:5555" Then Exit 36',
                '\t$g_sLockIdentity = $sInstance',
                '\t$g_sEvents &= "rebind|"',
                '\tReturn True',
                'EndFunc',
                'Func InitAndroid($bCheckOnly = False, $bLogChangesOnly = True)',
                '\tIf Not $g_bInitAndroid Or $g_bAndroidInitialized Then Exit 37',
                '\tIf $g_sLockIdentity <> "CloneB" Or $g_sAndroidInstance <> "CloneB" Then Exit 38',
                '\t$g_sEvents &= "init-exact|"',
                '\tIf $g_bInitShouldFail Then Return False',
                '\t$g_sAndroidAdbDevice = "127.0.0.1:6666"',
                '\t$g_bInitAndroid = False',
                '\t$g_bAndroidInitialized = True',
                '\tReturn True',
                'EndFunc',
                update_config,
                'If $CmdLine[0] <> 2 Then Exit 39',
                'Local $bResult = UpdateAndroidConfig("CloneB", "BlueStacks5")',
                'Local $hMarker = FileOpen($CmdLine[2], 2)',
                'If $hMarker = -1 Then Exit 40',
                'FileWrite($hMarker, ($bResult ? "true" : "false") & "|" & $g_sEvents & "|" & _',
                '\t$g_sAndroidEmulator & "|" & $g_sAndroidInstance & "|" & $g_sAndroidAdbDevice & "|" & _',
                '\t$g_sLockIdentity & "|" & ($g_bInitAndroid ? "init" : "cached") & "|" & _',
                '\t($g_bAndroidInitialized ? "ready" : "unavailable") & "|" & $g_sLastLog)',
                'FileClose($hMarker)',
                'Exit 0',
            )
        )
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / "android-transition.au3"
            script.write_text(harness, encoding="utf-8-sig")

            success_marker = root / "success.marker"
            success = subprocess.run(
                [str(AUTOIT), "/ErrorStdOut", str(script), "success", str(success_marker)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(0, success.returncode, success.stdout + success.stderr)
            success_state = success_marker.read_text(encoding="utf-8")
            self.assertEqual(
                "true|terminate|window|adapter-default|rebind|init-exact||BlueStacks5|CloneB|"
                "127.0.0.1:6666|CloneB|cached|ready|",
                success_state,
            )

            failure_marker = root / "failure.marker"
            failure = subprocess.run(
                [str(AUTOIT), "/ErrorStdOut", str(script), "fail", str(failure_marker)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(0, failure.returncode, failure.stdout + failure.stderr)
            failure_state = failure_marker.read_text(encoding="utf-8")
            self.assertTrue(
                failure_state.startswith(
                    "false|terminate|window|adapter-default|rebind|init-exact||BlueStacks5|CloneB|"
                    "127.0.0.1:5555|CloneB|init|unavailable|"
                ),
                failure_state,
            )
            self.assertIn("remains reserved, but its transport could not be initialized", failure_state)

            same_marker = root / "same.marker"
            same = subprocess.run(
                [str(AUTOIT), "/ErrorStdOut", str(script), "same", str(same_marker)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(0, same.returncode, same.stdout + same.stderr)
            self.assertEqual(
                "true|same-rebind||BlueStacks5|CloneB|127.0.0.1:6666|CloneB|cached|ready|",
                same_marker.read_text(encoding="utf-8"),
            )

    @unittest.skipUnless(AUTOIT.is_file(), "AutoIt runtime is required for the cross-process mutex test")
    def test_same_instance_serializes_while_distinct_instances_run_concurrently(self) -> None:
        functions = "\n".join(
            autoit_function(self.synchronization, name)
            for name in (
                "CreateMutex",
                "ReleaseMutex",
                "_CanonicalExactAndroidInstanceIdentity",
                "_ExactAndroidInstanceMutexName",
                "_AcquireExactAndroidInstanceMutexHandle",
                "AcquireExactAndroidInstanceLock",
                "ReleaseExactAndroidInstanceLock",
            )
        )
        harness = "\n".join(
            (
                '#include <StringConstants.au3>',
                '#include <WinAPIProc.au3>',
                'Opt("MustDeclareVars", 1)',
                'Global $g_bRunState = True',
                'Global $g_hExactAndroidInstanceMutex = 0',
                'Global $g_sExactAndroidInstanceMutexIdentity = ""',
                'Global $g_hConfiguredAndroidInstanceMutex = 0',
                'Global $g_sConfiguredAndroidInstanceMutexIdentity = ""',
                'Func __TimerInit()',
                '\tReturn TimerInit()',
                'EndFunc',
                'Func __TimerDiff($hTimer)',
                '\tReturn TimerDiff($hTimer)',
                'EndFunc',
                'Func SetDebugLog($sMessage)',
                'EndFunc',
                functions,
                'If $CmdLine[0] <> 4 Then Exit 9',
                'Local $sReason = ""',
                'If Not AcquireExactAndroidInstanceLock($CmdLine[1], $CmdLine[2], $sReason, 5000) Then Exit 8',
                'Local $hMarker = FileOpen($CmdLine[4], 2)',
                'If $hMarker = -1 Then Exit 7',
                'FileWrite($hMarker, @AutoItPID)',
                'FileClose($hMarker)',
                'Sleep(Int($CmdLine[3]))',
                'ReleaseExactAndroidInstanceLock()',
                'Exit 0',
            )
        )

        def wait_for(path: Path, timeout: float = 5.0) -> bool:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if path.exists():
                    return True
                time.sleep(0.025)
            return path.exists()

        aliases = (
            ("BlueStacks5", "Pie64-test-mutex", "Pie64-test-mutex", "Pie65-test-mutex"),
            ("Nox", "nox", "Nox_0", "clone_1"),
            ("LDPlayer9", "leidian0", "0", "1"),
            ("Mumu", "MuMuPlayerGlobal-12.0-0", "foo", "1"),
        )
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / "instance-mutex.au3"
            script.write_text(harness, encoding="utf-8-sig")
            for case_index, (emulator, first_instance, alias_instance, distinct_instance) in enumerate(aliases):
                first_marker = root / f"first-{case_index}.marker"
                same_marker = root / f"same-{case_index}.marker"
                distinct_marker = root / f"distinct-{case_index}.marker"
                first = subprocess.Popen(
                    [str(AUTOIT), "/ErrorStdOut", str(script), emulator, first_instance, "1000", str(first_marker)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                same = distinct = None
                try:
                    if not wait_for(first_marker):
                        stdout, stderr = first.communicate(timeout=5)
                        self.fail(
                            f"first owner did not acquire {emulator}/{first_instance}; exit={first.returncode}; "
                            f"stdout={stdout!r}; stderr={stderr!r}"
                        )
                    same = subprocess.Popen(
                        [str(AUTOIT), "/ErrorStdOut", str(script), emulator, alias_instance, "100", str(same_marker)]
                    )
                    distinct = subprocess.Popen(
                        [str(AUTOIT), "/ErrorStdOut", str(script), emulator, distinct_instance, "100", str(distinct_marker)]
                    )
                    self.assertTrue(wait_for(distinct_marker, 0.8), f"distinct {emulator} instance was blocked")
                    self.assertFalse(same_marker.exists(), f"{emulator} alias acquired concurrently")
                    first_stdout, first_stderr = first.communicate(timeout=3)
                    self.assertEqual(0, first.returncode, f"stdout={first_stdout!r}; stderr={first_stderr!r}")
                    self.assertTrue(wait_for(same_marker, 1.5), f"waiting {emulator} alias never acquired")
                    self.assertEqual(0, same.wait(timeout=2))
                    self.assertEqual(0, distinct.wait(timeout=2))
                finally:
                    for process in (first, same, distinct):
                        if process is not None and process.poll() is None:
                            process.kill()
                            process.wait(timeout=2)

    @unittest.skipUnless(AUTOIT.is_file(), "AutoIt runtime is required for the rebind ownership test")
    def test_action_keeps_original_instance_exclusive_while_process_reservation_rebinds(self) -> None:
        functions = "\n".join(
            autoit_function(self.synchronization, name)
            for name in (
                "CreateMutex",
                "ReleaseMutex",
                "_CanonicalExactAndroidInstanceIdentity",
                "_ExactAndroidInstanceMutexName",
                "_ConfiguredAndroidInstanceMutexName",
                "_AcquireExactAndroidInstanceMutexHandle",
                "ReserveConfiguredAndroidInstanceLock",
                "RebindConfiguredAndroidInstanceLock",
                "ReleaseConfiguredAndroidInstanceLock",
                "AcquireExactAndroidInstanceLock",
                "ReleaseExactAndroidInstanceLock",
            )
        )
        harness = "\n".join(
            (
                '#include <StringConstants.au3>',
                '#include <WinAPIProc.au3>',
                'Opt("MustDeclareVars", 1)',
                'Global $g_bRunState = True',
                'Global $g_hExactAndroidInstanceMutex = 0',
                'Global $g_sExactAndroidInstanceMutexIdentity = ""',
                'Global $g_hConfiguredAndroidInstanceMutex = 0',
                'Global $g_sConfiguredAndroidInstanceMutexIdentity = ""',
                'Func __TimerInit()',
                '\tReturn TimerInit()',
                'EndFunc',
                'Func __TimerDiff($hTimer)',
                '\tReturn TimerDiff($hTimer)',
                'EndFunc',
                'Func SetDebugLog($sMessage)',
                'EndFunc',
                functions,
                'If $CmdLine[0] <> 4 Then Exit 9',
                'Local $sReason = ""',
                'Local $bAcquired = False',
                'If $CmdLine[1] = "owner" Then',
                '\tIf Not ReserveConfiguredAndroidInstanceLock("BlueStacks5", "Rebind A", $sReason, 1000) Then Exit 7',
                '\tIf Not AcquireExactAndroidInstanceLock("BlueStacks5", "Rebind A", $sReason, 1000) Then Exit 6',
                '\tIf Not RebindConfiguredAndroidInstanceLock("BlueStacks5", "Rebind B", $sReason) Then Exit 5',
                '\t$bAcquired = True',
                'ElseIf $CmdLine[1] = "reserve-wait" Then',
                '\t$bAcquired = ReserveConfiguredAndroidInstanceLock("BlueStacks5", $CmdLine[2], $sReason, 400)',
                'Else',
                '\t$bAcquired = AcquireExactAndroidInstanceLock("BlueStacks5", $CmdLine[2], $sReason, 400)',
                'EndIf',
                'Local $hMarker = FileOpen($CmdLine[4], 2)',
                'If $hMarker = -1 Then Exit 4',
                'FileWrite($hMarker, ($bAcquired ? "acquired" : "failed:" & $sReason))',
                'FileClose($hMarker)',
                'If Not $bAcquired Then Exit 8',
                'Sleep(Int($CmdLine[3]))',
                'ReleaseExactAndroidInstanceLock()',
                'ReleaseConfiguredAndroidInstanceLock()',
                'Exit 0',
            )
        )

        def wait_for(marker: Path, timeout: float = 2.0) -> bool:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if marker.exists():
                    return True
                time.sleep(0.025)
            return marker.exists()

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / "instance-rebind.au3"
            script.write_text(harness, encoding="utf-8-sig")
            owner_marker = root / "owner.marker"
            owner = subprocess.Popen(
                [str(AUTOIT), "/ErrorStdOut", str(script), "owner", "ignored", "3000", str(owner_marker)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self.assertTrue(wait_for(owner_marker), "rebind owner did not acquire both reservations")
                blocked_a_marker = root / "blocked-A.marker"
                blocked_a = subprocess.run(
                    [str(AUTOIT), "/ErrorStdOut", str(script), "wait", "Rebind A", "0", str(blocked_a_marker)],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                self.assertEqual(8, blocked_a.returncode, blocked_a.stdout + blocked_a.stderr)
                self.assertTrue(blocked_a_marker.read_text(encoding="utf-8").startswith("failed:"))

                blocked_b_marker = root / "blocked-B.marker"
                blocked_b = subprocess.run(
                    [str(AUTOIT), "/ErrorStdOut", str(script), "reserve-wait", "Rebind B", "0", str(blocked_b_marker)],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                self.assertEqual(8, blocked_b.returncode, blocked_b.stdout + blocked_b.stderr)
                self.assertTrue(blocked_b_marker.read_text(encoding="utf-8").startswith("failed:"))
            finally:
                owner_stdout, owner_stderr = owner.communicate(timeout=5)
            self.assertEqual(0, owner.returncode, owner_stdout + owner_stderr)

            for mode, instance in (("wait", "Rebind A"), ("reserve-wait", "Rebind B")):
                marker = root / f"released-{instance[-1]}.marker"
                released = subprocess.run(
                    [str(AUTOIT), "/ErrorStdOut", str(script), mode, instance, "0", str(marker)],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                self.assertEqual(0, released.returncode, released.stdout + released.stderr)
                self.assertEqual("acquired", marker.read_text(encoding="utf-8"))

    @unittest.skipUnless(AUTOIT.is_file(), "AutoIt runtime is required for the mutex lifecycle test")
    def test_instance_wait_is_bounded_cancellable_and_recovers_abandoned_owner(self) -> None:
        functions = "\n".join(
            autoit_function(self.synchronization, name)
            for name in (
                "CreateMutex",
                "ReleaseMutex",
                "_CanonicalExactAndroidInstanceIdentity",
                "_ExactAndroidInstanceMutexName",
                "_AcquireExactAndroidInstanceMutexHandle",
                "AcquireExactAndroidInstanceLock",
                "ReleaseExactAndroidInstanceLock",
            )
        )
        harness = "\n".join(
            (
                '#include <StringConstants.au3>',
                '#include <WinAPIProc.au3>',
                'Opt("MustDeclareVars", 1)',
                'Global $g_bRunState = True',
                'Global $g_hExactAndroidInstanceMutex = 0',
                'Global $g_sExactAndroidInstanceMutexIdentity = ""',
                'Global $g_hConfiguredAndroidInstanceMutex = 0',
                'Global $g_sConfiguredAndroidInstanceMutexIdentity = ""',
                'Func __TimerInit()',
                '\tReturn TimerInit()',
                'EndFunc',
                'Func __TimerDiff($hTimer)',
                '\tReturn TimerDiff($hTimer)',
                'EndFunc',
                'Func SetDebugLog($sMessage)',
                'EndFunc',
                'Func _CancelInstanceWait()',
                '\t$g_bRunState = False',
                '\tAdlibUnRegister("_CancelInstanceWait")',
                'EndFunc',
                functions,
                'If $CmdLine[0] <> 6 Then Exit 9',
                'If $CmdLine[1] = "cancel" Then AdlibRegister("_CancelInstanceWait", 150)',
                'Local $sReason = ""',
                'Local $hStarted = TimerInit()',
                'Local $bAcquired = AcquireExactAndroidInstanceLock($CmdLine[2], $CmdLine[3], $sReason, Int($CmdLine[4]), True)',
                'Local $hMarker = FileOpen($CmdLine[6], 2)',
                'If $hMarker = -1 Then Exit 7',
                'FileWrite($hMarker, ($bAcquired ? "acquired" : "failed:" & $sReason) & "|elapsed=" & Int(TimerDiff($hStarted)))',
                'FileClose($hMarker)',
                'If Not $bAcquired Then Exit 8',
                'Sleep(Int($CmdLine[5]))',
                'If $CmdLine[1] <> "abandon" Then ReleaseExactAndroidInstanceLock()',
                'Exit 0',
            )
        )

        def wait_for(path: Path, timeout: float = 2.0) -> bool:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if path.exists():
                    return True
                time.sleep(0.025)
            return path.exists()

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / "instance-mutex-lifecycle.au3"
            script.write_text(harness, encoding="utf-8-sig")
            owner_marker = root / "owner.marker"
            owner = subprocess.Popen(
                [str(AUTOIT), "/ErrorStdOut", str(script), "hold", "BlueStacks5", "Lock Tests", "5000", "2500", str(owner_marker)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self.assertTrue(wait_for(owner_marker), "mutex owner did not acquire")

                timeout_marker = root / "timeout.marker"
                timeout_waiter = subprocess.run(
                    [str(AUTOIT), "/ErrorStdOut", str(script), "wait", "BlueStacks5", "Lock Tests", "300", "0", str(timeout_marker)],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                self.assertEqual(8, timeout_waiter.returncode, timeout_waiter.stdout + timeout_waiter.stderr)
                timeout_result = timeout_marker.read_text(encoding="utf-8")
                self.assertIn("failed:Another bot process is using the configured emulator instance", timeout_result)
                self.assertLess(int(timeout_result.rsplit("=", 1)[1]), 1200)

                cancel_marker = root / "cancel.marker"
                cancel_waiter = subprocess.run(
                    [str(AUTOIT), "/ErrorStdOut", str(script), "cancel", "BlueStacks5", "Lock Tests", "5000", "0", str(cancel_marker)],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                self.assertEqual(8, cancel_waiter.returncode, cancel_waiter.stdout + cancel_waiter.stderr)
                cancel_result = cancel_marker.read_text(encoding="utf-8")
                self.assertIn("failed:Start cancelled while waiting for the configured emulator instance", cancel_result)
                self.assertLess(int(cancel_result.rsplit("=", 1)[1]), 1200)
            finally:
                if owner.poll() is None:
                    owner.kill()
                owner_stdout, owner_stderr = owner.communicate(timeout=2)

            abandoned_marker = root / "abandoned.marker"
            abandoned = subprocess.Popen(
                [str(AUTOIT), "/ErrorStdOut", str(script), "abandon", "BlueStacks5", "Abandoned", "1000", "10000", str(abandoned_marker)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertTrue(wait_for(abandoned_marker), "abandoned owner did not acquire")
            abandoned.kill()
            abandoned_stdout, abandoned_stderr = abandoned.communicate(timeout=2)
            recovered_marker = root / "recovered.marker"
            recovered = subprocess.run(
                [str(AUTOIT), "/ErrorStdOut", str(script), "wait", "BlueStacks5", "Abandoned", "1000", "0", str(recovered_marker)],
                capture_output=True,
                text=True,
                timeout=2,
            )
            self.assertEqual(0, recovered.returncode, recovered.stdout + recovered.stderr)
            self.assertTrue(recovered_marker.read_text(encoding="utf-8").startswith("acquired|"))


if __name__ == "__main__":
    unittest.main()
