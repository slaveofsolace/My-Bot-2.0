; #FUNCTION# ====================================================================================================================
; Name ..........: MBR GUI Control Run Planner
; Description ...: Reads the Run Planner controls and turns them into a run intent the engine can act on.
; Remarks .......: This is the whole engine boundary for the planner: the GUI never touches battle code directly, it builds a
;                  RunIntent and reports what the engine says about it. This file is part of My Bot, distributed under the GNU GPL.
; ===============================================================================================================================
#include-once
#include "MBR GUI Design Run Planner.au3"
#include "..\functions\Run\RunIntent.au3"
#include "..\functions\Run\RunPlanFile.au3"
#include "..\functions\Run\RunEventLog.au3"
#include "..\functions\Run\RunExecutionContract.au3"

Global Const $RUN_PLANNER_URL = "http://127.0.0.1:8765/"
Global Const $RUN_PLANNER_HEALTH_URL = "http://127.0.0.1:8765/api/health"

; What /api/health has to say before this build will talk to the service. tools/check_plan_bridge.py
; compares these two against the values tools/planner_ui.py actually serves, because a bridge version
; bumped on one side and not the other would otherwise leave the GUI reporting "unavailable" forever
; with a healthy service running in front of it.
Global Const $RUN_PLANNER_SERVICE_NAME = "my-bot-control-center"
Global Const $RUN_PLANNER_BRIDGE_VERSION = "autoit-control-file-v1"
Global $g_oRunPlannerIntent = 0
Global $g_sRunPlannerHeroIds = ""

; Change token of the plan file as of the last time it was read into the controls. Empty means never read, or no file.
Global $g_sRunPlannerPlanFileStamp = ""
Global $g_sRunPlannerPlanFileNote = ""

; The payload is parsed rather than pattern-matched. Substring checks made this depend on the exact
; spacing json.dumps happens to emit: switching the server to compact separators, or adding an indent,
; would silently report a perfectly healthy service as unavailable with nothing to show why.
Func _RunPlannerServiceHealthy()
	Local $bPayload = InetRead($RUN_PLANNER_HEALTH_URL, 1)
	If @error Then Return False

	Local $sPayload = BinaryToString($bPayload, 4)
	If StringStripWS($sPayload, $STR_STRIPALL) = "" Then Return False

	Local $oPayload = Json_Decode($sPayload)
	If @error Or Not IsObj($oPayload) Then Return False

	; A service that answers but reports itself unhealthy is not healthy, so ok has to be the boolean
	; true rather than merely present.
	If Json_ObjGet($oPayload, "ok") <> True Then Return False
	If Json_ObjGet($oPayload, "service") <> $RUN_PLANNER_SERVICE_NAME Then Return False
	If Json_ObjGet($oPayload, "bridge") <> $RUN_PLANNER_BRIDGE_VERSION Then Return False
	Return True
EndFunc   ;==>_RunPlannerServiceHealthy

Func _RunPlannerPythonExecutable()
	Local $aCandidates = [ _
		@LocalAppDataDir & "\Programs\Python\Python313\pythonw.exe", _
		@LocalAppDataDir & "\Programs\Python\Python312\pythonw.exe", _
		@LocalAppDataDir & "\Programs\Python\Python311\pythonw.exe", _
		@LocalAppDataDir & "\Programs\Python\Python310\pythonw.exe"]
	For $i = 0 To UBound($aCandidates) - 1
		If FileExists($aCandidates[$i]) Then Return $aCandidates[$i]
	Next
	Return "pythonw.exe"
EndFunc   ;==>_RunPlannerPythonExecutable

Func _RunPlannerStartService(ByRef $sError)
	$sError = ""
	If _RunPlannerServiceHealthy() Then Return True
	Local $sScript = @ScriptDir & "\tools\planner_ui.py"
	If Not FileExists($sScript) Then
		$sError = "Planner service script is missing"
		Return False
	EndIf
	Local $sPython = _RunPlannerPythonExecutable()
	Local $iPid = Run('"' & $sPython & '" "' & $sScript & '" --no-browser', @ScriptDir, @SW_HIDE)
	If $iPid = 0 Then
		$sError = "Python could not start the planner service"
		Return False
	EndIf
	For $i = 1 To 25
		Sleep(200)
		If _RunPlannerServiceHealthy() Then Return True
	Next
	$sError = "Planner service did not become healthy"
	Return False
EndFunc   ;==>_RunPlannerStartService

Func _RunPlannerSetLabel($hControl, $sText, $iColor)
	If $hControl = 0 Then Return
	GUICtrlSetData($hControl, $sText)
	GUICtrlSetColor($hControl, $iColor)
EndFunc   ;==>_RunPlannerSetLabel

Func RunPlannerSettingIndex($sSettingId)
	For $i = 0 To UBound($g_aRunPlannerSettings, 1) - 1
		If $g_aRunPlannerSettings[$i][$eRunPlannerSettingId] = $sSettingId Then Return $i
	Next
	Return -1
EndFunc   ;==>RunPlannerSettingIndex

Func RunPlannerOptionIndex($sSettingId, $sValue)
	For $i = 0 To UBound($g_aRunPlannerOptions, 1) - 1
		If $g_aRunPlannerOptions[$i][$eRunPlannerOptionSettingId] <> $sSettingId Then ContinueLoop
		If $g_aRunPlannerOptions[$i][$eRunPlannerOptionValue] = $sValue Then Return $i
	Next
	Return -1
EndFunc   ;==>RunPlannerOptionIndex

; Combos display a decorated label, so read the control and map the text back to the option value.
Func RunPlannerSelectedValue($sSettingId)
	Local $iSetting = RunPlannerSettingIndex($sSettingId)
	If $iSetting < 0 Then Return ""
	Local $hControl = $g_ahRunPlannerControls[$iSetting]
	If $hControl = 0 Then Return ""
	Local $sText = GUICtrlRead($hControl)
	For $i = 0 To UBound($g_aRunPlannerOptions, 1) - 1
		If $g_aRunPlannerOptions[$i][$eRunPlannerOptionSettingId] <> $sSettingId Then ContinueLoop
		If _RunPlannerDecoratedLabel($i) = $sText Then Return $g_aRunPlannerOptions[$i][$eRunPlannerOptionValue]
	Next
	Return ""
EndFunc   ;==>RunPlannerSelectedValue

Func RunPlannerReadInteger($sSettingId)
	Local $iSetting = RunPlannerSettingIndex($sSettingId)
	If $iSetting < 0 Then Return 0
	If $g_ahRunPlannerControls[$iSetting] = 0 Then Return 0
	Return Int(GUICtrlRead($g_ahRunPlannerControls[$iSetting]))
EndFunc   ;==>RunPlannerReadInteger

Func RunPlannerReadBoolean($sSettingId)
	Local $iSetting = RunPlannerSettingIndex($sSettingId)
	If $iSetting < 0 Then Return False
	If $g_ahRunPlannerControls[$iSetting] = 0 Then Return False
	Return GUICtrlRead($g_ahRunPlannerControls[$iSetting]) = $GUI_CHECKED
EndFunc   ;==>RunPlannerReadBoolean

Func RunPlannerReadText($sSettingId)
	Local $iSetting = RunPlannerSettingIndex($sSettingId)
	If $iSetting < 0 Then Return ""
	If $g_ahRunPlannerControls[$iSetting] = 0 Then Return ""
	Return StringStripWS(GUICtrlRead($g_ahRunPlannerControls[$iSetting]), $STR_STRIPLEADING + $STR_STRIPTRAILING)
EndFunc   ;==>RunPlannerReadText

; ===============================================================================================================================
; The web planner writes config\run-plan.local.json; this reads it back into the tab.
;
; The file is the single source of truth and the traffic is one way: the tab mirrors the file, and nothing here writes to it.
; That is what makes the two views safe to have open at once - the browser cannot be quietly overwritten by a stale tab.
; ===============================================================================================================================

; A hand-edited file can hold anything. Booleans arrive as real booleans from the parser, but the words are accepted too so a
; file someone typed themselves behaves the way it reads.
Func _RunPlannerBooleanFromValue($vValue, ByRef $bValid)
	$bValid = True
	If IsBool($vValue) Then Return $vValue
	If IsNumber($vValue) Then Return ($vValue <> 0)
	Switch StringLower(StringStripWS(String($vValue), $STR_STRIPALL))
		Case "true", "1", "yes", "on"
			Return True
		Case "false", "0", "no", "off", ""
			Return False
	EndSwitch
	$bValid = False
	Return False
EndFunc   ;==>_RunPlannerBooleanFromValue

; Puts one value from the plan file into the control that owns it.
;
; True means the control now holds a usable value; False means it was left alone because the file's value could not be
; represented, which costs that one setting rather than the whole plan. $sError is set either way when there is something to
; say, so True with a message means the value was accepted after being adjusted.
Func _RunPlannerApplySetting($iSetting, $vValue, ByRef $sError)
	$sError = ""
	Local $sId = $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingId]
	Local $hControl = $g_ahRunPlannerControls[$iSetting]
	If $hControl = 0 Then
		$sError = $sId & " has no control"
		Return SetError(1, 0, False)
	EndIf

	Switch StringLower($g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingType])
		Case "select"
			Local $sValue = String($vValue)
			If RunPlannerOptionIndex($sId, $sValue) < 0 Then
				$sError = $sId & ": " & $sValue & " is not one of the offered options"
				Return SetError(2, 0, False)
			EndIf
			; Same clear-and-repopulate the Reset button uses: it is the one way to move a combo's selection that also keeps
			; the decorated availability labels correct.
			GUICtrlSetData($hControl, "")
			GUICtrlSetData($hControl, _RunPlannerOptionLabelList($sId), _RunPlannerDefaultLabel($sId, $sValue))
			_RunPlannerTintForAvailability($hControl, $sId, $sValue)

		Case "multi-select"
			; Heroes are held in a loadout rather than the control, so the list goes through the engine and an impossible
			; selection is refused here rather than surfacing at Apply.
			Local $sIds = StringStripWS(String($vValue), $STR_STRIPLEADING + $STR_STRIPTRAILING)
			Local $oLoadout = HeroLoadoutCreate($CURRENT_GAME_MAX_TOWN_HALL)
			If Not IsObj($oLoadout) Then
				$sError = $sId & ": unable to create a Hero loadout"
				Return SetError(3, 0, False)
			EndIf
			If $sIds <> "" Then
				Local $aIds = StringSplit($sIds, $RUN_PLAN_FILE_LIST_SEPARATOR, $STR_NOCOUNT)
				For $i = 0 To UBound($aIds) - 1
					Local $sHero = StringStripWS($aIds[$i], $STR_STRIPALL)
					If $sHero = "" Then ContinueLoop
					If Not HeroLoadoutAdd($oLoadout, $sHero, $sError) Then
						$sError = $sId & ": " & $sError
						Return SetError(4, 0, False)
					EndIf
				Next
			EndIf
			$g_sRunPlannerHeroIds = $oLoadout.Item("hero_ids")
			RunPlannerRefreshHeroSelection()

		Case "integer"
			If Not StringRegExp(StringStripWS(String($vValue), $STR_STRIPALL), "^-?[0-9]+$") Then
				$sError = $sId & ": " & String($vValue) & " is not a whole number"
				Return SetError(5, 0, False)
			EndIf
			Local $iValue = Int($vValue)
			Local $iMinimum = Int($g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingMinimum])
			Local $iMaximum = Int($g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingMaximum])
			; Out of range is clamped rather than refused: the control cannot hold the original either way, and a run that
			; keeps going at the nearest legal value beats one that silently ignored the setting.
			If $iValue < $iMinimum Then
				$sError = $sId & ": " & $iValue & " is below " & $iMinimum & ", used " & $iMinimum
				$iValue = $iMinimum
			ElseIf $iValue > $iMaximum Then
				$sError = $sId & ": " & $iValue & " is above " & $iMaximum & ", used " & $iMaximum
				$iValue = $iMaximum
			EndIf
			GUICtrlSetData($hControl, $iValue)

		Case "boolean"
			Local $bValid = False
			Local $bValue = _RunPlannerBooleanFromValue($vValue, $bValid)
			If Not $bValid Then
				$sError = $sId & ": " & String($vValue) & " is not a yes or no"
				Return SetError(6, 0, False)
			EndIf
			GUICtrlSetState($hControl, ($bValue ? $GUI_CHECKED : $GUI_UNCHECKED))

		Case Else
			GUICtrlSetData($hControl, String($vValue))
	EndSwitch

	Return True
EndFunc   ;==>_RunPlannerApplySetting

; Reads the plan file into the tab. Returns the number of settings applied, and leaves a one-line summary in
; $g_sRunPlannerPlanFileNote for whoever wants to show it.
Func RunPlannerApplyPlanFile($sPath, ByRef $sError)
	$sError = ""
	$g_sRunPlannerPlanFileNote = ""

	Local $oValues = RunPlanFileLoad($sPath, $sError)
	Local $iLoadStatus = @error ; captured before anything else can clear it
	If Not IsObj($oValues) Then
		; No file at all is the ordinary state, not a fault: nobody has opened the web planner on this machine.
		If $iLoadStatus = 2 Then
			$sError = ""
			Return SetError(1, 0, 0)
		EndIf
		Return SetError(2, 0, 0)
	EndIf

	Local $iApplied = 0, $iAdjusted = 0, $iRefused = 0, $iUnknown = 0
	Local $sFirstProblem = ""
	Local $aKeys = $oValues.Keys()

	For $i = 0 To UBound($aKeys) - 1
		Local $sKey = $aKeys[$i]
		Local $iSetting = RunPlannerSettingIndex($sKey)
		If $iSetting < 0 Then
			; A setting this build does not have. Older or newer plan files are readable either way, which is the point of
			; keying on setting ids rather than positions.
			$iUnknown += 1
			ContinueLoop
		EndIf

		Local $sSettingError = ""
		Local $bApplied = _RunPlannerApplySetting($iSetting, $oValues.Item($sKey), $sSettingError)
		If $bApplied Then
			$iApplied += 1
			If $sSettingError <> "" Then $iAdjusted += 1
		Else
			$iRefused += 1
		EndIf
		If $sSettingError <> "" And $sFirstProblem = "" Then $sFirstProblem = $sSettingError
	Next

	; The controls moved without anyone clicking them, so the derived panes have to be told.
	UpdateRunPlannerBanner()
	UpdateRunPlannerDetail("run.surface")

	$g_sRunPlannerPlanFileNote = "Loaded " & $iApplied & " setting" & (($iApplied = 1) ? "" : "s") & " from the run plan file"
	If $iAdjusted > 0 Then $g_sRunPlannerPlanFileNote &= ", " & $iAdjusted & " brought into range"
	If $iUnknown > 0 Then $g_sRunPlannerPlanFileNote &= ", ignored " & $iUnknown & " this build does not have"
	If $iRefused > 0 Then $g_sRunPlannerPlanFileNote &= ", refused " & $iRefused
	$sError = $sFirstProblem

	Return SetError(0, $iRefused, $iApplied)
EndFunc   ;==>RunPlannerApplyPlanFile

; Called wherever the tab is about to be believed. Cheap when nothing changed: it compares a timestamp and a size before it
; opens anything.
Func RunPlannerSyncPlanFile($bForce = False)
	; The mini GUI does not build the planner tab, so there are no controls to write into.
	If $g_iGuiMode <> 1 Then Return 0

	Local $sPath = RunPlanFileDefaultPath()
	Local $sStamp = RunPlanFileStamp($sPath)
	If Not $bForce And $sStamp = $g_sRunPlannerPlanFileStamp Then Return 0
	$g_sRunPlannerPlanFileStamp = $sStamp

	Local $sError = ""
	Local $iApplied = RunPlannerApplyPlanFile($sPath, $sError)
	Local $iStatus = @error

	If $iStatus = 1 Then Return 0 ; there is no plan file on this machine
	If $iStatus <> 0 Then
		SetLog("Run Planner: run plan file was not read - " & $sError, $COLOR_ERROR)
		If $g_hRunPlannerStatus <> 0 Then GUICtrlSetData($g_hRunPlannerStatus, "Run plan file could not be read")
		Return 0
	EndIf

	SetLog("Run Planner: " & $g_sRunPlannerPlanFileNote, ($sError = "") ? $COLOR_SUCCESS : $COLOR_ACTION)
	RunEventLogPlanFileLoaded($g_sRunPlannerPlanFileNote)
	If $sError <> "" Then SetLog("Run Planner: " & $sError, $COLOR_ACTION)
	If $g_hRunPlannerStatus <> 0 Then GUICtrlSetData($g_hRunPlannerStatus, $g_sRunPlannerPlanFileNote)
	Return $iApplied
EndFunc   ;==>RunPlannerSyncPlanFile

; The engine stores a plan mode; the planner stores an exact surface. This is the only place that maps between them.
Func RunPlannerPlanModeForSurface($sSurfaceId)
	Local $iIndex = CurrentGameFindBattleSurface($sSurfaceId)
	If $iIndex < 0 Then Return ""
	Local $sRoute = StringLower(StringStripWS($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleEngineRoute], $STR_STRIPALL))
	If $sRoute <> "" Then Return $sRoute
	Local $iParent = CurrentGameFindBattleSurface($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleParentSurface])
	If $iParent < 0 Then Return ""
	Return StringLower(StringStripWS($g_aCurrentGameBattleSurfaces[$iParent][$eGameBattleEngineRoute], $STR_STRIPALL))
EndFunc   ;==>RunPlannerPlanModeForSurface

Func RunPlannerBuildLoadout(ByRef $sError)
	$sError = ""
	Local $oLoadout = HeroLoadoutCreate($CURRENT_GAME_MAX_TOWN_HALL)
	If Not IsObj($oLoadout) Then
		$sError = "Unable to create a Hero loadout"
		Return SetError(1, 0, 0)
	EndIf
	If StringStripWS($g_sRunPlannerHeroIds, $STR_STRIPALL) = "" Then Return $oLoadout

	Local $aIds = StringSplit($g_sRunPlannerHeroIds, $HERO_LOADOUT_SEPARATOR, $STR_NOCOUNT)
	For $i = 0 To UBound($aIds) - 1
		If Not HeroLoadoutAdd($oLoadout, $aIds[$i], $sError) Then Return SetError(2, 0, 0)
	Next
	Return $oLoadout
EndFunc   ;==>RunPlannerBuildLoadout

Func RunPlannerBuildIntent(ByRef $sError)
	$sError = ""
	Local $sSurface = RunPlannerSelectedValue("run.surface")
	If $sSurface = "" Then
		$sError = "Choose a battle surface first"
		Return SetError(1, 0, 0)
	EndIf

	Local $sMode = RunPlannerPlanModeForSurface($sSurface)
	If $sMode = "" Then
		$sError = "Surface " & $sSurface & " has no reachable engine route"
		Return SetError(2, 0, 0)
	EndIf

	Local $sStrategy = RunPlannerSelectedValue("run.strategy")
	If $sStrategy = "" Then $sStrategy = "legacy.csv"

	Local $oPlan = RunPlanCreateDefault($sMode, $sStrategy)
	If Not IsObj($oPlan) Then
		$sError = "Unable to create a run plan"
		Return SetError(3, 0, 0)
	EndIf

	If Not RunPlanSetStopConditions($oPlan, RunPlannerReadInteger("run.duration_minutes"), RunPlannerReadInteger("run.max_battles"), RunPlannerReadBoolean("run.stop_on_star_bonus"), RunPlannerReadInteger("run.max_failures")) Then
		$sError = "Stop conditions are out of range"
		Return SetError(4, 0, 0)
	EndIf
	If Not RunPlanSetResourceTargets($oPlan, RunPlannerReadInteger("target.gold"), RunPlannerReadInteger("target.elixir"), RunPlannerReadInteger("target.dark_elixir")) Then
		$sError = "Resource targets are out of range"
		Return SetError(5, 0, 0)
	EndIf

	Local $sPolicy = RunPlannerSelectedValue("upgrade.policy")
	If $sPolicy <> "" Then $oPlan.Item("upgrade_policy") = $sPolicy
	$oPlan.Item("account_queue_id") = RunPlannerReadText("account.queue")

	Local $oLoadout = RunPlannerBuildLoadout($sError)
	If Not IsObj($oLoadout) Then Return SetError(6, 0, 0)

	Local $oIntent = RunIntentCreate($oPlan, $sSurface, $oLoadout, $sError)
	If Not IsObj($oIntent) Then Return SetError(7, 0, 0)

	If Not RunIntentSetPacing($oIntent, RunPlannerReadInteger("pacing.action_delay_ms"), RunPlannerReadInteger("pacing.settle_ms"), RunPlannerReadInteger("pacing.retry_attempts"), RunPlannerReadInteger("pacing.break_every_minutes"), RunPlannerReadInteger("pacing.break_minutes"), $sError) Then
		$sError = "Pacing is out of range: " & $sError
		Return SetError(8, 0, 0)
	EndIf

	; Diagnostic mode is the operator's choice, and the note is stored with the run so a later reader knows
	; the result was observed rather than demonstrated.
	If RunPlannerReadBoolean("run.diagnostic_mode") Then
		Local $sNote = RunPlannerReadText("run.diagnostic_note")
		If $sNote = "" Then
			$sError = "Add a diagnostic note naming who is watching this run"
			Return SetError(9, 0, 0)
		EndIf
		If Not RunIntentEnableDiagnostic($oIntent, $sNote, $sError) Then Return SetError(10, 0, 0)
	EndIf

	Return $oIntent
EndFunc   ;==>RunPlannerBuildIntent

Func UpdateRunPlannerBanner()
	If $g_hRunPlannerBanner = 0 Then Return
	Local $sSurface = RunPlannerSelectedValue("run.surface")
	If $sSurface = "" Then
		GUICtrlSetData($g_hRunPlannerBanner, "")
		Return
	EndIf

	Local $sReason = ""
	Local $sState = RunVerificationSurfaceState($sSurface, $sReason)
	If $sState = $RUN_VERIFICATION_VERIFIED Then
		GUICtrlSetData($g_hRunPlannerBanner, "Verified: this surface has been demonstrated on the current client.")
		GUICtrlSetColor($g_hRunPlannerBanner, $COLOR_GREEN)
		Return
	EndIf

	Local $sBanner = RunVerificationBanner($sState, $sReason)
	If Not RunPlannerReadBoolean("run.diagnostic_mode") Then
		$sBanner &= " Turn on the Diagnostics option to run it anyway."
	EndIf
	GUICtrlSetData($g_hRunPlannerBanner, $sBanner)
	GUICtrlSetColor($g_hRunPlannerBanner, $COLOR_MAROON)
EndFunc   ;==>UpdateRunPlannerBanner

Func UpdateRunPlannerDetail($sSettingId)
	If $g_hRunPlannerDetail = 0 Then Return
	Local $iSetting = RunPlannerSettingIndex($sSettingId)
	If $iSetting < 0 Then Return

	Local $sText = $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingDescription]
	Local $sValue = RunPlannerSelectedValue($sSettingId)
	Local $iOption = ($sValue = "") ? -1 : RunPlannerOptionIndex($sSettingId, $sValue)

	If $iOption >= 0 Then
		$sText &= @CRLF & @CRLF & $g_aRunPlannerOptions[$iOption][$eRunPlannerOptionLabel] & ": " & $g_aRunPlannerOptions[$iOption][$eRunPlannerOptionDescription]

		Local $sPrerequisites = $g_aRunPlannerOptions[$iOption][$eRunPlannerOptionPrerequisites]
		If $sPrerequisites <> "" Then
			$sText &= @CRLF & @CRLF & "Needs: " & StringReplace($sPrerequisites, $HERO_LOADOUT_SEPARATOR, ", ")
		EndIf

		Local $sDisabled = $g_aRunPlannerOptions[$iOption][$eRunPlannerOptionDisabledReason]
		If $sDisabled <> "" Then $sText &= @CRLF & @CRLF & "Not verified: " & $sDisabled

		Local $sWarning = $g_aRunPlannerOptions[$iOption][$eRunPlannerOptionWarning]
		If $sWarning <> "" Then $sText &= @CRLF & @CRLF & "Note: " & $sWarning
	EndIf

	GUICtrlSetData($g_hRunPlannerDetail, $sText)
EndFunc   ;==>UpdateRunPlannerDetail

Func RunPlannerRefreshHeroSelection()
	If $g_hRunPlannerHeroSelection = 0 Then Return
	If StringStripWS($g_sRunPlannerHeroIds, $STR_STRIPALL) = "" Then
		GUICtrlSetData($g_hRunPlannerHeroSelection, "No Heroes selected")
		Return
	EndIf

	Local $aIds = StringSplit($g_sRunPlannerHeroIds, $HERO_LOADOUT_SEPARATOR, $STR_NOCOUNT)
	Local $sLabels = ""
	For $i = 0 To UBound($aIds) - 1
		Local $iHero = CurrentGameFindHero($aIds[$i])
		Local $sLabel = ($iHero >= 0) ? $g_aCurrentGameHeroes[$iHero][$eGameHeroLabel] : $aIds[$i]
		$sLabels &= (($sLabels = "") ? "" : ", ") & $sLabel
	Next
	GUICtrlSetData($g_hRunPlannerHeroSelection, $sLabels & "   (" & UBound($aIds) & "/" & $CURRENT_GAME_MAX_ACTIVE_HERO_SLOTS & ")")
EndFunc   ;==>RunPlannerRefreshHeroSelection

Func btnRunPlannerHeroAdd()
	Local $sHero = RunPlannerSelectedValue("run.heroes")
	If $sHero = "" Then Return

	; Round-trip through the engine so the GUI cannot build a selection the engine would reject.
	Local $sError = ""
	Local $oLoadout = RunPlannerBuildLoadout($sError)
	If Not IsObj($oLoadout) Then
		GUICtrlSetData($g_hRunPlannerStatus, $sError)
		Return
	EndIf
	If Not HeroLoadoutAdd($oLoadout, $sHero, $sError) Then
		GUICtrlSetData($g_hRunPlannerStatus, $sError)
		Return
	EndIf

	$g_sRunPlannerHeroIds = $oLoadout.Item("hero_ids")
	GUICtrlSetData($g_hRunPlannerStatus, "")
	RunPlannerRefreshHeroSelection()
EndFunc   ;==>btnRunPlannerHeroAdd

Func btnRunPlannerHeroRemove()
	Local $sHero = RunPlannerSelectedValue("run.heroes")
	If $sHero = "" Then Return

	Local $sError = ""
	Local $oLoadout = RunPlannerBuildLoadout($sError)
	If Not IsObj($oLoadout) Then
		GUICtrlSetData($g_hRunPlannerStatus, $sError)
		Return
	EndIf
	If Not HeroLoadoutRemove($oLoadout, $sHero) Then
		GUICtrlSetData($g_hRunPlannerStatus, "That Hero is not in the active slots")
		Return
	EndIf

	$g_sRunPlannerHeroIds = $oLoadout.Item("hero_ids")
	GUICtrlSetData($g_hRunPlannerStatus, "")
	RunPlannerRefreshHeroSelection()
EndFunc   ;==>btnRunPlannerHeroRemove

Func btnRunPlannerApply()
	; The file has the last word, so a change made in the browser a moment ago is honoured rather than overwritten by
	; whatever the tab happened to be showing.
	RunPlannerSyncPlanFile()

	Local $sError = ""
	Local $oIntent = RunPlannerBuildIntent($sError)
	If Not IsObj($oIntent) Then
		GUICtrlSetData($g_hRunPlannerStatus, $sError)
		SetLog("Run Planner: " & $sError, $COLOR_ERROR)
		Return
	EndIf

	$g_oRunPlannerIntent = $oIntent

	; Apply prepares only. Pacing and every other override become active together at the explicit Start boundary.
	RunPacingDeactivate()

	; Recorded to the JSONL stream as well as the log, because the control centre's Activity panel reads that file and
	; applying a plan is the first thing an operator wants to see confirmed there.
	Local $sSurfaceId = $oIntent.Item("surface_id")

	Local $sReason = ""
	Local $bCanStart = RunIntentCanStart($oIntent, $sReason)
	If $bCanStart Then $bCanStart = RunExecutionContractValidate($oIntent, $sReason)
	If $bCanStart Then
		Local $sState = RunIntentVerificationState($oIntent)
		If $sState = $RUN_VERIFICATION_DIAGNOSTIC Then
			GUICtrlSetData($g_hRunPlannerStatus, "Ready as a diagnostic run")
			SetLog("Run Planner: " & RunIntentDescribe($oIntent), $COLOR_ACTION)
			SetLog("Run Planner: proceeding unverified - " & $sReason, $COLOR_ACTION)
		Else
			GUICtrlSetData($g_hRunPlannerStatus, "Ready")
			SetLog("Run Planner: " & RunIntentDescribe($oIntent), $COLOR_SUCCESS)
		EndIf
		RunEventLogPlanApplied($sSurfaceId, $sState, RunIntentDescribe($oIntent))
	Else
		GUICtrlSetData($g_hRunPlannerStatus, "Blocked")
		SetLog("Run Planner cannot start: " & $sReason, $COLOR_ERROR)
		RunEventLogPlanBlocked($sSurfaceId, $sReason)
	EndIf
	UpdateRunPlannerBanner()
EndFunc   ;==>btnRunPlannerApply

Func btnRunPlannerReset()
	For $i = 0 To UBound($g_aRunPlannerSettings, 1) - 1
		Local $hControl = $g_ahRunPlannerControls[$i]
		If $hControl = 0 Then ContinueLoop
		Local $sId = $g_aRunPlannerSettings[$i][$eRunPlannerSettingId]
		Switch StringLower($g_aRunPlannerSettings[$i][$eRunPlannerSettingType])
			Case "select", "multi-select"
				GUICtrlSetData($hControl, "")
				GUICtrlSetData($hControl, _RunPlannerOptionLabelList($sId), _RunPlannerDefaultLabel($sId, $g_aRunPlannerSettings[$i][$eRunPlannerSettingDefault]))
			Case "boolean"
				GUICtrlSetState($hControl, ($g_aRunPlannerSettings[$i][$eRunPlannerSettingDefault] ? $GUI_CHECKED : $GUI_UNCHECKED))
			Case Else
				GUICtrlSetData($hControl, $g_aRunPlannerSettings[$i][$eRunPlannerSettingDefault])
		EndSwitch
	Next
	$g_sRunPlannerHeroIds = ""
	$g_oRunPlannerIntent = 0
	; Reset drops the applied plan, so the pacing that came with it goes too rather than outliving the plan that set it.
	RunPacingDeactivate()
	RunPlannerRefreshHeroSelection()
	GUICtrlSetData($g_hRunPlannerStatus, "")
	UpdateRunPlannerBanner()
	UpdateRunPlannerDetail("run.surface")
EndFunc   ;==>btnRunPlannerReset

Func cmbRunPlannerSurface()
	UpdateRunPlannerBanner()
	UpdateRunPlannerDetail("run.surface")
EndFunc   ;==>cmbRunPlannerSurface

Func cmbRunPlannerHeroes()
	UpdateRunPlannerDetail("run.heroes")
EndFunc   ;==>cmbRunPlannerHeroes

Func cmbRunPlannerStrategy()
	UpdateRunPlannerDetail("run.strategy")
EndFunc   ;==>cmbRunPlannerStrategy

Func cmbRunPlannerEmulator()
	UpdateRunPlannerDetail("runtime.emulator")
EndFunc   ;==>cmbRunPlannerEmulator

Func cmbRunPlannerUpgradePolicy()
	UpdateRunPlannerDetail("upgrade.policy")
EndFunc   ;==>cmbRunPlannerUpgradePolicy

Func chkRunPlannerDiagnostic()
	UpdateRunPlannerBanner()
EndFunc   ;==>chkRunPlannerDiagnostic

Func btnRunPlannerRefresh()
	Local $bHealthy = _RunPlannerServiceHealthy()
	Local $sService = ($bHealthy ? "Control center online" : "Control center offline")
	Local $sPlan = "no saved plan"
	Local $bSaved = FileExists(RunPlanFileDefaultPath())
	If $bSaved Then $sPlan = "plan saved " & FileGetTime(RunPlanFileDefaultPath(), 0, 1)
	_RunPlannerSetLabel($g_hRunPlannerStatus, $sService & " · " & $sPlan, ($bHealthy And $bSaved ? $COLOR_GREEN : $COLOR_MAROON))
EndFunc   ;==>btnRunPlannerRefresh

Func btnRunPlannerOpen()
	Local $sError = ""
	If Not _RunPlannerStartService($sError) Then
		GUICtrlSetData($g_hRunPlannerStatus, $sError)
		SetLog("Run Planner: " & $sError, $COLOR_ERROR)
		btnRunPlannerRefresh()
		Return
	EndIf
	ShellExecute($RUN_PLANNER_URL)
	GUICtrlSetData($g_hRunPlannerStatus, "Control center opened")
	btnRunPlannerRefresh()
EndFunc   ;==>btnRunPlannerOpen

Func btnRunPlannerLoad()
	Local $sError = ""
	Local $oIntent = RunPlanFileLoadIntent(RunPlanFileDefaultPath(), $sError)
	If Not IsObj($oIntent) Then
		$g_oRunPlannerIntent = 0
		_RunPlannerSetLabel($g_hRunPlannerStatus, "Rejected · " & $sError, $COLOR_MAROON)
		SetLog("Run Planner: " & $sError, $COLOR_ERROR)
		Return
	EndIf
	$g_oRunPlannerIntent = $oIntent
	Local $sReason = ""
	Local $bCanStart = RunIntentCanStart($oIntent, $sReason)
	If $bCanStart Then $bCanStart = RunExecutionContractValidate($oIntent, $sReason)
	If $bCanStart Then
		_RunPlannerSetLabel($g_hRunPlannerStatus, "Prepared · engine gates cleared", $COLOR_GREEN)
	Else
		_RunPlannerSetLabel($g_hRunPlannerStatus, "Prepared · blocked: " & $sReason, $COLOR_MAROON)
	EndIf
	SetLog("Run Planner: " & RunIntentDescribe($oIntent), $COLOR_SUCCESS)
EndFunc   ;==>btnRunPlannerLoad

Func tabRunPlanner()
	If $g_iGuiMode <> 1 Then Return
	RunPlannerSyncPlanFile()
	UpdateRunPlannerBanner()
	RunPlannerRefreshHeroSelection()
	btnRunPlannerRefresh()
EndFunc   ;==>tabRunPlanner
