; #FUNCTION# ====================================================================================================================
; Name ..........: Run plan
; Description ...: Defines and validates a stable execution contract for farming and Builder Base sessions.
; Remarks .......: Run plans contain operational settings only. Credentials and authentication material are never stored here.
; ===============================================================================================================================
#include-once
#include "..\Game\GameCatalog.au3"

Func RunPlanCreateDefault($sMode = "home", $sStrategy = "auto", $sAttackScript = "profile-current")
	Local $oPlan = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oPlan) Then Return SetError(1, 0, 0)
	$oPlan.CompareMode = 1
	$oPlan.Add("schema_version", 1)
	$oPlan.Add("mode", StringLower($sMode))
	$oPlan.Add("strategy", $sStrategy)
	$oPlan.Add("attack_script", $sAttackScript)
	; Zero means the engine must use its freshly proven own-village identity at Start. Town Hall
	; presets replace zero with their exact level so an account/preset mismatch fails closed.
	$oPlan.Add("planned_town_hall", 0)
	$oPlan.Add("duration_minutes", 0)
	; The safest default uses the already-trained army without changing its queue. Keep that default
	; contract-valid and bounded to a single battle; users who enable training management may choose 0.
	$oPlan.Add("max_battles", 1)
	$oPlan.Add("stop_on_star_bonus", False)
	$oPlan.Add("max_failures", 3)
	$oPlan.Add("target_gold", 0)
	$oPlan.Add("target_elixir", 0)
	$oPlan.Add("target_dark_elixir", 0)
	$oPlan.Add("upgrade_policy", "disabled")
	$oPlan.Add("account_queue_id", "")
	$oPlan.Add("emulator", "auto")
	$oPlan.Add("emulator_instance", "")
	$oPlan.Add("army_source", "recipe")
	$oPlan.Add("army_recipe_name", "")
	$oPlan.Add("army_manage_training", False)
	$oPlan.Add("army_wait_for_full", True)
	$oPlan.Add("army_train_spells", False)
	$oPlan.Add("army_train_sieges", False)
	$oPlan.Add("search_min_gold", 0)
	$oPlan.Add("search_min_elixir", 0)
	$oPlan.Add("search_min_dark", 0)
	$oPlan.Add("search_max_seconds", 0)
	$oPlan.Add("search_town_hall_filter", "any")
	$oPlan.Add("donate_mode", "off")
	$oPlan.Add("donate_keep_army", True)
	$oPlan.Add("donate_max_per_run", 0)
	$oPlan.Add("donate_request_when_short", False)
	$oPlan.Add("events_clan_games", False)
	$oPlan.Add("events_clan_games_point_cap", 0)
	$oPlan.Add("events_laboratory", "off")
	$oPlan.Add("events_collect_resources", False)
	$oPlan.Add("events_collect_daily_reward", False)
	$oPlan.Add("notify_on_stop", False)
	$oPlan.Add("notify_on_error", True)
	$oPlan.Add("notify_channel", "log-only")
	Return $oPlan
EndFunc   ;==>RunPlanCreateDefault

Func RunPlanValidate(ByRef $oPlan, ByRef $sError)
	If Not IsObj($oPlan) Then
		$sError = "Run plan is not an object"
		Return SetError(1, 0, False)
	EndIf

	Local $aRequired = ["schema_version", "mode", "strategy", "attack_script", "planned_town_hall", "duration_minutes", "max_battles", "stop_on_star_bonus", "max_failures", "target_gold", "target_elixir", "target_dark_elixir", "upgrade_policy", "account_queue_id", _
		"emulator", "emulator_instance", "army_source", "army_recipe_name", "army_manage_training", "army_wait_for_full", "army_train_spells", "army_train_sieges", "search_min_gold", "search_min_elixir", "search_min_dark", "search_max_seconds", "search_town_hall_filter", _
		"donate_mode", "donate_keep_army", "donate_max_per_run", "donate_request_when_short", "events_clan_games", "events_clan_games_point_cap", "events_laboratory", "events_collect_resources", "events_collect_daily_reward", "notify_on_stop", "notify_on_error", "notify_channel"]
	For $i = 0 To UBound($aRequired) - 1
		If Not $oPlan.Exists($aRequired[$i]) Then
			$sError = "Missing run plan field: " & $aRequired[$i]
			Return SetError(2, $i, False)
		EndIf
	Next

	Switch StringLower($oPlan.Item("mode"))
		Case "home", "builder", "regular", "ranked", "legend"
		Case Else
			$sError = "Unsupported run mode: " & $oPlan.Item("mode")
			Return SetError(3, 0, False)
	EndSwitch

	If StringStripWS($oPlan.Item("strategy"), $STR_STRIPALL) = "" Then
		$sError = "Strategy cannot be empty"
		Return SetError(4, 0, False)
	EndIf
	Local $sAttackScript = StringStripWS(String($oPlan.Item("attack_script")), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sAttackScript = "" Or StringLen($sAttackScript) > 80 Or StringInStr($sAttackScript, "\") Or _
			StringInStr($sAttackScript, "/") Or StringInStr($sAttackScript, ":") Or StringInStr($sAttackScript, "*") Or _
			StringInStr($sAttackScript, "?") Or StringInStr($sAttackScript, Chr(34)) Or StringInStr($sAttackScript, "<") Or _
			StringInStr($sAttackScript, ">") Or StringInStr($sAttackScript, "|") Or StringInStr($sAttackScript, "..") Then
		$sError = "Attack script must be a safe bundled filename without an extension"
		Return SetError(4, 1, False)
	EndIf
	Local $iPlannedTownHall = Int(Number($oPlan.Item("planned_town_hall")))
	If Not IsNumber($oPlan.Item("planned_town_hall")) Or Number($oPlan.Item("planned_town_hall")) <> $iPlannedTownHall Or _
			$iPlannedTownHall < 0 Or $iPlannedTownHall > $CURRENT_GAME_MAX_TOWN_HALL Then
		$sError = "Planned Town Hall must be 0 (detect at Start) or a current Town Hall level"
		Return SetError(4, 2, False)
	EndIf

	Local $aNonNegative = ["duration_minutes", "max_battles", "max_failures", "target_gold", "target_elixir", "target_dark_elixir", "search_min_gold", "search_min_elixir", "search_min_dark", "search_max_seconds", "donate_max_per_run", "events_clan_games_point_cap"]
	For $i = 0 To UBound($aNonNegative) - 1
		If Number($oPlan.Item($aNonNegative[$i])) < 0 Then
			$sError = $aNonNegative[$i] & " cannot be negative"
			Return SetError(5, $i, False)
		EndIf
	Next

	Local $aBoolean = ["stop_on_star_bonus", "army_manage_training", "army_wait_for_full", "army_train_spells", "army_train_sieges", "donate_keep_army", "donate_request_when_short", "events_clan_games", "events_collect_resources", "events_collect_daily_reward", "notify_on_stop", "notify_on_error"]
	For $i = 0 To UBound($aBoolean) - 1
		If Not IsBool($oPlan.Item($aBoolean[$i])) Then
			$sError = $aBoolean[$i] & " must be boolean"
			Return SetError(6, $i, False)
		EndIf
	Next

	Switch StringLower($oPlan.Item("upgrade_policy"))
		Case "disabled", "walls", "suggested", "all"
		Case Else
			$sError = "Unsupported upgrade policy: " & $oPlan.Item("upgrade_policy")
			Return SetError(6, 0, False)
	EndSwitch

	Switch StringLower($oPlan.Item("emulator"))
		Case "auto", "bluestacks5", "memu", "nox", "ldplayer9", "mumu"
		Case Else
			$sError = "Unsupported emulator: " & $oPlan.Item("emulator")
			Return SetError(7, 0, False)
	EndSwitch
	Switch StringLower($oPlan.Item("army_source"))
		Case "recipe", "cookbook", "legacy-list"
		Case Else
			$sError = "Unsupported army source: " & $oPlan.Item("army_source")
			Return SetError(8, 0, False)
	EndSwitch
	Switch StringLower($oPlan.Item("search_town_hall_filter"))
		Case "any", "lower-only", "same-or-lower"
		Case Else
			$sError = "Unsupported Town Hall filter: " & $oPlan.Item("search_town_hall_filter")
			Return SetError(9, 0, False)
	EndSwitch
	Switch StringLower($oPlan.Item("donate_mode"))
		Case "off", "matching", "anything"
		Case Else
			$sError = "Unsupported donation mode: " & $oPlan.Item("donate_mode")
			Return SetError(10, 0, False)
	EndSwitch
	Switch StringLower($oPlan.Item("events_laboratory"))
		Case "off", "cheapest", "priority-list"
		Case Else
			$sError = "Unsupported laboratory mode: " & $oPlan.Item("events_laboratory")
			Return SetError(11, 0, False)
	EndSwitch
	Switch StringLower($oPlan.Item("notify_channel"))
		Case "log-only", "telegram", "windows-toast"
		Case Else
			$sError = "Unsupported notification channel: " & $oPlan.Item("notify_channel")
			Return SetError(12, 0, False)
	EndSwitch

	$sError = ""
	Return SetError(0, 0, True)
EndFunc   ;==>RunPlanValidate

Func RunPlanSetStopConditions(ByRef $oPlan, $iDurationMinutes = 0, $iMaxBattles = 0, $bStopOnStarBonus = False, $iMaxFailures = 3)
	Local $sError
	If Not RunPlanValidate($oPlan, $sError) Then Return SetError(1, 0, False)
	If $iDurationMinutes < 0 Or $iMaxBattles < 0 Or $iMaxFailures < 0 Then Return SetError(2, 0, False)
	$oPlan.Item("duration_minutes") = Int($iDurationMinutes)
	$oPlan.Item("max_battles") = Int($iMaxBattles)
	$oPlan.Item("stop_on_star_bonus") = ($bStopOnStarBonus = True)
	$oPlan.Item("max_failures") = Int($iMaxFailures)
	Return True
EndFunc   ;==>RunPlanSetStopConditions

Func RunPlanSetResourceTargets(ByRef $oPlan, $iGold = 0, $iElixir = 0, $iDarkElixir = 0)
	Local $sError
	If Not RunPlanValidate($oPlan, $sError) Then Return SetError(1, 0, False)
	If $iGold < 0 Or $iElixir < 0 Or $iDarkElixir < 0 Then Return SetError(2, 0, False)
	$oPlan.Item("target_gold") = Int($iGold)
	$oPlan.Item("target_elixir") = Int($iElixir)
	$oPlan.Item("target_dark_elixir") = Int($iDarkElixir)
	Return True
EndFunc   ;==>RunPlanSetResourceTargets

Func RunPlanSetPlannedTownHall(ByRef $oPlan, $iTownHall, ByRef $sError)
	$sError = ""
	If Not IsObj($oPlan) Or Not $oPlan.Exists("planned_town_hall") Then
		$sError = "Run plan cannot carry a planned Town Hall"
		Return SetError(1, 0, False)
	EndIf
	If Not IsNumber($iTownHall) Or Number($iTownHall) <> Int(Number($iTownHall)) Or _
			Int(Number($iTownHall)) < 0 Or Int(Number($iTownHall)) > $CURRENT_GAME_MAX_TOWN_HALL Then
		$sError = "Planned Town Hall must be 0 (detect at Start) or a current Town Hall level"
		Return SetError(2, 0, False)
	EndIf
	$oPlan.Item("planned_town_hall") = Int(Number($iTownHall))
	Return True
EndFunc   ;==>RunPlanSetPlannedTownHall

Func RunPlanShouldStop(ByRef $oPlan, $iElapsedMilliseconds, $iBattleCount, $iFailureCount, $bStarBonusComplete, $iGold = 0, $iElixir = 0, $iDarkElixir = 0)
	Local $sError
	If Not RunPlanValidate($oPlan, $sError) Then Return SetError(1, 0, "invalid-plan")

	Local $iDuration = Int($oPlan.Item("duration_minutes"))
	If $iDuration > 0 And $iElapsedMilliseconds >= $iDuration * 60000 Then Return "duration"

	Local $iMaxBattles = Int($oPlan.Item("max_battles"))
	If $iMaxBattles > 0 And $iBattleCount >= $iMaxBattles Then Return "battle-limit"

	If $oPlan.Item("stop_on_star_bonus") And $bStarBonusComplete Then Return "star-bonus"

	Local $iMaxFailures = Int($oPlan.Item("max_failures"))
	If $iMaxFailures > 0 And $iFailureCount >= $iMaxFailures Then Return "failure-limit"

	Local $iTargetGold = Int($oPlan.Item("target_gold"))
	Local $iTargetElixir = Int($oPlan.Item("target_elixir"))
	Local $iTargetDark = Int($oPlan.Item("target_dark_elixir"))
	If $iTargetGold > 0 And $iGold >= $iTargetGold Then Return "gold-target"
	If $iTargetElixir > 0 And $iElixir >= $iTargetElixir Then Return "elixir-target"
	If $iTargetDark > 0 And $iDarkElixir >= $iTargetDark Then Return "dark-elixir-target"

	Return ""
EndFunc   ;==>RunPlanShouldStop

Func RunPlanDescribe(ByRef $oPlan)
	Local $sError
	If Not RunPlanValidate($oPlan, $sError) Then Return SetError(1, 0, $sError)
	Local $sDescription = StringUpper($oPlan.Item("mode")) & " / " & $oPlan.Item("strategy")
	$sDescription &= (Int($oPlan.Item("planned_town_hall")) > 0 ? _
			(" / planned TH" & Int($oPlan.Item("planned_town_hall"))) : " / Town Hall detected at Start")
	If StringLower($oPlan.Item("attack_script")) <> "profile-current" Then $sDescription &= " / " & $oPlan.Item("attack_script")
	If Int($oPlan.Item("duration_minutes")) > 0 Then $sDescription &= " / " & Int($oPlan.Item("duration_minutes")) & " min"
	If Int($oPlan.Item("max_battles")) = 1 Then
		$sDescription &= " / 1 battle"
	ElseIf Int($oPlan.Item("max_battles")) > 1 Then
		$sDescription &= " / " & Int($oPlan.Item("max_battles")) & " battles"
	EndIf
	If Int($oPlan.Item("max_failures")) = 1 Then
		$sDescription &= " / 1 failure max"
	ElseIf Int($oPlan.Item("max_failures")) > 1 Then
		$sDescription &= " / " & Int($oPlan.Item("max_failures")) & " failures max"
	EndIf
	If $oPlan.Item("stop_on_star_bonus") Then $sDescription &= " / star bonus"
	If Not $oPlan.Item("army_manage_training") Then $sDescription &= " / current trained army"
	Return $sDescription
EndFunc   ;==>RunPlanDescribe
