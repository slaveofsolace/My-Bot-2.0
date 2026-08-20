; #FUNCTION# ====================================================================================================================
; Name ..........: One-unit clan donation route
; Description ...: Defines a bounded, side-effect-injectable donation state machine for one structured request icon.
; Remarks .......: This adapter is intentionally not wired to the inherited DonateCC path. It accepts no OCR or request text,
;                  requires a proved reserve above the attack-army floor, permits one input attempt, and never retries an
;                  issued-but-unconfirmed donation. Home proof is observation-only.
; ===============================================================================================================================
#include-once
#include <StringConstants.au3>

Global Const $CLAN_DONATION_STATE_STRUCTURED_READY = "structured-ready"
Global Const $CLAN_DONATION_STATE_UNAVAILABLE = "unavailable"
Global Const $CLAN_DONATION_STATE_POST_DONATED = "post-donated"
Global Const $CLAN_DONATION_OUTCOME_COMMITTED = "committed"
Global Const $CLAN_DONATION_OUTCOME_UNAVAILABLE = "unavailable"
Global Const $CLAN_DONATION_OUTCOME_UNCONFIRMED = "unconfirmed"
Global Const $CLAN_DONATION_OUTCOME_CANCELLED = "cancelled"

Func ClanDonationObservationCreate($sState, $iRequestSlot = -1, $sUnitId = "", $iCapacity = 0, _
		$iSourceAvailable = 0, $iSourceReserve = 0, $sRecognition = "none", $bFreeTextUsed = False)
	Local $oObservation = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oObservation) Then Return SetError(1, 0, 0)
	$oObservation.CompareMode = 1
	$oObservation.Add("state", StringLower(StringStripWS(String($sState), $STR_STRIPALL)))
	$oObservation.Add("request_slot", Int($iRequestSlot))
	$oObservation.Add("unit_id", StringLower(StringStripWS(String($sUnitId), $STR_STRIPALL)))
	$oObservation.Add("recipient_capacity", Int($iCapacity))
	$oObservation.Add("source_available", Int($iSourceAvailable))
	$oObservation.Add("source_reserve", Int($iSourceReserve))
	$oObservation.Add("recognition", StringLower(StringStripWS(String($sRecognition), $STR_STRIPALL)))
	$oObservation.Add("free_text_used", $bFreeTextUsed ? True : False)
	Return $oObservation
EndFunc   ;==>ClanDonationObservationCreate

Func ClanDonationObservationValid(ByRef $oObservation)
	If Not IsObj($oObservation) Then Return False
	Local $aFields = ["state", "request_slot", "unit_id", "recipient_capacity", "source_available", _
			"source_reserve", "recognition", "free_text_used"]
	For $sField In $aFields
		If Not $oObservation.Exists($sField) Then Return False
	Next
	If $oObservation.Item("free_text_used") Then Return False
	Local $sState = StringLower(String($oObservation.Item("state")))
	If $sState = $CLAN_DONATION_STATE_UNAVAILABLE Then _
		Return Int($oObservation.Item("request_slot")) = -1 And String($oObservation.Item("unit_id")) = "" And _
				StringLower(String($oObservation.Item("recognition"))) = "none"
	If $sState <> $CLAN_DONATION_STATE_STRUCTURED_READY And $sState <> $CLAN_DONATION_STATE_POST_DONATED Then Return False
	If StringLower(String($oObservation.Item("recognition"))) <> "structured-icon" Then Return False
	If Not StringRegExp(String($oObservation.Item("unit_id")), "^[a-z0-9][a-z0-9-]{0,39}$") Then Return False
	If Int($oObservation.Item("request_slot")) < 0 Or Int($oObservation.Item("request_slot")) > 19 Then Return False
	If Int($oObservation.Item("recipient_capacity")) < 0 Or Int($oObservation.Item("recipient_capacity")) > 50 Then Return False
	If Int($oObservation.Item("source_available")) < 0 Or Int($oObservation.Item("source_available")) > 999 Then Return False
	If Int($oObservation.Item("source_reserve")) < 0 Or Int($oObservation.Item("source_reserve")) > 999 Then Return False
	Return True
EndFunc   ;==>ClanDonationObservationValid

Func ClanDonationOutcomeCreate()
	Local $oOutcome = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oOutcome) Then Return SetError(1, 0, 0)
	$oOutcome.CompareMode = 1
	$oOutcome.Add("state", $CLAN_DONATION_OUTCOME_UNCONFIRMED)
	$oOutcome.Add("detail", "not started")
	$oOutcome.Add("unit_id", "")
	$oOutcome.Add("request_slot", -1)
	$oOutcome.Add("attempts", 0)
	$oOutcome.Add("input_issued", False)
	$oOutcome.Add("confirmed", False)
	$oOutcome.Add("capacity_before", -1)
	$oOutcome.Add("capacity_after", -1)
	$oOutcome.Add("source_before", -1)
	$oOutcome.Add("source_after", -1)
	$oOutcome.Add("home_proven", False)
	Return $oOutcome
EndFunc   ;==>ClanDonationOutcomeCreate

Func _ClanDonationCancel(ByRef $oOutcome, $sDetail, $bAfterInput = False)
	$oOutcome.Item("state") = $bAfterInput ? $CLAN_DONATION_OUTCOME_UNCONFIRMED : $CLAN_DONATION_OUTCOME_CANCELLED
	$oOutcome.Item("detail") = $sDetail
	Return $oOutcome
EndFunc   ;==>_ClanDonationCancel

Func _ClanDonationFinish(ByRef $oOutcome, $sState, $sDetail, $sProveHomeCallback)
	$oOutcome.Item("state") = $sState
	$oOutcome.Item("detail") = $sDetail
	Local $bHome = Call($sProveHomeCallback)
	Local $iHomeError = @error
	$oOutcome.Item("home_proven") = ($iHomeError = 0 And $bHome)
	If Not $oOutcome.Item("home_proven") And $sState <> $CLAN_DONATION_OUTCOME_UNCONFIRMED Then
		$oOutcome.Item("state") = $CLAN_DONATION_OUTCOME_UNCONFIRMED
		$oOutcome.Item("detail") &= "; Home Village was not passively re-proven"
	EndIf
	Return $oOutcome
EndFunc   ;==>_ClanDonationFinish

Func _ClanDonationPostProvesOne(ByRef $oBefore, ByRef $oAfter)
	If StringLower(String($oAfter.Item("state"))) <> $CLAN_DONATION_STATE_POST_DONATED Then Return False
	If Int($oAfter.Item("request_slot")) <> Int($oBefore.Item("request_slot")) Or _
			String($oAfter.Item("unit_id")) <> String($oBefore.Item("unit_id")) Then Return False
	Local $iCapacityDrop = Int($oBefore.Item("recipient_capacity")) - Int($oAfter.Item("recipient_capacity"))
	Local $iSourceDrop = Int($oBefore.Item("source_available")) - Int($oAfter.Item("source_available"))
	If $iCapacityDrop < 0 Or $iCapacityDrop > 1 Or $iSourceDrop < 0 Or $iSourceDrop > 1 Then Return False
	Return $iCapacityDrop = 1 Or $iSourceDrop = 1
EndFunc   ;==>_ClanDonationPostProvesOne

; Callback contract: detect(phase)->observation, issue_one(slot,unit)->bool, stop()->bool,
; no_gem_ready()->bool, prove_home()->bool. The input callback is invoked at most once.
Func ClanDonationOneRouteRunAdapter($sDetectCallback, $sIssueOneCallback, $sStopRequestedCallback, _
		$sNoGemReadyCallback, $sProveHomeCallback)
	Local $oOutcome = ClanDonationOutcomeCreate()
	If Not IsObj($oOutcome) Then Return SetError(1, 0, 0)
	If Call($sStopRequestedCallback) Then Return _ClanDonationCancel($oOutcome, "Stop requested before donation recognition")

	Local $oBefore = Call($sDetectCallback, "before")
	Local $iBeforeError = @error
	If $iBeforeError Or Not ClanDonationObservationValid($oBefore) Then _
		Return _ClanDonationFinish($oOutcome, $CLAN_DONATION_OUTCOME_UNCONFIRMED, _
				"Fresh structured donation state was not recognized", $sProveHomeCallback)
	If StringLower(String($oBefore.Item("state"))) = $CLAN_DONATION_STATE_UNAVAILABLE Then _
		Return _ClanDonationFinish($oOutcome, $CLAN_DONATION_OUTCOME_UNAVAILABLE, _
				"No structured unit request was available", $sProveHomeCallback)
	If StringLower(String($oBefore.Item("state"))) <> $CLAN_DONATION_STATE_STRUCTURED_READY Or _
			Int($oBefore.Item("recipient_capacity")) < 1 Or _
			Int($oBefore.Item("source_available")) <= Int($oBefore.Item("source_reserve")) Then _
		Return _ClanDonationFinish($oOutcome, $CLAN_DONATION_OUTCOME_UNCONFIRMED, _
				"Structured request or proved reserve policy was not satisfied", $sProveHomeCallback)

	$oOutcome.Item("unit_id") = String($oBefore.Item("unit_id"))
	$oOutcome.Item("request_slot") = Int($oBefore.Item("request_slot"))
	$oOutcome.Item("capacity_before") = Int($oBefore.Item("recipient_capacity"))
	$oOutcome.Item("source_before") = Int($oBefore.Item("source_available"))
	If Call($sStopRequestedCallback) Then Return _ClanDonationCancel($oOutcome, "Stop requested before the no-gem guard")
	Local $bNoGemReady = Call($sNoGemReadyCallback)
	Local $iNoGemError = @error
	If $iNoGemError Or Not $bNoGemReady Then _
		Return _ClanDonationFinish($oOutcome, $CLAN_DONATION_OUTCOME_UNCONFIRMED, _
				"Passive no-gem guard did not authorize the donation input", $sProveHomeCallback)
	; This is the final Stop poll before the only irreversible input attempt.
	If Call($sStopRequestedCallback) Then Return _ClanDonationCancel($oOutcome, "Stop requested immediately before Donate")

	$oOutcome.Item("attempts") = 1
	Local $bIssued = Call($sIssueOneCallback, $oOutcome.Item("request_slot"), $oOutcome.Item("unit_id"))
	Local $iIssueError = @error
	If $iIssueError Or Not $bIssued Then _
		Return _ClanDonationFinish($oOutcome, $CLAN_DONATION_OUTCOME_UNCONFIRMED, _
				"The one Donate attempt was not accepted by the input adapter", $sProveHomeCallback)
	$oOutcome.Item("input_issued") = True
	If Call($sStopRequestedCallback) Then Return _ClanDonationCancel($oOutcome, _
			"Stop requested after Donate; no post-input capture or cleanup was attempted", True)

	Local $oAfter = Call($sDetectCallback, "after")
	Local $iAfterError = @error
	If $iAfterError Or Not ClanDonationObservationValid($oAfter) Or Not _ClanDonationPostProvesOne($oBefore, $oAfter) Then _
		Return _ClanDonationFinish($oOutcome, $CLAN_DONATION_OUTCOME_UNCONFIRMED, _
				"Donate was issued but an exact one-unit decrement was not proved; it will not be retried", $sProveHomeCallback)
	$oOutcome.Item("capacity_after") = Int($oAfter.Item("recipient_capacity"))
	$oOutcome.Item("source_after") = Int($oAfter.Item("source_available"))
	$oOutcome.Item("confirmed") = True
	Return _ClanDonationFinish($oOutcome, $CLAN_DONATION_OUTCOME_COMMITTED, _
			"One structured requested unit was donated and confirmed", $sProveHomeCallback)
EndFunc   ;==>ClanDonationOneRouteRunAdapter
