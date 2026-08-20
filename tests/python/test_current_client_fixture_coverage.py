from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class CurrentClientFixtureCoverageTests(unittest.TestCase):
    def test_capture_guide_count_matches_the_authoritative_manifest(self) -> None:
        manifest = json.loads(
            (ROOT / "tests/fixtures/current-client/manifest.json").read_text(encoding="utf-8-sig")
        )
        guide = (ROOT / "docs/development/CAPTURING_FIXTURES.md").read_text(encoding="utf-8-sig")
        count = len(manifest["required_fixtures"])
        self.assertIn(f"current manifest defines {count} current-client fixture surfaces", guide)
        self.assertIn("The manifest is authoritative", guide)

    def test_readme_fixture_summary_matches_current_manifest_states(self) -> None:
        manifest = json.loads(
            (ROOT / "tests/fixtures/current-client/manifest.json").read_text(encoding="utf-8-sig")
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")
        states = [fixture["status"] for fixture in manifest["required_fixtures"]]
        verified = states.count("verified")
        redacted = states.count("redacted")
        missing = states.count("missing")
        self.assertIn(f"{verified + redacted} are complete and {missing} remain missing", readme)
        self.assertIn(
            f"{verified} reviewed fixtures replay through production recognizers and one additional training fixture is tracked as redacted",
            readme,
        )
        self.assertEqual(redacted, 1)
        self.assertNotIn("captures not yet supplied", readme)
        self.assertNotIn("all required current-client fixtures remain missing", readme)

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
            "village.treasury": "home.treasury.full",
            "events.daily-reward": "home.daily-reward",
            "village.donations": "clan.donation.structured-request",
            "village.clan-request": "clan.request.available",
            "village.upgrades-home": "home.upgrade.confirmation",
            "village.laboratory": "home.laboratory.ready",
            "army.training": "army.training.saved-recipe",
            "builder-base.upgrades": "builder.upgrades.list",
            "builder-base.battles": "builder.battle.entry",
            "events.clan-games": "home.clan-games.board",
            "orchestration.multi-account": "account.switcher.ready",
            "clan-capital.upgrades": "clan-capital.upgrades.ready",
            "village.pets": "home.pet-house.ready",
            "village.hero-equipment": "home.blacksmith.ready",
            "rewards.achievements": "home.achievements.ready",
            "rewards.personal-challenges": "home.personal-challenges.ready",
            "village.obstacles": "home.obstacle.ready",
            "clan-capital.forge": "clan-capital.forge.ready",
            "village.helper-hut": "home.helper-hut.ready",
            "builder-base.star-laboratory": "builder.star-laboratory.ready",
            "builder-base.resources": "builder.resources.ready",
            "rewards.magic-items": "home.trader.free-item",
            "rewards.streak-star-bonus": "home.streak-star-bonus",
            "village.boosts": "home.boost.ready",
            "heroes.upgrades": "home.hero-upgrade.ready",
            "builder-base.hero-upgrades": "builder.hero-upgrade.ready",
            "battle.trophy-drop": "battle.trophy-drop.ready",
            "battle.smart-zap": "battle.smart-zap.ready",
            "village.replay-share": "home.replay-share.ready",
            "village.profile-report": "home.profile-report.ready",
        }
        for capability_id, fixture_id in expected.items():
            self.assertIn(fixture_id, fixture_by_capability.get(capability_id, set()))


if __name__ == "__main__":
    unittest.main()
