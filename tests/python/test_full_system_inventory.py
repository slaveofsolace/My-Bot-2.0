from __future__ import annotations

import unittest

from tools import generate_full_system_inventory


class FullSystemInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = generate_full_system_inventory.build_report()

    def test_every_authoritative_surface_is_included_once(self) -> None:
        report = self.report
        self.assertEqual([], report["errors"])
        self.assertEqual(
            {
                "capabilities": 61,
                "planner_settings": 48,
                "fixtures": 57,
                "compile_targets": 6,
                "control_actions": 6,
                "infrastructure_routes": 8,
                "actuator_owners": 464,
                "actuator_sites": 1178,
                "exact_current_capabilities_ready": 0,
                "capability_truth_statuses": {"BLOCKED_EXTERNAL": 53, "FIXTURE_PROVEN": 8},
                "fixture_truth_statuses": {"BLOCKED_EXTERNAL": 49, "FIXTURE_PROVEN": 8},
                "actuator_truth_statuses": {
                    "BLOCKED_EXTERNAL": 30,
                    "NOT_APPLICABLE": 181,
                    "UNSUPPORTED": 253,
                },
                "og_parity_sources": 339,
                "og_gui_sources": 65,
                "og_function_sources": 273,
                "og_unclassified_sources": 0,
            },
            report["counts"],
        )
        for key, identity in (
            ("capabilities", "id"),
            ("planner_settings", "id"),
            ("fixtures", "id"),
            ("control_actions", "id"),
            ("infrastructure_routes", "id"),
            ("actuator_owners", "owner"),
        ):
            values = [item[identity] for item in report[key]]
            self.assertEqual(len(values), len(set(values)), key)
        for key in (
            "capabilities",
            "planner_settings",
            "compile_targets",
            "control_actions",
            "infrastructure_routes",
        ):
            self.assertTrue(all(item["automated_tests"] for item in report[key]), key)

    def test_test_credit_comes_only_from_explicit_surface_mappings(self) -> None:
        report = self.report
        capabilities = {item["id"]: item for item in report["capabilities"]}
        controls = {item["id"]: item for item in report["control_actions"]}

        self.assertEqual(set(capabilities), set(generate_full_system_inventory.CAPABILITY_TESTS))
        self.assertEqual(set(controls), set(generate_full_system_inventory.CONTROL_ACTION_TESTS))
        self.assertEqual(
            [
                "tests/python/test_gameplay_scope_catalog.py",
                "tests/python/test_current_client_fixture_coverage.py",
            ],
            capabilities["army.recipes"]["automated_tests"],
        )
        self.assertEqual(
            [
                "tests/python/test_native_profile_autolaunch.py",
                "tests/python/test_launcher_recovery.py",
            ],
            controls["start"]["automated_tests"],
        )
        mappings = (
            generate_full_system_inventory.CAPABILITY_TESTS,
            generate_full_system_inventory.CONTROL_ACTION_TESTS,
            generate_full_system_inventory.COMPILE_TARGET_TESTS,
            generate_full_system_inventory.INFRASTRUCTURE_TESTS,
            generate_full_system_inventory.OG_SURFACE_TESTS,
            generate_full_system_inventory.CONFIGURATION_PERSISTENCE_TESTS,
        )
        for mapping in mappings:
            for tests in mapping.values():
                for path in tests:
                    self.assertTrue((generate_full_system_inventory.ROOT / path).is_file(), path)

    def test_missing_live_proof_is_never_promoted(self) -> None:
        report = self.report
        self.assertEqual(2, report["schema_version"])
        self.assertEqual(
            {"BLOCKED_EXTERNAL": 53, "FIXTURE_PROVEN": 8},
            report["counts"]["capability_truth_statuses"],
        )
        self.assertEqual(
            {"BLOCKED_EXTERNAL": 49, "FIXTURE_PROVEN": 8},
            report["counts"]["fixture_truth_statuses"],
        )
        self.assertEqual(
            {"BLOCKED_EXTERNAL": 30, "NOT_APPLICABLE": 181, "UNSUPPORTED": 253},
            report["counts"]["actuator_truth_statuses"],
        )
        self.assertTrue(all(item["truth_status"] != "DEFERRED" for item in report["capabilities"]))
        self.assertTrue(all(item["truth_status"] != "DEFERRED" for item in report["fixtures"]))
        self.assertTrue(all(item["truth_status"] != "DEFERRED" for item in report["control_actions"]))
        self.assertTrue(all(item["truth_status"] != "DEFERRED" for item in report["compile_targets"]))
        self.assertTrue(all(item["truth_status"] != "DEFERRED" for item in report["infrastructure_routes"]))

        capability_status = {item["id"]: item["truth_status"] for item in report["capabilities"]}
        self.assertEqual("BLOCKED_EXTERNAL", capability_status["events.daily-reward"])
        self.assertEqual("FIXTURE_PROVEN", capability_status["village.collectors"])
        self.assertEqual("BLOCKED_EXTERNAL", capability_status["village.treasury"])
        self.assertEqual("BLOCKED_EXTERNAL", capability_status["safety.no-gem-guard"])
        fixture_status = {item["id"]: item["truth_status"] for item in report["fixtures"]}
        self.assertEqual("FIXTURE_PROVEN", fixture_status["home.daily-reward"])
        self.assertEqual("BLOCKED_EXTERNAL", fixture_status["safety.gem-window"])
        self.assertTrue(all(item["runtime_status"] == "BLOCKED_EXTERNAL" for item in report["control_actions"]))
        self.assertTrue(all(item["installed_runtime_status"] == "BLOCKED_EXTERNAL" for item in report["compile_targets"]))

    def test_pinned_og_gui_settings_and_function_graph_is_complete(self) -> None:
        report = self.report
        self.assertEqual("8ad6e5a552347acc2fcb8048d30262e2735a0c33", report["pinned_og_commit"])
        self.assertEqual(339, len(report["og_parity"]))
        self.assertTrue(all(item["family"] for item in report["og_parity"]))
        dimensions = (
            "source_presence",
            "configuration_persistence",
            "compile_inclusion",
            "dispatch_reachability",
            "actuator_ownership",
            "stop_recovery",
            "deterministic_test",
        )
        allowed = {"PASS", "DEFERRED", "NOT_APPLICABLE", "FAIL"}
        for item in report["og_parity"]:
            self.assertTrue(all(dimension in item for dimension in dimensions), item["path"])
            self.assertTrue(all(item[dimension]["status"] in allowed for dimension in dimensions), item["path"])
            self.assertEqual(item["source_contract"], item["composite_status"], item["path"])
            self.assertEqual("BLOCKED_EXTERNAL", item["exact_current_runtime_status"], item["path"])
            self.assertEqual("BLOCKED_EXTERNAL", item["truth_status"], item["path"])
            self.assertIn("exact-current installed runtime evidence", item["truth_reason"], item["path"])
        self.assertTrue(all(item["source_presence"]["status"] == "PASS" for item in report["og_parity"]))
        self.assertFalse(any(item["source_contract"] == "FAIL" for item in report["og_parity"]))
        self.assertTrue(any(item["source_contract"] == "DEFERRED" for item in report["og_parity"]))
        self.assertTrue(
            any(
                item["compile_inclusion"]["status"] == "PASS"
                and item["dispatch_reachability"]["status"] == "DEFERRED"
                for item in report["og_parity"]
            )
        )
        self.assertTrue(
            all(
                item["compile_inclusion"]["status"] == "PASS"
                for item in report["og_parity"]
                if item["dispatch_reachability"]["status"] == "PASS"
            )
        )
        self.assertEqual(len(report["og_parity"]), len({item["path"] for item in report["og_parity"]}))

        by_path = {item["path"]: item for item in report["og_parity"]}
        self.assertEqual(
            "PASS",
            by_path["COCBot/functions/Config/saveConfig.au3"]["configuration_persistence"]["status"],
        )
        self.assertEqual(
            "DEFERRED",
            by_path["COCBot/functions/Config/readConfig.au3"]["configuration_persistence"]["status"],
        )
        self.assertEqual("PASS", by_path["MyBot.run.au3"]["dispatch_reachability"]["status"])

    def test_dispatch_requires_an_invoked_function_not_include_or_comment_presence(self) -> None:
        sources = {
            "MyBot.run.au3": (
                '#include "live.au3"\n'
                '#include "dynamic.au3"\n'
                '#include "dead.au3"\n'
                '#include "trap.au3"\n'
                "Live()\n"
                "Fake()\n"
                "LineFake()\n"
            ),
            "live.au3": (
                "Func Live()\n"
                '    Call("Dynamic")\n'
                "    Call($runtimeCallback)\n"
                '    Call("Trap" & $suffix)\n'
                '    $object.Call("Trap")\n'
                "EndFunc\n"
            ),
            "dynamic.au3": "Func Dynamic()\nEndFunc\n",
            "dead.au3": (
                "#cs\n"
                "Func Fake()\n"
                "    Trap()\n"
                "EndFunc\n"
                "#ce\n"
                "; Func LineFake()\n"
                "; EndFunc\n"
                "Func NeverInvoked()\n"
                "    Trap()\n"
                "EndFunc\n"
            ),
            "trap.au3": "Func Trap()\nEndFunc\n",
        }

        compiled, compile_evidence, dispatched, dispatch_evidence = (
            generate_full_system_inventory._autoit_reachability_from_sources(sources)
        )

        self.assertEqual(set(sources), compiled)
        self.assertTrue(all(path in compile_evidence for path in sources))
        self.assertEqual({"MyBot.run.au3", "live.au3", "dynamic.au3"}, dispatched)
        self.assertNotIn("dead.au3", dispatch_evidence)
        self.assertNotIn("trap.au3", dispatch_evidence)
        self.assertTrue(
            any("literal-call:Dynamic" in item for item in dispatch_evidence["dynamic.au3"])
        )


if __name__ == "__main__":
    unittest.main()
