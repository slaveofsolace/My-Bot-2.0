; #FUNCTION# ====================================================================================================================
; Name ..........: Open Home collectors
; Description ...: Template-free, one-pass Home collection for an already-running, exact BlueStacks 5 Home Village.
; Remarks .......: This clean-room adapter uses only framebuffer pixels and the configured Click channel (ADB or WinAPI control). It never calls
;                  MyBot.run.dll, ImgLoc, XML templates, OCR, training, upgrades, donations, or account switching.
; ===============================================================================================================================
#include-once
#include "OpenHomeCollectorPolicy.au3"

Global Const $OPEN_HOME_MODE_OTHER = 0
Global Const $OPEN_HOME_MODE_COLLECTORS = 1
Global Const $OPEN_HOME_MODE_LOOT_CART = 2
Global Const $OPEN_HOME_MODE_DAILY_REWARD = 3
Global Const $OPEN_HOME_MODE_TREASURY = 4
Global Const $OPEN_HOME_MODE_REJECTED = -1

; Return 0 for another route, 1 for exact resource collectors, 2 for an exact Loot Cart pass, 3 for the
; startup Daily Reward, 4 for the bounded Treasury adapter, and -1 for an invalid Home selection. This
; prevents an unavailable reward task from silently falling through to the restricted inherited image engine.
Func OpenHomeCollectorsPreparedMode(ByRef $oIntent, ByRef $sError)
	$sError = ""
	If Not IsObj($oIntent) Or Not HomeMaintenanceRouteSelected($oIntent) Then Return $OPEN_HOME_MODE_OTHER
	Local $oPlan = $oIntent.Item("plan")
	Local $bCollectors = $oPlan.Item("events_collect_resources")
	Local $bDailyReward = $oPlan.Item("events_collect_daily_reward")
	Local $bLootCart = $oPlan.Item("events_collect_loot_cart")
	Local $bTreasury = $oPlan.Item("events_collect_treasury")
	Local $iSelected = ($bCollectors ? 1 : 0) + ($bDailyReward ? 1 : 0) + ($bLootCart ? 1 : 0) + ($bTreasury ? 1 : 0)
	If $iSelected <> 1 Then
		$sError = "This build can run exactly one template-free Home task at a time: resource collectors, Loot Cart, Treasury, or startup Daily Reward"
		Return $OPEN_HOME_MODE_REJECTED
	EndIf
	If StringLower(StringStripWS(String($oPlan.Item("emulator")), $STR_STRIPALL)) <> "bluestacks5" Then
		$sError = "Template-free Home collection currently requires the exact BlueStacks 5 adapter"
		Return $OPEN_HOME_MODE_REJECTED
	EndIf
	If $bCollectors Then Return $OPEN_HOME_MODE_COLLECTORS
	If $bLootCart Then Return $OPEN_HOME_MODE_LOOT_CART
	If $bTreasury Then Return $OPEN_HOME_MODE_TREASURY
	Return $OPEN_HOME_MODE_DAILY_REWARD
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

; Frame-only revalidation for one detected collector bubble. This is called by the
; no-premium gate on each of its two independent captures and never captures or clicks.
Func OpenHomeCollectorTargetReady($iType, $iX, $iY)
	If $g_hBitmap = 0 Or $iType < $OPEN_HOME_COLLECTOR_GOLD Or $iType > $OPEN_HOME_COLLECTOR_DARK Or _
			$iX < 70 Or $iX > 790 Or $iY < 100 Or $iY > 600 Or Not _CheckPixel($aIsMain, False) Then Return False
	Local $iCenter = _OpenHomeCollectorBitmapPixel($g_hBitmap, $iX, $iY)
	Local $iUpperLeft = _OpenHomeCollectorBitmapPixel($g_hBitmap, $iX - 4, $iY - 4)
	If OpenHomeCollectorClassify($iCenter, $iUpperLeft) <> $iType Then Return False
	Return OpenHomeCollectorGeometryScore( _
			_OpenHomeCollectorBitmapPixel($g_hBitmap, $iX - 8, $iY - 8), _
			_OpenHomeCollectorBitmapPixel($g_hBitmap, $iX + 8, $iY - 8), _
			_OpenHomeCollectorBitmapPixel($g_hBitmap, $iX + 8, $iY), _
			_OpenHomeCollectorBitmapPixel($g_hBitmap, $iX + 8, $iY + 8)) >= 0
EndFunc   ;==>OpenHomeCollectorTargetReady

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
	Local $bHomeProven = _CheckPixel($aIsMain, False)
	; The terminal Home routes deliberately bypass IsMainPage(), but the control bridge publishes
	; game_ready from the same authoritative main-window flag. Keep the two proofs synchronized so
	; a freshly recognized Home route cannot report running while falsely claiming the game is not ready.
	$g_bMainWindowOk = $bHomeProven
	Return $bHomeProven
EndFunc   ;==>OpenHomeCollectorsProveHome

; Passive no-gem input gate. This mirrors the legacy gem-window pixel recognizer but deliberately
; never calls isGemOpen(), CloseWindow(), or any other input helper. Every bounded Home route must
; use a freshly captured frame and pass this predicate immediately before an allowed click.
Func OpenHomeNoGemInputReady()
	If $g_hBitmap = 0 Then Return False
	Local $bGemSurface = _CheckPixel($aIsGemWindow1, False) Or _
			(_CheckPixel($aIsGemWindow2, False) And _CheckPixel($aIsGemWindow3, False) And _CheckPixel($aIsGemWindow4, False))
	Return Not $bGemSurface
EndFunc   ;==>OpenHomeNoGemInputReady

; Issue at most $iMaxClicks accepted clicks total, and never more than one accepted click per resource type.
; Every decision uses a fresh frame; Home and Stop are rechecked before every click and Home is re-proved
; after the last input. @extended is accepted clicks.
Func OpenHomeCollectorsCollectOnePass($iMaxClicks = 3)
        Local $iClickLimit = Int($iMaxClicks)
        If $iClickLimit < 1 Then $iClickLimit = 1
        If $iClickLimit > 3 Then $iClickLimit = 3
        Local $aIssued[4] = [False, False, False, False]
        Local $iClicks = 0
        For $iAction = 1 To $iClickLimit
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
		If Not OpenHomeNoGemInputReady() Then Return SetError(6, $iClicks, False)
		Local $sCollectorAction = ""
		Switch $iType
			Case $OPEN_HOME_COLLECTOR_GOLD
				$sCollectorAction = $NO_PREMIUM_ACTION_COLLECTOR_GOLD
			Case $OPEN_HOME_COLLECTOR_ELIXIR
				$sCollectorAction = $NO_PREMIUM_ACTION_COLLECTOR_ELIXIR
			Case $OPEN_HOME_COLLECTOR_DARK
				$sCollectorAction = $NO_PREMIUM_ACTION_COLLECTOR_DARK
		EndSwitch
		If Not NoPremiumPointClick($sCollectorAction, $aFound[$iType][1], $aFound[$iType][2], 120, "#OpenHomeCollector", True) Then
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

; The startup Daily Reward overlay is fixed to the canonical 860x732 client surface. These anchors
; cover the wood panel and the exact grayscale close control without depending on OCR, ImgLoc, or a
; language-specific label. The private live frame is represented by the verified redacted fixture.
Func OpenHomeDailyRewardOverlayReady()
	If $g_hBitmap = 0 Then Return False
	Return _OpenHomePixelNear(759, 173, 0xFFFFFF, 20) And _
			_OpenHomePixelNear(746, 173, 0x616161, 36) And _
			_OpenHomePixelNear(772, 173, 0x606060, 36) And _
			_OpenHomePixelNear(759, 160, 0xACACAC, 36) And _
			_OpenHomePixelNear(759, 186, 0x595959, 36) And _
			_OpenHomePixelNear(430, 155, 0xA57315, 44) And _
			_OpenHomePixelNear(80, 285, 0x844A00, 44)
EndFunc   ;==>OpenHomeDailyRewardOverlayReady

; After a successful Claim the same close control changes from gray to red. Keep this as a separate
; current-client predicate so Claim recognition still depends only on the pre-claim fixture, while
; cleanup can prove the exact post-claim state before issuing its one reversible close input.
Func OpenHomeDailyRewardClaimedOverlayReady()
	If $g_hBitmap = 0 Then Return False
	Return _OpenHomePixelNear(759, 173, 0xFFFFFF, 20) And _
			_OpenHomePixelNear(746, 173, 0xF02328, 28) And _
			_OpenHomePixelNear(772, 173, 0xF02227, 28) And _
			_OpenHomePixelNear(759, 160, 0xF38F8D, 36) And _
			_OpenHomePixelNear(759, 186, 0xDC2125, 28) And _
			_OpenHomePixelNear(430, 155, 0xA57315, 44) And _
			_OpenHomePixelNear(80, 285, 0x844A00, 44)
EndFunc   ;==>OpenHomeDailyRewardClaimedOverlayReady

; The returning-player summary blocks Home with a fixed red banner, neutral content panel, and one
; green operator-only Okay control. Recognition is passive and language-independent: no OCR, ImgLoc,
; click, or dismissal is permitted. The reviewed fixture masks the account header and opponent card.
Func OpenHomeWelcomeBackOverlayReady()
	If $g_hBitmap = 0 Then Return False
	Return _OpenHomePixelNear(160, 170, 0xB03222, 36) And _
			_OpenHomePixelNear(250, 170, 0xB03323, 36) And _
			_OpenHomePixelNear(610, 170, 0xAF3323, 36) And _
			_OpenHomePixelNear(700, 170, 0xAF3322, 36) And _
			_OpenHomePixelNear(120, 225, 0xE8E8E0, 24) And _
			_OpenHomePixelNear(740, 225, 0xE8E8E0, 24) And _
			_OpenHomePixelNear(120, 560, 0xE8E8E0, 24) And _
			_OpenHomePixelNear(740, 560, 0xE8E8E0, 24) And _
			_OpenHomePixelNear(390, 540, 0x8AD032, 44) And _
			_OpenHomePixelNear(490, 540, 0x8BD033, 44) And _
			_OpenHomePixelNear(440, 520, 0xD9F481, 44) And _
			_OpenHomePixelNear(440, 558, 0x64AD32, 44)
EndFunc   ;==>OpenHomeWelcomeBackOverlayReady

; Clash can place a foreground "Anyone there?" inactivity dialog over an otherwise valid startup
; Daily Reward panel. The dialog is recoverable and non-premium, but it must be handled before any
; reward Claim recognition because the Claim button is visually blocked and dimmed underneath.
Func OpenHomeInactivityReloadDialogReady()
	If $g_hBitmap = 0 Then Return False
	Return _OpenHomePixelNear(232, 319, 0x424242, 18) And _
			_OpenHomePixelNear(420, 288, 0x424242, 18) And _
			_OpenHomePixelNear(430, 366, 0x424242, 18) And _
			_OpenHomePixelNear(500, 418, 0x424242, 18) And _
			_OpenHomePixelNear(260, 418, 0x689591, 42) And _
			_OpenHomePixelNear(300, 418, 0x67938F, 42)
EndFunc   ;==>OpenHomeInactivityReloadDialogReady

Func OpenHomeInactivityReloadPointReady($iX, $iY)
	If Not NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_RECOVERY_RELOAD_GAME, $iX, $iY) Then Return False
	Return OpenHomeInactivityReloadDialogReady()
EndFunc   ;==>OpenHomeInactivityReloadPointReady

Func OpenHomeInactivityReloadIssue()
	If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, 0, False)
	If Not OpenHomeCollectorsCapture() Then Return SetError(1, 0, False)
	If Not OpenHomeInactivityReloadDialogReady() Then Return SetError(0, 0, False)
	If Not OpenHomeNoGemInputReady() Then Return SetError(6, 0, False)
	Return NoPremiumPointClick($NO_PREMIUM_ACTION_RECOVERY_RELOAD_GAME, 281, 418, 120, "#OpenHomeInactivityReload", False)
EndFunc   ;==>OpenHomeInactivityReloadIssue

Func OpenHomeStartupRecoveryWait()
	For $iAttempt = 1 To 60
		If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, 0, False)
		If OpenHomeCollectorsProveHome() Or OpenHomeDailyRewardOverlayReady() Or _
				OpenHomeDailyRewardClaimedOverlayReady() Or OpenHomeWelcomeBackOverlayReady() Then Return True
		If _Sleep(1000, True, True, False) Then Return SetError(2, 0, False)
	Next
	Return SetError(4, 0, False)
EndFunc   ;==>OpenHomeStartupRecoveryWait

; A Claim button is a 117x40 green control. Sampling four interior edges avoids its localized white
; label while rejecting the small green claimed check and the gray/brown inactive day controls.
Func _OpenHomeDailyRewardClaimCandidateReady($iX, $iY)
	Return _OpenHomePixelNear($iX - 45, $iY, 0xCAED87, 44) And _
			_OpenHomePixelNear($iX + 45, $iY, 0xCAED87, 44) And _
			_OpenHomePixelNear($iX, $iY - 16, 0xDEFF8D, 44) And _
			_OpenHomePixelNear($iX, $iY + 16, 0x6F9438, 44)
EndFunc   ;==>_OpenHomeDailyRewardClaimCandidateReady

; $aClaim receives the sole canonical Claim center. Return 0 for no overlay/no claim, 1 for the exact
; actionable state, or >1 for an ambiguous state that must never receive input.
Func OpenHomeDailyRewardFindClaim(ByRef $aClaim)
	If Not IsArray($aClaim) Or UBound($aClaim) < 2 Or Not OpenHomeDailyRewardOverlayReady() Then Return 0
	; The current client places the lower-row recognition center at y=485. The earlier y=477
	; landed on the white label and sampled above the green control at y-16.
	Local $aCandidates[7][2] = [[149, 326], [297, 326], [445, 326], [149, 485], [297, 485], [445, 485], [592, 485]]
	Local $iMatches = 0
	For $i = 0 To UBound($aCandidates) - 1
		If Not _OpenHomeDailyRewardClaimCandidateReady($aCandidates[$i][0], $aCandidates[$i][1]) Then ContinueLoop
		If $iMatches = 0 Then
			$aClaim[0] = $aCandidates[$i][0]
			$aClaim[1] = $aCandidates[$i][1]
		EndIf
		$iMatches += 1
	Next
	Return $iMatches
EndFunc   ;==>OpenHomeDailyRewardFindClaim

Func OpenHomeDailyRewardCaptureClaim(ByRef $aClaim)
	If Not OpenHomeCollectorsCapture() Then Return SetError(1, 0, 0)
	Return OpenHomeDailyRewardFindClaim($aClaim)
EndFunc   ;==>OpenHomeDailyRewardCaptureClaim

Func OpenHomeDailyRewardClaimPointReady($iX, $iY)
	If $g_hBitmap = 0 Or Not NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_DAILY_REWARD_CLAIM, $iX, $iY) Then Return False
	Local $aClaim[2]
	Local $iClaims = OpenHomeDailyRewardFindClaim($aClaim)
	Return $iClaims = 1 And $aClaim[0] = Int($iX) And $aClaim[1] = Int($iY)
EndFunc   ;==>OpenHomeDailyRewardClaimPointReady

Func OpenHomeDailyRewardClosePointReady($iX, $iY)
	If Not NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_DAILY_REWARD_CLOSE, $iX, $iY) Then Return False
	Return OpenHomeDailyRewardOverlayReady() Or OpenHomeDailyRewardClaimedOverlayReady()
EndFunc   ;==>OpenHomeDailyRewardClosePointReady

; Re-capture and re-resolve immediately before the irreversible Claim input. A changed/moved/ambiguous
; button is rejected, and the one attempt is never retried.
Func OpenHomeDailyRewardIssueClaim($iExpectedX, $iExpectedY)
	If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, 0, False)
	Local $aFreshClaim[2]
	Local $iClaims = OpenHomeDailyRewardCaptureClaim($aFreshClaim)
	If $iClaims <> 1 Or $aFreshClaim[0] <> $iExpectedX Or $aFreshClaim[1] <> $iExpectedY Then _
		Return SetError(1, $iClaims, False)
	If Not OpenHomeNoGemInputReady() Then Return SetError(6, 0, False)
	If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, 0, False)
	; This route is admitted only when the exact ADB/minitouch input channel is ready.
	; Do not force a window ControlClick: PostMessage acceptance is not game delivery.
	Return NoPremiumPointClick($NO_PREMIUM_ACTION_DAILY_REWARD_CLAIM, $iExpectedX, $iExpectedY, 120, "#OpenHomeDailyRewardClaim", False)
EndFunc   ;==>OpenHomeDailyRewardIssueClaim

; After Claim, never accept an Okay/Confirm/sell/gem-conversion action. If the exact Daily Reward panel
; remains, one reversible close click is allowed; otherwise only a passive Home proof can succeed.
Func OpenHomeDailyRewardCloseAndProveHome(ByRef $bCloseIssued)
	$bCloseIssued = False
	If _Sleep(1200, True, True, False) Then Return SetError(2, 0, False)
	For $iAttempt = 1 To 8
		If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, 0, False)
		If OpenHomeCollectorsProveHome() Then Return True
		If $iAttempt = 1 And (OpenHomeDailyRewardOverlayReady() Or OpenHomeDailyRewardClaimedOverlayReady()) Then
			If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, 0, False)
			If Not OpenHomeNoGemInputReady() Then Return SetError(6, 0, False)
			If Not NoPremiumPointClick($NO_PREMIUM_ACTION_DAILY_REWARD_CLOSE, 759, 173, 120, "#OpenHomeDailyRewardClose", False) Then _
				Return SetError(3, 0, False)
			$bCloseIssued = True
		EndIf
		If $iAttempt < 8 And _Sleep(250, True, True, False) Then Return SetError(2, 0, False)
	Next
	Return SetError(4, 0, False)
EndFunc   ;==>OpenHomeDailyRewardCloseAndProveHome

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

Func OpenHomeLootCartOpenPointReady($iX, $iY)
	If $g_hBitmap = 0 Or Not _CheckPixel($aIsMain, False) Or _
			Not NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_LOOT_CART_OPEN, $iX, $iY) Then Return False
	Return _OpenHomeLootCartCueAt(Int($iX) - 15, Int($iY) - 26)
EndFunc   ;==>OpenHomeLootCartOpenPointReady

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
Func _OpenHomeLootCartCollectPanelFrameReady()
	If $g_hBitmap = 0 Then Return False
	Return _OpenHomePixelNear(395, 580, 0xFFFADA, 36) And _
			_OpenHomePixelNear(470, 580, 0xFFFFFF, 36) And _
			_OpenHomePixelNear(430, 570, 0xF6F2DB, 36) And _
			_OpenHomePixelNear(415, 628, 0xBFBBB0, 36) And _
			_OpenHomePixelNear(445, 628, 0x151614, 36) And _
			_OpenHomePixelNear(461, 628, 0x9FA879, 36) And _
			_OpenHomePixelNear(410, 550, 0xFFFFB7, 36) And _
			_OpenHomePixelNear(390, 600, 0x5C5C5A, 36)
EndFunc   ;==>_OpenHomeLootCartCollectPanelFrameReady

Func OpenHomeLootCartCollectPanelReady()
	If Not OpenHomeCollectorsCapture() Then Return False
	Return _OpenHomeLootCartCollectPanelFrameReady()
EndFunc   ;==>OpenHomeLootCartCollectPanelReady

Func OpenHomeLootCartCollectPointReady($iX, $iY)
	Return NoPremiumPermitTargetValid($NO_PREMIUM_ACTION_LOOT_CART_COLLECT, $iX, $iY) And _
			_OpenHomeLootCartCollectPanelFrameReady()
EndFunc   ;==>OpenHomeLootCartCollectPointReady

Func OpenHomeLootCartDetectCollect()
	For $iAttempt = 1 To 6
		If RunControlStopRequested() Or Not $g_bRunState Then Return SetError(2, 0, 0)
		If OpenHomeLootCartCollectPanelReady() Then Return LootCartObservationCreate($LOOT_CART_STATE_COLLECT_READY, 431, 608)
		If _Sleep(250, True, True, False) Then Return SetError(2, 0, 0)
	Next
	Return LootCartObservationCreate($LOOT_CART_STATE_COLLECT_MISSING)
EndFunc   ;==>OpenHomeLootCartDetectCollect

Func OpenHomeLootCartIssueOpen($iX, $iY)
	If RunControlStopRequested() Or Not $g_bRunState Or Not OpenHomeCollectorsProveHome() Then Return False
	If Not _CheckPixel($aIsMain, False) Then Return False
	If Not OpenHomeNoGemInputReady() Then Return SetError(6, 0, False)
	Local $bIssued = NoPremiumPointClick($NO_PREMIUM_ACTION_LOOT_CART_OPEN, Int($iX), Int($iY), 120, "#OpenHomeLootCart", True)
	If $bIssued Then RunEventLogMaintenanceLootCartOpenIssued(1)
	Return $bIssued
EndFunc   ;==>OpenHomeLootCartIssueOpen

Func OpenHomeLootCartIssueCollect($iX, $iY)
	If RunControlStopRequested() Or Not $g_bRunState Or Not OpenHomeLootCartCollectPanelReady() Then Return False
	If Not OpenHomeNoGemInputReady() Then Return SetError(6, 0, False)
	Local $bIssued = NoPremiumPointClick($NO_PREMIUM_ACTION_LOOT_CART_COLLECT, Int($iX), Int($iY), 120, "#OpenHomeLootCartCollect", True)
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
