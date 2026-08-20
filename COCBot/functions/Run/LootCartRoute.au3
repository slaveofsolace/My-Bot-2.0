; #FUNCTION# ====================================================================================================================
; Name ..........: Loot Cart route
; Description ...: Defines a bounded, side-effect-injectable Loot Cart collection state machine.
; Remarks .......: This route never calls the legacy CollectLootCart routine. It opens no chat, uses no fallback coordinates,
;                  accepts no confirmation or gem-conversion dialog, and permits at most one Collect input.
; ===============================================================================================================================
#include-once

Global Const $LOOT_CART_STATE_AVAILABLE = "cart-available"
Global Const $LOOT_CART_STATE_ABSENT = "cart-absent"
Global Const $LOOT_CART_STATE_COLLECT_READY = "collect-ready"
Global Const $LOOT_CART_STATE_COLLECT_MISSING = "collect-missing"
Global Const $LOOT_CART_OUTCOME_COLLECT_ISSUED = "collect-issued"
Global Const $LOOT_CART_OUTCOME_UNAVAILABLE = "unavailable"
Global Const $LOOT_CART_OUTCOME_UNCONFIRMED = "unconfirmed"
Global Const $LOOT_CART_OUTCOME_CANCELLED = "cancelled"

Func LootCartObservationCreate($sState, $iX = -1, $iY = -1)
	Local $oObservation = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oObservation) Then Return SetError(1, 0, 0)
	$oObservation.CompareMode = 1
	$oObservation.Add("state", StringLower(StringStripWS(String($sState), $STR_STRIPALL)))
	$oObservation.Add("x", Int($iX))
	$oObservation.Add("y", Int($iY))
	Return $oObservation
EndFunc   ;==>LootCartObservationCreate

Func LootCartObservationValid(ByRef $oObservation)
	If Not IsObj($oObservation) Or Not $oObservation.Exists("state") Or _
			Not $oObservation.Exists("x") Or Not $oObservation.Exists("y") Then Return False
	Local $sState = StringLower(String($oObservation.Item("state")))
	Switch $sState
		Case $LOOT_CART_STATE_AVAILABLE, $LOOT_CART_STATE_COLLECT_READY
			Return Int($oObservation.Item("x")) >= 0 And Int($oObservation.Item("x")) <= 859 And _
					Int($oObservation.Item("y")) >= 0 And Int($oObservation.Item("y")) <= 731
		Case $LOOT_CART_STATE_ABSENT, $LOOT_CART_STATE_COLLECT_MISSING
			Return Int($oObservation.Item("x")) = -1 And Int($oObservation.Item("y")) = -1
	EndSwitch
	Return False
EndFunc   ;==>LootCartObservationValid

Func LootCartOutcomeCreate()
	Local $oOutcome = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oOutcome) Then Return SetError(1, 0, 0)
	$oOutcome.CompareMode = 1
	$oOutcome.Add("state", $LOOT_CART_OUTCOME_UNCONFIRMED)
	$oOutcome.Add("detail", "not started")
	$oOutcome.Add("cart_state", "")
	$oOutcome.Add("collect_state", "")
	$oOutcome.Add("cart_attempts", 0)
	$oOutcome.Add("cart_issued", False)
	$oOutcome.Add("collect_attempts", 0)
	$oOutcome.Add("collect_issued", False)
	$oOutcome.Add("home_proven", False)
	Return $oOutcome
EndFunc   ;==>LootCartOutcomeCreate

Func _LootCartRouteCancel(ByRef $oOutcome, $sDetail, $bAfterInput = False)
	$oOutcome.Item("state") = $bAfterInput ? $LOOT_CART_OUTCOME_UNCONFIRMED : $LOOT_CART_OUTCOME_CANCELLED
	$oOutcome.Item("detail") = $sDetail
	Return $oOutcome
EndFunc   ;==>_LootCartRouteCancel

; Home proof is observation-only. This callback may capture pixels but may not issue cleanup input.
Func _LootCartRouteFinish(ByRef $oOutcome, $sState, $sDetail, $sProveHomeCallback)
	$oOutcome.Item("state") = $sState
	$oOutcome.Item("detail") = $sDetail
	Local $bHome = Call($sProveHomeCallback)
	Local $iHomeError = @error
	$oOutcome.Item("home_proven") = ($iHomeError = 0 And $bHome)
	If Not $oOutcome.Item("home_proven") And $sState <> $LOOT_CART_OUTCOME_UNCONFIRMED Then
		$oOutcome.Item("state") = $LOOT_CART_OUTCOME_UNCONFIRMED
		$oOutcome.Item("detail") &= "; Home Village was not passively re-proven"
	EndIf
	Return $oOutcome
EndFunc   ;==>_LootCartRouteFinish

; Callback contract: detect_cart()->observation, issue_cart(x,y)->bool, detect_collect()->observation,
; issue_collect(x,y)->bool, stop_requested()->bool, prove_home()->bool. The two permitted input attempts
; are latched before their callbacks and their accepted-delivery receipts are recorded separately.
Func LootCartRouteRunAdapter($sDetectCartCallback, $sIssueCartCallback, $sDetectCollectCallback, _
		$sIssueCollectCallback, $sStopRequestedCallback, $sProveHomeCallback)
	Local $oOutcome = LootCartOutcomeCreate()
	If Not IsObj($oOutcome) Then Return SetError(1, 0, 0)

	If Call($sStopRequestedCallback) Then _
		Return _LootCartRouteCancel($oOutcome, "Stop requested before Loot Cart recognition")
	Local $oCart = Call($sDetectCartCallback)
	Local $iCartError = @error
	If $iCartError Or Not LootCartObservationValid($oCart) Then
		If Call($sStopRequestedCallback) Then _
			Return _LootCartRouteCancel($oOutcome, "Stop requested during Loot Cart recognition")
		Return _LootCartRouteFinish($oOutcome, $LOOT_CART_OUTCOME_UNCONFIRMED, _
				"Fresh Loot Cart state was not recognized", $sProveHomeCallback)
	EndIf
	$oOutcome.Item("cart_state") = StringLower(String($oCart.Item("state")))
	If $oOutcome.Item("cart_state") = $LOOT_CART_STATE_ABSENT Then _
		Return _LootCartRouteFinish($oOutcome, $LOOT_CART_OUTCOME_UNAVAILABLE, _
				"No actionable Loot Cart was recognized", $sProveHomeCallback)
	If $oOutcome.Item("cart_state") <> $LOOT_CART_STATE_AVAILABLE Then _
		Return _LootCartRouteFinish($oOutcome, $LOOT_CART_OUTCOME_UNCONFIRMED, _
				"Expected one actionable Loot Cart before any input", $sProveHomeCallback)

	If Call($sStopRequestedCallback) Then _
		Return _LootCartRouteCancel($oOutcome, "Stop requested immediately before opening the Loot Cart")
	$oOutcome.Item("cart_attempts") = 1
	Local $bCartIssued = Call($sIssueCartCallback, Int($oCart.Item("x")), Int($oCart.Item("y")))
	Local $iCartIssueError = @error
	If $iCartIssueError Or Not $bCartIssued Then
		If Call($sStopRequestedCallback) Then _
			Return _LootCartRouteCancel($oOutcome, "Stop requested during the Loot Cart open attempt")
		Local $sCartIssueDetail = $iCartIssueError = 6 ? _
				"Passive no-gem guard recognized a gem surface; no Loot Cart open input was issued" : _
				"The one Loot Cart open attempt was not accepted by the input adapter"
		Return _LootCartRouteFinish($oOutcome, $LOOT_CART_OUTCOME_UNCONFIRMED, $sCartIssueDetail, $sProveHomeCallback)
	EndIf
	$oOutcome.Item("cart_issued") = True
	If Call($sStopRequestedCallback) Then _
		Return _LootCartRouteCancel($oOutcome, _
				"Stop requested after opening the Loot Cart; no further capture or input was attempted", True)

	Local $oCollect = Call($sDetectCollectCallback)
	Local $iCollectError = @error
	If $iCollectError Or Not LootCartObservationValid($oCollect) Then
		If Call($sStopRequestedCallback) Then _
			Return _LootCartRouteCancel($oOutcome, _
					"Stop requested while recognizing Collect; no further input was attempted", True)
		Return _LootCartRouteFinish($oOutcome, $LOOT_CART_OUTCOME_UNCONFIRMED, _
				"Fresh Loot Cart Collect state was not recognized", $sProveHomeCallback)
	EndIf
	$oOutcome.Item("collect_state") = StringLower(String($oCollect.Item("state")))
	If $oOutcome.Item("collect_state") = $LOOT_CART_STATE_COLLECT_MISSING Then _
		Return _LootCartRouteFinish($oOutcome, $LOOT_CART_OUTCOME_UNCONFIRMED, _
				"The Loot Cart opened but no exact Collect button was recognized", $sProveHomeCallback)
	If $oOutcome.Item("collect_state") <> $LOOT_CART_STATE_COLLECT_READY Then _
		Return _LootCartRouteFinish($oOutcome, $LOOT_CART_OUTCOME_UNCONFIRMED, _
				"Expected one exact Collect button after opening the Loot Cart", $sProveHomeCallback)

	; This Stop poll is the final operation before the irreversible resource-transfer input.
	If Call($sStopRequestedCallback) Then _
		Return _LootCartRouteCancel($oOutcome, _
				"Stop requested immediately before Loot Cart Collect; no Collect input was attempted", True)
	$oOutcome.Item("collect_attempts") = 1
	Local $bCollectIssued = Call($sIssueCollectCallback, Int($oCollect.Item("x")), Int($oCollect.Item("y")))
	Local $iCollectIssueError = @error
	If $iCollectIssueError Or Not $bCollectIssued Then
		If Call($sStopRequestedCallback) Then _
			Return _LootCartRouteCancel($oOutcome, _
					"Stop requested during the Collect attempt; no input-delivery receipt was returned", True)
		Local $sCollectIssueDetail = $iCollectIssueError = 6 ? _
				"Passive no-gem guard recognized a gem surface; no Loot Cart Collect input was issued" : _
				"The one Loot Cart Collect attempt was not accepted by the input adapter"
		Return _LootCartRouteFinish($oOutcome, $LOOT_CART_OUTCOME_UNCONFIRMED, $sCollectIssueDetail, $sProveHomeCallback)
	EndIf
	$oOutcome.Item("collect_issued") = True
	If Call($sStopRequestedCallback) Then _
		Return _LootCartRouteCancel($oOutcome, _
				"Stop requested after Loot Cart Collect; no post-input capture was attempted", True)

	Return _LootCartRouteFinish($oOutcome, $LOOT_CART_OUTCOME_COLLECT_ISSUED, _
			"One exact Loot Cart Collect input was issued", $sProveHomeCallback)
EndFunc   ;==>LootCartRouteRunAdapter
