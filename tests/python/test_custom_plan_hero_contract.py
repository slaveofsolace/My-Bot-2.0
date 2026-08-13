import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import planner_ui  # noqa: E402


PRESETS = json.loads((ROOT / "config" / "ui" / "run-planner.presets.json").read_text(encoding="utf-8"))
SETTINGS_SCHEMA = json.loads((ROOT / "config" / "ui" / "settings.schema.json").read_text(encoding="utf-8"))
PLANNER_JS = (ROOT / "ui" / "planner.js").read_text(encoding="utf-8")
PLANNER_HTML = (ROOT / "ui" / "planner.html").read_text(encoding="utf-8")
EXECUTION = (ROOT / "COCBot" / "functions" / "Run" / "RunExecution.au3").read_text(encoding="utf-8")
CONTRACT = (ROOT / "COCBot" / "functions" / "Run" / "RunExecutionContract.au3").read_text(encoding="utf-8")


class CustomPlanHeroContract(unittest.TestCase):
    def test_hero_option_unlock_metadata_is_declared_by_the_ui_schema(self):
        option_properties = SETTINGS_SCHEMA["$defs"]["option"]["properties"]
        self.assertEqual(
            option_properties["unlock_town_hall"],
            {"type": "integer", "minimum": 2, "maximum": 99},
        )
        self.assertEqual(option_properties["active_slot_eligible"], {"type": "boolean"})

    def test_every_town_hall_preset_replaces_a_contaminated_hero_selection(self):
        preserved = set(PRESETS["preserved_settings"])
        setting_ids = set(planner_ui.default_plan())
        for preset in PRESETS["presets"]:
            with self.subTest(preset=preset["id"]):
                values = {**PRESETS["common_values"], **preset["values"]}
                self.assertEqual(set(values), setting_ids - preserved)
                self.assertIn("run.heroes", values)
                self.assertEqual(values["run.town_hall"], preset["town_hall"])
                plan = planner_ui.default_plan()
                plan["run.town_hall"] = 18
                plan["run.heroes"] = ["barbarian-king", "archer-queen", "minion-prince", "grand-warden"]
                plan.update(values)
                clean, adjustments, rejected = planner_ui.validate_plan(plan)
                self.assertFalse(adjustments)
                self.assertFalse(rejected)
                self.assertEqual(clean["run.heroes"], values["run.heroes"])
                with tempfile.TemporaryDirectory() as folder:
                    target = pathlib.Path(folder) / "plan.json"
                    planner_ui.write_plan_atomic(clean, target)
                    persisted = json.loads(target.read_text(encoding="utf-8"))
                    self.assertEqual(persisted["run.heroes"], values["run.heroes"])
                    self.assertEqual(persisted["run.town_hall"], preset["town_hall"])

    def test_custom_town_hall_zero_defers_unlock_validation_to_fresh_start_detection(self):
        plan = planner_ui.default_plan()
        plan["run.town_hall"] = 0
        plan["run.heroes"] = ["archer-queen"]
        clean, adjustments, rejected = planner_ui.validate_plan(plan)
        self.assertFalse(adjustments)
        self.assertFalse(rejected)
        self.assertEqual(clean["run.town_hall"], 0)
        main = (ROOT / "MyBot.run.au3").read_text(encoding="utf-8-sig")
        self.assertIn("HeroLoadoutValidateForDetectedTownHall", main)
        self.assertIn("selected Heroes require a fresh visual Town Hall detection", main)

    def test_collectors_strategy_loads_only_a_visible_unsaved_safety_patch(self):
        self.assertIn("const STRATEGY_SAFETY_PATCHES", PLANNER_JS)
        self.assertIn("'home.collectors':", PLANNER_JS)
        self.assertIn("function applyStrategySafetyPatch(strategyId)", PLANNER_JS)
        body = PLANNER_JS.split("function applyStrategySafetyPatch(strategyId)", 1)[1].split("function ", 1)[0]
        self.assertIn("loaded ${changes.length} unsaved change", body)
        self.assertIn("PLAN[id] = clone(value)", body)
        for forbidden in ("fetch(", "savePlan(", "sendControl("):
            self.assertNotIn(forbidden, body)
        patch = PLANNER_JS.split("'home.collectors':", 1)[1].split("},", 1)[0]
        for preserved in ("runtime.emulator", "runtime.instance", "run.diagnostic_mode", "run.diagnostic_note"):
            self.assertNotIn(preserved, patch)

    def test_custom_plan_shows_an_explicit_hero_receipt(self):
        self.assertIn('Custom plan — your settings', PLANNER_HTML)
        self.assertIn("function selectedHeroLabels(plan = PLAN)", PLANNER_JS)
        self.assertIn("`Heroes: ${heroes.length ? heroes.join(', ') : 'none'}`", PLANNER_JS)
        self.assertIn("No Heroes are selected for deployment.", PLANNER_JS)
        self.assertIn("Selected Heroes deploy only when their attack-bar slots are present.", PLANNER_JS)

    def test_saved_preset_identity_is_recovered_and_preserved_operator_fields_do_not_clear_it(self):
        self.assertIn("function matchingPresetForPlan(plan = PLAN)", PLANNER_JS)
        self.assertIn("SELECTED_PRESET = matched?.id || 'custom'", PLANNER_JS)
        self.assertIn("if (settingId && preserved.has(settingId))", PLANNER_JS)
        self.assertIn("markPresetCustom(setting.id)", PLANNER_JS)

    def test_current_army_heroes_deploy_without_unprovable_hero_hall_wait(self):
        self.assertIn("Func RunExecutionHeroWaitMask(", CONTRACT)
        self.assertIn("If Not $bWaitForFullArmy Or Not $bManageTraining Then Return 0", CONTRACT)
        self.assertIn("$g_aiAttackUseHeroes[$iMode] = $iHeroMask", EXECUTION)
        self.assertIn("$g_aiSearchHeroWaitEnable[$iMode] = $iHeroWaitMask", EXECUTION)

    def test_standard_plan_owns_original_style_tactics_and_every_selected_actor(self):
        self.assertIn('If $sStrategy = "legacy.standard" Then', EXECUTION)
        self.assertIn("$g_abAttackStdSmartAttack[$iMode] = True", EXECUTION)
        self.assertIn("$g_aiAttackStdDropSides[$iMode] = 0", EXECUTION)
        self.assertIn("$g_abAttackDropCC[$iMode] = True", EXECUTION)
        self.assertIn("$g_abRunExecutionSnapshotAttackDropCC[$iMode] = $g_abAttackDropCC[$iMode]", EXECUTION)
        self.assertIn("$g_abAttackDropCC[$iMode] = $g_abRunExecutionSnapshotAttackDropCC[$iMode]", EXECUTION)

        algorithm = (ROOT / "COCBot/functions/Attack/Attack Algorithms/algorithm_AllTroops.au3").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("Func _AttackEnsurePlannedActorsDeployed()", algorithm)
        self.assertIn("_AttackDeploySelectedHeroesAtPoint($aActorBaseline, $iHeroMask, $iDropX, $iDropY)", algorithm)
        self.assertIn("_AttackDeployLiveSiegeAtPoint($aActorBaseline, $iDropX, $iDropY)", algorithm)
        self.assertIn("Click($iPortraitX, $iPortraitY", algorithm)
        self.assertIn("Func _AttackRefreshPlannedActorProof(", algorithm)
        self.assertIn("GetAttackBar(True, $g_iMatchMode)", algorithm)
        self.assertNotIn("$g_aiCmbCustomHeroOrder", algorithm.split("Func _AttackDeploySelectedHeroesAtPoint", 1)[1].split("EndFunc", 1)[0])
        for flag in ("$g_bDropKing", "$g_bDropQueen", "$g_bDropPrince", "$g_bDropWarden", "$g_bDropChampion"):
            self.assertIn(flag, algorithm)


if __name__ == "__main__":
    unittest.main()
