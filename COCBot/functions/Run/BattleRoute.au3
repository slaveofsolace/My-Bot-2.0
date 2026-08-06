; #FUNCTION# ====================================================================================================================
; Name ..........: Battle route
; Description ...: Normalizes battle destinations and keeps recognition/execution readiness separate from user intent.
; Remarks .......: A route is not runnable until both recognition and execution evidence have been supplied.
; ===============================================================================================================================
#include-once

Func BattleRouteCreate($sMode = "regular")
	Local $oRoute = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oRoute) Then Return SetError(1, 0, 0)

	$sMode = StringLower(StringStripWS($sMode, $STR_STRIPALL))
	Local $sSurface = "", $sFixture = "", $bLimitedAttacks = False, $bLegacyFallback = False

	Switch $sMode
		Case "home", "regular"
			$sMode = "regular"
			$sSurface = "multiplayer"
			$sFixture = "battle.regular.entry"
			$bLegacyFallback = True
		Case "ranked"
			$sSurface = "ranked"
			$sFixture = "battle.ranked.entry"
			$bLimitedAttacks = True
		Case "legend"
			$sSurface = "legend"
			$sFixture = "battle.legend.tier"
			$bLimitedAttacks = True
		Case "builder"
			$sSurface = "builder-base"
			$sFixture = "builder.home.extra-builder"
			$bLegacyFallback = True
		Case Else
			Return SetError(2, 0, 0)
	EndSwitch

	$oRoute.CompareMode = 1
	$oRoute.Add("schema_version", 1)
	$oRoute.Add("mode", $sMode)
	$oRoute.Add("surface", $sSurface)
	$oRoute.Add("entry_fixture", $sFixture)
	$oRoute.Add("limited_attacks", $bLimitedAttacks)
	$oRoute.Add("legacy_fallback", $bLegacyFallback)
	$oRoute.Add("recognition_ready", False)
	$oRoute.Add("execution_ready", False)
	$oRoute.Add("readiness_reason", "Current-client recognition and controlled runtime evidence are required")
	Return $oRoute
EndFunc   ;==>BattleRouteCreate

Func BattleRouteValidate(ByRef $oRoute, ByRef $sError)
	$sError = ""
	If Not IsObj($oRoute) Then
		$sError = "Battle route is not an object"
		Return SetError(1, 0, False)
	EndIf

	Local $aRequired = ["schema_version", "mode", "surface", "entry_fixture", "limited_attacks", "legacy_fallback", "recognition_ready", "execution_ready", "readiness_reason"]
	For $i = 0 To UBound($aRequired) - 1
		If Not $oRoute.Exists($aRequired[$i]) Then
			$sError = "Missing battle route field: " & $aRequired[$i]
			Return SetError(2, $i, False)
		EndIf
	Next

	Switch StringLower($oRoute.Item("mode"))
		Case "regular", "ranked", "legend", "builder"
		Case Else
			$sError = "Unsupported battle route: " & $oRoute.Item("mode")
			Return SetError(3, 0, False)
	EndSwitch

	If StringStripWS($oRoute.Item("surface"), $STR_STRIPALL) = "" Then
		$sError = "Battle surface cannot be empty"
		Return SetError(4, 0, False)
	EndIf
	If StringStripWS($oRoute.Item("entry_fixture"), $STR_STRIPALL) = "" Then
		$sError = "Entry fixture cannot be empty"
		Return SetError(5, 0, False)
	EndIf
	Return True
EndFunc   ;==>BattleRouteValidate

Func BattleRouteFromRunPlan(ByRef $oPlan, ByRef $sError)
	If Not RunPlanValidate($oPlan, $sError) Then Return SetError(1, 0, 0)
	Local $sMode = StringLower($oPlan.Item("mode"))
	If $sMode = "home" Then $sMode = "regular"
	Local $oRoute = BattleRouteCreate($sMode)
	If @error Or Not IsObj($oRoute) Then
		$sError = "Unable to create battle route for mode: " & $sMode
		Return SetError(2, 0, 0)
	EndIf
	Return $oRoute
EndFunc   ;==>BattleRouteFromRunPlan

Func BattleRouteSetReadiness(ByRef $oRoute, $bRecognitionReady, $bExecutionReady, $sReason = "")
	Local $sError
	If Not BattleRouteValidate($oRoute, $sError) Then Return SetError(1, 0, False)
	$oRoute.Item("recognition_ready") = ($bRecognitionReady = True)
	$oRoute.Item("execution_ready") = ($bExecutionReady = True)
	If $bRecognitionReady And $bExecutionReady Then
		$oRoute.Item("readiness_reason") = ""
	ElseIf StringStripWS($sReason, $STR_STRIPALL) <> "" Then
		$oRoute.Item("readiness_reason") = $sReason
	Else
		$oRoute.Item("readiness_reason") = "Recognition and execution evidence are incomplete"
	EndIf
	Return True
EndFunc   ;==>BattleRouteSetReadiness

Func BattleRouteCanStart(ByRef $oRoute, ByRef $sReason)
	If Not BattleRouteValidate($oRoute, $sReason) Then Return False
	If Not $oRoute.Item("recognition_ready") Then
		$sReason = "Recognition is not ready for fixture " & $oRoute.Item("entry_fixture")
		Return False
	EndIf
	If Not $oRoute.Item("execution_ready") Then
		$sReason = "Controlled execution evidence is not complete for " & $oRoute.Item("mode")
		Return False
	EndIf
	$sReason = ""
	Return True
EndFunc   ;==>BattleRouteCanStart

Func BattleRouteDescribe(ByRef $oRoute)
	Local $sError
	If Not BattleRouteValidate($oRoute, $sError) Then Return SetError(1, 0, $sError)
	Local $sDescription = StringUpper($oRoute.Item("mode")) & " via " & $oRoute.Item("surface")
	If $oRoute.Item("limited_attacks") Then $sDescription &= " / limited attacks"
	If Not $oRoute.Item("recognition_ready") Or Not $oRoute.Item("execution_ready") Then $sDescription &= " / evidence required"
	Return $sDescription
EndFunc   ;==>BattleRouteDescribe
