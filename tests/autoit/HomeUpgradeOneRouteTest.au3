#NoTrayIcon
#include "..\..\COCBot\functions\Run\HomeUpgradeOneRoute.au3"

Global $g_iAssertions = 0
Global $g_iStopCalls = 0
Global $g_iStopAt = 0
Global $g_iSelectCalls = 0
Global $g_iConfirmCalls = 0
Global $g_iNoGemCalls = 0
Global $g_iHomeCalls = 0
Global $g_bConfirmAccepted = True
Global $g_bNoGemReady = True
Global $g_oCandidate = 0
Global $g_oConfirm = 0
Global $g_oPost = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 10
	EndIf
EndFunc

Func FixtureReset()
	$g_iStopCalls = 0
	$g_iStopAt = 0
	$g_iSelectCalls = 0
	$g_iConfirmCalls = 0
	$g_iNoGemCalls = 0
	$g_iHomeCalls = 0
	$g_bConfirmAccepted = True
	$g_bNoGemReady = True
	$g_oCandidate = HomeUpgradeObservationCreate($HOME_UPGRADE_STATE_CANDIDATE_READY, "cannon", 20, "gold", 1000, 5000, 3000, True, False, 400, 500)
	$g_oConfirm = HomeUpgradeObservationCreate($HOME_UPGRADE_STATE_CONFIRM_READY, "cannon", 20, "gold", 1000, 5000, 3000, True, False, 600, 600)
	$g_oPost = HomeUpgradeObservationCreate($HOME_UPGRADE_STATE_POST_STARTED, "cannon", 20, "gold", 1000, 4000, 3000, False, True)
EndFunc

Func FixtureDetect($sPhase)
	Switch StringLower($sPhase)
		Case "confirm"
			Return $g_oConfirm
		Case "post"
			Return $g_oPost
	EndSwitch
	Return $g_oCandidate
EndFunc

Func FixtureSelect($iX, $iY)
	$g_iSelectCalls += 1
	Return $iX = 400 And $iY = 500
EndFunc

Func FixtureConfirm($iX, $iY)
	$g_iConfirmCalls += 1
	Return $g_bConfirmAccepted And $iX = 600 And $iY = 600
EndFunc

Func FixtureStop()
	$g_iStopCalls += 1
	Return $g_iStopAt > 0 And $g_iStopCalls >= $g_iStopAt
EndFunc

Func FixtureNoGem()
	$g_iNoGemCalls += 1
	Return $g_bNoGemReady
EndFunc

Func FixtureHome()
	$g_iHomeCalls += 1
	Return True
EndFunc

Func FixtureRun($iCap = 1000)
	Return HomeUpgradeOneRouteRunAdapter($iCap, "FixtureDetect", "FixtureSelect", "FixtureConfirm", _
			"FixtureStop", "FixtureNoGem", "FixtureHome")
EndFunc

FixtureReset()
Local $oStarted = FixtureRun()
AssertTrue($oStarted.Item("state") = $HOME_UPGRADE_OUTCOME_STARTED, "one upgrade starts")
AssertTrue($oStarted.Item("select_attempts") = 1 And $oStarted.Item("confirm_attempts") = 1, "both UI steps are capped at one")
AssertTrue($oStarted.Item("select_issued") And $oStarted.Item("confirm_issued"), "accepted input receipts are truthful")
AssertTrue($oStarted.Item("post_state_proven") And $oStarted.Item("available_before") = 5000 And $oStarted.Item("available_after") = 4000, "exact resource decrement is proved")
AssertTrue($oStarted.Item("home_proven") And $g_iNoGemCalls = 2, "Home and both no-gem boundaries are proved")

FixtureReset()
Local $oOverCap = FixtureRun(999)
AssertTrue($oOverCap.Item("state") = $HOME_UPGRADE_OUTCOME_UNCONFIRMED, "configured cost cap is fail-closed")
AssertTrue($g_iSelectCalls = 0 And $g_iConfirmCalls = 0, "over-cap candidate issues no input")

FixtureReset()
$g_oCandidate = HomeUpgradeObservationCreate($HOME_UPGRADE_STATE_CANDIDATE_READY, "cannon", 20, "gold", 1000, 3999, 3000, True, False, 400, 500)
Local $oReserve = FixtureRun()
AssertTrue($oReserve.Item("state") = $HOME_UPGRADE_OUTCOME_UNCONFIRMED, "resource reserve is fail-closed")
AssertTrue($g_iSelectCalls = 0, "reserve failure issues no input")

FixtureReset()
$g_oConfirm = HomeUpgradeObservationCreate($HOME_UPGRADE_STATE_CONFIRM_READY, "cannon", 20, "gold", 1001, 5000, 3000, True, False, 600, 600)
Local $oMismatch = FixtureRun()
AssertTrue($oMismatch.Item("state") = $HOME_UPGRADE_OUTCOME_UNCONFIRMED, "confirmation mismatch is rejected")
AssertTrue($g_iSelectCalls = 1 And $g_iConfirmCalls = 0, "mismatch stops before resource spend")

FixtureReset()
$g_bNoGemReady = False
Local $oGemBlocked = FixtureRun()
AssertTrue($oGemBlocked.Item("state") = $HOME_UPGRADE_OUTCOME_UNCONFIRMED, "no-gem guard blocks selection")
AssertTrue($g_iSelectCalls = 0 And $g_iConfirmCalls = 0, "gem guard issues nothing")

FixtureReset()
$g_bConfirmAccepted = False
Local $oRejectedConfirm = FixtureRun()
AssertTrue($oRejectedConfirm.Item("state") = $HOME_UPGRADE_OUTCOME_UNCONFIRMED, "rejected confirmation is unconfirmed")
AssertTrue($oRejectedConfirm.Item("confirm_attempts") = 1 And Not $oRejectedConfirm.Item("confirm_issued") And $g_iConfirmCalls = 1, "confirmation is attempted once")

FixtureReset()
$g_oPost = HomeUpgradeObservationCreate($HOME_UPGRADE_STATE_POST_STARTED, "cannon", 20, "gold", 1000, 3999, 3000, False, True)
Local $oBadPost = FixtureRun()
AssertTrue($oBadPost.Item("state") = $HOME_UPGRADE_OUTCOME_UNCONFIRMED, "wrong post-spend amount is not confirmed")
AssertTrue($oBadPost.Item("confirm_issued") And $g_iConfirmCalls = 1, "issued unconfirmed spend is never retried")

For $i = 1 To 6
	FixtureReset()
	$g_iStopAt = $i
	Local $oStopped = FixtureRun()
	If $i <= 3 Then
		AssertTrue($oStopped.Item("state") = $HOME_UPGRADE_OUTCOME_CANCELLED, "pre-input Stop cancels at boundary " & $i)
	Else
		AssertTrue($oStopped.Item("state") = $HOME_UPGRADE_OUTCOME_UNCONFIRMED, "post-selection Stop is uncertainty at boundary " & $i)
	EndIf
	AssertTrue($g_iConfirmCalls = 0, "Stop before confirmation issues no resource spend at boundary " & $i)
Next

FixtureReset()
$g_iStopAt = 7
Local $oAfterConfirmStop = FixtureRun()
AssertTrue($oAfterConfirmStop.Item("state") = $HOME_UPGRADE_OUTCOME_UNCONFIRMED And $oAfterConfirmStop.Item("confirm_issued"), "post-confirm Stop preserves irreversible truth")
AssertTrue($g_iHomeCalls = 0 And $g_iConfirmCalls = 1, "post-confirm Stop performs no capture or cleanup")

ConsoleWrite("Home upgrade one-route tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
