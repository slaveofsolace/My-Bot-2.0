import json
import pathlib
import re
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import planner_ui  # noqa: E402


def source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8-sig")


def autoit_function(text: str, name: str) -> str:
    start = text.index(f"Func {name}(")
    return text[start : text.index("EndFunc", start)]


def regular_battle_scout_plan() -> dict:
    plan = planner_ui.default_plan()
    plan.update(
        {
            "run.surface": "regular",
            "run.strategy": "regular.battle-scout",
            "run.attack_script": "profile-current",
            "run.duration_minutes": 0,
            "run.max_battles": 1,
            "run.stop_on_star_bonus": False,
            "run.max_failures": 0,
            "run.heroes": [],
            "run.diagnostic_mode": True,
            "run.diagnostic_note": "supervised regular battle scout fixture",
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
            "pacing.retry_attempts": 0,
            "donate.mode": "off",
            "donate.keep_army": True,
            "donate.max_per_run": 0,
            "donate.request_when_short": False,
            "events.clan_games": False,
            "events.clan_games_point_cap": 0,
            "events.laboratory": "off",
            "events.collect_resources": False,
            "events.collect_loot_cart": False,
            "events.collect_treasury": False,
            "events.collect_daily_reward": False,
            "upgrade.policy": "disabled",
            "account.queue": "",
            "notify.channel": "log-only",
            "runtime.emulator": "bluestacks5",
            "runtime.instance": "Pie64",
        }
    )
    return plan


class RegularBattleScoutRouteTests(unittest.TestCase):
    def test_truthful_regular_battle_scout_plan_passes_server_preflight(self):
        self.assertEqual(planner_ui.engine_preflight(regular_battle_scout_plan()), [])

    def test_server_preflight_rejects_unsafe_scout_mixes(self):
        no_diagnostic = regular_battle_scout_plan()
        no_diagnostic["run.diagnostic_mode"] = False
        self.assertTrue(any("Regular battle scout requires supervised diagnostic" in problem for problem in planner_ui.engine_preflight(no_diagnostic)))

        resource_mix = regular_battle_scout_plan()
        resource_mix["events.collect_resources"] = True
        self.assertTrue(any("Regular battle scout cannot collect resources" in problem for problem in planner_ui.engine_preflight(resource_mix)))

        deployment_mix = regular_battle_scout_plan()
        deployment_mix["run.heroes"] = ["barbarian-king"]
        self.assertTrue(any("Regular battle scout cannot deploy or inspect Heroes" in problem for problem in planner_ui.engine_preflight(deployment_mix)))

        battle_count_mix = regular_battle_scout_plan()
        battle_count_mix["run.max_battles"] = 0
        self.assertTrue(any("Regular battle scout enters exactly one match" in problem for problem in planner_ui.engine_preflight(battle_count_mix)))

    def test_browser_preflight_exposes_scout_with_closed_world_constraints(self):
        browser = source("ui/planner.js")
        self.assertIn("'regular.battle-scout': {", browser)
        self.assertIn("'run.surface': 'regular', 'run.strategy': 'regular.battle-scout'", browser)
        self.assertIn("const regularBattleScout = plan['run.strategy'] === 'regular.battle-scout';", browser)
        self.assertIn("'regular.battle-scout'", browser[browser.index("if (!['legacy.csv'"): browser.index("].includes(plan['run.strategy'])")])
        self.assertIn("Regular battle scout enters exactly one match", browser)
        self.assertIn("cannot collect resources", browser)

    def test_native_contract_delegates_before_generic_imgloc_gate(self):
        contract = source("COCBot/functions/Run/RunExecutionContract.au3")
        validate = autoit_function(contract, "RunExecutionContractValidate")
        self.assertIn("RegularBattleScoutRouteSelected($oIntent)", validate)
        self.assertLess(validate.index("RegularBattleScoutRouteSelected($oIntent)"), validate.index("inherited ImgLoc remains disabled"))

        route = source("COCBot/functions/Run/RegularBattleEntryRoute.au3")
        self.assertIn('$REGULAR_BATTLE_SCOUT_ROUTE_STRATEGY = "regular.battle-scout"', route)
        self.assertIn("Regular battle scout cannot collect resources", route)
        self.assertIn("Regular battle scout enters exactly one match", route)

    def test_native_execution_scouts_without_deployment_or_imgloc_redline(self):
        execution = source("COCBot/functions/Run/RunExecution.au3")
        scout_scope = "\n".join(
            autoit_function(execution, name)
            for name in (
                "_RegularBattleScoutIssueFindMatch",
                "_RegularBattleScoutIssueCurrentArmyConfirmationIfPresent",
                "_RegularBattleScoutWaitForAttackPage",
                "_RegularBattleScoutReturnHome",
                "RegularBattleScoutRouteExecute",
            )
        )
        for expected in (
            "OpenRegularBattleEntryIssueOpen()",
            "PrepareSearchCurrentRegularFindMatchRegionReady(160, 470)",
            "$NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_FIND_MATCH, 160, 470",
            "$NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_CONFIRM_ARMY, 735, 508 + $g_iMidOffsetY",
            "$NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_END_BATTLE",
            "$NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_CONFIRM_SURRENDER",
            "$NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_RETURN_HOME",
            "SaveDebugImage(\"RegularBattleScoutEnemy\")",
            "deployment=false",
            "returned_home=true",
            "RunExecutionComplete($sReason)",
        ):
            self.assertIn(expected, scout_scope)
        for forbidden in ("PrepareSearch(", "VillageSearch", "AttackMain", "RunExecutionPrepareEnemyDeploymentView", "SearchRedLines", "DropTroop"):
            self.assertNotIn(forbidden, scout_scope)
        self.assertIsNone(re.search(r"(?<!Scout)ReturnHome\(", scout_scope))

        run_bot = autoit_function(source("MyBot.run.au3"), "runBot")
        self.assertLess(run_bot.index("RegularBattleScoutRouteExecute()"), run_bot.index("_RunExecutionRunCurrentArmyOneBattle()"))

    def test_start_uses_terminal_scout_before_engine_initialization(self):
        action = source("COCBot/MBR GUI Action.au3")
        bot_start = autoit_function(action, "BotStart")
        self.assertIn("If RegularBattleScoutRouteSelected($oPreparedIntent) Then Return FuncReturn(_BotStartRunOneShot(10, $sStartError))", bot_start)
        self.assertLess(bot_start.index("RegularBattleScoutRouteSelected($oPreparedIntent)"), bot_start.index("MBRFuncProbeEngine"))
        self.assertLess(bot_start.index("RegularBattleScoutRouteSelected($oPreparedIntent)"), bot_start.index("MBRFuncInitialize"))

        selector = autoit_function(action, "_BotStartRunOneShot")
        self.assertIn("Case 10", selector)
        self.assertIn("_BotStartRegularBattleScout($sStartError)", selector)

        scout_start = autoit_function(action, "_BotStartRegularBattleScout")
        self.assertIn("RunExecutionApplyPrepared($sStartError)", scout_start)
        self.assertIn("RegularBattleEntryRouteAccountMatches", scout_start)
        self.assertIn("_BotOpenHomeEnsureExactBlueStacks", scout_start)
        self.assertIn("OpenHomeCollectorsProveHome()", scout_start)
        self.assertIn("RunExecutionBegin($sStartError)", scout_start)
        self.assertIn('RunControlReportStartOutcome(True, "Regular battle scout started")', scout_start)
        self.assertIn("Local $bResult = RegularBattleScoutRouteExecute()", scout_start)
        self.assertNotIn("MBRFuncInitialize", scout_start)
        self.assertNotIn("ForumAuthentication", scout_start)

    def test_no_premium_points_are_exact_and_frame_revalidated(self):
        policy = source("COCBot/functions/Run/NoPremiumPermitPolicy.au3")
        click = source("COCBot/functions/Other/Click.au3")
        route = source("COCBot/functions/Run/RegularBattleEntryRoute.au3")
        prepare_search = source("COCBot/functions/Search/PrepareSearch.au3")
        for token in (
            '$NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_FIND_MATCH = "regular.battle-scout.find-match"',
            '$NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_CONFIRM_ARMY = "regular.battle-scout.confirm-army"',
            '$NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_END_BATTLE = "regular.battle-scout.end-battle"',
            '$NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_CONFIRM_SURRENDER = "regular.battle-scout.confirm-surrender"',
            '$NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_RETURN_HOME = "regular.battle-scout.return-home"',
            "$iX = 160 And $iY = 470",
            "$iX = 735 And $iY = 508 + _NoPremiumPermitMidOffsetY()",
            "$iX = 70 And $iY = 545 + _NoPremiumPermitBottomOffsetY()",
            "$iX = 535 And $iY = 435 + _NoPremiumPermitMidOffsetY()",
            "$iX = 430 And $iY = 566 + _NoPremiumPermitMidOffsetY()",
        ):
            self.assertIn(token, policy)

        surface = autoit_function(click, "NoPremiumSurfaceState")
        for token in (
            "PrepareSearchCurrentRegularFindMatchRegionReady",
            "PrepareSearchCurrentArmyConfirmationAttackPointReady",
            "RegularBattleScoutEndBattlePointReady",
            "RegularBattleScoutConfirmSurrenderPointReady",
            "RegularBattleScoutReturnHomePointReady",
        ):
            self.assertIn(token, surface)

        self.assertIn("Func PrepareSearchCurrentArmyConfirmationAttackPointReady", prepare_search)
        for name in ("RegularBattleScoutEndBattlePointReady", "RegularBattleScoutConfirmSurrenderPointReady", "RegularBattleScoutReturnHomePointReady"):
            self.assertIn(f"Func {name}", route)

    def test_metadata_exposes_regular_battle_scout_as_diagnostic_no_deployment(self):
        settings = json.loads(source("config/ui/run-planner.settings.json"))
        strategy = next(
            setting
            for section in settings["sections"]
            for setting in section["settings"]
            if setting["id"] == "run.strategy"
        )
        option = next(item for item in strategy["options"] if item["value"] == "regular.battle-scout")
        self.assertEqual(option["availability"], "gated")
        self.assertEqual(option["capability_ids"], ["battle.regular-ranked-split"])
        self.assertFalse(option["runtime_verified"])
        self.assertIn("enters one match", option["warning"])
        self.assertIn("never deploys troops", option["description"])


if __name__ == "__main__":
    unittest.main()
