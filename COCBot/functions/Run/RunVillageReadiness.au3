; #FUNCTION# ====================================================================================================================
; Name ..........: Run village readiness
; Description ...: Pure fail-closed validation for the own-village identity a planned run is about to automate.
; Remarks .......: Detection remains the inherited engine's responsibility. This contract only decides whether its result is
;                  safe to use, and deliberately performs no profile writes.
; ===============================================================================================================================
#include-once

; The identity latch is deliberately process-local and tied to the detected level. A saved profile
; level or an old building coordinate can never make it true. BotDetectFirstTime resets it before
; every planned preflight and marks it only after a fresh Town Hall template match on a proven main
; screen.
Global $g_iRunVillageReadinessIdentityLevel = 0
Global $g_sRunVillageReadinessIdentitySource = ""

Func RunVillageReadinessResetIdentity()
	$g_iRunVillageReadinessIdentityLevel = 0
	$g_sRunVillageReadinessIdentitySource = ""
EndFunc   ;==>RunVillageReadinessResetIdentity

Func RunVillageReadinessMarkIdentityVerified($iTownHallLevel)
	RunVillageReadinessResetIdentity()
	Local $iLevel = Int(Number($iTownHallLevel))
	If $iLevel < 2 Then Return SetError(1, 0, False)
	$g_iRunVillageReadinessIdentityLevel = $iLevel
	$g_sRunVillageReadinessIdentitySource = "template"
	Return True
EndFunc   ;==>RunVillageReadinessMarkIdentityVerified

; A current-army one-shot never consumes own-building coordinates. When its current main screen is
; freshly proven but the visual Town Hall template misses (for example immediately after a client
; recovery or camera change), it may attest the loaded profile level within the supported range.
; Building-managing runs never call this fallback and still require a fresh template match.
Func RunVillageReadinessMarkMainScreenProfileAttested($iTownHallLevel, $iMaxTownHallLevel)
	RunVillageReadinessResetIdentity()
	Local $iLevel = Int(Number($iTownHallLevel))
	Local $iMaximum = Int(Number($iMaxTownHallLevel))
	If $iMaximum < 2 Or $iLevel < 2 Or $iLevel > $iMaximum Then Return SetError(1, 0, False)
	$g_iRunVillageReadinessIdentityLevel = $iLevel
	$g_sRunVillageReadinessIdentitySource = "main-screen-profile"
	Return True
EndFunc   ;==>RunVillageReadinessMarkMainScreenProfileAttested

Func RunVillageReadinessIdentityVerified($iTownHallLevel)
	Local $iLevel = Int(Number($iTownHallLevel))
	Return $iLevel >= 2 And $g_iRunVillageReadinessIdentityLevel = $iLevel And $g_sRunVillageReadinessIdentitySource <> ""
EndFunc   ;==>RunVillageReadinessIdentityVerified

Func RunVillageReadinessIdentitySource()
	Return $g_sRunVillageReadinessIdentitySource
EndFunc   ;==>RunVillageReadinessIdentitySource

Func RunVillageReadinessValidate($iTownHallLevel, $bTownHallCoordinatesValid, $iMaxTownHallLevel, ByRef $sError, _
		$bTownHallIdentityVerified = False, $bTownHallCoordinatesRequired = True, $iPlannedTownHall = 0, $sIdentitySource = "")
	$sError = ""
	Local $iLevel = Int(Number($iTownHallLevel))
	Local $iMaximum = Int(Number($iMaxTownHallLevel))

	If $iMaximum < 2 Then
		$sError = "the engine Town Hall support range is unavailable"
		Return SetError(1, 0, False)
	EndIf
	If $iLevel < 2 Then
		$sError = "the own-village Town Hall level was not detected; locate the Town Hall and retry"
		Return SetError(2, 0, False)
	EndIf
	If $iLevel > $iMaximum Then
		$sError = "own-village TH" & $iLevel & " exceeds this engine's supported maximum TH" & $iMaximum
		Return SetError(3, 0, False)
	EndIf
	If Not $bTownHallIdentityVerified Then
		$sError = "the own-village Town Hall identity was not freshly verified on the current main screen"
		Return SetError(4, 0, False)
	EndIf
	If $bTownHallCoordinatesRequired And Not $bTownHallCoordinatesValid Then
		$sError = "the own-village Town Hall coordinates are invalid; locate the Town Hall and retry"
		Return SetError(5, 0, False)
	EndIf
	Local $iPlanned = Int(Number($iPlannedTownHall))
	If $iPlanned > 0 Then
		If $sIdentitySource <> "template" Then
			$sError = "the planned Town Hall requires a fresh own-village template detection before Start"
			Return SetError(6, 0, False)
		EndIf
		If $iLevel <> $iPlanned Then
			$sError = "planned TH" & $iPlanned & " does not match freshly detected own-village TH" & $iLevel
			Return SetError(7, 0, False)
		EndIf
	EndIf
	Return True
EndFunc   ;==>RunVillageReadinessValidate
