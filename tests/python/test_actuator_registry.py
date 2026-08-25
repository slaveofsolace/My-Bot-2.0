from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from tools import validate_actuator_registry


ROOT = Path(__file__).resolve().parents[2]


class ActuatorRegistryTests(unittest.TestCase):
    def test_every_direct_actuator_owner_has_one_fail_closed_mapping(self) -> None:
        report = validate_actuator_registry.build_report()
        self.assertEqual([], report["errors"])
        self.assertEqual(468, report["owners"])
        self.assertEqual(73, report["sink_functions"])
        self.assertEqual(
            "2ef3e9bc6e540ebcb3c11be1185ac400531207b96701b2034e1389824ca91b5f",
            report["fingerprint"],
        )
        self.assertEqual(report["owners"], len(report["classifications"]))
        self.assertEqual(report["owners"], sum(report["owner_policy_counts"].values()))
        self.assertEqual(0, report["owner_policy_counts"]["unclassified"])
        self.assertGreater(report["owner_policy_counts"]["blocked"], 0)
        self.assertGreater(report["owner_policy_counts"]["capability"], 0)
        self.assertEqual(1, report["owner_policy_counts"]["test-only"])
        self.assertEqual(
            len(json.loads((ROOT / "config/actuator-registry.json").read_text(encoding="utf-8"))["mappings"]),
            sum(report["mapping_policy_counts"].values()),
        )

    def test_dynamic_dispatch_is_always_an_actuator_boundary(self) -> None:
        sinks = {"click": "Click", "dynamiccall": "DynamicCall"}
        self.assertEqual(
            {"DynamicCall"},
            validate_actuator_registry._line_sinks("Call($callback, 1)", sinks),
        )
        self.assertEqual(
            {"Click", "DynamicCall"},
            validate_actuator_registry._line_sinks('Call("Click", 1, 2)', sinks),
        )
        self.assertEqual(
            {"DynamicCall"},
            validate_actuator_registry._line_sinks('Call("RunControl" & "Poll")', sinks),
        )
        self.assertEqual(set(), validate_actuator_registry._line_sinks('DllCall("user32.dll")', sinks))
        self.assertEqual(set(), validate_actuator_registry._line_sinks('SetLog("Call($hidden)")', sinks))

    def test_intended_untracked_route_sources_are_inventoried(self) -> None:
        relative = {
            path.relative_to(ROOT).as_posix()
            for path in validate_actuator_registry._inventory_autoit_paths()
        }
        self.assertTrue(
            {
                "COCBot/functions/Run/ClanDonationOneRoute.au3",
                "COCBot/functions/Run/ExactRecipeTrainingRoute.au3",
                "COCBot/functions/Run/HomeUpgradeOneRoute.au3",
            }
            <= relative
        )

    def test_public_input_wrappers_expose_their_callers_to_policy(self) -> None:
        report = validate_actuator_registry.build_report()
        wrappers = {
            "ClickP", "BuildingClick", "ClickAway", "PureClickP", "GemClickP",
            "ClickDrag", "ClickB", "ClickButton", "TrainClick", "TrainClickP",
            "AndroidAdbSendShellCommand", "_WinAPI_PostMessage", "WinSetState",
        }
        registry = json.loads((ROOT / "config/actuator-registry.json").read_text(encoding="utf-8"))
        sinks = {name for group in registry["sink_groups"].values() for name in group}
        self.assertTrue(wrappers <= sinks)
        treasury = report["classifications"]["COCBot/functions/Village/TreasuryCollect.au3::TreasuryCollect"]
        self.assertEqual("blocked.legacy-treasury", treasury["mapping"])
        self.assertIn("ClickP", treasury["sinks"])

    def test_unmapped_dynamic_dispatch_fails_closed(self) -> None:
        owner = "COCBot/functions/Unmapped/NewRoute.au3::Run"
        with mock.patch.object(
            validate_actuator_registry,
            "scan_owners",
            return_value=({owner: {"DynamicCall"}}, [{"owner": owner, "line": 1, "sinks": ["DynamicCall"]}]),
        ):
            report = validate_actuator_registry.build_report()
        self.assertIn(f"unowned actuator: {owner} -> ['DynamicCall']", report["errors"])

    def test_gem_click_owners_are_never_capability_authorized(self) -> None:
        report = validate_actuator_registry.build_report()
        gem_owners = {
            owner: classification
            for owner, classification in report["classifications"].items()
            if "GemClick" in classification["sinks"]
        }
        self.assertEqual(
            {
                "COCBot/functions/Image Search/imglocCheckWall.au3::imglocCheckWall",
                "COCBot/functions/Other/Click.au3::GemClickP",
            },
            set(gem_owners),
        )
        self.assertEqual("blocked", gem_owners["COCBot/functions/Image Search/imglocCheckWall.au3::imglocCheckWall"]["policy"])
        self.assertEqual("infrastructure", gem_owners["COCBot/functions/Other/Click.au3::GemClickP"]["policy"])

    def test_scope_matrix_reports_current_owner_policy_counts(self) -> None:
        report = validate_actuator_registry.build_report()
        matrix = (ROOT / "docs/development/GAMEPLAY_SCOPE_MATRIX.md").read_text(
            encoding="utf-8"
        )
        expected = (
            f"covers {report['sites']:,} actuator call sites in {report['owners']} non-test AutoIt owners. "
            f"Of those owners, {report['owner_policy_counts']['capability']} are held by closed-world "
            f"capability routes, {report['owner_policy_counts']['blocked']} remain explicitly blocked, "
            f"{report['owner_policy_counts']['infrastructure']} are shared infrastructure, "
            f"{report['owner_policy_counts']['test-only']} is a compile-time test/reference owner, and "
            f"{report['owner_policy_counts']['unclassified']} are unclassified."
        )
        self.assertIn(expected, matrix)

    def test_ci_persists_the_actuator_progress_report(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn(
            "python tools/validate_actuator_registry.py --json > actuator-validation.json",
            workflow,
        )
        self.assertIn("            actuator-validation.json", workflow)

    def test_omitted_inherited_actuator_families_are_catalogued_but_not_supported(self) -> None:
        catalog = json.loads(
            (ROOT / "config/current-client-capabilities.json").read_text(encoding="utf-8-sig")
        )
        capabilities = {item["id"]: item for item in catalog["capabilities"]}
        expected = {
            "village.pets",
            "village.hero-equipment",
            "rewards.achievements",
            "rewards.personal-challenges",
            "village.obstacles",
            "clan-capital.forge",
            "village.helper-hut",
            "builder-base.star-laboratory",
            "builder-base.resources",
            "rewards.magic-items",
            "rewards.streak-star-bonus",
            "village.boosts",
            "heroes.upgrades",
            "builder-base.hero-upgrades",
            "battle.trophy-drop",
            "battle.smart-zap",
            "village.replay-share",
            "village.profile-report",
        }
        self.assertTrue(expected <= set(capabilities))
        for capability_id in expected:
            with self.subTest(capability_id=capability_id):
                self.assertEqual("legacy-implemented", capabilities[capability_id]["status"])
                self.assertEqual("required", capabilities[capability_id]["fixture_status"])
                self.assertEqual("required", capabilities[capability_id]["runtime_evidence"])


if __name__ == "__main__":
    unittest.main()
