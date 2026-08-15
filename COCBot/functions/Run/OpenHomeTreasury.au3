; #FUNCTION# ====================================================================================================================
; Name ..........: Open Home Treasury
; Description ...: Template-free Treasury unavailable-state adapter for an exact BlueStacks 5 Home Village.
; Remarks .......: The adapter may select one configured Clan Castle, open its exact Treasury action, and close the exact window.
;                  It never calls MyBot.run.dll, ImgLoc, OCR, LocateClanCastle, ClickOkay, or a fallback coordinate. A visibly
;                  full/actionable Treasury remains fail-closed until its Collect and confirmation states have independent proof.
; ===============================================================================================================================
#include-once

Global Const $OPEN_HOME_TREASURY_ENTRY_X = 574
Global Const $OPEN_HOME_TREASURY_ENTRY_Y = 608
Global Const $OPEN_HOME_TREASURY_CLOSE_X = 699
Global Const $OPEN_HOME_TREASURY_CLOSE_Y = 182

Func _OpenHomeTreasuryStopRequested()
	Return RunControlStopRequested() Or Not $g_bRunState
EndFunc   ;==>_OpenHomeTreasuryStopRequested

; Five independent action-card anchors bind this state to a selected Clan Castle, rather than to an
; arbitrary selected Home building. The title strip and Info/Clan/Treasury/Guard icon colors are all
; outside the resource HUD and the variable village playfield.
Func _OpenHomeTreasurySelectedFrameReady()
	If $g_hBitmap = 0 Then Return False
	Return _OpenHomePixelNear(430, 550, 0xFFFFB7, 36) And _
			_OpenHomePixelNear(160, 575, 0xF3F2DE, 32) And _
			_OpenHomePixelNear(196, 608, 0x387CB0, 40) And _
			_OpenHomePixelNear(480, 608, 0xC6735F, 44) And _
			_OpenHomePixelNear(574, 608, 0xCB9832, 44) And _
			_OpenHomePixelNear(670, 575, 0xEDF0D8, 32) And _
			_OpenHomePixelNear(670, 608, 0x8A6A27, 44)
EndFunc   ;==>_OpenHomeTreasurySelectedFrameReady

Func OpenHomeTreasurySelectedReady()
	If Not OpenHomeCollectorsCapture() Then Return False
	Return _CheckPixel($aIsMain, False) And _OpenHomeTreasurySelectedFrameReady()
EndFunc   ;==>OpenHomeTreasurySelectedReady

; Current-client 860x732 Treasury panel. The red close control, neutral header/content frame, and all
; three resource tracks must agree before the panel is treated as owned.
Func _OpenHomeTreasuryWindowFrameReady()
	If $g_hBitmap = 0 Then Return False
	Return _OpenHomePixelNear(160, 210, 0x5E5451, 32) And _
			_OpenHomePixelNear(430, 210, 0xE8E8E0, 28) And _
			_OpenHomePixelNear(699, 182, 0xFFFFFF, 20) And _
			_OpenHomePixelNear(685, 182, 0xFF6E76, 32) And _
			_OpenHomePixelNear(711, 182, 0xFF6E74, 32) And _
			_OpenHomePixelNear(430, 235, 0x6D6662, 32) And _
			_OpenHomePixelNear(430, 283, 0x6E6763, 32) And _
			_OpenHomePixelNear(430, 330, 0x6E6763, 32)
EndFunc   ;==>_OpenHomeTreasuryWindowFrameReady

Func OpenHomeTreasuryWindowReady()
	If Not OpenHomeCollectorsCapture() Then Return False
	Return _OpenHomeTreasuryWindowFrameReady()
EndFunc   ;==>OpenHomeTreasuryWindowReady

; A full bar reaches the right edge with a green fill. All three gray endpoints prove that this
; Treasury is not full under the route's conservative full-only transfer policy.
Func _OpenHomeTreasuryAllBarEndsGray()
	Return _OpenHomePixelNear(695, 235, 0x6E6763, 32) And _
			_OpenHomePixelNear(695, 283, 0x6E6763, 32) And _
			_OpenHomePixelNear(695, 330, 0x6E6763, 32) And _
			_OpenHomePixelNear(370, 475, 0xC7C7C7, 32) And _
			_OpenHomePixelNear(500, 510, 0x959595, 32)
EndFunc   ;==>_OpenHomeTreasuryAllBarEndsGray

Func OpenHomeTreasuryDetectCastle()
	If _OpenHomeTreasuryStopRequested() Then Return 0
	If Not OpenHomeCollectorsCapture() Or Not _CheckPixel($aIsMain, False) Then Return 0
	If _OpenHomeTreasurySelectedFrameReady() Then _
		Return TreasuryObservationCreate($TREASURY_STATE_CASTLE_SELECTED)
	If Not IsArray($g_aiClanCastlePos) Or UBound($g_aiClanCastlePos) < 2 Then _
		Return TreasuryObservationCreate($TREASURY_STATE_CASTLE_MISSING)
	If Int($g_aiClanCastlePos[0]) < 0 Or Int($g_aiClanCastlePos[1]) < 0 Or Not isInsideDiamond($g_aiClanCastlePos) Then _
		Return TreasuryObservationCreate($TREASURY_STATE_CASTLE_MISSING)
	Return TreasuryObservationCreate($TREASURY_STATE_CASTLE_READY, Int($g_aiClanCastlePos[0]), Int($g_aiClanCastlePos[1]))
EndFunc   ;==>OpenHomeTreasuryDetectCastle

Func OpenHomeTreasuryIssueCastle($iX, $iY)
	If _OpenHomeTreasuryStopRequested() Or Not OpenHomeCollectorsProveHome() Then Return False
	If _OpenHomeTreasuryStopRequested() Then Return False
	Local $bIssued = Click(Int($iX), Int($iY), 1, 120, "#OpenHomeTreasuryCastle")
	If $bIssued Then RunEventLogMaintenanceTreasuryCastleIssued()
	Return $bIssued
EndFunc   ;==>OpenHomeTreasuryIssueCastle

Func OpenHomeTreasuryDetectEntry()
	For $iAttempt = 1 To 8
		If _OpenHomeTreasuryStopRequested() Then Return 0
		If OpenHomeTreasurySelectedReady() Then _
			Return TreasuryObservationCreate($TREASURY_STATE_ENTRY_READY, $OPEN_HOME_TREASURY_ENTRY_X, $OPEN_HOME_TREASURY_ENTRY_Y)
		If $iAttempt < 8 And _Sleep(250, True, True, False) Then Return 0
	Next
	Return TreasuryObservationCreate($TREASURY_STATE_ENTRY_MISSING)
EndFunc   ;==>OpenHomeTreasuryDetectEntry

Func OpenHomeTreasuryIssueEntry($iX, $iY)
	If _OpenHomeTreasuryStopRequested() Then Return False
	If Int($iX) <> $OPEN_HOME_TREASURY_ENTRY_X Or Int($iY) <> $OPEN_HOME_TREASURY_ENTRY_Y Then Return False
	If Not OpenHomeTreasurySelectedReady() Or _OpenHomeTreasuryStopRequested() Then Return False
	Local $bIssued = Click(Int($iX), Int($iY), 1, 120, "#OpenHomeTreasuryEntry")
	If $bIssued Then RunEventLogMaintenanceTreasuryEntryIssued()
	Return $bIssued
EndFunc   ;==>OpenHomeTreasuryIssueEntry

Func OpenHomeTreasuryDetectCollect()
	For $iAttempt = 1 To 10
		If _OpenHomeTreasuryStopRequested() Then Return 0
		If OpenHomeTreasuryWindowReady() Then
			If _OpenHomeTreasuryAllBarEndsGray() Then Return TreasuryObservationCreate($TREASURY_STATE_NOT_FULL)
			; Never infer a transferable balance or a Collect target from an unreviewed green/partial state.
			Return TreasuryObservationCreate($TREASURY_STATE_COLLECT_MISSING)
		EndIf
		If $iAttempt < 10 And _Sleep(250, True, True, False) Then Return 0
	Next
	Return 0
EndFunc   ;==>OpenHomeTreasuryDetectCollect

Func OpenHomeTreasuryIssueCollect($iX, $iY)
	Return False
EndFunc   ;==>OpenHomeTreasuryIssueCollect

Func OpenHomeTreasuryDetectConfirm()
	Return TreasuryObservationCreate($TREASURY_STATE_CONFIRM_MISSING)
EndFunc   ;==>OpenHomeTreasuryDetectConfirm

Func OpenHomeTreasuryIssueConfirm($iX, $iY)
	Return False
EndFunc   ;==>OpenHomeTreasuryIssueConfirm

Func OpenHomeTreasuryCleanup()
	If _OpenHomeTreasuryStopRequested() Then Return TreasuryCleanupCreate(0, False, False)
	If OpenHomeCollectorsProveHome() And _OpenHomeTreasurySelectedFrameReady() Then _
		Return TreasuryCleanupCreate(0, False, True)
	If Not OpenHomeTreasuryWindowReady() Then Return TreasuryCleanupCreate(0, False, False)
	If _OpenHomeTreasuryStopRequested() Then Return TreasuryCleanupCreate(0, False, False)
	If Not Click($OPEN_HOME_TREASURY_CLOSE_X, $OPEN_HOME_TREASURY_CLOSE_Y, 1, 120, "#OpenHomeTreasuryClose") Then _
		Return TreasuryCleanupCreate(1, False, False)
	If _Sleep(350, True, True, False) Then Return TreasuryCleanupCreate(1, True, False)
	If _OpenHomeTreasuryStopRequested() Then Return TreasuryCleanupCreate(1, True, False)
	Return TreasuryCleanupCreate(1, True, OpenHomeCollectorsProveHome())
EndFunc   ;==>OpenHomeTreasuryCleanup
