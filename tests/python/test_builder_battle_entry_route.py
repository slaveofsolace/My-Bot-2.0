import json
import pathlib
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


def builder_battle_entry_plan() -> dict:
    plan = planner_ui.default_plan()
    plan.update(
        {
            "run.surface": "builder",
            "run.strategy": "builder.battle-entry",
            "run.attack_script": "profile-current",
            "run.duration_minutes": 0,
            "run.max_battles": 0,
            "run.stop_on_star_bonus": False,
            "run.max_failures": 0,
            "run.heroes": [],
            "run.diagnostic_mode": True,
            "run.diagnostic_note": "supervised builder battle entry fixture",
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


class BuilderBattleEntryRouteTests(unittest.TestCase):
    def test_truthful_builder_battle_entry_plan_passes_server_preflight(self):
        self.assertEqual(planner_ui.engine_preflight(builder_battle_entry_plan()), [])

    def test_server_preflight_rejects_unsafe_builder_battle_entry_mixes(self):
        no_diagnostic = builder_battle_entry_plan()
        no_diagnostic["run.diagnostic_mode"] = False
        self.assertTrue(any("Builder battle entry proof requires supervised diagnostic" in problem for problem in planner_ui.engine_preflight(no_diagnostic)))

        resource_mix = builder_battle_entry_plan()
        resource_mix["events.collect_resources"] = True
        self.assertTrue(any("Builder battle entry proof cannot collect resources" in problem for problem in planner_ui.engine_preflight(resource_mix)))

        battle_mix = builder_battle_entry_plan()
        battle_mix["run.max_battles"] = 1
        self.assertTrue(any("Builder battle entry proof is one pre-search pass" in problem for problem in planner_ui.engine_preflight(battle_mix)))

        wrong_emulator = builder_battle_entry_plan()
        wrong_emulator["runtime.emulator"] = "auto"
        self.assertTrue(any("Builder battle entry proof currently requires BlueStacks 5" in problem for problem in planner_ui.engine_preflight(wrong_emulator)))

    def test_browser_contract_exposes_honest_builder_battle_entry_preset(self):
        browser = source("ui/planner.js")
        self.assertIn("'builder.battle-entry': {", browser)
        self.assertIn("'run.surface': 'builder', 'run.strategy': 'builder.battle-entry'", browser)
        self.assertIn("const builderBattleEntry = plan['run.strategy'] === 'builder.battle-entry';", browser)
        self.assertIn("'builder.battle-entry'", browser[browser.index("if (!['legacy.csv'"): browser.index("].includes(plan['run.strategy'])")])
        self.assertIn("Builder battle entry proof cannot collect resources, Home rewards, Loot Cart, or Treasury.", browser)
        self.assertIn("Builder battle entry proof is one pre-search pass; duration, battles, star bonus, and failure limits must be 0/off.", browser)
        self.assertIn("this proves the pre-search surface", source("config/ui/run-planner.settings.json"))

    def test_native_contract_delegates_before_regular_battle_imgloc_gate(self):
        contract = source("COCBot/functions/Run/RunExecutionContract.au3")
        validate = autoit_function(contract, "RunExecutionContractValidate")
        self.assertIn('BuilderBattleEntryRouteSelected($oIntent)', validate)
        self.assertLess(validate.index("BuilderBattleEntryRouteSelected($oIntent)"), validate.index('$sSurface <> "regular"'))
        self.assertLess(validate.index("BuilderBattleEntryRouteSelected($oIntent)"), validate.index("inherited ImgLoc remains disabled"))

        route = source("COCBot/functions/Run/BuilderBattleEntryRoute.au3")
        self.assertIn('$BUILDER_BATTLE_ENTRY_ROUTE_STRATEGY = "builder.battle-entry"', route)
        self.assertIn("Builder battle entry proof cannot collect resources", route)
        self.assertIn("Builder battle entry proof is exactly one pre-search pass", route)
        for forbidden in ("PrepareSearch", "CollectBuilderBase", "AttackBB", "SuggestedUpgrades", "CleanBBYard"):
            self.assertNotIn(forbidden, route)

    def test_native_execution_opens_and_closes_entry_without_search_or_battle(self):
        execution = source("COCBot/functions/Run/RunExecution.au3")
        route = autoit_function(execution, "BuilderBattleEntryRouteExecute")
        for expected in (
            "BuilderBattleEntryRouteAccountMatches($g_oRunExecutionIntent, $g_sProfileCurrentName)",
            "OpenBuilderBaseCollectorsProveBuilder()",
            "OpenHomeCollectorsProveHome()",
            "OpenBuilderBaseSwitchToBuilder()",
            "OpenBuilderBattleEntryIssueOpen()",
            "OpenBuilderBattleFindNowRegionReady(650, 455)",
            "OpenBuilderBattleEntryIssueClose()",
            "OpenBuilderBaseReturnHome()",
            'search_started=false; battle_started=false',
            "RunExecutionComplete($sReason)",
        ):
            self.assertIn(expected, route)
        for forbidden in (
            "PrepareSearch",
            "VillageSearch",
            "AttackMain",
            "CollectBuilderBase",
            "SwitchBetweenBases",
            "AttackBB",
            "SuggestedUpgrades",
            "CleanBBYard",
            "StarLaboratory",
            "UpgradeBattleMachine",
            "InitiateSwitchAcc",
        ):
            self.assertNotIn(forbidden, route)
        self.assertNotIn("ReturnHome(", route.replace("OpenBuilderBaseReturnHome(", ""))

        run_bot = autoit_function(source("MyBot.run.au3"), "runBot")
        self.assertLess(run_bot.index("BuilderBattleEntryRouteExecute()"), run_bot.index("_RunExecutionRunCurrentArmyOneBattle()"))
        self.assertLess(run_bot.index("BuilderBattleEntryRouteExecute()"), run_bot.index("InitiateSwitchAcc()"))

    def test_builder_battle_entry_start_uses_terminal_one_shot_before_engine_initialization(self):
        action = source("COCBot/MBR GUI Action.au3")
        bot_start = autoit_function(action, "BotStart")
        self.assertIn("If BuilderBattleEntryRouteSelected($oPreparedIntent) Then Return FuncReturn(_BotStartRunOneShot(9, $sStartError))", bot_start)
        self.assertLess(bot_start.index("BuilderBattleEntryRouteSelected($oPreparedIntent)"), bot_start.index("MBRFuncProbeEngine"))
        self.assertLess(bot_start.index("BuilderBattleEntryRouteSelected($oPreparedIntent)"), bot_start.index("MBRFuncInitialize"))

        selector = autoit_function(action, "_BotStartRunOneShot")
        self.assertIn("Case 9", selector)
        self.assertIn("_BotStartBuilderBattleEntryProof($sStartError)", selector)

        builder_start = autoit_function(action, "_BotStartBuilderBattleEntryProof")
        self.assertIn("RunExecutionApplyPrepared($sStartError)", builder_start)
        self.assertIn("BuilderBattleEntryRouteAccountMatches", builder_start)
        self.assertIn("_BotOpenHomeEnsureExactBlueStacks", builder_start)
        self.assertIn("OpenHomeStartupRecoveryWait(False)", builder_start)
        self.assertIn("Not OpenHomeCollectorsProveHome() And Not OpenBuilderBaseCollectorsProveBuilder()", builder_start)
        self.assertIn("RunExecutionBegin($sStartError)", builder_start)
        self.assertIn('RunControlReportStartOutcome(True, "Builder battle entry proof started")', builder_start)
        self.assertIn("Local $bResult = BuilderBattleEntryRouteExecute()", builder_start)
        self.assertIn('RunControlReportOneShotOutcome("completed", $sMessage)', builder_start)
        self.assertNotIn("MBRFuncInitialize", builder_start)
        self.assertNotIn("ForumAuthentication", builder_start)

    def test_no_premium_points_are_exact_and_frame_revalidated(self):
        policy = source("COCBot/functions/Run/NoPremiumPermitPolicy.au3")
        click = source("COCBot/functions/Other/Click.au3")
        recognizers = source("COCBot/functions/Run/OpenBuilderBaseCollectors.au3")
        self.assertIn('$NO_PREMIUM_ACTION_BUILDER_BATTLE_ENTRY_OPEN = "builder-base.battle-entry.open"', policy)
        self.assertIn('$NO_PREMIUM_ACTION_BUILDER_BATTLE_ENTRY_CLOSE = "builder-base.battle-entry.close"', policy)
        self.assertIn("$iX = 62 And $iY = 685", policy)
        self.assertIn("$iX = 748 And $iY = 204", policy)

        surface = autoit_function(click, "NoPremiumSurfaceState")
        self.assertIn("OpenBuilderBattleEntryOpenPointReady", surface)
        self.assertIn("OpenBuilderBattleEntryClosePointReady", surface)

        helper_scope = (
            autoit_function(recognizers, "OpenBuilderBattleEntryIssueOpen")
            + autoit_function(recognizers, "OpenBuilderBattleEntryIssueClose")
        )
        self.assertEqual(helper_scope.count("NoPremiumPointClick("), 2)
        self.assertIn("$OPEN_BUILDER_BATTLE_ENTRY_OPEN_X = 62", recognizers)
        self.assertIn("$OPEN_BUILDER_BATTLE_ENTRY_OPEN_Y = 685", recognizers)
        self.assertIn("$OPEN_BUILDER_BATTLE_ENTRY_CLOSE_X = 748", recognizers)
        self.assertIn("$OPEN_BUILDER_BATTLE_ENTRY_CLOSE_Y = 204", recognizers)
        self.assertIn("$NO_PREMIUM_ACTION_BUILDER_BATTLE_ENTRY_OPEN, $OPEN_BUILDER_BATTLE_ENTRY_OPEN_X, $OPEN_BUILDER_BATTLE_ENTRY_OPEN_Y", helper_scope)
        self.assertIn("$NO_PREMIUM_ACTION_BUILDER_BATTLE_ENTRY_CLOSE, $OPEN_BUILDER_BATTLE_ENTRY_CLOSE_X, $OPEN_BUILDER_BATTLE_ENTRY_CLOSE_Y", helper_scope)
        for forbidden in ("findImage(", "findMultiple(", "returnMultipleMatchesOwnVillage(", "Click(", "PureClick(", "GemClick("):
            self.assertNotIn(forbidden, helper_scope.replace("NoPremiumPointClick(", ""))

    def test_metadata_exposes_builder_battle_entry_as_pre_search_only(self):
        settings = json.loads(source("config/ui/run-planner.settings.json"))
        strategy = next(
            setting
            for section in settings["sections"]
            for setting in section["settings"]
            if setting["id"] == "run.strategy"
        )
        option = next(item for item in strategy["options"] if item["value"] == "builder.battle-entry")
        self.assertEqual(option["availability"], "gated")
        self.assertEqual(option["capability_ids"], ["builder-base.battles"])
        self.assertFalse(option["runtime_verified"])
        self.assertIn("pre-search surface", option["warning"])
        self.assertIn("never starts search", option["description"])


if __name__ == "__main__":
    unittest.main()
