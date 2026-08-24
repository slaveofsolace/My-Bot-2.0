; #FUNCTION# ====================================================================================================================
; Name ..........: Window placement
; Description ...: Keeps restored native windows on a currently attached display.
; Remarks .......: Managed installed launches require the primary display. Direct native launches preserve valid negative
;                  coordinates on multi-monitor desktops while rejecting stale coordinates outside every physical display.
; ===============================================================================================================================
#include-once

Func WindowPlacementEnsureVisible($hWindow, ByRef $iSavedX, ByRef $iSavedY)
	If Not IsHWnd($hWindow) Or Not WinExists($hWindow) Then Return SetError(1, 0, False)

	Local $aWindow = WinGetPos($hWindow)
	If @error Or Not IsArray($aWindow) Or UBound($aWindow) < 4 Or $aWindow[2] <= 0 Or $aWindow[3] <= 0 Then _
		Return SetError(2, 0, False)

	If $g_bForcePrimaryWindow Then
		If WindowPlacementIntersectsPrimary($aWindow) Then Return SetExtended(0, True)
	Else
		Local $aMonitor = DllCall("user32.dll", "handle", "MonitorFromWindow", "hwnd", $hWindow, "dword", 0)
		If Not @error And IsArray($aMonitor) And $aMonitor[0] <> 0 Then Return SetExtended(0, True)
	EndIf

	; The primary display always contains the virtual-desktop origin. Keep a small margin when the
	; current desktop can accommodate it and fall back to the origin for compact displays.
	Local $iVisibleX = (@DesktopWidth >= $aWindow[2] + 128) ? 64 : 0
	Local $iVisibleY = (@DesktopHeight >= $aWindow[3] + 128) ? 64 : 0
	WinMove($hWindow, "", $iVisibleX, $iVisibleY)
	If @error Then Return SetError(3, 0, False)

	Local $aMoved = WinGetPos($hWindow)
	If @error Or Not IsArray($aMoved) Or UBound($aMoved) < 4 Then Return SetError(4, 0, False)
	If Not WindowPlacementIntersectsPrimary($aMoved) Then Return SetError(5, 0, False)

	$iSavedX = $aMoved[0]
	$iSavedY = $aMoved[1]
	Return SetExtended(1, True)
EndFunc   ;==>WindowPlacementEnsureVisible

Func WindowPlacementIntersectsPrimary(Const ByRef $aWindow)
	If Not IsArray($aWindow) Or UBound($aWindow) < 4 Or $aWindow[2] <= 0 Or $aWindow[3] <= 0 Then Return False
	Return $aWindow[0] < @DesktopWidth And $aWindow[1] < @DesktopHeight And _
		$aWindow[0] + $aWindow[2] > 0 And $aWindow[1] + $aWindow[3] > 0
EndFunc   ;==>WindowPlacementIntersectsPrimary
