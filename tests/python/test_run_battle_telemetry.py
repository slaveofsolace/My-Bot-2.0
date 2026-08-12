import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class RunBattleTelemetryContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.attack_report = (ROOT / "COCBot/functions/Attack/AttackReport.au3").read_text(encoding="utf-8-sig")
        cls.event = (ROOT / "COCBot/functions/Run/RunEvent.au3").read_text(encoding="utf-8-sig")
        cls.event_log = (ROOT / "COCBot/functions/Run/RunEventLog.au3").read_text(encoding="utf-8-sig")
        cls.schema = json.loads((ROOT / "config/run-event.schema.json").read_text(encoding="utf-8-sig"))

    def test_event_contract_exposes_exact_battle_result_fields(self):
        properties = self.schema["properties"]
        for field in ("stars", "destruction_percent", "trophy_delta", "search_count"):
            self.assertIn(field, properties)
            self.assertIn(f'"{field}"', self.event)
        self.assertNotIn("minimum", properties["trophy_delta"], "trophy losses must remain signed")
        self.assertEqual(properties["stars"].get("maximum"), 3)
        self.assertEqual(properties["destruction_percent"].get("maximum"), 100)

    def test_attack_report_emits_after_exact_result_commit_before_reset(self):
        body = self.attack_report.split("Func AttackReport()", 1)[1].split("EndFunc", 1)[0]
        battle_commit = body.find("$g_aiAttackedVillageCount[$g_iMatchMode] += 1")
        telemetry = body.find("RunEventLogBattleCompleted(")
        damage_reset = body.find("$g_iPercentageDamage = 0")
        self.assertGreaterEqual(battle_commit, 0)
        self.assertGreater(telemetry, battle_commit)
        self.assertGreater(damage_reset, telemetry)
        for value in (
            "$starsearned",
            "$g_iPercentageDamage",
            "$g_iStatsLastAttack[$eLootGold]",
            "$g_iStatsLastAttack[$eLootElixir]",
            "$g_iStatsLastAttack[$eLootDarkElixir]",
            "$g_iStatsLastAttack[$eLootTrophy]",
            "$g_iSearchCount",
        ):
            self.assertIn(value, body[telemetry:damage_reset])
        self.assertNotIn("RunIntentRecordBattle", body, "telemetry must not advance planner limits")

    def test_battle_writer_is_bound_and_uses_the_latched_run_context(self):
        body = self.event_log.split("Func RunEventLogBattleCompleted", 1)[1].split("EndFunc", 1)[0]
        self.assertIn("If Not $g_bRunEventSessionBound", body)
        self.assertIn('$g_sRunEventSessionId = ""', body)
        self.assertIn('RunEventCreate("battle.completed"', body)
        self.assertIn("$g_sRunEventSessionId", body)
        self.assertIn("$g_sRunEventRoute", body)
        self.assertIn("$g_sRunEventSurfaceId", body)
        self.assertIn("$g_sRunEventVerificationState", body)

        started = self.event_log.split("Func RunEventLogRunStarted", 1)[1].split("EndFunc", 1)[0]
        self.assertIn("_RunEventLogSetRunContext($sSurfaceId, $sVerificationState)", started)


if __name__ == "__main__":
    unittest.main()
