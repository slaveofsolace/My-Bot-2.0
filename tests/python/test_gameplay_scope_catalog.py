import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class GameplayScopeCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / "config/current-client-capabilities.json").read_text(encoding="utf-8-sig"))
        self.capabilities = {item["id"]: item for item in self.catalog["capabilities"]}
        self.policies = self.catalog["runtime_evidence_policy"]["capabilities"]

    def test_a_to_z_native_scopes_fail_closed_until_evidence_exists(self):
        expected = {
            "village.collectors": "COCBot/functions/Village/Collect.au3",
            "events.daily-reward": "COCBot/functions/Main Screen/checkObstacles.au3",
            "village.donations": "COCBot/functions/Village/DonateCC.au3",
            "village.clan-request": "COCBot/functions/Run/ClanRequestRoute.au3",
            "army.training": "COCBot/functions/CreateArmy/TrainSystem.au3",
            "village.upgrades-home": "COCBot/functions/Village/Auto Upgrade.au3",
            "builder-base.upgrades": "COCBot/functions/Village/BuilderBase/SuggestedUpgrades.au3",
            "builder-base.battles": "COCBot/functions/Attack/BuilderBase/AttackBB.au3",
            "village.laboratory": "COCBot/functions/Village/Laboratory.au3",
            "events.clan-games": "COCBot/functions/Village/Clan Games/ClanGames.au3",
            "orchestration.multi-account": "COCBot/functions/Village/SwitchAccount.au3",
            "runtime.recovery": "COCBot/functions/Main Screen/checkObstacles.au3",
            "clan-capital.upgrades": "COCBot/functions/Village/ClanCapital.au3",
        }
        for capability_id, implementation in expected.items():
            with self.subTest(capability_id=capability_id):
                capability = self.capabilities[capability_id]
                self.assertEqual(capability["implementation"], implementation)
                self.assertTrue((ROOT / implementation).is_file())
                self.assertEqual(capability["runtime_evidence"], "required")
                self.assertTrue(self.policies[capability_id]["required_tests"])
                if capability_id not in {"runtime.recovery", "village.clan-request", "events.daily-reward"}:
                    self.assertEqual(capability["status"], "legacy-implemented")
                if capability_id != "runtime.recovery":
                    self.assertEqual(capability["fixture_status"], "required")
        self.assertEqual(self.capabilities["village.clan-request"]["status"], "engine-added")
        self.assertEqual(self.capabilities["events.daily-reward"]["status"], "engine-added")

    def test_memu_is_static_only_and_names_exact_runtime_gate(self):
        capability = self.capabilities["emulator.memu"]
        policy = self.policies["emulator.memu"]
        self.assertEqual(capability["status"], "adapter-added")
        self.assertEqual(capability["implementation"], "COCBot/functions/Android/AndroidMEmu.au3")
        self.assertEqual(policy["environment_patterns"]["emulator"], r"(?i)^memu(?:\s|$)")
        self.assertEqual(
            policy["required_tests"][0]["required_checks"],
            ["emulator.detected", "instance.bound", "adb.connected", "background.capture", "game.ready"],
        )

    def test_planner_and_provenance_point_to_the_reviewed_memu_reference(self):
        settings = json.loads((ROOT / "config/ui/run-planner.settings.json").read_text(encoding="utf-8-sig"))
        emulator = next(
            setting
            for section in settings["sections"]
            for setting in section["settings"]
            if setting["id"] == "runtime.emulator"
        )
        memu = next(option for option in emulator["options"] if option["value"] == "memu")
        self.assertEqual(memu["availability"], "gated")
        self.assertFalse(memu["runtime_verified"])
        self.assertEqual(memu["capability_ids"], ["emulator.memu"])

        lock = json.loads((ROOT / "upstreams.lock.json").read_text(encoding="utf-8-sig"))
        reference = next(source for source in lock["sources"] if source["id"] == "mybot-py-memu-reference")
        self.assertEqual(reference["repository"], "evgmalkov/mybot-py")
        self.assertEqual(reference["commit"], "ae24b6d99d522730ab2822282563af764dfa9f5a")
        self.assertEqual(reference["license"], "MIT")

    def test_scope_document_never_equates_source_presence_with_support(self):
        document = (ROOT / "docs/development/GAMEPLAY_SCOPE_MATRIX.md").read_text(encoding="utf-8")
        self.assertIn("source path means **implemented**", document)
        self.assertIn("support requires current recognition fixtures", document)
        self.assertIn("No gems, purchases", document)

    def test_active_maintenance_switches_publish_setting_level_evidence(self):
        settings = json.loads((ROOT / "config/ui/run-planner.settings.json").read_text(encoding="utf-8-sig"))
        by_id = {
            setting["id"]: setting
            for section in settings["sections"]
            for setting in section["settings"]
        }
        expected = {
            "army.manage_training": "army.training",
            "donate.request_when_short": "village.clan-request",
            "events.clan_games": "events.clan-games",
            "events.collect_resources": "village.collectors",
            "events.collect_daily_reward": "events.daily-reward",
        }
        for setting_id, capability_id in expected.items():
            with self.subTest(setting_id=setting_id):
                setting = by_id[setting_id]
                expected_availability = "unsupported" if setting_id == "army.manage_training" else "gated"
                self.assertEqual(setting["availability"], expected_availability)
                self.assertFalse(setting["runtime_verified"])
                self.assertEqual(setting["capability_ids"], [capability_id])
                self.assertTrue(setting["prerequisites"])
                self.assertTrue(setting["disabled_reason"])

        self.assertFalse(by_id["army.manage_training"]["native_fixed_value"])
        self.assertIn("closed-world", by_id["army.manage_training"]["native_fixed_reason"])

        planner = (ROOT / "ui/planner.js").read_text(encoding="utf-8-sig")
        self.assertIn("settingEvidenceActive", planner)
        self.assertIn("setting.availability && !same(plan[setting.id], setting.default)", planner)
        self.assertGreaterEqual(planner.count("option.availability === 'gated' && !plan['run.diagnostic_mode']"), 2)

    def test_planner_capability_links_match_the_surface_being_gated(self):
        settings = json.loads((ROOT / "config/ui/run-planner.settings.json").read_text(encoding="utf-8-sig"))
        by_id = {
            setting["id"]: setting
            for section in settings["sections"]
            for setting in section["settings"]
        }

        def option_capabilities(setting_id, value):
            option = next(item for item in by_id[setting_id]["options"] if item["value"] == value)
            return set(option["capability_ids"])

        self.assertEqual(option_capabilities("run.surface", "builder"), {"builder-base.battles"})
        self.assertEqual(option_capabilities("run.strategy", "builder.baby-dragon"), {"builder-base.battles"})
        self.assertEqual(option_capabilities("run.strategy", "home.clan-request"), {"village.clan-request"})
        self.assertEqual(option_capabilities("events.laboratory", "cheapest"), {"village.laboratory"})
        self.assertEqual(option_capabilities("events.laboratory", "priority-list"), {"village.laboratory"})
        self.assertEqual(option_capabilities("upgrade.policy", "suggested"), {"village.upgrades-home"})
        self.assertIn("village.upgrades-home", option_capabilities("upgrade.policy", "walls"))
        self.assertIn("village.upgrades-home", option_capabilities("upgrade.policy", "all"))
        self.assertIn("village.laboratory", option_capabilities("upgrade.policy", "all"))
        for value in ("matching", "anything"):
            self.assertEqual(
                option_capabilities("donate.mode", value),
                {"village.donations", "chat.global-chat"},
            )


if __name__ == "__main__":
    unittest.main()
