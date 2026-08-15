; #FUNCTION# ====================================================================================================================
; Name ..........: CollectorBubbleRecognizer
; Description ...: Finds one Gold, Elixir, and Dark Elixir collection bubble from a captured 860x732 Home Village frame.
; Remarks .......: This is a clean-room pixel classifier. It deliberately does not call the inherited ImgLoc DLL or consume its
;                  encrypted templates. The caller still owns main-screen proof, cancellation, input receipts, and post-input proof.
; ===============================================================================================================================
#include-once

Global Const $eCollectorBubbleGold = 0, $eCollectorBubbleElixir = 1, $eCollectorBubbleDark = 2

Func _CollectorBubbleReadPixel(ByRef $tPixels, $iWidth, $iX, $iY, ByRef $iRed, ByRef $iGreen, ByRef $iBlue)
	Local $iOffset = (($iY * $iWidth) + $iX) * 4
	$iBlue = DllStructGetData($tPixels, 1, $iOffset + 1)
	$iGreen = DllStructGetData($tPixels, 1, $iOffset + 2)
	$iRed = DllStructGetData($tPixels, 1, $iOffset + 3)
EndFunc   ;==>_CollectorBubbleReadPixel

Func _CollectorBubbleIsGold($iRed, $iGreen, $iBlue)
	Return $iRed > 230 And $iGreen > 140 And $iGreen < 230 And $iBlue < 45
EndFunc   ;==>_CollectorBubbleIsGold

Func _CollectorBubbleIsElixir($iRed, $iGreen, $iBlue)
	Return $iRed > 175 And $iBlue > 150 And $iGreen < 135 And Abs($iRed - $iBlue) < 90
EndFunc   ;==>_CollectorBubbleIsElixir

Func _CollectorBubbleIsDark($iRed, $iGreen, $iBlue)
	Return _Max(_Max($iRed, $iGreen), $iBlue) < 35
EndFunc   ;==>_CollectorBubbleIsDark

Func _CollectorBubbleIsPale($iRed, $iGreen, $iBlue)
	Return $iRed > 180 And $iGreen > 180 And $iBlue > 130
EndFunc   ;==>_CollectorBubbleIsPale

Func _CollectorBubbleIsPurple($iRed, $iGreen, $iBlue)
	Return $iBlue > ($iRed * 0.85) And $iBlue > ($iGreen * 1.15) And _
			$iRed > 40 And $iRed < 180 And $iGreen > 20 And $iGreen < 140 And $iBlue > 50 And $iBlue < 190
EndFunc   ;==>_CollectorBubbleIsPurple

Func _CollectorBubbleWindowStats(ByRef $tPixels, $iWidth, $iCenterX, $iCenterY, ByRef $aCount, ByRef $aSumX, ByRef $aSumY, $iStep = 1)
	Local $iRed, $iGreen, $iBlue
	For $iY = $iCenterY - 16 To $iCenterY + 16 Step $iStep
		For $iX = $iCenterX - 16 To $iCenterX + 16 Step $iStep
			_CollectorBubbleReadPixel($tPixels, $iWidth, $iX, $iY, $iRed, $iGreen, $iBlue)
			If _CollectorBubbleIsGold($iRed, $iGreen, $iBlue) Then
				$aCount[0] += 1
				$aSumX[0] += $iX
				$aSumY[0] += $iY
			EndIf
			If _CollectorBubbleIsElixir($iRed, $iGreen, $iBlue) Then
				$aCount[1] += 1
				$aSumX[1] += $iX
				$aSumY[1] += $iY
			EndIf
			If _CollectorBubbleIsDark($iRed, $iGreen, $iBlue) Then $aCount[2] += 1
			If _CollectorBubbleIsPale($iRed, $iGreen, $iBlue) Then $aCount[3] += 1
			If _CollectorBubbleIsPurple($iRed, $iGreen, $iBlue) Then
				$aCount[4] += 1
				$aSumX[4] += $iX
				$aSumY[4] += $iY
			EndIf
		Next
	Next
EndFunc   ;==>_CollectorBubbleWindowStats

Func CollectorBubbleRecognize($hBitmap)
	Local $aFound[3][3] = [["collectmines", -1, -1], ["collectelix", -1, -1], ["collectdelix", -1, -1]]
	If $hBitmap = 0 Then Return SetError(1, 0, $aFound)

	Local $tBitmap = DllStructCreate("long Type;long Width;long Height;long WidthBytes;word Planes;word BitsPixel;ptr Bits")
	Local $aObject = DllCall("gdi32.dll", "int", "GetObjectW", "handle", $hBitmap, "int", DllStructGetSize($tBitmap), "struct*", $tBitmap)
	If @error Or Not IsArray($aObject) Or $aObject[0] = 0 Then Return SetError(2, 0, $aFound)

	Local $iWidth = DllStructGetData($tBitmap, "Width")
	Local $iHeight = Abs(DllStructGetData($tBitmap, "Height"))
	If $iWidth < 760 Or $iHeight < 620 Or $iWidth > 2048 Or $iHeight > 2048 Then Return SetError(3, 0, $aFound)

	Local $tInfo = DllStructCreate("dword Size;long Width;long Height;word Planes;word BitCount;dword Compression;dword SizeImage;long XPelsPerMeter;long YPelsPerMeter;dword ClrUsed;dword ClrImportant")
	DllStructSetData($tInfo, "Size", DllStructGetSize($tInfo))
	DllStructSetData($tInfo, "Width", $iWidth)
	DllStructSetData($tInfo, "Height", -$iHeight)
	DllStructSetData($tInfo, "Planes", 1)
	DllStructSetData($tInfo, "BitCount", 32)
	DllStructSetData($tInfo, "Compression", 0)
	Local $tPixels = DllStructCreate("byte[" & ($iWidth * $iHeight * 4) & "]")

	Local $aDC = DllCall("user32.dll", "handle", "GetDC", "hwnd", 0)
	If @error Or Not IsArray($aDC) Or $aDC[0] = 0 Then Return SetError(4, 0, $aFound)
	Local $hDC = $aDC[0]
	Local $aBits = DllCall("gdi32.dll", "int", "GetDIBits", "handle", $hDC, "handle", $hBitmap, "uint", 0, "uint", $iHeight, _
			"struct*", $tPixels, "struct*", $tInfo, "uint", 0)
	DllCall("user32.dll", "int", "ReleaseDC", "hwnd", 0, "handle", $hDC)
	If @error Or Not IsArray($aBits) Or $aBits[0] <> $iHeight Then Return SetError(5, 0, $aFound)

	Local $iFound = 0, $iRed, $iGreen, $iBlue, $iMaxX
	For $iY = 100 To _Min(600, $iHeight - 17) Step 4
		If Mod($iY - 100, 32) = 0 Then
			Local $vStop = Call("RunControlStop" & "Requested")
			Local $iStopError = @error
			If $iStopError = 0 And $vStop Then Return SetError(6, 0, $aFound)
		EndIf
		; The right-side resource HUD overlaps the search area only near the top. Village bubbles below it remain eligible.
		$iMaxX = ($iY < 181) ? _Min(730, $iWidth - 17) : _Min(800, $iWidth - 17)
		For $iX = 100 To $iMaxX Step 4
			_CollectorBubbleReadPixel($tPixels, $iWidth, $iX, $iY, $iRed, $iGreen, $iBlue)
			Local $bGoldCandidate = $aFound[$eCollectorBubbleGold][1] < 0 And _CollectorBubbleIsGold($iRed, $iGreen, $iBlue)
			Local $bElixirCandidate = $aFound[$eCollectorBubbleElixir][1] < 0 And _CollectorBubbleIsElixir($iRed, $iGreen, $iBlue)
			Local $bDarkCandidate = $aFound[$eCollectorBubbleDark][1] < 0 And _CollectorBubbleIsDark($iRed, $iGreen, $iBlue)
			If Not $bGoldCandidate And Not $bElixirCandidate And Not $bDarkCandidate Then ContinueLoop

			; A 9x9 coarse sample rejects storage/building colors before the full 33x33 count.
			Local $aCoarseCount[5] = [0, 0, 0, 0, 0]
			Local $aCoarseSumX[5] = [0, 0, 0, 0, 0]
			Local $aCoarseSumY[5] = [0, 0, 0, 0, 0]
			_CollectorBubbleWindowStats($tPixels, $iWidth, $iX, $iY, $aCoarseCount, $aCoarseSumX, $aCoarseSumY, 4)
			$bGoldCandidate = $bGoldCandidate And $aCoarseCount[0] >= 3 And $aCoarseCount[0] <= 9 And $aCoarseCount[3] >= 10
			$bElixirCandidate = $bElixirCandidate And $aCoarseCount[1] >= 8 And $aCoarseCount[1] <= 16 And $aCoarseCount[3] >= 10
			$bDarkCandidate = $bDarkCandidate And $aCoarseCount[2] >= 7 And $aCoarseCount[2] <= 17 And _
					$aCoarseCount[3] >= 10 And $aCoarseCount[4] >= 5
			If Not $bGoldCandidate And Not $bElixirCandidate And Not $bDarkCandidate Then ContinueLoop

			Local $aCount[5] = [0, 0, 0, 0, 0]
			Local $aSumX[5] = [0, 0, 0, 0, 0]
			Local $aSumY[5] = [0, 0, 0, 0, 0]
			_CollectorBubbleWindowStats($tPixels, $iWidth, $iX, $iY, $aCount, $aSumX, $aSumY)

			If $bGoldCandidate And $aCount[0] >= 50 And $aCount[0] <= 90 And $aCount[3] >= 180 Then
				$aFound[$eCollectorBubbleGold][1] = Int($aSumX[0] / $aCount[0])
				$aFound[$eCollectorBubbleGold][2] = Int($aSumY[0] / $aCount[0])
				$iFound += 1
			EndIf
			If $bElixirCandidate And $aCount[1] >= 120 And $aCount[1] <= 180 And $aCount[3] >= 180 Then
				$aFound[$eCollectorBubbleElixir][1] = Int($aSumX[1] / $aCount[1])
				$aFound[$eCollectorBubbleElixir][2] = Int($aSumY[1] / $aCount[1])
				$iFound += 1
			EndIf
			If $bDarkCandidate And $aCount[2] >= 100 And $aCount[2] <= 180 And $aCount[3] >= 180 And $aCount[4] >= 80 Then
				$aFound[$eCollectorBubbleDark][1] = Int($aSumX[4] / $aCount[4])
				$aFound[$eCollectorBubbleDark][2] = Int($aSumY[4] / $aCount[4])
				$iFound += 1
			EndIf
			If $iFound = 3 Then Return $aFound
		Next
	Next
	Return $aFound
EndFunc   ;==>CollectorBubbleRecognize
