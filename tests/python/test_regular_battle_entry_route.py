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


def regular_battle_entry_plan() -> dict:
    plan = planner_ui.default_plan()
    plan.update(
        {
            "run.surface": "regular",
            "run.strategy": "regular.battle-entry",
            "run.attack_script": "profile-current",
            "run.duration_minutes": 0,
            "run.max_battles": 0,
            "run.stop_on_star_bonus": False,
            "run.max_failures": 0,
            "run.heroes": [],
            "run.diagnostic_mode": True,
            "run.diagnostic_note": "supervised regular battle entry fixture",
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


class RegularBattleEntryRouteTests(unittest.TestCase):
    def test_truthful_regular_battle_entry_plan_passes_server_preflight(self):
        self.assertEqual(planner_ui.engine_preflight(regular_battle_entry_plan()), [])

    def test_server_preflight_rejects_unsafe_regular_battle_entry_mixes(self):
        no_diagnostic = regular_battle_entry_plan()
        no_diagnostic["run.diagnostic_mode"] = False
        self.assertTrue(
            any("Regular battle entry proof requires supervised diagnostic" in problem for problem in planner_ui.engine_preflight(no_diagnostic))
        )

        resource_mix = regular_battle_entry_plan()
        resource_mix["events.collect_resources"] = True
        self.assertTrue(
            any("Regular battle entry proof cannot collect resources" in problem for problem in planner_ui.engine_preflight(resource_mix))
        )

        battle_mix = regular_battle_entry_plan()
        battle_mix["run.max_battles"] = 1
        self.assertTrue(
            any("Regular battle entry proof is one pre-search pass" in problem for problem in planner_ui.engine_preflight(battle_mix))
        )

        wrong_emulator = regular_battle_entry_plan()
        wrong_emulator["runtime.emulator"] = "auto"
        self.assertTrue(
            any("Regular battle entry proof currently requires BlueStacks 5" in problem for problem in planner_ui.engine_preflight(wrong_emulator))
        )

    def test_browser_contract_exposes_honest_regular_battle_entry_preset(self):
        browser = source("ui/planner.js")
        self.assertIn("'regular.battle-entry': {", browser)
        self.assertIn("'run.surface': 'regular', 'run.strategy': 'regular.battle-entry'", browser)
        self.assertIn("const regularBattleEntry = plan['run.strategy'] === 'regular.battle-entry';", browser)
        self.assertIn("'regular.battle-entry'", browser[browser.index("if (!['legacy.csv'"): browser.index("].includes(plan['run.strategy'])")])
        self.assertIn("Regular battle-entry proof safety settings", browser)
        self.assertIn("cannot collect resources", browser)
        self.assertIn("Regular battle entry proof is one pre-search pass; duration, battles, star bonus, and failure limits must be 0/off.", browser)
        self.assertIn("this proves the Find a Match surface", source("config/ui/run-planner.settings.json"))

    def test_native_contract_delegates_before_battle_imgloc_gate(self):
        contract = source("COCBot/functions/Run/RunExecutionContract.au3")
        validate = autoit_function(contract, "RunExecutionContractValidate")
        self.assertIn("RegularBattleEntryRouteSelected($oIntent)", validate)
        self.assertLess(validate.index("RegularBattleEntryRouteSelected($oIntent)"), validate.index("inherited ImgLoc remains disabled"))

        route = source("COCBot/functions/Run/RegularBattleEntryRoute.au3")
        self.assertIn('$REGULAR_BATTLE_ENTRY_ROUTE_STRATEGY = "regular.battle-entry"', route)
        self.assertIn("Regular battle entry proof cannot collect resources", route)
        self.assertIn("Regular battle entry proof is exactly one pre-search pass", route)
        entry_validate = autoit_function(route, "RegularBattleEntryRouteValidate")
        for forbidden in ("PrepareSearch(", "VillageSearch", "AttackMain", "ReturnHome", "Collect", "DonateCC", "TrainSystem"):
            self.assertNotIn(forbidden, entry_validate)

    def test_native_execution_opens_and_closes_entry_without_find_match_or_battle(self):
        execution = source("COCBot/functions/Run/RunExecution.au3")
        route = autoit_function(execution, "RegularBattleEntryRouteExecute")
        for expected in (
            "RegularBattleEntryRouteAccountMatches($g_oRunExecutionIntent, $g_sProfileCurrentName)",
            "OpenHomeCollectorsProveHome()",
            "OpenRegularBattleEntryIssueOpen()",
            "PrepareSearchCurrentRegularFindMatchRegionReady(160, 470)",
            "OpenRegularBattleEntryIssueClose()",
            'find_match_clicked=false; battle_started=false',
            "RunExecutionComplete($sReason)",
        ):
            self.assertIn(expected, route)
        for forbidden in ("PrepareSearch(", "VillageSearch", "AttackMain", "ReturnHome", "_RunExecutionRunCurrentArmyOneBattle"):
            self.assertNotIn(forbidden, route)

        run_bot = autoit_function(source("MyBot.run.au3"), "runBot")
        self.assertLess(run_bot.index("RegularBattleEntryRouteExecute()"), run_bot.index("_RunExecutionRunCurrentArmyOneBattle()"))

    def test_start_uses_terminal_one_shot_before_engine_initialization(self):
        action = source("COCBot/MBR GUI Action.au3")
        bot_start = autoit_function(action, "BotStart")
        self.assertIn("If RegularBattleEntryRouteSelected($oPreparedIntent) Then Return FuncReturn(_BotStartRunOneShot(8, $sStartError))", bot_start)
        self.assertLess(bot_start.index("RegularBattleEntryRouteSelected($oPreparedIntent)"), bot_start.index("MBRFuncProbeEngine"))
        self.assertLess(bot_start.index("RegularBattleEntryRouteSelected($oPreparedIntent)"), bot_start.index("MBRFuncInitialize"))

        selector = autoit_function(action, "_BotStartRunOneShot")
        self.assertIn("Case 8", selector)
        self.assertIn("_BotStartRegularBattleEntryProof($sStartError)", selector)

        regular_start = autoit_function(action, "_BotStartRegularBattleEntryProof")
        self.assertIn("RunExecutionApplyPrepared($sStartError)", regular_start)
        self.assertIn("RegularBattleEntryRouteAccountMatches", regular_start)
        self.assertIn("_BotOpenHomeEnsureExactBlueStacks", regular_start)
        self.assertIn("OpenHomeStartupRecoveryWait(False)", regular_start)
        self.assertIn("OpenHomeCollectorsProveHome()", regular_start)
        self.assertIn("RunExecutionBegin($sStartError)", regular_start)
        self.assertIn('RunControlReportStartOutcome(True, "Regular battle entry proof started")', regular_start)
        self.assertIn("Local $bResult = RegularBattleEntryRouteExecute()", regular_start)
        self.assertNotIn("MBRFuncInitialize", regular_start)
        self.assertNotIn("ForumAuthentication", regular_start)

    def test_no_premium_points_are_exact_and_frame_revalidated(self):
        policy = source("COCBot/functions/Run/NoPremiumPermitPolicy.au3")
        click = source("COCBot/functions/Other/Click.au3")
        recognizers = source("COCBot/functions/Run/OpenHomeCollectors.au3")
        self.assertIn('$NO_PREMIUM_ACTION_REGULAR_BATTLE_ENTRY_OPEN = "regular.battle-entry.open"', policy)
        self.assertIn('$NO_PREMIUM_ACTION_REGULAR_BATTLE_ENTRY_CLOSE = "regular.battle-entry.close"', policy)
        self.assertIn("$iX = 62 And $iY = 685", policy)
        self.assertIn("$iX = 820 And $iY = 42", policy)

        surface = autoit_function(click, "NoPremiumSurfaceState")
        self.assertIn("OpenRegularBattleEntryOpenPointReady", surface)
        self.assertIn("OpenRegularBattleEntryClosePointReady", surface)

        helper_scope = (
            autoit_function(recognizers, "OpenRegularBattleEntryIssueOpen")
            + autoit_function(recognizers, "OpenRegularBattleEntryIssueClose")
        )
        self.assertEqual(helper_scope.count("NoPremiumPointClick("), 2)
        self.assertIn("$OPEN_REGULAR_BATTLE_ENTRY_OPEN_X = 62", recognizers)
        self.assertIn("$OPEN_REGULAR_BATTLE_ENTRY_OPEN_Y = 685", recognizers)
        self.assertIn("$OPEN_REGULAR_BATTLE_ENTRY_CLOSE_X = 820", recognizers)
        self.assertIn("$OPEN_REGULAR_BATTLE_ENTRY_CLOSE_Y = 42", recognizers)
        self.assertIn("$NO_PREMIUM_ACTION_REGULAR_BATTLE_ENTRY_OPEN, $OPEN_REGULAR_BATTLE_ENTRY_OPEN_X, $OPEN_REGULAR_BATTLE_ENTRY_OPEN_Y", helper_scope)
        self.assertIn("$NO_PREMIUM_ACTION_REGULAR_BATTLE_ENTRY_CLOSE, $OPEN_REGULAR_BATTLE_ENTRY_CLOSE_X, $OPEN_REGULAR_BATTLE_ENTRY_CLOSE_Y", helper_scope)
        for forbidden in ("findImage(", "findMultiple(", "returnMultipleMatchesOwnVillage(", "Click(", "PureClick(", "GemClick("):
            self.assertNotIn(forbidden, helper_scope.replace("NoPremiumPointClick(", ""))

    def test_metadata_exposes_regular_battle_entry_as_pre_search_only(self):
        settings = json.loads(source("config/ui/run-planner.settings.json"))
        strategy = next(
            setting
            for section in settings["sections"]
            for setting in section["settings"]
            if setting["id"] == "run.strategy"
        )
        option = next(item for item in strategy["options"] if item["value"] == "regular.battle-entry")
        self.assertEqual(option["availability"], "gated")
        self.assertEqual(option["capability_ids"], ["battle.regular-ranked-split"])
        self.assertFalse(option["runtime_verified"])
        self.assertIn("Find a Match surface", option["warning"])
        self.assertIn("never starts search", option["description"])


if __name__ == "__main__":
    unittest.main()
