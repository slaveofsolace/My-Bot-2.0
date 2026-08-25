; #FUNCTION# ====================================================================================================================
; Name ..........: Exact saved-recipe training route
; Description ...: Defines one bounded queue action for a freshly recognized exact saved recipe.
; Remarks .......: No inherited trainer, Quick Train fallback, deletion, boost, gem completion, or per-unit profile array is used.
;                  The queue must be empty, the recipe id and digest must match the plan, and one post-state must prove that the
;                  exact missing-unit count and recipe digest were queued.
; ===============================================================================================================================
#include-once
#include <StringConstants.au3>

Global Const $EXACT_TRAINING_ROUTE_STRATEGY = "army.exact-recipe"
Global Const $EXACT_TRAINING_STATE_RECIPE_READY = "recipe-ready"
Global Const $EXACT_TRAINING_STATE_UNAVAILABLE = "unavailable"
Global Const $EXACT_TRAINING_STATE_POST_QUEUED = "post-queued"
Global Const $EXACT_TRAINING_OUTCOME_QUEUED = "queued"
Global Const $EXACT_TRAINING_OUTCOME_UNAVAILABLE = "unavailable"
Global Const $EXACT_TRAINING_OUTCOME_UNCONFIRMED = "unconfirmed"
Global Const $EXACT_TRAINING_OUTCOME_CANCELLED = "cancelled"

Func ExactRecipeTrainingRouteSelected(ByRef $oIntent)
	If Not IsObj($oIntent) Or Not $oIntent.Exists("plan") Then Return False
	Local $oPlan = $oIntent.Item("plan")
	If Not IsObj($oPlan) Or Not $oPlan.Exists("strategy") Then Return False
	Return StringLower(StringStripWS(String($oPlan.Item("strategy")), $STR_STRIPALL)) = $EXACT_TRAINING_ROUTE_STRATEGY
EndFunc   ;==>ExactRecipeTrainingRouteSelected

Func ExactRecipeTrainingRouteAccountMatches(ByRef $oIntent, $sCurrentProfile)
	If Not IsObj($oIntent) Or Not $oIntent.Exists("profile_id") Then Return False
	Local $sBound = StringStripWS(String($oIntent.Item("profile_id")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	Local $sCurrent = StringStripWS(String($sCurrentProfile), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	Return $sBound <> "" And $sCurrent <> "" And $sBound = $sCurrent
EndFunc   ;==>ExactRecipeTrainingRouteAccountMatches

Func ExactRecipeTrainingRouteRecipeId(ByRef $oIntent)
	If Not IsObj($oIntent) Or Not $oIntent.Exists("plan") Then Return ""
	Local $oPlan = $oIntent.Item("plan")
	If Not IsObj($oPlan) Or Not $oPlan.Exists("army_recipe_name") Then Return ""
	Return StringLower(StringStripWS(String($oPlan.Item("army_recipe_name")), $STR_STRIPALL))
EndFunc   ;==>ExactRecipeTrainingRouteRecipeId

Func ExactRecipeTrainingRouteRecipeDigest(ByRef $oIntent)
	If Not IsObj($oIntent) Or Not $oIntent.Exists("plan") Then Return ""
	Local $oPlan = $oIntent.Item("plan")
	If Not IsObj($oPlan) Or Not $oPlan.Exists("army_recipe_digest") Then Return ""
	Return StringLower(StringStripWS(String($oPlan.Item("army_recipe_digest")), $STR_STRIPALL))
EndFunc   ;==>ExactRecipeTrainingRouteRecipeDigest

Func ExactRecipeTrainingRouteMaxQueueUnits(ByRef $oIntent)
	If Not IsObj($oIntent) Or Not $oIntent.Exists("plan") Then Return 0
	Local $oPlan = $oIntent.Item("plan")
	If Not IsObj($oPlan) Or Not $oPlan.Exists("army_max_queue_units") Then Return 0
	Return Int($oPlan.Item("army_max_queue_units"))
EndFunc   ;==>ExactRecipeTrainingRouteMaxQueueUnits

Func ExactRecipeTrainingRouteValidate(ByRef $oIntent, ByRef $sError)
	$sError = ""
	If Not ExactRecipeTrainingRouteSelected($oIntent) Then
		$sError = "Exact saved-recipe training was not explicitly selected"
		Return SetError(1, 0, False)
	EndIf

	If StringLower(StringStripWS(String($oIntent.Item("surface_id")), $STR_STRIPALL)) <> "regular" Then
		$sError = "Exact saved-recipe training must remain bound to the current Home Village account"
		Return SetError(2, 0, False)
	EndIf

	Local $oRoute = $oIntent.Item("route")
	If Not $oRoute.Item("diagnostic_enabled") Then
		$sError = "Exact saved-recipe training requires Allow unverified and a supervised diagnostic acknowledgement"
		Return SetError(3, 0, False)
	EndIf
	Local $sProfile = StringStripWS(String($oIntent.Item("profile_id")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sProfile = "" Or StringLen($sProfile) > 64 Or Not StringRegExp($sProfile, "^[A-Za-z0-9_. -]+$") Then
		$sError = "Exact saved-recipe training requires the exact active profile/account binding"
		Return SetError(3, 1, False)
	EndIf

	Local $oPlan = $oIntent.Item("plan")
	If StringLower(StringStripWS(String($oPlan.Item("attack_script")), $STR_STRIPALL)) <> "profile-current" Then
		$sError = "Exact saved-recipe training does not accept an attack script"
		Return SetError(4, 1, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("army_source")), $STR_STRIPALL)) <> "recipe" Then
		$sError = "Exact saved-recipe training requires the saved recipe army source"
		Return SetError(4, 2, False)
	EndIf
	Local $sRecipeId = ExactRecipeTrainingRouteRecipeId($oIntent)
	Local $sRecipeDigest = ExactRecipeTrainingRouteRecipeDigest($oIntent)
	Local $iMaxQueueUnits = ExactRecipeTrainingRouteMaxQueueUnits($oIntent)
	If Not StringRegExp($sRecipeId, "^[a-z0-9][a-z0-9_.-]{0,63}$") Then
		$sError = "Exact saved-recipe training requires a safe recipe id"
		Return SetError(4, 3, False)
	EndIf
	If Not StringRegExp($sRecipeDigest, "^[a-f0-9]{64}$") Then
		$sError = "Exact saved-recipe training requires a 64-character recipe digest"
		Return SetError(4, 4, False)
	EndIf
	If $iMaxQueueUnits < 1 Or $iMaxQueueUnits > 500 Then
		$sError = "Exact saved-recipe training requires a max queue cap from 1 to 500 units"
		Return SetError(4, 5, False)
	EndIf
	If $oPlan.Item("army_manage_training") Or $oPlan.Item("army_wait_for_full") Or _
			$oPlan.Item("army_train_spells") Or $oPlan.Item("army_train_sieges") Then
		$sError = "Exact saved-recipe training owns one route-specific queue attempt; generic training, army wait, spells, and sieges must be off"
		Return SetError(5, 0, False)
	EndIf
	Local $oLoadout = $oIntent.Item("loadout")
	Local $iHeroCount = 0
	If IsObj($oLoadout) And $oLoadout.Exists("count") Then $iHeroCount = Int($oLoadout.Item("count"))
	If $iHeroCount > 0 Then
		$sError = "Exact saved-recipe training cannot deploy or inspect Heroes"
		Return SetError(6, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("donate_mode")), $STR_STRIPALL)) <> "off" Or _
			$oPlan.Item("donate_request_when_short") Or Int($oPlan.Item("donate_max_per_run")) <> 0 Then
		$sError = "Exact saved-recipe training requires donations and requests off"
		Return SetError(7, 0, False)
	EndIf
	If $oPlan.Item("events_collect_resources") Or $oPlan.Item("events_collect_daily_reward") Or _
			$oPlan.Item("events_collect_loot_cart") Or $oPlan.Item("events_collect_treasury") Or _
			$oPlan.Item("events_clan_games") Or Int($oPlan.Item("events_clan_games_point_cap")) <> 0 Then
		$sError = "Exact saved-recipe training cannot collect resources, claim rewards, or enter Clan Games"
		Return SetError(8, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("events_laboratory")), $STR_STRIPALL)) <> "off" Then
		$sError = "Exact saved-recipe training requires Laboratory off"
		Return SetError(9, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("upgrade_policy")), $STR_STRIPALL)) <> "disabled" Then
		$sError = "Exact saved-recipe training requires upgrades disabled"
		Return SetError(10, 0, False)
	EndIf
	If StringStripWS(String($oPlan.Item("account_queue_id")), $STR_STRIPALL) <> "" Then
		$sError = "Exact saved-recipe training cannot rotate accounts"
		Return SetError(11, 0, False)
	EndIf
	If Int($oPlan.Item("duration_minutes")) <> 0 Or Int($oPlan.Item("max_battles")) <> 0 Or _
			$oPlan.Item("stop_on_star_bonus") Or Int($oPlan.Item("max_failures")) <> 0 Then
		$sError = "Exact saved-recipe training is exactly one route pass; duration, battles, star bonus, and failure limits must be 0/off"
		Return SetError(11, 1, False)
	EndIf
	If Int($oPlan.Item("target_gold")) <> 0 Or Int($oPlan.Item("target_elixir")) <> 0 Or Int($oPlan.Item("target_dark_elixir")) <> 0 Then
		$sError = "Exact saved-recipe training cannot use battle-loot targets"
		Return SetError(11, 2, False)
	EndIf
	If Int($oPlan.Item("search_min_gold")) <> 0 Or Int($oPlan.Item("search_min_elixir")) <> 0 Or _
			Int($oPlan.Item("search_min_dark")) <> 0 Or Int($oPlan.Item("search_max_seconds")) <> 0 Or _
			StringLower(StringStripWS(String($oPlan.Item("search_town_hall_filter")), $STR_STRIPALL)) <> "any" Then
		$sError = "Exact saved-recipe training cannot configure matchmaking search"
		Return SetError(11, 3, False)
	EndIf
	Local $oPacing = $oIntent.Item("pacing")
	If Int($oPacing.Item("retry_attempts")) <> 0 Then
		$sError = "Exact saved-recipe training requires retries set to 0"
		Return SetError(12, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("notify_channel")), $STR_STRIPALL)) <> "log-only" Then
		$sError = "Only Bot log notifications are wired for exact saved-recipe training"
		Return SetError(13, 0, False)
	EndIf

	Local $sEmulator = StringLower(StringStripWS(String($oPlan.Item("emulator")), $STR_STRIPALL))
	Local $sInstance = StringStripWS(String($oPlan.Item("emulator_instance")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sEmulator = "" Or $sEmulator = "auto" Then
		$sError = "Choose the exact emulator for exact saved-recipe training"
		Return SetError(14, 0, False)
	EndIf
	If $sInstance = "" Then
		$sError = "Choose the exact emulator instance for exact saved-recipe training"
		Return SetError(14, 1, False)
	EndIf
	If Not StringRegExp($sInstance, "^[A-Za-z0-9_. -]{1,64}$") Then
		$sError = "The emulator instance name contains unsupported characters"
		Return SetError(14, 2, False)
	EndIf

	Return True
EndFunc   ;==>ExactRecipeTrainingRouteValidate

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
