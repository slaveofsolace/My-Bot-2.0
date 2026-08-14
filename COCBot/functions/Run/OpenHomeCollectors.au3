; #FUNCTION# ====================================================================================================================
; Name ..........: Open Home collectors
; Description ...: Template-free, one-pass collector recognition for an already-running, exact BlueStacks 5 Home Village.
; Remarks .......: This clean-room adapter uses only framebuffer pixels and the existing ADB capture/click channel. It never calls
;                  MyBot.run.dll, ImgLoc, XML templates, OCR, training, upgrades, donations, rewards, or account switching.
; ===============================================================================================================================
#include-once
#include "OpenHomeCollectorPolicy.au3"

; Return 0 for another route, 1 for the exact clean-room collectors route, and -1 for a Home task
; that still needs an independently reviewed adapter. This prevents an unavailable reward task from
; silently falling through to the restricted inherited image engine.
Func OpenHomeCollectorsPreparedMode(ByRef $oIntent, ByRef $sError)
	$sError = ""
	If Not IsObj($oIntent) Or Not HomeMaintenanceRouteSelected($oIntent) Then Return 0
	Local $oPlan = $oIntent.Item("plan")
	If Not $oPlan.Item("events_collect_resources") Or $oPlan.Item("events_collect_daily_reward") Or _
			$oPlan.Item("events_collect_loot_cart") Or $oPlan.Item("events_collect_treasury") Then
		$sError = "This build can run template-free resource collectors only; Daily Reward, Loot Cart, and Treasury remain unavailable"
		Return -1
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("emulator")), $STR_STRIPALL)) <> "bluestacks5" Then
		$sError = "Template-free collectors currently require the exact BlueStacks 5 adapter"
		Return -1
	EndIf
	Return 1
EndFunc   ;==>OpenHomeCollectorsPreparedMode

Func _OpenHomeCollectorBitmapPixel($hBitmap, $iX, $iY)
	Return BitAND(_GDIPlus_BitmapGetPixel($hBitmap, $iX, $iY), 0xFFFFFF)
EndFunc   ;==>_OpenHomeCollectorBitmapPixel

; $aFound is [type][present,x,y,score]. Four 2-pixel parity passes cover every pixel while allowing
; early exit as soon as one strict candidate for each resource type is available.
Func OpenHomeCollectorsDetect(ByRef $aFound, $hBitmap = Default)
	If $hBitmap = Default Then $hBitmap = $g_hBitmap
	If $hBitmap = 0 Or Not IsArray($aFound) Or UBound($aFound, 1) < 4 Or UBound($aFound, 2) < 4 Then Return 0
	Local $aOffsetX[4] = [0, 1, 0, 1]
	Local $aOffsetY[4] = [0, 1, 1, 0]
	Local $iFound = 0
	For $iPass = 0 To 3
		For $iY = 100 + $aOffsetY[$iPass] To 600 Step 2
			For $iX = 70 + $aOffsetX[$iPass] To 790 Step 2
				Local $iCenter = _OpenHomeCollectorBitmapPixel($hBitmap, $iX, $iY)
				Local $iUpperLeft = _OpenHomeCollectorBitmapPixel($hBitmap, $iX - 4, $iY - 4)
				Local $iType = OpenHomeCollectorClassify($iCenter, $iUpperLeft)
				If $iType = $OPEN_HOME_COLLECTOR_NONE Or $aFound[$iType][0] Then ContinueLoop
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
		If $iFound = 3 Then ExitLoop
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
		OpenHomeCollectorsDetect($aFound)
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
