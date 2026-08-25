; #FUNCTION# ====================================================================================================================
; Name ..........: Open Builder Base collectors
; Description ...: Template-free, one-pass Builder Base resource collection for the exact BlueStacks 5 current client.
; Remarks .......: This clean-room adapter uses framebuffer pixels and the reviewed NoPremiumPointClick transport only. It never calls
;                  ImgLoc, inherited image exports, XML templates, OCR, legacy battle/upgrade/obstacle routines,
;                  training, donations, account switching, shop, gems, or any generic click helper.
; ===============================================================================================================================
#include-once

Global Const $OPEN_BUILDER_MODE_OTHER = 0
Global Const $OPEN_BUILDER_MODE_COLLECTORS = 1
Global Const $OPEN_BUILDER_MODE_REJECTED = -1

Global Const $OPEN_BUILDER_COLLECTOR_GOLD = 1
Global Const $OPEN_BUILDER_COLLECTOR_ELIXIR = 2

Global Const $OPEN_BUILDER_SWITCH_X = 145
Global Const $OPEN_BUILDER_SWITCH_Y = 620
Global Const $OPEN_BUILDER_RETURN_X = 821
Global Const $OPEN_BUILDER_RETURN_Y = 465

Func OpenBuilderBaseCollectorsPreparedMode(ByRef $oIntent, ByRef $sError)
	$sError = ""
	If Not IsObj($oIntent) Or Not BuilderMaintenanceRouteSelected($oIntent) Then Return $OPEN_BUILDER_MODE_OTHER
	Local $oPlan = $oIntent.Item("plan")
	If Not $oPlan.Item("events_collect_resources") Or $oPlan.Item("events_collect_daily_reward") Or _
			$oPlan.Item("events_collect_loot_cart") Or $oPlan.Item("events_collect_treasury") Then
		$sError = "Builder Base collection must be the only selected collection task"
		Return $OPEN_BUILDER_MODE_REJECTED
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("emulator")), $STR_STRIPALL)) <> "bluestacks5" Then
		$sError = "Template-free Builder Base collection currently requires the exact BlueStacks 5 adapter"
		Return $OPEN_BUILDER_MODE_REJECTED
	EndIf
	Return $OPEN_BUILDER_MODE_COLLECTORS
EndFunc   ;==>OpenBuilderBaseCollectorsPreparedMode

Func OpenBuilderBaseCurrentFrameReady()
	If $g_hBitmap = 0 Then Return False
	Return _CheckPixel($aIsOnBuilderBase, False)
EndFunc   ;==>OpenBuilderBaseCurrentFrameReady

Func OpenBuilderBaseCollectorsProveBuilder()
	If Not OpenHomeCollectorsCapture() Then Return False
	Local $bBuilderProven = OpenBuilderBaseCurrentFrameReady()
	$g_bMainWindowOk = $bBuilderProven
	Return $bBuilderProven
EndFunc   ;==>OpenBuilderBaseCollectorsProveBuilder

Func OpenBuilderBaseHomeBoatPointReady($iX, $iY)
	If Not NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_BUILDER_SWITCH, $iX, $iY) Then Return False
	If Not _CheckPixel($aIsMain, False) Then Return False
	Return _OpenHomePixelNear(128, 583, 0xB3463E, 48) And _
			_OpenHomePixelNear(122, 603, 0xBD9355, 56) And _
			_OpenHomePixelNear(168, 638, 0x1E384D, 48)
EndFunc   ;==>OpenBuilderBaseHomeBoatPointReady

Func OpenBuilderBaseReturnBoatPointReady($iX, $iY)
	If Not NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_BUILDER_RETURN_HOME, $iX, $iY) Then Return False
	If Not OpenBuilderBaseCurrentFrameReady() Then Return False
	Return _OpenHomePixelNear(821, 465, 0xEE5C54, 48) And _
			_OpenHomePixelNear(798, 442, 0xFFED1A, 48) And _
			_OpenHomePixelNear(804, 479, 0xD3AC35, 48)
EndFunc   ;==>OpenBuilderBaseReturnBoatPointReady

Func _OpenBuilderBaseColorRed($iColor)
	Return BitAND(BitShift($iColor, 16), 0xFF)
EndFunc   ;==>_OpenBuilderBaseColorRed

Func _OpenBuilderBaseColorGreen($iColor)
	Return BitAND(BitShift($iColor, 8), 0xFF)
EndFunc   ;==>_OpenBuilderBaseColorGreen

Func _OpenBuilderBaseColorBlue($iColor)
	Return BitAND($iColor, 0xFF)
EndFunc   ;==>_OpenBuilderBaseColorBlue

Func _OpenBuilderBasePixel($iX, $iY)
	Return BitAND(_GDIPlus_BitmapGetPixel($g_hBitmap, $iX, $iY), 0xFFFFFF)
EndFunc   ;==>_OpenBuilderBasePixel

Func _OpenBuilderBaseIsGoldColor($iColor)
	Local $iRed = _OpenBuilderBaseColorRed($iColor)
	Local $iGreen = _OpenBuilderBaseColorGreen($iColor)
	Local $iBlue = _OpenBuilderBaseColorBlue($iColor)
	Return $iRed >= 220 And $iGreen >= 145 And $iGreen <= 235 And $iBlue <= 110
EndFunc   ;==>_OpenBuilderBaseIsGoldColor

Func _OpenBuilderBaseIsElixirColor($iColor)
	Local $iRed = _OpenBuilderBaseColorRed($iColor)
	Local $iGreen = _OpenBuilderBaseColorGreen($iColor)
	Local $iBlue = _OpenBuilderBaseColorBlue($iColor)
	Return $iRed >= 130 And $iBlue >= 150 And $iGreen <= 130 And ($iRed + $iBlue - 2 * $iGreen) >= 120
EndFunc   ;==>_OpenBuilderBaseIsElixirColor

Func _OpenBuilderBaseResourceCandidateAllowed($iType, $iX, $iY)
	; Narrow to the reviewed current-client Builder Base resource-bubble lane. This prevents gold piles,
	; decorations, and the green Gem Mine bubble from minting a permit.
	Switch $iType
		Case $OPEN_BUILDER_COLLECTOR_GOLD
			Return $iX >= 500 And $iX <= 530 And $iY >= 405 And $iY <= 435
		Case $OPEN_BUILDER_COLLECTOR_ELIXIR
			Return $iX >= 320 And $iX <= 350 And $iY >= 395 And $iY <= 420
	EndSwitch
	Return False
EndFunc   ;==>_OpenBuilderBaseResourceCandidateAllowed

Func OpenBuilderBaseResourceTargetReady($iType, $iX, $iY)
	If Not OpenBuilderBaseCurrentFrameReady() Or Not NoPremiumPermitTargetValid( _
			$iType = $OPEN_BUILDER_COLLECTOR_GOLD ? $NO_PREMIUM_ACTION_BUILDER_COLLECT_GOLD : $NO_PREMIUM_ACTION_BUILDER_COLLECT_ELIXIR, _
			$iX, $iY) Then Return False
	If Not _OpenBuilderBaseResourceCandidateAllowed($iType, Int($iX), Int($iY)) Then Return False
	Local $iColor = _OpenBuilderBasePixel(Int($iX), Int($iY))
	If $iType = $OPEN_BUILDER_COLLECTOR_GOLD Then Return _OpenBuilderBaseIsGoldColor($iColor)
	Return _OpenBuilderBaseIsElixirColor($iColor)
EndFunc   ;==>OpenBuilderBaseResourceTargetReady

Func OpenBuilderBaseCollectorsDetect(ByRef $aFound)
	If $g_hBitmap = 0 Or Not IsArray($aFound) Or UBound($aFound, 1) < 3 Or UBound($aFound, 2) < 3 Then Return 0
	If Not OpenBuilderBaseCurrentFrameReady() Then Return SetError(1, 0, 0)
	Local $iFound = 0
	For $iY = 395 To 435 Step 2
		If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, $iFound, $iFound)
		For $iX = 300 To 540 Step 2
			Local $iColor = _OpenBuilderBasePixel($iX, $iY)
			Local $iType = 0
			If _OpenBuilderBaseIsGoldColor($iColor) Then
				$iType = $OPEN_BUILDER_COLLECTOR_GOLD
			ElseIf _OpenBuilderBaseIsElixirColor($iColor) Then
				$iType = $OPEN_BUILDER_COLLECTOR_ELIXIR
			EndIf
			If $iType = 0 Or $aFound[$iType][0] Or Not _OpenBuilderBaseResourceCandidateAllowed($iType, $iX, $iY) Then ContinueLoop
			$aFound[$iType][0] = 1
			$aFound[$iType][1] = $iX
			$aFound[$iType][2] = $iY
			$iFound += 1
			If $iFound = 2 Then Return $iFound
		Next
	Next
	Return $iFound
EndFunc   ;==>OpenBuilderBaseCollectorsDetect

Func OpenBuilderBaseSwitchToBuilder()
	If OpenBuilderBaseCollectorsProveBuilder() Then Return True
	If Not OpenHomeCollectorsProveHome() Then Return SetError(1, 0, False)
	If Not OpenBuilderBaseHomeBoatPointReady($OPEN_BUILDER_SWITCH_X, $OPEN_BUILDER_SWITCH_Y) Then Return SetError(3, 0, False)
	If Not OpenHomeNoGemInputReady() Then Return SetError(6, 0, False)
	If Not NoPremiumPointClick($NO_PREMIUM_ACTION_BUILDER_SWITCH, $OPEN_BUILDER_SWITCH_X, $OPEN_BUILDER_SWITCH_Y, 120, "#OpenBuilderBaseSwitch", True) Then _
		Return SetError(4, 0, False)
	RunEventLogBuilderMaintenanceSwitchIssued()
	For $iAttempt = 1 To 16
		If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, 0, False)
		If OpenBuilderBaseCollectorsProveBuilder() Then Return True
		If _Sleep(350, True, True, False) Then Return SetError(2, 0, False)
	Next
	Return SetError(5, 0, False)
EndFunc   ;==>OpenBuilderBaseSwitchToBuilder

Func OpenBuilderBaseReturnHome()
	If OpenHomeCollectorsProveHome() Then Return True
	If Not OpenBuilderBaseCollectorsProveBuilder() Then Return SetError(1, 0, False)
	If Not OpenBuilderBaseReturnBoatPointReady($OPEN_BUILDER_RETURN_X, $OPEN_BUILDER_RETURN_Y) Then Return SetError(3, 0, False)
	If Not OpenHomeNoGemInputReady() Then Return SetError(6, 0, False)
	If Not NoPremiumPointClick($NO_PREMIUM_ACTION_BUILDER_RETURN_HOME, $OPEN_BUILDER_RETURN_X, $OPEN_BUILDER_RETURN_Y, 120, "#OpenBuilderBaseReturn", True) Then _
		Return SetError(4, 0, False)
	For $iAttempt = 1 To 16
		If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, 0, False)
		If OpenHomeCollectorsProveHome() Then Return True
		If _Sleep(350, True, True, False) Then Return SetError(2, 0, False)
	Next
	Return SetError(5, 0, False)
EndFunc   ;==>OpenBuilderBaseReturnHome

Func OpenBuilderBaseCollectorsCollectOnePass($iMaxClicks = 2)
	Local $iClickLimit = Int($iMaxClicks)
	If $iClickLimit < 1 Then $iClickLimit = 1
	If $iClickLimit > 2 Then $iClickLimit = 2
	If Not OpenBuilderBaseSwitchToBuilder() Then Return SetError(@error, 0, False)
	Local $aIssued[3] = [False, False, False]
	Local $iClicks = 0
	For $iAction = 1 To $iClickLimit
		If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, $iClicks, False)
		If Not OpenBuilderBaseCollectorsProveBuilder() Then Return SetError(3, $iClicks, False)
		Local $aFound[3][3]
		Local $iFound = OpenBuilderBaseCollectorsDetect($aFound)
		If @error = 2 Then Return SetError(2, $iClicks, False)
		If @error Then ExitLoop
		Local $iType = 0
		For $iCandidateType = $OPEN_BUILDER_COLLECTOR_ELIXIR To $OPEN_BUILDER_COLLECTOR_GOLD Step -1
			If Not $aIssued[$iCandidateType] And $aFound[$iCandidateType][0] Then
				$iType = $iCandidateType
				ExitLoop
			EndIf
		Next
		If $iType = 0 Then ExitLoop
		If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, $iClicks, False)
		If Not OpenBuilderBaseCurrentFrameReady() Then Return SetError(3, $iClicks, False)
		If Not OpenHomeNoGemInputReady() Then Return SetError(6, $iClicks, False)
		Local $sAction = $iType = $OPEN_BUILDER_COLLECTOR_GOLD ? $NO_PREMIUM_ACTION_BUILDER_COLLECT_GOLD : $NO_PREMIUM_ACTION_BUILDER_COLLECT_ELIXIR
		If Not NoPremiumPointClick($sAction, $aFound[$iType][1], $aFound[$iType][2], 120, "#OpenBuilderBaseCollector", True) Then
			If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, $iClicks, False)
			Return SetError(4, $iClicks, False)
		EndIf
		$iClicks += 1
		$aIssued[$iType] = True
		RunEventLogBuilderMaintenanceResourceIssued($iType, $aFound[$iType][1], $aFound[$iType][2])
		If _Sleep(700, True, True, False) Then Return SetError(2, $iClicks, False)
	Next
	If Not OpenBuilderBaseReturnHome() Then Return SetError(7, $iClicks, False)
	Return SetError(0, $iClicks, True)
EndFunc   ;==>OpenBuilderBaseCollectorsCollectOnePass
