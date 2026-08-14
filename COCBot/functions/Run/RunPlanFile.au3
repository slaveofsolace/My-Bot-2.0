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

Global Const $RUN_PLAN_FILE_SCHEMA_VERSION = 1

Func _RunPlanFileModeForSurface($sSurface)
	Switch StringLower(String($sSurface))
		Case "builder"
			Return "builder"
		Case "ranked"
			Return "ranked"
		Case "legend-iii", "legend-ii", "legend-i"
			Return "legend"
		Case "regular", "revenge"
			Return "regular"
	EndSwitch
	Return ""
EndFunc   ;==>_RunPlanFileModeForSurface

; The exact contract. 46 keys: 41 run settings plus the five pacing settings the cloud surface adds.
; If a setting is added to config/ui/run-planner.settings.json it MUST be added here too, or every
; saved plan is refused.
Func _RunPlanFileRequiredKeys()
	Local $aKeys = ["run.surface", "run.strategy", "run.attack_script", "run.town_hall", "run.heroes", "runtime.emulator", "runtime.instance", "run.duration_minutes", "run.max_battles", "run.stop_on_star_bonus", "run.max_failures", _
		"target.gold", "target.elixir", "target.dark_elixir", "upgrade.policy", "account.queue", "army.source", "army.recipe_name", "army.manage_training", "army.wait_for_full", "army.train_spells", "army.train_sieges", _
		"search.min_gold", "search.min_elixir", "search.min_dark", "search.max_seconds", "search.town_hall_filter", "donate.mode", "donate.keep_army", "donate.max_per_run", "donate.request_when_short", _
		"events.clan_games", "events.clan_games_point_cap", "events.laboratory", "events.collect_resources", "events.collect_daily_reward", "notify.on_stop", "notify.on_error", "notify.channel", "run.diagnostic_mode", "run.diagnostic_note", _
		"pacing.action_delay_ms", "pacing.settle_ms", "pacing.retry_attempts", "pacing.break_every_minutes", "pacing.break_minutes"]
	Return $aKeys
EndFunc   ;==>_RunPlanFileRequiredKeys

; Current plans own the explicit Daily Reward choice. The preceding 45-key build did not, so migrate
; it to the safe default (False). Earlier 44/43/42-key migrations retain their original meanings for
; Town Hall, training management, and attack script before that final addition. Unknown or otherwise
; incomplete documents remain strict failures below.
Func _RunPlanFileNormalizeCurrentContract(ByRef $oJson)
	If Not IsObj($oJson) Then Return False
	If $oJson.Count = 42 And Not $oJson.Exists("run.attack_script") Then $oJson.Add("run.attack_script", "profile-current")
	If $oJson.Count = 43 And Not $oJson.Exists("army.manage_training") Then $oJson.Add("army.manage_training", True)
	If $oJson.Count = 44 And Not $oJson.Exists("run.town_hall") Then $oJson.Add("run.town_hall", 0)
	If $oJson.Count = 45 And Not $oJson.Exists("events.collect_daily_reward") Then $oJson.Add("events.collect_daily_reward", False)
	Return True
EndFunc   ;==>_RunPlanFileNormalizeCurrentContract

Func _RunPlanFileValidateShape(ByRef $oJson, ByRef $sError)
	If Not IsObj($oJson) Then
		$sError = "Saved plan must contain one JSON object"
		Return False
	EndIf
	Local $aRequired = _RunPlanFileRequiredKeys()
	If $oJson.Count <> UBound($aRequired) Then
		$sError = "Saved plan has " & $oJson.Count & " fields; the planner contract has " & UBound($aRequired)
		Return False
	EndIf
	For $i = 0 To UBound($aRequired) - 1
		If Not $oJson.Exists($aRequired[$i]) Then
			$sError = "Saved plan is missing: " & $aRequired[$i]
			Return False
		EndIf
	Next
	Return True
EndFunc   ;==>_RunPlanFileValidateShape

Func _RunPlanFileRequireString(ByRef $oJson, $sKey, ByRef $sError)
	Local $vValue = $oJson.Item($sKey)
	If Not IsString($vValue) Then
		$sError = $sKey & " must be text"
		Return SetError(1, 0, "")
	EndIf
	Return $vValue
EndFunc   ;==>_RunPlanFileRequireString

Func _RunPlanFileRequireInteger(ByRef $oJson, $sKey, ByRef $sError)
	Local $vValue = $oJson.Item($sKey)
	If Not IsNumber($vValue) Or Int($vValue) <> Number($vValue) Or Number($vValue) < 0 Then
		$sError = $sKey & " must be a non-negative integer"
		Return SetError(1, 0, 0)
	EndIf
	Return Int($vValue)
EndFunc   ;==>_RunPlanFileRequireInteger

Func _RunPlanFileRequireBoolean(ByRef $oJson, $sKey, ByRef $sError)
	Local $vValue = $oJson.Item($sKey)
	If Not IsBool($vValue) Then
		$sError = $sKey & " must be true or false"
		Return SetError(1, 0, False)
	EndIf
	Return $vValue
EndFunc   ;==>_RunPlanFileRequireBoolean

Func _RunPlanFileAssignString(ByRef $oPlan, ByRef $oJson, $sPlanKey, $sJsonKey, ByRef $sError)
	Local $sValue = _RunPlanFileRequireString($oJson, $sJsonKey, $sError)
	If @error Then Return False
	$oPlan.Item($sPlanKey) = $sValue
	Return True
EndFunc   ;==>_RunPlanFileAssignString

Func _RunPlanFileAssignInteger(ByRef $oPlan, ByRef $oJson, $sPlanKey, $sJsonKey, ByRef $sError)
	Local $iValue = _RunPlanFileRequireInteger($oJson, $sJsonKey, $sError)
	If @error Then Return False
	$oPlan.Item($sPlanKey) = $iValue
	Return True
EndFunc   ;==>_RunPlanFileAssignInteger

Func _RunPlanFileAssignBoolean(ByRef $oPlan, ByRef $oJson, $sPlanKey, $sJsonKey, ByRef $sError)
	Local $bValue = _RunPlanFileRequireBoolean($oJson, $sJsonKey, $sError)
	If @error Then Return False
	$oPlan.Item($sPlanKey) = $bValue
	Return True
EndFunc   ;==>_RunPlanFileAssignBoolean

; LIST REPRESENTATION - do not simplify this.
; tools/check_plan_bridge.py requires `RUN_PLAN_FILE_LIST_SEPARATOR = "|"` in this file and checks
; "list delimiter consistency between parser and applier", so cloud's parser hands multi-select
; values back as a PIPE-DELIMITED STRING, not an AutoIt array.
;
; The Windows original assumed an array and treated any string as a single Hero. Composed against
; cloud's parser that silently breaks: "barbarian-king|archer-queen" would be passed to
; HeroLoadoutAdd as one identifier and rejected as an unknown Hero. Split first.
;
; The array branch is kept as defence in case the parser is ever changed to return real arrays.
Func _RunPlanFileBuildLoadout(ByRef $oJson, ByRef $sError)
	Local $iPlannedTownHall = _RunPlanFileRequireInteger($oJson, "run.town_hall", $sError)
	If @error Or $iPlannedTownHall > $CURRENT_GAME_MAX_TOWN_HALL Then
		If $sError = "" Then $sError = "run.town_hall exceeds the current Town Hall catalog"
		Return SetError(1, 0, 0)
	EndIf
	Local $oLoadout = HeroLoadoutCreate($iPlannedTownHall)
	If Not IsObj($oLoadout) Then
		$sError = "Unable to create a Hero loadout"
		Return SetError(2, 0, 0)
	EndIf
	Local $vHeroes = $oJson.Item("run.heroes")
	Local $aHeroes
	If IsString($vHeroes) Then
		If StringStripWS($vHeroes, 3) = "" Then Return $oLoadout ; an empty selection is legitimate
		$aHeroes = StringSplit($vHeroes, $RUN_PLAN_FILE_LIST_SEPARATOR, $STR_ENTIRESPLIT + $STR_NOCOUNT)
	ElseIf IsArray($vHeroes) Then
		$aHeroes = $vHeroes
	Else
		$sError = "run.heroes must be a list"
		Return SetError(3, 0, 0)
	EndIf

	For $i = 0 To UBound($aHeroes) - 1
		If Not IsString($aHeroes[$i]) Then
			$sError = "run.heroes must contain Hero identifiers"
			Return SetError(4, $i, 0)
		EndIf
		Local $sHero = StringStripWS($aHeroes[$i], 3)
		If $sHero = "" Then ContinueLoop
		If Not HeroLoadoutAdd($oLoadout, $sHero, $sError) Then Return SetError(5, $i, 0)
	Next
	Return $oLoadout
EndFunc   ;==>_RunPlanFileBuildLoadout

; Reads five pacing integers off the saved document and installs them on the intent.
; Kept separate so the bound errors name pacing rather than surfacing as a generic plan failure.
Func _RunPlanFileApplyPacing(ByRef $oIntent, ByRef $oJson, ByRef $sError)
	Local $iActionDelay = _RunPlanFileRequireInteger($oJson, "pacing.action_delay_ms", $sError)
	If @error Then Return False
	Local $iSettle = _RunPlanFileRequireInteger($oJson, "pacing.settle_ms", $sError)
	If @error Then Return False
	Local $iRetries = _RunPlanFileRequireInteger($oJson, "pacing.retry_attempts", $sError)
	If @error Then Return False
	Local $iBreakEvery = _RunPlanFileRequireInteger($oJson, "pacing.break_every_minutes", $sError)
	If @error Then Return False
	Local $iBreakFor = _RunPlanFileRequireInteger($oJson, "pacing.break_minutes", $sError)
	If @error Then Return False

	; RunIntentSetPacing enforces the engine's own bounds and is the single place they live.
	; Note break_minutes is 1-240: a hand-edited 0 is refused here, which is correct.
	If Not RunIntentSetPacing($oIntent, $iActionDelay, $iSettle, $iRetries, $iBreakEvery, $iBreakFor, $sError) Then Return False
	Return True
EndFunc   ;==>_RunPlanFileApplyPacing

; Loads the saved planner document and prepares engine objects. Prepares only: opening a session
; and pressing Start remain the run loop's job. Nothing here begins a run.
Func RunPlanFileLoadIntent($sPath, ByRef $sError)
	$sError = ""
	If $sPath = "" Then $sPath = RunPlanFileDefaultPath()

	; Cloud's loader already checks existence, bounds the size, and refuses nested objects/arrays.
	Local $oJson = RunPlanFileLoad($sPath, $sError)
	If Not IsObj($oJson) Then Return SetError(1, 0, 0)
	_RunPlanFileNormalizeCurrentContract($oJson)
	If Not _RunPlanFileValidateShape($oJson, $sError) Then Return SetError(2, 0, 0)

	Local $sSurface = _RunPlanFileRequireString($oJson, "run.surface", $sError)
	If @error Then Return SetError(3, 0, 0)
	Local $sMode = _RunPlanFileModeForSurface($sSurface)
	If $sMode = "" Then
		$sError = "Unsupported saved surface: " & $sSurface
		Return SetError(4, 0, 0)
	EndIf
	Local $sStrategy = _RunPlanFileRequireString($oJson, "run.strategy", $sError)
	If @error Then Return SetError(5, 0, 0)
	Local $oPlan = RunPlanCreateDefault($sMode, $sStrategy)
	If Not IsObj($oPlan) Then
		$sError = "Unable to create a run plan"
		Return SetError(6, 0, 0)
	EndIf

	Local $aStrings[11][2] = [["attack_script", "run.attack_script"], ["emulator", "runtime.emulator"], ["emulator_instance", "runtime.instance"], ["upgrade_policy", "upgrade.policy"], ["account_queue_id", "account.queue"], ["army_source", "army.source"], ["army_recipe_name", "army.recipe_name"], ["search_town_hall_filter", "search.town_hall_filter"], ["donate_mode", "donate.mode"], ["events_laboratory", "events.laboratory"], ["notify_channel", "notify.channel"]]
	; mode is derived from the surface. Assign every other text field explicitly.
	For $i = 0 To UBound($aStrings) - 1
		If Not _RunPlanFileAssignString($oPlan, $oJson, $aStrings[$i][0], $aStrings[$i][1], $sError) Then Return SetError(7, $i, 0)
	Next
	; pacing.* is deliberately absent from this table - it belongs to the intent, not the plan.
	Local $aIntegers[13][2] = [["planned_town_hall", "run.town_hall"], ["duration_minutes", "run.duration_minutes"], ["max_battles", "run.max_battles"], ["max_failures", "run.max_failures"], ["target_gold", "target.gold"], ["target_elixir", "target.elixir"], ["target_dark_elixir", "target.dark_elixir"], ["search_min_gold", "search.min_gold"], ["search_min_elixir", "search.min_elixir"], ["search_min_dark", "search.min_dark"], ["search_max_seconds", "search.max_seconds"], ["donate_max_per_run", "donate.max_per_run"], ["events_clan_games_point_cap", "events.clan_games_point_cap"]]
	For $i = 0 To UBound($aIntegers) - 1
		If Not _RunPlanFileAssignInteger($oPlan, $oJson, $aIntegers[$i][0], $aIntegers[$i][1], $sError) Then Return SetError(8, $i, 0)
	Next
	Local $aBooleans[12][2] = [["stop_on_star_bonus", "run.stop_on_star_bonus"], ["army_manage_training", "army.manage_training"], ["army_wait_for_full", "army.wait_for_full"], ["army_train_spells", "army.train_spells"], ["army_train_sieges", "army.train_sieges"], ["donate_keep_army", "donate.keep_army"], ["donate_request_when_short", "donate.request_when_short"], ["events_clan_games", "events.clan_games"], ["events_collect_resources", "events.collect_resources"], ["events_collect_daily_reward", "events.collect_daily_reward"], ["notify_on_stop", "notify.on_stop"], ["notify_on_error", "notify.on_error"]]
	For $i = 0 To UBound($aBooleans) - 1
		If Not _RunPlanFileAssignBoolean($oPlan, $oJson, $aBooleans[$i][0], $aBooleans[$i][1], $sError) Then Return SetError(9, $i, 0)
	Next
	If Not RunPlanValidate($oPlan, $sError) Then Return SetError(10, 0, 0)

	Local $oLoadout = _RunPlanFileBuildLoadout($oJson, $sError)
	If Not IsObj($oLoadout) Then Return SetError(11, 0, 0)
	Local $oIntent = RunIntentCreate($oPlan, $sSurface, $oLoadout, $sError)
	If Not IsObj($oIntent) Then Return SetError(12, 0, 0)
	If Not _RunPlanFileApplyPacing($oIntent, $oJson, $sError) Then Return SetError(13, 0, 0)

	Local $bDiagnostic = _RunPlanFileRequireBoolean($oJson, "run.diagnostic_mode", $sError)
	If @error Then Return SetError(14, 0, 0)
	Local $sDiagnosticNote = _RunPlanFileRequireString($oJson, "run.diagnostic_note", $sError)
	If @error Then Return SetError(15, 0, 0)
	If $bDiagnostic And Not RunIntentEnableDiagnostic($oIntent, $sDiagnosticNote, $sError) Then Return SetError(16, 0, 0)
	Return $oIntent
EndFunc   ;==>RunPlanFileLoadIntent
