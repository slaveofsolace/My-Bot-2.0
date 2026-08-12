import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "COCBot/functions/Attack/Attack Algorithms/SmartAttackPolicy.au3"
AUTOIT_TEST = ROOT / "tests/autoit/SmartAttackPolicyTest.au3"


def _find_windows_tool(name: str, relative_candidates: tuple[str, ...]) -> str | None:
    discovered = shutil.which(name)
    if discovered:
        return discovered
    roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]
    for root in filter(None, roots):
        for relative in relative_candidates:
            candidate = Path(root) / relative
            if candidate.is_file():
                return str(candidate)
    return None


class SmartAttackPolicySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = POLICY.read_text(encoding="utf-8-sig")

    def test_policy_is_isolated_and_side_effect_free(self):
        self.assertNotRegex(self.source, r"(?im)^#include\s")
        self.assertIn("#include-once", self.source.lower())
        for forbidden in (
            "Random(",
            "SetSleep",
            "_Sleep(",
            "Click(",
            "AttackClick(",
            "Mouse",
            "InetRead",
            "http://",
            "https://",
        ):
            self.assertNotIn(forbidden, self.source)

    def test_stable_integration_apis_exist(self):
        for signature in (
            "Func SmartAttackPolicyChooseSide(",
            "Func SmartAttackPolicyTargetPoint(",
            "Func SmartAttackPolicyTargetSafetyDecision(",
            "Func SmartAttackPolicyHeroAbilityReason(",
            "Func SmartAttackPolicyHeroAbilityDecision(",
            "Func SmartAttackPolicySelectAttackBarSlot(",
            "Func SmartAttackPolicyRageDecision(",
            "Func SmartAttackPolicyFreezeDecision(",
        ):
            self.assertIn(signature, self.source)

    def test_side_tie_order_and_scores_are_explicit(self):
        function = re.search(
            r"(?ims)^Func SmartAttackPolicyChooseSide\b.*?^EndFunc\b",
            self.source,
        )
        self.assertIsNotNone(function)
        body = function.group(0)
        offsets = [
            body.index("$aBRMetrics, $SMART_ATTACK_SIDE_BR"),
            body.index("$aBLMetrics, $SMART_ATTACK_SIDE_BL"),
            body.index("$aTRMetrics, $SMART_ATTACK_SIDE_TR"),
            body.index("$aTLMetrics, $SMART_ATTACK_SIDE_TL"),
        ]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("$fScore < $fBestScore", self.source)
        self.assertIn("$fScore > $fBestScore", self.source)
        self.assertIn('"nearest-median-to-town-hall"', body)
        self.assertIn('"longest-valid-side-dead-base"', body)

    def test_thresholds_and_spell_schedule_are_fixed(self):
        expected_literals = (
            "$SMART_ATTACK_HERO_KING_ELAPSED_MS = 34000",
            "$SMART_ATTACK_HERO_KING_DAMAGE_PERCENT = 50",
            "$SMART_ATTACK_HERO_QUEEN_ELAPSED_MS = 24000",
            "$SMART_ATTACK_HERO_QUEEN_DAMAGE_PERCENT = 35",
            "$SMART_ATTACK_HERO_PRINCE_ELAPSED_MS = 18000",
            "$SMART_ATTACK_HERO_PRINCE_DAMAGE_PERCENT = 25",
            "$SMART_ATTACK_HERO_WARDEN_ELAPSED_MS = 10000",
            "$SMART_ATTACK_HERO_WARDEN_DAMAGE_PERCENT = 12",
            "$SMART_ATTACK_HERO_CHAMPION_ELAPSED_MS = 30000",
            "$SMART_ATTACK_HERO_CHAMPION_DAMAGE_PERCENT = 45",
            "$SMART_ATTACK_RAGE_SECOND_DUE_MS = 7000",
            "$SMART_ATTACK_RAGE_THIRD_DUE_MS = 14000",
            "$SMART_ATTACK_RAGE_FIRST_PROGRESS = 0.35",
            "$SMART_ATTACK_RAGE_SECOND_PROGRESS = 0.60",
            "$SMART_ATTACK_RAGE_THIRD_PROGRESS = 0.82",
            "$SMART_ATTACK_FREEZE_FIRST_DUE_MS = 8000",
            "$SMART_ATTACK_FREEZE_INTERVAL_MS = 4000",
        )
        for literal in expected_literals:
            self.assertIn(literal, self.source)

    def test_autoit_behavior_when_runtime_is_available(self):
        executable = _find_windows_tool(
            "AutoIt3.exe",
            ("AutoIt3/AutoIt3.exe", "AutoIt3/AutoIt3_x64.exe"),
        )
        if not executable:
            self.skipTest("AutoIt runtime is not installed")
        result = subprocess.run(
            [executable, "/ErrorStdOut", str(AUTOIT_TEST)],
            cwd=AUTOIT_TEST.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("SmartAttackPolicyTest passed", result.stdout)

    def test_au3check_when_available(self):
        checker = _find_windows_tool(
            "Au3Check.exe",
            ("AutoIt3/Au3Check.exe", "AutoIt3/SciTE/Au3Check.exe"),
        )
        if not checker:
            self.skipTest("Au3Check is not installed")
        result = subprocess.run(
            [checker, "-q", str(AUTOIT_TEST)],
            cwd=AUTOIT_TEST.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_full_autoit_matrix_registers_the_policy_test(self):
        matrix = (ROOT / "tools" / "Test-AutoIt.ps1").read_text(encoding="utf-8-sig")
        self.assertIn('"tests\\autoit\\SmartAttackPolicyTest.au3"', matrix)


if __name__ == "__main__":
    unittest.main()
