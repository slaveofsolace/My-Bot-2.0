; #FUNCTION# ====================================================================================================================
; Name ..........: Current screen-state registry
; Description ...: Query current-client screens and enforce evidence-closed handler readiness.
; ===============================================================================================================================
#include-once
#include "GameCatalog.au3"

Func CurrentGameFindScreenState($sStateId)
	Return _CurrentGameFindRow($g_aCurrentGameScreenStates, $eGameScreenId, $sStateId)
EndFunc   ;==>CurrentGameFindScreenState

Func CurrentGameScreenCanHandle($sStateId, ByRef $sReason)
	$sReason = ""
	Local $iIndex = CurrentGameFindScreenState($sStateId)
	If $iIndex < 0 Then
		$sReason = "Unknown screen state: " & $sStateId
		Return SetError(1, 0, False)
	EndIf
	If StringLower($g_aCurrentGameScreenStates[$iIndex][$eGameScreenRecognitionStatus]) <> "verified" Then
		$sReason = "Recognition is not verified for " & $sStateId
		Return False
	EndIf
	If StringLower($g_aCurrentGameScreenStates[$iIndex][$eGameScreenHandlerStatus]) <> "verified" Then
		$sReason = "Handler is not verified for " & $sStateId
		Return False
	EndIf
	Return True
EndFunc   ;==>CurrentGameScreenCanHandle

Func CurrentGameScreenDefaultAction($sStateId)
	Local $iIndex = CurrentGameFindScreenState($sStateId)
	If $iIndex < 0 Then Return SetError(1, 0, "stop-route")
	Return $g_aCurrentGameScreenStates[$iIndex][$eGameScreenSafeDefaultAction]
EndFunc   ;==>CurrentGameScreenDefaultAction

Func CurrentGameScreenIsBlocking($sStateId)
	Local $iIndex = CurrentGameFindScreenState($sStateId)
	If $iIndex < 0 Then Return SetError(1, 0, True)
	Return ($g_aCurrentGameScreenStates[$iIndex][$eGameScreenBlocking] = True)
EndFunc   ;==>CurrentGameScreenIsBlocking

Func CurrentGameScreenRetryLimit($sStateId)
	Local $iIndex = CurrentGameFindScreenState($sStateId)
	If $iIndex < 0 Then Return SetError(1, 0, 0)
	Return Int($g_aCurrentGameScreenStates[$iIndex][$eGameScreenRetryLimit])
EndFunc   ;==>CurrentGameScreenRetryLimit

Func CurrentGameScreenAppearsAfterSeconds($sStateId)
	Local $iIndex = CurrentGameFindScreenState($sStateId)
	If $iIndex < 0 Then Return SetError(1, 0, -1)
	Return Int($g_aCurrentGameScreenStates[$iIndex][$eGameScreenAppearsAfterSeconds])
EndFunc   ;==>CurrentGameScreenAppearsAfterSeconds

Func CurrentGameScreenSpeedMultiplier($sStateId)
	Local $iIndex = CurrentGameFindScreenState($sStateId)
	If $iIndex < 0 Then Return SetError(1, 0, -1)
	Return Int($g_aCurrentGameScreenStates[$iIndex][$eGameScreenSpeedMultiplier])
EndFunc   ;==>CurrentGameScreenSpeedMultiplier

Func CurrentGameScreenShouldStopRoute($sStateId)
	Local $iIndex = CurrentGameFindScreenState($sStateId)
	If $iIndex < 0 Then Return True
	Local $sReason
	If CurrentGameScreenCanHandle($sStateId, $sReason) Then Return False
	Return StringLower($g_aCurrentGameScreenStates[$iIndex][$eGameScreenSafeDefaultAction]) = "stop-route"
EndFunc   ;==>CurrentGameScreenShouldStopRoute
