; #FUNCTION# ====================================================================================================================
; Name ..........: FindPos
; Description ...:
; Syntax ........: FindPos()
; Parameters ....:
; Return values .: None
; Author ........: Your Name
; Modified ......:
; Remarks .......: This file is part of MyBot, previously known as ClashGameBot. Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
; Related .......:
; Link ..........: https://github.com/MyBotRun/MyBot/wiki
; Example .......: No
; ===============================================================================================================================
Func FindPos()
	Local $aModernSurface = GetBlueStacks5ModernAdbSurfacePosition()
	Local $aModernViewport = 0
	If IsArray($aModernSurface) Then
		$aModernViewport = GetBlueStacks5ModernManualViewportPosition()
		If Not IsArray($aModernViewport) Then
			SetLog("Manual building location refused: the BlueStacks5 game viewport could not be proven", $COLOR_ERROR)
			Local $aInvalidPos[2] = [-1, -1]
			Return SetError(1, 0, $aInvalidPos)
		EndIf
		$g_aiBSpos[0] = $aModernViewport[0]
		$g_aiBSpos[1] = $aModernViewport[1]
	Else
		getBSPos()
	EndIf
	AndroidToFront(Default, "FindPos") ; Activate Android Window
	Local $wasDown = AndroidShieldForceDown(True, True)
	While 1
		If _IsPressed("01") Or _IsPressed("02") Then
			Local $Pos = MouseGetPos()
			; wait till released
			While _IsPressed("01") Or _IsPressed("02")
				Sleep(10)
			WEnd
			If IsArray($aModernViewport) Then
				If Not ManualViewportMapToFramebuffer($Pos[0], $Pos[1], $aModernViewport, $g_iAndroidClientWidth, $g_iAndroidClientHeight) Then
					SetLog("Click inside the visible Clash of Clans game viewport", $COLOR_WARNING)
					ContinueLoop
				EndIf
			Else
				; adjust Android Control Position
				$Pos[0] -= $g_aiBSpos[0]
				$Pos[1] -= $g_aiBSpos[1]
			EndIf
			; adjust village offset
			ConvertFromVillagePos($Pos[0], $Pos[1])
			AndroidShieldForceDown($wasDown, True)
			Return $Pos
		EndIf
		Sleep(10)
	WEnd
EndFunc   ;==>FindPos
