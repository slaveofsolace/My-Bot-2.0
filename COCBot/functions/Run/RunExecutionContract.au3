; #FUNCTION# ====================================================================================================================
; Name ..........: Run execution contract
; Description ...: Declares which prepared planner values the inherited engine can execute exactly.
; Remarks .......: Values without a faithful adapter are rejected at Start. Silently ignoring them would make the planner lie.
; ===============================================================================================================================
#include-once
#include <StringConstants.au3>
#include "RunIntent.au3"
#include "HomeMaintenanceRoute.au3"
#include "ClanRequestRoute.au3"
#include "LootCartRoute.au3"
#include "TreasuryRoute.au3"

; Smart uses one concentrated deployment side. The actual BR/BL/TR/TL side is chosen after current-frame
; red-line extraction by SmartAttackPolicy; the legacy selector-5 DLL branch is not current-client proven.
; The Boolean remains in the signature for backward-compatible tests/callers.
Func RunExecutionSmartDropSides($iTownHall, $bActiveBase)
	Local $iTH = Int($iTownHall)
	If $iTH >= 2 Then Return 0
	Return 0
EndFunc   ;==>RunExecutionSmartDropSides

; A selected Hero has two separate meanings: deploy it when its attack-bar slot is present, and wait
; for it to become available before searching. Current-trained-army mode can safely do the first but
; deliberately does not open Hero Hall or mutate training to prove the second. Keep its readiness
; mask empty so selecting Heroes does not make the one-shot path reject itself before matchmaking.
Func RunExecutionHeroWaitMask($iSelectedHeroMask, $bWaitForFullArmy, $bManageTraining)
	If Not $bWaitForFullArmy Or Not $bManageTraining Then Return 0
	Return Int($iSelectedHeroMask)
EndFunc   ;==>RunExecutionHeroWaitMask

Func RunExecutionContractValidate(ByRef $oIntent, ByRef $sError)
	$sError = ""
	If Not RunIntentValidate($oIntent, $sError) Then Return SetError(1, 0, False)
	If HomeMaintenanceRouteSelected($oIntent) Then Return HomeMaintenanceRouteValidate($oIntent, $sError)
	If ClanRequestRouteSelected($oIntent) Then Return ClanRequestRouteValidate($oIntent, $sError)

	Local $sSurface = StringLower(StringStripWS(String($oIntent.Item("surface_id")), $STR_STRIPALL))
	If $sSurface <> "regular" Then
		$sError = "The inherited attack engine is only wired to Regular Battles. " & $sSurface & " remains evidence-only."
		Return SetError(2, 0, False)
	EndIf

	Local $oPlan = $oIntent.Item("plan")
	Local $oPacing = $oIntent.Item("pacing")
	Local $oRoute = $oIntent.Item("route")
	Local $bDiagnostic = $oRoute.Item("diagnostic_enabled")
	If Int($oPacing.Item("retry_attempts")) > 0 Then
		$sError = "Generic action retries need a visual-change observer and are not wired yet; use 0"
		Return SetError(3, 0, False)
	EndIf
	Local $sStrategy = StringLower(StringStripWS(String($oPlan.Item("strategy")), $STR_STRIPALL))
	If $sStrategy <> "legacy.csv" And $sStrategy <> "legacy.standard" And $sStrategy <> "smart.local" Then
		$sError = "Attack strategy " & $sStrategy & " has no exact legacy-engine adapter"
		Return SetError(4, 0, False)
	EndIf
	If $sStrategy = "legacy.csv" And Not $bDiagnostic Then
		$sError = "Scripted CSV deployment still requires Allow unverified and a supervised diagnostic acknowledgement"
		Return SetError(4, 2, False)
	EndIf
	Local $sAttackScript = StringStripWS(String($oPlan.Item("attack_script")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sStrategy <> "legacy.csv" And StringLower($sAttackScript) <> "profile-current" Then
		$sError = "A named CSV attack script requires the Scripted strategy"
		Return SetError(4, 1, False)
	EndIf

	If StringLower(StringStripWS(String($oPlan.Item("army_source")), $STR_STRIPALL)) <> "recipe" Or _
			StringStripWS(String($oPlan.Item("army_recipe_name")), $STR_STRIPALL) <> "" Then
		$sError = "Named army recipes are not wired yet; leave the recipe name empty to use the active profile army"
		Return SetError(5, 0, False)
	EndIf
	; The inherited training entry point is profile-owned rather than plan-owned: it may boost a Super
	; Troop, choose Quick Train or the custom profile army, delete mismatches, and queue troops, spells,
	; or sieges. Diagnostic acknowledgement cannot turn that hidden actuator set into an exact route.
	; Keep planned combat on the separately bounded current-army observer and terminal one-battle path.
	If RunIntentManagesTraining($oIntent) Then
		$sError = "Managed training is disabled because the inherited profile training path is not closed-world; turn Manage training off and use the current trained army for one battle"
		Return SetError(5, 9, False)
	EndIf
	If Int($oPlan.Item("max_battles")) <> 1 Then
		$sError = "Using the trained army without managing training is limited to exactly one battle; set Max battles to 1"
		Return SetError(5, 1, False)
	EndIf
	If Not $oPlan.Item("army_wait_for_full") Then
		$sError = "Current-army mode requires Wait for full army so a fresh passive readiness check can fail closed"
		Return SetError(5, 2, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("donate_mode")), $STR_STRIPALL)) <> "off" Then
		$sError = "Turn donations off when using the current trained army so the one-shot army cannot be consumed"
		Return SetError(5, 3, False)
	EndIf
	If $oPlan.Item("donate_request_when_short") Then
		$sError = "Current-army mode cannot request troops before its terminal one-battle attempt"
		Return SetError(5, 4, False)
	EndIf
	If $oPlan.Item("events_collect_resources") Or $oPlan.Item("events_collect_daily_reward") Or $oPlan.Item("events_collect_loot_cart") Or _
			$oPlan.Item("events_collect_treasury") Then
		$sError = "Home collection work requires the explicit Home maintenance strategy"
		Return SetError(5, 5, False)
	EndIf
	If $oPlan.Item("events_clan_games") Then
		$sError = "Current-army mode cannot run Clan Games before its terminal battle"
		Return SetError(5, 6, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("events_laboratory")), $STR_STRIPALL)) <> "off" Then
		$sError = "Current-army mode cannot enter the Laboratory before its terminal battle"
		Return SetError(5, 7, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("upgrade_policy")), $STR_STRIPALL)) <> "disabled" Then
		$sError = "Current-army mode requires upgrades disabled before its terminal battle"
		Return SetError(5, 8, False)
	EndIf
	If Int($oPlan.Item("search_max_seconds")) > 0 Then
		$sError = "Search time limits are not wired to a safe search-loop exit yet; use 0"
		Return SetError(6, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("search_town_hall_filter")), $STR_STRIPALL)) <> "any" Then
		$sError = "Town Hall search filters are not current-client verified; use Any"
		Return SetError(7, 0, False)
	EndIf

	Local $oLoadout = $oIntent.Item("loadout")
	If HeroLoadoutContains($oLoadout, "dragon-duke") Then
		$sError = "Dragon Duke is not present in the inherited five-Hero deployment engine"
		Return SetError(8, 0, False)
	EndIf
	If HeroLoadoutCount($oLoadout) > 0 And Not $bDiagnostic Then
		$sError = "Selected Hero deployment and ability use require Allow unverified and a supervised diagnostic acknowledgement"
		Return SetError(8, 1, False)
	EndIf

	Local $sEmulator = StringLower(StringStripWS(String($oPlan.Item("emulator")), $STR_STRIPALL))
	Local $sEmulatorInstance = StringStripWS(String($oPlan.Item("emulator_instance")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sEmulator = "auto" And $sEmulatorInstance <> "" Then
		$sError = "Choose a specific emulator before selecting an instance"
		Return SetError(9, 0, False)
	EndIf
	If $sEmulatorInstance <> "" And Not StringRegExp($sEmulatorInstance, "^[A-Za-z0-9_. -]{1,64}$") Then
		$sError = "The emulator instance name contains unsupported characters"
		Return SetError(9, 1, False)
	EndIf
	If $sEmulator <> "auto" And $sEmulatorInstance = "" Then
		$sError = "Choose the exact emulator instance so capture, input, and docking target the same account"
		Return SetError(9, 2, False)
	EndIf
	If StringRegExp($sEmulator, "^(memu|nox|ldplayer9|mumu)$") And Not $bDiagnostic Then
		$sError = "This emulator adapter still requires Allow unverified and a supervised diagnostic acknowledgement"
		Return SetError(9, 3, False)
	EndIf
	If Not $oPlan.Item("donate_keep_army") Then
		$sError = "Allowing donations to consume the attack army has no bounded legacy adapter"
		Return SetError(10, 0, False)
	EndIf
	If Int($oPlan.Item("donate_max_per_run")) > 0 Then
		$sError = "Per-run donation limits are not wired yet; use 0"
		Return SetError(11, 0, False)
	EndIf
	If (StringLower(StringStripWS(String($oPlan.Item("donate_mode")), $STR_STRIPALL)) <> "off" Or _
			$oPlan.Item("donate_request_when_short")) And Not $bDiagnostic Then
		$sError = "Donation and request actions require Allow unverified and a supervised diagnostic acknowledgement"
		Return SetError(11, 1, False)
	EndIf
	If Int($oPlan.Item("events_clan_games_point_cap")) > 0 Then
		$sError = "The Clan Games point cap is not wired yet; use 0"
		Return SetError(12, 0, False)
	EndIf
	If $oPlan.Item("events_collect_resources") Or $oPlan.Item("events_collect_daily_reward") Or $oPlan.Item("events_collect_loot_cart") Or _
			$oPlan.Item("events_collect_treasury") Then
		$sError = "Home collection work requires the explicit Home maintenance strategy"
		Return SetError(12, 1, False)
	EndIf
	If $oPlan.Item("events_clan_games") And Not $bDiagnostic Then
		$sError = "Clan Games requires Allow unverified and a supervised diagnostic acknowledgement"
		Return SetError(12, 1, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("events_laboratory")), $STR_STRIPALL)) <> "off" Then
		$sError = "Planner-driven laboratory selection is not wired yet; leave Laboratory off"
		Return SetError(13, 0, False)
	EndIf
	Switch StringLower(StringStripWS(String($oPlan.Item("upgrade_policy")), $STR_STRIPALL))
		Case "disabled", "walls"
		Case Else
			$sError = "Upgrade policy " & $oPlan.Item("upgrade_policy") & " has no exact legacy-engine adapter"
			Return SetError(14, 0, False)
	EndSwitch
	If StringLower(StringStripWS(String($oPlan.Item("upgrade_policy")), $STR_STRIPALL)) = "walls" And Not $bDiagnostic Then
		$sError = "Wall upgrades require Allow unverified and a supervised diagnostic acknowledgement"
		Return SetError(14, 1, False)
	EndIf
	If StringStripWS(String($oPlan.Item("account_queue_id")), $STR_STRIPALL) <> "" Then
		$sError = "Planner account queues are not wired to profile switching yet"
		Return SetError(15, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("notify_channel")), $STR_STRIPALL)) <> "log-only" Then
		$sError = "Only Bot log notifications are wired for planned runs"
		Return SetError(16, 0, False)
	EndIf

	; Exact-current supervised readiness on this fork reached the inherited FindTile export, which
	; returned its anti-copycat/licensing critical error before matchmaking. Every generic battle
	; strategy above depends on that recognizer. Keep the detailed plan validation for truthful
	; diagnostics, but never let diagnostic acknowledgement bypass a rejected runtime dependency.
	$sError = "Battle routes are unavailable in this fork because the inherited ImgLoc runtime rejected exact-current supervised readiness. Licensed permission or a clean-room recognizer is required; diagnostic mode cannot bypass this gate."
	Return SetError(17, 0, False)

EndFunc   ;==>RunExecutionContractValidate
