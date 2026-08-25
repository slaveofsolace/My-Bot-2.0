; #FUNCTION# ====================================================================================================================
; Name ..........: Clean-room red-line detector
; Description ...: Bounded current-frame detector for the Clash no-deploy red line.
; Remarks .......: Reads only the already-captured in-memory game bitmap. It performs no capture, process, DLL,
;                  emulator, ADB, browser, shell, file, or input action.
; ===============================================================================================================================
#include-once

Global Const $CLEANROOM_REDLINE_MIN_POINTS = 50
Global Const $CLEANROOM_REDLINE_MAX_POINTS = 512
Global Const $CLEANROOM_REDLINE_SCAN_STEP = 3
Global Const $CLEANROOM_REDLINE_EDGE_BAND = 72

Func CleanRoomRedlineDetectorRuntimeReady()
	Return True
EndFunc   ;==>CleanRoomRedlineDetectorRuntimeReady

Func CleanRoomRedlineDetectCurrentFrame($sCocDiamond = "ECD", $iMinPoints = $CLEANROOM_REDLINE_MIN_POINTS)
	If $g_hBitmap = 0 Then Return SetError(1, 0, "")
	If Not IsInt($iMinPoints) Or $iMinPoints < 1 Or $iMinPoints > $CLEANROOM_REDLINE_MAX_POINTS Then Return SetError(2, 0, "")

	Local $aDiamond[4][2]
	_CleanRoomRedlineDecodeDiamond($sCocDiamond, $aDiamond)

	Local $iLeft = 8, $iRight = $g_iGAME_WIDTH - 9
	Local $iTop = 42, $iBottom = $g_iGAME_HEIGHT - 108
	If $iBottom > 626 + $g_iMidOffsetY Then $iBottom = 626 + $g_iMidOffsetY
	If $iBottom > $g_iGAME_HEIGHT - 1 Then $iBottom = $g_iGAME_HEIGHT - 1
	If $iTop < 0 Then $iTop = 0
	If $iLeft < 0 Then $iLeft = 0
	If $iRight >= $g_iGAME_WIDTH Then $iRight = $g_iGAME_WIDTH - 1
	If $iBottom <= $iTop Or $iRight <= $iLeft Then Return SetError(3, 0, "")

	Local $aPoints[$CLEANROOM_REDLINE_MAX_POINTS][2]
	Local $iCount = 0
	Local $iLastX = -9999, $iLastY = -9999

	For $iY = $iTop To $iBottom Step $CLEANROOM_REDLINE_SCAN_STEP
		For $iX = $iLeft To $iRight Step $CLEANROOM_REDLINE_SCAN_STEP
			If Not _CleanRoomRedlineNearDiamondEdge($iX, $iY, $aDiamond, $CLEANROOM_REDLINE_EDGE_BAND) Then ContinueLoop
			If Not _CleanRoomRedlineColorLooksLikeNoDeployRed($iX, $iY) Then ContinueLoop
			If Abs($iX - $iLastX) <= $CLEANROOM_REDLINE_SCAN_STEP And Abs($iY - $iLastY) <= $CLEANROOM_REDLINE_SCAN_STEP Then ContinueLoop
			$aPoints[$iCount][0] = $iX
			$aPoints[$iCount][1] = $iY
			$iCount += 1
			$iLastX = $iX
			$iLastY = $iY
			If $iCount >= $CLEANROOM_REDLINE_MAX_POINTS Then ExitLoop 2
		Next
	Next

	If $iCount < $iMinPoints Then Return SetError(4, $iCount, "")
	Return SetError(0, $iCount, _CleanRoomRedlinePointsToString($aPoints, $iCount))
EndFunc   ;==>CleanRoomRedlineDetectCurrentFrame

Func _CleanRoomRedlineDecodeDiamond($sCocDiamond, ByRef $aDiamond)
	Local $aFallback[4][2] = [ _
			[Int($g_iGAME_WIDTH / 2), 62 + $g_iMidOffsetY], _
			[$g_iGAME_WIDTH - 18, 326 + $g_iMidOffsetY], _
			[Int($g_iGAME_WIDTH / 2), 626 + $g_iMidOffsetY], _
			[18, 326 + $g_iMidOffsetY] _
			]

	Local $sDiamond = StringStripWS(String($sCocDiamond), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sDiamond <> "" And StringUpper($sDiamond) <> "ECD" Then
		Local $aRaw = StringSplit($sDiamond, "|", $STR_NOCOUNT)
		If UBound($aRaw) >= 4 Then
			Local $bValid = True
			For $iPoint = 0 To 3
				Local $aXY = StringSplit($aRaw[$iPoint], ",", $STR_NOCOUNT)
				If UBound($aXY) < 2 Or Not StringIsInt(StringStripWS($aXY[0], $STR_STRIPALL)) Or _
						Not StringIsInt(StringStripWS($aXY[1], $STR_STRIPALL)) Then
					$bValid = False
					ExitLoop
				EndIf
				$aDiamond[$iPoint][0] = Int(StringStripWS($aXY[0], $STR_STRIPALL))
				$aDiamond[$iPoint][1] = Int(StringStripWS($aXY[1], $STR_STRIPALL))
			Next
			If $bValid Then Return True
		EndIf
	EndIf

	For $iPoint = 0 To 3
		$aDiamond[$iPoint][0] = $aFallback[$iPoint][0]
		$aDiamond[$iPoint][1] = $aFallback[$iPoint][1]
	Next
	Return False
EndFunc   ;==>_CleanRoomRedlineDecodeDiamond

Func _CleanRoomRedlineColorLooksLikeNoDeployRed($iX, $iY)
	Local $sColor = _GetPixelColor($iX, $iY)
	If StringLen($sColor) < 6 Then Return False
	Local $iRed = Dec(StringLeft($sColor, 2))
	Local $iGreen = Dec(StringMid($sColor, 3, 2))
	Local $iBlue = Dec(StringRight($sColor, 2))

	If $iRed < 168 Then Return False
	If $iGreen < 18 Or $iGreen > 150 Then Return False
	If $iBlue < 18 Or $iBlue > 165 Then Return False
	If ($iRed - $iGreen) < 45 Then Return False
	If ($iRed - $iBlue) < 35 Then Return False
	Return True
EndFunc   ;==>_CleanRoomRedlineColorLooksLikeNoDeployRed

Func _CleanRoomRedlineNearDiamondEdge($iX, $iY, ByRef $aDiamond, $iBand)
	For $iSide = 0 To 3
		Local $iNext = Mod($iSide + 1, 4)
		If _CleanRoomRedlinePointLineDistance($iX, $iY, $aDiamond[$iSide][0], $aDiamond[$iSide][1], _
				$aDiamond[$iNext][0], $aDiamond[$iNext][1]) <= $iBand Then Return True
	Next
	Return False
EndFunc   ;==>_CleanRoomRedlineNearDiamondEdge

Func _CleanRoomRedlinePointLineDistance($iX, $iY, $iX1, $iY1, $iX2, $iY2)
	Local $iDx = $iX2 - $iX1
	Local $iDy = $iY2 - $iY1
	Local $iLengthSquared = $iDx * $iDx + $iDy * $iDy
	If $iLengthSquared = 0 Then Return 99999
	Local $fT = (($iX - $iX1) * $iDx + ($iY - $iY1) * $iDy) / $iLengthSquared
	If $fT < 0 Or $fT > 1 Then Return 99999
	Local $fProjX = $iX1 + $fT * $iDx
	Local $fProjY = $iY1 + $fT * $iDy
	Local $fOffX = $iX - $fProjX
	Local $fOffY = $iY - $fProjY
	Return Sqrt($fOffX * $fOffX + $fOffY * $fOffY)
EndFunc   ;==>_CleanRoomRedlinePointLineDistance

Func _CleanRoomRedlinePointsToString(ByRef $aPoints, $iCount)
	Local $sResult = ""
	For $iPoint = 0 To $iCount - 1
		$sResult &= "|" & $aPoints[$iPoint][0] & "," & $aPoints[$iPoint][1]
	Next
	Return StringMid($sResult, 2)
EndFunc   ;==>_CleanRoomRedlinePointsToString
