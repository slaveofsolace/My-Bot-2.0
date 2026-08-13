; #FUNCTION# ====================================================================================================================
; Name ..........: MBR GUI Design Run Planner
; Description ...: Builds the Run Planner tab from the generated planner metadata.
; Remarks .......: Controls are rendered from $g_aRunPlannerSettings rather than laid out by hand, so adding a battle surface
;                  or changing a disabled reason is a catalog edit. This file is part of My Bot, distributed under the GNU GPL.
; ===============================================================================================================================
#include-once
#include "RunPlannerMetadata.generated.au3"

Global $g_hGUI_RUNPLANNER = 0
Global $g_hRunPlannerTab = 0
Global $g_hRunPlannerBanner = 0
Global $g_hRunPlannerDetail = 0
Global $g_hRunPlannerStatus = 0
Global $g_hBtnRunPlannerApply = 0
Global $g_hBtnRunPlannerReset = 0
Global $g_hBtnRunPlannerOpen = 0
Global $g_hBtnRunPlannerLoad = 0
Global $g_hBtnRunPlannerRefresh = 0
Global $g_hBtnRunPlannerHeroAdd = 0
Global $g_hBtnRunPlannerHeroRemove = 0
Global $g_hRunPlannerHeroSelection = 0

; One control handle per row of $g_aRunPlannerSettings, plus the buddy controls some types need.
Global $g_ahRunPlannerControls[UBound($g_aRunPlannerSettings, 1)]
Global $g_ahRunPlannerBuddies[UBound($g_aRunPlannerSettings, 1)]
Global $g_ahRunPlannerTabItems[UBound($g_aRunPlannerSections, 1)]

; A combo cannot grey out individual entries, so availability is marked in the text itself and the detail pane
; below spells out what is missing. One decorator keeps the list, the default, and the reverse lookup consistent.
Func _RunPlannerDecoratedLabel($iOptionRow)
	Local $sLabel = $g_aRunPlannerOptions[$iOptionRow][$eRunPlannerOptionLabel]
	Switch StringLower($g_aRunPlannerOptions[$iOptionRow][$eRunPlannerOptionAvailability])
		Case "available"
			If $g_aRunPlannerOptions[$iOptionRow][$eRunPlannerOptionRecommended] Then $sLabel &= "  (recommended)"
		Case "planned"
			$sLabel &= "  (not implemented)"
		Case "unsupported"
			$sLabel &= "  (unsupported)"
		Case Else
			$sLabel &= "  (unverified)"
	EndSwitch
	Return $sLabel
EndFunc   ;==>_RunPlannerDecoratedLabel

Func _RunPlannerOptionLabelList($sSettingId)
	Local $sList = ""
	For $i = 0 To UBound($g_aRunPlannerOptions, 1) - 1
		If $g_aRunPlannerOptions[$i][$eRunPlannerOptionSettingId] <> $sSettingId Then ContinueLoop
		If Not _RunPlannerOptionSelectable($i) Then ContinueLoop
		$sList &= (($sList = "") ? "" : "|") & _RunPlannerDecoratedLabel($i)
	Next
	Return $sList
EndFunc   ;==>_RunPlannerOptionLabelList

; Native combo boxes cannot disable individual rows. Omit choices that the execution contract cannot
; represent instead of letting the operator select a value that is guaranteed to fail at Apply/Start.
Func _RunPlannerOptionSelectable($iOptionRow)
	If $iOptionRow < 0 Or $iOptionRow >= UBound($g_aRunPlannerOptions, 1) Then Return False
	Switch StringLower($g_aRunPlannerOptions[$iOptionRow][$eRunPlannerOptionAvailability])
		Case "planned", "unsupported"
			Return False
	EndSwitch
	Return True
EndFunc   ;==>_RunPlannerOptionSelectable

; The GUI runs in OnEvent mode, so each interactive control needs a named handler. Settings without one simply
; hold their value until Apply reads them.
Func _RunPlannerHandlerFor($sSettingId)
	Switch $sSettingId
		Case "run.surface"
			Return "cmbRunPlannerSurface"
		Case "run.heroes"
			Return "cmbRunPlannerHeroes"
		Case "run.town_hall"
			Return "inpRunPlannerTownHall"
		Case "run.strategy"
			Return "cmbRunPlannerStrategy"
		Case "runtime.emulator"
			Return "cmbRunPlannerEmulator"
		Case "upgrade.policy"
			Return "cmbRunPlannerUpgradePolicy"
		Case "run.diagnostic_mode"
			Return "chkRunPlannerDiagnostic"
	EndSwitch
	Return ""
EndFunc   ;==>_RunPlannerHandlerFor

; Availability, expressed as colour. Green reads as demonstrated, maroon as not yet, grey as absent.
Func _RunPlannerTintForAvailability($hControl, $sSettingId, $sValue)
	If $hControl = 0 Then Return
	For $i = 0 To UBound($g_aRunPlannerOptions, 1) - 1
		If $g_aRunPlannerOptions[$i][$eRunPlannerOptionSettingId] <> $sSettingId Then ContinueLoop
		If $g_aRunPlannerOptions[$i][$eRunPlannerOptionValue] <> $sValue Then ContinueLoop
		Switch StringLower($g_aRunPlannerOptions[$i][$eRunPlannerOptionAvailability])
			Case "available"
				GUICtrlSetColor($hControl, $COLOR_GREEN)
			Case "planned", "unsupported"
				GUICtrlSetColor($hControl, $COLOR_GRAY)
			Case Else
				GUICtrlSetColor($hControl, $COLOR_MAROON)
		EndSwitch
		Return
	Next
EndFunc   ;==>_RunPlannerTintForAvailability

Func _RunPlannerDefaultLabel($sSettingId, $sValue)
	For $i = 0 To UBound($g_aRunPlannerOptions, 1) - 1
		If $g_aRunPlannerOptions[$i][$eRunPlannerOptionSettingId] <> $sSettingId Then ContinueLoop
		If $g_aRunPlannerOptions[$i][$eRunPlannerOptionValue] <> $sValue Then ContinueLoop
		Return _RunPlannerDecoratedLabel($i)
	Next
	Return ""
EndFunc   ;==>_RunPlannerDefaultLabel

; Keep the native tab faithful to the same fixed-value contract the browser renders. These values
; remain visible with an explanation, but neither mouse/keyboard input nor a hand-edited plan can
; leave the controls displaying an option the engine will refuse.
Func _RunPlannerApplyNativeFixedState($iSetting)
	If $iSetting < 0 Or $iSetting >= UBound($g_aRunPlannerSettings, 1) Then Return
	If Not $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingNativeFixed] Then Return
	Local $hControl = $g_ahRunPlannerControls[$iSetting]
	If $hControl = 0 Then Return
	Local $vFixed = $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingNativeFixedValue]
	Switch StringLower($g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingType])
		Case "boolean"
			GUICtrlSetState($hControl, ($vFixed ? $GUI_CHECKED : $GUI_UNCHECKED))
		Case Else
			GUICtrlSetData($hControl, $vFixed)
	EndSwitch
	GUICtrlSetState($hControl, $GUI_DISABLE)
	If $g_ahRunPlannerBuddies[$iSetting] <> 0 Then GUICtrlSetState($g_ahRunPlannerBuddies[$iSetting], $GUI_DISABLE)
	_GUICtrlSetTip($hControl, $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingNativeFixedReason])
EndFunc   ;==>_RunPlannerApplyNativeFixedState

Func _RunPlannerApplyAllNativeFixedStates()
	For $i = 0 To UBound($g_aRunPlannerSettings, 1) - 1
		_RunPlannerApplyNativeFixedState($i)
	Next
EndFunc   ;==>_RunPlannerApplyAllNativeFixedStates

Func CreateRunPlannerTab()
	$g_hGUI_RUNPLANNER = _GUICreate("", $g_iSizeWGrpTab1, $g_iSizeHGrpTab1, $_GUI_CHILD_LEFT, $_GUI_CHILD_TOP, BitOR($WS_CHILD, $WS_TABSTOP), -1, $g_hFrmBotEx)

	Local $iLeft = 8
	Local $iWidth = $g_iSizeWGrpTab1 - 22
	Local $y = 6

	GUICtrlCreateLabel($RUN_PLANNER_TITLE, $iLeft, $y, $iWidth, 18)
	GUICtrlSetFont(-1, 10, $FW_BOLD, Default, "Arial")
	$y += 20

	GUICtrlCreateLabel($RUN_PLANNER_DESCRIPTION, $iLeft, $y, $iWidth, 32)
	GUICtrlSetFont(-1, 8, $FW_NORMAL, Default, "Arial")
	$y += 36

	; Verification banner. Filled in by UpdateRunPlannerBanner() once a surface is chosen.
	$g_hRunPlannerBanner = GUICtrlCreateLabel("", $iLeft, $y, $iWidth, 28)
	GUICtrlSetFont(-1, 8, $FW_BOLD, Default, "Arial")
	GUICtrlSetColor(-1, $COLOR_MAROON)
	$y += 32

	; 52px of multiline tab headers plus six 26px rows on the Army page.
	$g_hRunPlannerTab = GUICtrlCreateTab($iLeft, $y, $iWidth, 204, $TCS_MULTILINE)
	GUICtrlSetResizing(-1, $GUI_DOCKBORDERS)

	Local $iSettingRow = 0
	For $iSection = 0 To UBound($g_aRunPlannerSections, 1) - 1
		Local $sSectionId = $g_aRunPlannerSections[$iSection][$eRunPlannerSectionId]
		$g_ahRunPlannerTabItems[$iSection] = GUICtrlCreateTabItem($g_aRunPlannerSections[$iSection][$eRunPlannerSectionTabLabel])

		Local $iRowY = $y + 52
		Local $iLabelX = $iLeft + 8
		Local $iCtrlX = $iLeft + 150
		Local $iCtrlW = $iWidth - 166

		For $iSetting = 0 To UBound($g_aRunPlannerSettings, 1) - 1
			If $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingSectionId] <> $sSectionId Then ContinueLoop

			Local $sId = $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingId]
			Local $sType = StringLower($g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingType])
			Local $sLabel = $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingLabel]
			If $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingRequired] Then $sLabel &= " *"

			GUICtrlCreateLabel($sLabel, $iLabelX, $iRowY + 3, 138, 18)
			GUICtrlSetFont(-1, 8.5, ($g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingRequired] ? $FW_BOLD : $FW_NORMAL), Default, "Arial")
			_GUICtrlSetTip(-1, $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingSummary])

			Switch $sType
				Case "select"
					$g_ahRunPlannerControls[$iSetting] = GUICtrlCreateCombo("", $iCtrlX, $iRowY, $iCtrlW, 20, BitOR($CBS_DROPDOWNLIST, $WS_VSCROLL))
					GUICtrlSetData(-1, _RunPlannerOptionLabelList($sId), _RunPlannerDefaultLabel($sId, $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingDefault]))
					_GUICtrlSetTip(-1, $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingDescription])
					If _RunPlannerHandlerFor($sId) <> "" Then GUICtrlSetOnEvent(-1, _RunPlannerHandlerFor($sId))
					_RunPlannerTintForAvailability($g_ahRunPlannerControls[$iSetting], $sId, $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingDefault])
					$iRowY += 26

				Case "multi-select"
					; Four active slots out of six Heroes, so this is a picker plus a running selection, not one choice.
					$g_ahRunPlannerControls[$iSetting] = GUICtrlCreateCombo("", $iCtrlX, $iRowY, $iCtrlW - 90, 20, BitOR($CBS_DROPDOWNLIST, $WS_VSCROLL))
					GUICtrlSetData(-1, _RunPlannerOptionLabelList($sId), _RunPlannerDefaultLabel($sId, $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingDefault]))
					_GUICtrlSetTip(-1, $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingDescription])
					If _RunPlannerHandlerFor($sId) <> "" Then GUICtrlSetOnEvent(-1, _RunPlannerHandlerFor($sId))
					$g_hBtnRunPlannerHeroAdd = GUICtrlCreateButton("Add", $iCtrlX + $iCtrlW - 86, $iRowY, 40, 21)
					GUICtrlSetOnEvent(-1, "btnRunPlannerHeroAdd")
					_GUICtrlSetTip(-1, "Puts the selected Hero into an active slot.")
					$g_hBtnRunPlannerHeroRemove = GUICtrlCreateButton("Drop", $iCtrlX + $iCtrlW - 43, $iRowY, 43, 21)
					GUICtrlSetOnEvent(-1, "btnRunPlannerHeroRemove")
					_GUICtrlSetTip(-1, "Frees the slot the selected Hero occupies.")
					$iRowY += 26
					GUICtrlCreateLabel("Active slots", $iLabelX, $iRowY + 3, 138, 18)
					GUICtrlSetFont(-1, 8.5, $FW_NORMAL, Default, "Arial")
					$g_hRunPlannerHeroSelection = GUICtrlCreateInput("", $iCtrlX, $iRowY, $iCtrlW, 20, BitOR($ES_READONLY, $ES_AUTOHSCROLL))
					$g_ahRunPlannerBuddies[$iSetting] = $g_hRunPlannerHeroSelection
					$iRowY += 26

				Case "integer"
					$g_ahRunPlannerControls[$iSetting] = GUICtrlCreateInput($g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingDefault], $iCtrlX, $iRowY, 90, 20, BitOR($ES_NUMBER, $ES_RIGHT))
					_GUICtrlSetTip(-1, $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingDescription])
					$g_ahRunPlannerBuddies[$iSetting] = GUICtrlCreateUpdown(-1)
					GUICtrlSetLimit(-1, $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingMaximum], $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingMinimum])
					Local $sUnit = $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingUnit]
					If $sUnit <> "" Then
						GUICtrlCreateLabel($sUnit, $iCtrlX + 96, $iRowY + 3, $iCtrlW - 96, 18)
						GUICtrlSetFont(-1, 8, $FW_NORMAL, Default, "Arial")
						GUICtrlSetColor(-1, $COLOR_GRAY)
					EndIf
					$iRowY += 26

				Case "boolean"
					$g_ahRunPlannerControls[$iSetting] = GUICtrlCreateCheckbox("", $iCtrlX, $iRowY, 20, 20)
					If $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingDefault] Then GUICtrlSetState(-1, $GUI_CHECKED)
					_GUICtrlSetTip(-1, $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingDescription])
					If _RunPlannerHandlerFor($sId) <> "" Then GUICtrlSetOnEvent(-1, _RunPlannerHandlerFor($sId))
					GUICtrlCreateLabel($g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingSummary], $iCtrlX + 24, $iRowY + 3, $iCtrlW - 24, 18)
					GUICtrlSetFont(-1, 8, $FW_NORMAL, Default, "Arial")
					GUICtrlSetColor(-1, $COLOR_GRAY)
					$iRowY += 26

				Case Else
					; instance-select and profile-queue are free text until their sources can be enumerated.
					$g_ahRunPlannerControls[$iSetting] = GUICtrlCreateInput($g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingDefault], $iCtrlX, $iRowY, $iCtrlW, 20, $ES_AUTOHSCROLL)
					_GUICtrlSetTip(-1, $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingDescription])
					Local $sEmpty = $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingEmptyState]
					If $sEmpty <> "" Then
						$iRowY += 20
						GUICtrlCreateLabel($sEmpty, $iCtrlX, $iRowY, $iCtrlW, 16)
						GUICtrlSetFont(-1, 7.5, $FW_NORMAL, Default, "Arial")
						GUICtrlSetColor(-1, $COLOR_GRAY)
						$iRowY += 8
					EndIf
					$iRowY += 26
			EndSwitch
			_RunPlannerApplyNativeFixedState($iSetting)
			$iSettingRow += 1
		Next
	Next
	GUICtrlCreateTabItem("")

	$y += 210

	GUICtrlCreateLabel("About the selected option", $iLeft, $y, $iWidth, 16)
	GUICtrlSetFont(-1, 8.5, $FW_BOLD, Default, "Arial")
	$y += 18
	$g_hRunPlannerDetail = GUICtrlCreateEdit("Select a control to see what it does and what it still needs.", $iLeft, $y, $iWidth, 60, BitOR($ES_READONLY, $ES_MULTILINE, $WS_VSCROLL))
	GUICtrlSetFont(-1, 8, $FW_NORMAL, Default, "Arial")
	GUICtrlSetBkColor(-1, $COLOR_WHITE)
	$y += 66

	$g_hBtnRunPlannerApply = GUICtrlCreateButton("Apply", $iLeft, $y, 70, 24)
	GUICtrlSetOnEvent(-1, "btnRunPlannerApply")
	_GUICtrlSetTip(-1, "Builds the run intent from these settings and reports whether it can start.")
	$g_hBtnRunPlannerReset = GUICtrlCreateButton("Reset", $iLeft + 75, $y, 55, 24)
	GUICtrlSetOnEvent(-1, "btnRunPlannerReset")
	_GUICtrlSetTip(-1, "Restores every control to its default.")
	$g_hBtnRunPlannerOpen = GUICtrlCreateButton("Open center", $iLeft + 135, $y, 105, 24)
	GUICtrlSetOnEvent(-1, "btnRunPlannerOpen")
	_GUICtrlSetTip(-1, "Starts the loopback planner service when needed, then opens it in your browser.")
	$g_hBtnRunPlannerLoad = GUICtrlCreateButton("Load saved", $iLeft + 245, $y, 100, 24)
	GUICtrlSetOnEvent(-1, "btnRunPlannerLoad")
	_GUICtrlSetTip(-1, "Revalidates the saved plan and prepares an engine RunIntent.")
	$g_hBtnRunPlannerRefresh = GUICtrlCreateButton("Refresh", $iLeft + 350, $y, 60, 24)
	GUICtrlSetOnEvent(-1, "btnRunPlannerRefresh")
	$y += 28
	$g_hRunPlannerStatus = GUICtrlCreateLabel("", $iLeft, $y + 2, $iWidth, 18)
	GUICtrlSetFont(-1, 8, $FW_NORMAL, Default, "Arial")

	GUISetState(@SW_HIDE, $g_hGUI_RUNPLANNER)
EndFunc   ;==>CreateRunPlannerTab
