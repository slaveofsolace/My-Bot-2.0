#NoTrayIcon
#include <StringConstants.au3>
#include "..\..\COCBot\functions\Run\RunPlan.au3"
#include "..\..\COCBot\functions\Run\AccountQueue.au3"
#include "..\..\COCBot\functions\Run\BattleRoute.au3"
#include "..\..\COCBot\functions\Run\RunSession.au3"

Global $g_iAssertions = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 10
	EndIf
EndFunc   ;==>AssertTrue

Local $oPlan = RunPlanCreateDefault("ranked", "fixture-strategy")
AssertTrue(IsObj($oPlan), "default run plan is created")
Local $sError = ""
AssertTrue(RunPlanValidate($oPlan, $sError), "run plan validates: " & $sError)
AssertTrue(RunPlanSetStopConditions($oPlan, 0, 2, False, 2), "stop conditions are accepted")
AssertTrue(RunPlanSetResourceTargets($oPlan, 1000, 0, 0), "resource targets are accepted")

Local $oRoute = BattleRouteFromRunPlan($oPlan, $sError)
AssertTrue(IsObj($oRoute), "battle route is created")
AssertTrue($oRoute.Item("mode") = "ranked", "ranked route remains distinct")
Local $sReason = ""
AssertTrue(Not BattleRouteCanStart($oRoute, $sReason), "route is blocked before evidence")
AssertTrue(StringInStr($sReason, "Recognition") > 0, "blocked route explains recognition requirement")
AssertTrue(BattleRouteSetReadiness($oRoute, True, True), "route readiness can be recorded")
AssertTrue(BattleRouteCanStart($oRoute, $sReason), "route starts after both gates pass")

Local $oSession = RunSessionCreate($oPlan, "contract-test")
AssertTrue(IsObj($oSession), "run session is created")
AssertTrue(RunSessionSetAccount($oSession, "profile-a"), "profile reference is assigned")
AssertTrue(RunSessionStart($oSession), "run session starts")
AssertTrue(RunSessionRecordBattle($oSession, True, 400, 200, 0), "first battle is recorded")
AssertTrue(RunSessionEvaluateStop($oSession, 1000, False) = "", "session continues below limits")
AssertTrue(RunSessionRecordBattle($oSession, True, 700, 300, 0), "second battle is recorded")
AssertTrue(RunSessionEvaluateStop($oSession, 2000, False) = "battle-limit", "battle limit stops the session before a later resource check")
AssertTrue($oSession.Item("state") = "stopping", "session enters stopping state")
AssertTrue(RunSessionComplete($oSession), "session completes")
AssertTrue($oSession.Item("state") = "completed", "completed state is retained")
Local $oSnapshot = RunSessionSnapshot($oSession)
AssertTrue(IsObj($oSnapshot), "snapshot is created")
AssertTrue($oSnapshot.Item("gold") = 1100, "loot totals are accumulated")
AssertTrue($oSnapshot.Item("account_profile_id") = "profile-a", "snapshot contains profile reference")

Local $oQueue = AccountQueueCreate(False)
AssertTrue(AccountQueueAdd($oQueue, "profile-a", "Alpha"), "first queue item is added")
AssertTrue(AccountQueueAdd($oQueue, "profile-b", "Beta", False), "disabled queue item is added")
AssertTrue(AccountQueueAdd($oQueue, "profile-c", "Gamma"), "third queue item is added")
Local $sProfile = "", $sName = ""
AssertTrue(AccountQueueNext($oQueue, $sProfile, $sName), "first enabled queue item is returned")
AssertTrue($sProfile = "profile-a", "first profile order is stable")
AssertTrue(AccountQueueNext($oQueue, $sProfile, $sName), "disabled queue item is skipped")
AssertTrue($sProfile = "profile-c", "third profile follows the disabled item")
AssertTrue(Not AccountQueueNext($oQueue, $sProfile, $sName), "non-cycling queue ends")

ConsoleWrite("Run contract tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
