; #FUNCTION# ====================================================================================================================
; Name ..........: Exact saved-recipe training route
; Description ...: Defines one bounded queue action for a freshly recognized exact saved recipe.
; Remarks .......: No inherited trainer, Quick Train fallback, deletion, boost, gem completion, or per-unit profile array is used.
;                  The queue must be empty, the recipe id and digest must match the plan, and one post-state must prove that the
;                  exact missing-unit count and recipe digest were queued. This adapter remains unwired until dedicated fixtures exist.
; ===============================================================================================================================
#include-once
#include <StringConstants.au3>

Global Const $EXACT_TRAINING_STATE_RECIPE_READY = "recipe-ready"
Global Const $EXACT_TRAINING_STATE_UNAVAILABLE = "unavailable"
Global Const $EXACT_TRAINING_STATE_POST_QUEUED = "post-queued"
Global Const $EXACT_TRAINING_OUTCOME_QUEUED = "queued"
Global Const $EXACT_TRAINING_OUTCOME_UNAVAILABLE = "unavailable"
Global Const $EXACT_TRAINING_OUTCOME_UNCONFIRMED = "unconfirmed"
Global Const $EXACT_TRAINING_OUTCOME_CANCELLED = "cancelled"

Func ExactRecipeTrainingObservationCreate($sState, $sRecipeId = "", $sRecipeDigest = "", $iMissingUnits = 0, _
		$iQueuedUnits = 0, $sQueueDigest = "", $bBoostActive = False, $bGemSurface = False, _
		$bDeleteRequired = False, $iX = -1, $iY = -1)
	Local $oObservation = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oObservation) Then Return SetError(1, 0, 0)
	$oObservation.CompareMode = 1
	$oObservation.Add("state", StringLower(StringStripWS(String($sState), $STR_STRIPALL)))
	$oObservation.Add("recipe_id", StringLower(StringStripWS(String($sRecipeId), $STR_STRIPALL)))
	$oObservation.Add("recipe_digest", StringLower(StringStripWS(String($sRecipeDigest), $STR_STRIPALL)))
	$oObservation.Add("missing_units", Int($iMissingUnits))
	$oObservation.Add("queued_units", Int($iQueuedUnits))
	$oObservation.Add("queue_digest", StringLower(StringStripWS(String($sQueueDigest), $STR_STRIPALL)))
	$oObservation.Add("boost_active", $bBoostActive ? True : False)
	$oObservation.Add("gem_surface", $bGemSurface ? True : False)
	$oObservation.Add("delete_required", $bDeleteRequired ? True : False)
	$oObservation.Add("x", Int($iX))
	$oObservation.Add("y", Int($iY))
	Return $oObservation
EndFunc   ;==>ExactRecipeTrainingObservationCreate

Func ExactRecipeTrainingObservationValid(ByRef $oObservation)
	If Not IsObj($oObservation) Then Return False
	Local $aFields = ["state", "recipe_id", "recipe_digest", "missing_units", "queued_units", "queue_digest", _
			"boost_active", "gem_surface", "delete_required", "x", "y"]
	For $sField In $aFields
		If Not $oObservation.Exists($sField) Then Return False
	Next
	If $oObservation.Item("boost_active") Or $oObservation.Item("gem_surface") Or $oObservation.Item("delete_required") Then Return False
	Local $sState = StringLower(String($oObservation.Item("state")))
	If $sState = $EXACT_TRAINING_STATE_UNAVAILABLE Then _
		Return String($oObservation.Item("recipe_id")) = "" And Int($oObservation.Item("x")) = -1 And Int($oObservation.Item("y")) = -1
	If $sState <> $EXACT_TRAINING_STATE_RECIPE_READY And $sState <> $EXACT_TRAINING_STATE_POST_QUEUED Then Return False
	If Not StringRegExp(String($oObservation.Item("recipe_id")), "^[a-z0-9][a-z0-9_.-]{0,63}$") Then Return False
	If Not StringRegExp(String($oObservation.Item("recipe_digest")), "^[a-f0-9]{64}$") Then Return False
	If Int($oObservation.Item("missing_units")) < 0 Or Int($oObservation.Item("missing_units")) > 500 Then Return False
	If Int($oObservation.Item("queued_units")) < 0 Or Int($oObservation.Item("queued_units")) > 500 Then Return False
	If $sState = $EXACT_TRAINING_STATE_RECIPE_READY Then
		If String($oObservation.Item("queue_digest")) <> "" Or Int($oObservation.Item("queued_units")) <> 0 Then Return False
		Return Int($oObservation.Item("x")) >= 0 And Int($oObservation.Item("x")) <= 859 And _
				Int($oObservation.Item("y")) >= 0 And Int($oObservation.Item("y")) <= 731
	EndIf
	Return String($oObservation.Item("queue_digest")) = String($oObservation.Item("recipe_digest")) And _
			Int($oObservation.Item("x")) = -1 And Int($oObservation.Item("y")) = -1
EndFunc   ;==>ExactRecipeTrainingObservationValid

Func ExactRecipeTrainingOutcomeCreate()
	Local $oOutcome = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oOutcome) Then Return SetError(1, 0, 0)
	$oOutcome.CompareMode = 1
	$oOutcome.Add("state", $EXACT_TRAINING_OUTCOME_UNCONFIRMED)
	$oOutcome.Add("detail", "not started")
	$oOutcome.Add("recipe_id", "")
	$oOutcome.Add("recipe_digest", "")
	$oOutcome.Add("missing_units", 0)
	$oOutcome.Add("queue_attempts", 0)
	$oOutcome.Add("queue_issued", False)
	$oOutcome.Add("queue_confirmed", False)
	$oOutcome.Add("home_proven", False)
	Return $oOutcome
EndFunc   ;==>ExactRecipeTrainingOutcomeCreate

Func _ExactRecipeTrainingCancel(ByRef $oOutcome, $sDetail, $bAfterInput = False)
	$oOutcome.Item("state") = $bAfterInput ? $EXACT_TRAINING_OUTCOME_UNCONFIRMED : $EXACT_TRAINING_OUTCOME_CANCELLED
	$oOutcome.Item("detail") = $sDetail
	Return $oOutcome
EndFunc   ;==>_ExactRecipeTrainingCancel

Func _ExactRecipeTrainingFinish(ByRef $oOutcome, $sState, $sDetail, $sCloseAndProveHomeCallback)
	$oOutcome.Item("state") = $sState
	$oOutcome.Item("detail") = $sDetail
	Local $bHome = Call($sCloseAndProveHomeCallback)
	Local $iHomeError = @error
	$oOutcome.Item("home_proven") = ($iHomeError = 0 And $bHome)
	If Not $oOutcome.Item("home_proven") And $sState <> $EXACT_TRAINING_OUTCOME_UNCONFIRMED Then
		$oOutcome.Item("state") = $EXACT_TRAINING_OUTCOME_UNCONFIRMED
		$oOutcome.Item("detail") &= "; Home Village was not re-proven"
	EndIf
	Return $oOutcome
EndFunc   ;==>_ExactRecipeTrainingFinish

; Callback contract: detect(phase)->observation, issue_queue(x,y)->bool, stop()->bool,
; no_gem_ready()->bool, close_and_prove_home()->bool. The queue callback is invoked at most once.
Func ExactRecipeTrainingRouteRunAdapter($sExpectedRecipeId, $sExpectedRecipeDigest, $iMaxQueueUnits, _
		$sDetectCallback, $sIssueQueueCallback, $sStopRequestedCallback, $sNoGemReadyCallback, $sCloseAndProveHomeCallback)
	Local $oOutcome = ExactRecipeTrainingOutcomeCreate()
	If Not IsObj($oOutcome) Then Return SetError(1, 0, 0)
	Local $sRecipeId = StringLower(StringStripWS(String($sExpectedRecipeId), $STR_STRIPALL))
	Local $sRecipeDigest = StringLower(StringStripWS(String($sExpectedRecipeDigest), $STR_STRIPALL))
	If Not StringRegExp($sRecipeId, "^[a-z0-9][a-z0-9_.-]{0,63}$") Or _
			Not StringRegExp($sRecipeDigest, "^[a-f0-9]{64}$") Or Int($iMaxQueueUnits) < 1 Or Int($iMaxQueueUnits) > 500 Then _
		Return _ExactRecipeTrainingFinish($oOutcome, $EXACT_TRAINING_OUTCOME_UNCONFIRMED, _
				"The exact recipe identity, digest, or queue cap is invalid", $sCloseAndProveHomeCallback)
	If Call($sStopRequestedCallback) Then Return _ExactRecipeTrainingCancel($oOutcome, "Stop requested before recipe recognition")

	Local $oBefore = Call($sDetectCallback, "before")
	Local $iBeforeError = @error
	If $iBeforeError Or Not ExactRecipeTrainingObservationValid($oBefore) Then _
		Return _ExactRecipeTrainingFinish($oOutcome, $EXACT_TRAINING_OUTCOME_UNCONFIRMED, _
				"Fresh saved-recipe state was not recognized", $sCloseAndProveHomeCallback)
	If StringLower(String($oBefore.Item("state"))) = $EXACT_TRAINING_STATE_UNAVAILABLE Then _
		Return _ExactRecipeTrainingFinish($oOutcome, $EXACT_TRAINING_OUTCOME_UNAVAILABLE, _
				"The exact saved recipe was unavailable", $sCloseAndProveHomeCallback)
	If StringLower(String($oBefore.Item("state"))) <> $EXACT_TRAINING_STATE_RECIPE_READY Or _
			String($oBefore.Item("recipe_id")) <> $sRecipeId Or String($oBefore.Item("recipe_digest")) <> $sRecipeDigest Or _
			Int($oBefore.Item("missing_units")) < 1 Or Int($oBefore.Item("missing_units")) > Int($iMaxQueueUnits) Then _
		Return _ExactRecipeTrainingFinish($oOutcome, $EXACT_TRAINING_OUTCOME_UNCONFIRMED, _
				"Recipe identity, empty-queue policy, or missing-unit cap was not satisfied", $sCloseAndProveHomeCallback)

	$oOutcome.Item("recipe_id") = $sRecipeId
	$oOutcome.Item("recipe_digest") = $sRecipeDigest
	$oOutcome.Item("missing_units") = Int($oBefore.Item("missing_units"))
	If Call($sStopRequestedCallback) Then Return _ExactRecipeTrainingCancel($oOutcome, "Stop requested before the training no-gem guard")
	Local $bNoGemReady = Call($sNoGemReadyCallback)
	Local $iNoGemError = @error
	If $iNoGemError Or Not $bNoGemReady Then _
		Return _ExactRecipeTrainingFinish($oOutcome, $EXACT_TRAINING_OUTCOME_UNCONFIRMED, _
				"Passive no-gem guard blocked the recipe queue input", $sCloseAndProveHomeCallback)
	; This is the final Stop poll before the one queue input attempt.
	If Call($sStopRequestedCallback) Then Return _ExactRecipeTrainingCancel($oOutcome, "Stop requested immediately before queueing the recipe")
	$oOutcome.Item("queue_attempts") = 1
	Local $bQueueIssued = Call($sIssueQueueCallback, Int($oBefore.Item("x")), Int($oBefore.Item("y")))
	Local $iQueueError = @error
	If $iQueueError Or Not $bQueueIssued Then _
		Return _ExactRecipeTrainingFinish($oOutcome, $EXACT_TRAINING_OUTCOME_UNCONFIRMED, _
				"The one exact-recipe queue attempt was not accepted", $sCloseAndProveHomeCallback)
	$oOutcome.Item("queue_issued") = True
	If Call($sStopRequestedCallback) Then Return _ExactRecipeTrainingCancel($oOutcome, _
			"Stop requested after queueing; no post-input capture or cleanup was attempted", True)

	Local $oAfter = Call($sDetectCallback, "after")
	Local $iAfterError = @error
	If $iAfterError Or Not ExactRecipeTrainingObservationValid($oAfter) Or _
			StringLower(String($oAfter.Item("state"))) <> $EXACT_TRAINING_STATE_POST_QUEUED Or _
			String($oAfter.Item("recipe_id")) <> $sRecipeId Or String($oAfter.Item("recipe_digest")) <> $sRecipeDigest Or _
			String($oAfter.Item("queue_digest")) <> $sRecipeDigest Or _
			Int($oAfter.Item("queued_units")) <> Int($oBefore.Item("missing_units")) Or Int($oAfter.Item("missing_units")) <> 0 Then _
		Return _ExactRecipeTrainingFinish($oOutcome, $EXACT_TRAINING_OUTCOME_UNCONFIRMED, _
				"Recipe queue input was issued but its exact digest and unit delta were not proved; it will not be retried", _
				$sCloseAndProveHomeCallback)
	$oOutcome.Item("queue_confirmed") = True
	Return _ExactRecipeTrainingFinish($oOutcome, $EXACT_TRAINING_OUTCOME_QUEUED, _
			"One exact saved recipe was queued without boosts, deletion, or gem completion", $sCloseAndProveHomeCallback)
EndFunc   ;==>ExactRecipeTrainingRouteRunAdapter
