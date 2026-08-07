; #FUNCTION# ====================================================================================================================
; Name ..........: Battle quota
; Description ...: Tracks how many attacks remain on a specific battle surface.
; Remarks .......: A published maximum is not the player's current remaining count. Surfaces with a finite or UI-reported budget
;                  start unobserved and stay unrunnable until the live remaining count has actually been read from the client.
; ===============================================================================================================================
#include-once
#include "..\Game\GameCatalog.au3"

Func BattleQuotaCreate($sSurfaceId)
	Local $iIndex = CurrentGameFindBattleSurface($sSurfaceId)
	If $iIndex < 0 Then Return SetError(1, 0, 0)

	Local $oQuota = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oQuota) Then Return SetError(2, 0, 0)

	Local $sKind = StringLower($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleBudgetKind])
	Local $iPublished = Int($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleBudgetValue])

	$oQuota.CompareMode = 1
	$oQuota.Add("schema_version", 1)
	$oQuota.Add("surface_id", $g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleId])
	$oQuota.Add("kind", $sKind)
	$oQuota.Add("unit", $g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleBudgetUnit])
	$oQuota.Add("published_maximum", $iPublished)
	$oQuota.Add("verified", ($sKind = "unlimited"))
	$oQuota.Add("remaining", -1)
	$oQuota.Add("observed_at_ms", -1)
	$oQuota.Add("consumed", 0)
	Return $oQuota
EndFunc   ;==>BattleQuotaCreate

Func BattleQuotaValidate(ByRef $oQuota, ByRef $sError)
	$sError = ""
	If Not IsObj($oQuota) Then
		$sError = "Battle quota is not an object"
		Return SetError(1, 0, False)
	EndIf

	Local $aRequired = ["schema_version", "surface_id", "kind", "unit", "published_maximum", "verified", "remaining", "observed_at_ms", "consumed"]
	For $i = 0 To UBound($aRequired) - 1
		If Not $oQuota.Exists($aRequired[$i]) Then
			$sError = "Missing battle quota field: " & $aRequired[$i]
			Return SetError(2, $i, False)
		EndIf
	Next

	Switch StringLower($oQuota.Item("kind"))
		Case "unlimited", "ui-reported", "fixed", "single-opportunity"
		Case Else
			$sError = "Unsupported attack budget kind: " & $oQuota.Item("kind")
			Return SetError(3, 0, False)
	EndSwitch

	If CurrentGameFindBattleSurface($oQuota.Item("surface_id")) < 0 Then
		$sError = "Unknown battle surface: " & $oQuota.Item("surface_id")
		Return SetError(4, 0, False)
	EndIf
	If Int($oQuota.Item("consumed")) < 0 Then
		$sError = "Consumed attack count cannot be negative"
		Return SetError(5, 0, False)
	EndIf
	If $oQuota.Item("verified") And StringLower($oQuota.Item("kind")) <> "unlimited" And Int($oQuota.Item("remaining")) < 0 Then
		$sError = "A verified finite quota requires an observed remaining count"
		Return SetError(6, 0, False)
	EndIf
	Return True
EndFunc   ;==>BattleQuotaValidate

Func BattleQuotaIsUnlimited(ByRef $oQuota)
	If Not IsObj($oQuota) Then Return SetError(1, 0, False)
	Return StringLower($oQuota.Item("kind")) = "unlimited"
EndFunc   ;==>BattleQuotaIsUnlimited

Func BattleQuotaObserve(ByRef $oQuota, $iRemaining, $iObservedAtMs, ByRef $sError)
	$sError = ""
	If Not BattleQuotaValidate($oQuota, $sError) Then Return SetError(1, 0, False)
	If BattleQuotaIsUnlimited($oQuota) Then
		$sError = "An unlimited surface has no remaining count to observe"
		Return SetError(2, 0, False)
	EndIf
	$iRemaining = Int($iRemaining)
	If $iRemaining < 0 Then
		$sError = "Observed remaining attacks cannot be negative"
		Return SetError(3, 0, False)
	EndIf

	Local $iPublished = Int($oQuota.Item("published_maximum"))
	If $iPublished > 0 And $iRemaining > $iPublished Then
		$sError = "Observed remaining attacks (" & $iRemaining & ") exceed the published maximum of " & $iPublished
		Return SetError(4, 0, False)
	EndIf

	$oQuota.Item("remaining") = $iRemaining
	$oQuota.Item("observed_at_ms") = Int($iObservedAtMs)
	$oQuota.Item("verified") = True
	Return True
EndFunc   ;==>BattleQuotaObserve

Func BattleQuotaInvalidate(ByRef $oQuota, $sReason = "")
	If Not IsObj($oQuota) Then Return SetError(1, 0, False)
	If BattleQuotaIsUnlimited($oQuota) Then Return True
	$oQuota.Item("verified") = False
	$oQuota.Item("remaining") = -1
	$oQuota.Item("observed_at_ms") = -1
	Return True
EndFunc   ;==>BattleQuotaInvalidate

Func BattleQuotaCanConsume(ByRef $oQuota, ByRef $sReason)
	$sReason = ""
	If Not BattleQuotaValidate($oQuota, $sReason) Then Return False
	If BattleQuotaIsUnlimited($oQuota) Then Return True
	If Not $oQuota.Item("verified") Then
		$sReason = "Remaining attacks for " & $oQuota.Item("surface_id") & " have not been read from the client yet"
		Return False
	EndIf
	If Int($oQuota.Item("remaining")) <= 0 Then
		$sReason = "No attacks remain on " & $oQuota.Item("surface_id")
		Return False
	EndIf
	Return True
EndFunc   ;==>BattleQuotaCanConsume

Func BattleQuotaConsume(ByRef $oQuota, ByRef $sError)
	$sError = ""
	If Not BattleQuotaCanConsume($oQuota, $sError) Then Return SetError(1, 0, False)
	$oQuota.Item("consumed") = Int($oQuota.Item("consumed")) + 1
	If Not BattleQuotaIsUnlimited($oQuota) Then
		$oQuota.Item("remaining") = Int($oQuota.Item("remaining")) - 1
	EndIf
	Return True
EndFunc   ;==>BattleQuotaConsume

Func BattleQuotaIsExhausted(ByRef $oQuota)
	Local $sError
	If Not BattleQuotaValidate($oQuota, $sError) Then Return SetError(1, 0, True)
	If BattleQuotaIsUnlimited($oQuota) Then Return False
	If Not $oQuota.Item("verified") Then Return False
	Return Int($oQuota.Item("remaining")) <= 0
EndFunc   ;==>BattleQuotaIsExhausted

Func BattleQuotaRemaining(ByRef $oQuota)
	If Not IsObj($oQuota) Then Return SetError(1, 0, -1)
	If BattleQuotaIsUnlimited($oQuota) Then Return -1
	If Not $oQuota.Item("verified") Then Return -1
	Return Int($oQuota.Item("remaining"))
EndFunc   ;==>BattleQuotaRemaining

Func BattleQuotaDescribe(ByRef $oQuota)
	Local $sError
	If Not BattleQuotaValidate($oQuota, $sError) Then Return SetError(1, 0, $sError)
	If BattleQuotaIsUnlimited($oQuota) Then Return "Unlimited attacks"
	If Not $oQuota.Item("verified") Then
		Local $sPublished = ""
		If Int($oQuota.Item("published_maximum")) > 0 Then $sPublished = " (published maximum " & Int($oQuota.Item("published_maximum")) & " " & $oQuota.Item("unit") & ")"
		Return "Remaining attacks not yet read from the client" & $sPublished
	EndIf
	Return Int($oQuota.Item("remaining")) & " attacks remaining, " & Int($oQuota.Item("consumed")) & " used this session"
EndFunc   ;==>BattleQuotaDescribe
