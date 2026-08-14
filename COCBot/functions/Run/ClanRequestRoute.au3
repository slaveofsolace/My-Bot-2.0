; #FUNCTION# ====================================================================================================================
; Name ..........: Clan request route
; Description ...: Defines the bounded, request-only Home Village route and its side-effect-injectable state machine.
; Remarks .......: This route never donates, inspects/removes Clan Castle contents, enters matchmaking, or retries Send.
;                  The live adapter is supplied by RunExecution.au3; fixture tests inject no-click callbacks here.
; ===============================================================================================================================
#include-once

Global Const $CLAN_REQUEST_ROUTE_STRATEGY = "home.clan-request"
Global Const $CLAN_REQUEST_STATE_AVAILABLE = "available"
Global Const $CLAN_REQUEST_STATE_ALREADY_MADE = "already-made"
Global Const $CLAN_REQUEST_STATE_FULL_OR_UNAVAILABLE = "full-or-unavailable"
Global Const $CLAN_REQUEST_STATE_SEND_READY = "send-ready"
Global Const $CLAN_REQUEST_OUTCOME_COMMITTED = "committed"
Global Const $CLAN_REQUEST_OUTCOME_UNAVAILABLE = "unavailable"
Global Const $CLAN_REQUEST_OUTCOME_UNCONFIRMED = "unconfirmed"
Global Const $CLAN_REQUEST_OUTCOME_CANCELLED = "cancelled"

Func ClanRequestRouteSelected(ByRef $oIntent)
	If Not IsObj($oIntent) Or Not $oIntent.Exists("plan") Then Return False
	Local $oPlan = $oIntent.Item("plan")
	If Not IsObj($oPlan) Or Not $oPlan.Exists("strategy") Then Return False
	Return StringLower(StringStripWS(String($oPlan.Item("strategy")), $STR_STRIPALL)) = $CLAN_REQUEST_ROUTE_STRATEGY
EndFunc   ;==>ClanRequestRouteSelected

Func ClanRequestRouteAccountMatches(ByRef $oIntent, $sCurrentProfile)
	If Not IsObj($oIntent) Or Not $oIntent.Exists("profile_id") Then Return False
	Local $sBound = StringStripWS(String($oIntent.Item("profile_id")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	Local $sCurrent = StringStripWS(String($sCurrentProfile), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	Return $sBound <> "" And $sCurrent <> "" And $sBound = $sCurrent
EndFunc   ;==>ClanRequestRouteAccountMatches

Func ClanRequestRouteValidate(ByRef $oIntent, ByRef $sError)
	$sError = ""
	If Not ClanRequestRouteSelected($oIntent) Then
		$sError = "Clan request was not explicitly selected"
		Return SetError(1, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oIntent.Item("surface_id")), $STR_STRIPALL)) <> "regular" Then
		$sError = "Clan request must remain bound to the current Home Village account"
		Return SetError(2, 0, False)
	EndIf

	Local $oRoute = $oIntent.Item("route")
	If Not $oRoute.Item("diagnostic_enabled") Then
		$sError = "Clan request requires Allow unverified and a supervised diagnostic acknowledgement"
		Return SetError(3, 0, False)
	EndIf
	Local $sProfile = StringStripWS(String($oIntent.Item("profile_id")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sProfile = "" Or StringLen($sProfile) > 64 Or Not StringRegExp($sProfile, "^[A-Za-z0-9_. -]+$") Then
		$sError = "Clan request requires the exact active profile/account binding"
		Return SetError(4, 0, False)
	EndIf

	Local $oPlan = $oIntent.Item("plan")
	If StringLower(StringStripWS(String($oPlan.Item("attack_script")), $STR_STRIPALL)) <> "profile-current" Then
		$sError = "Clan request does not accept an attack script"
		Return SetError(5, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("army_source")), $STR_STRIPALL)) <> "recipe" Or _
			StringStripWS(String($oPlan.Item("army_recipe_name")), $STR_STRIPALL) <> "" Then
		$sError = "Clan request cannot select an army recipe"
		Return SetError(5, 1, False)
	EndIf
	If $oPlan.Item("army_manage_training") Or $oPlan.Item("army_wait_for_full") Or _
			$oPlan.Item("army_train_spells") Or $oPlan.Item("army_train_sieges") Then
		$sError = "Clan request requires all training and army inspection off"
		Return SetError(6, 0, False)
	EndIf
	Local $oLoadout = $oIntent.Item("loadout")
	If HeroLoadoutCount($oLoadout) > 0 Then
		$sError = "Clan request cannot deploy or inspect Heroes"
		Return SetError(7, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("donate_mode")), $STR_STRIPALL)) <> "off" Or _
			Not $oPlan.Item("donate_request_when_short") Or Not $oPlan.Item("donate_keep_army") Or _
			Int($oPlan.Item("donate_max_per_run")) <> 0 Then
		$sError = "Clan request requires donate.mode Off, Request when available on, army preservation on, and donation limit 0"
		Return SetError(8, 0, False)
	EndIf
	If $oPlan.Item("events_collect_resources") Or $oPlan.Item("events_collect_daily_reward") Or $oPlan.Item("events_collect_loot_cart") Or _
			$oPlan.Item("events_collect_treasury") Or $oPlan.Item("events_clan_games") Or _
			Int($oPlan.Item("events_clan_games_point_cap")) <> 0 Then
		$sError = "Clan request cannot collect resources, claim rewards, or enter Clan Games"
		Return SetError(9, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("events_laboratory")), $STR_STRIPALL)) <> "off" Or _
			StringLower(StringStripWS(String($oPlan.Item("upgrade_policy")), $STR_STRIPALL)) <> "disabled" Then
		$sError = "Clan request requires Laboratory and upgrades off"
		Return SetError(10, 0, False)
	EndIf
	If StringStripWS(String($oPlan.Item("account_queue_id")), $STR_STRIPALL) <> "" Then
		$sError = "Clan request cannot rotate accounts"
		Return SetError(11, 0, False)
	EndIf
	If Int($oPlan.Item("duration_minutes")) <> 0 Or Int($oPlan.Item("max_battles")) <> 0 Or _
			$oPlan.Item("stop_on_star_bonus") Or Int($oPlan.Item("max_failures")) <> 0 Then
		$sError = "Clan request is exactly one bounded pass; duration, battles, star bonus, and failures must be 0/off"
		Return SetError(12, 0, False)
	EndIf
	If Int($oPlan.Item("target_gold")) <> 0 Or Int($oPlan.Item("target_elixir")) <> 0 Or _
			Int($oPlan.Item("target_dark_elixir")) <> 0 Then
		$sError = "Clan request cannot use battle-loot targets"
		Return SetError(12, 1, False)
	EndIf
	If Int($oPlan.Item("search_min_gold")) <> 0 Or Int($oPlan.Item("search_min_elixir")) <> 0 Or _
			Int($oPlan.Item("search_min_dark")) <> 0 Or Int($oPlan.Item("search_max_seconds")) <> 0 Or _
			StringLower(StringStripWS(String($oPlan.Item("search_town_hall_filter")), $STR_STRIPALL)) <> "any" Then
		$sError = "Clan request cannot configure matchmaking search"
		Return SetError(12, 2, False)
	EndIf

	Local $oPacing = $oIntent.Item("pacing")
	If Int($oPacing.Item("retry_attempts")) <> 0 Or Int($oPacing.Item("break_every_minutes")) <> 0 Then
		$sError = "Clan request requires retries and scheduled breaks set to 0"
		Return SetError(13, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("notify_channel")), $STR_STRIPALL)) <> "log-only" Then
		$sError = "Only Bot log notifications are wired for Clan request"
		Return SetError(14, 0, False)
	EndIf

	Local $sEmulator = StringLower(StringStripWS(String($oPlan.Item("emulator")), $STR_STRIPALL))
	Local $sInstance = StringStripWS(String($oPlan.Item("emulator_instance")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sEmulator = "auto" Or $sInstance = "" Then
		$sError = "Choose the exact emulator and instance for Clan request"
		Return SetError(15, 0, False)
	EndIf
	If Not StringRegExp($sInstance, "^[A-Za-z0-9_. -]{1,64}$") Then
		$sError = "The emulator instance name contains unsupported characters"
		Return SetError(15, 1, False)
	EndIf
	Return True
EndFunc   ;==>ClanRequestRouteValidate

Func ClanRequestObservationCreate($sState, $iX = -1, $iY = -1)
	Local $oObservation = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oObservation) Then Return SetError(1, 0, 0)
	$oObservation.CompareMode = 1
	$oObservation.Add("state", StringLower(StringStripWS(String($sState), $STR_STRIPALL)))
	$oObservation.Add("x", Int($iX))
	$oObservation.Add("y", Int($iY))
	Return $oObservation
EndFunc   ;==>ClanRequestObservationCreate

Func ClanRequestObservationValid(ByRef $oObservation)
	If Not IsObj($oObservation) Or Not $oObservation.Exists("state") Or _
			Not $oObservation.Exists("x") Or Not $oObservation.Exists("y") Then Return False
	Switch StringLower(String($oObservation.Item("state")))
		Case $CLAN_REQUEST_STATE_AVAILABLE, $CLAN_REQUEST_STATE_ALREADY_MADE, _
				$CLAN_REQUEST_STATE_FULL_OR_UNAVAILABLE, $CLAN_REQUEST_STATE_SEND_READY
			Return True
	EndSwitch
	Return False
EndFunc   ;==>ClanRequestObservationValid

Func ClanRequestOutcomeCreate()
	Local $oOutcome = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oOutcome) Then Return SetError(1, 0, 0)
	$oOutcome.CompareMode = 1
	$oOutcome.Add("state", $CLAN_REQUEST_OUTCOME_UNCONFIRMED)
	$oOutcome.Add("detail", "not started")
	$oOutcome.Add("before_state", "")
	$oOutcome.Add("after_state", "")
	$oOutcome.Add("send_issued", False)
	$oOutcome.Add("send_attempts", 0)
	$oOutcome.Add("home_proven", False)
	Return $oOutcome
EndFunc   ;==>ClanRequestOutcomeCreate

Func _ClanRequestRouteFinish(ByRef $oOutcome, $sState, $sDetail, $sCloseAndProveHomeCallback)
	$oOutcome.Item("state") = $sState
	$oOutcome.Item("detail") = $sDetail
	Local $bHome = Call($sCloseAndProveHomeCallback)
	Local $iCallError = @error
	$oOutcome.Item("home_proven") = ($iCallError = 0 And $bHome)
	Return $oOutcome
EndFunc   ;==>_ClanRequestRouteFinish

; A Stop before Send authorizes no further emulator input. Do not invoke the close/Home callback:
; the dialog/screen is intentionally left where the operator stopped it, and BotStop owns shutdown.
Func _ClanRequestRouteCancel(ByRef $oOutcome, $sDetail)
	$oOutcome.Item("state") = $CLAN_REQUEST_OUTCOME_CANCELLED
	$oOutcome.Item("detail") = $sDetail
	Return $oOutcome
EndFunc   ;==>_ClanRequestRouteCancel

; Callback contract: open(), detect(phase)->observation, open_dialog(x,y)->send-ready observation,
; issue_send(x,y)->bool, stop_requested()->bool, close_and_prove_home()->bool.
; The Send latch is set before invoking issue_send, so no callback failure can permit a retry.
Func ClanRequestRouteRunAdapter($sOpenOverviewCallback, $sDetectStateCallback, $sOpenDialogCallback, _
		$sIssueSendCallback, $sStopRequestedCallback, $sCloseAndProveHomeCallback)
	Local $oOutcome = ClanRequestOutcomeCreate()
	If Not IsObj($oOutcome) Then Return SetError(1, 0, 0)

	If Call($sStopRequestedCallback) Then _
		Return _ClanRequestRouteCancel($oOutcome, "Stop requested before opening Army Overview")
	Local $bOpened = Call($sOpenOverviewCallback)
	Local $iOpenError = @error
	If $iOpenError Or Not $bOpened Then
		If Call($sStopRequestedCallback) Then _
			Return _ClanRequestRouteCancel($oOutcome, "Stop requested while opening Army Overview")
		Return _ClanRequestRouteFinish($oOutcome, $CLAN_REQUEST_OUTCOME_UNCONFIRMED, "Army Overview did not open", $sCloseAndProveHomeCallback)
	EndIf

	Local $oBefore = Call($sDetectStateCallback, "before")
	Local $iBeforeError = @error
	If $iBeforeError Or Not ClanRequestObservationValid($oBefore) Then
		If Call($sStopRequestedCallback) Then _
			Return _ClanRequestRouteCancel($oOutcome, "Stop requested while reading the request-button state")
		Return _ClanRequestRouteFinish($oOutcome, $CLAN_REQUEST_OUTCOME_UNCONFIRMED, "Fresh request-button state was not recognized", $sCloseAndProveHomeCallback)
	EndIf
	Local $sBefore = StringLower(String($oBefore.Item("state")))
	$oOutcome.Item("before_state") = $sBefore
	If Call($sStopRequestedCallback) Then _
		Return _ClanRequestRouteCancel($oOutcome, "Stop requested after reading the request-button state")
	If $sBefore = $CLAN_REQUEST_STATE_ALREADY_MADE Or $sBefore = $CLAN_REQUEST_STATE_FULL_OR_UNAVAILABLE Then _
		Return _ClanRequestRouteFinish($oOutcome, $CLAN_REQUEST_OUTCOME_UNAVAILABLE, "Request is not currently available: " & $sBefore, $sCloseAndProveHomeCallback)
	If $sBefore <> $CLAN_REQUEST_STATE_AVAILABLE Then _
		Return _ClanRequestRouteFinish($oOutcome, $CLAN_REQUEST_OUTCOME_UNCONFIRMED, "Expected Available before any request action", $sCloseAndProveHomeCallback)

	If Call($sStopRequestedCallback) Then _
		Return _ClanRequestRouteCancel($oOutcome, "Stop requested before opening the request dialog")
	Local $oSend = Call($sOpenDialogCallback, Int($oBefore.Item("x")), Int($oBefore.Item("y")))
	Local $iDialogError = @error
	If $iDialogError Or Not ClanRequestObservationValid($oSend) Then
		If Call($sStopRequestedCallback) Then _
			Return _ClanRequestRouteCancel($oOutcome, "Stop requested while opening the request dialog")
		Return _ClanRequestRouteFinish($oOutcome, $CLAN_REQUEST_OUTCOME_UNCONFIRMED, "Fresh Send button was not recognized", $sCloseAndProveHomeCallback)
	EndIf
	If StringLower(String($oSend.Item("state"))) <> $CLAN_REQUEST_STATE_SEND_READY Then _
		Return _ClanRequestRouteFinish($oOutcome, $CLAN_REQUEST_OUTCOME_UNCONFIRMED, "Fresh Send button was not recognized", $sCloseAndProveHomeCallback)

	; This is the final operation before the irreversible click. No capture, sleep, or other action may be inserted here.
	If Call($sStopRequestedCallback) Then _
		Return _ClanRequestRouteCancel($oOutcome, "Stop requested immediately before Send")
	; Latch the one permitted attempt before the callback so no failure can grant a retry. Record
	; delivery separately: send_issued becomes true only when the input adapter accepts the command.
	$oOutcome.Item("send_attempts") = 1
	Local $bIssued = Call($sIssueSendCallback, Int($oSend.Item("x")), Int($oSend.Item("y")))
	Local $iSendError = @error
	If $iSendError Or Not $bIssued Then
		If Call($sStopRequestedCallback) Then
			$oOutcome.Item("state") = $CLAN_REQUEST_OUTCOME_UNCONFIRMED
			$oOutcome.Item("detail") = "Stop requested during the Send attempt; no input-delivery receipt was returned"
			Return $oOutcome
		EndIf
		Return _ClanRequestRouteFinish($oOutcome, $CLAN_REQUEST_OUTCOME_UNCONFIRMED, "The one Send attempt was not accepted by the input adapter", $sCloseAndProveHomeCallback)
	EndIf
	$oOutcome.Item("send_issued") = True
	If Call($sStopRequestedCallback) Then
		; Send is already irreversible. Stop authorizes no post-Send capture or close click: record the
		; uncertainty with send_issued=true and leave the current screen untouched for BotStop/operator.
		$oOutcome.Item("state") = $CLAN_REQUEST_OUTCOME_UNCONFIRMED
		$oOutcome.Item("detail") = "Stop requested after Send; post-send state and Home return were not attempted"
		Return $oOutcome
	EndIf

	Local $oAfter = Call($sDetectStateCallback, "after")
	Local $iAfterError = @error
	If $iAfterError Or Not ClanRequestObservationValid($oAfter) Then
		If Call($sStopRequestedCallback) Then
			$oOutcome.Item("state") = $CLAN_REQUEST_OUTCOME_UNCONFIRMED
			$oOutcome.Item("detail") = "Stop requested while reading post-send state; Send remains unconfirmed"
			Return $oOutcome
		EndIf
		Return _ClanRequestRouteFinish($oOutcome, $CLAN_REQUEST_OUTCOME_UNCONFIRMED, "Send was issued but no fresh post-send state was recognized", $sCloseAndProveHomeCallback)
	EndIf
	$oOutcome.Item("after_state") = StringLower(String($oAfter.Item("state")))
	If Call($sStopRequestedCallback) Then
		$oOutcome.Item("state") = $CLAN_REQUEST_OUTCOME_UNCONFIRMED
		$oOutcome.Item("detail") = "Stop requested after post-send observation; no close/Home input was attempted"
		Return $oOutcome
	EndIf
	If $oOutcome.Item("after_state") <> $CLAN_REQUEST_STATE_ALREADY_MADE Then _
		Return _ClanRequestRouteFinish($oOutcome, $CLAN_REQUEST_OUTCOME_UNCONFIRMED, _
				"Send was issued but Available did not transition to AlreadyMade", $sCloseAndProveHomeCallback)
	Return _ClanRequestRouteFinish($oOutcome, $CLAN_REQUEST_OUTCOME_COMMITTED, _
			"Fresh Available transitioned to fresh AlreadyMade after one Send", $sCloseAndProveHomeCallback)
EndFunc   ;==>ClanRequestRouteRunAdapter
