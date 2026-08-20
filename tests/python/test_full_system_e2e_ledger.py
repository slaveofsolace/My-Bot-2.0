from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools import generate_full_system_inventory


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "tests/evidence/system/full-system-e2e.20260820.json"


class FullSystemE2ELedgerTests(unittest.TestCase):
    def test_ledger_covers_every_inventory_facet_exactly_once(self) -> None:
        inventory = generate_full_system_inventory.build_report()
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        mappings = (
            ("capabilities", "id", "id"),
            ("planner_settings", "id", "id"),
            ("fixtures", "id", "id"),
            ("compile_targets", "output", "id"),
            ("control_actions", "id", "id"),
            ("infrastructure_routes", "id", "id"),
            ("actuator_owners", "owner", "id"),
        )
        for collection, inventory_id, ledger_id in mappings:
            expected = [item[inventory_id] for item in inventory[collection]]
            actual = [item[ledger_id] for item in ledger["facets"][collection]]
            self.assertEqual(len(expected), len(set(expected)), collection)
            self.assertEqual(len(actual), len(set(actual)), collection)
            self.assertEqual(set(expected), set(actual), collection)

    def test_runtime_claims_preserve_fail_closed_nonclaims(self) -> None:
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        runtime = ledger["runtime"]
        self.assertEqual("PASS", runtime["engine_check"]["verdict"])
        self.assertEqual(
            [
                "prepared", "pool-entered", "pool-returned", "max-entered",
                "max-returned", "android-entered", "android-returned",
                "gui-entered", "initialized",
            ],
            runtime["engine_check"]["phase_history"],
        )
        self.assertFalse(any(runtime["engine_check"][key] for key in (
            "emulator_attached", "window_attached", "adb_ready", "game_ready"
        )))
        self.assertEqual("PASS", runtime["engine_cancel"]["verdict"])
        self.assertTrue(runtime["engine_cancel"]["receipt_removed"])
        self.assertTrue(runtime["engine_cancel"]["cancel_removed"])
        actions = ledger["account_and_emulator_actions"]
        self.assertFalse(actions["BlueStacks_player_launched"])
        self.assertFalse(actions["game_opened"])
        self.assertFalse(actions["account_action_performed"])
        self.assertFalse(actions["gems_used"])
        self.assertFalse(actions["money_spent"])
        self.assertEqual("BLOCKED", ledger["package"]["public_distribution"])

    def test_missing_live_proof_remains_deferred(self) -> None:
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        capability_verdicts = {item["id"]: item["verdict"] for item in ledger["facets"]["capabilities"]}
        self.assertEqual("PASS", capability_verdicts["orchestration.engine-initialization"])
        self.assertEqual("PASS", capability_verdicts["runtime.recovery"])
        self.assertEqual(59, sum(value == "DEFERRED" for value in capability_verdicts.values()))
        control = {item["id"]: item["verdict"] for item in ledger["facets"]["control_actions"]}
        self.assertEqual("PASS", control["check-engine"])
        self.assertEqual("PASS", control["stop"])
        self.assertEqual("DEFERRED", control["start"])
        self.assertTrue(all(item["execution_verdict"] == "DEFERRED" for item in ledger["facets"]["planner_settings"]))


if __name__ == "__main__":
    unittest.main()
