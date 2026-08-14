; #FUNCTION# ====================================================================================================================
; Name ..........: Home maintenance route
; Description ...: Executes one explicit, diagnostic Home collection pass without entering matchmaking or other village work.
; Remarks .......: This adapter owns only the selected collector and startup Daily Reward tasks. Donations, training, upgrades,
;                  Laboratory, Clan Games, account rotation, Heroes, and battle search remain outside this route.
; ===============================================================================================================================
#include-once

Global Const $HOME_MAINTENANCE_COLLECTORS_STRATEGY = "home.collectors"

Func HomeMaintenanceRouteSelected(ByRef $oIntent)
	If Not IsObj($oIntent) Or Not $oIntent.Exists("plan") Then Return False
	Local $oPlan = $oIntent.Item("plan")
	If Not IsObj($oPlan) Or Not $oPlan.Exists("strategy") Then Return False
	Return StringLower(StringStripWS(String($oPlan.Item("strategy")), $STR_STRIPALL)) = $HOME_MAINTENANCE_COLLECTORS_STRATEGY
EndFunc   ;==>HomeMaintenanceRouteSelected

Func HomeMaintenanceRouteAccountMatches(ByRef $oIntent, $sCurrentProfile)
	If Not IsObj($oIntent) Or Not $oIntent.Exists("profile_id") Then Return False
	Local $sBound = StringStripWS(String($oIntent.Item("profile_id")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	Local $sCurrent = StringStripWS(String($sCurrentProfile), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	Return $sBound <> "" And $sCurrent <> "" And $sBound = $sCurrent
EndFunc   ;==>HomeMaintenanceRouteAccountMatches

; The home route uses the existing regular intent only as a session/account binding. It never consumes
; the route's battle quota and never calls PrepareSearch, VillageSearch, AttackMain, or ReturnHome.
Func HomeMaintenanceRouteValidate(ByRef $oIntent, ByRef $sError)
	$sError = ""
	If Not HomeMaintenanceRouteSelected($oIntent) Then
		$sError = "Home maintenance was not explicitly selected"
		Return SetError(1, 0, False)
	EndIf

	If StringLower(StringStripWS(String($oIntent.Item("surface_id")), $STR_STRIPALL)) <> "regular" Then
		$sError = "Home maintenance must remain bound to the current Home Village account"
		Return SetError(2, 0, False)
	EndIf

	Local $oRoute = $oIntent.Item("route")
	If Not $oRoute.Item("diagnostic_enabled") Then
		$sError = "Home maintenance requires Allow unverified and a supervised diagnostic acknowledgement"
		Return SetError(3, 0, False)
	EndIf
	Local $sProfile = StringStripWS(String($oIntent.Item("profile_id")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sProfile = "" Or StringLen($sProfile) > 64 Or Not StringRegExp($sProfile, "^[A-Za-z0-9_. -]+$") Then
		$sError = "Home maintenance requires the exact active profile/account binding"
		Return SetError(3, 1, False)
	EndIf

	Local $oPlan = $oIntent.Item("plan")
	If Not $oPlan.Item("events_collect_resources") And Not $oPlan.Item("events_collect_daily_reward") Then
		$sError = "Home maintenance requires at least one selected task: collectors or startup Daily Reward"
		Return SetError(4, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("attack_script")), $STR_STRIPALL)) <> "profile-current" Then
		$sError = "Home maintenance does not accept an attack script"
		Return SetError(4, 1, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("army_source")), $STR_STRIPALL)) <> "recipe" Or _
			StringStripWS(String($oPlan.Item("army_recipe_name")), $STR_STRIPALL) <> "" Then
		$sError = "Home maintenance cannot select an army recipe"
		Return SetError(4, 2, False)
	EndIf
	If $oPlan.Item("army_manage_training") Or $oPlan.Item("army_train_spells") Or $oPlan.Item("army_train_sieges") Then
		$sError = "Home maintenance cannot manage or train an army"
		Return SetError(5, 0, False)
	EndIf
	If $oPlan.Item("army_wait_for_full") Then
		$sError = "Home maintenance cannot wait for or inspect an army"
		Return SetError(5, 1, False)
	EndIf
	Local $oLoadout = $oIntent.Item("loadout")
	If HeroLoadoutCount($oLoadout) > 0 Then
		$sError = "Home maintenance cannot deploy or inspect Heroes"
		Return SetError(6, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("donate_mode")), $STR_STRIPALL)) <> "off" Or _
			$oPlan.Item("donate_request_when_short") Or Int($oPlan.Item("donate_max_per_run")) <> 0 Then
		$sError = "Home maintenance requires donations and requests off"
		Return SetError(7, 0, False)
	EndIf
	If $oPlan.Item("events_clan_games") Or Int($oPlan.Item("events_clan_games_point_cap")) <> 0 Then
		$sError = "Home maintenance cannot enter Clan Games"
		Return SetError(8, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("events_laboratory")), $STR_STRIPALL)) <> "off" Then
		$sError = "Home maintenance requires Laboratory off"
		Return SetError(9, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("upgrade_policy")), $STR_STRIPALL)) <> "disabled" Then
		$sError = "Home maintenance requires upgrades disabled"
		Return SetError(10, 0, False)
	EndIf
	If StringStripWS(String($oPlan.Item("account_queue_id")), $STR_STRIPALL) <> "" Then
		$sError = "Home maintenance cannot rotate accounts"
		Return SetError(11, 0, False)
	EndIf
	If Int($oPlan.Item("duration_minutes")) <> 0 Or Int($oPlan.Item("max_battles")) <> 0 Or _
			$oPlan.Item("stop_on_star_bonus") Or Int($oPlan.Item("max_failures")) <> 0 Then
		$sError = "Home maintenance is exactly one pass; duration, battles, star bonus, and failure limits must be 0/off"
		Return SetError(11, 1, False)
	EndIf
	If Int($oPlan.Item("target_gold")) <> 0 Or Int($oPlan.Item("target_elixir")) <> 0 Or Int($oPlan.Item("target_dark_elixir")) <> 0 Then
		$sError = "Home maintenance cannot use battle-loot targets"
		Return SetError(11, 2, False)
	EndIf
	If Int($oPlan.Item("search_min_gold")) <> 0 Or Int($oPlan.Item("search_min_elixir")) <> 0 Or _
			Int($oPlan.Item("search_min_dark")) <> 0 Or Int($oPlan.Item("search_max_seconds")) <> 0 Or _
			StringLower(StringStripWS(String($oPlan.Item("search_town_hall_filter")), $STR_STRIPALL)) <> "any" Then
		$sError = "Home maintenance cannot configure matchmaking search"
		Return SetError(11, 3, False)
	EndIf
	Local $oPacing = $oIntent.Item("pacing")
	If Int($oPacing.Item("retry_attempts")) <> 0 Then
		$sError = "Home maintenance requires retries set to 0"
		Return SetError(12, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("notify_channel")), $STR_STRIPALL)) <> "log-only" Then
		$sError = "Only Bot log notifications are wired for Home maintenance"
		Return SetError(13, 0, False)
	EndIf

	Local $sEmulator = StringLower(StringStripWS(String($oPlan.Item("emulator")), $STR_STRIPALL))
	Local $sInstance = StringStripWS(String($oPlan.Item("emulator_instance")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sEmulator = "" Or $sEmulator = "auto" Then
		$sError = "Choose the exact emulator for Home maintenance"
		Return SetError(14, 0, False)
	EndIf
	If $sInstance = "" Then
		$sError = "Choose the exact emulator instance for Home maintenance"
		Return SetError(14, 1, False)
	EndIf
	If Not StringRegExp($sInstance, "^[A-Za-z0-9_. -]{1,64}$") Then
		$sError = "The emulator instance name contains unsupported characters"
		Return SetError(14, 2, False)
	EndIf
	If StringRegExp($sEmulator, "^(memu|nox|ldplayer9|mumu)$") And Not $oRoute.Item("diagnostic_enabled") Then
		$sError = "This emulator adapter still requires a supervised diagnostic acknowledgement"
		Return SetError(14, 3, False)
	EndIf

	Return True
EndFunc   ;==>HomeMaintenanceRouteValidate
