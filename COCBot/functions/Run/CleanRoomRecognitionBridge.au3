; #FUNCTION# ====================================================================================================================
; Name ..........: Clean-room recognition bridge
; Description ...: Inert, read-only native access to reviewed pure coordinate transforms and fixture replay attestation.
; Remarks .......: This module has no capture, process, emulator, input, DLL, or legacy-wire surface.
; ===============================================================================================================================
#include-once

#include "CleanRoomRecognitionContract.generated.au3"

Func CleanRoomRecognitionRuntimeStatus($sExport)
	If StringCompare($sExport, "GetOffSetRedline", 1) = 0 Or _
			StringCompare($sExport, "GetDeployableNextTo", 1) = 0 Then _
		Return $CLEANROOM_RECOGNITION_STATUS_READ_ONLY_PURE
	If StringCompare($sExport, "FindTile", 1) = 0 Then _
		Return $CLEANROOM_RECOGNITION_STATUS_FIXTURE_REPLAY_ONLY

	Local $aUnavailable = StringSplit($CLEANROOM_RECOGNITION_UNAVAILABLE_EXPORTS, "|", 2)
	Local $sUnavailable
	For $sUnavailable In $aUnavailable
		If StringCompare($sExport, $sUnavailable, 1) = 0 Then Return $CLEANROOM_RECOGNITION_STATUS_UNAVAILABLE
	Next
	Return $CLEANROOM_RECOGNITION_STATUS_REJECTED
EndFunc   ;==>CleanRoomRecognitionRuntimeStatus

Func CleanRoomRecognitionRuntimeAvailable($sExport)
	Return CleanRoomRecognitionRuntimeStatus($sExport) = $CLEANROOM_RECOGNITION_STATUS_READ_ONLY_PURE
EndFunc   ;==>CleanRoomRecognitionRuntimeAvailable

Func CleanRoomRecognitionProviderState($sExport = "")
	If StringStripWS(String($sExport), 8) = "" Then Return $CLEANROOM_RECOGNITION_DEFAULT_PROVIDER
	Local $sStatus = CleanRoomRecognitionRuntimeStatus($sExport)
	If $sStatus = $CLEANROOM_RECOGNITION_STATUS_READ_ONLY_PURE Or _
			$sStatus = $CLEANROOM_RECOGNITION_STATUS_FIXTURE_REPLAY_ONLY Then _
		Return $CLEANROOM_RECOGNITION_PROVIDER_CLEANROOMLOCAL
	Return $CLEANROOM_RECOGNITION_PROVIDER_UNAVAILABLE
EndFunc   ;==>CleanRoomRecognitionProviderState

Func CleanRoomRecognitionProviderReason($sExport = "")
	Local $sProvider = CleanRoomRecognitionProviderState($sExport)
	If $sProvider = $CLEANROOM_RECOGNITION_PROVIDER_CLEANROOMLOCAL Then _
		Return "CleanRoomLocal supports only bounded local-profile calibration, verified fixture replay, and pure coordinate transforms; it does not authorize full-profile BotStart."
	If $sProvider = $CLEANROOM_RECOGNITION_PROVIDER_INHERITEDAUTHORIZED Then _
		Return $CLEANROOM_RECOGNITION_INHERITEDAUTHORIZED_REASON
	Return $CLEANROOM_RECOGNITION_UNAVAILABLE_REASON
EndFunc   ;==>CleanRoomRecognitionProviderReason

; This proves only that an already-hashed fixture receipt names the exact reviewed fixture bytes.
; It deliberately returns no match box, center, or other coordinate that could be reused as game input.
Func CleanRoomRecognitionFixtureReplayAttested($sAssetId, $sFixtureId, $sImageSha256, $sMetadataSha256, $iWidth, $iHeight)
	If StringCompare($sAssetId, $CLEANROOM_RECOGNITION_FIXTURE_ASSET_ID, 1) <> 0 Then Return SetError(1, 0, False)
	If StringCompare($sFixtureId, $CLEANROOM_RECOGNITION_FIXTURE_ID, 1) <> 0 Then Return SetError(2, 0, False)
	If StringCompare($sImageSha256, $CLEANROOM_RECOGNITION_FIXTURE_IMAGE_SHA256, 1) <> 0 Then Return SetError(3, 0, False)
	If StringCompare($sMetadataSha256, $CLEANROOM_RECOGNITION_FIXTURE_METADATA_SHA256, 1) <> 0 Then Return SetError(4, 0, False)
	If Not IsInt($iWidth) Or Not IsInt($iHeight) Or _
			$iWidth <> $CLEANROOM_RECOGNITION_FIXTURE_WIDTH Or $iHeight <> $CLEANROOM_RECOGNITION_FIXTURE_HEIGHT Then _
		Return SetError(5, 0, False)
	Return SetError(0, 0, True)
EndFunc   ;==>CleanRoomRecognitionFixtureReplayAttested

Func _CleanRoomRecognitionDimensionsValid($iWidth, $iHeight, $iMaxResults)
	If Not IsInt($iWidth) Or Not IsInt($iHeight) Or Not IsInt($iMaxResults) Then Return False
	If $iWidth < 1 Or $iWidth > $CLEANROOM_RECOGNITION_MAX_WIDTH Then Return False
	If $iHeight < 1 Or $iHeight > $CLEANROOM_RECOGNITION_MAX_HEIGHT Then Return False
	If $iWidth * $iHeight > $CLEANROOM_RECOGNITION_MAX_PIXELS Then Return False
	Return $iMaxResults >= 1 And $iMaxResults <= $CLEANROOM_RECOGNITION_MAX_RESULTS
EndFunc   ;==>_CleanRoomRecognitionDimensionsValid

Func _CleanRoomRecognitionPointsValid(ByRef $aPoints, $iWidth, $iHeight)
	If Not IsArray($aPoints) Or UBound($aPoints, 0) <> 2 Or UBound($aPoints, 2) <> 2 Then Return False
	Local $iCount = UBound($aPoints, 1)
	If $iCount < 1 Or $iCount > $CLEANROOM_RECOGNITION_MAX_POINTS Then Return False
	For $iPoint = 0 To $iCount - 1
		If Not IsInt($aPoints[$iPoint][0]) Or Not IsInt($aPoints[$iPoint][1]) Then Return False
		If $aPoints[$iPoint][0] < 0 Or $aPoints[$iPoint][0] >= $iWidth Then Return False
		If $aPoints[$iPoint][1] < 0 Or $aPoints[$iPoint][1] >= $iHeight Then Return False
	Next
	Return True
EndFunc   ;==>_CleanRoomRecognitionPointsValid

Func _CleanRoomRecognitionPointExists(ByRef $aPoints, $iCount, $iX, $iY)
	For $iPoint = 0 To $iCount - 1
		If $aPoints[$iPoint][0] = $iX And $aPoints[$iPoint][1] = $iY Then Return True
	Next
	Return False
EndFunc   ;==>_CleanRoomRecognitionPointExists

Func _CleanRoomRecognitionOffsetPoint($iX, $iY, $iOriginX, $iOriginY, $iDistance, $iWidth, $iHeight, ByRef $iOutputX, ByRef $iOutputY)
	Local $iDeltaX = $iX - $iOriginX
	Local $iDeltaY = $iY - $iOriginY
	If $iDeltaX = 0 And $iDeltaY = 0 Then Return False
	Local $fLength = Sqrt($iDeltaX * $iDeltaX + $iDeltaY * $iDeltaY)
	$iOutputX = Int(Round($iX + ($iDeltaX / $fLength) * $iDistance, 0))
	$iOutputY = Int(Round($iY + ($iDeltaY / $fLength) * $iDistance, 0))
	If $iOutputX < 0 Then $iOutputX = 0
	If $iOutputY < 0 Then $iOutputY = 0
	If $iOutputX >= $iWidth Then $iOutputX = $iWidth - 1
	If $iOutputY >= $iHeight Then $iOutputY = $iHeight - 1
	Return True
EndFunc   ;==>_CleanRoomRecognitionOffsetPoint

; Typed pure transform. The result count is returned; only rows below that count are meaningful.
Func CleanRoomRecognitionGetOffsetRedline(ByRef $aPoints, $sArea, $iDistance, $iWidth, $iHeight, ByRef $aOutput, $iMaxResults = 8)
	$aOutput = 0
	If Not _CleanRoomRecognitionDimensionsValid($iWidth, $iHeight, $iMaxResults) Then Return SetError(1, 0, 0)
	If Not _CleanRoomRecognitionPointsValid($aPoints, $iWidth, $iHeight) Then Return SetError(2, 0, 0)
	If Not IsInt($iDistance) Or $iDistance < 1 Or $iDistance > 64 Then Return SetError(3, 0, 0)
	If StringCompare($sArea, "TL", 1) <> 0 And StringCompare($sArea, "BL", 1) <> 0 And _
			StringCompare($sArea, "BR", 1) <> 0 And StringCompare($sArea, "TR", 1) <> 0 Then _
		Return SetError(3, 0, 0)

	Local $aResult[$iMaxResults][2]
	Local $iResultCount = 0
	Local $iCenterX = Int($iWidth / 2)
	Local $iCenterY = Int($iHeight / 2)
	For $iPoint = 0 To UBound($aPoints, 1) - 1
		Local $sPointArea = ($aPoints[$iPoint][1] <= $iCenterY ? "T" : "B") & _
				($aPoints[$iPoint][0] <= $iCenterX ? "L" : "R")
		If StringCompare($sPointArea, $sArea, 1) <> 0 Then ContinueLoop
		Local $iOutputX = 0
		Local $iOutputY = 0
		If Not _CleanRoomRecognitionOffsetPoint($aPoints[$iPoint][0], $aPoints[$iPoint][1], $iCenterX, $iCenterY, _
				$iDistance, $iWidth, $iHeight, $iOutputX, $iOutputY) Then Return SetError(4, 0, 0)
		If Not _CleanRoomRecognitionPointExists($aResult, $iResultCount, $iOutputX, $iOutputY) Then
			$aResult[$iResultCount][0] = $iOutputX
			$aResult[$iResultCount][1] = $iOutputY
			$iResultCount += 1
			If $iResultCount >= $iMaxResults Then ExitLoop
		EndIf
	Next
	$aOutput = $aResult
	Return SetError(0, 0, $iResultCount)
EndFunc   ;==>CleanRoomRecognitionGetOffsetRedline

; Typed pure transform. It does not read or retain the legacy recognizer's hidden redline state.
Func CleanRoomRecognitionGetDeployableNextTo(ByRef $aTargets, ByRef $aRedlinePoints, $iDistance, $iWidth, $iHeight, ByRef $aOutput, $iMaxResults = 8)
	$aOutput = 0
	If Not _CleanRoomRecognitionDimensionsValid($iWidth, $iHeight, $iMaxResults) Then Return SetError(1, 0, 0)
	If Not _CleanRoomRecognitionPointsValid($aTargets, $iWidth, $iHeight) Or _
			Not _CleanRoomRecognitionPointsValid($aRedlinePoints, $iWidth, $iHeight) Then Return SetError(2, 0, 0)
	If Not IsInt($iDistance) Or $iDistance < 1 Or $iDistance > 64 Then Return SetError(3, 0, 0)

	Local $aResult[$iMaxResults][2]
	Local $iResultCount = 0
	For $iTarget = 0 To UBound($aTargets, 1) - 1
		Local $iBest = -1
		Local $iBestSquared = 0
		For $iRedline = 0 To UBound($aRedlinePoints, 1) - 1
			Local $iDeltaX = $aRedlinePoints[$iRedline][0] - $aTargets[$iTarget][0]
			Local $iDeltaY = $aRedlinePoints[$iRedline][1] - $aTargets[$iTarget][1]
			Local $iSquared = $iDeltaX * $iDeltaX + $iDeltaY * $iDeltaY
			If $iBest = -1 Or $iSquared < $iBestSquared Or _
					($iSquared = $iBestSquared And $aRedlinePoints[$iRedline][1] < $aRedlinePoints[$iBest][1]) Or _
					($iSquared = $iBestSquared And $aRedlinePoints[$iRedline][1] = $aRedlinePoints[$iBest][1] And _
					$aRedlinePoints[$iRedline][0] < $aRedlinePoints[$iBest][0]) Then
				$iBest = $iRedline
				$iBestSquared = $iSquared
			EndIf
		Next
		Local $iOutputX = 0
		Local $iOutputY = 0
		If Not _CleanRoomRecognitionOffsetPoint($aRedlinePoints[$iBest][0], $aRedlinePoints[$iBest][1], _
				$aTargets[$iTarget][0], $aTargets[$iTarget][1], $iDistance, $iWidth, $iHeight, $iOutputX, $iOutputY) Then _
			Return SetError(4, 0, 0)
		If Not _CleanRoomRecognitionPointExists($aResult, $iResultCount, $iOutputX, $iOutputY) Then
			$aResult[$iResultCount][0] = $iOutputX
			$aResult[$iResultCount][1] = $iOutputY
			$iResultCount += 1
			If $iResultCount >= $iMaxResults Then ExitLoop
		EndIf
	Next
	$aOutput = $aResult
	Return SetError(0, 0, $iResultCount)
EndFunc   ;==>CleanRoomRecognitionGetDeployableNextTo
