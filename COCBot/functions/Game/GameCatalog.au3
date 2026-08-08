; #FUNCTION# ====================================================================================================================
; Name ..........: Current game catalog
; Description ...: Query and validate the generated current-client source model.
; Remarks .......: Recognition and execution remain closed until evidence changes the generated status fields to verified.
; ===============================================================================================================================
#include-once
#include "GameCatalog.generated.au3"

Func _CurrentGameNormalizeId($sValue)
	Return StringLower(StringStripWS(String($sValue), 3))
EndFunc   ;==>_CurrentGameNormalizeId

Func _CurrentGameFindRow(ByRef $aTable, $iIdColumn, $sId)
	Local $sNeedle = _CurrentGameNormalizeId($sId)
	If $sNeedle = "" Then Return SetError(1, 0, -1)
	For $i = 0 To UBound($aTable, 1) - 1
		If _CurrentGameNormalizeId($aTable[$i][$iIdColumn]) = $sNeedle Then Return $i
	Next
	Return SetError(2, 0, -1)
EndFunc   ;==>_CurrentGameFindRow

Func _CurrentGameValidateUniqueIds(ByRef $aTable, $iIdColumn, $sLabel, ByRef $sError)
	For $i = 0 To UBound($aTable, 1) - 1
		Local $sId = _CurrentGameNormalizeId($aTable[$i][$iIdColumn])
		If $sId = "" Then
			$sError = $sLabel & " contains an empty identifier at row " & $i
			Return False
		EndIf
		For $j = $i + 1 To UBound($aTable, 1) - 1
			If _CurrentGameNormalizeId($aTable[$j][$iIdColumn]) = $sId Then
				$sError = $sLabel & " contains a duplicate identifier: " & $sId
				Return False
			EndIf
		Next
	Next
	Return True
EndFunc   ;==>_CurrentGameValidateUniqueIds

Func CurrentGameFindSource($sSourceId)
	Return _CurrentGameFindRow($g_aCurrentGameSources, $eGameSourceId, $sSourceId)
EndFunc   ;==>CurrentGameFindSource

Func CurrentGameSourceUrl($sSourceId)
	Local $iIndex = CurrentGameFindSource($sSourceId)
	If $iIndex < 0 Then Return SetError(1, 0, "")
	Return $g_aCurrentGameSources[$iIndex][$eGameSourceUrl]
EndFunc   ;==>CurrentGameSourceUrl

Func CurrentGameFindHero($sHeroId)
	Return _CurrentGameFindRow($g_aCurrentGameHeroes, $eGameHeroId, $sHeroId)
EndFunc   ;==>CurrentGameFindHero

Func CurrentGameGetHeroUnlockTH($sHeroId)
	Local $iIndex = CurrentGameFindHero($sHeroId)
	If $iIndex < 0 Then Return SetError(1, 0, -1)
	Return Int($g_aCurrentGameHeroes[$iIndex][$eGameHeroUnlockTownHall])
EndFunc   ;==>CurrentGameGetHeroUnlockTH

Func CurrentGameHeroIsUnlocked($sHeroId, $iTownHall)
	Local $iUnlockTownHall = CurrentGameGetHeroUnlockTH($sHeroId)
	If @error Then Return SetError(1, 0, False)
	Return Int($iTownHall) >= $iUnlockTownHall
EndFunc   ;==>CurrentGameHeroIsUnlocked

Func CurrentGameHeroMovement($sHeroId)
	Local $iIndex = CurrentGameFindHero($sHeroId)
	If $iIndex < 0 Then Return SetError(1, 0, "")
	Return $g_aCurrentGameHeroes[$iIndex][$eGameHeroMovement]
EndFunc   ;==>CurrentGameHeroMovement

Func CurrentGameFindGuardian($sGuardianId)
	Return _CurrentGameFindRow($g_aCurrentGameGuardians, $eGameGuardianId, $sGuardianId)
EndFunc   ;==>CurrentGameFindGuardian

Func CurrentGameGuardianRequiresBuilder($sGuardianId)
	Local $iIndex = CurrentGameFindGuardian($sGuardianId)
	If $iIndex < 0 Then Return SetError(1, 0, False)
	Return $g_aCurrentGameGuardians[$iIndex][$eGameGuardianBuilderRequired]
EndFunc   ;==>CurrentGameGuardianRequiresBuilder

Func CurrentGameGuardianUnavailableWhileUpgrading($sGuardianId)
	Local $iIndex = CurrentGameFindGuardian($sGuardianId)
	If $iIndex < 0 Then Return SetError(1, 0, False)
	Return $g_aCurrentGameGuardians[$iIndex][$eGameGuardianUnavailableWhileUpgrading]
EndFunc   ;==>CurrentGameGuardianUnavailableWhileUpgrading

Func CurrentGameFindBattleSurface($sSurfaceId)
	Return _CurrentGameFindRow($g_aCurrentGameBattleSurfaces, $eGameBattleId, $sSurfaceId)
EndFunc   ;==>CurrentGameFindBattleSurface

Func CurrentGameGetBattleMinimumTH($sSurfaceId)
	Local $iIndex = CurrentGameFindBattleSurface($sSurfaceId)
	If $iIndex < 0 Then Return SetError(1, 0, -1)
	Return Int($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleMinimumTownHall])
EndFunc   ;==>CurrentGameGetBattleMinimumTH

Func CurrentGameGetBattleAttackBudget($sSurfaceId, ByRef $sKind, ByRef $iValue, ByRef $sUnit)
	$sKind = ""
	$iValue = -1
	$sUnit = ""
	Local $iIndex = CurrentGameFindBattleSurface($sSurfaceId)
	If $iIndex < 0 Then Return SetError(1, 0, False)
	$sKind = $g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleBudgetKind]
	$iValue = Int($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleBudgetValue])
	$sUnit = $g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleBudgetUnit]
	Return True
EndFunc   ;==>CurrentGameGetBattleAttackBudget

Func CurrentGameBattleSurfaceReady($sSurfaceId, ByRef $sReason)
	$sReason = ""
	Local $iIndex = CurrentGameFindBattleSurface($sSurfaceId)
	If $iIndex < 0 Then
		$sReason = "Unknown battle surface: " & $sSurfaceId
		Return SetError(1, 0, False)
	EndIf
	If StringLower($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleRecognitionStatus]) <> "verified" Then
		$sReason = "Recognition is not verified for " & $sSurfaceId
		Return False
	EndIf
	If StringLower($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleExecutionStatus]) <> "verified" Then
		$sReason = "Execution is not verified for " & $sSurfaceId
		Return False
	EndIf
	$sReason = ""
	Return True
EndFunc   ;==>CurrentGameBattleSurfaceReady

Func CurrentGameCatalogValidate(ByRef $sError)
	$sError = ""
	If $CURRENT_GAME_SCHEMA_VERSION <> 1 Then
		$sError = "Unsupported current-game schema version"
		Return SetError(1, 0, False)
	EndIf
	If $CURRENT_GAME_MAX_TOWN_HALL <> 18 Then
		$sError = "Expected Town Hall 18 as the current maximum"
		Return SetError(2, 0, False)
	EndIf
	If $CURRENT_GAME_HOME_HERO_COUNT <> 6 Or $CURRENT_GAME_MAX_ACTIVE_HERO_SLOTS <> 4 Then
		$sError = "Expected six Home Village Heroes and four active slots"
		Return SetError(3, 0, False)
	EndIf
	If UBound($g_aCurrentGameHeroes, 1) <> $CURRENT_GAME_HOME_HERO_COUNT Then
		$sError = "Generated Hero row count does not match the current-client constant"
		Return SetError(4, 0, False)
	EndIf
	If $CURRENT_GAME_GUARDIAN_COUNT <> 3 Or $CURRENT_GAME_MAX_ACTIVE_GUARDIANS <> 1 Or UBound($g_aCurrentGameGuardians, 1) <> $CURRENT_GAME_GUARDIAN_COUNT Then
		$sError = "Expected three Guardians and one active slot"
		Return SetError(5, 0, False)
	EndIf
	If Not _CurrentGameValidateUniqueIds($g_aCurrentGameSources, $eGameSourceId, "Source catalog", $sError) Then Return SetError(5, 0, False)
	If Not _CurrentGameValidateUniqueIds($g_aCurrentGameHeroes, $eGameHeroId, "Hero catalog", $sError) Then Return SetError(6, 0, False)
	If Not _CurrentGameValidateUniqueIds($g_aCurrentGameGuardians, $eGameGuardianId, "Guardian catalog", $sError) Then Return SetError(7, 0, False)
	If Not _CurrentGameValidateUniqueIds($g_aCurrentGameBattleSurfaces, $eGameBattleId, "Battle surface catalog", $sError) Then Return SetError(8, 0, False)
	If Not _CurrentGameValidateUniqueIds($g_aCurrentGameScreenStates, $eGameScreenId, "Screen-state catalog", $sError) Then Return SetError(9, 0, False)

	For $i = 0 To UBound($g_aCurrentGameHeroes, 1) - 1
		If Int($g_aCurrentGameHeroes[$i][$eGameHeroUnlockTownHall]) < 1 Or Int($g_aCurrentGameHeroes[$i][$eGameHeroUnlockTownHall]) > $CURRENT_GAME_MAX_TOWN_HALL Then
			$sError = "Hero unlock Town Hall is outside the current range: " & $g_aCurrentGameHeroes[$i][$eGameHeroId]
			Return SetError(9, $i, False)
		EndIf
		If CurrentGameFindSource($g_aCurrentGameHeroes[$i][$eGameHeroSourceId]) < 0 Then
			$sError = "Hero references an unknown source: " & $g_aCurrentGameHeroes[$i][$eGameHeroId]
			Return SetError(10, $i, False)
		EndIf
		If StringStripWS($g_aCurrentGameHeroes[$i][$eGameHeroFixtureIds], 8) = "" Then
			$sError = "Hero has no fixture requirement: " & $g_aCurrentGameHeroes[$i][$eGameHeroId]
			Return SetError(11, $i, False)
		EndIf
	Next

	For $i = 0 To UBound($g_aCurrentGameGuardians, 1) - 1
		If Int($g_aCurrentGameGuardians[$i][$eGameGuardianUnlockTownHall]) <> 18 Then
			$sError = "Guardian unlock Town Hall must be 18: " & $g_aCurrentGameGuardians[$i][$eGameGuardianId]
			Return SetError(12, $i, False)
		EndIf
		If CurrentGameFindSource($g_aCurrentGameGuardians[$i][$eGameGuardianSourceId]) < 0 Then
			$sError = "Guardian references an unknown source: " & $g_aCurrentGameGuardians[$i][$eGameGuardianId]
			Return SetError(13, $i, False)
		EndIf
		If Not $g_aCurrentGameGuardians[$i][$eGameGuardianBuilderRequired] Or Not $g_aCurrentGameGuardians[$i][$eGameGuardianUnavailableWhileUpgrading] Or Not $g_aCurrentGameGuardians[$i][$eGameGuardianCompletedLevelDefends] Then
			$sError = "Guardian upgrade safety contract is incomplete: " & $g_aCurrentGameGuardians[$i][$eGameGuardianId]
			Return SetError(14, $i, False)
		EndIf
		If StringStripWS($g_aCurrentGameGuardians[$i][$eGameGuardianFixtureIds], 8) = "" Then
			$sError = "Guardian has no fixture requirement: " & $g_aCurrentGameGuardians[$i][$eGameGuardianId]
			Return SetError(15, $i, False)
		EndIf
	Next

	For $i = 0 To UBound($g_aCurrentGameBattleSurfaces, 1) - 1
		If CurrentGameFindSource($g_aCurrentGameBattleSurfaces[$i][$eGameBattleSourceId]) < 0 Then
			$sError = "Battle surface references an unknown source: " & $g_aCurrentGameBattleSurfaces[$i][$eGameBattleId]
			Return SetError(12, $i, False)
		EndIf
		If $g_aCurrentGameBattleSurfaces[$i][$eGameBattleLegacyFallbackAllowed] Then
			$sError = "Current battle surface enables legacy fallback: " & $g_aCurrentGameBattleSurfaces[$i][$eGameBattleId]
			Return SetError(13, $i, False)
		EndIf
		Switch StringLower($g_aCurrentGameBattleSurfaces[$i][$eGameBattleRecognitionStatus])
			Case "fixture-required", "verified"
			Case Else
				$sError = "Invalid battle recognition status: " & $g_aCurrentGameBattleSurfaces[$i][$eGameBattleId]
				Return SetError(14, $i, False)
		EndSwitch
		Switch StringLower($g_aCurrentGameBattleSurfaces[$i][$eGameBattleExecutionStatus])
			Case "blocked", "not-implemented", "verified"
			Case Else
				$sError = "Invalid battle execution status: " & $g_aCurrentGameBattleSurfaces[$i][$eGameBattleId]
				Return SetError(15, $i, False)
		EndSwitch
	Next

	For $i = 0 To UBound($g_aCurrentGameScreenStates, 1) - 1
		If CurrentGameFindSource($g_aCurrentGameScreenStates[$i][$eGameScreenSourceId]) < 0 Then
			$sError = "Screen state references an unknown source: " & $g_aCurrentGameScreenStates[$i][$eGameScreenId]
			Return SetError(16, $i, False)
		EndIf
		If Int($g_aCurrentGameScreenStates[$i][$eGameScreenRetryLimit]) < 0 Or Int($g_aCurrentGameScreenStates[$i][$eGameScreenRetryLimit]) > 10 Then
			$sError = "Screen-state retry limit is outside the allowed range: " & $g_aCurrentGameScreenStates[$i][$eGameScreenId]
			Return SetError(17, $i, False)
		EndIf
		If StringStripWS($g_aCurrentGameScreenStates[$i][$eGameScreenFixtureIds], 8) = "" Then
			$sError = "Screen state has no fixture requirement: " & $g_aCurrentGameScreenStates[$i][$eGameScreenId]
			Return SetError(18, $i, False)
		EndIf
	Next

	Return True
EndFunc   ;==>CurrentGameCatalogValidate
