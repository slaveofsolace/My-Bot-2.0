from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def autoit_function(text: str, name: str) -> str:
    match = re.search(rf"(?ims)^Func\s+{re.escape(name)}\s*\([^\r\n]*\).*?^EndFunc\b", text)
    if not match:
        raise AssertionError(f"AutoIt function not found: {name}")
    return match.group(0)


class RunVillageReadinessStaticTest(unittest.TestCase):
    def test_planned_start_is_not_reported_started_before_village_preflight(self) -> None:
        initiate = autoit_function(source("COCBot/GUI/MBR GUI Control Bottom.au3"), "Initiate")
        ordered = (
            "$bPlannedVillagePreflight",
            "ZoomOut()",
            "BotDetectFirstTime(True)",
            "RunVillageReadinessIdentityVerified(",
            "RunExecutionPreparedIntent()",
            "RunIntentPlannedTownHall(",
            "RunVillageReadinessValidate(",
            "HeroLoadoutValidateForDetectedTownHall(",
            "AndroidBotStartEvent()",
            "RunExecutionBegin(",
            "RunControlReportStartOutcome(True",
        )
        offsets = [initiate.index(fragment) for fragment in ordered]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("RunEventLogPlanBlocked", initiate)
        self.assertIn("Return False", initiate)
        self.assertNotIn("RunVillageReadinessValidate($g_iTownHallLevel, isInsideDiamond(", initiate)

        execution = source("COCBot/functions/Run/RunExecution.au3")
        event_log = source("COCBot/functions/Run/RunEventLog.au3")
        prepare = autoit_function(execution, "RunExecutionPrepareStart")
        cancel = autoit_function(execution, "RunExecutionCancelPrepared")
        self.assertIn("RunEventLogPreflightStarted", prepare)
        self.assertIn('RunEventLogWrite("session.preparing"', event_log)
        self.assertNotIn('RunEventLogWrite("session.ready"', event_log)
        self.assertIn("RunSessionFail($g_oRunExecutionSession, $sReason)", cancel)
        self.assertIn('"Preflight failed: " & $sReason', cancel)
        self.assertLess(prepare.index("RunEventLogBindSession"), prepare.index("RunEventLogPreflightStarted"))
        self.assertIn("RunVillageReadinessIdentitySource()", initiate)
        self.assertIn("selected Heroes require a fresh visual Town Hall detection", initiate)

    def test_account_switch_gate_precedes_training_donation_and_attack(self) -> None:
        main = source("MyBot.run.au3")
        first_check = autoit_function(main, "FirstCheck")
        legacy_detection = first_check.index("imglocTHSearch(")
        legacy_gate = first_check.index("_RunExecutionRequireOwnVillageReady()", legacy_detection)
        self.assertLess(legacy_detection, legacy_gate)
        self.assertLess(first_check.index("_RunExecutionRequireOwnVillageReady()"), first_check.index("TrainSystem()"))
        self.assertLess(first_check.index("_RunExecutionRequireOwnVillageReady()"), first_check.index("AttackMain()"))

        run_bot = autoit_function(main, "runBot")
        self.assertLess(run_bot.index("FirstCheck()"), run_bot.index("_RunExecutionRequireOwnVillageReady()"))
        self.assertLess(run_bot.index("_RunExecutionRequireOwnVillageReady()"), run_bot.index("PrepareDonateCC()"))

    def test_current_army_run_skips_legacy_zoom_and_building_interaction(self) -> None:
        main = source("MyBot.run.au3")
        run_bot = autoit_function(main, "runBot")
        home_start = run_bot.index("If HomeMaintenanceRouteActive() Then")
        home_execute = run_bot.index("HomeMaintenanceRouteExecute()", home_start)
        home_return = run_bot.index("Return", home_execute)
        passive_start = run_bot.index("If RunExecutionPlanActive() And Not RunExecutionShouldManageTraining() Then")
        passive_execute = run_bot.index("_RunExecutionRunCurrentArmyOneBattle()", passive_start)
        passive_return = run_bot.index("Return", passive_execute)
        offsets = [
            home_start,
            home_execute,
            home_return,
            passive_start,
            passive_execute,
            passive_return,
            run_bot.index("InitiateSwitchAcc()", passive_return),
            run_bot.index("FirstCheck()", passive_return),
            run_bot.index("While 1", passive_return),
        ]
        self.assertEqual(offsets, sorted(offsets))

        one_battle = autoit_function(main, "_RunExecutionRunCurrentArmyOneBattle")
        ordered = (
            "$g_bIsFullArmywithHeroesAndSpells = False",
            "TrainSystem()",
            "If Not $g_bIsFullArmywithHeroesAndSpells Then",
            "current trained army is not ready",
            "$g_bRestart = False",
            "AttackMain(True)",
            "RunExecutionCheckStop()",
            "single attack attempt returned without completing the planned battle",
        )
        one_battle_offsets = [one_battle.index(fragment) for fragment in ordered]
        self.assertEqual(one_battle_offsets, sorted(one_battle_offsets))
        self.assertLess(
            one_battle.index("Local $bMainScreenReady = checkMainScreen(False)"),
            one_battle.index("If Not $bMainScreenReady Then"),
        )
        self.assertLess(
            one_battle.index("If $g_bRunControlStopRequested Or Not $g_bRunState Then Return False"),
            one_battle.index("If Not $bMainScreenReady Then"),
        )
        self.assertEqual(one_battle.count("AttackMain(True)"), 1)
        self.assertEqual(one_battle.count("RunExecutionCheckStop()"), 1)
        self.assertEqual(one_battle.count("$g_bRestart = False"), 1)
        for forbidden in (
            "ZoomOut(",
            "SearchZoomOut(",
            "GetVillageSize(",
            "BuildingClick(",
            "BuildingClickP(",
            "HiddenSlotstatus(",
            "BotDetectFirstTime(",
            "imglocTHSearch(",
            "VillageReport(",
            "_RunFunction(",
            "Idle(",
            "Unbreakable(",
            "BuilderBase(",
            "TakeWardenValues(",
        ):
            self.assertNotIn(forbidden, one_battle)

        attack_main = autoit_function(main, "AttackMain")
        planner_branch_start = attack_main.index("If $bPlannerTerminalOneBattle Then")
        legacy_schedule_start = attack_main.index("If IsSearchAttackEnabled() Then")
        planner_branch = attack_main[planner_branch_start:legacy_schedule_start]
        self.assertLess(planner_branch_start, legacy_schedule_start)
        self.assertIn("Return _AttackMainExecuteRegularBattle()", planner_branch)
        for forbidden in (
            "SmartPause(",
            "IsSearchAttackEnabled(",
            "UniversalCloseWaitOpenCoC(",
            "_ClanGames(",
            "DropTrophy(",
            "ProfileReport(",
            "checkSwitchAcc(",
        ):
            self.assertNotIn(forbidden, planner_branch)

        battle_core = autoit_function(main, "_AttackMainExecuteRegularBattle")
        core_order = (
            "PrepareSearch()",
            "VillageSearch()",
            "PrepareAttack($g_iMatchMode)",
            "Attack()",
            "ReturnHome($g_bTakeLootSnapShot)",
            "Return True",
        )
        core_offsets = [battle_core.index(fragment) for fragment in core_order]
        self.assertEqual(core_offsets, sorted(core_offsets))
        for forbidden in ("SmartPause(", "UniversalCloseWaitOpenCoC(", "_ClanGames(", "DropTrophy("):
            self.assertNotIn(forbidden, battle_core)

        main_screen = autoit_function(
            source("COCBot/functions/Main Screen/checkMainScreen.au3"), "_checkMainScreen"
        )
        self.assertLess(
            main_screen.index("RunExecutionSkipVillageZoomCalibration()"),
            main_screen.index("ZoomOut()"),
        )
        self.assertIn(
            "Run Planner bounded mode: skipped legacy pending notifications during screen proof",
            main_screen,
        )
        self.assertRegex(
            main_screen,
            r"(?s)If RunExecutionSkipPendingNotifications\(\) Then.*?Else\s+NotifyPendingActions\(\)\s+EndIf",
        )

        execution = autoit_function(
            source("COCBot/functions/Run/RunExecution.au3"), "RunExecutionSkipVillageZoomCalibration"
        )
        self.assertIn("If Not $g_bRunExecutionPrepared Or $g_bRunExecutionManageTraining Then Return False", execution)
        self.assertIn("HomeMaintenanceRouteSelected($g_oRunExecutionIntent) Then Return False", execution)

        builder_count = autoit_function(
            source("COCBot/functions/Read Text/getBuilderCount.au3"), "getBuilderCount"
        )
        self.assertIn("Builder OCR failed repeatedly; leaving Android running", builder_count)
        self.assertNotIn("$g_bGfxError = True", builder_count)
        self.assertNotIn("CheckAndroidReboot()", builder_count)

    def test_current_army_emulator_open_never_runs_village_zoom_calibration(self) -> None:
        open_android = autoit_function(source("COCBot/functions/Android/Android.au3"), "_OpenAndroid")
        guard = "If Not RunExecutionSkipVillageZoomCalibration() Then ZoomOut()"
        self.assertEqual(open_android.count(guard), 2)
        self.assertEqual(
            [line for line in open_android.splitlines() if line.strip() == "ZoomOut()"],
            [],
        )

    def test_current_army_contract_rejects_every_pre_battle_side_effect(self) -> None:
        contract = autoit_function(
            source("COCBot/functions/Run/RunExecutionContract.au3"),
            "RunExecutionContractValidate",
        )
        for required in (
            'If Not $oPlan.Item("army_wait_for_full") Then',
            '$oPlan.Item("donate_request_when_short")',
            'If $oPlan.Item("events_collect_resources") Then',
            'Collector work requires the explicit Home maintenance - collectors only strategy',
            'If $oPlan.Item("events_clan_games") Then',
            '$oPlan.Item("events_laboratory")',
            '$oPlan.Item("upgrade_policy")',
        ):
            self.assertIn(required, contract)

    def test_active_failure_is_terminal_and_cleans_up(self) -> None:
        main = source("MyBot.run.au3")
        fail = autoit_function(main, "_RunExecutionFailOwnVillageReadiness")
        self.assertLess(
            fail.index("If $g_bRunControlStopRequested Then"),
            fail.index("RunEventLogRunFailed("),
        )
        ordered = (
            "RunEventLogRunFailed(",
            "RunExecutionCancelPrepared(",
            "btnStop()",
            "RunControlReportRunFailure(",
        )
        offsets = [fail.index(fragment) for fragment in ordered]
        self.assertEqual(offsets, sorted(offsets))

        control = source("COCBot/functions/Run/RunControlBridge.au3")
        report = autoit_function(control, "RunControlReportRunFailure")
        self.assertLess(
            report.index("If $g_bRunControlStopRequested Then"),
            report.index('$g_sRunControlLastOutcome = "failed"'),
        )
        self.assertIn('$g_sRunControlLastOutcome = "failed"', report)
        self.assertIn("RunControlWriteStatus(True)", report)
        planner = source("ui/planner.js")
        terminal_outcomes = re.search(
            r"const CONTROL_TERMINAL_OUTCOMES\s*=\s*new Set\(\[(.*?)\]\);",
            planner,
            re.DOTALL,
        )
        self.assertIsNotNone(terminal_outcomes)
        self.assertIn("'failed'", terminal_outcomes.group(1))

    def test_detector_retries_out_of_range_levels_and_bounds_stats_index(self) -> None:
        detector = autoit_function(source("COCBot/functions/Village/BotDetectFirstTime.au3"), "BotDetectFirstTime")
        self.assertIn("Number($g_iTownHallLevel) > $g_iMaxTHLevel", detector)
        self.assertRegex(detector, r"Number\(\$g_iTownHallLevel\) <= \$g_iMaxTHLevel Then\s+_?\s*GUICtrlSetState")

    def test_planned_detector_never_enters_manual_or_optional_building_locators(self) -> None:
        detector = autoit_function(source("COCBot/functions/Village/BotDetectFirstTime.au3"), "BotDetectFirstTime")
        self.assertIn("$bOwnVillageReadinessOnly = False", detector)
        identity_branch = detector.index("If $bOwnVillageReadinessOnly Then", detector.index("SetLog("))
        self.assertLess(identity_branch, detector.index("If Not isInsideDiamond($g_aiTownHallPos) Then"))
        identity_slice = detector[identity_branch:detector.index("#cs", identity_branch)]
        self.assertIn("RunVillageReadinessResetIdentity()", detector[:identity_branch])
        self.assertIn("imglocOwnVillageTownHallIdentity(", identity_slice)
        self.assertIn("RunVillageReadinessMarkIdentityVerified(", identity_slice)
        self.assertIn("RunExecutionSkipVillageZoomCalibration()", identity_slice)
        self.assertIn("RunVillageReadinessMarkMainScreenProfileAttested(", identity_slice)
        fallback = identity_slice.index("RunVillageReadinessMarkMainScreenProfileAttested(")
        strict_failure = identity_slice.index("Own-village Town Hall identity could not be verified")
        self.assertLess(fallback, strict_failure)
        self.assertIn("without building coordinates", identity_slice)
        self.assertNotIn("ConvertFromVillagePos", identity_slice)
        self.assertNotIn("LocateTownHall", identity_slice)
        self.assertNotIn("Collect(", identity_slice)
        self.assertNotIn("BuildingClick", identity_slice)
        self.assertNotRegex(identity_slice, r"\bLocate\w*\s*\(")
        readiness_returns = [match.start() for match in re.finditer(r"If \$bOwnVillageReadinessOnly Then Return", detector)]
        self.assertGreaterEqual(len(readiness_returns), 2)
        for locator in (
            "LocateTownHall(False, False)",
            "LocateClanCastle(False)",
            "LocateHeroHall(False)",
            "LocateLab(False)",
            "LocatePetHouse(False)",
            "LocateBlacksmith(False)",
            "LocateHelperHut(False)",
        ):
            self.assertGreater(detector.index(locator), readiness_returns[0 if locator.startswith("LocateTownHall") else 1])

        first_check = autoit_function(source("MyBot.run.au3"), "FirstCheck")
        self.assertIn("BotDetectFirstTime(RunExecutionPlanActive())", first_check)

    def test_identity_detector_has_no_legacy_coordinate_or_attack_state_side_effects(self) -> None:
        detector = autoit_function(
            source("COCBot/functions/Image Search/imglocTHSearch.au3"),
            "imglocOwnVillageTownHallIdentity",
        )
        self.assertIn("findMultiple(", detector)
        self.assertIn("objectname,objectlevel,objectpoints", detector)
        self.assertIn("$iMinimumLevel = ($iExpectedLevel > 0 ? $iExpectedLevel : 2)", detector)
        self.assertIn("$iMaximumLevel = ($iExpectedLevel > 0 ? $iExpectedLevel : $g_iMaxTHLevel)", detector)
        self.assertIn("$iMinimumLevel, $iMaximumLevel, 3", detector)
        self.assertNotIn("$CocDiamondECD, $CocDiamondECD, 6, _", detector)
        for forbidden in (
            "ResetTHsearch",
            "ConvertFromVillagePos",
            "_ObjPutValue",
            "$g_iSearchTH",
            "$g_iTHx",
            "$g_iTHy",
            "BuildingClick",
            "SaveConfig",
        ):
            self.assertNotIn(forbidden, detector)

        gate = autoit_function(source("MyBot.run.au3"), "_RunExecutionRequireOwnVillageReady")
        self.assertIn("RunVillageReadinessIdentityVerified(", gate)
        self.assertNotIn("RunVillageReadinessValidate($g_iTownHallLevel, isInsideDiamond(", gate)
        self.assertIn("HeroLoadoutValidateForDetectedTownHall", gate)
        self.assertLess(gate.index("RunVillageReadinessValidate("), gate.index("HeroLoadoutValidateForDetectedTownHall"))
        self.assertLess(gate.index("HeroLoadoutValidateForDetectedTownHall"), gate.rindex("Return True"))

    def test_identity_detector_uses_profile_level_and_rejects_conflicting_matches(self) -> None:
        detector = autoit_function(
            source("COCBot/functions/Image Search/imglocTHSearch.au3"),
            "imglocOwnVillageTownHallIdentity",
        )
        first_check = autoit_function(
            source("COCBot/functions/Village/BotDetectFirstTime.au3"),
            "BotDetectFirstTime",
        )
        self.assertIn("$iExpectedTownHallLevel = 0", source("COCBot/functions/Image Search/imglocTHSearch.au3"))
        self.assertIn("conflicting matches; identity was not accepted", detector)
        self.assertIn("$g_iTownHallLevel", first_check)
        call_index = first_check.index("imglocOwnVillageTownHallIdentity")
        assignment_index = first_check.index("$g_iTownHallLevel = $iDetectedTownHallLevel")
        self.assertGreater(assignment_index, call_index)

    def test_validator_is_pure(self) -> None:
        validator = source("COCBot/functions/Run/RunVillageReadiness.au3")
        self.assertNotIn("IniWrite", validator)
        self.assertNotIn("SaveConfig", validator)
        self.assertNotIn("FileWrite", validator)


if __name__ == "__main__":
    unittest.main()
