import pathlib
import json
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "tools" / "run_supervised_battle_acceptance.ps1").read_text(encoding="utf-8")


class SupervisedBattleAcceptanceContract(unittest.TestCase):
    def test_requires_explicit_account_action_authorization(self):
        self.assertIn("[switch]$AuthorizeOneBattle", SCRIPT)
        self.assertIn("if (-not $AuthorizeOneBattle)", SCRIPT)

    def test_requires_exact_zoom_and_deployment_evidence(self):
        for marker in (
            "enemy zoom-out and [5-9][0-9]+ deployable red-line points verified",
            "live attack bar read 1/2 contains zero deployable troops",
            "live attack bar read 2/2 contains zero deployable troops",
            "deployable troops reduced to zero",
            "stop condition reached - battle-limit",
        ):
            self.assertIn(marker, SCRIPT)
        self.assertIn("deployment verification failed", SCRIPT)
        self.assertIn("could not send enemy zoom-out gesture", SCRIPT)
        self.assertIn("lost the attack page after zoom-out", SCRIPT)
        self.assertIn("could not prove deployable red-line geometry after zoom-out", SCRIPT)

    def test_requires_smart_side_heroes_and_both_spell_receipts(self):
        self.assertIn("$plan.'run.strategy' -ne 'smart.local'", SCRIPT)
        self.assertIn("Smart supervised acceptance requires at least one explicitly selected Hero", SCRIPT)
        self.assertNotIn("@('legacy.standard', 'smart.local')", SCRIPT)
        self.assertIn("Smart side .+ selected:", SCRIPT)
        self.assertIn("Smart combat started from", SCRIPT)
        self.assertIn("ability command issued:", SCRIPT)
        self.assertIn("ability not issued:", SCRIPT)
        self.assertIn("Require-ProvenSpellCast $result.events 'Rage'", SCRIPT)
        self.assertIn("Require-ProvenSpellCast $result.events 'Freeze'", SCRIPT)
        self.assertIn("combat.spell-retained", SCRIPT)
        self.assertIn("cast was not proven", SCRIPT)
        self.assertIn("Smart Attack retained", SCRIPT)

    def test_requires_one_event_and_clean_internal_stop(self):
        self.assertIn("Exactly one battle.completed event", SCRIPT)
        self.assertIn("Exactly one session.completed event", SCRIPT)
        self.assertIn("session.stopping", SCRIPT)
        self.assertIn("battle-limit", SCRIPT)
        self.assertIn("final.session_id", SCRIPT)

    def test_requires_human_visual_confirmation_after_automation(self):
        proof_offset = SCRIPT.index("$result.automated_proof = $true")
        review_offset = SCRIPT.index('Read-Host "Type exactly SMART DEPLOYMENT ABILITIES AND SPELLS CONFIRMED')
        pass_offset = SCRIPT.index("$result.pass = $true")
        self.assertLess(proof_offset, review_offset)
        self.assertLess(review_offset, pass_offset)

    def test_preserves_plan_emulator_and_binary_identity(self):
        self.assertIn("Saved plan changed during the run", SCRIPT)
        self.assertIn("BlueStacks process changed or exited", SCRIPT)
        self.assertIn("does not match binary provenance", SCRIPT)
        self.assertIn("BlueStacks5/Pie64", SCRIPT)
        self.assertIn("$preflightDeferredAttachment", SCRIPT)
        self.assertNotIn("-not $pre.emulator_attached -or -not $pre.window_attached -or -not $pre.adb_ready", SCRIPT)

        provenance = json.loads((ROOT / "config" / "binary-provenance.json").read_text(encoding="utf-8"))
        self.assertIn("artifacts", provenance)
        self.assertIn("$provenance.artifacts", SCRIPT)
        self.assertIn("$binaryRecord[0].bytes", SCRIPT)


if __name__ == "__main__":
    unittest.main()
