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


def collectors_plan() -> dict:
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
            "run.diagnostic_note": "supervised collectors fixture",
            "target.gold": 0,
            "target.elixir": 0,
            "target.dark_elixir": 0,
            "army.source": "recipe",
            "army.recipe_name": "",
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
            "donate.max_per_run": 0,
            "donate.request_when_short": False,
            "events.clan_games": False,
            "events.clan_games_point_cap": 0,
            "events.laboratory": "off",
            "events.collect_resources": True,
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


class HomeMaintenanceRouteTest(unittest.TestCase):
    def test_truthful_collectors_plan_passes_server_preflight(self):
        self.assertEqual(planner_ui.engine_preflight(collectors_plan()), [])

    def test_collectors_require_an_exact_safe_emulator_instance(self):
        ambiguous = collectors_plan()
        ambiguous["runtime.emulator"] = "auto"
        ambiguous["runtime.instance"] = ""
        self.assertTrue(any("exact non-Auto emulator and instance" in problem for problem in planner_ui.engine_preflight(ambiguous)))

        unsafe = collectors_plan()
        unsafe["runtime.instance"] = "Pie64&wrong"
        self.assertTrue(any("unsupported characters" in problem for problem in planner_ui.engine_preflight(unsafe)))

    def test_route_fails_closed_without_explicit_selection_and_supervision(self):
        no_diagnostic = collectors_plan()
        no_diagnostic["run.diagnostic_mode"] = False
        self.assertTrue(any("supervised diagnostic" in problem for problem in planner_ui.engine_preflight(no_diagnostic)))

        generic_battle = collectors_plan()
        generic_battle.update(
            {
                "run.strategy": "legacy.standard",
                "run.max_battles": 1,
                "run.max_failures": 3,
                "army.wait_for_full": True,
            }
        )
        problems = planner_ui.engine_preflight(generic_battle)
        self.assertTrue(any("Home collection work requires the Home maintenance strategy" in problem for problem in problems))

        nothing_selected = collectors_plan()
        nothing_selected["events.collect_resources"] = False
        nothing_selected["events.collect_loot_cart"] = False
        nothing_selected["events.collect_treasury"] = False
        nothing_selected["events.collect_daily_reward"] = False
        self.assertTrue(any("choose exactly one available template-free task" in problem for problem in planner_ui.engine_preflight(nothing_selected)))

    def test_daily_reward_only_plan_fails_closed_in_server_preflight(self):
        plan = collectors_plan()
        plan["events.collect_resources"] = False
        plan["events.collect_daily_reward"] = True
        self.assertTrue(any("Daily Reward and Treasury remain unavailable" in problem for problem in planner_ui.engine_preflight(plan)))

    def test_loot_cart_only_plan_passes_server_preflight(self):
        plan = collectors_plan()
        plan["events.collect_resources"] = False
        plan["events.collect_loot_cart"] = True
        self.assertEqual(planner_ui.engine_preflight(plan), [])

        mixed = collectors_plan()
        mixed["events.collect_loot_cart"] = True
        self.assertTrue(any("choose exactly one available template-free task" in problem for problem in planner_ui.engine_preflight(mixed)))

    def test_treasury_only_plan_fails_closed_in_server_preflight(self):
        plan = collectors_plan()
        plan["events.collect_resources"] = False
        plan["events.collect_treasury"] = True
        self.assertTrue(any("Daily Reward and Treasury remain unavailable" in problem for problem in planner_ui.engine_preflight(plan)))

    def test_native_route_is_terminal_and_has_no_matchmaking_or_battle_calls(self):
        execution = source("COCBot/functions/Run/RunExecution.au3")
        route = autoit_function(execution, "HomeMaintenanceRouteExecute")
        self.assertIn("LootCartRouteRunAdapter", route)
        self.assertIn("TreasuryRouteRunAdapter", route)
        self.assertLess(route.index("LootCartRouteRunAdapter"), route.index("Collect(False, True)"))
        self.assertLess(route.index("TreasuryRouteRunAdapter"), route.index("Collect(False, True)"))
        self.assertIn("Collect(False, True)", route)
        self.assertIn("$iCollectorClicks = @extended", route)
        self.assertIn("RunEventLogMaintenanceHomeVerified($iCollectorClicks", route)
        self.assertNotIn("RunEventLogMaintenanceDailyRewardClickIssued", route)
        self.assertIn("RunEventLogMaintenanceDailyRewardUnconfirmed", route)
        self.assertIn("If $iCollectorClicks > 0 Then", route)
        self.assertIn("RunEventLogMaintenanceCollectorsCompleted($iCollectorClicks)", route)
        self.assertIn("RunEventLogMaintenanceCollectorsNoneActionable()", route)
        self.assertIn("RunSessionRequestStop", route)
        self.assertIn("btnStop()", route)
        for forbidden in (
            "PrepareSearch",
            "VillageSearch",
            "AttackMain",
            "ReturnHome",
            "DonateCC",
            "Laboratory",
            "Upgrade",
            "InitiateSwitchAcc",
        ):
            self.assertNotIn(forbidden, route)

        run_bot = autoit_function(source("MyBot.run.au3"), "runBot")
        self.assertLess(run_bot.index("HomeMaintenanceRouteExecute()"), run_bot.index("_RunExecutionRunCurrentArmyOneBattle()"))
        self.assertLess(run_bot.index("HomeMaintenanceRouteExecute()"), run_bot.index("InitiateSwitchAcc()"))

    def test_route_rechecks_exact_profile_and_emulator_instance(self):
        execution = source("COCBot/functions/Run/RunExecution.au3")
        route_source = source("COCBot/functions/Run/HomeMaintenanceRoute.au3")
        route = autoit_function(execution, "HomeMaintenanceRouteExecute")
        validate = autoit_function(route_source, "HomeMaintenanceRouteValidate")
        self.assertIn(
            "HomeMaintenanceRouteAccountMatches($g_oRunExecutionIntent, $g_sProfileCurrentName)",
            route,
        )
        self.assertIn("exact active profile/account binding", validate)
        self.assertIn('$sEmulator = "" Or $sEmulator = "auto"', validate)
        self.assertIn('$sInstance = ""', validate)
        self.assertIn('^[A-Za-z0-9_. -]{1,64}$', validate)

    def test_collector_adapter_rechecks_cancellation_and_home_screen(self):
        collect = autoit_function(source("COCBot/functions/Village/Collect.au3"), "Collect")
        self.assertIn("$bCollectorsOnly = False", collect)
        self.assertIn("If Not $g_bRunState Then Return SetExtended($iCollectorClicks, False)", collect)
        self.assertIn("If Not IsMainPage() Then Return SetExtended($iCollectorClicks, False)", collect)
        self.assertIn("Local $bMainScreenReady = checkMainScreen(False)", collect)
        self.assertIn(
            'If Click($aCollectXY[$t][0], $aCollectXY[$t][1], 1, 120, "#0430") Then $iCollectorClicks += 1',
            collect,
        )
        self.assertIn("Return SetExtended($iCollectorClicks, $bMainScreenReady And $g_bRunState)", collect)
        self.assertIn("If Not $bCollectorsOnly And $g_bChkCollectCartFirst", collect)
        self.assertIn("If Not $bCollectorsOnly And $g_bChkTreasuryCollect", collect)

    def test_plan_metadata_and_events_expose_only_the_bounded_route(self):
        settings = json.loads(source("config/ui/run-planner.settings.json"))
        strategy = next(
            setting
            for section in settings["sections"]
            for setting in section["settings"]
            if setting["id"] == "run.strategy"
        )
        option = next(item for item in strategy["options"] if item["value"] == "home.collectors")
        self.assertEqual(option["availability"], "gated")
        self.assertFalse(option["runtime_verified"])

        event_schema = json.loads(source("config/run-event.schema.json"))
        event_types = event_schema["properties"]["type"]["enum"]
        self.assertIn("maintenance.collectors.started", event_types)
        self.assertIn("maintenance.home-verified", event_types)
        self.assertIn("maintenance.collectors.completed", event_types)
        self.assertIn("maintenance.collectors.none-actionable", event_types)
        self.assertIn("maintenance.daily-reward.started", event_types)
        self.assertIn("maintenance.daily-reward.claim-issued", event_types)
        self.assertIn("maintenance.daily-reward.unavailable", event_types)
        self.assertIn("maintenance.daily-reward.unconfirmed", event_types)
        self.assertIn("maintenance.loot-cart.started", event_types)
        self.assertIn("maintenance.loot-cart.open-issued", event_types)
        self.assertIn("maintenance.loot-cart.collect-issued", event_types)
        self.assertIn("maintenance.loot-cart.unavailable", event_types)
        self.assertIn("maintenance.loot-cart.unconfirmed", event_types)
        self.assertIn("maintenance.loot-cart.home-verified", event_types)
        self.assertIn("maintenance.treasury.started", event_types)
        self.assertIn("maintenance.treasury.collect-issued", event_types)
        self.assertIn("maintenance.treasury.confirm-issued", event_types)
        self.assertIn("maintenance.treasury.unavailable", event_types)
        self.assertIn("maintenance.treasury.unconfirmed", event_types)
        self.assertIn("maintenance.treasury.home-verified", event_types)

        event_log = source("COCBot/functions/Run/RunEventLog.au3")
        completed = autoit_function(event_log, "RunEventLogMaintenanceCollectorsCompleted")
        none_actionable = autoit_function(event_log, "RunEventLogMaintenanceCollectorsNoneActionable")
        self.assertIn("If Int($iCollectorClicks) < 1 Then Return False", completed)
        self.assertIn('collector_clicks=" & Int($iCollectorClicks)', completed)
        self.assertIn("storage/threshold guards skipped every match", none_actionable)
        self.assertIn("collector_clicks=0", none_actionable)

        presets = json.loads(source("config/ui/run-planner.presets.json"))
        self.assertFalse(presets["common_values"]["events.collect_resources"])
        self.assertFalse(presets["common_values"]["events.collect_loot_cart"])
        self.assertFalse(presets["common_values"]["events.collect_treasury"])


if __name__ == "__main__":
    unittest.main()
