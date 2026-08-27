; #FUNCTION# ====================================================================================================================
; Name ..........: Regular battle entry proof route
; Description ...: Opens the current-client Regular Battle entry surface and stops before matchmaking.
; Remarks .......: This route proves the installed product can navigate from Home to the Multiplayer "Find a Match" surface through
;                  product-owned Start without searching, deploying, upgrading, collecting, donating, training, or spending.
; ===============================================================================================================================
#include-once

Global Const $REGULAR_BATTLE_ENTRY_ROUTE_STRATEGY = "regular.battle-entry"
Global Const $REGULAR_BATTLE_SCOUT_ROUTE_STRATEGY = "regular.battle-scout"

Func RegularBattleEntryRouteSelected(ByRef $oIntent)
	If Not IsObj($oIntent) Or Not $oIntent.Exists("plan") Then Return False
	Local $oPlan = $oIntent.Item("plan")
	If Not IsObj($oPlan) Or Not $oPlan.Exists("strategy") Then Return False
	Return StringLower(StringStripWS(String($oPlan.Item("strategy")), $STR_STRIPALL)) = $REGULAR_BATTLE_ENTRY_ROUTE_STRATEGY
EndFunc   ;==>RegularBattleEntryRouteSelected

Func RegularBattleScoutRouteSelected(ByRef $oIntent)
	If Not IsObj($oIntent) Or Not $oIntent.Exists("plan") Then Return False
	Local $oPlan = $oIntent.Item("plan")
	If Not IsObj($oPlan) Or Not $oPlan.Exists("strategy") Then Return False
	Return StringLower(StringStripWS(String($oPlan.Item("strategy")), $STR_STRIPALL)) = $REGULAR_BATTLE_SCOUT_ROUTE_STRATEGY
EndFunc   ;==>RegularBattleScoutRouteSelected

Func RegularBattleEntryRouteAccountMatches(ByRef $oIntent, $sCurrentProfile)
	If Not IsObj($oIntent) Or Not $oIntent.Exists("profile_id") Then Return False
	Local $sBound = StringStripWS(String($oIntent.Item("profile_id")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	Local $sCurrent = StringStripWS(String($sCurrentProfile), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	Return $sBound <> "" And $sCurrent <> "" And $sBound = $sCurrent
EndFunc   ;==>RegularBattleEntryRouteAccountMatches

; Terminal proof route only: open Multiplayer, prove the reviewed Find a Match region, close it, and stop.
; It deliberately rejects actual battles, search filters, collectors, rewards, upgrades, training, donations,
; Clan Games, and account rotation.
Func RegularBattleEntryRouteValidate(ByRef $oIntent, ByRef $sError)
	$sError = ""
	If Not RegularBattleEntryRouteSelected($oIntent) Then
		$sError = "Regular battle entry proof was not explicitly selected"
		Return SetError(1, 0, False)
	EndIf

	If StringLower(StringStripWS(String($oIntent.Item("surface_id")), $STR_STRIPALL)) <> "regular" Then
		$sError = "Regular battle entry proof must remain bound to the Regular/Home surface"
		Return SetError(2, 0, False)
	EndIf

	Local $oRoute = $oIntent.Item("route")
	If Not $oRoute.Item("diagnostic_enabled") Then
		$sError = "Regular battle entry proof requires Allow unverified and a supervised diagnostic acknowledgement"
		Return SetError(3, 0, False)
	EndIf
	Local $sProfile = StringStripWS(String($oIntent.Item("profile_id")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sProfile = "" Or StringLen($sProfile) > 64 Or Not StringRegExp($sProfile, "^[A-Za-z0-9_. -]+$") Then
		$sError = "Regular battle entry proof requires the exact active profile/account binding"
		Return SetError(3, 1, False)
	EndIf

	Local $oPlan = $oIntent.Item("plan")
	If $oPlan.Item("events_collect_resources") Or $oPlan.Item("events_collect_daily_reward") Or _
			$oPlan.Item("events_collect_loot_cart") Or $oPlan.Item("events_collect_treasury") Then
		$sError = "Regular battle entry proof cannot collect resources, rewards, Loot Cart, or Treasury"
		Return SetError(4, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("attack_script")), $STR_STRIPALL)) <> "profile-current" Then
		$sError = "Regular battle entry proof does not accept an attack script"
		Return SetError(4, 1, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("army_source")), $STR_STRIPALL)) <> "recipe" Or _
			StringStripWS(String($oPlan.Item("army_recipe_name")), $STR_STRIPALL) <> "" Or _
			StringStripWS(String($oPlan.Item("army_recipe_digest")), $STR_STRIPALL) <> "" Or _
			Int($oPlan.Item("army_max_queue_units")) <> 0 Then
		$sError = "Regular battle entry proof cannot select or queue an army recipe"
		Return SetError(4, 2, False)
	EndIf
	If $oPlan.Item("army_manage_training") Or $oPlan.Item("army_train_spells") Or $oPlan.Item("army_train_sieges") Or _
			$oPlan.Item("army_wait_for_full") Then
		$sError = "Regular battle entry proof cannot manage, train, or inspect an army"
		Return SetError(5, 0, False)
	EndIf
	Local $oLoadout = $oIntent.Item("loadout")
	If HeroLoadoutCount($oLoadout) > 0 Then
		$sError = "Regular battle entry proof cannot deploy or inspect Heroes"
		Return SetError(6, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("donate_mode")), $STR_STRIPALL)) <> "off" Or _
			$oPlan.Item("donate_request_when_short") Or Int($oPlan.Item("donate_max_per_run")) <> 0 Then
		$sError = "Regular battle entry proof requires donations and requests off"
		Return SetError(7, 0, False)
	EndIf
	If $oPlan.Item("events_clan_games") Or Int($oPlan.Item("events_clan_games_point_cap")) <> 0 Then
		$sError = "Regular battle entry proof cannot enter Clan Games"
		Return SetError(8, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("events_laboratory")), $STR_STRIPALL)) <> "off" Then
		$sError = "Regular battle entry proof requires Laboratory off"
		Return SetError(9, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("upgrade_policy")), $STR_STRIPALL)) <> "disabled" Then
		$sError = "Regular battle entry proof requires upgrades disabled"
		Return SetError(10, 0, False)
	EndIf
	If StringStripWS(String($oPlan.Item("account_queue_id")), $STR_STRIPALL) <> "" Then
		$sError = "Regular battle entry proof cannot rotate accounts"
		Return SetError(11, 0, False)
	EndIf
	If Int($oPlan.Item("duration_minutes")) <> 0 Or Int($oPlan.Item("max_battles")) <> 0 Or _
			$oPlan.Item("stop_on_star_bonus") Or Int($oPlan.Item("max_failures")) <> 0 Then
		$sError = "Regular battle entry proof is exactly one pre-search pass; duration, battles, star bonus, and failure limits must be 0/off"
		Return SetError(11, 1, False)
	EndIf
	If Int($oPlan.Item("target_gold")) <> 0 Or Int($oPlan.Item("target_elixir")) <> 0 Or Int($oPlan.Item("target_dark_elixir")) <> 0 Then
		$sError = "Regular battle entry proof cannot use battle-loot targets"
		Return SetError(11, 2, False)
	EndIf
	If Int($oPlan.Item("search_min_gold")) <> 0 Or Int($oPlan.Item("search_min_elixir")) <> 0 Or _
			Int($oPlan.Item("search_min_dark")) <> 0 Or Int($oPlan.Item("search_max_seconds")) <> 0 Or _
			StringLower(StringStripWS(String($oPlan.Item("search_town_hall_filter")), $STR_STRIPALL)) <> "any" Then
		$sError = "Regular battle entry proof cannot configure matchmaking search"
		Return SetError(11, 3, False)
	EndIf
	Local $oPacing = $oIntent.Item("pacing")
	If Int($oPacing.Item("retry_attempts")) <> 0 Then
		$sError = "Regular battle entry proof requires retries set to 0"
		Return SetError(12, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("notify_channel")), $STR_STRIPALL)) <> "log-only" Then
		$sError = "Only Bot log notifications are wired for Regular battle entry proof"
		Return SetError(13, 0, False)
	EndIf

	Local $sEmulator = StringLower(StringStripWS(String($oPlan.Item("emulator")), $STR_STRIPALL))
	Local $sInstance = StringStripWS(String($oPlan.Item("emulator_instance")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sEmulator <> "bluestacks5" Then
		$sError = "Regular battle entry proof currently requires the exact BlueStacks 5 adapter"
		Return SetError(14, 0, False)
	EndIf
	If $sInstance = "" Then
		$sError = "Choose the exact emulator instance for Regular battle entry proof"
		Return SetError(14, 1, False)
	EndIf
	If Not StringRegExp($sInstance, "^[A-Za-z0-9_. -]{1,64}$") Then
		$sError = "The emulator instance name contains unsupported characters"
		Return SetError(14, 2, False)
	EndIf

	Return True
EndFunc   ;==>RegularBattleEntryRouteValidate

; Terminal scout route only: open Multiplayer, issue one reviewed Find a Match tap, prove the
; attack screen, capture evidence for clean-room recognition, surrender/return Home through reviewed
; battle-exit permits, and stop. It never deploys troops, searches additional bases, upgrades, collects,
; donates, trains, opens social flows, or rotates accounts.
Func RegularBattleScoutRouteValidate(ByRef $oIntent, ByRef $sError)
	$sError = ""
	If Not RegularBattleScoutRouteSelected($oIntent) Then
		$sError = "Regular battle scout was not explicitly selected"
		Return SetError(1, 0, False)
	EndIf

	If StringLower(StringStripWS(String($oIntent.Item("surface_id")), $STR_STRIPALL)) <> "regular" Then
		$sError = "Regular battle scout must remain bound to the Regular/Home surface"
		Return SetError(2, 0, False)
	EndIf

	Local $oRoute = $oIntent.Item("route")
	If Not $oRoute.Item("diagnostic_enabled") Then
		$sError = "Regular battle scout requires Allow unverified and a supervised diagnostic acknowledgement"
		Return SetError(3, 0, False)
	EndIf
	Local $sProfile = StringStripWS(String($oIntent.Item("profile_id")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sProfile = "" Or StringLen($sProfile) > 64 Or Not StringRegExp($sProfile, "^[A-Za-z0-9_. -]+$") Then
		$sError = "Regular battle scout requires the exact active profile/account binding"
		Return SetError(3, 1, False)
	EndIf

	Local $oPlan = $oIntent.Item("plan")
	If $oPlan.Item("events_collect_resources") Or $oPlan.Item("events_collect_daily_reward") Or _
			$oPlan.Item("events_collect_loot_cart") Or $oPlan.Item("events_collect_treasury") Then
		$sError = "Regular battle scout cannot collect resources, rewards, Loot Cart, or Treasury"
		Return SetError(4, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("attack_script")), $STR_STRIPALL)) <> "profile-current" Then
		$sError = "Regular battle scout cannot select a deployment script"
		Return SetError(4, 1, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("army_source")), $STR_STRIPALL)) <> "recipe" Or _
			StringStripWS(String($oPlan.Item("army_recipe_name")), $STR_STRIPALL) <> "" Or _
			StringStripWS(String($oPlan.Item("army_recipe_digest")), $STR_STRIPALL) <> "" Or _
			Int($oPlan.Item("army_max_queue_units")) <> 0 Then
		$sError = "Regular battle scout cannot select or queue an army recipe"
		Return SetError(4, 2, False)
	EndIf
	If $oPlan.Item("army_manage_training") Or $oPlan.Item("army_train_spells") Or $oPlan.Item("army_train_sieges") Or _
			$oPlan.Item("army_wait_for_full") Then
		$sError = "Regular battle scout cannot manage, train, or wait for an army"
		Return SetError(5, 0, False)
	EndIf
	Local $oLoadout = $oIntent.Item("loadout")
	If HeroLoadoutCount($oLoadout) > 0 Then
		$sError = "Regular battle scout cannot deploy or inspect Heroes"
		Return SetError(6, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("donate_mode")), $STR_STRIPALL)) <> "off" Or _
			$oPlan.Item("donate_request_when_short") Or Int($oPlan.Item("donate_max_per_run")) <> 0 Then
		$sError = "Regular battle scout requires donations and requests off"
		Return SetError(7, 0, False)
	EndIf
	If $oPlan.Item("events_clan_games") Or Int($oPlan.Item("events_clan_games_point_cap")) <> 0 Then
		$sError = "Regular battle scout cannot enter Clan Games"
		Return SetError(8, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("events_laboratory")), $STR_STRIPALL)) <> "off" Then
		$sError = "Regular battle scout requires Laboratory off"
		Return SetError(9, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("upgrade_policy")), $STR_STRIPALL)) <> "disabled" Then
		$sError = "Regular battle scout requires upgrades disabled"
		Return SetError(10, 0, False)
	EndIf
	If StringStripWS(String($oPlan.Item("account_queue_id")), $STR_STRIPALL) <> "" Then
		$sError = "Regular battle scout cannot rotate accounts"
		Return SetError(11, 0, False)
	EndIf
	If Int($oPlan.Item("duration_minutes")) <> 0 Or Int($oPlan.Item("max_battles")) <> 1 Or _
			$oPlan.Item("stop_on_star_bonus") Or Int($oPlan.Item("max_failures")) <> 0 Then
		$sError = "Regular battle scout enters exactly one match; duration must be 0, Max battles 1, star bonus off, failures 0"
		Return SetError(11, 1, False)
	EndIf
	If Int($oPlan.Item("target_gold")) <> 0 Or Int($oPlan.Item("target_elixir")) <> 0 Or Int($oPlan.Item("target_dark_elixir")) <> 0 Then
		$sError = "Regular battle scout cannot use battle-loot targets"
		Return SetError(11, 2, False)
	EndIf
	If Int($oPlan.Item("search_min_gold")) <> 0 Or Int($oPlan.Item("search_min_elixir")) <> 0 Or _
			Int($oPlan.Item("search_min_dark")) <> 0 Or Int($oPlan.Item("search_max_seconds")) <> 0 Or _
			StringLower(StringStripWS(String($oPlan.Item("search_town_hall_filter")), $STR_STRIPALL)) <> "any" Then
		$sError = "Regular battle scout cannot configure matchmaking search"
		Return SetError(11, 3, False)
	EndIf
	Local $oPacing = $oIntent.Item("pacing")
	If Int($oPacing.Item("retry_attempts")) <> 0 Then
		$sError = "Regular battle scout requires retries set to 0"
		Return SetError(12, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("notify_channel")), $STR_STRIPALL)) <> "log-only" Then
		$sError = "Only Bot log notifications are wired for Regular battle scout"
		Return SetError(13, 0, False)
	EndIf

	Local $sEmulator = StringLower(StringStripWS(String($oPlan.Item("emulator")), $STR_STRIPALL))
	Local $sInstance = StringStripWS(String($oPlan.Item("emulator_instance")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sEmulator <> "bluestacks5" Then
		$sError = "Regular battle scout currently requires the exact BlueStacks 5 adapter"
		Return SetError(14, 0, False)
	EndIf
	If $sInstance = "" Then
		$sError = "Choose the exact emulator instance for Regular battle scout"
		Return SetError(14, 1, False)
	EndIf
	If Not StringRegExp($sInstance, "^[A-Za-z0-9_. -]{1,64}$") Then
		$sError = "The emulator instance name contains unsupported characters"
		Return SetError(14, 2, False)
	EndIf

	Return True
EndFunc   ;==>RegularBattleScoutRouteValidate

Func RegularBattleScoutEndBattlePointReady($iX, $iY)
	If Not NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_END_BATTLE, $iX, $iY) Then Return False
	Return IsAttackPage(True)
EndFunc   ;==>RegularBattleScoutEndBattlePointReady

Func RegularBattleScoutConfirmSurrenderPointReady($iX, $iY)
	If Not NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_CONFIRM_SURRENDER, $iX, $iY) Then Return False
	Return IsEndBattlePage(False)
EndFunc   ;==>RegularBattleScoutConfirmSurrenderPointReady

Func RegularBattleScoutReturnHomePointReady($iX, $iY)
	If Not NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_REGULAR_BATTLE_SCOUT_RETURN_HOME, $iX, $iY) Then Return False
	Return IsReturnHomeBattlePage(True, False)
EndFunc   ;==>RegularBattleScoutReturnHomePointReady
