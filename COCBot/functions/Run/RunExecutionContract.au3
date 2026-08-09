; #FUNCTION# ====================================================================================================================
; Name ..........: Run execution contract
; Description ...: Declares which prepared planner values the inherited engine can execute exactly.
; Remarks .......: Values without a faithful adapter are rejected at Start. Silently ignoring them would make the planner lie.
; ===============================================================================================================================
#include-once
#include <StringConstants.au3>
#include "RunIntent.au3"

Func RunExecutionContractValidate(ByRef $oIntent, ByRef $sError)
	$sError = ""
	If Not RunIntentValidate($oIntent, $sError) Then Return SetError(1, 0, False)

	Local $sSurface = StringLower(StringStripWS(String($oIntent.Item("surface_id")), $STR_STRIPALL))
	If $sSurface <> "regular" Then
		$sError = "The inherited attack engine is only wired to Regular Battles. " & $sSurface & " remains evidence-only."
		Return SetError(2, 0, False)
	EndIf

	Local $oPlan = $oIntent.Item("plan")
	Local $oPacing = $oIntent.Item("pacing")
	If Int($oPacing.Item("retry_attempts")) > 0 Then
		$sError = "Generic action retries need a visual-change observer and are not wired yet; use 0"
		Return SetError(3, 0, False)
	EndIf
	Local $sStrategy = StringLower(StringStripWS(String($oPlan.Item("strategy")), $STR_STRIPALL))
	If $sStrategy <> "legacy.csv" And $sStrategy <> "legacy.standard" Then
		$sError = "Attack strategy " & $sStrategy & " has no exact legacy-engine adapter"
		Return SetError(4, 0, False)
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

	Local $sEmulator = StringLower(StringStripWS(String($oPlan.Item("emulator")), $STR_STRIPALL))
	If $sEmulator = "auto" And StringStripWS(String($oPlan.Item("emulator_instance")), $STR_STRIPALL) <> "" Then
		$sError = "Choose a specific emulator before selecting an instance"
		Return SetError(9, 0, False)
	EndIf
	If Not $oPlan.Item("donate_keep_army") Then
		$sError = "Allowing donations to consume the attack army has no bounded legacy adapter"
		Return SetError(10, 0, False)
	EndIf
	If Int($oPlan.Item("donate_max_per_run")) > 0 Then
		$sError = "Per-run donation limits are not wired yet; use 0"
		Return SetError(11, 0, False)
	EndIf
	If Int($oPlan.Item("events_clan_games_point_cap")) > 0 Then
		$sError = "The Clan Games point cap is not wired yet; use 0"
		Return SetError(12, 0, False)
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
	If StringStripWS(String($oPlan.Item("account_queue_id")), $STR_STRIPALL) <> "" Then
		$sError = "Planner account queues are not wired to profile switching yet"
		Return SetError(15, 0, False)
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("notify_channel")), $STR_STRIPALL)) <> "log-only" Then
		$sError = "Only Bot log notifications are wired for planned runs"
		Return SetError(16, 0, False)
	EndIf

	Return True
EndFunc   ;==>RunExecutionContractValidate
