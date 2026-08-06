; #FUNCTION# ====================================================================================================================
; Name ..........: Run plan
; Description ...: Defines and validates a stable execution contract for farming and Builder Base sessions.
; Remarks .......: Run plans contain operational settings only. Credentials and authentication material are never stored here.
; ===============================================================================================================================
#include-once

Func RunPlanCreateDefault($sMode = "home", $sStrategy = "auto")
	Local $oPlan = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oPlan) Then Return SetError(1, 0, 0)
	$oPlan.CompareMode = 1
	$oPlan.Add("schema_version", 1)
	$oPlan.Add("mode", StringLower($sMode))
	$oPlan.Add("strategy", $sStrategy)
	$oPlan.Add("duration_minutes", 0)
	$oPlan.Add("max_battles", 0)
	$oPlan.Add("stop_on_star_bonus", False)
	$oPlan.Add("max_failures", 3)
	$oPlan.Add("target_gold", 0)
	$oPlan.Add("target_elixir", 0)
	$oPlan.Add("target_dark_elixir", 0)
	$oPlan.Add("upgrade_policy", "disabled")
	$oPlan.Add("account_queue_id", "")
	Return $oPlan
EndFunc   ;==>RunPlanCreateDefault

Func RunPlanValidate(ByRef $oPlan, ByRef $sError = Default)
	If $sError = Default Then Local $sError = ""
	If Not IsObj($oPlan) Then
		$sError = "Run plan is not an object"
		Return SetError(1, 0, False)
	EndIf

	Local $aRequired = ["schema_version", "mode", "strategy", "duration_minutes", "max_battles", "stop_on_star_bonus", "max_failures", "target_gold", "target_elixir", "target_dark_elixir", "upgrade_policy", "account_queue_id"]
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

	Local $aNonNegative = ["duration_minutes", "max_battles", "max_failures", "target_gold", "target_elixir", "target_dark_elixir"]
	For $i = 0 To UBound($aNonNegative) - 1
		If Number($oPlan.Item($aNonNegative[$i])) < 0 Then
			$sError = $aNonNegative[$i] & " cannot be negative"
			Return SetError(5, $i, False)
		EndIf
	Next

	Switch StringLower($oPlan.Item("upgrade_policy"))
		Case "disabled", "walls", "suggested", "all"
		Case Else
			$sError = "Unsupported upgrade policy: " & $oPlan.Item("upgrade_policy")
			Return SetError(6, 0, False)
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
	If Int($oPlan.Item("duration_minutes")) > 0 Then $sDescription &= " / " & Int($oPlan.Item("duration_minutes")) & " min"
	If Int($oPlan.Item("max_battles")) > 0 Then $sDescription &= " / " & Int($oPlan.Item("max_battles")) & " battles"
	If $oPlan.Item("stop_on_star_bonus") Then $sDescription &= " / star bonus"
	Return $sDescription
EndFunc   ;==>RunPlanDescribe
