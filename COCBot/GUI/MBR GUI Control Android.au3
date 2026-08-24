; #FUNCTION# ====================================================================================================================
; Name ..........: MBR GUI Control Android
; Description ...: This file Includes all functions to current GUI
; Syntax ........: None
; Parameters ....:
; Return values .: None
; Author ........: MMHK (11-2016)
; Modified ......: CodeSlinger69 (2017)
; Remarks .......: This file is part of MyBot, previously known as ClashGameBot. Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
; Related .......:
; Link ..........: https://github.com/MyBotRun/MyBot/wiki
; Example .......: No
; ===============================================================================================================================
#include-once

Func LoadCOCDistributorsComboBox()
	Local $sDistributors = $g_sNO_COC
	Local $aDistributorsData = GetCOCDistributors()

	If @error = 2 Then
		$sDistributors = $g_sUNKNOWN_COC
	ElseIf IsArray($aDistributorsData) Then
		$sDistributors = _ArrayToString($aDistributorsData, "|")
	EndIf

	GUICtrlSetData($g_hCmbCOCDistributors, "", "")
	GUICtrlSetData($g_hCmbCOCDistributors, $sDistributors)
EndFunc   ;==>LoadCOCDistributorsComboBox

Func SetCurSelCmbCOCDistributors()
	Local $sIniDistributor
	Local $iIndex
	If _GUICtrlComboBox_GetCount($g_hCmbCOCDistributors) = 1 Then ; when no/unknown/one coc installed
		_GUICtrlComboBox_SetCurSel($g_hCmbCOCDistributors, 0)
		GUICtrlSetState($g_hCmbCOCDistributors, $GUI_DISABLE)
	Else
		$sIniDistributor = GetCOCTranslated($g_sAndroidGameDistributor)
		$iIndex = _GUICtrlComboBox_FindStringExact($g_hCmbCOCDistributors, $sIniDistributor)
		If $iIndex = -1 Then ; not found on combo
			_GUICtrlComboBox_SetCurSel($g_hCmbCOCDistributors, 0)
		Else
			_GUICtrlComboBox_SetCurSel($g_hCmbCOCDistributors, $iIndex)
		EndIf
		GUICtrlSetState($g_hCmbCOCDistributors, $GUI_ENABLE)
	EndIf
EndFunc   ;==>SetCurSelCmbCOCDistributors

Func cmbCOCDistributors()
	Local $sDistributor
	_GUICtrlComboBox_GetLBText($g_hCmbCOCDistributors, _GUICtrlComboBox_GetCurSel($g_hCmbCOCDistributors), $sDistributor)

	If $sDistributor = $g_sUserGameDistributor Then ; ini user option
		$g_sAndroidGameDistributor = $g_sUserGameDistributor
		$g_sAndroidGamePackage = $g_sUserGamePackage
		$g_sAndroidGameClass = $g_sUserGameClass
	Else
		GetCOCUnTranslated($sDistributor)
		If Not @error Then ; not no/unknown
			$g_sAndroidGameDistributor = GetCOCUnTranslated($sDistributor)
			$g_sAndroidGamePackage = GetCOCPackage($sDistributor)
			$g_sAndroidGameClass = GetCOCClass($sDistributor)
		EndIf ; else existing one (no emulator bot startup compatible), if wrong ini info either kept or replaced by cursel when saveconfig, not fall back to google
	EndIf
EndFunc   ;==>cmbCOCDistributors

Func DistributorsUpdateGUI()
	LoadCOCDistributorsComboBox()
	SetCurSelCmbCOCDistributors()
EndFunc   ;==>DistributorsUpdateGUI

Func AndroidSuspendFlagsToIndex($iFlags)
	Local $idx = 0
	If BitAND($iFlags, 2) > 0 Then
		$idx = 2
	ElseIf BitAND($iFlags, 1) > 0 Then
		$idx = 1
	EndIf
	If $idx > 0 And BitAND($iFlags, 4) > 0 Then $idx += 2
	Return $idx
EndFunc   ;==>AndroidSuspendFlagsToIndex

Func AndroidSuspendIndexToFlags($idx)
	Local $iFlags = 0
	Switch $idx
		Case 1
			$iFlags = 1
		Case 2
			$iFlags = 2
		Case 3
			$iFlags = 1 + 4
		Case 4
			$iFlags = 2 + 4
	EndSwitch
	Return $iFlags
EndFunc   ;==>AndroidSuspendIndexToFlags

Func cmbSuspendAndroid()
	$g_iAndroidSuspendModeFlags = AndroidSuspendIndexToFlags(_GUICtrlComboBox_GetCurSel($g_hCmbSuspendAndroid))
EndFunc   ;==>cmbSuspendAndroid

Func cmbAndroidBackgroundMode()
	$g_iAndroidBackgroundMode = _GUICtrlComboBox_GetCurSel($g_hCmbAndroidBackgroundMode)
	UpdateAndroidBackgroundMode()
EndFunc   ;==>cmbAndroidBackgroundMode

Func EnableShowTouchs()
	AndroidAdbSendShellCommand("content insert --uri content://settings/system --bind name:s:show_touches --bind value:i:1")
	SetDebugLog("EnableShowTouchs ON")
EndFunc   ;==>EnableShowTouchs

Func DisableShowTouchs()
	AndroidAdbSendShellCommand("content insert --uri content://settings/system --bind name:s:show_touches --bind value:i:0")
	SetDebugLog("EnableShowTouchs OFF")
EndFunc   ;==>DisableShowTouchs

Func sldAdditionalClickDelay($bSetControls = False)
	If $bSetControls Then
		GUICtrlSetData($g_hSldAdditionalClickDelay, Int($g_iAndroidControlClickAdditionalDelay / 2))
		GUICtrlSetData($g_hLblAdditionalClickDelay, $g_iAndroidControlClickAdditionalDelay & " ms")
	Else
		Local $iValue = GUICtrlRead($g_hSldAdditionalClickDelay) * 2
		If $iValue <> $g_iAndroidControlClickAdditionalDelay Then
			$g_iAndroidControlClickAdditionalDelay = $iValue
			GUICtrlSetData($g_hLblAdditionalClickDelay, $g_iAndroidControlClickAdditionalDelay & " ms")
		EndIf
	EndIf
	Opt("MouseClickDelay", GetClickUpDelay()) ;Default: 10 milliseconds
	Opt("MouseClickDownDelay", GetClickDownDelay()) ;Default: 5 milliseconds
EndFunc   ;==>sldAdditionalClickDelay

Func cmbAndroidEmulator()
	getAllEmulatorsInstances()
	Local $Emulator = GUICtrlRead($g_hCmbAndroidEmulator)
	If MsgBox($MB_YESNO, "Emulator Selection", $Emulator & ", Is correct?" & @CRLF & "Any mistake and your profile will be not useful!" & @CRLF & "If 'yes' and your instance is OK, is necessary " & @CRLF & "REBOOT the 'bot'.", 10) = $IDYES Then
		Local $sInstance = GUICtrlRead($g_hCmbAndroidInstance)
		If Not UpdateAndroidConfig($sInstance, $Emulator) Then
			If $g_sAndroidEmulator = $Emulator And $g_sAndroidInstance = $sInstance Then
				SetLog("The selected instance is reserved, but its Android transport is unavailable. Restart the bot before using Android controls.", $COLOR_ERROR)
			Else
				SetLog("Cannot select emulator instance; the previous instance remains reserved.", $COLOR_ERROR)
			EndIf
			_GUICtrlComboBox_SelectString($g_hCmbAndroidEmulator, $g_sAndroidEmulator)
			getAllEmulatorsInstances()
			Return
		EndIf
		SetLog("Emulator " & $Emulator & " Selected. Please select an Instance.")
		BtnSaveprofile()
	Else
		_GUICtrlComboBox_SelectString($g_hCmbAndroidEmulator, $g_sAndroidEmulator)
		getAllEmulatorsInstances()
	EndIf
EndFunc   ;==>cmbAndroidEmulator

Func cmbAndroidInstance()
	Local $Instance = GUICtrlRead($g_hCmbAndroidInstance)
	If MsgBox($MB_YESNO, "Instance Selection", $Instance & ", Is correct?" & @CRLF & "If 'yes' is necessary REBOOT the 'bot'.", 10) = $IDYES Then
		If Not UpdateAndroidConfig($Instance, $g_sAndroidEmulator) Then
			If $g_sAndroidInstance = $Instance Then
				SetLog("The selected instance is reserved, but its Android transport is unavailable. Restart the bot before using Android controls.", $COLOR_ERROR)
			Else
				SetLog("Cannot select emulator instance; the previous instance remains reserved.", $COLOR_ERROR)
			EndIf
			getAllEmulatorsInstances()
			Return
		EndIf
		SetLog("Instance " & $Instance & " Selected.")
		BtnSaveprofile()
	Else
		getAllEmulatorsInstances()
	EndIf
EndFunc   ;==>cmbAndroidInstance

Func InitializeConfiguredEmulatorSelection()
	GUICtrlSetData($g_hCmbAndroidEmulator, $g_sAndroidEmulator, $g_sAndroidEmulator)
	Local $sInstance = ($g_sAndroidInstance = "" ? "Android" : $g_sAndroidInstance)
	GUICtrlSetData($g_hCmbAndroidInstance, $sInstance, $sInstance)
	SetDebugLog("Configured emulator restored; installed-emulator scan deferred")
EndFunc   ;==>InitializeConfiguredEmulatorSelection

Func btnDetectEmulators()
	GUICtrlSetState($g_hBtnAndroidDetect, $GUI_DISABLE)
	SetLog("Scanning installed emulators…", $COLOR_INFO)
	getAllEmulators()
	GUICtrlSetState($g_hBtnAndroidDetect, $GUI_ENABLE)
EndFunc   ;==>btnDetectEmulators

Func getAllEmulators()

	; Initial Var with all emulators , will populate the ComboBox UI
	Local $sEmulatorString = ""

	; Reset content , Emulator ComboBox var
	GUICtrlSetData($g_hCmbAndroidEmulator, '')

	; Bluestacks :
	$__BlueStacks5_Version = RegRead($g_sHKLM & "\SOFTWARE\BlueStacks_nxt\", "Version")
    If Not @error Then
        If GetVersionNormalized($__BlueStacks5_Version) > GetVersionNormalized("5.0") Then $sEmulatorString &= "BlueStacks5|"
    EndIf

	; Nox :
	Local $NoxEmulator = GetNoxPath()
	If FileExists($NoxEmulator) Then $sEmulatorString &= "Nox|"

	; Memu :
	Local $MEmuEmulator = GetMEmuPath()
	If FileExists($MEmuEmulator) Then $sEmulatorString &= "MEmu|"

	; Current client emulator adapters
	Local $sLDPlayer9Version = RegRead($g_sHKLM & "\SOFTWARE" & $g_sWow6432Node & "\Microsoft\Windows\CurrentVersion\Uninstall\LDPlayer9\", "DisplayVersion")
	Local $iLDPlayer9RegError = @error
	If $iLDPlayer9RegError = 0 And GetVersionNormalized($sLDPlayer9Version) >= GetVersionNormalized("9.0") Then $sEmulatorString &= "LDPlayer9|"

	Local $sMumuVersion = RegRead($g_sHKLM & "\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MuMuPlayerGlobal\", "DisplayVersion")
	Local $iMumuRegError = @error
	If $iMumuRegError <> 0 Then
		$sMumuVersion = RegRead($g_sHKLM & "\SOFTWARE" & $g_sWow6432Node & "\Microsoft\Windows\CurrentVersion\Uninstall\MuMuPlayerGlobal\", "DisplayVersion")
		$iMumuRegError = @error
	EndIf
	If $iMumuRegError = 0 And GetVersionNormalized($sMumuVersion) >= GetVersionNormalized("5.0") Then $sEmulatorString &= "MuMu|"

	Local $sResult = StringRight($sEmulatorString, 1)
	If $sResult == "|" Then $sEmulatorString = StringTrimRight($sEmulatorString, 1)

	Local $aEmulator = StringSplit($sEmulatorString, "|", $STR_NOCOUNT)
	If $sEmulatorString <> "" Then
		SetLog("Emulator" & (UBound($aEmulator) > 1 ? "s" : "") & " Found In Your Machine :")
		For $i = 0 To UBound($aEmulator) - 1
			Local $emuVer = ""
			If StringInStr($aEmulator[$i], "BlueStacks5") Then $emuVer = $__BlueStacks5_Version
			If StringInStr($aEmulator[$i], "Memu") Then $emuVer = $__MEmu_Version
			If StringInStr($aEmulator[$i], "nox") Then $emuVer = $__Nox_Version
			; Current client emulator versions
			If StringInStr($aEmulator[$i], "LDPlayer9") Then $emuVer = $sLDPlayer9Version
			If StringInStr($aEmulator[$i], "MuMu") Then $emuVer = $sMumuVersion
			SetLog("  - " & $aEmulator[$i] & " version: " & $emuVer, $COLOR_SUCCESS)
		Next
	Else
		SetLog("No Emulator found in your machine")
		Return
	EndIf

	GUICtrlSetData($g_hCmbAndroidEmulator, $sEmulatorString)

	; $g_sAndroidEmulator Cosote Var to store the Emulator
	_GUICtrlComboBox_SelectString($g_hCmbAndroidEmulator, $g_sAndroidEmulator)

	; Lets get all Instances
	getAllEmulatorsInstances()
EndFunc   ;==>getAllEmulators

Func getAllEmulatorsInstances()

	; Reset content, Instance ComboBox var
	GUICtrlSetData($g_hCmbAndroidInstance, '')

	; Get all Instances from SELECTED EMULATOR - $g_hCmbAndroidEmulator is the Emulator ComboBox
	Local $Emulator = GUICtrlRead($g_hCmbAndroidEmulator)
	Local $sEmulatorPath = 0

	Switch $emulator
		Case "BlueStacks5"
            Local $VMsBlueStacks = RegRead($g_sHKLM & "\SOFTWARE\BlueStacks_nxt\", "DataDir")
            $sEmulatorPath = $VMsBlueStacks ; C:\ProgramData\BlueStacks\Engine
		Case "Nox"
			$sEmulatorPath = GetNoxPath() & "\BignoxVMS"
		Case "MEmu"
			$sEmulatorPath = GetMEmuPath() & "\MemuHyperv VMs"
		; Current client emulator instance roots
		Case "LDPlayer9"
			Local $sLDPlayerPath = RegRead($g_sHKLM & "\SOFTWARE\XuanZhi\LDPlayer9\", "InstallDir")
			$sEmulatorPath = $sLDPlayerPath & "vms\"
		Case "MuMu"
			Local $sMumuUninstall = RegRead($g_sHKLM & "\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MuMuPlayerGlobal\", "UninstallString")
			If @error Then $sMumuUninstall = RegRead($g_sHKLM & "\SOFTWARE" & $g_sWow6432Node & "\Microsoft\Windows\CurrentVersion\Uninstall\MuMuPlayerGlobal\", "UninstallString")
			$sEmulatorPath = StringReplace(StringReplace($sMumuUninstall, "uninstall.exe", "vms"), Chr(34), "")
		Case Else
			GUICtrlSetData($g_hCmbAndroidInstance, "Android", "Android")
			Return
	EndSwitch

	; Just in case
	$sEmulatorPath = StringReplace($sEmulatorPath, "\\", "\")

	; BS Multi Instance
	Local $sBlueStacksFolder = ($Emulator = "BlueStacks5") ? ("Pie*;Oreo*;Nougat*;Android*") : ("*")

	; Getting all VM Folders
	Local $eError = 0

	; Populating the Instance ComboBox var
	Local $aEmulatorFolders = _FileListToArrayRec($sEmulatorPath, $sBlueStacksFolder, $FLTA_FOLDERS)
	$eError = @error
	If $eError = 0 Then
		GUICtrlSetData($g_hCmbAndroidInstance, StringReplace(_ArrayToString($aEmulatorFolders, "|", 1), "\", ""))
	EndIf

	If $emulator == $g_sAndroidEmulator Then
		_GUICtrlComboBox_SelectString($g_hCmbAndroidInstance, $g_sAndroidInstance)
	Else
		_GUICtrlComboBox_SetCurSel($g_hCmbAndroidInstance, 0)
	EndIf
EndFunc   ;==>getAllEmulatorsInstances
