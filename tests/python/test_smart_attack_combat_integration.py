import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


class SmartAttackCombatIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.combat = read("COCBot/functions/Attack/Attack Algorithms/SmartAttackCombat.au3")
        cls.policy = read("COCBot/functions/Attack/Attack Algorithms/SmartAttackPolicy.au3")
        cls.algorithm = read("COCBot/functions/Attack/Attack Algorithms/algorithm_AllTroops.au3")
        cls.redline = read("COCBot/functions/Attack/RedArea/GetPixelDropTroop.au3")
        cls.execution = read("COCBot/functions/Run/RunExecution.au3")
        cls.contract = read("COCBot/functions/Run/RunExecutionContract.au3")
        cls.hero = read("COCBot/functions/Attack/Troops/CheckHeroesHealth.au3")
        cls.waiter = read("COCBot/functions/Attack/GoldElixirChangeEBO.au3")
        cls.search = read("COCBot/functions/Search/VillageSearch.au3")
        cls.th_search = read("COCBot/functions/Image Search/imglocTHSearch.au3")
        cls.return_home = read("COCBot/functions/Attack/ReturnHome.au3")
        cls.event = read("COCBot/functions/Run/RunEvent.au3")
        cls.event_log = read("COCBot/functions/Run/RunEventLog.au3")
        cls.event_schema = json.loads(read("config/run-event.schema.json"))

    def test_planner_owns_and_restores_smart_spell_flags(self):
        for name in ("Rage", "Freeze"):
            snapshot = f"g_abRunExecutionSnapshotAttackUse{name}Spell"
            tactical = f"g_abAttackUse{name}Spell[$iMode]"
            self.assertIn(f"Global ${snapshot}", self.execution)
            self.assertIn(f"{tactical} = True", self.execution)
            self.assertRegex(
                self.execution,
                rf"{re.escape(tactical)}\s*=\s*\${snapshot}\[\$iMode\]",
            )

    def test_current_frame_side_policy_replaces_legacy_th_selector(self):
        self.assertNotIn("Return 5", self.contract.split("Func RunExecutionSmartDropSides", 1)[1].split("EndFunc", 1)[0])
        smart = self.algorithm.split("Func SmartAttackStrategy", 1)[1].split("EndFunc", 1)[0]
        self.assertLess(smart.index("_GetRedArea()"), smart.index("SmartAttackCombatSelectDeploymentSide()"))
        self.assertIn("Return False", smart)
        algorithm = self.algorithm.split("Func algorithm_AllTroops", 1)[1].split("EndFunc", 1)[0]
        self.assertIn("If Not SmartAttackStrategy($g_iMatchMode) Then", algorithm)
        self.assertLess(algorithm.index("If Not SmartAttackStrategy"), algorithm.index("Local $nbSides"))
        self.assertIn("SmartAttackPolicyChooseSide", self.combat)
        self.assertIn("SmartAttackCombatSelectedSide()", self.redline)
        self.assertIn("$SMART_ATTACK_SIDE_BL", self.redline)
        self.assertIn("$SMART_ATTACK_SIDE_TR", self.redline)
        self.assertIn("$SMART_ATTACK_SIDE_TL", self.redline)

    def test_smart_forces_fresh_town_hall_detection_and_proves_uniqueness(self):
        town_hall_block = self.search.split("FIND TARGET TOWNHALL", 1)[1].split("For $i = 0", 1)[0]
        self.assertIn("If RunExecutionSmartAttackEnabled() Then", town_hall_block)
        self.assertIn("FindTownhall(True, False)", town_hall_block)
        self.assertLess(
            town_hall_block.index("If RunExecutionSmartAttackEnabled() Then"),
            town_hall_block.index("ElseIf $match[$DB] Or $match[$LB] Then"),
        )
        self.assertIn("Local $maxReturnPoints = 3", self.th_search)
        self.assertIn("$g_bImglocTHUnique = (UBound($result) = 1)", self.th_search)
        self.assertIn("$g_bImglocTHUnique = False", self.th_search)
        self.assertIn("$g_bImglocTHUnique And $g_iImglocTHLevel > 0", self.combat)
        start = self.combat.split("Func SmartAttackCombatStart", 1)[1].split("EndFunc", 1)[0]
        self.assertIn("If $g_bImglocTHUnique And $g_iImglocTHLevel > 0", start)
        self.assertIn("$g_iSmartCombatTargetX = -1", start)
        self.assertIn("$g_iSmartCombatTargetY = -1", start)
        self.assertLess(start.index("$g_bImglocTHUnique"), start.index("$g_iSmartCombatTargetX = Int($g_iTHx)"))

    def test_hero_activation_is_armed_after_actor_proof_and_uses_fresh_coordinates(self):
        algorithm = self.algorithm.split("Func algorithm_AllTroops", 1)[1].split("EndFunc", 1)[0]
        self.assertLess(algorithm.index("_AttackEnsurePlannedActorsDeployed()"), algorithm.index("SmartAttackCombatStart("))
        self.assertIn("SmartAttackCombatArmSelectedHeroes()", self.combat)
        self.assertIn("SmartAttackPolicyHeroAbilityReason", self.combat)
        self.assertIn("FindImageInPlace2", self.combat)
        self.assertIn("SmartAttackCombatRememberHeroAbilityPoint", self.combat)
        self.assertIn("same-battle deployment-proven point=", self.combat)
        self.assertIn("_SmartAttackCombatActivateRememberedHero", self.combat)
        self.assertIn("SmartAttackCombatRememberHeroAbilityPoint", self.algorithm)
        self.assertIn('" ability command issued: "', self.event_log)
        self.assertIn('" ability not issued: "', self.event_log)
        self.assertIn("elapsed_ms=", self.combat)
        self.assertIn("destruction=", self.combat)
        hero_body = self.hero.split("Func CheckHeroesHealth()", 1)[1].split("EndFunc", 1)[0]
        self.assertIn("SmartAttackCombatTickHeroes", hero_body)
        self.assertLess(hero_body.index("SmartAttackCombatTickHeroes"), hero_body.index("Return"))
        self.assertLess(
            algorithm.index("_AttackConfirmStandardDeploymentGone()"),
            algorithm.index("SmartAttackCombatStart("),
        )

    def test_spell_casts_are_fresh_proven_and_bounded(self):
        self.assertNotIn("Random(", self.combat)
        self.assertIn("SmartAttackPolicyRageDecision", self.combat)
        self.assertIn("SmartAttackPolicyFreezeDecision", self.combat)
        self.assertIn("SmartAttackPolicyTargetSafetyDecision", self.combat)
        self.assertIn("SmartAttackPolicySelectAttackBarSlot", self.combat)
        self.assertIn("GetAttackBar(False", self.combat)
        self.assertIn("Further ", self.combat)
        self.assertIn(" clicks are disabled", self.combat)
        self.assertIn("_SmartAttackCombatReadStableSpell", self.combat)
        self.assertIn("two consecutive fresh", self.combat)
        self.assertIn("SmartAttackPolicySpellQuantityProved", self.combat)
        self.assertIn("did not match expected", self.combat)
        self.assertIn('"; quantity "', self.combat)
        self.assertIn("SmartAttackCombatTick(Number($CurDamage))", self.waiter)
        self.assertIn("SmartAttackCombatTickHeroes(Number($CurDamage))", self.waiter)

    def test_smart_final_hero_path_does_not_use_shifted_legacy_slots(self):
        end_block = self.return_home.split("If RunExecutionSmartAttackEnabled() Then", 1)[1]
        self.assertIn("SmartAttackCombatTickHeroes($g_iPercentageDamage, True)", end_block)
        self.assertLess(
            end_block.index("SmartAttackCombatTickHeroes"),
            end_block.index("ElseIf ($g_bCheckKingPower"),
        )
        self.assertIn("SmartAttackCombatReset()", self.return_home)

    def test_combat_event_types_match_schema(self):
        expected = {
            "combat.decision",
            "combat.hero-ability",
            "combat.spell-cast",
            "combat.spell-retained",
        }
        schema_types = set(self.event_schema["properties"]["type"]["enum"])
        self.assertTrue(expected <= schema_types)
        for event_type in expected:
            self.assertIn(f'"{event_type}"', self.event)
            self.assertIn(f'RunEventLogWrite("{event_type}"', self.event_log)


if __name__ == "__main__":
    unittest.main()
