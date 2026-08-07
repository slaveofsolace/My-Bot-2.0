; #FUNCTION# ====================================================================================================================
; Name ..........: Run session
; Description ...: Deterministic state machine for a run plan, battle counters, loot totals, failures, and stop decisions.
; Remarks .......: Time is supplied by the caller so tests do not depend on wall-clock timing. Verification state is a one-way
;                  latch: once a session executes anything undemonstrated it reports itself unverified for the rest of its life.
; ===============================================================================================================================
#include-once
#include "RunVerification.au3"
#include "BattleRoute.au3"

Func RunSessionCreate(ByRef $oPlan, $sSessionId = "session")
	Local $sError
	If Not RunPlanValidate($oPlan, $sError) Then Return SetError(1, 0, 0)
	$sSessionId = StringStripWS($sSessionId, $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sSessionId = "" Then Return SetError(2, 0, 0)

	Local $oSession = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oSession) Then Return SetError(3, 0, 0)
	$oSession.CompareMode = 1
	$oSession.Add("schema_version", 1)
	$oSession.Add("session_id", $sSessionId)
	$oSession.Add("state", "ready")
	$oSession.Add("plan", $oPlan)
	$oSession.Add("account_profile_id", "")
	$oSession.Add("battle_count", 0)
	$oSession.Add("success_count", 0)
	$oSession.Add("failure_count", 0)
	$oSession.Add("gold", 0)
	$oSession.Add("elixir", 0)
	$oSession.Add("dark_elixir", 0)
	$oSession.Add("stop_reason", "")
	$oSession.Add("last_error", "")
	$oSession.Add("verification_state", $RUN_VERIFICATION_VERIFIED)
	$oSession.Add("verification_reason", "")
	Return $oSession
EndFunc   ;==>RunSessionCreate

; One-way latch. Nothing in this file ever moves a session back to verified.
Func RunSessionMarkDiagnostic(ByRef $oSession, $sReason = "")
	Local $sError
	If Not RunSessionValidate($oSession, $sError) Then Return SetError(1, 0, False)
	$oSession.Item("verification_state") = $RUN_VERIFICATION_DIAGNOSTIC
	If StringStripWS(String($sReason), $STR_STRIPALL) <> "" Then
		Local $sExisting = $oSession.Item("verification_reason")
		If $sExisting = "" Then
			$oSession.Item("verification_reason") = $sReason
		ElseIf Not StringInStr($sExisting, $sReason) Then
			$oSession.Item("verification_reason") = $sExisting & "; " & $sReason
		EndIf
	EndIf
	Return True
EndFunc   ;==>RunSessionMarkDiagnostic

Func RunSessionIsVerified(ByRef $oSession)
	If Not IsObj($oSession) Then Return SetError(1, 0, False)
	Return StringLower($oSession.Item("verification_state")) = $RUN_VERIFICATION_VERIFIED
EndFunc   ;==>RunSessionIsVerified

; Binds a route to the session and inherits its verification state before any battle is recorded.
Func RunSessionAttachRoute(ByRef $oSession, ByRef $oRoute, ByRef $sError)
	$sError = ""
	If Not RunSessionValidate($oSession, $sError) Then Return SetError(1, 0, False)
	If Not BattleRouteValidate($oRoute, $sError) Then Return SetError(2, 0, False)
	If $oSession.Item("state") <> "ready" Then
		$sError = "A route can only be attached before the session starts"
		Return SetError(3, 0, False)
	EndIf
	If BattleRouteVerificationState($oRoute) = $RUN_VERIFICATION_DIAGNOSTIC Then
		Local $sRouteReason = $oRoute.Item("readiness_reason")
		Local $sWhy = (($sRouteReason = "") ? ("Route " & $oRoute.Item("surface_id") & " has no current-client evidence") : $sRouteReason)
		RunSessionMarkDiagnostic($oSession, $sWhy)
	EndIf
	Return True
EndFunc   ;==>RunSessionAttachRoute

Func RunSessionValidate(ByRef $oSession, ByRef $sError)
	$sError = ""
	If Not IsObj($oSession) Then
		$sError = "Run session is not an object"
		Return SetError(1, 0, False)
	EndIf

	Local $aRequired = ["schema_version", "session_id", "state", "plan", "account_profile_id", "battle_count", "success_count", "failure_count", "gold", "elixir", "dark_elixir", "stop_reason", "last_error", "verification_state", "verification_reason"]
	For $i = 0 To UBound($aRequired) - 1
		If Not $oSession.Exists($aRequired[$i]) Then
			$sError = "Missing run session field: " & $aRequired[$i]
			Return SetError(2, $i, False)
		EndIf
	Next

	Switch StringLower($oSession.Item("state"))
		Case "ready", "running", "stopping", "completed", "failed"
		Case Else
			$sError = "Unsupported run session state: " & $oSession.Item("state")
			Return SetError(3, 0, False)
	EndSwitch

	Local $oPlan = $oSession.Item("plan"), $sPlanError
	If Not RunPlanValidate($oPlan, $sPlanError) Then
		$sError = "Invalid run plan: " & $sPlanError
		Return SetError(4, 0, False)
	EndIf
	Return True
EndFunc   ;==>RunSessionValidate

Func RunSessionSetAccount(ByRef $oSession, $sProfileId)
	Local $sError
	If Not RunSessionValidate($oSession, $sError) Then Return SetError(1, 0, False)
	If $oSession.Item("state") <> "ready" Then Return SetError(2, 0, False)
	$sProfileId = StringStripWS($sProfileId, $STR_STRIPLEADING + $STR_STRIPTRAILING)
	$oSession.Item("account_profile_id") = $sProfileId
	Return True
EndFunc   ;==>RunSessionSetAccount

Func RunSessionStart(ByRef $oSession)
	Local $sError
	If Not RunSessionValidate($oSession, $sError) Then Return SetError(1, 0, False)
	If $oSession.Item("state") <> "ready" Then Return SetError(2, 0, False)
	$oSession.Item("state") = "running"
	Return True
EndFunc   ;==>RunSessionStart

Func RunSessionRecordBattle(ByRef $oSession, $bSuccess, $iGold = 0, $iElixir = 0, $iDarkElixir = 0)
	Local $sError
	If Not RunSessionValidate($oSession, $sError) Then Return SetError(1, 0, False)
	If $oSession.Item("state") <> "running" Then Return SetError(2, 0, False)
	If $iGold < 0 Or $iElixir < 0 Or $iDarkElixir < 0 Then Return SetError(3, 0, False)

	$oSession.Item("battle_count") = Int($oSession.Item("battle_count")) + 1
	If $bSuccess Then
		$oSession.Item("success_count") = Int($oSession.Item("success_count")) + 1
	Else
		$oSession.Item("failure_count") = Int($oSession.Item("failure_count")) + 1
	EndIf
	$oSession.Item("gold") = Int($oSession.Item("gold")) + Int($iGold)
	$oSession.Item("elixir") = Int($oSession.Item("elixir")) + Int($iElixir)
	$oSession.Item("dark_elixir") = Int($oSession.Item("dark_elixir")) + Int($iDarkElixir)
	Return True
EndFunc   ;==>RunSessionRecordBattle

Func RunSessionEvaluateStop(ByRef $oSession, $iElapsedMilliseconds, $bStarBonusComplete = False)
	Local $sError
	If Not RunSessionValidate($oSession, $sError) Then Return SetError(1, 0, "invalid-session")
	If $oSession.Item("state") <> "running" Then Return SetError(2, 0, "not-running")

	Local $oPlan = $oSession.Item("plan")
	Local $sReason = RunPlanShouldStop($oPlan, $iElapsedMilliseconds, $oSession.Item("battle_count"), $oSession.Item("failure_count"), $bStarBonusComplete, $oSession.Item("gold"), $oSession.Item("elixir"), $oSession.Item("dark_elixir"))
	If $sReason <> "" Then
		$oSession.Item("state") = "stopping"
		$oSession.Item("stop_reason") = $sReason
	EndIf
	Return $sReason
EndFunc   ;==>RunSessionEvaluateStop

Func RunSessionRequestStop(ByRef $oSession, $sReason = "requested")
	Local $sError
	If Not RunSessionValidate($oSession, $sError) Then Return SetError(1, 0, False)
	Switch $oSession.Item("state")
		Case "ready", "running"
			$oSession.Item("state") = "stopping"
			$oSession.Item("stop_reason") = $sReason
			Return True
		Case "stopping"
			Return True
		Case Else
			Return SetError(2, 0, False)
	EndSwitch
EndFunc   ;==>RunSessionRequestStop

Func RunSessionComplete(ByRef $oSession)
	Local $sError
	If Not RunSessionValidate($oSession, $sError) Then Return SetError(1, 0, False)
	Switch $oSession.Item("state")
		Case "running", "stopping"
			$oSession.Item("state") = "completed"
			Return True
		Case Else
			Return SetError(2, 0, False)
	EndSwitch
EndFunc   ;==>RunSessionComplete

Func RunSessionFail(ByRef $oSession, $sErrorMessage)
	Local $sError
	If Not RunSessionValidate($oSession, $sError) Then Return SetError(1, 0, False)
	If $oSession.Item("state") = "completed" Or $oSession.Item("state") = "failed" Then Return SetError(2, 0, False)
	$oSession.Item("state") = "failed"
	$oSession.Item("last_error") = $sErrorMessage
	$oSession.Item("stop_reason") = "error"
	Return True
EndFunc   ;==>RunSessionFail

Func RunSessionSnapshot(ByRef $oSession)
	Local $sError
	If Not RunSessionValidate($oSession, $sError) Then Return SetError(1, 0, 0)
	Local $oSnapshot = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oSnapshot) Then Return SetError(2, 0, 0)
	Local $aFields = ["schema_version", "session_id", "state", "account_profile_id", "battle_count", "success_count", "failure_count", "gold", "elixir", "dark_elixir", "stop_reason", "last_error", "verification_state", "verification_reason"]
	For $i = 0 To UBound($aFields) - 1
		$oSnapshot.Add($aFields[$i], $oSession.Item($aFields[$i]))
	Next
	Return $oSnapshot
EndFunc   ;==>RunSessionSnapshot
