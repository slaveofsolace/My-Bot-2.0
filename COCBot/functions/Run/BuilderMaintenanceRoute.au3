; #FUNCTION# ====================================================================================================================
; Name ..........: Builder maintenance route
; Description ...: Executes one explicit, diagnostic Builder Base collection pass without entering battle, upgrade, or legacy loops.
; Remarks .......: This route is limited to clean-room Builder Gold/Elixir bubble collection, a Home->Builder switch, and Home return.
;                  It never calls inherited image search, BuilderBase(), DoAttackBB(), upgrade, obstacle, training, donation, shop,
;                  account switching, or any premium-currency path.
; ===============================================================================================================================
#include-once

Global Const $BUILDER_MAINTENANCE_COLLECTORS_STRATEGY = "builder.collectors"

Func BuilderMaintenanceRouteSelected(ByRef $oIntent)
	If Not IsObj($oIntent) Or Not $oIntent.Exists("plan") Then Return False
	Local $oPlan = $oIntent.Item("plan")
	If Not IsObj($oPlan) Or Not $oPlan.Exists("strategy") Then Return False
	Return StringLower(StringStripWS(String($oPlan.Item("strategy")), $STR_STRIPALL)) = $BUILDER_MAINTENANCE_COLLECTORS_STRATEGY
EndFunc   ;==>BuilderMaintenanceRouteSelected

Func BuilderMaintenanceRouteAccountMatches(ByRef $oIntent, $sCurrentProfile)
	If Not IsObj($oIntent) Or Not $oIntent.Exists("profile_id") Then Return False
	Local $sBound = StringStripWS(String($oIntent.Item("profile_id")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	Local $sCurrent = StringStripWS(String($sCurrentProfile), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	Return $sBound <> "" And $sCurrent <> "" And $sBound = $sCurrent
EndFunc   ;==>BuilderMaintenanceRouteAccountMatches

Func BuilderMaintenanceRouteValidate(ByRef $oIntent, ByRef $sError)
	$sError = ""
	If Not BuilderMaintenanceRouteSelected($oIntent) Then
		$sError = "Builder Base maintenance was not explicitly selected"
		Return SetError(1, 0, False)
	EndIf

	If StringLower(StringStripWS(String($oIntent.Item("surface_id")), $STR_STRIPALL)) <> "builder" Then
		$sError = "Builder Base maintenance must remain bound to the Builder Base surface"
		Return SetError(2, 0, False)
	EndIf

	Local $oRoute = $oIntent.Item("route")
	If Not $oRoute.Item("diagnostic_enabled") Then
		$sError = "Builder Base maintenance requires Allow unverified and a supervised diagnostic acknowledgement"
		Return SetError(3, 0, False)
	EndIf
	Local $sProfile = StringStripWS(String($oIntent.Item("profile_id")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sProfile = "" Or StringLen($sProfile) > 64 Or Not StringRegExp($sProfile, "^[A-Za-z0-9_. -]+$") Then
		$sError = "Builder Base maintenance requires the exact active profile/account binding"
		Return SetError(3, 1, False)
	EndIf

	Local $oPlan = $oIntent.Item("plan")
	If Not $oPlan.Item("events_collect_resources") Then
		$sError = "Builder Base maintenance requires Builder resource collection enabled"
		Return SetError(4, 0, False)
	EndIf
	If $oPlan.Item("events_collect_daily_reward") Or $oPlan.Item("events_collect_loot_cart") Or _
			$oPlan.Item("events_collect_treasury") Then
		$sError = "Builder Base maintenance cannot run Home Daily Reward, Loot Cart, or Treasury tasks"
		Return SetError(4, 1, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("attack_script")), $STR_STRIPALL)) <> "profile-current" Then
		$sError = "Builder Base maintenance does not accept an attack script"
		Return SetError(4, 2, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("army_source")), $STR_STRIPALL)) <> "recipe" Or _
			StringStripWS(String($oPlan.Item("army_recipe_name")), $STR_STRIPALL) <> "" Or _
			StringStripWS(String($oPlan.Item("army_recipe_digest")), $STR_STRIPALL) <> "" Or _
			Int($oPlan.Item("army_max_queue_units")) <> 0 Then
		$sError = "Builder Base maintenance cannot select or queue an army recipe"
		Return SetError(4, 3, False)
	EndIf
	If $oPlan.Item("army_manage_training") Or $oPlan.Item("army_wait_for_full") Or _
			$oPlan.Item("army_train_spells") Or $oPlan.Item("army_train_sieges") Then
		$sError = "Builder Base maintenance cannot train or inspect an army"
		Return SetError(5, 0, False)
	EndIf
	Local $oLoadout = $oIntent.Item("loadout")
	If HeroLoadoutCount($oLoadout) > 0 Then
		$sError = "Builder Base maintenance cannot deploy or inspect Heroes"
		Return SetError(6, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("donate_mode")), $STR_STRIPALL)) <> "off" Or _
			$oPlan.Item("donate_request_when_short") Or Int($oPlan.Item("donate_max_per_run")) <> 0 Then
		$sError = "Builder Base maintenance requires donations and requests off"
		Return SetError(7, 0, False)
	EndIf
	If $oPlan.Item("events_clan_games") Or Int($oPlan.Item("events_clan_games_point_cap")) <> 0 Then
		$sError = "Builder Base maintenance cannot enter Clan Games"
		Return SetError(8, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("events_laboratory")), $STR_STRIPALL)) <> "off" Then
		$sError = "Builder Base maintenance requires Laboratory off"
		Return SetError(9, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("upgrade_policy")), $STR_STRIPALL)) <> "disabled" Then
		$sError = "Builder Base maintenance requires upgrades disabled"
		Return SetError(10, 0, False)
	EndIf
	If StringStripWS(String($oPlan.Item("account_queue_id")), $STR_STRIPALL) <> "" Then
		$sError = "Builder Base maintenance cannot rotate accounts"
		Return SetError(11, 0, False)
	EndIf
	If Int($oPlan.Item("duration_minutes")) <> 0 Or Int($oPlan.Item("max_battles")) <> 0 Or _
			$oPlan.Item("stop_on_star_bonus") Or Int($oPlan.Item("max_failures")) <> 0 Then
		$sError = "Builder Base maintenance is exactly one pass; duration, battles, star bonus, and failure limits must be 0/off"
		Return SetError(11, 1, False)
	EndIf
	If Int($oPlan.Item("target_gold")) <> 0 Or Int($oPlan.Item("target_elixir")) <> 0 Or Int($oPlan.Item("target_dark_elixir")) <> 0 Then
		$sError = "Builder Base maintenance cannot use battle-loot targets"
		Return SetError(11, 2, False)
	EndIf
	If Int($oPlan.Item("search_min_gold")) <> 0 Or Int($oPlan.Item("search_min_elixir")) <> 0 Or _
			Int($oPlan.Item("search_min_dark")) <> 0 Or Int($oPlan.Item("search_max_seconds")) <> 0 Or _
			StringLower(StringStripWS(String($oPlan.Item("search_town_hall_filter")), $STR_STRIPALL)) <> "any" Then
		$sError = "Builder Base maintenance cannot configure matchmaking search"
		Return SetError(11, 3, False)
	EndIf
	Local $oPacing = $oIntent.Item("pacing")
	If Int($oPacing.Item("retry_attempts")) <> 0 Then
		$sError = "Builder Base maintenance requires retries set to 0"
		Return SetError(12, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("notify_channel")), $STR_STRIPALL)) <> "log-only" Then
		$sError = "Only Bot log notifications are wired for Builder Base maintenance"
		Return SetError(13, 0, False)
	EndIf

	Local $sEmulator = StringLower(StringStripWS(String($oPlan.Item("emulator")), $STR_STRIPALL))
	Local $sInstance = StringStripWS(String($oPlan.Item("emulator_instance")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sEmulator <> "bluestacks5" Then
		$sError = "Template-free Builder Base maintenance currently requires the exact BlueStacks 5 adapter"
		Return SetError(14, 0, False)
	EndIf
	If $sInstance = "" Then
		$sError = "Choose the exact emulator instance for Builder Base maintenance"
		Return SetError(14, 1, False)
	EndIf
	If Not StringRegExp($sInstance, "^[A-Za-z0-9_. -]{1,64}$") Then
		$sError = "The emulator instance name contains unsupported characters"
		Return SetError(14, 2, False)
	EndIf

	Return True
EndFunc   ;==>BuilderMaintenanceRouteValidate
