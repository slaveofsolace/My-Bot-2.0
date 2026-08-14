; #FUNCTION# ====================================================================================================================
; Name ..........: Open Home collectors
; Description ...: Template-free, one-pass Home collection for an already-running, exact BlueStacks 5 Home Village.
; Remarks .......: This clean-room adapter uses only framebuffer pixels and the existing ADB capture/click channel. It never calls
;                  MyBot.run.dll, ImgLoc, XML templates, OCR, training, upgrades, donations, or account switching.
; ===============================================================================================================================
#include-once
#include "OpenHomeCollectorPolicy.au3"

Global Const $OPEN_HOME_MODE_OTHER = 0
Global Const $OPEN_HOME_MODE_COLLECTORS = 1
Global Const $OPEN_HOME_MODE_LOOT_CART = 2
Global Const $OPEN_HOME_MODE_REJECTED = -1

; Return 0 for another route, 1 for exact resource collectors, 2 for an exact Loot Cart pass, and -1 for a Home task
; that still needs an independently reviewed adapter. This prevents an unavailable reward task from
; silently falling through to the restricted inherited image engine.
Func OpenHomeCollectorsPreparedMode(ByRef $oIntent, ByRef $sError)
	$sError = ""
	If Not IsObj($oIntent) Or Not HomeMaintenanceRouteSelected($oIntent) Then Return $OPEN_HOME_MODE_OTHER
	Local $oPlan = $oIntent.Item("plan")
	Local $bCollectors = $oPlan.Item("events_collect_resources")
	Local $bDailyReward = $oPlan.Item("events_collect_daily_reward")
	Local $bLootCart = $oPlan.Item("events_collect_loot_cart")
	Local $bTreasury = $oPlan.Item("events_collect_treasury")
	If $bDailyReward Or $bTreasury Or ($bCollectors And $bLootCart) Or (Not $bCollectors And Not $bLootCart) Then
		$sError = "This build can run one template-free Home task at a time: resource collectors or Loot Cart; Daily Reward and Treasury remain unavailable"
		Return $OPEN_HOME_MODE_REJECTED
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("emulator")), $STR_STRIPALL)) <> "bluestacks5" Then
		$sError = "Template-free Home collection currently requires the exact BlueStacks 5 adapter"
		Return $OPEN_HOME_MODE_REJECTED
	EndIf
	Return $bCollectors ? $OPEN_HOME_MODE_COLLECTORS : $OPEN_HOME_MODE_LOOT_CART
EndFunc   ;==>OpenHomeCollectorsPreparedMode

Func _OpenHomeCollectorBitmapPixel($hBitmap, $iX, $iY)
	Return BitAND(_GDIPlus_BitmapGetPixel($hBitmap, $iX, $iY), 0xFFFFFF)
EndFunc   ;==>_OpenHomeCollectorBitmapPixel

; $aFound is [type][present,x,y,score]. A 3-pixel grid cuts the normal scan to about 40k centers.
; The remaining eight parity grids are fail-safe fallbacks only when a requested type is not found.
Func OpenHomeCollectorsDetect(ByRef $aFound, $hBitmap = Default, $iRequiredMask = 7)
	If $hBitmap = Default Then $hBitmap = $g_hBitmap
	If $hBitmap = 0 Or Not IsArray($aFound) Or UBound($aFound, 1) < 4 Or UBound($aFound, 2) < 4 Then Return 0
	Local $aOffsetX[9] = [0, 1, 2, 0, 1, 2, 0, 1, 2]
	Local $aOffsetY[9] = [0, 0, 0, 1, 1, 1, 2, 2, 2]
	Local $iRequired = 0
	For $iRequiredType = $OPEN_HOME_COLLECTOR_GOLD To $OPEN_HOME_COLLECTOR_DARK
		If BitAND($iRequiredMask, BitShift(1, -($iRequiredType - 1))) Then $iRequired += 1
	Next
	If $iRequired = 0 Then Return 0
	Local $iFound = 0
	For $iPass = 0 To 8
		For $iY = 100 + $aOffsetY[$iPass] To 600 Step 3
			If Mod($iY, 12) = 0 And (RunControlStopRequested() Or Not $g_bRunState) Then Return SetError(2, $iFound, $iFound)
			For $iX = 70 + $aOffsetX[$iPass] To 790 Step 3
				Local $iCenter = _OpenHomeCollectorBitmapPixel($hBitmap, $iX, $iY)
				Local $iUpperLeft = _OpenHomeCollectorBitmapPixel($hBitmap, $iX - 4, $iY - 4)
				Local $iType = OpenHomeCollectorClassify($iCenter, $iUpperLeft)
				If $iType = $OPEN_HOME_COLLECTOR_NONE Or $aFound[$iType][0] Or _
						Not BitAND($iRequiredMask, BitShift(1, -($iType - 1))) Then ContinueLoop
				Local $iScore = OpenHomeCollectorGeometryScore( _
						_OpenHomeCollectorBitmapPixel($hBitmap, $iX - 8, $iY - 8), _
						_OpenHomeCollectorBitmapPixel($hBitmap, $iX + 8, $iY - 8), _
						_OpenHomeCollectorBitmapPixel($hBitmap, $iX + 8, $iY), _
						_OpenHomeCollectorBitmapPixel($hBitmap, $iX + 8, $iY + 8))
				If $iScore < 0 Then ContinueLoop
				$aFound[$iType][0] = 1
				$aFound[$iType][1] = $iX
				$aFound[$iType][2] = $iY
				$aFound[$iType][3] = $iScore
				$iFound += 1
			Next
		Next
		If $iFound = $iRequired Then ExitLoop
	Next
	Return $iFound
EndFunc   ;==>OpenHomeCollectorsDetect

; Capture directly through the already-proven ADB channel. This deliberately avoids _CaptureRegion's
; legacy CheckAndroidRunning(auto-start/reboot) side effect: a missing exact emulator is a hard failure.
Func OpenHomeCollectorsCapture()
	If Not $g_bAndroidAdbScreencap Or Not IsArray(GetBlueStacks5ModernAdbSurfacePosition()) Then Return False
	ForceCaptureRegion()
	Local $hNewBitmap = AndroidScreencap(0, 0, $g_iGAME_WIDTH, $g_iGAME_HEIGHT)
	Local $iCaptureError = @error
	If $iCaptureError Or $hNewBitmap = 0 Then Return SetError(1, $iCaptureError, False)
	If $g_hHBitmap <> 0 And $g_hHBitmap <> $g_hHBitmapTest And $g_hHBitmap2 <> $g_hHBitmap Then GdiDeleteHBitmap($g_hHBitmap)
	$g_hHBitmap = $hNewBitmap
	GdiAddHBitmap($g_hHBitmap)
	If $g_hBitmap <> 0 Then GdiDeleteBitmap($g_hBitmap)
	$g_hBitmap = _GDIPlus_BitmapCreateFromHBITMAP($g_hHBitmap)
	If $g_hBitmap = 0 Then Return SetError(2, 0, False)
	GdiAddBitmap($g_hBitmap)
	Return True
EndFunc   ;==>OpenHomeCollectorsCapture

Func OpenHomeCollectorsProveHome()
	If Not OpenHomeCollectorsCapture() Then Return False
	Return _CheckPixel($aIsMain, False)
EndFunc   ;==>OpenHomeCollectorsProveHome

; Issue at most one accepted click per resource type. Every decision uses a fresh frame; Home and Stop
; are rechecked before every click and Home is re-proved after the last input. @extended is accepted clicks.
Func OpenHomeCollectorsCollectOnePass()
	Local $aIssued[4] = [False, False, False, False]
	Local $iClicks = 0
	For $iAction = 1 To 3
		If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, $iClicks, False)
		If Not OpenHomeCollectorsProveHome() Then Return SetError(3, $iClicks, False)
		Local $aFound[4][4]
		Local $iRequiredMask = 0
		For $iRequiredType = $OPEN_HOME_COLLECTOR_GOLD To $OPEN_HOME_COLLECTOR_DARK
			If Not $aIssued[$iRequiredType] Then $iRequiredMask = BitOR($iRequiredMask, BitShift(1, -($iRequiredType - 1)))
		Next
		OpenHomeCollectorsDetect($aFound, Default, $iRequiredMask)
		If @error = 2 Then Return SetError(2, $iClicks, False)
		Local $iType = $OPEN_HOME_COLLECTOR_NONE
		For $iCandidateType = $OPEN_HOME_COLLECTOR_GOLD To $OPEN_HOME_COLLECTOR_DARK
			If Not $aIssued[$iCandidateType] And $aFound[$iCandidateType][0] Then
				$iType = $iCandidateType
				ExitLoop
			EndIf
		Next
		If $iType = $OPEN_HOME_COLLECTOR_NONE Then ExitLoop
		If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, $iClicks, False)
		If Not _CheckPixel($aIsMain, False) Then Return SetError(3, $iClicks, False)
		If Not Click($aFound[$iType][1], $aFound[$iType][2], 1, 120, "#OpenHomeCollector") Then
			If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, $iClicks, False)
			Return SetError(4, $iClicks, False)
		EndIf
		$iClicks += 1
		$aIssued[$iType] = True
		If _Sleep(600, True, True, False) Then Return SetError(2, $iClicks, False)
	Next
	If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, $iClicks, False)
	If Not OpenHomeCollectorsProveHome() Then Return SetError(5, $iClicks, False)
	Return SetError(0, $iClicks, True)
EndFunc   ;==>OpenHomeCollectorsCollectOnePass

Func _OpenHomePixelNear($iX, $iY, $iExpected, $iVariation = 32)
	If $g_hBitmap = 0 Or $iX < 0 Or $iX >= $g_iGAME_WIDTH Or $iY < 0 Or $iY >= $g_iGAME_HEIGHT Then Return False
	Return _ColorCheck(Hex(_OpenHomeCollectorBitmapPixel($g_hBitmap, $iX, $iY), 6), Hex($iExpected, 6), $iVariation)
EndFunc   ;==>_OpenHomePixelNear

; Current-client 860x732 Home Village cue for the in-game "Collect" label above a Loot Cart.
; Eight anti-aliased glyph pixels make the cue unique in the verified redacted Home fixture while
; keeping the recognizer independent from the inherited ImgLoc engine and proprietary XML assets.
Func _OpenHomeLootCartCueAt($iX, $iY)
	Return _OpenHomePixelNear($iX + 26, $iY + 2, 0xC3BDBA) And _
			_OpenHomePixelNear($iX + 1, $iY + 5, 0xB7B0AA) And _
			_OpenHomePixelNear($iX + 4, $iY, 0x65635A) And _
			_OpenHomePixelNear($iX + 13, $iY, 0xB8B2AF) And _
			_OpenHomePixelNear($iX + 8, $iY + 2, 0xBBB4B0) And _
			_OpenHomePixelNear($iX + 15, $iY + 5, 0xBDB6B4) And _
			_OpenHomePixelNear($iX + 10, $iY + 3, 0x75736C) And _
			_OpenHomePixelNear($iX + 29, $iY + 5, 0x828273)
EndFunc   ;==>_OpenHomeLootCartCueAt

Func _OpenHomeLootCartScanRegion($iLeft, $iTop, $iRight, $iBottom)
	For $iX = $iLeft To $iRight
		If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, 0, 0)
		For $iY = $iTop To $iBottom
			If Mod($iY - $iTop, 48) = 0 And (RunControlStopRequested() Or Not $g_bRunState) Then Return SetError(2, 0, 0)
			If _OpenHomeLootCartCueAt($iX, $iY) Then
				; The cart sits directly below the label. Keep the issued point inside the exact viewport.
				Return LootCartObservationCreate($LOOT_CART_STATE_AVAILABLE, $iX + 15, $iY + 26)
			EndIf
		Next
	Next
	Return LootCartObservationCreate($LOOT_CART_STATE_ABSENT)
EndFunc   ;==>_OpenHomeLootCartScanRegion

Func OpenHomeLootCartDetectCue()
	If Not OpenHomeCollectorsProveHome() Then Return SetError(1, 0, 0)
	Local $oCue = _OpenHomeLootCartScanRegion(0, 80, 150, 515)
	If @error Or (IsObj($oCue) And $oCue.Item("state") = $LOOT_CART_STATE_AVAILABLE) Then Return $oCue
	$oCue = _OpenHomeLootCartScanRegion(680, 80, 830, 515)
	If @error Or (IsObj($oCue) And $oCue.Item("state") = $LOOT_CART_STATE_AVAILABLE) Then Return $oCue
	Return _OpenHomeLootCartScanRegion(150, 515, 680, 600)
EndFunc   ;==>OpenHomeLootCartDetectCue

; Fixed selected-object action card. These anchors cover the title, white card, dark border, and
; Collect glyph; all eight were absent before selection and after the verified live collection.
Func OpenHomeLootCartCollectPanelReady()
	If Not OpenHomeCollectorsCapture() Then Return False
	Return _OpenHomePixelNear(395, 580, 0xFFFADA, 36) And _
			_OpenHomePixelNear(470, 580, 0xFFFFFF, 36) And _
			_OpenHomePixelNear(430, 570, 0xF6F2DB, 36) And _
			_OpenHomePixelNear(415, 628, 0xBFBBB0, 36) And _
			_OpenHomePixelNear(445, 628, 0x151614, 36) And _
			_OpenHomePixelNear(461, 628, 0x9FA879, 36) And _
			_OpenHomePixelNear(410, 550, 0xFFFFB7, 36) And _
			_OpenHomePixelNear(390, 600, 0x5C5C5A, 36)
EndFunc   ;==>OpenHomeLootCartCollectPanelReady

Func OpenHomeLootCartDetectCollect()
	For $iAttempt = 1 To 6
		If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, 0, 0)
		If OpenHomeLootCartCollectPanelReady() Then Return LootCartObservationCreate($LOOT_CART_STATE_COLLECT_READY, 431, 608)
		If _Sleep(250, True, True, False) Then Return SetError(2, 0, 0)
	Next
	Return LootCartObservationCreate($LOOT_CART_STATE_COLLECT_MISSING)
EndFunc   ;==>OpenHomeLootCartDetectCollect

Func OpenHomeLootCartIssueOpen($iX, $iY)
	If RunControlStopRequested() Or Not $g_bRunState Or Not _CheckPixel($aIsMain, False) Then Return False
	Local $bIssued = Click(Int($iX), Int($iY), 1, 120, "#OpenHomeLootCart")
	If $bIssued Then RunEventLogMaintenanceLootCartOpenIssued(1)
	Return $bIssued
EndFunc   ;==>OpenHomeLootCartIssueOpen

Func OpenHomeLootCartIssueCollect($iX, $iY)
	If RunControlStopRequested() Or Not $g_bRunState Or Not OpenHomeLootCartCollectPanelReady() Then Return False
	Local $bIssued = Click(Int($iX), Int($iY), 1, 120, "#OpenHomeLootCartCollect")
	If $bIssued Then RunEventLogMaintenanceLootCartCollectIssued(1)
	Return $bIssued
EndFunc   ;==>OpenHomeLootCartIssueCollect

Func OpenHomeLootCartProveHome()
	For $iAttempt = 1 To 8
		If RunControlStopRequested() Or Not $g_bRunState Then Return False
		If OpenHomeCollectorsProveHome() Then Return True
		If _Sleep(250, True, True, False) Then Return False
	Next
	Return False
EndFunc   ;==>OpenHomeLootCartProveHome
