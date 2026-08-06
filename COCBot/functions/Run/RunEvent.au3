; #FUNCTION# ====================================================================================================================
; Name ..........: Run event
; Description ...: Creates, validates, serializes, and appends structured session events for diagnostics and the future UI.
; Remarks .......: The event contract intentionally excludes credentials, account identifiers, chat content, and machine details.
; ===============================================================================================================================
#include-once
#include <FileConstants.au3>

Func RunEventCreate($sType, $iSequence, $iTimestampMs, $sSessionId, $sSeverity = "info", $sMessage = "", $sProfileId = "", $sRoute = "", $iBattleIndex = 0, $iGold = 0, $iElixir = 0, $iDarkElixir = 0, $iFailureCount = 0)
	Local $oEvent = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oEvent) Then Return SetError(1, 0, 0)
	$oEvent.CompareMode = 1
	$oEvent.Add("schema_version", 1)
	$oEvent.Add("sequence", Int($iSequence))
	$oEvent.Add("type", StringLower(StringStripWS($sType, $STR_STRIPALL)))
	$oEvent.Add("severity", StringLower(StringStripWS($sSeverity, $STR_STRIPALL)))
	$oEvent.Add("session_id", StringStripWS($sSessionId, $STR_STRIPLEADING + $STR_STRIPTRAILING))
	$oEvent.Add("timestamp_ms", Int($iTimestampMs))
	$oEvent.Add("message", $sMessage)
	$oEvent.Add("account_profile_id", StringStripWS($sProfileId, $STR_STRIPLEADING + $STR_STRIPTRAILING))
	$oEvent.Add("route", StringLower(StringStripWS($sRoute, $STR_STRIPALL)))
	$oEvent.Add("battle_index", Int($iBattleIndex))
	$oEvent.Add("gold", Int($iGold))
	$oEvent.Add("elixir", Int($iElixir))
	$oEvent.Add("dark_elixir", Int($iDarkElixir))
	$oEvent.Add("failure_count", Int($iFailureCount))
	Local $sError
	If Not RunEventValidate($oEvent, $sError) Then Return SetError(2, 0, 0)
	Return $oEvent
EndFunc   ;==>RunEventCreate

Func RunEventValidate(ByRef $oEvent, ByRef $sError)
	$sError = ""
	If Not IsObj($oEvent) Then
		$sError = "Run event is not an object"
		Return SetError(1, 0, False)
	EndIf
	Local $aRequired = ["schema_version", "sequence", "type", "severity", "session_id", "timestamp_ms", "message", "account_profile_id", "route", "battle_index", "gold", "elixir", "dark_elixir", "failure_count"]
	For $i = 0 To UBound($aRequired) - 1
		If Not $oEvent.Exists($aRequired[$i]) Then
			$sError = "Missing run event field: " & $aRequired[$i]
			Return SetError(2, $i, False)
		EndIf
	Next
	Switch $oEvent.Item("type")
		Case "session.ready", "session.started", "session.stopping", "session.completed", "session.failed", "route.blocked", "route.ready", "account.changed", "battle.started", "battle.completed", "battle.failed", "loot.updated", "warning", "error"
		Case Else
			$sError = "Unsupported run event type: " & $oEvent.Item("type")
			Return SetError(3, 0, False)
	EndSwitch
	Switch $oEvent.Item("severity")
		Case "debug", "info", "warning", "error"
		Case Else
			$sError = "Unsupported run event severity: " & $oEvent.Item("severity")
			Return SetError(4, 0, False)
	EndSwitch
	Switch $oEvent.Item("route")
		Case "", "regular", "ranked", "legend", "builder"
		Case Else
			$sError = "Unsupported run event route: " & $oEvent.Item("route")
			Return SetError(5, 0, False)
	EndSwitch
	If $oEvent.Item("session_id") = "" Then
		$sError = "Session identifier cannot be empty"
		Return SetError(6, 0, False)
	EndIf
	Local $aNonNegative = ["sequence", "timestamp_ms", "battle_index", "gold", "elixir", "dark_elixir", "failure_count"]
	For $i = 0 To UBound($aNonNegative) - 1
		If Number($oEvent.Item($aNonNegative[$i])) < 0 Then
			$sError = $aNonNegative[$i] & " cannot be negative"
			Return SetError(7, $i, False)
		EndIf
	Next
	Return True
EndFunc   ;==>RunEventValidate

Func _RunEventJsonString($sValue)
	Local $sEscaped = String($sValue)
	$sEscaped = StringReplace($sEscaped, Chr(92), Chr(92) & Chr(92))
	$sEscaped = StringReplace($sEscaped, Chr(34), Chr(92) & Chr(34))
	$sEscaped = StringReplace($sEscaped, @CR, Chr(92) & "r")
	$sEscaped = StringReplace($sEscaped, @LF, Chr(92) & "n")
	$sEscaped = StringReplace($sEscaped, @TAB, Chr(92) & "t")
	Return Chr(34) & $sEscaped & Chr(34)
EndFunc   ;==>_RunEventJsonString

Func RunEventToJson(ByRef $oEvent)
	Local $sError
	If Not RunEventValidate($oEvent, $sError) Then Return SetError(1, 0, "")
	Local $sJson = "{"
	$sJson &= _RunEventJsonString("schema_version") & ":1,"
	$sJson &= _RunEventJsonString("sequence") & ":" & Int($oEvent.Item("sequence")) & ","
	$sJson &= _RunEventJsonString("type") & ":" & _RunEventJsonString($oEvent.Item("type")) & ","
	$sJson &= _RunEventJsonString("severity") & ":" & _RunEventJsonString($oEvent.Item("severity")) & ","
	$sJson &= _RunEventJsonString("session_id") & ":" & _RunEventJsonString($oEvent.Item("session_id")) & ","
	$sJson &= _RunEventJsonString("timestamp_ms") & ":" & Int($oEvent.Item("timestamp_ms")) & ","
	$sJson &= _RunEventJsonString("message") & ":" & _RunEventJsonString($oEvent.Item("message")) & ","
	$sJson &= _RunEventJsonString("account_profile_id") & ":" & _RunEventJsonString($oEvent.Item("account_profile_id")) & ","
	$sJson &= _RunEventJsonString("route") & ":" & _RunEventJsonString($oEvent.Item("route")) & ","
	$sJson &= _RunEventJsonString("battle_index") & ":" & Int($oEvent.Item("battle_index")) & ","
	$sJson &= _RunEventJsonString("gold") & ":" & Int($oEvent.Item("gold")) & ","
	$sJson &= _RunEventJsonString("elixir") & ":" & Int($oEvent.Item("elixir")) & ","
	$sJson &= _RunEventJsonString("dark_elixir") & ":" & Int($oEvent.Item("dark_elixir")) & ","
	$sJson &= _RunEventJsonString("failure_count") & ":" & Int($oEvent.Item("failure_count"))
	$sJson &= "}"
	Return $sJson
EndFunc   ;==>RunEventToJson

Func RunEventAppendJsonLine($sPath, ByRef $oEvent)
	Local $sJson = RunEventToJson($oEvent)
	If @error Or $sJson = "" Then Return SetError(1, 0, False)
	Local $hFile = FileOpen($sPath, BitOR($FO_APPEND, $FO_CREATEPATH, $FO_UTF8_NOBOM))
	If $hFile = -1 Then Return SetError(2, 0, False)
	Local $bWritten = FileWriteLine($hFile, $sJson)
	FileClose($hFile)
	If Not $bWritten Then Return SetError(3, 0, False)
	Return True
EndFunc   ;==>RunEventAppendJsonLine
