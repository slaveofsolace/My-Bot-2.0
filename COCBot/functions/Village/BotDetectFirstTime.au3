; #FUNCTION# ====================================================================================================================
; Name ..........: BotDetectFirstTime
; Description ...: This script detects your builings on the first run
; Author ........: HungLe (04/2015)
; Modified ......: Hervidero (05/2015), HungLe (05/2015), KnowJack(07/2015), Sardo (08/2015), CodeSlinger69 (01/2017)
; Remarks .......: This file is part of MyBot, previously known as ClashGameBot. Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
; Related .......:
; Link ..........: https://github.com/MyBotRun/MyBot/wiki
; Example .......: No
; ===============================================================================================================================
#include-once

Func BotDetectFirstTime($bOwnVillageReadinessOnly = False)
	If $bOwnVillageReadinessOnly Then RunVillageReadinessResetIdentity()
	If $g_bIsClientSyncError Then Return ; if restart after OOS, and User stop/start bot, skip this.

	ClearScreen()
	If _Sleep($DELAYBOTDETECT1) Then Return

	SetLog("Detecting your Buildings", $COLOR_INFO)

	If $bOwnVillageReadinessOnly Then
		; Planned Start needs a fresh identity proof, not a desktop mouse coordinate. Current-army
		; mode has no village zoom calibration, so retain the raw framebuffer point only for logging
		; and never pass it through legacy village-coordinate conversion or to a building-click consumer.
		If Not checkMainScreen() Then Return
		If RunExecutionSkipVillageZoomCalibration() Then
			If RunVillageReadinessMarkMainScreenProfileAttested($g_iTownHallLevel, $g_iMaxTHLevel) Then
				SetLog("Bounded planned route verified the Home screen and active-profile TH" & $g_iTownHallLevel & _
						" without protected template recognition", $COLOR_INFO)
			Else
				SetLog("Bounded planned route could not attest the active profile Town Hall", $COLOR_ERROR)
			EndIf
			Return
		EndIf
		Local $iDetectedTownHallLevel = 0
		Local $aRawTownHallPoint[2] = [-1, -1]
		; If the loaded profile has a supported Town Hall, search only that level. A lower-level
		; lookalike elsewhere in the frame must not replace the identity used for Heroes/strategy.
		If Not imglocOwnVillageTownHallIdentity($iDetectedTownHallLevel, $aRawTownHallPoint, True, _
				$g_iTownHallLevel) Then
			; Passive current-army mode is a terminal one-battle path that never uses own-building
			; coordinates. A proven main screen may therefore attest the already loaded profile TH
			; level when the template misses after a camera/client transition. Every other planned
			; mode remains fail-closed on the visual template.
			If RunExecutionSkipVillageZoomCalibration() And _
					RunVillageReadinessMarkMainScreenProfileAttested($g_iTownHallLevel, $g_iMaxTHLevel) Then
				SetLog("Town Hall template missed; current-army one-shot is using main-screen/profile TH" & _
						$g_iTownHallLevel & " attestation without building coordinates", $COLOR_WARNING)
				Return
			EndIf
			SetLog("Own-village Town Hall identity could not be verified on the current main screen", $COLOR_ERROR)
			Return
		EndIf
		$g_iTownHallLevel = $iDetectedTownHallLevel
		RunVillageReadinessMarkIdentityVerified($g_iTownHallLevel)
		SetLog("Own-village identity verified as TH" & $g_iTownHallLevel, $COLOR_SUCCESS)

		If RunExecutionSkipVillageZoomCalibration() Then Return
		If Not isInsideDiamond($g_aiTownHallPos) Then
			; Planned readiness is still pre-session. Never collect, donate, upgrade, or click a
			; building here: Home maintenance must account for every action inside its own route.
			imglocTHSearch(True, True, True)
			SetLog("Townhall: (" & $g_aiTownHallPos[0] & "," & $g_aiTownHallPos[1] & ")", $COLOR_DEBUG)
		EndIf
		Return
	EndIf

	#cs
	If Not isInsideDiamond($g_aiTownHallPos) Then
	checkMainScreen()
	Collect(False)
	_CaptureRegion2()
	; USES OLD OPENCV DETECTION
	Local $PixelTHHere = GetLocationItem("getLocationTownHall")
	If UBound($PixelTHHere) > 0 Then
	Local $pixel = $PixelTHHere[0]
	$g_aiTownHallPos[0] = $pixel[0]
	$g_aiTownHallPos[1] = $pixel[1]
	SetDebugLog("DLLc# Townhall: (" & $g_aiTownHallPos[0] & "," & $g_aiTownHallPos[1] & ")", $COLOR_ERROR)
	EndIf
	If $g_aiTownHallPos[1] = "" Or $g_aiTownHallPos[1] = -1 Then
	imglocTHSearch(True, True) ; search th on myvillage
	$g_aiTownHallPos[0] = $g_iTHx
	$g_aiTownHallPos[1] = $g_iTHy
	SetDebugLog("OldDDL Townhall: (" & $g_aiTownHallPos[0] & "," & $g_aiTownHallPos[1] & ")", $COLOR_ERROR)
	EndIf
	SetLog("Townhall: (" & $g_aiTownHallPos[0] & "," & $g_aiTownHallPos[1] & ")", $COLOR_DEBUG)
	EndIf
	#ce

	If Not isInsideDiamond($g_aiTownHallPos) Then
		checkMainScreen()
		Collect(False)
		imglocTHSearch(True, True, True) ; search th on myvillage
		SetLog("Townhall: (" & $g_aiTownHallPos[0] & "," & $g_aiTownHallPos[1] & ")", $COLOR_DEBUG)
	EndIf

	If Number($g_iTownHallLevel) < 2 Or Number($g_iTownHallLevel) > $g_iMaxTHLevel Then
		Local $aTownHallLevel = GetTownHallLevel(True) ; Get the Users TH level
		If IsArray($aTownHallLevel) Then $g_iTownHallLevel = 0 ; Check for error finding TH level, and reset to zero if yes
	EndIf

	If Number($g_iTownHallLevel) > 1 And Number($g_iTownHallLevel) < 6 Then
		SetLog("Warning: TownHall level below 6 NOT RECOMMENDED!", $COLOR_ERROR)
		SetLog("Proceed with caution as errors may occur.", $COLOR_ERROR)
	EndIf

	If $g_iTownHallLevel < 2 Or ($g_aiTownHallPos[1] = "" Or $g_aiTownHallPos[1] = -1) Then
		; Planned runs fail closed through RunVillageReadinessValidate. Never open the legacy
		; manual locator during unattended Start, because it captures desktop mouse coordinates
		; and can target a scaled/docked emulator window incorrectly.
		If $bOwnVillageReadinessOnly Then Return
		LocateTownHall(False, False)
	EndIf

	; A planned one-run session needs only a supported Town Hall and canonical coordinates.
	; Clan Castle, Hero Hall, Laboratory, Pet House, Blacksmith and Helper Hut discovery is
	; legacy profile setup and must not block or click through the Start readiness boundary.
	If $bOwnVillageReadinessOnly Then Return

	If _Sleep($DELAYBOTDETECT1) Then Return
	; CheckImageType()
	If _Sleep($DELAYBOTDETECT1) Then Return

	If $g_bScreenshotHideName Then
		If _Sleep($DELAYBOTDETECT3) Then Return
		If $g_aiClanCastlePos[0] = -1 Or $g_aiClanCastleTroopsCap = -1 Then
			LocateClanCastle(False)
			SaveConfig()
		EndIf
	EndIf

	If Number($g_iTownHallLevel) >= 7 Then
		If _Sleep($DELAYBOTDETECT3) Then Return
		If $g_aiHeroHallPos[0] = "" Or $g_aiHeroHallPos[0] = -1 Then
			LocateHeroHall(False)
			SaveConfig()
		EndIf
	EndIf

	If _Sleep($DELAYBOTDETECT3) Then Return
	If $g_aiLaboratoryPos[0] = "" Or $g_aiLaboratoryPos[0] = -1 Then
		LocateLab(False)
		SaveConfig()
	EndIf

	If Number($g_iTownHallLevel) >= 14 Then
		If _Sleep($DELAYBOTDETECT3) Then Return
		If $g_aiPetHousePos[0] = "" Or $g_aiPetHousePos[0] = -1 Then
			LocatePetHouse(False)
			SaveConfig()
		EndIf
	EndIf

	If Number($g_iTownHallLevel) >= 8 Then
		If _Sleep($DELAYBOTDETECT3) Then Return
		If $g_aiBlacksmithPos[0] = "" Or $g_aiBlacksmithPos[0] = -1 Then
			LocateBlacksmith(False)
			SaveConfig()
		EndIf
	EndIf

	If Number($g_iTownHallLevel) >= 9 Then
		If _Sleep($DELAYBOTDETECT3) Then Return
		If $g_aiHelperHutPos[0] = "" Or $g_aiHelperHutPos[0] = -1 Then
		LocateHelperHut(False)
		SaveConfig()
		EndIf
	EndIf

	;Display Level TH in Stats
	GUICtrlSetData($g_hLblTHLevels, "")

	_GUI_Value_STATE("HIDE", $g_aGroupListTHLevels)
	SetDebugLog("Select TH Level:" & Number($g_iTownHallLevel), $COLOR_DEBUG)
	If Number($g_iTownHallLevel) >= 0 And Number($g_iTownHallLevel) <= $g_iMaxTHLevel Then _
		GUICtrlSetState($g_ahPicTHLevels[$g_iTownHallLevel], $GUI_SHOW)
	GUICtrlSetData($g_hLblTHLevels, $g_iTownHallLevel)
EndFunc   ;==>BotDetectFirstTime
