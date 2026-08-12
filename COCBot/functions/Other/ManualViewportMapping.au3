; #FUNCTION# ====================================================================================================================
; Name ..........: ManualViewportFindBlueStacks5Surface
; Description ...: Returns the one proven visible BlueStacksApp render child contained by a Qt player window.
; ===============================================================================================================================
Func ManualViewportFindBlueStacks5Surface($hWindow, $iFramebufferWidth, $iFramebufferHeight)
	If Not IsHWnd($hWindow) Or $iFramebufferWidth <= 0 Or $iFramebufferHeight <= 0 Then Return 0
	If BitAND(WinGetState($hWindow), 16) <> 0 Then Return 0
	Local $aWindow = WinGetPos($hWindow)
	If Not IsArray($aWindow) Then Return 0
	Local $aChildren = _WinAPI_EnumChildWindows($hWindow, False)
	If Not IsArray($aChildren) Then Return 0
	Local $iRootPid = WinGetProcess($hWindow)
	Local $fExpectedRatio = $iFramebufferWidth / $iFramebufferHeight
	Local $aViewport = 0
	Local $iFound = 0
	For $i = 1 To $aChildren[0][0]
		Local $hChild = $aChildren[$i][0]
		If StringCompare(_WinAPI_GetClassName($hChild), "BlueStacksApp", 0) <> 0 Then ContinueLoop
		If WinGetProcess($hChild) <> $iRootPid Or BitAND(WinGetState($hChild), 2) = 0 Then ContinueLoop
		Local $aCandidate = WinGetPos($hChild)
		If Not IsArray($aCandidate) Or $aCandidate[2] < 400 Or $aCandidate[3] < 400 Then ContinueLoop
		If Abs(($aCandidate[2] / $aCandidate[3]) - $fExpectedRatio) > 0.01 Then ContinueLoop
		If $aCandidate[0] < $aWindow[0] Or $aCandidate[1] < $aWindow[1] Or _
			$aCandidate[0] + $aCandidate[2] > $aWindow[0] + $aWindow[2] + 2 Or _
			$aCandidate[1] + $aCandidate[3] > $aWindow[1] + $aWindow[3] + 2 Then ContinueLoop
		$aViewport = $aCandidate
		$iFound += 1
	Next
	If $iFound <> 1 Then Return 0
	Return $aViewport
EndFunc   ;==>ManualViewportFindBlueStacks5Surface

; #FUNCTION# ====================================================================================================================
; Name ..........: ManualViewportMapToFramebuffer
; Description ...: Maps a desktop point inside a proven emulator viewport to its ADB framebuffer pixel.
; ===============================================================================================================================
Func ManualViewportMapToFramebuffer(ByRef $iX, ByRef $iY, $aViewport, $iFramebufferWidth, $iFramebufferHeight)
	If Not IsArray($aViewport) Or UBound($aViewport) < 4 Then Return False
	If $aViewport[2] <= 0 Or $aViewport[3] <= 0 Or $iFramebufferWidth <= 0 Or $iFramebufferHeight <= 0 Then Return False
	Local $iViewportX = $iX - $aViewport[0]
	Local $iViewportY = $iY - $aViewport[1]
	If $iViewportX < 0 Or $iViewportY < 0 Or $iViewportX >= $aViewport[2] Or $iViewportY >= $aViewport[3] Then Return False
	; Map pixel centers so scaled surfaces keep both edges aligned without an accumulating offset.
	$iX = Int((($iViewportX + 0.5) * $iFramebufferWidth) / $aViewport[2])
	$iY = Int((($iViewportY + 0.5) * $iFramebufferHeight) / $aViewport[3])
	Return True
EndFunc   ;==>ManualViewportMapToFramebuffer
