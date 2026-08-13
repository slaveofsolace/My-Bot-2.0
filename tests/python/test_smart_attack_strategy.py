import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


class SmartAttackStrategyTests(unittest.TestCase):
    def test_research_catalog_is_complete_and_offline(self):
        catalog = json.loads((ROOT / "config/game/smart-attack-strategies.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["strategy_id"], "smart.local")
        self.assertFalse(catalog["runtime_network_access"])
        self.assertEqual(catalog["runtime_side_policy"]["legacy_selector_override"], 0)
        self.assertFalse(catalog["safety"]["strategy_quality_verified"])
        self.assertEqual(catalog["safety"]["hero_ability_and_spell_policy_status"], "runtime-observed-th17")
        self.assertGreaterEqual(len(catalog["sources"]), 3)
        policies = catalog["town_hall_policies"]
        self.assertEqual([policy["town_hall"] for policy in policies], list(range(2, 19)))
        source_ids = {source["id"] for source in catalog["sources"]}
        for policy in policies:
            self.assertIn(policy["live_base_selector"], {0, 3, 5})
            self.assertIn(policy["dead_base_selector"], {0, 3})
            self.assertTrue(policy["recommended_army"])
            self.assertTrue(set(policy["source_ids"]) <= source_ids)
            self.assertIn("hero_plan", policy)
        self.assertTrue(catalog["safety"]["uses_only_current_trained_army"])
        self.assertFalse(catalog["safety"]["downloads_runtime_coordinates"])
        self.assertFalse(catalog["safety"]["uses_llm_in_actuator_loop"])
        self.assertFalse(catalog["safety"]["trains_recommended_army"])
        th17 = next(policy for policy in policies if policy["town_hall"] == 17)
        self.assertIn("Smart TH17 EDragon/Balloon", th17["reason"])
        self.assertIn("two stars, 55% destruction", th17["reason"])
        self.assertIn("not a controlled quality comparison", th17["reason"])

    def test_runtime_maps_smart_to_bounded_local_actuator(self):
        contract = (ROOT / "COCBot/functions/Run/RunExecutionContract.au3").read_text(encoding="utf-8", errors="replace")
        execution = (ROOT / "COCBot/functions/Run/RunExecution.au3").read_text(encoding="utf-8", errors="replace")
        algorithm = (ROOT / "COCBot/functions/Attack/Attack Algorithms/algorithm_AllTroops.au3").read_text(encoding="utf-8", errors="replace")
        combat = (ROOT / "COCBot/functions/Attack/Attack Algorithms/SmartAttackCombat.au3").read_text(encoding="utf-8", errors="replace")
        self.assertIn('$sStrategy <> "smart.local"', contract)
        self.assertIn('= "smart.local"', execution)
        self.assertIn("RunExecutionSmartDropSides", execution)
        self.assertIn("RunExecutionConfigureSmartAttackForMode($imode)", algorithm)
        selector = contract.split("Func RunExecutionSmartDropSides", 1)[1].split("EndFunc", 1)[0]
        self.assertNotIn("Return 5", selector)
        self.assertNotIn("Return 3", selector)
        self.assertIn("Return 0", selector)
        self.assertIn("SmartAttackPolicyChooseSide", combat)
        for forbidden in ("http://", "https://", "WinHttp", "InetRead", "OpenAI"):
            self.assertNotIn(forbidden, execution)

    def test_planner_exposes_the_strategy_honestly(self):
        settings = json.loads((ROOT / "config/ui/run-planner.settings.json").read_text(encoding="utf-8"))
        options = []
        for section in settings["sections"]:
            for setting in section["settings"]:
                if setting["id"] == "run.strategy":
                    options = setting["options"]
        smart = next(option for option in options if option["value"] == "smart.local")
        standard = next(option for option in options if option["value"] == "legacy.standard")
        self.assertEqual(standard["availability"], "gated")
        self.assertFalse(standard["runtime_verified"])
        self.assertIn("older-binary", standard["description"].lower())
        self.assertIn("current 438d43a1 source", standard["description"].lower())
        self.assertEqual(smart["availability"], "gated")
        self.assertFalse(smart["runtime_verified"])
        self.assertIn("local", smart["description"].lower())
        self.assertIn("older-binary bounded supervised th17 run", smart["description"].lower())
        self.assertIn("strategy quality", smart["description"].lower())
        self.assertIn("current 438d43a1 source", smart["description"].lower())
        self.assertIn("historical", smart["warning"].lower())

    def test_each_town_hall_preset_uses_its_smart_policy_and_exact_hero_plan(self):
        catalog = json.loads((ROOT / "config/game/smart-attack-strategies.json").read_text(encoding="utf-8"))
        presets = json.loads((ROOT / "config/ui/run-planner.settings.json").read_text(encoding="utf-8"))["presets"]["items"]
        by_th = {policy["town_hall"]: policy for policy in catalog["town_hall_policies"]}
        self.assertEqual([preset["town_hall"] for preset in presets], list(range(2, 19)))
        for preset in presets:
            with self.subTest(town_hall=preset["town_hall"]):
                policy = by_th[preset["town_hall"]]
                self.assertEqual(preset["compatibility"], "research-guided")
                self.assertEqual(preset["values"]["run.strategy"], "smart.local")
                self.assertEqual(preset["values"]["run.attack_script"], "profile-current")
                self.assertEqual(preset["values"]["run.heroes"], policy["hero_plan"])
                self.assertFalse(preset["values"]["army.manage_training"])
                self.assertTrue(preset["values"]["army.wait_for_full"])
                self.assertFalse(preset["values"]["army.train_spells"])
                self.assertFalse(preset["values"]["army.train_sieges"])
                self.assertEqual(preset["values"]["run.duration_minutes"], 0)
                self.assertEqual(preset["values"]["run.max_battles"], 1)
                self.assertIn("one supervised battle", preset["description"].lower())
                self.assertIn("current trained army", preset["description"].lower())
                self.assertIn("never changes its training queue", preset["description"].lower())
                self.assertIn(policy["recommended_army"], preset["source_note"])

    def test_battle_and_emulator_evidence_are_not_conflated(self):
        metadata = json.loads((ROOT / "config/ui/run-planner.settings.json").read_text(encoding="utf-8"))
        settings = {
            setting["id"]: setting
            for section in metadata["sections"]
            for setting in section.get("settings", [])
        }
        regular = next(item for item in settings["run.surface"]["options"] if item["value"] == "regular")
        bluestacks = next(item for item in settings["runtime.emulator"]["options"] if item["value"] == "bluestacks5")
        self.assertEqual(regular["availability"], "gated")
        self.assertFalse(regular["runtime_verified"])
        self.assertIn("current 438d43a1 source", regular["description"].lower())
        self.assertEqual(bluestacks["availability"], "gated")
        self.assertFalse(bluestacks["runtime_verified"])
        self.assertIn("older binary", bluestacks["description"].lower())
        self.assertIn("live human review", bluestacks["description"].lower())
        self.assertEqual(bluestacks["capability_ids"], ["emulator.bluestacks5"])


if __name__ == "__main__":
    unittest.main()
