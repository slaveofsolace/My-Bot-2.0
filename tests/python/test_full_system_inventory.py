from __future__ import annotations

import unittest

from tools import generate_full_system_inventory


class FullSystemInventoryTests(unittest.TestCase):
    def test_every_authoritative_surface_is_included_once(self) -> None:
        report = generate_full_system_inventory.build_report()
        self.assertEqual([], report["errors"])
        self.assertEqual(
            {
                "capabilities": 61,
                "planner_settings": 48,
                "fixtures": 56,
                "compile_targets": 6,
                "control_actions": 6,
                "infrastructure_routes": 8,
                "actuator_owners": 462,
                "actuator_sites": 1183,
                "exact_current_capabilities_ready": 0,
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

    def test_missing_live_proof_is_never_promoted(self) -> None:
        report = generate_full_system_inventory.build_report()
        self.assertTrue(all(item["final_status"] == "DEFERRED" for item in report["capabilities"]))
        self.assertTrue(all(item["runtime_status"] == "DEFERRED" for item in report["control_actions"]))
        self.assertTrue(all(item["installed_runtime_status"] == "DEFERRED" for item in report["compile_targets"]))

    def test_pinned_og_gui_settings_and_function_graph_is_complete(self) -> None:
        report = generate_full_system_inventory.build_report()
        self.assertEqual("8ad6e5a552347acc2fcb8048d30262e2735a0c33", report["pinned_og_commit"])
        self.assertEqual(339, len(report["og_parity"]))
        self.assertTrue(all(item["family"] for item in report["og_parity"]))
        self.assertTrue(all(item["source_contract"] == "PASS" for item in report["og_parity"]))
        self.assertTrue(all(item["exact_current_runtime_status"] == "DEFERRED" for item in report["og_parity"]))
        self.assertEqual(len(report["og_parity"]), len({item["path"] for item in report["og_parity"]}))


if __name__ == "__main__":
    unittest.main()
