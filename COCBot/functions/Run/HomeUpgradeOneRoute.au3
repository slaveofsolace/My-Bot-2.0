; #FUNCTION# ====================================================================================================================
; Name ..........: One Home upgrade route
; Description ...: Defines a bounded, side-effect-injectable state machine for starting one observed no-gem upgrade.
; Remarks .......: This adapter never calls inherited Auto Upgrade, wall, or Hero routines. Candidate, confirmation, resource,
;                  builder, and post-start observations must agree. It permits one selection and one irreversible confirmation,
;                  never retries a confirmation, and remains unwired until a reviewed recognizer and fixture exist.
; ===============================================================================================================================
#include-once
#include <StringConstants.au3>

Global Const $HOME_UPGRADE_STATE_CANDIDATE_READY = "candidate-ready"
Global Const $HOME_UPGRADE_STATE_UNAVAILABLE = "unavailable"
Global Const $HOME_UPGRADE_STATE_CONFIRM_READY = "confirm-ready"
Global Const $HOME_UPGRADE_STATE_POST_STARTED = "post-started"
Global Const $HOME_UPGRADE_OUTCOME_STARTED = "started"
Global Const $HOME_UPGRADE_OUTCOME_UNAVAILABLE = "unavailable"
Global Const $HOME_UPGRADE_OUTCOME_UNCONFIRMED = "unconfirmed"
Global Const $HOME_UPGRADE_OUTCOME_CANCELLED = "cancelled"

Func HomeUpgradeObservationCreate($sState, $sBuildingId = "", $iLevel = -1, $sResource = "", $iCost = 0, _
		$iAvailable = 0, $iReserve = 0, $bBuilderFree = False, $bUpgradeInProgress = False, _
		$iX = -1, $iY = -1, $bGemSurface = False)
	Local $oObservation = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oObservation) Then Return SetError(1, 0, 0)
	$oObservation.CompareMode = 1
	$oObservation.Add("state", StringLower(StringStripWS(String($sState), $STR_STRIPALL)))
	$oObservation.Add("building_id", StringLower(StringStripWS(String($sBuildingId), $STR_STRIPALL)))
	$oObservation.Add("level", Int($iLevel))
	$oObservation.Add("resource", StringLower(StringStripWS(String($sResource), $STR_STRIPALL)))
	$oObservation.Add("cost", Int($iCost))
	$oObservation.Add("available", Int($iAvailable))
	$oObservation.Add("reserve", Int($iReserve))
	$oObservation.Add("builder_free", $bBuilderFree ? True : False)
	$oObservation.Add("upgrade_in_progress", $bUpgradeInProgress ? True : False)
	$oObservation.Add("x", Int($iX))
	$oObservation.Add("y", Int($iY))
	$oObservation.Add("gem_surface", $bGemSurface ? True : False)
	Return $oObservation
EndFunc   ;==>HomeUpgradeObservationCreate

Func HomeUpgradeObservationValid(ByRef $oObservation)
	If Not IsObj($oObservation) Then Return False
	Local $aFields = ["state", "building_id", "level", "resource", "cost", "available", "reserve", _
			"builder_free", "upgrade_in_progress", "x", "y", "gem_surface"]
	For $sField In $aFields
		If Not $oObservation.Exists($sField) Then Return False
	Next
	If $oObservation.Item("gem_surface") Then Return False
	Local $sState = StringLower(String($oObservation.Item("state")))
	If $sState = $HOME_UPGRADE_STATE_UNAVAILABLE Then _
		Return String($oObservation.Item("building_id")) = "" And Int($oObservation.Item("x")) = -1 And Int($oObservation.Item("y")) = -1
	If $sState <> $HOME_UPGRADE_STATE_CANDIDATE_READY And $sState <> $HOME_UPGRADE_STATE_CONFIRM_READY And _
			$sState <> $HOME_UPGRADE_STATE_POST_STARTED Then Return False
	If Not StringRegExp(String($oObservation.Item("building_id")), "^[a-z0-9][a-z0-9-]{0,63}$") Then Return False
	If Int($oObservation.Item("level")) < 0 Or Int($oObservation.Item("level")) > 99 Then Return False
	Switch StringLower(String($oObservation.Item("resource")))
		Case "gold", "elixir", "dark-elixir"
		Case Else
			Return False
	EndSwitch
	If Int($oObservation.Item("cost")) < 1 Or Int($oObservation.Item("cost")) > 2000000000 Then Return False
	If Int($oObservation.Item("available")) < 0 Or Int($oObservation.Item("available")) > 2000000000 Then Return False
	If Int($oObservation.Item("reserve")) < 0 Or Int($oObservation.Item("reserve")) > 2000000000 Then Return False
	If $sState = $HOME_UPGRADE_STATE_POST_STARTED Then _
		Return Int($oObservation.Item("x")) = -1 And Int($oObservation.Item("y")) = -1
	Return Int($oObservation.Item("x")) >= 0 And Int($oObservation.Item("x")) <= 859 And _
			Int($oObservation.Item("y")) >= 0 And Int($oObservation.Item("y")) <= 731
EndFunc   ;==>HomeUpgradeObservationValid

Func HomeUpgradeOutcomeCreate()
	Local $oOutcome = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oOutcome) Then Return SetError(1, 0, 0)
	$oOutcome.CompareMode = 1
	$oOutcome.Add("state", $HOME_UPGRADE_OUTCOME_UNCONFIRMED)
	$oOutcome.Add("detail", "not started")
	$oOutcome.Add("building_id", "")
	$oOutcome.Add("resource", "")
	$oOutcome.Add("cost", 0)
	$oOutcome.Add("available_before", -1)
	$oOutcome.Add("available_after", -1)
	$oOutcome.Add("reserve", -1)
	$oOutcome.Add("select_attempts", 0)
	$oOutcome.Add("select_issued", False)
	$oOutcome.Add("confirm_attempts", 0)
	$oOutcome.Add("confirm_issued", False)
	$oOutcome.Add("post_state_proven", False)
	$oOutcome.Add("home_proven", False)
	Return $oOutcome
EndFunc   ;==>HomeUpgradeOutcomeCreate

Func _HomeUpgradeCancel(ByRef $oOutcome, $sDetail, $bAfterInput = False)
	$oOutcome.Item("state") = $bAfterInput ? $HOME_UPGRADE_OUTCOME_UNCONFIRMED : $HOME_UPGRADE_OUTCOME_CANCELLED
	$oOutcome.Item("detail") = $sDetail
	Return $oOutcome
EndFunc   ;==>_HomeUpgradeCancel

Func _HomeUpgradeFinish(ByRef $oOutcome, $sState, $sDetail, $sCloseAndProveHomeCallback)
	$oOutcome.Item("state") = $sState
	$oOutcome.Item("detail") = $sDetail
	Local $bHome = Call($sCloseAndProveHomeCallback)
	Local $iHomeError = @error
	$oOutcome.Item("home_proven") = ($iHomeError = 0 And $bHome)
	If Not $oOutcome.Item("home_proven") And $sState <> $HOME_UPGRADE_OUTCOME_UNCONFIRMED Then
		$oOutcome.Item("state") = $HOME_UPGRADE_OUTCOME_UNCONFIRMED
		$oOutcome.Item("detail") &= "; Home Village was not re-proven"
	EndIf
	Return $oOutcome
EndFunc   ;==>_HomeUpgradeFinish

Func _HomeUpgradeSameOffer(ByRef $oCandidate, ByRef $oConfirm)
	Return String($oConfirm.Item("building_id")) = String($oCandidate.Item("building_id")) And _
			Int($oConfirm.Item("level")) = Int($oCandidate.Item("level")) And _
			String($oConfirm.Item("resource")) = String($oCandidate.Item("resource")) And _
			Int($oConfirm.Item("cost")) = Int($oCandidate.Item("cost")) And _
			Int($oConfirm.Item("available")) = Int($oCandidate.Item("available")) And _
			Int($oConfirm.Item("reserve")) = Int($oCandidate.Item("reserve")) And _
			$oConfirm.Item("builder_free") And Not $oConfirm.Item("upgrade_in_progress")
EndFunc   ;==>_HomeUpgradeSameOffer

Func _HomeUpgradePostProvesStart(ByRef $oCandidate, ByRef $oPost)
	If StringLower(String($oPost.Item("state"))) <> $HOME_UPGRADE_STATE_POST_STARTED Then Return False
	Return String($oPost.Item("building_id")) = String($oCandidate.Item("building_id")) And _
			Int($oPost.Item("level")) = Int($oCandidate.Item("level")) And _
			String($oPost.Item("resource")) = String($oCandidate.Item("resource")) And _
			Int($oPost.Item("cost")) = Int($oCandidate.Item("cost")) And _
			Int($oPost.Item("reserve")) = Int($oCandidate.Item("reserve")) And _
			Int($oPost.Item("available")) = Int($oCandidate.Item("available")) - Int($oCandidate.Item("cost")) And _
			Not $oPost.Item("builder_free") And $oPost.Item("upgrade_in_progress")
EndFunc   ;==>_HomeUpgradePostProvesStart

; Callback contract: detect(phase)->observation, issue_select(x,y)->bool, issue_confirm(x,y)->bool,
; stop()->bool, no_gem_ready()->bool, close_and_prove_home()->bool. Confirmation is attempted at most once.
Func HomeUpgradeOneRouteRunAdapter($iConfiguredCostCap, $sDetectCallback, $sIssueSelectCallback, _
		$sIssueConfirmCallback, $sStopRequestedCallback, $sNoGemReadyCallback, $sCloseAndProveHomeCallback)
	Local $oOutcome = HomeUpgradeOutcomeCreate()
	If Not IsObj($oOutcome) Then Return SetError(1, 0, 0)
	If Int($iConfiguredCostCap) < 1 Then Return _HomeUpgradeFinish($oOutcome, $HOME_UPGRADE_OUTCOME_UNCONFIRMED, _
			"A positive configured upgrade cost cap is required", $sCloseAndProveHomeCallback)
	If Call($sStopRequestedCallback) Then Return _HomeUpgradeCancel($oOutcome, "Stop requested before upgrade recognition")

	Local $oCandidate = Call($sDetectCallback, "candidate")
	Local $iCandidateError = @error
	If $iCandidateError Or Not HomeUpgradeObservationValid($oCandidate) Then _
		Return _HomeUpgradeFinish($oOutcome, $HOME_UPGRADE_OUTCOME_UNCONFIRMED, _
				"Fresh upgrade candidate state was not recognized", $sCloseAndProveHomeCallback)
	If StringLower(String($oCandidate.Item("state"))) = $HOME_UPGRADE_STATE_UNAVAILABLE Then _
		Return _HomeUpgradeFinish($oOutcome, $HOME_UPGRADE_OUTCOME_UNAVAILABLE, _
				"No eligible upgrade candidate was recognized", $sCloseAndProveHomeCallback)
	If StringLower(String($oCandidate.Item("state"))) <> $HOME_UPGRADE_STATE_CANDIDATE_READY Or _
			Not $oCandidate.Item("builder_free") Or $oCandidate.Item("upgrade_in_progress") Or _
			Int($oCandidate.Item("cost")) > Int($iConfiguredCostCap) Or _
			Int($oCandidate.Item("available")) - Int($oCandidate.Item("cost")) < Int($oCandidate.Item("reserve")) Then _
		Return _HomeUpgradeFinish($oOutcome, $HOME_UPGRADE_OUTCOME_UNCONFIRMED, _
				"Observed cost, resource reserve, or builder policy rejected the candidate", $sCloseAndProveHomeCallback)

	$oOutcome.Item("building_id") = String($oCandidate.Item("building_id"))
	$oOutcome.Item("resource") = String($oCandidate.Item("resource"))
	$oOutcome.Item("cost") = Int($oCandidate.Item("cost"))
	$oOutcome.Item("available_before") = Int($oCandidate.Item("available"))
	$oOutcome.Item("reserve") = Int($oCandidate.Item("reserve"))
	If Call($sStopRequestedCallback) Then Return _HomeUpgradeCancel($oOutcome, "Stop requested before the selection no-gem guard")
	Local $bSelectSafe = Call($sNoGemReadyCallback)
	Local $iSelectSafeError = @error
	If $iSelectSafeError Or Not $bSelectSafe Then Return _HomeUpgradeFinish($oOutcome, $HOME_UPGRADE_OUTCOME_UNCONFIRMED, _
			"Passive no-gem guard blocked the candidate selection", $sCloseAndProveHomeCallback)
	If Call($sStopRequestedCallback) Then Return _HomeUpgradeCancel($oOutcome, "Stop requested immediately before selecting the upgrade")
	$oOutcome.Item("select_attempts") = 1
	Local $bSelectIssued = Call($sIssueSelectCallback, Int($oCandidate.Item("x")), Int($oCandidate.Item("y")))
	Local $iSelectError = @error
	If $iSelectError Or Not $bSelectIssued Then Return _HomeUpgradeFinish($oOutcome, $HOME_UPGRADE_OUTCOME_UNCONFIRMED, _
			"The one upgrade selection attempt was not accepted", $sCloseAndProveHomeCallback)
	$oOutcome.Item("select_issued") = True
	If Call($sStopRequestedCallback) Then Return _HomeUpgradeCancel($oOutcome, _
			"Stop requested after selection; no confirmation capture or input was attempted", True)

	Local $oConfirm = Call($sDetectCallback, "confirm")
	Local $iConfirmError = @error
	If $iConfirmError Or Not HomeUpgradeObservationValid($oConfirm) Or _
			StringLower(String($oConfirm.Item("state"))) <> $HOME_UPGRADE_STATE_CONFIRM_READY Or _
			Not _HomeUpgradeSameOffer($oCandidate, $oConfirm) Then _
		Return _HomeUpgradeFinish($oOutcome, $HOME_UPGRADE_OUTCOME_UNCONFIRMED, _
				"The confirmation surface did not exactly match the observed candidate", $sCloseAndProveHomeCallback)
	If Call($sStopRequestedCallback) Then Return _HomeUpgradeCancel($oOutcome, _
			"Stop requested before the confirmation no-gem guard", True)
	Local $bConfirmSafe = Call($sNoGemReadyCallback)
	Local $iConfirmSafeError = @error
	If $iConfirmSafeError Or Not $bConfirmSafe Then Return _HomeUpgradeFinish($oOutcome, $HOME_UPGRADE_OUTCOME_UNCONFIRMED, _
			"Passive no-gem guard blocked the upgrade confirmation", $sCloseAndProveHomeCallback)
	; This is the final Stop poll before the only irreversible resource-spend input.
	If Call($sStopRequestedCallback) Then Return _HomeUpgradeCancel($oOutcome, _
			"Stop requested immediately before upgrade confirmation", True)
	$oOutcome.Item("confirm_attempts") = 1
	Local $bConfirmIssued = Call($sIssueConfirmCallback, Int($oConfirm.Item("x")), Int($oConfirm.Item("y")))
	Local $iConfirmIssueError = @error
	If $iConfirmIssueError Or Not $bConfirmIssued Then Return _HomeUpgradeFinish($oOutcome, $HOME_UPGRADE_OUTCOME_UNCONFIRMED, _
			"The one upgrade confirmation attempt was not accepted", $sCloseAndProveHomeCallback)
	$oOutcome.Item("confirm_issued") = True
	If Call($sStopRequestedCallback) Then Return _HomeUpgradeCancel($oOutcome, _
			"Stop requested after confirmation; no post-input capture or cleanup was attempted", True)

	Local $oPost = Call($sDetectCallback, "post")
	Local $iPostError = @error
	If $iPostError Or Not HomeUpgradeObservationValid($oPost) Or Not _HomeUpgradePostProvesStart($oCandidate, $oPost) Then _
		Return _HomeUpgradeFinish($oOutcome, $HOME_UPGRADE_OUTCOME_UNCONFIRMED, _
				"Upgrade confirmation was issued but exact resource and builder post-state was not proved; it will not be retried", _
				$sCloseAndProveHomeCallback)
	$oOutcome.Item("available_after") = Int($oPost.Item("available"))
	$oOutcome.Item("post_state_proven") = True
	Return _HomeUpgradeFinish($oOutcome, $HOME_UPGRADE_OUTCOME_STARTED, _
			"One observed no-gem Home upgrade was started and confirmed", $sCloseAndProveHomeCallback)
EndFunc   ;==>HomeUpgradeOneRouteRunAdapter
