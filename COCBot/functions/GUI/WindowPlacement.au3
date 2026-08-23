; #FUNCTION# ====================================================================================================================
; Name ..........: Window placement
; Description ...: Keeps restored native windows on a currently attached display.
; Remarks .......: MonitorFromWindow with MONITOR_DEFAULTTONULL preserves valid negative coordinates on multi-monitor desktops
;                  while rejecting stale coordinates that no longer intersect any physical display.
; ===============================================================================================================================
#include-once

Func WindowPlacementEnsureVisible($hWindow, ByRef $iSavedX, ByRef $iSavedY)
	If Not IsHWnd($hWindow) Or Not WinExists($hWindow) Then Return SetError(1, 0, False)

	Local $aMonitor = DllCall("user32.dll", "handle", "MonitorFromWindow", "hwnd", $hWindow, "dword", 0)
	If Not @error And IsArray($aMonitor) And $aMonitor[0] <> 0 Then Return SetExtended(0, True)

	Local $aWindow = WinGetPos($hWindow)
	If @error Or Not IsArray($aWindow) Or UBound($aWindow) < 4 Or $aWindow[2] <= 0 Or $aWindow[3] <= 0 Then _
		Return SetError(2, 0, False)

	; The primary display always contains the virtual-desktop origin. Keep a small margin when the
	; current desktop can accommodate it and fall back to the origin for compact displays.
	Local $iVisibleX = (@DesktopWidth >= $aWindow[2] + 128) ? 64 : 0
	Local $iVisibleY = (@DesktopHeight >= $aWindow[3] + 128) ? 64 : 0
	WinMove($hWindow, "", $iVisibleX, $iVisibleY)
	If @error Then Return SetError(3, 0, False)

	Local $aMoved = WinGetPos($hWindow)
	If @error Or Not IsArray($aMoved) Or UBound($aMoved) < 4 Then Return SetError(4, 0, False)
	Local $aMovedMonitor = DllCall("user32.dll", "handle", "MonitorFromWindow", "hwnd", $hWindow, "dword", 0)
	If @error Or Not IsArray($aMovedMonitor) Or $aMovedMonitor[0] = 0 Then Return SetError(5, 0, False)

	$iSavedX = $aMoved[0]
	$iSavedY = $aMoved[1]
	Return SetExtended(1, True)
EndFunc   ;==>WindowPlacementEnsureVisible
