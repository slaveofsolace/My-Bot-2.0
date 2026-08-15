; #FUNCTION# ====================================================================================================================
; Name ..........: Treasury route
; Description ...: Defines a bounded, side-effect-injectable Treasury collection state machine.
; Remarks .......: This route never calls the legacy TreasuryCollect routine. It never locates a Clan Castle, clears the screen,
;                  uses fallback coordinates, retries an input, or calls generic ClickOkay. Every permitted input is latched once.
; ===============================================================================================================================
#include-once

Global Const $TREASURY_STATE_CASTLE_READY = "clan-castle-ready"
Global Const $TREASURY_STATE_CASTLE_SELECTED = "clan-castle-selected"
Global Const $TREASURY_STATE_CASTLE_MISSING = "clan-castle-missing"
Global Const $TREASURY_STATE_ENTRY_READY = "treasury-entry-ready"
Global Const $TREASURY_STATE_ENTRY_MISSING = "treasury-entry-missing"
Global Const $TREASURY_STATE_COLLECT_READY = "treasury-collect-ready"
Global Const $TREASURY_STATE_NOT_FULL = "treasury-not-full"
Global Const $TREASURY_STATE_HOME_STORAGE_FULL = "home-storage-full"
Global Const $TREASURY_STATE_COLLECT_MISSING = "treasury-collect-missing"
Global Const $TREASURY_STATE_CONFIRM_READY = "treasury-confirm-ready"
Global Const $TREASURY_STATE_CONFIRM_MISSING = "treasury-confirm-missing"
Global Const $TREASURY_OUTCOME_CONFIRM_ISSUED = "confirm-issued"
Global Const $TREASURY_OUTCOME_UNAVAILABLE = "unavailable"
Global Const $TREASURY_OUTCOME_UNCONFIRMED = "unconfirmed"
Global Const $TREASURY_OUTCOME_CANCELLED = "cancelled"

Func TreasuryObservationCreate($sState, $iX = -1, $iY = -1)
	Local $oObservation = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oObservation) Then Return SetError(1, 0, 0)
	$oObservation.CompareMode = 1
	$oObservation.Add("state", StringLower(StringStripWS(String($sState), $STR_STRIPALL)))
	$oObservation.Add("x", Int($iX))
	$oObservation.Add("y", Int($iY))
	Return $oObservation
EndFunc   ;==>TreasuryObservationCreate

Func TreasuryObservationValid(ByRef $oObservation)
	If Not IsObj($oObservation) Or Not $oObservation.Exists("state") Or _
			Not $oObservation.Exists("x") Or Not $oObservation.Exists("y") Then Return False
	Switch StringLower(String($oObservation.Item("state")))
		Case $TREASURY_STATE_CASTLE_READY, $TREASURY_STATE_ENTRY_READY, $TREASURY_STATE_COLLECT_READY, $TREASURY_STATE_CONFIRM_READY
			Return Int($oObservation.Item("x")) >= 0 And Int($oObservation.Item("x")) <= 859 And _
					Int($oObservation.Item("y")) >= 0 And Int($oObservation.Item("y")) <= 731
		Case $TREASURY_STATE_CASTLE_SELECTED, $TREASURY_STATE_CASTLE_MISSING, $TREASURY_STATE_ENTRY_MISSING, $TREASURY_STATE_NOT_FULL, _
				$TREASURY_STATE_HOME_STORAGE_FULL, $TREASURY_STATE_COLLECT_MISSING, $TREASURY_STATE_CONFIRM_MISSING
			Return Int($oObservation.Item("x")) = -1 And Int($oObservation.Item("y")) = -1
	EndSwitch
	Return False
EndFunc   ;==>TreasuryObservationValid

Func TreasuryCleanupCreate($iCloseAttempts, $bCloseIssued, $bHomeProven)
	Local $oCleanup = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oCleanup) Then Return SetError(1, 0, 0)
	$oCleanup.CompareMode = 1
	$oCleanup.Add("close_attempts", Int($iCloseAttempts))
	$oCleanup.Add("close_issued", $bCloseIssued ? True : False)
	$oCleanup.Add("home_proven", $bHomeProven ? True : False)
	Return $oCleanup
EndFunc   ;==>TreasuryCleanupCreate

Func TreasuryOutcomeCreate()
	Local $oOutcome = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oOutcome) Then Return SetError(1, 0, 0)
	$oOutcome.CompareMode = 1
	$oOutcome.Add("state", $TREASURY_OUTCOME_UNCONFIRMED)
	$oOutcome.Add("detail", "not started")
	Local $aSteps = ["castle", "entry", "collect", "confirm", "close"]
	For $sStep In $aSteps
		$oOutcome.Add($sStep & "_attempts", 0)
		$oOutcome.Add($sStep & "_issued", False)
	Next
	$oOutcome.Add("home_proven", False)
	Return $oOutcome
EndFunc   ;==>TreasuryOutcomeCreate

Func _TreasuryRouteCancel(ByRef $oOutcome, $sDetail, $bAfterInput = False)
	$oOutcome.Item("state") = $bAfterInput ? $TREASURY_OUTCOME_UNCONFIRMED : $TREASURY_OUTCOME_CANCELLED
	$oOutcome.Item("detail") = $sDetail
	Return $oOutcome
EndFunc   ;==>_TreasuryRouteCancel

; Cleanup may issue at most one recognized Treasury-window close and must return an explicit receipt.
Func _TreasuryRouteFinish(ByRef $oOutcome, $sState, $sDetail, $sCleanupCallback)
	$oOutcome.Item("state") = $sState
	$oOutcome.Item("detail") = $sDetail
	Local $oCleanup = Call($sCleanupCallback)
	Local $iCleanupError = @error
	If $iCleanupError Or Not IsObj($oCleanup) Or Not $oCleanup.Exists("close_attempts") Or _
			Not $oCleanup.Exists("close_issued") Or Not $oCleanup.Exists("home_proven") Then
		$oOutcome.Item("state") = $TREASURY_OUTCOME_UNCONFIRMED
		$oOutcome.Item("detail") &= "; cleanup returned no bounded receipt"
		Return $oOutcome
	EndIf
	$oOutcome.Item("close_attempts") = Int($oCleanup.Item("close_attempts"))
	$oOutcome.Item("close_issued") = $oCleanup.Item("close_issued") ? True : False
	$oOutcome.Item("home_proven") = $oCleanup.Item("home_proven") ? True : False
	If $oOutcome.Item("close_attempts") < 0 Or $oOutcome.Item("close_attempts") > 1 Or _
			($oOutcome.Item("close_issued") And $oOutcome.Item("close_attempts") <> 1) Then
		$oOutcome.Item("state") = $TREASURY_OUTCOME_UNCONFIRMED
		$oOutcome.Item("detail") &= "; cleanup exceeded its one-close contract"
	ElseIf Not $oOutcome.Item("home_proven") Then
		$oOutcome.Item("state") = $TREASURY_OUTCOME_UNCONFIRMED
		$oOutcome.Item("detail") &= "; Home Village was not re-proven"
	EndIf
	Return $oOutcome
EndFunc   ;==>_TreasuryRouteFinish

; Recognition may finish on the same scheduler turn that Stop becomes visible. Poll again at the
; finish boundary so a latched Stop never enters the cleanup callback. The live cleanup callback
; independently rechecks Stop immediately before any permitted close input.
Func _TreasuryRouteFinishUnlessStopped(ByRef $oOutcome, $sState, $sDetail, $sStopRequestedCallback, _
		$sCleanupCallback, $bAfterInput = False)
	If Call($sStopRequestedCallback) Then _
		Return _TreasuryRouteCancel($oOutcome, "Stop requested before Treasury cleanup", $bAfterInput)
	Return _TreasuryRouteFinish($oOutcome, $sState, $sDetail, $sCleanupCallback)
EndFunc   ;==>_TreasuryRouteFinishUnlessStopped

Func _TreasuryRouteReadObservation($sCallback, ByRef $oObservation)
	$oObservation = Call($sCallback)
	Local $iCallError = @error
	Return $iCallError = 0 And TreasuryObservationValid($oObservation)
EndFunc   ;==>_TreasuryRouteReadObservation

Func _TreasuryRouteIssue(ByRef $oOutcome, $sStep, $sCallback, ByRef $oObservation)
	$oOutcome.Item($sStep & "_attempts") = 1
	Local $bIssued = Call($sCallback, Int($oObservation.Item("x")), Int($oObservation.Item("y")))
	Local $iIssueError = @error
	If $iIssueError Or Not $bIssued Then Return False
	$oOutcome.Item($sStep & "_issued") = True
	Return True
EndFunc   ;==>_TreasuryRouteIssue

; Callback order: detect/issue Clan Castle, Treasury entry, Collect, and contextual Okay; then cleanup.
Func TreasuryRouteRunAdapter($sDetectCastleCallback, $sIssueCastleCallback, $sDetectEntryCallback, $sIssueEntryCallback, _
		$sDetectCollectCallback, $sIssueCollectCallback, $sDetectConfirmCallback, $sIssueConfirmCallback, _
		$sStopRequestedCallback, $sCleanupCallback)
	Local $oOutcome = TreasuryOutcomeCreate()
	If Not IsObj($oOutcome) Then Return SetError(1, 0, 0)
	Local $oObservation = 0

	If Call($sStopRequestedCallback) Then Return _TreasuryRouteCancel($oOutcome, "Stop requested before Treasury recognition")
	If Not _TreasuryRouteReadObservation($sDetectCastleCallback, $oObservation) Then _
		Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNCONFIRMED, "Fresh Clan Castle state was not recognized", $sStopRequestedCallback, $sCleanupCallback)
	If String($oObservation.Item("state")) = $TREASURY_STATE_CASTLE_MISSING Then _
		Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNAVAILABLE, "No exact cached Clan Castle location is available", $sStopRequestedCallback, $sCleanupCallback)
	Local $bAfterInput = False
	Switch String($oObservation.Item("state"))
		Case $TREASURY_STATE_CASTLE_READY
			If Call($sStopRequestedCallback) Then Return _TreasuryRouteCancel($oOutcome, "Stop requested before selecting the Clan Castle")
			If Not _TreasuryRouteIssue($oOutcome, "castle", $sIssueCastleCallback, $oObservation) Then _
				Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNCONFIRMED, "The one Clan Castle selection attempt was not accepted", $sStopRequestedCallback, $sCleanupCallback)
			$bAfterInput = True
			If Call($sStopRequestedCallback) Then Return _TreasuryRouteCancel($oOutcome, "Stop requested after selecting the Clan Castle", True)
		Case $TREASURY_STATE_CASTLE_SELECTED
			; A freshly recognized selected Clan Castle needs no redundant village input.
		Case Else
			Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNCONFIRMED, "Expected a verified or already-selected Clan Castle", $sStopRequestedCallback, $sCleanupCallback)
	EndSwitch

	If Not _TreasuryRouteReadObservation($sDetectEntryCallback, $oObservation) Then _
		Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNCONFIRMED, "The selected building was not a recognized Clan Castle with a Treasury entry", $sStopRequestedCallback, $sCleanupCallback, $bAfterInput)
	If String($oObservation.Item("state")) <> $TREASURY_STATE_ENTRY_READY Then _
		Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNCONFIRMED, "No exact Treasury entry button was recognized", $sStopRequestedCallback, $sCleanupCallback, $bAfterInput)
	If Call($sStopRequestedCallback) Then Return _TreasuryRouteCancel($oOutcome, "Stop requested before opening Treasury", $bAfterInput)
	If Not _TreasuryRouteIssue($oOutcome, "entry", $sIssueEntryCallback, $oObservation) Then _
		Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNCONFIRMED, "The one Treasury entry attempt was not accepted", $sStopRequestedCallback, $sCleanupCallback, $bAfterInput)
	$bAfterInput = True
	If Call($sStopRequestedCallback) Then Return _TreasuryRouteCancel($oOutcome, "Stop requested after opening Treasury", True)

	If Not _TreasuryRouteReadObservation($sDetectCollectCallback, $oObservation) Then _
		Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNCONFIRMED, "Fresh Treasury Collect state was not recognized", $sStopRequestedCallback, $sCleanupCallback, True)
	Switch String($oObservation.Item("state"))
		Case $TREASURY_STATE_NOT_FULL
			Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNAVAILABLE, "Treasury is not full; no transfer was attempted", $sStopRequestedCallback, $sCleanupCallback, True)
		Case $TREASURY_STATE_HOME_STORAGE_FULL
			Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNAVAILABLE, "A Home Village resource storage is full; no Treasury transfer was attempted", $sStopRequestedCallback, $sCleanupCallback, True)
		Case $TREASURY_STATE_COLLECT_MISSING
			Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNCONFIRMED, "Treasury is full but no exact Collect button was recognized", $sStopRequestedCallback, $sCleanupCallback, True)
		Case $TREASURY_STATE_COLLECT_READY
		Case Else
			Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNCONFIRMED, "Unexpected Treasury Collect state", $sStopRequestedCallback, $sCleanupCallback, True)
	EndSwitch
	If Call($sStopRequestedCallback) Then Return _TreasuryRouteCancel($oOutcome, "Stop requested immediately before Treasury Collect", True)
	If Not _TreasuryRouteIssue($oOutcome, "collect", $sIssueCollectCallback, $oObservation) Then _
		Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNCONFIRMED, "The one Treasury Collect attempt was not accepted", $sStopRequestedCallback, $sCleanupCallback, True)
	If Call($sStopRequestedCallback) Then Return _TreasuryRouteCancel($oOutcome, "Stop requested after Treasury Collect; no confirmation was attempted", True)

	If Not _TreasuryRouteReadObservation($sDetectConfirmCallback, $oObservation) Or _
			String($oObservation.Item("state")) <> $TREASURY_STATE_CONFIRM_READY Then _
		Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNCONFIRMED, "No contextual Treasury confirmation was recognized", $sStopRequestedCallback, $sCleanupCallback, True)
	If Call($sStopRequestedCallback) Then Return _TreasuryRouteCancel($oOutcome, "Stop requested immediately before Treasury confirmation", True)
	If Not _TreasuryRouteIssue($oOutcome, "confirm", $sIssueConfirmCallback, $oObservation) Then _
		Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_UNCONFIRMED, "The one contextual Treasury confirmation attempt was not accepted", $sStopRequestedCallback, $sCleanupCallback, True)
	If Call($sStopRequestedCallback) Then Return _TreasuryRouteCancel($oOutcome, "Stop requested after Treasury confirmation; no cleanup input was attempted", True)

	Return _TreasuryRouteFinishUnlessStopped($oOutcome, $TREASURY_OUTCOME_CONFIRM_ISSUED, _
			"One contextual Treasury confirmation input was issued; resource transfer is not visually confirmed", _
			$sStopRequestedCallback, $sCleanupCallback, True)
EndFunc   ;==>TreasuryRouteRunAdapter
