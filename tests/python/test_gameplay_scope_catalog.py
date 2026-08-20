import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class GameplayScopeCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / "config/current-client-capabilities.json").read_text(encoding="utf-8-sig"))
        self.capabilities = {item["id"]: item for item in self.catalog["capabilities"]}
        self.policies = self.catalog["runtime_evidence_policy"]["capabilities"]

    def test_every_mutating_live_route_requires_the_no_gem_contract(self):
        contract = self.catalog["runtime_evidence_policy"]["no_gem_contract"]
        self.assertEqual("2026-08-20T00:00:00Z", contract["effective_at"])
        self.assertEqual("gems.not-spent", contract["required_check"])
        self.assertEqual(
            {
                "army.training",
                "battle.fast-forward",
                "battle.legend-tiers",
                "battle.regular-ranked-split",
                "battle.revenge",
                "battle.smart-zap",
                "battle.trophy-drop",
                "builder-base.battles",
                "builder-base.hero-upgrades",
                "builder-base.resources",
                "builder-base.star-laboratory",
                "builder-base.upgrades",
                "clan-capital.forge",
                "clan-capital.upgrades",
                "events.clan-games",
                "events.daily-reward",
                "heroes.upgrades",
                "orchestration.battle-route",
                "rewards.achievements",
                "rewards.magic-items",
                "rewards.personal-challenges",
                "rewards.streak-star-bonus",
                "shop.chain-offers",
                "village.boosts",
                "village.clan-request",
                "village.collectors",
                "village.donations",
                "village.hero-equipment",
                "village.helper-hut",
                "village.laboratory",
                "village.loot-cart",
                "village.obstacles",
                "village.pets",
                "village.replay-share",
                "village.treasury",
                "village.upgrades-home",
            },
            set(contract["capabilities"]),
        )
        policies = self.catalog["runtime_evidence_policy"]["capabilities"]
        guarded = set(contract["capabilities"])
        for capability_id, policy in policies.items():
            requires_untouched_balance = any(
                "gems.untouched" in test["required_checks"]
                for test in policy["required_tests"]
            )
            if requires_untouched_balance and capability_id != "safety.no-gem-guard":
                self.assertIn(capability_id, guarded)

    def test_a_to_z_native_scopes_fail_closed_until_evidence_exists(self):
        expected = {
            "safety.no-gem-guard": "COCBot/functions/Run/OpenHomeCollectors.au3",
            "village.collectors": "COCBot/functions/Run/OpenHomeCollectors.au3",
            "village.loot-cart": "COCBot/functions/Run/LootCartRoute.au3",
            "village.treasury": "COCBot/functions/Run/TreasuryRoute.au3",
            "events.daily-reward": "COCBot/functions/Run/OpenHomeCollectors.au3",
            "village.donations": "COCBot/functions/Run/ClanDonationOneRoute.au3",
            "village.clan-request": "COCBot/functions/Run/ClanRequestRoute.au3",
            "army.training": "COCBot/functions/Run/ExactRecipeTrainingRoute.au3",
            "village.upgrades-home": "COCBot/functions/Run/HomeUpgradeOneRoute.au3",
            "builder-base.upgrades": "COCBot/functions/Village/BuilderBase/SuggestedUpgrades.au3",
            "builder-base.battles": "COCBot/functions/Attack/BuilderBase/AttackBB.au3",
            "village.laboratory": "COCBot/functions/Village/Laboratory.au3",
            "events.clan-games": "COCBot/functions/Village/Clan Games/ClanGames.au3",
            "orchestration.multi-account": "COCBot/functions/Village/SwitchAccount.au3",
            "runtime.recovery": "COCBot/functions/Main Screen/checkObstacles.au3",
            "clan-capital.upgrades": "COCBot/functions/Village/ClanCapital.au3",
            "village.pets": "COCBot/functions/Village/PetHouse.au3",
            "village.hero-equipment": "COCBot/functions/Village/Blacksmith.au3",
            "rewards.achievements": "COCBot/functions/Village/CollectAchievements.au3",
            "rewards.personal-challenges": "COCBot/functions/Village/Personal Challenges/DailyChallenges.au3",
            "village.obstacles": "COCBot/functions/Image Search/CheckTombs.au3",
            "clan-capital.forge": "COCBot/functions/Village/ClanCapital.au3",
            "village.helper-hut": "COCBot/functions/Village/HelperHut.au3",
            "builder-base.star-laboratory": "COCBot/functions/Village/BuilderBase/StarLaboratory.au3",
            "builder-base.resources": "COCBot/functions/Village/BuilderBase/Collect.au3",
            "rewards.magic-items": "COCBot/functions/Village/FreeMagicItems.au3",
            "rewards.streak-star-bonus": "COCBot/functions/Attack/ReturnHome.au3",
            "village.boosts": "COCBot/functions/Village/BoostStructure.au3",
            "heroes.upgrades": "COCBot/functions/Village/UpgradeHeroes.au3",
            "builder-base.hero-upgrades": "COCBot/functions/Village/BuilderBase/UpgradeBattleMachine.au3",
            "battle.trophy-drop": "COCBot/functions/Village/DropTrophy.au3",
            "battle.smart-zap": "COCBot/functions/Attack/SmartZap/smartZap.au3",
            "village.replay-share": "COCBot/functions/Village/ReplayShare.au3",
            "village.profile-report": "COCBot/functions/Village/ProfileReport.au3",
        }
        for capability_id, implementation in expected.items():
            with self.subTest(capability_id=capability_id):
                capability = self.capabilities[capability_id]
                self.assertEqual(capability["implementation"], implementation)
                self.assertTrue((ROOT / implementation).is_file())
                self.assertEqual(capability["runtime_evidence"], "required")
                self.assertTrue(self.policies[capability_id]["required_tests"])
                if capability_id not in {"runtime.recovery", "safety.no-gem-guard", "army.training", "village.collectors", "village.clan-request", "village.donations", "village.loot-cart", "village.treasury", "village.upgrades-home", "events.daily-reward"}:
                    self.assertEqual(capability["status"], "legacy-implemented")
                if capability_id != "runtime.recovery":
                    self.assertEqual(capability["fixture_status"], "required")
        self.assertEqual(self.capabilities["village.clan-request"]["status"], "engine-added")
        self.assertEqual(self.capabilities["village.collectors"]["status"], "engine-added")
        self.assertEqual(self.capabilities["village.loot-cart"]["status"], "engine-added")
        self.assertEqual(self.capabilities["village.treasury"]["status"], "engine-added")
        self.assertEqual(self.capabilities["events.daily-reward"]["status"], "engine-added")
        self.assertEqual(self.capabilities["safety.no-gem-guard"]["status"], "engine-added")

    def test_no_gem_guard_has_a_positive_fixture_and_exact_proof_contract(self):
        fixture_manifest = json.loads(
            (ROOT / "tests/fixtures/current-client/manifest.json").read_text(encoding="utf-8-sig")
        )
        fixture = next(item for item in fixture_manifest["required_fixtures"] if item["id"] == "safety.gem-window")
        self.assertEqual("missing", fixture["status"])
        self.assertEqual(["safety.no-gem-guard"], fixture["capability_ids"])
        policy = self.policies["safety.no-gem-guard"]["required_tests"]
        self.assertEqual(["game-surface-recognition", "end-to-end"], [item["test_type"] for item in policy])
        self.assertIn("gem-surface.recognized", policy[0]["required_checks"])
        self.assertIn("black-frame.rejected", policy[0]["required_checks"])
        self.assertIn("gems.untouched", policy[1]["required_checks"])

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
            "events.collect_loot_cart": "village.loot-cart",
            "events.collect_treasury": "village.treasury",
            "events.collect_daily_reward": "events.daily-reward",
        }
        planned = {"events.collect_treasury"}
        for setting_id, capability_id in expected.items():
            with self.subTest(setting_id=setting_id):
                setting = by_id[setting_id]
                expected_availability = (
                    "unsupported" if setting_id == "army.manage_training"
                    else "planned" if setting_id in planned
                    else "gated"
                )
                self.assertEqual(setting["availability"], expected_availability)
                self.assertFalse(setting["runtime_verified"])
                if setting_id == "events.collect_resources":
                    self.assertIn("historical packaged-binary receipt", setting["disabled_reason"].lower())
                    self.assertIn("no exact-current collector receipt", setting["disabled_reason"].lower())
                    self.assertIn("zero gem change", setting["disabled_reason"].lower())
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
