; #FUNCTION# ====================================================================================================================
; Name ..........: Run plan file
; Description ...: Reads the run plan that tools/planner_ui.py writes, so the web UI and the native tab describe one run.
; Remarks .......: The file is the source of truth. It is a flat JSON object of setting id to value, exactly the ids in
;                  config/ui/run-planner.settings.json, so nothing here needs to know what any particular setting means.
;                  AutoIt has no JSON parser in its standard library and pulling in a UDF for one flat object is not worth the
;                  dependency, so the subset that file can contain is parsed here: strings, numbers, booleans, null, and arrays
;                  of those. Nested objects are refused by name rather than flattened, because a plan that grew a nested shape
;                  is a contract change and should fail loudly. This file is part of My Bot, distributed under the GNU GPL.
; ===============================================================================================================================
#include-once
#include <FileConstants.au3>
#include <StringConstants.au3>

; Values from a multi-select arrive as a JSON array. They are joined with this so the rest of the engine sees the same
; pipe-delimited form Hero loadouts already use.
Global Const $RUN_PLAN_FILE_LIST_SEPARATOR = "|"

; Written by tools/planner_ui.py, read here. Local to one machine, so it is not in version control.
Global Const $RUN_PLAN_FILE_NAME = "config\run-plan.local.json"

; Guards a hand-edited or truncated file: a plan is a couple of kilobytes, so anything past this is not one.
Global Const $RUN_PLAN_FILE_MAX_BYTES = 262144

Func RunPlanFileDefaultPath()
	Return @ScriptDir & "\" & $RUN_PLAN_FILE_NAME
EndFunc   ;==>RunPlanFileDefaultPath

; A cheap token that changes whenever the file does, so the GUI can poll without re-parsing. Missing file returns "",
; which is a value the token can hold like any other, so appearing and disappearing both register as changes.
Func RunPlanFileStamp($sPath)
	If Not FileExists($sPath) Then Return ""
	Local $sModified = FileGetTime($sPath, $FT_MODIFIED, $FT_STRING)
	If @error Then Return ""
	Return $sModified & ":" & FileGetSize($sPath)
EndFunc   ;==>RunPlanFileStamp

Func _RunPlanFileSkipWhitespace($sText, ByRef $iPos)
	Local $iLength = StringLen($sText)
	While $iPos <= $iLength
		Local $sChar = StringMid($sText, $iPos, 1)
		If $sChar <> " " And $sChar <> @TAB And $sChar <> @CR And $sChar <> @LF Then ExitLoop
		$iPos += 1
	WEnd
EndFunc   ;==>_RunPlanFileSkipWhitespace

; Reads one JSON string starting at the opening quote and leaves $iPos just past the closing one.
Func _RunPlanFileReadString($sText, ByRef $iPos, ByRef $sError)
	Local $iLength = StringLen($sText)
	If StringMid($sText, $iPos, 1) <> '"' Then
		$sError = "expected a quoted string at character " & $iPos
		Return SetError(1, 0, "")
	EndIf
	$iPos += 1

	Local $sResult = ""
	While $iPos <= $iLength
		Local $sChar = StringMid($sText, $iPos, 1)
		If $sChar = '"' Then
			$iPos += 1
			$sError = ""
			Return SetError(0, 0, $sResult)
		EndIf

		If $sChar <> "\" Then
			$sResult &= $sChar
			$iPos += 1
			ContinueLoop
		EndIf

		Local $sEscape = StringMid($sText, $iPos + 1, 1)
		Switch $sEscape
			Case '"', "\", "/"
				$sResult &= $sEscape
				$iPos += 2
			Case "b"
				$sResult &= Chr(8)
				$iPos += 2
			Case "f"
				$sResult &= Chr(12)
				$iPos += 2
			Case "n"
				$sResult &= @LF
				$iPos += 2
			Case "r"
				$sResult &= @CR
				$iPos += 2
			Case "t"
				$sResult &= @TAB
				$iPos += 2
			Case "u"
				Local $sHex = StringMid($sText, $iPos + 2, 4)
				If StringLen($sHex) < 4 Or Not StringRegExp($sHex, "^[0-9A-Fa-f]{4}$") Then
					$sError = "malformed \u escape at character " & $iPos
					Return SetError(2, 0, "")
				EndIf
				$sResult &= ChrW(Dec($sHex))
				$iPos += 6
			Case Else
				$sError = "unsupported escape \" & $sEscape & " at character " & $iPos
				Return SetError(3, 0, "")
		EndSwitch
	WEnd

	$sError = "string is not closed"
	Return SetError(4, 0, "")
EndFunc   ;==>_RunPlanFileReadString

; Scalars only: string, number, true, false, null. Arrays are handled by the caller because only it knows they are allowed.
Func _RunPlanFileReadScalar($sText, ByRef $iPos, ByRef $sError)
	_RunPlanFileSkipWhitespace($sText, $iPos)
	Local $sChar = StringMid($sText, $iPos, 1)

	If $sChar = '"' Then
		Local $sString = _RunPlanFileReadString($sText, $iPos, $sError)
		If @error Then Return SetError(1, 0, "")
		Return SetError(0, 0, $sString)
	EndIf

	If StringMid($sText, $iPos, 4) = "true" Then
		$iPos += 4
		$sError = ""
		Return SetError(0, 0, True)
	EndIf
	If StringMid($sText, $iPos, 5) = "false" Then
		$iPos += 5
		$sError = ""
		Return SetError(0, 0, False)
	EndIf
	If StringMid($sText, $iPos, 4) = "null" Then
		$iPos += 4
		$sError = ""
		Return SetError(0, 0, "")
	EndIf

	; A number: take the run of characters a JSON number can be built from and let Number() read it.
	Local $sNumber = ""
	Local $iLength = StringLen($sText)
	While $iPos <= $iLength
		Local $sDigit = StringMid($sText, $iPos, 1)
		If Not StringRegExp($sDigit, "[-+0-9.eE]") Then ExitLoop
		$sNumber &= $sDigit
		$iPos += 1
	WEnd
	If $sNumber = "" Or Not StringRegExp($sNumber, "^-?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?$") Then
		$sError = "expected a value at character " & $iPos
		Return SetError(2, 0, "")
	EndIf
	$sError = ""
	Return SetError(0, 0, Number($sNumber))
EndFunc   ;==>_RunPlanFileReadScalar

; Arrays hold scalars and come back joined, because every list the planner writes is a list of option values.
Func _RunPlanFileReadArray($sText, ByRef $iPos, ByRef $sError)
	If StringMid($sText, $iPos, 1) <> "[" Then
		$sError = "expected an array at character " & $iPos
		Return SetError(1, 0, "")
	EndIf
	$iPos += 1

	Local $sJoined = ""
	Local $bFirst = True
	Local $iLength = StringLen($sText)
	While $iPos <= $iLength
		_RunPlanFileSkipWhitespace($sText, $iPos)
		If StringMid($sText, $iPos, 1) = "]" Then
			$iPos += 1
			$sError = ""
			Return SetError(0, 0, $sJoined)
		EndIf

		If Not $bFirst Then
			If StringMid($sText, $iPos, 1) <> "," Then
				$sError = "expected a comma in an array at character " & $iPos
				Return SetError(2, 0, "")
			EndIf
			$iPos += 1
			_RunPlanFileSkipWhitespace($sText, $iPos)
		EndIf
		$bFirst = False

		If StringMid($sText, $iPos, 1) = "[" Or StringMid($sText, $iPos, 1) = "{" Then
			$sError = "nested arrays and objects are not part of the run plan contract"
			Return SetError(3, 0, "")
		EndIf

		Local $vItem = _RunPlanFileReadScalar($sText, $iPos, $sError)
		If @error Then Return SetError(4, 0, "")
		$sJoined &= (($sJoined = "") ? "" : $RUN_PLAN_FILE_LIST_SEPARATOR) & String($vItem)
	WEnd

	$sError = "array is not closed"
	Return SetError(5, 0, "")
EndFunc   ;==>_RunPlanFileReadArray

; Parses the whole document into a dictionary of setting id to value. Booleans stay booleans and numbers stay numbers, so
; the caller can tell 0 from "0" without guessing.
Func RunPlanFileParse($sText, ByRef $sError)
	$sError = ""
	Local $oValues = ObjCreate("Scripting.Dictionary")
	If Not IsObj($oValues) Then
		$sError = "Unable to create a dictionary for the run plan"
		Return SetError(1, 0, 0)
	EndIf
	$oValues.CompareMode = 1

	; A UTF-8 byte order mark survives FileRead and would otherwise look like a stray character before the brace.
	If StringLeft($sText, 1) = ChrW(65279) Then $sText = StringTrimLeft($sText, 1)

	Local $iPos = 1
	_RunPlanFileSkipWhitespace($sText, $iPos)
	If StringMid($sText, $iPos, 1) <> "{" Then
		$sError = "Run plan must be a JSON object"
		Return SetError(2, 0, 0)
	EndIf
	$iPos += 1

	Local $bFirst = True
	Local $iLength = StringLen($sText)
	While $iPos <= $iLength
		_RunPlanFileSkipWhitespace($sText, $iPos)
		If StringMid($sText, $iPos, 1) = "}" Then
			$iPos += 1
			Return SetError(0, 0, $oValues)
		EndIf

		If Not $bFirst Then
			If StringMid($sText, $iPos, 1) <> "," Then
				$sError = "Expected a comma between run plan entries at character " & $iPos
				Return SetError(3, 0, 0)
			EndIf
			$iPos += 1
			_RunPlanFileSkipWhitespace($sText, $iPos)
		EndIf
		$bFirst = False

		Local $sKey = _RunPlanFileReadString($sText, $iPos, $sError)
		If @error Then
			$sError = "Run plan key: " & $sError
			Return SetError(4, 0, 0)
		EndIf

		_RunPlanFileSkipWhitespace($sText, $iPos)
		If StringMid($sText, $iPos, 1) <> ":" Then
			$sError = "Expected a colon after " & $sKey
			Return SetError(5, 0, 0)
		EndIf
		$iPos += 1
		_RunPlanFileSkipWhitespace($sText, $iPos)

		Local $vValue
		If StringMid($sText, $iPos, 1) = "[" Then
			$vValue = _RunPlanFileReadArray($sText, $iPos, $sError)
			If @error Then
				$sError = $sKey & ": " & $sError
				Return SetError(6, 0, 0)
			EndIf
		ElseIf StringMid($sText, $iPos, 1) = "{" Then
			$sError = $sKey & ": nested objects are not part of the run plan contract"
			Return SetError(7, 0, 0)
		Else
			$vValue = _RunPlanFileReadScalar($sText, $iPos, $sError)
			If @error Then
				$sError = $sKey & ": " & $sError
				Return SetError(8, 0, 0)
			EndIf
		EndIf

		; A duplicate key is a corrupt file rather than an update, so it is refused instead of silently taking the last one.
		If $oValues.Exists($sKey) Then
			$sError = "Run plan lists " & $sKey & " more than once"
			Return SetError(9, 0, 0)
		EndIf
		$oValues.Add($sKey, $vValue)
	WEnd

	$sError = "Run plan object is not closed"
	Return SetError(10, 0, 0)
EndFunc   ;==>RunPlanFileParse

; @error 2 means there is simply no plan file, which is the normal state on a machine that never opened the web UI.
Func RunPlanFileLoad($sPath, ByRef $sError)
	$sError = ""
	If Not FileExists($sPath) Then
		$sError = "No run plan file at " & $sPath
		Return SetError(2, 0, 0)
	EndIf

	Local $iSize = FileGetSize($sPath)
	If $iSize > $RUN_PLAN_FILE_MAX_BYTES Then
		$sError = "Run plan file is " & $iSize & " bytes; a run plan is a few kilobytes"
		Return SetError(3, 0, 0)
	EndIf

	Local $hFile = FileOpen($sPath, $FO_READ + $FO_UTF8_NOBOM)
	If $hFile = -1 Then
		$sError = "Unable to open " & $sPath
		Return SetError(4, 0, 0)
	EndIf
	Local $sText = FileRead($hFile)
	FileClose($hFile)

	Local $oValues = RunPlanFileParse($sText, $sError)
	If Not IsObj($oValues) Then Return SetError(5, 0, 0)
	Return SetError(0, 0, $oValues)
EndFunc   ;==>RunPlanFileLoad
