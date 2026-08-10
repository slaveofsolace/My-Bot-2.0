#NoTrayIcon
#include <StringConstants.au3>
#include "..\..\COCBot\functions\Run\RunPlan.au3"
#include "..\..\COCBot\functions\Run\AccountQueue.au3"
#include "..\..\COCBot\functions\Run\BattleRoute.au3"
#include "..\..\COCBot\functions\Run\RunSession.au3"
#include "..\..\COCBot\functions\Run\RunEvent.au3"

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
AssertTrue($oSnapshot.Item("verification_state") = $RUN_VERIFICATION_VERIFIED, "snapshot contains verification state")
AssertTrue($oSnapshot.Item("verification_reason") = "", "verified snapshot has no diagnostic reason")

Local $oManualSession = RunSessionCreate($oPlan, "manual-stop")
AssertTrue(IsObj($oManualSession) And RunSessionStart($oManualSession), "manual-stop session starts")
AssertTrue(RunSessionRequestStop($oManualSession, "stopped"), "manual Stop requests the stopping transition")
AssertTrue($oManualSession.Item("state") = "stopping" And $oManualSession.Item("stop_reason") = "stopped", "manual Stop records its state and reason")
AssertTrue(RunSessionRequestStop($oManualSession, "second request"), "repeated Stop remains idempotent")
AssertTrue($oManualSession.Item("stop_reason") = "stopped", "repeated Stop preserves the first terminal reason")
AssertTrue(RunSessionComplete($oManualSession) And $oManualSession.Item("state") = "completed", "manual-stop session completes exactly once")
AssertTrue(Not RunSessionComplete($oManualSession), "a completed session refuses a second completion")
Local $oReadySession = RunSessionCreate($oPlan, "not-started")
AssertTrue(Not RunSessionComplete($oReadySession) And $oReadySession.Item("state") = "ready", "a session cannot claim completion before it starts")

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

Local $oEvent = RunEventCreate("battle.completed", 7, 2000, "contract-test", "info", "Battle complete", "profile-a", "ranked", 2, 700, 300, 0, 0)
AssertTrue(IsObj($oEvent), "run event is created")
Local $sEventJson = RunEventToJson($oEvent)
AssertTrue(StringInStr($sEventJson, Chr(34) & "type" & Chr(34) & ":" & Chr(34) & "battle.completed" & Chr(34)) > 0, "run event serializes its type")
AssertTrue(StringInStr($sEventJson, Chr(34) & "gold" & Chr(34) & ":700") > 0, "run event serializes numeric loot")
Local $sEventPath = @TempDir & "\mybot-run-contract-event.jsonl"
FileDelete($sEventPath)
AssertTrue(RunEventAppendJsonLine($sEventPath, $oEvent), "run event is appended to JSONL")
AssertTrue(FileExists($sEventPath), "JSONL event file is created")
AssertTrue(StringInStr(FileRead($sEventPath), "Battle complete") > 0, "JSONL event can be read back")
FileDelete($sEventPath)

ConsoleWrite("Run contract tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
