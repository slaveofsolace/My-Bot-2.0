; #FUNCTION# ====================================================================================================================
; Name ..........: Account queue
; Description ...: Maintains an ordered profile queue for authorized multi-account test sessions.
; Remarks .......: The queue stores profile identifiers and display labels only; it never stores credentials.
; ===============================================================================================================================
#include-once

Func AccountQueueCreate($bCycle = False)
	Local $oQueue = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oQueue) Then Return SetError(1, 0, 0)
	Local $aItems[1][3]
	$oQueue.CompareMode = 1
	$oQueue.Add("schema_version", 1)
	$oQueue.Add("items", $aItems)
	$oQueue.Add("count", 0)
	$oQueue.Add("index", -1)
	$oQueue.Add("cycle", ($bCycle = True))
	Return $oQueue
EndFunc   ;==>AccountQueueCreate

Func AccountQueueValidate(ByRef $oQueue)
	If Not IsObj($oQueue) Then Return SetError(1, 0, False)
	Local $aRequired = ["schema_version", "items", "count", "index", "cycle"]
	For $i = 0 To UBound($aRequired) - 1
		If Not $oQueue.Exists($aRequired[$i]) Then Return SetError(2, $i, False)
	Next
	Local $aItems = $oQueue.Item("items")
	If Not IsArray($aItems) Or UBound($aItems, 2) <> 3 Then Return SetError(3, 0, False)
	If Int($oQueue.Item("count")) < 0 Or Int($oQueue.Item("count")) > UBound($aItems, 1) Then Return SetError(4, 0, False)
	Return True
EndFunc   ;==>AccountQueueValidate

Func AccountQueueAdd(ByRef $oQueue, $sProfileId, $sDisplayName, $bEnabled = True)
	If Not AccountQueueValidate($oQueue) Then Return SetError(1, 0, False)
	$sProfileId = StringStripWS($sProfileId, $STR_STRIPLEADING + $STR_STRIPTRAILING)
	$sDisplayName = StringStripWS($sDisplayName, $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If $sProfileId = "" Then Return SetError(2, 0, False)
	If $sDisplayName = "" Then $sDisplayName = $sProfileId

	Local $aItems = $oQueue.Item("items")
	Local $iCount = Int($oQueue.Item("count"))
	For $i = 0 To $iCount - 1
		If StringLower($aItems[$i][0]) = StringLower($sProfileId) Then Return SetError(3, $i, False)
	Next

	If $iCount >= UBound($aItems, 1) Then ReDim $aItems[$iCount + 1][3]
	$aItems[$iCount][0] = $sProfileId
	$aItems[$iCount][1] = $sDisplayName
	$aItems[$iCount][2] = ($bEnabled = True)
	$oQueue.Item("items") = $aItems
	$oQueue.Item("count") = $iCount + 1
	Return True
EndFunc   ;==>AccountQueueAdd

Func AccountQueueCount(ByRef $oQueue, $bEnabledOnly = False)
	If Not AccountQueueValidate($oQueue) Then Return SetError(1, 0, 0)
	Local $iCount = Int($oQueue.Item("count"))
	If Not $bEnabledOnly Then Return $iCount
	Local $aItems = $oQueue.Item("items"), $iEnabled = 0
	For $i = 0 To $iCount - 1
		If $aItems[$i][2] Then $iEnabled += 1
	Next
	Return $iEnabled
EndFunc   ;==>AccountQueueCount

Func AccountQueueSetEnabled(ByRef $oQueue, $sProfileId, $bEnabled)
	If Not AccountQueueValidate($oQueue) Then Return SetError(1, 0, False)
	Local $aItems = $oQueue.Item("items")
	For $i = 0 To Int($oQueue.Item("count")) - 1
		If StringLower($aItems[$i][0]) = StringLower($sProfileId) Then
			$aItems[$i][2] = ($bEnabled = True)
			$oQueue.Item("items") = $aItems
			Return True
		EndIf
	Next
	Return SetError(2, 0, False)
EndFunc   ;==>AccountQueueSetEnabled

Func AccountQueueReset(ByRef $oQueue)
	If Not AccountQueueValidate($oQueue) Then Return SetError(1, 0, False)
	$oQueue.Item("index") = -1
	Return True
EndFunc   ;==>AccountQueueReset

Func AccountQueueNext(ByRef $oQueue, ByRef $sProfileId, ByRef $sDisplayName)
	$sProfileId = ""
	$sDisplayName = ""
	If Not AccountQueueValidate($oQueue) Then Return SetError(1, 0, False)
	Local $iCount = Int($oQueue.Item("count"))
	If $iCount = 0 Then Return SetError(2, 0, False)

	Local $aItems = $oQueue.Item("items")
	Local $iIndex = Int($oQueue.Item("index"))
	For $iStep = 1 To $iCount
		$iIndex += 1
		If $iIndex >= $iCount Then
			If $oQueue.Item("cycle") Then
				$iIndex = 0
			Else
				$oQueue.Item("index") = $iCount
				Return SetError(3, 0, False)
			EndIf
		EndIf
		If $aItems[$iIndex][2] Then
			$oQueue.Item("index") = $iIndex
			$sProfileId = $aItems[$iIndex][0]
			$sDisplayName = $aItems[$iIndex][1]
			Return True
		EndIf
	Next
	Return SetError(4, 0, False)
EndFunc   ;==>AccountQueueNext

Func AccountQueueCurrentIndex(ByRef $oQueue)
	If Not AccountQueueValidate($oQueue) Then Return SetError(1, 0, -1)
	Return Int($oQueue.Item("index"))
EndFunc   ;==>AccountQueueCurrentIndex
