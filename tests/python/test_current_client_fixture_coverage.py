from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class CurrentClientFixtureCoverageTests(unittest.TestCase):
    def test_every_fixture_required_capability_has_a_named_capture(self) -> None:
        capabilities = json.loads(
            (ROOT / "config/current-client-capabilities.json").read_text(encoding="utf-8-sig")
        )["capabilities"]
        manifest = json.loads(
            (ROOT / "tests/fixtures/current-client/manifest.json").read_text(encoding="utf-8-sig")
        )
        mapped = {
            capability_id
            for fixture in manifest["required_fixtures"]
            for capability_id in fixture["capability_ids"]
        }
        required = {
            capability["id"]
            for capability in capabilities
            if capability.get("fixture_status") == "required"
        }
        self.assertEqual(set(), required - mapped)

    def test_a_to_z_maintenance_surfaces_have_specific_fixture_targets(self) -> None:
        manifest = json.loads(
            (ROOT / "tests/fixtures/current-client/manifest.json").read_text(encoding="utf-8-sig")
        )
        fixture_by_capability = {}
        for fixture in manifest["required_fixtures"]:
            for capability_id in fixture["capability_ids"]:
                fixture_by_capability.setdefault(capability_id, set()).add(fixture["id"])

        expected = {
            "village.collectors": "home.maintenance.ready",
            "village.loot-cart": "home.loot-cart",
            "events.daily-reward": "home.daily-reward",
            "village.donations": "home.maintenance.ready",
            "village.clan-request": "home.maintenance.ready",
            "village.upgrades-home": "home.maintenance.ready",
            "village.laboratory": "home.laboratory.ready",
            "army.training": "army.training.ready",
            "builder-base.upgrades": "builder.upgrades.list",
            "builder-base.battles": "builder.battle.entry",
            "events.clan-games": "home.clan-games.board",
            "orchestration.multi-account": "account.switcher.ready",
            "clan-capital.upgrades": "clan-capital.upgrades.ready",
        }
        for capability_id, fixture_id in expected.items():
            self.assertIn(fixture_id, fixture_by_capability.get(capability_id, set()))


if __name__ == "__main__":
    unittest.main()
