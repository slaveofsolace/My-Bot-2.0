; #FUNCTION# ====================================================================================================================
; Name ..........: Run intent
; Description ...: Binds a run plan to one exact battle surface, one Hero loadout, and that surface's attack quota.
; Remarks .......: The intent is the only object allowed to open a session. Keeping the exact surface attached from the start is
;                  what stops the engine from accepting "Legend I" and then executing whatever the legacy coordinates respond to.
; ===============================================================================================================================
#include-once
#include "RunPlan.au3"
#include "BattleRoute.au3"
#include "BattleQuota.au3"
#include "HeroLoadout.au3"
#include "RunSession.au3"
#include "RunEvent.au3"
#include "RunVerification.au3"
#include "RunPacing.au3"

Func _RunIntentRouteForPlanMode($sMode)
	Switch StringLower(StringStripWS(String($sMode), $STR_STRIPALL))
		Case "home", "regular"
			Return "regular"
		Case "ranked"
			Return "ranked"
		Case "legend"
			Return "legend"
		Case "builder"
			Return "builder"
	EndSwitch
	Return ""
EndFunc   ;==>_RunIntentRouteForPlanMode

Func RunIntentCreate(ByRef $oPlan, $sSurfaceId, ByRef $oLoadout, ByRef $sError)
	$sError = ""
	If Not RunPlanValidate($oPlan, $sError) Then Return SetError(1, 0, 0)
	If Not HeroLoadoutValidate($oLoadout, $sError) Then Return SetError(2, 0, 0)
	Local $iPlannedTownHall = Int($oPlan.Item("planned_town_hall"))
	If Int($oLoadout.Item("town_hall")) <> $iPlannedTownHall Then
		$sError = "Hero loadout Town Hall does not match the run plan"
		Return SetError(2, 1, 0)
	EndIf

	Local $iSurface = CurrentGameFindBattleSurface($sSurfaceId)
	If $iSurface < 0 Then
		$sError = "Unknown battle surface: " & $sSurfaceId
		Return SetError(3, 0, 0)
	EndIf

	Local $oRoute = BattleRouteCreateForSurface($sSurfaceId)
	If Not IsObj($oRoute) Then
		$sError = "Battle surface " & $sSurfaceId & " has no reachable engine route"
		Return SetError(4, 0, 0)
	EndIf

	Local $sPlanRoute = _RunIntentRouteForPlanMode($oPlan.Item("mode"))
	If $sPlanRoute <> "" And $sPlanRoute <> StringLower($oRoute.Item("mode")) Then
		$sError = "Run plan mode " & $oPlan.Item("mode") & " does not match surface " & $sSurfaceId
		Return SetError(5, 0, 0)
	EndIf

	Local $oQuota = BattleQuotaCreate($sSurfaceId)
	If Not IsObj($oQuota) Then
		$sError = "Unable to build an attack quota for " & $sSurfaceId
		Return SetError(6, 0, 0)
	EndIf

	; Every intent carries pacing, defaulted rather than optional, so nothing downstream has to check whether it is there.
	Local $oPacing = RunPacingCreateDefault()
	If Not IsObj($oPacing) Then
		$sError = "Unable to create run pacing for " & $sSurfaceId
		Return SetError(7, 0, 0)
	EndIf

	Local $oIntent = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oIntent) Then Return SetError(8, 0, 0)
	$oIntent.CompareMode = 1
	$oIntent.Add("schema_version", 1)
	$oIntent.Add("surface_id", $g_aCurrentGameBattleSurfaces[$iSurface][$eGameBattleId])
	$oIntent.Add("surface_label", $g_aCurrentGameBattleSurfaces[$iSurface][$eGameBattleLabel])
	$oIntent.Add("planned_town_hall", $iPlannedTownHall)
	$oIntent.Add("plan", $oPlan)
	$oIntent.Add("route", $oRoute)
	$oIntent.Add("quota", $oQuota)
	$oIntent.Add("loadout", $oLoadout)
	$oIntent.Add("pacing", $oPacing)
	$oIntent.Add("profile_id", "")
	Return $oIntent
EndFunc   ;==>RunIntentCreate

Func RunIntentSetPacing(ByRef $oIntent, $iActionDelayMs, $iSettleMs, $iRetryAttempts, $iBreakEveryMinutes, $iBreakMinutes, ByRef $sError)
	$sError = ""
	If Not RunIntentValidate($oIntent, $sError) Then Return SetError(1, 0, False)
	Local $oPacing = $oIntent.Item("pacing")
	If Not RunPacingSet($oPacing, $iActionDelayMs, $iSettleMs, $iRetryAttempts, $iBreakEveryMinutes, $iBreakMinutes, $sError) Then Return SetError(2, 0, False)
	Return True
EndFunc   ;==>RunIntentSetPacing

Func RunIntentValidate(ByRef $oIntent, ByRef $sError)
	$sError = ""
	If Not IsObj($oIntent) Then
		$sError = "Run intent is not an object"
		Return SetError(1, 0, False)
	EndIf

	Local $aRequired = ["schema_version", "surface_id", "surface_label", "planned_town_hall", "plan", "route", "quota", "loadout", "pacing", "profile_id"]
	For $i = 0 To UBound($aRequired) - 1
		If Not $oIntent.Exists($aRequired[$i]) Then
			$sError = "Missing run intent field: " & $aRequired[$i]
			Return SetError(2, $i, False)
		EndIf
	Next

	Local $oPlan = $oIntent.Item("plan")
	If Not RunPlanValidate($oPlan, $sError) Then
		$sError = "Invalid run plan: " & $sError
		Return SetError(3, 0, False)
	EndIf
	Local $oRoute = $oIntent.Item("route")
	If Not BattleRouteValidate($oRoute, $sError) Then
		$sError = "Invalid battle route: " & $sError
		Return SetError(4, 0, False)
	EndIf
	Local $oQuota = $oIntent.Item("quota")
	If Not BattleQuotaValidate($oQuota, $sError) Then
		$sError = "Invalid attack quota: " & $sError
		Return SetError(5, 0, False)
	EndIf
	Local $oLoadout = $oIntent.Item("loadout")
	If Not HeroLoadoutValidate($oLoadout, $sError) Then
		$sError = "Invalid Hero loadout: " & $sError
		Return SetError(6, 0, False)
	EndIf
	Local $iPlannedTownHall = Int($oPlan.Item("planned_town_hall"))
	If Int($oIntent.Item("planned_town_hall")) <> $iPlannedTownHall Or _
			Int($oLoadout.Item("town_hall")) <> $iPlannedTownHall Then
		$sError = "Run intent Town Hall, plan, and Hero loadout do not match"
		Return SetError(6, 1, False)
	EndIf
	Local $oPacing = $oIntent.Item("pacing")
	If Not RunPacingValidate($oPacing, $sError) Then
		$sError = "Invalid run pacing: " & $sError
		Return SetError(9, 0, False)
	EndIf

	If StringLower($oQuota.Item("surface_id")) <> StringLower($oIntent.Item("surface_id")) Then
		$sError = "Attack quota belongs to a different surface"
		Return SetError(7, 0, False)
	EndIf
	If StringLower($oRoute.Item("surface_id")) <> StringLower($oIntent.Item("surface_id")) Then
		$sError = "Battle route belongs to a different surface"
		Return SetError(8, 0, False)
	EndIf
	Return True
EndFunc   ;==>RunIntentValidate

Func RunIntentVerificationState(ByRef $oIntent)
	Local $sError
	If Not RunIntentValidate($oIntent, $sError) Then Return SetError(1, 0, $RUN_VERIFICATION_DIAGNOSTIC)
	Local $oRoute = $oIntent.Item("route")
	Return BattleRouteVerificationState($oRoute)
EndFunc   ;==>RunIntentVerificationState

Func RunIntentEnableDiagnostic(ByRef $oIntent, $sAcknowledgement, ByRef $sError)
	$sError = ""
	If Not RunIntentValidate($oIntent, $sError) Then Return SetError(1, 0, False)
	Local $oRoute = $oIntent.Item("route")
	If Not BattleRouteEnableDiagnostic($oRoute, $sAcknowledgement, $sError) Then Return SetError(2, 0, False)
	Return True
EndFunc   ;==>RunIntentEnableDiagnostic

Func RunIntentObserveQuota(ByRef $oIntent, $iRemaining, $iObservedAtMs, ByRef $sError)
	$sError = ""
	If Not RunIntentValidate($oIntent, $sError) Then Return SetError(1, 0, False)
	Local $oQuota = $oIntent.Item("quota")
	If Not BattleQuotaObserve($oQuota, $iRemaining, $iObservedAtMs, $sError) Then Return SetError(2, 0, False)
	Return True
EndFunc   ;==>RunIntentObserveQuota

Func RunIntentSetProfile(ByRef $oIntent, $sProfileId)
	Local $sError
	If Not RunIntentValidate($oIntent, $sError) Then Return SetError(1, 0, False)
	$oIntent.Item("profile_id") = StringStripWS(String($sProfileId), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	Return True
EndFunc   ;==>RunIntentSetProfile

; Training management is part of the plan rather than the profile. Callers use this accessor so the
; one-run current-army mode cannot accidentally be inferred from mutable legacy training globals.
Func RunIntentManagesTraining(ByRef $oIntent)
	Local $sError = ""
	If Not RunIntentValidate($oIntent, $sError) Then Return SetError(1, 0, True)
	Local $oPlan = $oIntent.Item("plan")
	Return $oPlan.Item("army_manage_training")
EndFunc   ;==>RunIntentManagesTraining

Func RunIntentPlannedTownHall(ByRef $oIntent)
        Local $sError = ""
        If Not RunIntentValidate($oIntent, $sError) Then Return SetError(1, 0, 0)
        Return Int($oIntent.Item("planned_town_hall"))
EndFunc   ;==>RunIntentPlannedTownHall

Func RunIntentRequiresBattleQuota(ByRef $oIntent)
        Local $sError = ""
        If Not RunIntentValidate($oIntent, $sError) Then Return SetError(1, 0, True)
        Local $oPlan = $oIntent.Item("plan")
        Local $sStrategy = StringLower(StringStripWS(String($oPlan.Item("strategy")), $STR_STRIPALL))
        Switch $sStrategy
                Case "builder.collectors"
                        Return False
        EndSwitch
        Return True
EndFunc   ;==>RunIntentRequiresBattleQuota

; Every gate an intent must clear before a session may open. Diagnostic mode relaxes the evidence gate only.
; Battle intents keep the quota gate hard; non-battle maintenance intents do not consume attack availability.
Func RunIntentCanStart(ByRef $oIntent, ByRef $sReason)
        $sReason = ""
        If Not RunIntentValidate($oIntent, $sReason) Then Return False

	Local $oRoute = $oIntent.Item("route")
	Local $sRouteReason = ""
	If Not BattleRouteCanStart($oRoute, $sRouteReason) Then
		$sReason = $sRouteReason
		Return False
	EndIf

        Local $oQuota = $oIntent.Item("quota")
        Local $sQuotaReason = ""
        If RunIntentRequiresBattleQuota($oIntent) Then
                If Not BattleQuotaCanConsume($oQuota, $sQuotaReason) Then
                        $sReason = $sQuotaReason
                        Return False
                EndIf
        EndIf

        ; Carried through so callers can log what diagnostic mode is standing in for.
        $sReason = $sRouteReason
        Return True
EndFunc   ;==>RunIntentCanStart

Func RunIntentOpenSession(ByRef $oIntent, $sSessionId, ByRef $sError)
	$sError = ""
	If Not RunIntentCanStart($oIntent, $sError) Then Return SetError(1, 0, 0)

	Local $oPlan = $oIntent.Item("plan")
	Local $oSession = RunSessionCreate($oPlan, $sSessionId)
	If Not IsObj($oSession) Then
		$sError = "Unable to create a run session for " & $sSessionId
		Return SetError(2, 0, 0)
	EndIf

	Local $oRoute = $oIntent.Item("route")
	Local $sAttachError = ""
	If Not RunSessionAttachRoute($oSession, $oRoute, $sAttachError) Then
		$sError = $sAttachError
		Return SetError(3, 0, 0)
	EndIf

	If $oIntent.Item("profile_id") <> "" Then RunSessionSetAccount($oSession, $oIntent.Item("profile_id"))
	Return $oSession
EndFunc   ;==>RunIntentOpenSession

Func RunIntentRecordBattle(ByRef $oIntent, ByRef $oSession, $bSuccess, ByRef $sError, $iGold = 0, $iElixir = 0, $iDarkElixir = 0)
	$sError = ""
	If Not RunIntentValidate($oIntent, $sError) Then Return SetError(1, 0, False)
	Local $oQuota = $oIntent.Item("quota")
	If Not BattleQuotaConsume($oQuota, $sError) Then Return SetError(2, 0, False)
	If Not RunSessionRecordBattle($oSession, $bSuccess, $iGold, $iElixir, $iDarkElixir) Then
		$sError = "Session refused the battle record"
		Return SetError(3, 0, False)
	EndIf
	Return True
EndFunc   ;==>RunIntentRecordBattle

Func RunIntentDescribe(ByRef $oIntent)
	Local $sError
	If Not RunIntentValidate($oIntent, $sError) Then Return SetError(1, 0, $sError)
	Local $oQuota = $oIntent.Item("quota")
	Local $oLoadout = $oIntent.Item("loadout")
	Local $oPacing = $oIntent.Item("pacing")
	Local $oPlan = $oIntent.Item("plan")
	Local $sDescription = $oIntent.Item("surface_label") & " / Plan: " & RunPlanDescribe($oPlan) & " / " & _
		HeroLoadoutDescribe($oLoadout) & " / Surface quota: " & BattleQuotaDescribe($oQuota) & " / " & RunPacingDescribe($oPacing)
	If RunIntentVerificationState($oIntent) = $RUN_VERIFICATION_DIAGNOSTIC Then $sDescription &= " / " & RunVerificationLabel($RUN_VERIFICATION_DIAGNOSTIC)
	Return $sDescription
EndFunc   ;==>RunIntentDescribe
