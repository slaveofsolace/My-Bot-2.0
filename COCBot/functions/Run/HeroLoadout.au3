; #FUNCTION# ====================================================================================================================
; Name ..........: Hero loadout
; Description ...: Selects the active Heroes for a run from the current six-Hero catalog.
; Remarks .......: The Hero Hall holds six Heroes but only four may be active at once, so the loadout is a bounded selection
;                  rather than a fixed array. Membership is checked against the generated catalog, never against a hard-coded list.
; ===============================================================================================================================
#include-once
#include "..\Game\GameCatalog.au3"

Global Const $HERO_LOADOUT_SEPARATOR = "|"

Func HeroLoadoutCreate($iTownHall = 0)
	Local $oLoadout = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oLoadout) Then Return SetError(1, 0, 0)
	$oLoadout.CompareMode = 1
	$oLoadout.Add("schema_version", 1)
	$oLoadout.Add("town_hall", Int($iTownHall))
	$oLoadout.Add("hero_ids", "")
	$oLoadout.Add("count", 0)
	$oLoadout.Add("max_slots", $CURRENT_GAME_MAX_ACTIVE_HERO_SLOTS)
	Return $oLoadout
EndFunc   ;==>HeroLoadoutCreate

Func HeroLoadoutValidate(ByRef $oLoadout, ByRef $sError)
	$sError = ""
	If Not IsObj($oLoadout) Then
		$sError = "Hero loadout is not an object"
		Return SetError(1, 0, False)
	EndIf

	Local $aRequired = ["schema_version", "town_hall", "hero_ids", "count", "max_slots"]
	For $i = 0 To UBound($aRequired) - 1
		If Not $oLoadout.Exists($aRequired[$i]) Then
			$sError = "Missing hero loadout field: " & $aRequired[$i]
			Return SetError(2, $i, False)
		EndIf
	Next

	Local $iMax = Int($oLoadout.Item("max_slots"))
	If $iMax < 1 Or $iMax > $CURRENT_GAME_HOME_HERO_COUNT Then
		$sError = "Hero loadout slot count is outside the current range"
		Return SetError(3, 0, False)
	EndIf

	Local $iTownHall = Int($oLoadout.Item("town_hall"))
	If $iTownHall < 0 Or $iTownHall > $CURRENT_GAME_MAX_TOWN_HALL Then
		$sError = "Town Hall level is outside the current range"
		Return SetError(4, 0, False)
	EndIf

	Local $aIds = HeroLoadoutIds($oLoadout)
	If UBound($aIds) <> Int($oLoadout.Item("count")) Then
		$sError = "Hero loadout count does not match its selection"
		Return SetError(5, 0, False)
	EndIf
	If UBound($aIds) > $iMax Then
		$sError = "Hero loadout exceeds " & $iMax & " active slots"
		Return SetError(6, 0, False)
	EndIf

	For $i = 0 To UBound($aIds) - 1
		If CurrentGameFindHero($aIds[$i]) < 0 Then
			$sError = "Unknown Hero in loadout: " & $aIds[$i]
			Return SetError(7, $i, False)
		EndIf
		For $j = $i + 1 To UBound($aIds) - 1
			If $aIds[$i] = $aIds[$j] Then
				$sError = "Duplicate Hero in loadout: " & $aIds[$i]
				Return SetError(8, $i, False)
			EndIf
		Next
		If $iTownHall > 0 And Not CurrentGameHeroIsUnlocked($aIds[$i], $iTownHall) Then
			$sError = $aIds[$i] & " is not unlocked at Town Hall " & $iTownHall
			Return SetError(9, $i, False)
		EndIf
	Next

	Return True
EndFunc   ;==>HeroLoadoutValidate

Func HeroLoadoutIds(ByRef $oLoadout)
	Local $aEmpty[0]
	If Not IsObj($oLoadout) Then Return SetError(1, 0, $aEmpty)
	Local $sIds = StringStripWS($oLoadout.Item("hero_ids"), $STR_STRIPALL)
	If $sIds = "" Then Return $aEmpty
	Return StringSplit($sIds, $HERO_LOADOUT_SEPARATOR, $STR_NOCOUNT)
EndFunc   ;==>HeroLoadoutIds

Func HeroLoadoutCount(ByRef $oLoadout)
	If Not IsObj($oLoadout) Then Return SetError(1, 0, 0)
	Return Int($oLoadout.Item("count"))
EndFunc   ;==>HeroLoadoutCount

Func HeroLoadoutContains(ByRef $oLoadout, $sHeroId)
	Local $aIds = HeroLoadoutIds($oLoadout)
	$sHeroId = _CurrentGameNormalizeId($sHeroId)
	For $i = 0 To UBound($aIds) - 1
		If _CurrentGameNormalizeId($aIds[$i]) = $sHeroId Then Return True
	Next
	Return False
EndFunc   ;==>HeroLoadoutContains

Func HeroLoadoutAdd(ByRef $oLoadout, $sHeroId, ByRef $sError)
	$sError = ""
	If Not HeroLoadoutValidate($oLoadout, $sError) Then Return SetError(1, 0, False)

	$sHeroId = _CurrentGameNormalizeId($sHeroId)
	If $sHeroId = "" Then
		$sError = "Hero identifier cannot be empty"
		Return SetError(2, 0, False)
	EndIf

	Local $iIndex = CurrentGameFindHero($sHeroId)
	If $iIndex < 0 Then
		$sError = "Unknown Hero: " & $sHeroId
		Return SetError(3, 0, False)
	EndIf
	If Not $g_aCurrentGameHeroes[$iIndex][$eGameHeroActiveSlotEligible] Then
		$sError = $sHeroId & " cannot occupy an active Hero slot"
		Return SetError(4, 0, False)
	EndIf
	If HeroLoadoutContains($oLoadout, $sHeroId) Then
		$sError = $sHeroId & " is already selected"
		Return SetError(5, 0, False)
	EndIf
	If Int($oLoadout.Item("count")) >= Int($oLoadout.Item("max_slots")) Then
		$sError = "All " & Int($oLoadout.Item("max_slots")) & " active Hero slots are already filled"
		Return SetError(6, 0, False)
	EndIf

	Local $iTownHall = Int($oLoadout.Item("town_hall"))
	If $iTownHall > 0 And Not CurrentGameHeroIsUnlocked($sHeroId, $iTownHall) Then
		$sError = $sHeroId & " unlocks at Town Hall " & CurrentGameGetHeroUnlockTH($sHeroId)
		Return SetError(7, 0, False)
	EndIf

	Local $sIds = $oLoadout.Item("hero_ids")
	$oLoadout.Item("hero_ids") = (($sIds = "") ? $sHeroId : ($sIds & $HERO_LOADOUT_SEPARATOR & $sHeroId))
	$oLoadout.Item("count") = Int($oLoadout.Item("count")) + 1
	Return True
EndFunc   ;==>HeroLoadoutAdd

Func HeroLoadoutRemove(ByRef $oLoadout, $sHeroId)
	Local $sError
	If Not HeroLoadoutValidate($oLoadout, $sError) Then Return SetError(1, 0, False)
	If Not HeroLoadoutContains($oLoadout, $sHeroId) Then Return SetError(2, 0, False)

	$sHeroId = _CurrentGameNormalizeId($sHeroId)
	Local $aIds = HeroLoadoutIds($oLoadout)
	Local $sKept = ""
	For $i = 0 To UBound($aIds) - 1
		If _CurrentGameNormalizeId($aIds[$i]) = $sHeroId Then ContinueLoop
		$sKept = (($sKept = "") ? $aIds[$i] : ($sKept & $HERO_LOADOUT_SEPARATOR & $aIds[$i]))
	Next
	$oLoadout.Item("hero_ids") = $sKept
	$oLoadout.Item("count") = Int($oLoadout.Item("count")) - 1
	Return True
EndFunc   ;==>HeroLoadoutRemove

Func HeroLoadoutClear(ByRef $oLoadout)
	If Not IsObj($oLoadout) Then Return SetError(1, 0, False)
	$oLoadout.Item("hero_ids") = ""
	$oLoadout.Item("count") = 0
	Return True
EndFunc   ;==>HeroLoadoutClear

Func HeroLoadoutSetTownHall(ByRef $oLoadout, $iTownHall, ByRef $sError)
	$sError = ""
	If Not IsObj($oLoadout) Then
		$sError = "Hero loadout is not an object"
		Return SetError(1, 0, False)
	EndIf
	$iTownHall = Int($iTownHall)
	If $iTownHall < 0 Or $iTownHall > $CURRENT_GAME_MAX_TOWN_HALL Then
		$sError = "Town Hall level is outside the current range"
		Return SetError(2, 0, False)
	EndIf

	; Dropping to a lower Town Hall can invalidate an existing selection, so locked Heroes are released here
	; instead of failing validation later with a selection the player cannot actually field.
	Local $aIds = HeroLoadoutIds($oLoadout)
	Local $sKept = "", $iKept = 0
	For $i = 0 To UBound($aIds) - 1
		If $iTownHall > 0 And Not CurrentGameHeroIsUnlocked($aIds[$i], $iTownHall) Then ContinueLoop
		$sKept = (($sKept = "") ? $aIds[$i] : ($sKept & $HERO_LOADOUT_SEPARATOR & $aIds[$i]))
		$iKept += 1
	Next
	$oLoadout.Item("town_hall") = $iTownHall
	$oLoadout.Item("hero_ids") = $sKept
	$oLoadout.Item("count") = $iKept
	Return True
EndFunc   ;==>HeroLoadoutSetTownHall

Func HeroLoadoutAvailable($iTownHall)
	Local $sAvailable = ""
	For $i = 0 To UBound($g_aCurrentGameHeroes, 1) - 1
		If Not $g_aCurrentGameHeroes[$i][$eGameHeroActiveSlotEligible] Then ContinueLoop
		If $iTownHall > 0 And Int($g_aCurrentGameHeroes[$i][$eGameHeroUnlockTownHall]) > $iTownHall Then ContinueLoop
		$sAvailable = (($sAvailable = "") ? $g_aCurrentGameHeroes[$i][$eGameHeroId] : ($sAvailable & $HERO_LOADOUT_SEPARATOR & $g_aCurrentGameHeroes[$i][$eGameHeroId]))
	Next
	Local $aEmpty[0]
	If $sAvailable = "" Then Return $aEmpty
	Return StringSplit($sAvailable, $HERO_LOADOUT_SEPARATOR, $STR_NOCOUNT)
EndFunc   ;==>HeroLoadoutAvailable

Func HeroLoadoutDescribe(ByRef $oLoadout)
	Local $sError
	If Not HeroLoadoutValidate($oLoadout, $sError) Then Return SetError(1, 0, $sError)
	Local $aIds = HeroLoadoutIds($oLoadout)
	If UBound($aIds) = 0 Then Return "No Heroes selected"
	Local $sDescription = ""
	For $i = 0 To UBound($aIds) - 1
		Local $iIndex = CurrentGameFindHero($aIds[$i])
		Local $sLabel = ($iIndex >= 0) ? $g_aCurrentGameHeroes[$iIndex][$eGameHeroLabel] : $aIds[$i]
		$sDescription &= (($sDescription = "") ? "" : ", ") & $sLabel
	Next
	Return $sDescription & " (" & UBound($aIds) & "/" & Int($oLoadout.Item("max_slots")) & ")"
EndFunc   ;==>HeroLoadoutDescribe
