from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUN_EXECUTION = (ROOT / "COCBot/functions/Run/RunExecution.au3").read_text(encoding="utf-8-sig")
OBSTACLES = (ROOT / "COCBot/functions/Main Screen/checkObstacles.au3").read_text(encoding="utf-8-sig")


REWARD_FLAGS = (
    "ChkCollectCartFirst",
    "ChkTreasuryCollect",
    "ChkCollectAchievements",
    "ChkCollectFreeMagicItems",
    "ChkCollectRewards",
    "ChkSellRewards",
)


class ManagedRewardSafetyTest(unittest.TestCase):
    def test_every_legacy_reward_flag_is_snapshotted_disabled_and_restored(self) -> None:
        reset = RUN_EXECUTION.index("A reviewed plan is closed-world")
        collectors = RUN_EXECUTION.index("If $sStrategy = $HOME_MAINTENANCE_COLLECTORS_STRATEGY", reset)
        common_reset = RUN_EXECUTION[reset:collectors]
        for suffix in REWARD_FLAGS:
            with self.subTest(flag=suffix):
                self.assertIn(f"Global $g_bRunExecutionSnapshot{suffix} = False", RUN_EXECUTION)
                self.assertIn(
                    f"$g_bRunExecutionSnapshot{suffix} = $g_b{suffix}", RUN_EXECUTION
                )
                self.assertIn(f"$g_b{suffix} = False", common_reset)
                self.assertIn(
                    f"$g_b{suffix} = $g_bRunExecutionSnapshot{suffix}", RUN_EXECUTION
                )

    def test_only_the_explicit_home_route_may_attempt_one_daily_reward_claim(self) -> None:
        start = OBSTACLES.index("Func CheckDailyRewardWindow()")
        end = OBSTACLES.index("EndFunc   ;==>CheckDailyRewardWindow", start)
        body = OBSTACLES[start:end]
        guard = body.index(
            "If RunExecutionManagedPlanPrepared() And Not RunExecutionDailyRewardClaimAllowed() Then"
        )
        close = body.index("CloseWindow2()", guard)
        early_return = body.index("Return", close)
        claim_search = body.index('findMultiple(@ScriptDir & "\\imgxml\\DailyChallenge\\"')
        self.assertLess(guard, close)
        self.assertLess(close, early_return)
        self.assertLess(early_return, claim_search)

        managed = body.index("If RunExecutionManagedPlanPrepared() Then", claim_search)
        legacy = body.index("For $j = 0 To UBound($aAllCoords) - 1", managed)
        managed_body = body[managed:legacy]
        self.assertIn("If $iClaimButtons <> 1 Then", managed_body)
        self.assertIn("RunControlStopRequested() Or Not $g_bRunState", managed_body)
        self.assertEqual(managed_body.count("Local $bClaimIssued = Click("), 1)
        self.assertIn('RunExecutionRecordDailyReward($bClaimIssued ? "click-issued" : "click-rejected", 1', managed_body)
        self.assertIn("If $bClaimIssued Then RunEventLogMaintenanceDailyRewardClickIssued(1)", managed_body)
        self.assertLess(
            managed_body.index("RunExecutionRecordDailyReward("),
            managed_body.index("RunEventLogMaintenanceDailyRewardClickIssued(1)"),
        )
        self.assertIn("Never click an Okay/Confirm button here", managed_body)
        self.assertNotIn("ClickP(", managed_body)
        self.assertNotIn("Okay Btn", managed_body)
        self.assertNotIn("Confirm", managed_body.replace("Okay/Confirm", ""))

    def test_no_gem_conversion_is_available_to_any_managed_plan(self) -> None:
        reset = RUN_EXECUTION.index("A reviewed plan is closed-world")
        generic_apply = RUN_EXECUTION.index("Switch StringLower", reset)
        self.assertIn("$g_bChkSellRewards = False", RUN_EXECUTION[reset:generic_apply])
        self.assertIn("selling a full magic item", RUN_EXECUTION[reset:generic_apply])

    def test_explicit_loot_cart_route_does_not_reenable_the_legacy_reward_path(self) -> None:
        home_start = RUN_EXECUTION.index("Func HomeMaintenanceRouteExecute()")
        home_end = RUN_EXECUTION.index("EndFunc   ;==>HomeMaintenanceRouteExecute", home_start)
        home = RUN_EXECUTION[home_start:home_end]
        self.assertIn("LootCartRouteRunAdapter", home)
        self.assertNotIn("CollectLootCart(", home)
        self.assertNotIn("$g_bChkCollectCartFirst = True", RUN_EXECUTION)
        self.assertNotIn("$g_bChkTreasuryCollect = True", RUN_EXECUTION)


if __name__ == "__main__":
    unittest.main()
