#NoTrayIcon
#include "..\..\COCBot\functions\Run\ExactRecipeTrainingRoute.au3"

Global Const $FIXTURE_DIGEST = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
Global $g_iAssertions = 0
Global $g_iIssueCalls = 0
Global $g_iStopCalls = 0
Global $g_iStopAt = 0
Global $g_iHomeCalls = 0
Global $g_bIssueAccepted = True
Global $g_bNoGemReady = True
Global $g_oBefore = 0
Global $g_oAfter = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 10
	EndIf
EndFunc

Func FixtureReset()
	$g_iIssueCalls = 0
	$g_iStopCalls = 0
	$g_iStopAt = 0
	$g_iHomeCalls = 0
	$g_bIssueAccepted = True
	$g_bNoGemReady = True
	$g_oBefore = ExactRecipeTrainingObservationCreate($EXACT_TRAINING_STATE_RECIPE_READY, "war-army", $FIXTURE_DIGEST, 42, 0, "", False, False, False, 700, 600)
	$g_oAfter = ExactRecipeTrainingObservationCreate($EXACT_TRAINING_STATE_POST_QUEUED, "war-army", $FIXTURE_DIGEST, 0, 42, $FIXTURE_DIGEST)
EndFunc

Func FixtureDetect($sPhase)
	If StringLower($sPhase) = "after" Then Return $g_oAfter
	Return $g_oBefore
EndFunc

Func FixtureIssue($iX, $iY)
	$g_iIssueCalls += 1
	Return $g_bIssueAccepted And $iX = 700 And $iY = 600
EndFunc

Func FixtureStop()
	$g_iStopCalls += 1
	Return $g_iStopAt > 0 And $g_iStopCalls >= $g_iStopAt
EndFunc

Func FixtureNoGem()
	Return $g_bNoGemReady
EndFunc

Func FixtureHome()
	$g_iHomeCalls += 1
	Return True
EndFunc

Func FixtureRun($iMax = 50)
	Return ExactRecipeTrainingRouteRunAdapter("war-army", $FIXTURE_DIGEST, $iMax, "FixtureDetect", _
			"FixtureIssue", "FixtureStop", "FixtureNoGem", "FixtureHome")
EndFunc

FixtureReset()
Local $oQueued = FixtureRun()
AssertTrue($oQueued.Item("state") = $EXACT_TRAINING_OUTCOME_QUEUED, "exact recipe queues")
AssertTrue($oQueued.Item("queue_attempts") = 1 And $oQueued.Item("queue_issued") And $oQueued.Item("queue_confirmed"), "one queue receipt is truthful")
AssertTrue($oQueued.Item("missing_units") = 42 And $g_iIssueCalls = 1, "exact missing-unit delta is recorded")
AssertTrue($oQueued.Item("home_proven"), "Home is re-proven")

FixtureReset()
Local $oOverCap = FixtureRun(41)
AssertTrue($oOverCap.Item("state") = $EXACT_TRAINING_OUTCOME_UNCONFIRMED, "queue cap rejects oversized recipe")
AssertTrue($g_iIssueCalls = 0, "oversized recipe issues no input")

FixtureReset()
$g_oBefore = ExactRecipeTrainingObservationCreate($EXACT_TRAINING_STATE_RECIPE_READY, "war-army", $FIXTURE_DIGEST, 42, 0, "", True, False, False, 700, 600)
Local $oBoost = FixtureRun()
AssertTrue($oBoost.Item("state") = $EXACT_TRAINING_OUTCOME_UNCONFIRMED, "active boost is rejected")
AssertTrue($g_iIssueCalls = 0, "boost rejection issues no input")

FixtureReset()
$g_oBefore = ExactRecipeTrainingObservationCreate($EXACT_TRAINING_STATE_RECIPE_READY, "war-army", $FIXTURE_DIGEST, 42, 0, "", False, False, True, 700, 600)
Local $oDelete = FixtureRun()
AssertTrue($oDelete.Item("state") = $EXACT_TRAINING_OUTCOME_UNCONFIRMED, "delete-required queue is rejected")
AssertTrue($g_iIssueCalls = 0, "delete-required queue issues no input")

FixtureReset()
$g_bNoGemReady = False
Local $oGem = FixtureRun()
AssertTrue($oGem.Item("state") = $EXACT_TRAINING_OUTCOME_UNCONFIRMED, "no-gem guard blocks queue")
AssertTrue($oGem.Item("queue_attempts") = 0 And $g_iIssueCalls = 0, "gem guard consumes no attempt")

FixtureReset()
$g_bIssueAccepted = False
Local $oRejected = FixtureRun()
AssertTrue($oRejected.Item("state") = $EXACT_TRAINING_OUTCOME_UNCONFIRMED, "rejected queue delivery is unconfirmed")
AssertTrue($oRejected.Item("queue_attempts") = 1 And Not $oRejected.Item("queue_issued") And $g_iIssueCalls = 1, "rejected delivery is attempted once")

FixtureReset()
$g_oAfter = ExactRecipeTrainingObservationCreate($EXACT_TRAINING_STATE_POST_QUEUED, "war-army", $FIXTURE_DIGEST, 0, 41, $FIXTURE_DIGEST)
Local $oWrongDelta = FixtureRun()
AssertTrue($oWrongDelta.Item("state") = $EXACT_TRAINING_OUTCOME_UNCONFIRMED, "wrong post-queue delta is unconfirmed")
AssertTrue($oWrongDelta.Item("queue_issued") And $g_iIssueCalls = 1, "unconfirmed issued queue is never retried")

For $i = 1 To 3
	FixtureReset()
	$g_iStopAt = $i
	Local $oStopped = FixtureRun()
	AssertTrue($oStopped.Item("state") = $EXACT_TRAINING_OUTCOME_CANCELLED, "pre-input Stop cancels at boundary " & $i)
	AssertTrue($g_iIssueCalls = 0, "pre-input Stop issues nothing at boundary " & $i)
Next

FixtureReset()
$g_iStopAt = 4
Local $oAfterInputStop = FixtureRun()
AssertTrue($oAfterInputStop.Item("state") = $EXACT_TRAINING_OUTCOME_UNCONFIRMED And $oAfterInputStop.Item("queue_issued"), "post-input Stop preserves uncertainty")
AssertTrue($g_iHomeCalls = 0 And $g_iIssueCalls = 1, "post-input Stop performs no capture or cleanup")

ConsoleWrite("Exact recipe training route tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
