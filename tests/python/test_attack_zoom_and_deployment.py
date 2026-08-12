import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def function_body(source: str, name: str) -> str:
    match = re.search(rf"Func\s+{re.escape(name)}\b.*?\n(.*?)\nEndFunc", source, re.S | re.I)
    if not match:
        raise AssertionError(f"missing AutoIt function {name}")
    return match.group(1)


class AttackZoomAndDeploymentTests(unittest.TestCase):
    def test_enemy_zoom_precedes_every_planned_target_read(self):
        source = (ROOT / "COCBot/functions/Search/VillageSearch.au3").read_text(encoding="utf-8-sig")
        body = function_body(source, "_VillageSearch")
        ordered = [
            "WaitForClouds()",
            "RunExecutionPrepareEnemyDeploymentView()",
            "AttackRemainingTime(True)",
            "GetResources(False)",
        ]
        offsets = [body.index(token) for token in ordered]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("$g_bRestart = True", body)

    def test_zoom_is_immediate_bounded_and_reuses_the_upstream_adb_primitive(self):
        source = (ROOT / "COCBot/functions/Run/RunExecution.au3").read_text(encoding="utf-8-sig")
        body = function_body(source, "RunExecutionPrepareEnemyDeploymentView")
        self.assertIn("For $iZoom = 0 To 2", body)
        self.assertEqual(body.count("AndroidZoomOut("), 1)
        self.assertIn('AndroidZoomOut($iZoom, Default, ($g_iAndroidZoomoutMode <> 2), Default, "Normal2")', body)
        self.assertIn("Local $iZoomError = @error", body)
        self.assertIn("If $iZoomError Then", body)
        self.assertNotIn("$iZoomResult <> 1", body)
        self.assertIn("ForceCaptureRegion()", body)
        self.assertIn("_CaptureRegions()", body)
        self.assertNotIn("_CaptureRegion2()", body)
        self.assertLess(body.index("_CaptureRegions()"), body.index("IsAttackPage(False)"))
        self.assertNotIn("CheckZoomOut(", body)
        self.assertIn("SearchRedLines($CocDiamondECD)", body)
        self.assertIn("If $iRedlinePoints < 50 Then", body)
        self.assertLess(body.index("AndroidZoomOut("), body.index("SearchRedLines("))
        self.assertLess(body.index("SearchRedLines("), body.rindex("Return True"))
        self.assertNotIn("$g_bRunExecutionManageTraining", body)

        android = (ROOT / "COCBot/functions/Android/Android.au3").read_text(encoding="utf-8-sig")
        zoom = function_body(android, "AndroidZoomOut")
        self.assertIn('If $sForcedScript <> "" Then', zoom)
        self.assertIn('Local $sScript = $sForcedScript', zoom)

        script_transport = function_body(android, "AndroidAdbScript")
        self.assertIn("Local $iScriptError = @error", script_transport)
        self.assertIn("Local $iScriptExtended = @extended", script_transport)
        self.assertIn("If $iScriptError Then Return SetError($iScriptError, $iScriptExtended, 0)", script_transport)
        self.assertIn("Return SetError(0, $iScriptExtended, 1)", script_transport)
        self.assertNotIn("(@error = 0 ? 1 : 0)", script_transport)

        proof_gate = function_body(source, "RunExecutionStandardDeploymentProofRequired")
        self.assertNotIn("$g_bRunExecutionManageTraining", proof_gate)

    def test_planned_search_does_not_repeat_the_slow_scenery_measurement(self):
        source = (ROOT / "COCBot/functions/Search/VillageSearch.au3").read_text(encoding="utf-8-sig")
        body = function_body(source, "_VillageSearch")
        planned = body.index("If RunExecutionPlanActive() Then")
        legacy = body.index('ElseIf Not CheckZoomOut("VillageSearch", True, False) Then', planned)
        self.assertLess(planned, legacy)
        self.assertIn("post-zoom red-line proof", body[planned:legacy])

    def test_zoom_failure_surrenders_and_returns_home(self):
        source = (ROOT / "COCBot/functions/Search/VillageSearch.au3").read_text(encoding="utf-8-sig")
        body = function_body(source, "_VillageSearch")
        failure = body.index("If Not RunExecutionPrepareEnemyDeploymentView() Then")
        close = body.index("CloseBattle()", failure)
        home = body.index("ReturnHome(False)", close)
        restart = body.index("$g_bRestart = True", home)
        self.assertLess(failure, close)
        self.assertLess(close, home)
        self.assertLess(home, restart)

    def test_standard_attack_requires_post_drop_bar_evidence(self):
        source = (ROOT / "COCBot/functions/Attack/Attack Algorithms/algorithm_AllTroops.au3").read_text(
            encoding="utf-8-sig"
        )
        body = function_body(source, "algorithm_AllTroops")
        self.assertLess(body.index("RunExecutionResetDeploymentProof(_AttackDeployableTroopCount())"), body.index("LaunchTroop2("))
        self.assertLess(body.index("LaunchTroop2("), body.index("_AttackEnsurePlannedActorsDeployed()"))
        self.assertLess(body.index('SetLog("Dropping left over troops"'), body.index("_AttackConfirmStandardDeploymentGone()"))
        self.assertLess(body.index("_AttackConfirmStandardDeploymentGone()"), body.index('SetLog("Finished Attacking'))

        read_body = function_body(source, "_AttackReadLiveDeployableTroopCount")
        self.assertIn("ForceCaptureRegion()", read_body)
        self.assertIn("_CaptureRegion2()", read_body)
        self.assertIn("GetAttackBar(True, $g_iMatchMode)", read_body)
        self.assertIn("If Not IsArray($aLiveAttackBar) Then", read_body)

        confirm_body = function_body(source, "_AttackConfirmStandardDeploymentGone")
        self.assertIn("For $iRead = 1 To 2", confirm_body)
        self.assertIn("If Not $bReadValid Or $iDeployableAfter <> 0 Then", confirm_body)
        self.assertEqual(confirm_body.count("_AttackReadLiveDeployableTroopCount("), 1)
        self.assertLess(confirm_body.index("For $iRead = 1 To 2"), confirm_body.index("RunExecutionRecordDeploymentProof(0)"))

        actor_body = function_body(source, "_AttackEnsurePlannedActorsDeployed")
        self.assertIn("Run Planner actors: hero mask", actor_body)
        self.assertIn("_AttackSelectedHeroesDropped($iHeroMask)", actor_body)
        self.assertIn("_AttackRefreshPlannedActorProof($iHeroMask, $bProofValid)", actor_body)
        self.assertIn("$g_aiDeployHeroesPosition[0]", actor_body)
        self.assertIn("$g_aiDeployCCPosition[0]", actor_body)
        self.assertIn("_AttackDeploySelectedHeroesAtPoint(", actor_body)
        self.assertIn("_AttackDeployLiveSiegeAtPoint(", actor_body)
        self.assertIn("_AttackReadLiveActorBar(True)", actor_body)
        self.assertLess(actor_body.index("_AttackRefreshPlannedActorProof("), actor_body.index("_AttackDeploySelectedHeroesAtPoint("))
        self.assertLess(actor_body.index("_AttackDeploySelectedHeroesAtPoint("), actor_body.rindex("_AttackRefreshPlannedActorProof("))

        direct_heroes = function_body(source, "_AttackDeploySelectedHeroesAtPoint")
        self.assertNotIn("$g_aiCmbCustomHeroOrder", direct_heroes)
        for hero_type, proof in (
            ("$eKing", "$g_bDropKing"),
            ("$eQueen", "$g_bDropQueen"),
            ("$ePrince", "$g_bDropPrince"),
            ("$eWarden", "$g_bDropWarden"),
            ("$eChampion", "$g_bDropChampion"),
        ):
            self.assertIn("_AttackDeployLiveActorAtPoint($aLiveActors, " + hero_type, direct_heroes)
            self.assertIn("Not " + proof, direct_heroes)

        live_actor = function_body(source, "_AttackDeployLiveActorAtPoint")
        self.assertIn("$aLiveActors[$i][3]", live_actor)
        self.assertIn("$aLiveActors[$i][4]", live_actor)
        self.assertLess(live_actor.index("Click($iPortraitX, $iPortraitY"), live_actor.index("AttackClick($iDropX, $iDropY"))

        proof_body = function_body(source, "_AttackRefreshPlannedActorProof")
        self.assertIn("_AttackReadLiveActorBar($bHasBaseline)", proof_body)
        for hero in ("King", "Queen", "Minion Prince", "Grand Warden", "Royal Champion"):
            self.assertIn(f'_AttackProveActiveHero("{hero}"', proof_body)
        self.assertNotIn("Case $eQueen", proof_body)
        self.assertIn("$g_bDropQueen = $bQueen", proof_body)
        self.assertIn("$g_bIsCCDropped = $bCC", proof_body)
        self.assertIn("_AttackProveRaisedHero($aActorBaseline, $aLiveAttackBar", proof_body)
        self.assertIn("Local $bCC = $g_bIsCCDropped Or", proof_body)

        live_bar = function_body(source, "_AttackReadLiveActorBar")
        self.assertIn("ForceCaptureRegion()", live_bar)
        self.assertIn("GetAttackBar(Not $bFreshCoordinates, $g_iMatchMode)", live_bar)

        active_hero = function_body(source, "_AttackProveActiveHero")
        self.assertIn("FindImageInPlace2(", active_hero)
        self.assertIn("570 + $g_iBottomOffsetY", active_hero)
        self.assertIn("$aHealth[0] = $aHero[0] - $aHealth[4]", active_hero)
        self.assertIn("_ColorCheck($sHealthColor, Hex($aHealth[2], 6), $aHealth[3])", active_hero)
        self.assertNotIn("_CheckPixel2(", active_hero)
        self.assertNotIn("Click(", active_hero)
        self.assertNotIn("AttackClick(", active_hero)

        raised_hero = function_body(source, "_AttackProveRaisedHero")
        self.assertIn("Local $iRise = $iBeforeY - $iAfterY", raised_hero)
        self.assertIn("$iRise >= 8 And $iRise <= 30", raised_hero)
        self.assertIn("Abs($iAfterX - $iBeforeX) <= 12", raised_hero)
        self.assertNotIn("Click(", raised_hero)

        live_siege = function_body(source, "_AttackDeployLiveSiegeAtPoint")
        self.assertEqual(live_siege.count("$g_bIsCCDropped = True"), 2)
        self.assertIn("If $bDeployed Then $g_bIsCCDropped = True", live_siege)
        self.assertIn("is absent from the fresh live bar; deployment proved", live_siege)

    def test_compact_current_attack_bar_has_unique_visual_slots(self):
        source = (ROOT / "COCBot/functions/Attack/GetAttackBar.au3").read_text(encoding="utf-8-sig")
        body = function_body(source, "GetAttackBar")
        self.assertIn("If Not $bRemaining And Not $bDoubleRow And Not $bCheckSlot12 Then", body)
        self.assertIn("_NormalizeSingleRowAttackSlots($aFinalAttackBar)", body)
        normalize = function_body(source, "_NormalizeSingleRowAttackSlots")
        self.assertIn("_ArraySort($aFinalAttackBar, 0, 0, 0, 3)", normalize)
        self.assertIn("$aFinalAttackBar[$iSlot][1] = $iSlot", normalize)

    def test_live_run_never_repositions_bluestacks_from_activateapp(self):
        source = (ROOT / "COCBot/MBR GUI Control.au3").read_text(encoding="utf-8-sig")
        body = function_body(source, "GUIControl_WM_ACTIVATEAPP")
        show_line = next(line for line in body.splitlines() if "ShowAndroidWindow(" in line)
        self.assertIn("Not $g_bRunState", show_line)
        self.assertIn("$g_bChkBackgroundMode", show_line)

    def test_unproven_deployment_surrenders_instead_of_claiming_completion(self):
        source = (ROOT / "MyBot.run.au3").read_text(encoding="utf-8-sig")
        body = function_body(source, "_AttackMainExecuteRegularBattle")
        proof = body.index("If Not RunExecutionDeploymentVerified() Then")
        self.assertLess(body.index("Attack()"), proof)
        self.assertLess(proof, body.index("CloseBattle()", proof))
        cleanup = body.index("ReturnHome(False)", proof)
        self.assertLess(body.index("CloseBattle()", proof), cleanup)
        self.assertLess(cleanup, body.index("CleanSuperchargeTemplates()", cleanup))
        self.assertLess(body.index("CleanSuperchargeTemplates()", cleanup), body.index("Return False", cleanup))

    def test_missing_attack_bar_surrenders_before_algorithm_dispatch(self):
        source = (ROOT / "MyBot.run.au3").read_text(encoding="utf-8-sig")
        body = function_body(source, "_AttackMainExecuteRegularBattle")
        prepare = body.index("Local $iPreparedTroops = PrepareAttack($g_iMatchMode)")
        fail_closed = body.index("If Number($iPreparedTroops) <= 0 Then", prepare)
        surrender = body.index("CloseBattle()", fail_closed)
        home = body.index("ReturnHome(False)", surrender)
        dispatch = body.index("Attack()", home)
        self.assertLess(prepare, fail_closed)
        self.assertLess(fail_closed, surrender)
        self.assertLess(surrender, home)
        self.assertLess(home, dispatch)

    def test_planned_battle_requires_authoritative_attack_report_commit(self):
        source = (ROOT / "MyBot.run.au3").read_text(encoding="utf-8-sig")
        body = function_body(source, "_AttackMainExecuteRegularBattle")
        self.assertIn("Local $iBattleTotalBefore = _RunExecutionBattleTotal()", body)
        return_home = body.rindex("ReturnHome($g_bTakeLootSnapShot)")
        counter_gate = body.index("_RunExecutionBattleTotal() <= $iBattleTotalBefore", return_home)
        self.assertLess(return_home, counter_gate)
        self.assertLess(counter_gate, body.rindex("Return True"))


if __name__ == "__main__":
    unittest.main()
