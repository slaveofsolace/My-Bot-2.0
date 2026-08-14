; #FUNCTION# ====================================================================================================================
; Name ..........: Battle route
; Description ...: Normalizes battle destinations and keeps recognition/execution readiness separate from user intent.
; Remarks .......: A route reports two things separately: which exact surface it targets, and whether that surface has been
;                  demonstrated on the current client. Diagnostic mode lets an undemonstrated route run so its behaviour can be
;                  observed, but the route keeps reporting itself as unverified for as long as the evidence is missing.
; ===============================================================================================================================
#include-once
#include "RunVerification.au3"

; Builds a route for an exact catalog surface (regular, ranked, revenge, legend-iii, legend-ii, legend-i, builder)
; rather than for a coarse engine route, so selecting Legend I can never execute the Legend III path.
Func BattleRouteCreateForSurface($sSurfaceId)
	Local $iIndex = CurrentGameFindBattleSurface($sSurfaceId)
	If $iIndex < 0 Then Return SetError(1, 0, 0)

	Local $sEngineRoute = StringLower(StringStripWS($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleEngineRoute], $STR_STRIPALL))
	If $sEngineRoute = "" Then
		; Sub-surfaces such as Revenge are reached through their parent's route.
		Local $iParent = CurrentGameFindBattleSurface($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleParentSurface])
		If $iParent < 0 Then Return SetError(2, 0, 0)
		$sEngineRoute = StringLower(StringStripWS($g_aCurrentGameBattleSurfaces[$iParent][$eGameBattleEngineRoute], $STR_STRIPALL))
		If $sEngineRoute = "" Then Return SetError(3, 0, 0)
	EndIf

	Local $oRoute = BattleRouteCreate($sEngineRoute)
	If Not IsObj($oRoute) Then Return SetError(4, 0, 0)

	$oRoute.Item("surface_id") = $g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleId]
	$oRoute.Item("surface") = $g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleId]
	$oRoute.Item("entry_fixture") = $g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleFixtureIds]
	$oRoute.Item("limited_attacks") = (StringLower($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleBudgetKind]) <> "unlimited")

	Local $sReason = ""
	If CurrentGameBattleSurfaceReady($oRoute.Item("surface_id"), $sReason) Then
		BattleRouteSetReadiness($oRoute, True, True)
	Else
		BattleRouteSetReadiness($oRoute, False, False, $sReason)
	EndIf
	Return $oRoute
EndFunc   ;==>BattleRouteCreateForSurface

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
			$sFixture = "builder.battle.entry"
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
	$oRoute.Add("surface_id", $sSurface)
	$oRoute.Add("diagnostic_enabled", False)
	$oRoute.Add("diagnostic_acknowledgement", "")
	Return $oRoute
EndFunc   ;==>BattleRouteCreate

; Permits an undemonstrated route to run so its behaviour can be watched. The acknowledgement is required so the choice is
; recorded against the operator rather than defaulted on, and it is echoed into session snapshots and event logs.
Func BattleRouteEnableDiagnostic(ByRef $oRoute, $sAcknowledgement, ByRef $sError)
	$sError = ""
	If Not BattleRouteValidate($oRoute, $sError) Then Return SetError(1, 0, False)
	$sAcknowledgement = StringStripWS(String($sAcknowledgement), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sAcknowledgement = "" Then
		$sError = "Diagnostic mode requires an acknowledgement describing who is observing the run"
		Return SetError(2, 0, False)
	EndIf
	$oRoute.Item("diagnostic_enabled") = True
	$oRoute.Item("diagnostic_acknowledgement") = $sAcknowledgement
	Return True
EndFunc   ;==>BattleRouteEnableDiagnostic

Func BattleRouteDisableDiagnostic(ByRef $oRoute)
	If Not IsObj($oRoute) Then Return SetError(1, 0, False)
	$oRoute.Item("diagnostic_enabled") = False
	$oRoute.Item("diagnostic_acknowledgement") = ""
	Return True
EndFunc   ;==>BattleRouteDisableDiagnostic

; The state this route would run under right now. Diagnostic mode never upgrades a route to verified.
Func BattleRouteVerificationState(ByRef $oRoute)
	If Not IsObj($oRoute) Then Return SetError(1, 0, $RUN_VERIFICATION_DIAGNOSTIC)
	If $oRoute.Item("recognition_ready") And $oRoute.Item("execution_ready") Then Return $RUN_VERIFICATION_VERIFIED
	Return $RUN_VERIFICATION_DIAGNOSTIC
EndFunc   ;==>BattleRouteVerificationState

Func BattleRouteValidate(ByRef $oRoute, ByRef $sError)
	$sError = ""
	If Not IsObj($oRoute) Then
		$sError = "Battle route is not an object"
		Return SetError(1, 0, False)
	EndIf

	Local $aRequired = ["schema_version", "mode", "surface", "entry_fixture", "limited_attacks", "legacy_fallback", "recognition_ready", "execution_ready", "readiness_reason", "surface_id", "diagnostic_enabled", "diagnostic_acknowledgement"]
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

	Local $sMissing = ""
	If Not $oRoute.Item("recognition_ready") Then
		$sMissing = "Recognition is not ready for fixture " & $oRoute.Item("entry_fixture")
	ElseIf Not $oRoute.Item("execution_ready") Then
		$sMissing = "Controlled execution evidence is not complete for " & $oRoute.Item("mode")
	EndIf

	If $sMissing = "" Then
		$sReason = ""
		Return True
	EndIf

	; Diagnostic mode trades a demonstrated route for an observable one. The reason survives so the caller can log
	; exactly what was missing while the run proceeds.
	If $oRoute.Item("diagnostic_enabled") Then
		$sReason = $sMissing
		Return True
	EndIf

	$sReason = $sMissing
	Return False
EndFunc   ;==>BattleRouteCanStart

Func BattleRouteDescribe(ByRef $oRoute)
	Local $sError
	If Not BattleRouteValidate($oRoute, $sError) Then Return SetError(1, 0, $sError)
	Local $sDescription = StringUpper($oRoute.Item("mode")) & " via " & $oRoute.Item("surface")
	If $oRoute.Item("limited_attacks") Then $sDescription &= " / limited attacks"
	If BattleRouteVerificationState($oRoute) = $RUN_VERIFICATION_DIAGNOSTIC Then
		$sDescription &= ($oRoute.Item("diagnostic_enabled") ? " / diagnostic" : " / evidence required")
	EndIf
	Return $sDescription
EndFunc   ;==>BattleRouteDescribe
