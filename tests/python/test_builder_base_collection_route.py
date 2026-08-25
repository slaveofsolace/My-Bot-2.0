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


def builder_collectors_plan() -> dict:
    plan = planner_ui.default_plan()
    plan.update(
        {
            "run.surface": "builder",
            "run.strategy": "builder.collectors",
            "run.attack_script": "profile-current",
            "run.duration_minutes": 0,
            "run.max_battles": 0,
            "run.stop_on_star_bonus": False,
            "run.max_failures": 0,
            "run.heroes": [],
            "run.diagnostic_mode": True,
            "run.diagnostic_note": "supervised builder collection fixture",
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
            "pacing.break_every_minutes": 0,
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


class BuilderBaseCollectionRouteTest(unittest.TestCase):
    def test_truthful_builder_collection_plan_passes_server_preflight(self):
        self.assertEqual(planner_ui.engine_preflight(builder_collectors_plan()), [])

    def test_builder_collection_fails_closed_for_every_broader_route(self):
        plan = builder_collectors_plan()
        plan["run.diagnostic_mode"] = False
        self.assertTrue(any("supervised diagnostic" in item for item in planner_ui.engine_preflight(plan)))

        plan = builder_collectors_plan()
        plan["events.collect_daily_reward"] = True
        self.assertTrue(any("only Builder resource collection" in item for item in planner_ui.engine_preflight(plan)))

        plan = builder_collectors_plan()
        plan["run.max_battles"] = 1
        self.assertTrue(any("one pass" in item for item in planner_ui.engine_preflight(plan)))

        plan = builder_collectors_plan()
        plan["upgrade.policy"] = "suggested"
        self.assertTrue(any("upgrades disabled" in item for item in planner_ui.engine_preflight(plan)))

        plan = builder_collectors_plan()
        plan["donate.mode"] = "matching"
        self.assertTrue(any("donations and requests off" in item for item in planner_ui.engine_preflight(plan)))

        plan = builder_collectors_plan()
        plan["runtime.emulator"] = "auto"
        self.assertTrue(any("requires BlueStacks 5" in item for item in planner_ui.engine_preflight(plan)))

    def test_native_builder_route_is_template_free_and_no_premium_owned(self):
        route = source("COCBot/functions/Run/OpenBuilderBaseCollectors.au3")
        forbidden = (
            "findImage",
            "findMultiple",
            "QuickMIS",
            "MBRFunc",
            "$g_sImg",
            "DoAttackBB",
            "CollectBuilderBase",
            "GemClick",
            "PureClick",
            "ClickP(",
        )
        for token in forbidden:
            self.assertNotIn(token, route)
        self.assertIn("NoPremiumPointClick", route)
        self.assertIn("$NO_PREMIUM_ACTION_BUILDER_SWITCH", route)
        self.assertIn("$NO_PREMIUM_ACTION_BUILDER_COLLECT_GOLD", route)
        self.assertIn("$NO_PREMIUM_ACTION_BUILDER_COLLECT_ELIXIR", route)
        self.assertIn("$NO_PREMIUM_ACTION_BUILDER_RETURN", route)
        self.assertIn("OpenBuilderBaseResourceTargetReady", route)
        self.assertIn("OpenBuilderBaseReturnBoatPointReady", route)
        self.assertIn("$aIsOnBuilderBase", route)
        self.assertIn("green Gem Mine bubble", route)
        self.assertNotIn("COLLECT_GEM", route)
        self.assertNotIn("GEM_MINE", route)

    def test_builder_route_is_bound_to_start_contract_and_run_events(self):
        gui = source("COCBot/MBR GUI Action.au3")
        run = source("COCBot/functions/Run/RunExecution.au3")
        contract = source("COCBot/functions/Run/RunExecutionContract.au3")
        policy = source("COCBot/functions/Run/NoPremiumPermitPolicy.au3")
        events = json.loads(source("config/run-event.schema.json"))["properties"]["type"]["enum"]

        self.assertIn("OpenBuilderBaseCollectorsPreparedMode", gui)
        self.assertIn("Return FuncReturn(_BotStartRunOneShot(7", gui)
        self.assertIn("_BotStartOpenBuilderCollectors", gui)
        self.assertIn("BuilderMaintenanceRouteSelected", contract)
        self.assertIn("BuilderMaintenanceRouteValidate", contract)
        self.assertIn("BuilderMaintenanceRouteActive", run)
        self.assertIn("Builder Base maintenance", run)
        self.assertIn("NoPremiumPermitActionKnown", policy)
        self.assertIn('"builder-base.collect-gold"', policy)
        self.assertIn('"builder-base.collect-elixir"', policy)
        self.assertIn('"builder-base.return-home"', policy)

        self.assertIn("maintenance.builder-collectors.started", events)
        self.assertIn("maintenance.builder-collectors.resource-issued", events)
        self.assertIn("maintenance.builder-collectors.completed", events)

    def test_builder_collection_is_non_battle_and_does_not_require_attack_quota(self):
        intent = source("COCBot/functions/Run/RunIntent.au3")
        requires = autoit_function(intent, "RunIntentRequiresBattleQuota")
        can_start = autoit_function(intent, "RunIntentCanStart")

        self.assertIn('"builder.collectors"', requires)
        self.assertIn("Return False", requires)
        self.assertIn("If RunIntentRequiresBattleQuota($oIntent) Then", can_start)
        self.assertIn("BattleQuotaCanConsume", can_start)
        self.assertLess(can_start.index("RunIntentRequiresBattleQuota"), can_start.index("BattleQuotaCanConsume"))

    def test_ui_and_metadata_expose_builder_collection_without_claiming_battles(self):
        settings = json.loads(source("config/ui/run-planner.settings.json"))
        strategy = next(
            setting
            for section in settings["sections"]
            for setting in section["settings"]
            if setting["id"] == "run.strategy"
        )
        option = next(item for item in strategy["options"] if item["value"] == "builder.collectors")
        self.assertEqual(option["availability"], "gated")
        self.assertFalse(option["runtime_verified"])
        self.assertEqual(option["capability_ids"], ["builder-base.resources"])
        self.assertIn("Gem Mine", option["warning"])
        self.assertIn("at most two resource clicks", option["description"])

        planner_js = source("ui/planner.js")
        self.assertIn("'builder.collectors'", planner_js)
        self.assertIn("Builder Base collection is available as one bounded supervised pass", planner_js)
        self.assertIn("Builder battles, Builder upgrades, Gem Mine", planner_js)


if __name__ == "__main__":
    unittest.main()
