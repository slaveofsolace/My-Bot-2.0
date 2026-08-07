; #FUNCTION# ====================================================================================================================
; Name ..........: MBR GUI Control Run Planner
; Description ...: Reads the Run Planner controls and turns them into a run intent the engine can act on.
; Remarks .......: This is the whole engine boundary for the planner: the GUI never touches battle code directly, it builds a
;                  RunIntent and reports what the engine says about it. This file is part of My Bot, distributed under the GNU GPL.
; ===============================================================================================================================
#include-once
#include "MBR GUI Design Run Planner.au3"
#include "..\functions\Run\RunIntent.au3"

Global $g_oRunPlannerIntent = 0
Global $g_sRunPlannerHeroIds = ""

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

	; Diagnostic mode is the operator's choice, and the note is stored with the run so a later reader knows
	; the result was observed rather than demonstrated.
	If RunPlannerReadBoolean("run.diagnostic_mode") Then
		Local $sNote = RunPlannerReadText("run.diagnostic_note")
		If $sNote = "" Then
			$sError = "Add a diagnostic note naming who is watching this run"
			Return SetError(8, 0, 0)
		EndIf
		If Not RunIntentEnableDiagnostic($oIntent, $sNote, $sError) Then Return SetError(9, 0, 0)
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
	Local $sError = ""
	Local $oIntent = RunPlannerBuildIntent($sError)
	If Not IsObj($oIntent) Then
		GUICtrlSetData($g_hRunPlannerStatus, $sError)
		SetLog("Run Planner: " & $sError, $COLOR_ERROR)
		Return
	EndIf

	$g_oRunPlannerIntent = $oIntent

	Local $sReason = ""
	If RunIntentCanStart($oIntent, $sReason) Then
		Local $sState = RunIntentVerificationState($oIntent)
		If $sState = $RUN_VERIFICATION_DIAGNOSTIC Then
			GUICtrlSetData($g_hRunPlannerStatus, "Ready as a diagnostic run")
			SetLog("Run Planner: " & RunIntentDescribe($oIntent), $COLOR_ACTION)
			SetLog("Run Planner: proceeding unverified - " & $sReason, $COLOR_ACTION)
		Else
			GUICtrlSetData($g_hRunPlannerStatus, "Ready")
			SetLog("Run Planner: " & RunIntentDescribe($oIntent), $COLOR_SUCCESS)
		EndIf
	Else
		GUICtrlSetData($g_hRunPlannerStatus, "Blocked")
		SetLog("Run Planner cannot start: " & $sReason, $COLOR_ERROR)
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

Func tabRunPlanner()
	If $g_iGuiMode <> 1 Then Return
	UpdateRunPlannerBanner()
	RunPlannerRefreshHeroSelection()
EndFunc   ;==>tabRunPlanner
