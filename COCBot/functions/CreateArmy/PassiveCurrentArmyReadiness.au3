; #FUNCTION# ====================================================================================================================
; Name ..........: PassiveCurrentArmyReadiness
; Description ...: Pure validation helpers for a planned one-shot that preserves the army already trained in game.
; Remarks .......: This file is part of MyBot, previously known as ClashGameBot. Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
; ===============================================================================================================================
#include-once

Func PassiveCurrentArmyRequirementsSupported($iHeroWaitMask, $bWaitForSpells, $bWaitForSieges, ByRef $sError)
	$sError = ""
	If Int($iHeroWaitMask) <> 0 Then
		$sError = "selected Heroes cannot be proved without Hero Hall/building location"
		Return False
	EndIf
	If $bWaitForSpells Then
		$sError = "spell readiness is not available in passive current-army mode"
		Return False
	EndIf
	If $bWaitForSieges Then
		$sError = "siege readiness is not available in passive current-army mode"
		Return False
	EndIf
	Return True
EndFunc   ;==>PassiveCurrentArmyRequirementsSupported

Func PassiveCurrentArmyCapacityParse($sObservation, ByRef $iCurrent, ByRef $iTotal, ByRef $sError)
	$iCurrent = 0
	$iTotal = 0
	$sError = ""

	Local $sNormalized = StringStripWS(String($sObservation), 8)
	If StringRegExp($sNormalized, "^[0-9]+#[0-9]+$") <> 1 Then
		$sError = "Army Overview capacity OCR was not a current#total pair"
		Return False
	EndIf

	Local $aCapacity = StringSplit($sNormalized, "#", 2)
	If Not IsArray($aCapacity) Or UBound($aCapacity) <> 2 Then
		$sError = "Army Overview capacity OCR did not contain exactly two values"
		Return False
	EndIf

	$iCurrent = Number($aCapacity[0])
	$iTotal = Number($aCapacity[1])
	If $iTotal < 10 Then
		$sError = "Army Overview total capacity is below the valid minimum"
		Return False
	EndIf
	If Mod($iTotal, 5) <> 0 Then
		$sError = "Army Overview total capacity is not a multiple of five"
		Return False
	EndIf
	Return True
EndFunc   ;==>PassiveCurrentArmyCapacityParse

Func PassiveCurrentArmyCapacityReady($iCurrent, $iTotal, ByRef $sError)
	$sError = ""
	If $iTotal < 10 Or Mod($iTotal, 5) <> 0 Then
		$sError = "Army Overview total capacity is invalid"
		Return False
	EndIf
	If $iCurrent <= 0 Or $iCurrent < $iTotal Then
		$sError = "current army is not full (" & $iCurrent & "/" & $iTotal & ")"
		Return False
	EndIf
	Return True
EndFunc   ;==>PassiveCurrentArmyCapacityReady

Func PassiveCurrentArmyCapacityProof($sFirstObservation, $sSecondObservation, ByRef $iCurrent, ByRef $iTotal, ByRef $sError)
	$iCurrent = 0
	$iTotal = 0
	$sError = ""

	Local $iFirstCurrent = 0, $iFirstTotal = 0
	If Not PassiveCurrentArmyCapacityParse($sFirstObservation, $iFirstCurrent, $iFirstTotal, $sError) Then Return False
	If Not PassiveCurrentArmyCapacityParse($sSecondObservation, $iCurrent, $iTotal, $sError) Then Return False

	If $iFirstCurrent <> $iCurrent Or $iFirstTotal <> $iTotal Then
		$sError = "two consecutive Army Overview capacity observations did not match"
		Return False
	EndIf

	Return PassiveCurrentArmyCapacityReady($iCurrent, $iTotal, $sError)
EndFunc   ;==>PassiveCurrentArmyCapacityProof
