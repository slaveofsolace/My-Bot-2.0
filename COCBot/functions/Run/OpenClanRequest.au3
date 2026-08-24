; #FUNCTION# ====================================================================================================================
; Name ..........: Open Clan request
; Description ...: Template-free, one-send Clan Castle request for an already-running exact BlueStacks 5 Home Village.
; Remarks .......: This adapter uses only fresh framebuffer pixels and the configured Click channel (ADB or WinAPI control). It never calls
;                  MyBot.run.dll, ImgLoc, XML templates, OCR, training, donation, battle, upgrades, or account switching.
; ===============================================================================================================================
#include-once

Global Const $OPEN_CLAN_REQUEST_ARMY_X = 39
Global Const $OPEN_CLAN_REQUEST_ARMY_Y = 585
Global Const $OPEN_CLAN_REQUEST_BUTTON_X = 761
Global Const $OPEN_CLAN_REQUEST_BUTTON_Y = 498
Global Const $OPEN_CLAN_REQUEST_SEND_X = 545
Global Const $OPEN_CLAN_REQUEST_SEND_Y = 478
Global Const $OPEN_CLAN_REQUEST_CANCEL_X = 316
Global Const $OPEN_CLAN_REQUEST_CANCEL_Y = 478
Global Const $OPEN_CLAN_REQUEST_CLOSE_X = 792
Global Const $OPEN_CLAN_REQUEST_CLOSE_Y = 187

; These structural anchors are approved against the committed redacted 860x732 Army Overview fixture.
; Keep this predicate independent from the variable troop cards and from every privacy mask.
Func _OpenClanRequestArmyOverviewFrameReady($bRequireAvailable = False)
	If $g_hBitmap = 0 Then Return False
	Local $bReady = _OpenHomePixelNear(50, 210, 0x9F6B42, 32) And _
			_OpenHomePixelNear(400, 210, 0x956245, 32) And _
			_OpenHomePixelNear(800, 210, 0x956245, 32) And _
			_OpenHomePixelNear(100, 555, 0x624336, 32) And _
			_OpenHomePixelNear(790, 250, 0xFFFCED, 28) And _
			_OpenHomePixelNear(790, 400, 0x6DBCF1, 36)
	If Not $bReady Or Not $bRequireAvailable Then Return $bReady
	Return _OpenHomePixelNear(740, 500, 0xB0E477, 32) And _
			_OpenHomePixelNear(750, 500, 0xB0E477, 32) And _
			_OpenHomePixelNear(770, 510, 0x8BD43A, 32) And _
			_OpenHomePixelNear(760, 485, 0x8BD43A, 32)
EndFunc   ;==>_OpenClanRequestArmyOverviewFrameReady

; The dialog cue requires both independently colored buttons plus the white message panel and frame.
Func _OpenClanRequestDialogFrameReady()
	If $g_hBitmap = 0 Then Return False
	Return _OpenHomePixelNear(200, 120, 0xEAEAE1, 28) And _
			_OpenHomePixelNear(430, 110, 0x635A57, 32) And _
			_OpenHomePixelNear(180, 200, 0xEAEAE1, 28) And _
			_OpenHomePixelNear(220, 330, 0xFFFFFF, 20) And _
			_OpenHomePixelNear(650, 330, 0xEAEAE1, 28) And _
			_OpenHomePixelNear(430, 320, 0x000000, 20) And _
			_OpenHomePixelNear(470, 450, 0xE3FA8F, 28) And _
			_OpenHomePixelNear(620, 450, 0xE4FB8F, 28) And _
			_OpenHomePixelNear(545, 510, 0x77C120, 32) And _
			_OpenHomePixelNear(240, 450, 0xFFCB7E, 28) And _
			_OpenHomePixelNear(390, 450, 0xFFCB7E, 28)
EndFunc   ;==>_OpenClanRequestDialogFrameReady

; These point predicates read only the current captured framebuffer. The one-shot permit
; gate invokes them once while minting and again immediately before the single egress.
Func _OpenClanRequestNeutralHomeFrameReady()
	If $g_hBitmap = 0 Then Return False
	If _OpenClanRequestDialogFrameReady() Or _OpenClanRequestArmyOverviewFrameReady(False) Then Return False
	Return _CheckPixel($aIsMain, False)
EndFunc   ;==>_OpenClanRequestNeutralHomeFrameReady

Func OpenClanRequestArmyOverviewPointReady($iX, $iY)
	If Int($iX) <> $OPEN_CLAN_REQUEST_ARMY_X Or Int($iY) <> $OPEN_CLAN_REQUEST_ARMY_Y Then Return False
	Return _OpenClanRequestNeutralHomeFrameReady()
EndFunc   ;==>OpenClanRequestArmyOverviewPointReady

Func OpenClanRequestRequestPointReady($iX, $iY)
	If Int($iX) <> $OPEN_CLAN_REQUEST_BUTTON_X Or Int($iY) <> $OPEN_CLAN_REQUEST_BUTTON_Y Then Return False
	Return _OpenClanRequestArmyOverviewFrameReady(True)
EndFunc   ;==>OpenClanRequestRequestPointReady

Func OpenClanRequestSendPointReady($iX, $iY)
	If Int($iX) <> $OPEN_CLAN_REQUEST_SEND_X Or Int($iY) <> $OPEN_CLAN_REQUEST_SEND_Y Then Return False
	Return _OpenClanRequestDialogFrameReady()
EndFunc   ;==>OpenClanRequestSendPointReady

Func OpenClanRequestCancelPointReady($iX, $iY)
	If Int($iX) <> $OPEN_CLAN_REQUEST_CANCEL_X Or Int($iY) <> $OPEN_CLAN_REQUEST_CANCEL_Y Then Return False
	Return _OpenClanRequestDialogFrameReady()
EndFunc   ;==>OpenClanRequestCancelPointReady

Func OpenClanRequestClosePointReady($iX, $iY)
	If Int($iX) <> $OPEN_CLAN_REQUEST_CLOSE_X Or Int($iY) <> $OPEN_CLAN_REQUEST_CLOSE_Y Then Return False
	Return _OpenClanRequestArmyOverviewFrameReady(False)
EndFunc   ;==>OpenClanRequestClosePointReady

Func OpenClanRequestArmyOverviewReady($bRequireAvailable = False)
	If Not OpenHomeCollectorsCapture() Then Return False
	Return _OpenClanRequestArmyOverviewFrameReady($bRequireAvailable)
EndFunc   ;==>OpenClanRequestArmyOverviewReady

Func OpenClanRequestDialogReady()
	If Not OpenHomeCollectorsCapture() Then Return False
	Return _OpenClanRequestDialogFrameReady()
EndFunc   ;==>OpenClanRequestDialogReady

Func OpenClanRequestProveNeutralHome()
	If Not OpenHomeCollectorsCapture() Then Return False
	Return _OpenClanRequestNeutralHomeFrameReady()
EndFunc   ;==>OpenClanRequestProveNeutralHome

Func OpenClanRequestOpenArmyOverview()
	If RunControlStopRequested() Or Not $g_bRunState Then Return False
	If Not OpenClanRequestProveNeutralHome() Then Return False
	If Not OpenHomeNoGemInputReady() Then Return SetError(6, 0, False)
	If RunControlStopRequested() Or Not $g_bRunState Then Return False
	If Not NoPremiumPointClick($NO_PREMIUM_ACTION_CLAN_REQUEST_ARMY, $OPEN_CLAN_REQUEST_ARMY_X, _
			$OPEN_CLAN_REQUEST_ARMY_Y, 120, "#OpenClanRequestArmy", True) Then Return False
	If _Sleep(400, True, True, False) Then Return False
	For $iAttempt = 1 To 10
		If RunControlStopRequested() Or Not $g_bRunState Then Return False
		If OpenClanRequestArmyOverviewReady(False) Then Return True
		If $iAttempt < 10 And _Sleep(250, True, True, False) Then Return False
	Next
	Return False
EndFunc   ;==>OpenClanRequestOpenArmyOverview

Func OpenClanRequestDetectState($sPhase)
	Local $bAfter = StringLower(StringStripWS(String($sPhase), $STR_STRIPALL)) = "after"
	Local $iAttempts = $bAfter ? 10 : 1
	For $iAttempt = 1 To $iAttempts
		If RunControlStopRequested() Or Not $g_bRunState Then Return 0
		If OpenClanRequestArmyOverviewReady(False) Then
			If _OpenClanRequestArmyOverviewFrameReady(True) Then _
				Return ClanRequestObservationCreate($CLAN_REQUEST_STATE_AVAILABLE, $OPEN_CLAN_REQUEST_BUTTON_X, $OPEN_CLAN_REQUEST_BUTTON_Y)
			Return ClanRequestObservationCreate($bAfter ? $CLAN_REQUEST_STATE_ALREADY_MADE : $CLAN_REQUEST_STATE_FULL_OR_UNAVAILABLE)
		EndIf
		If $iAttempt < $iAttempts And _Sleep(250, True, True, False) Then Return 0
	Next
	Return 0
EndFunc   ;==>OpenClanRequestDetectState

Func OpenClanRequestOpenDialog($iRequestX, $iRequestY)
	If RunControlStopRequested() Or Not $g_bRunState Then Return 0
	If Int($iRequestX) <> $OPEN_CLAN_REQUEST_BUTTON_X Or Int($iRequestY) <> $OPEN_CLAN_REQUEST_BUTTON_Y Then Return 0
	If Not OpenClanRequestArmyOverviewReady(True) Then Return 0
	If Not OpenHomeNoGemInputReady() Then Return SetError(6, 0, 0)
	If RunControlStopRequested() Or Not $g_bRunState Then Return 0
	If Not NoPremiumPointClick($NO_PREMIUM_ACTION_CLAN_REQUEST_REQUEST, $OPEN_CLAN_REQUEST_BUTTON_X, _
			$OPEN_CLAN_REQUEST_BUTTON_Y, 120, "#OpenClanRequestDialog", True) Then Return 0
	If _Sleep(300, True, True, False) Then Return 0
	For $iAttempt = 1 To 8
		If RunControlStopRequested() Or Not $g_bRunState Then Return 0
		If OpenClanRequestDialogReady() Then _
			Return ClanRequestObservationCreate($CLAN_REQUEST_STATE_SEND_READY, $OPEN_CLAN_REQUEST_SEND_X, $OPEN_CLAN_REQUEST_SEND_Y)
		If $iAttempt < 8 And _Sleep(250, True, True, False) Then Return 0
	Next
	Return 0
EndFunc   ;==>OpenClanRequestOpenDialog

Func OpenClanRequestIssueSend($iSendX, $iSendY)
	If RunControlStopRequested() Or Not $g_bRunState Then Return False
	If Int($iSendX) <> $OPEN_CLAN_REQUEST_SEND_X Or Int($iSendY) <> $OPEN_CLAN_REQUEST_SEND_Y Then Return False
	If Not OpenClanRequestDialogReady() Then Return False
	If Not OpenHomeNoGemInputReady() Then Return SetError(6, 0, False)
	If RunControlStopRequested() Or Not $g_bRunState Then Return False
	Return NoPremiumPointClick($NO_PREMIUM_ACTION_CLAN_REQUEST_SEND, $OPEN_CLAN_REQUEST_SEND_X, _
			$OPEN_CLAN_REQUEST_SEND_Y, 120, "#OpenClanRequestSend", True)
EndFunc   ;==>OpenClanRequestIssueSend

; Close only recognized request-owned overlays. A Stop authorizes no cleanup input.
Func OpenClanRequestCloseAndProveHome()
	For $iAction = 1 To 2
		If RunControlStopRequested() Or Not $g_bRunState Then Return False
		If OpenClanRequestDialogReady() Then
			If RunControlStopRequested() Or Not $g_bRunState Then Return False
			If Not OpenHomeNoGemInputReady() Then Return SetError(6, 0, False)
			If Not NoPremiumPointClick($NO_PREMIUM_ACTION_CLAN_REQUEST_CANCEL, $OPEN_CLAN_REQUEST_CANCEL_X, _
					$OPEN_CLAN_REQUEST_CANCEL_Y, 120, "#OpenClanRequestCancel", True) Then Return False
			If _Sleep(300, True, True, False) Then Return False
			ContinueLoop
		EndIf
		If OpenClanRequestArmyOverviewReady(False) Then
			If RunControlStopRequested() Or Not $g_bRunState Then Return False
			If Not OpenHomeNoGemInputReady() Then Return SetError(6, 0, False)
			If Not NoPremiumPointClick($NO_PREMIUM_ACTION_CLAN_REQUEST_CLOSE, $OPEN_CLAN_REQUEST_CLOSE_X, _
					$OPEN_CLAN_REQUEST_CLOSE_Y, 120, "#OpenClanRequestClose", True) Then Return False
			If _Sleep(300, True, True, False) Then Return False
			ContinueLoop
		EndIf
		Return OpenClanRequestProveNeutralHome()
	Next
	If RunControlStopRequested() Or Not $g_bRunState Then Return False
	Return OpenClanRequestProveNeutralHome()
EndFunc   ;==>OpenClanRequestCloseAndProveHome
