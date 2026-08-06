; #FUNCTION# ====================================================================================================================
; Name ..........: MuMu Player adapter
; Description ...: Discovers, configures, starts, stops, and addresses MuMu Player 12 instances.
; Source lineage : Adapted for the v8.2.0 engine from xbebenk/MBR_xbebenkMod.
; ===============================================================================================================================
#include-once

Global $__Mumu_Version = ""
Global $__Mumu_Path = ""
Global $__Mumu_Device_Path = ""
Global $__Mumu_Manage_Path = ""
Global $__Mumu_ConfigDir = ""

Func _MumuInstanceIndex()
	Local $sIndex = StringReplace($g_sAndroidInstance, "MuMuPlayerGlobal-12.0-", "")
	If Not StringIsInt($sIndex) Then $sIndex = "0"
	Return Int($sIndex)
EndFunc   ;==>_MumuInstanceIndex

Func _MumuReadInstallPath()
	Local $sUninstall = RegRead($g_sHKLM & "\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MuMuPlayerGlobal\", "UninstallString")
	If @error Or $sUninstall = "" Then $sUninstall = RegRead($g_sHKLM & "\SOFTWARE" & $g_sWow6432Node & "\Microsoft\Windows\CurrentVersion\Uninstall\MuMuPlayerGlobal\", "UninstallString")
	Local $sRoot = StringReplace(StringReplace($sUninstall, "uninstall.exe", ""), '"', "")
	$sRoot = StringReplace($sRoot, "\\", "\")
	If $sRoot <> "" And StringRight($sRoot, 1) <> "\" Then $sRoot &= "\"
	Return $sRoot
EndFunc   ;==>_MumuReadInstallPath

Func GetMumuProgramParameter($bAlternative = False)
	Return AddSpace("-v " & _MumuInstanceIndex())
EndFunc   ;==>GetMumuProgramParameter

Func GetMumuAdbPath()
	Local $sEmulatorAdb = $__Mumu_Device_Path & "adb.exe"
	If FileExists($sEmulatorAdb) Then Return $sEmulatorAdb
	Local $sBundledAdb = @ScriptDir & "\lib\adb\adb.exe"
	If FileExists($sBundledAdb) Then Return $sBundledAdb
	Return ""
EndFunc   ;==>GetMumuAdbPath

Func _ResolveMumuAdbPath()
	Local $sPath = GetMumuAdbPath()
	If $g_iAndroidAdbReplace = 1 Then
		Local $sBundled = @ScriptDir & "\lib\adb\adb.exe"
		If FileExists($sBundled) Then $sPath = $sBundled
	EndIf
	Return $sPath
EndFunc   ;==>_ResolveMumuAdbPath

Func InitMumuX($bCheckOnly = False)
	$__Mumu_Version = RegRead($g_sHKLM & "\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MuMuPlayerGlobal\", "DisplayVersion")
	If @error Or $__Mumu_Version = "" Then $__Mumu_Version = RegRead($g_sHKLM & "\SOFTWARE" & $g_sWow6432Node & "\Microsoft\Windows\CurrentVersion\Uninstall\MuMuPlayerGlobal\", "DisplayVersion")
	$__Mumu_Path = _MumuReadInstallPath()
	$__Mumu_Device_Path = $__Mumu_Path & "nx_device\12.0\shell\"
	$__Mumu_Manage_Path = $__Mumu_Path & "nx_main\"

	Local $sProgram = $__Mumu_Device_Path & "MuMuNxDevice.exe"
	Local $sManager = $__Mumu_Manage_Path & "MuMuManager.exe"
	If $__Mumu_Path = "" Or Not FileExists($sProgram) Or Not FileExists($sManager) Then
		If Not $bCheckOnly Then SetLog("MuMu Player installation is incomplete or could not be located", $COLOR_ERROR)
		Return SetError(1, 0, False)
	EndIf

	Local $sAdbPath = _ResolveMumuAdbPath()
	If $sAdbPath = "" Then
		If Not $bCheckOnly Then SetLog("No compatible ADB executable was found for MuMu Player", $COLOR_ERROR)
		Return SetError(2, 0, False)
	EndIf

	If Not $bCheckOnly Then
		$g_sAndroidPath = $__Mumu_Path
		$g_sAndroidProgramPath = $sProgram
		$g_sAndroidAdbPath = $sAdbPath
		$g_sAndroidVersion = $__Mumu_Version
		ConfigureSharedFolderMumu()
		WinGetAndroidHandle()
	EndIf
	Return True
EndFunc   ;==>InitMumuX

Func InitMumu($bCheckOnly = False)
	Local $bInstalled = InitMumuX($bCheckOnly)
	If Not $bInstalled Then Return False
	If $__Mumu_Version <> "" And GetVersionNormalized($__Mumu_Version) < GetVersionNormalized("5.0") Then
		If Not $bCheckOnly Then SetLog("MuMu Player 5 or newer is required", $COLOR_ERROR)
		Return SetError(3, 0, False)
	EndIf
	If Not $bCheckOnly Then
		$g_sAndroidAdbShellOptions = " /system/xbin/su root"
		GetMumuBackgroundMode()
	EndIf
	Return True
EndFunc   ;==>InitMumu

Func OpenMumu($bRestart = False)
	SetLog("Starting MuMu Player", $COLOR_SUCCESS)
	If Not InitAndroid() Then Return False
	Local $sManager = $__Mumu_Manage_Path & "MuMuManager.exe", $process_killed
	Local $sParameters = "control launch --vmindex " & _MumuInstanceIndex()
	LaunchConsole($g_sAndroidAdbPath, AddSpace($g_sAndroidAdbGlobalOptions) & "start-server", $process_killed)
	If WinGetAndroidHandle() = 0 Then
		LaunchConsole($sManager, AddSpace($sParameters), $process_killed)
		If _SleepStatus(5000) Then Return False
	Else
		SetLog("MuMu Player is already running")
		Return True
	EndIf

	Local $hTimer = __TimerInit()
	While $g_hAndroidControl = 0
		_StatusUpdateTime($hTimer, $g_sAndroidEmulator & " Starting")
		If __TimerDiff($hTimer) > $g_iAndroidLaunchWaitSec * 1000 Then
			SetLog("MuMu Player did not become ready within the configured launch timeout", $COLOR_ERROR)
			Return SetError(1, 0, False)
		EndIf
		If _Sleep(500) Then Return False
		WinGetAndroidHandle()
	WEnd

	ConnectAndroidAdb(False, 3000)
	If WaitForAndroidBootCompleted($g_iAndroidLaunchWaitSec - __TimerDiff($hTimer) / 1000, $hTimer) Then Return False
	SetLog("MuMu Player loaded in " & Round(__TimerDiff($hTimer) / 1000, 2) & " seconds", $COLOR_SUCCESS)
	Return True
EndFunc   ;==>OpenMumu

Func ConfigureSharedFolderMumu($iMode = 0, $bSetLog = Default)
	Local $iIndex = _MumuInstanceIndex()
	Local $sInstance = "MuMuPlayerGlobal-12.0-" & $iIndex
	Local $sConfig = $__Mumu_Path & "vms\" & $sInstance & "\" & $sInstance & ".nemu"
	Local $aLines = FileReadToArray($sConfig)
	If @error Then Return SetError(1, 0, False)

	Local $bSharedFolder = False
	For $i = 0 To UBound($aLines) - 1
		If StringInStr($aLines[$i], "MuMuShared") Then
			Local $aPath = StringRegExp($aLines[$i], 'hostPath="([^"]+)"', $STR_REGEXPARRAYMATCH)
			If IsArray($aPath) Then
				$g_sAndroidPicturesHostPath = $aPath[0] & "\Pictures\"
				$g_sAndroidPicturesPath = "/data/media/0/Pictures/"
				$g_bAndroidSharedFolderAvailable = True
				$bSharedFolder = True
				SetDebugLog("MuMu shared folder: " & $g_sAndroidPicturesHostPath)
			EndIf
		EndIf
		If StringInStr($aLines[$i], "ADB_PORT_EX") Then
			Local $aDevice = StringRegExp($aLines[$i], 'hostip="([^"]+)"\s+hostport="(\d+)"', $STR_REGEXPARRAYMATCH)
			If IsArray($aDevice) And UBound($aDevice) = 2 Then $g_sAndroidAdbDevice = $aDevice[0] & ":" & $aDevice[1]
		EndIf
	Next
	Return $bSharedFolder
EndFunc   ;==>ConfigureSharedFolderMumu

Func GetMumuBackgroundMode()
	Local $sInstance = "MuMuPlayerGlobal-12.0-" & _MumuInstanceIndex()
	$__Mumu_ConfigDir = $__Mumu_Path & "vms\" & $sInstance & "\configs"
	Local $sText = FileRead($__Mumu_ConfigDir & "\shell_config.json")
	Local $sRenderer = "dx"
	If Not @error Then
		Local $aRenderer = StringRegExp($sText, '"platform"\s*:\s*"([^"]+)"', $STR_REGEXPARRAYMATCH)
		If IsArray($aRenderer) Then $sRenderer = StringLower($aRenderer[0])
	EndIf
	Switch $sRenderer
		Case "dx", "dx11", "vk", "vlcn"
			$g_iAndroidBackgroundMode = $g_iAndroidBackgroundModeDirectX
			Return $g_iAndroidBackgroundModeDirectX
		Case "gl"
			$g_iAndroidBackgroundMode = $g_iAndroidBackgroundModeOpenGL
			Return $g_iAndroidBackgroundModeOpenGL
		Case Else
			SetLog("Unsupported MuMu rendering mode: " & $sRenderer, $COLOR_WARNING)
			Return 0
	EndSwitch
EndFunc   ;==>GetMumuBackgroundMode

Func CheckScreenMumu($bSetLog = True)
	Local $sInstance = "MuMuPlayerGlobal-12.0-" & _MumuInstanceIndex()
	Local $sText = FileRead($__Mumu_Path & "vms\" & $sInstance & "\configs\shell_config.json")
	If @error Or $sText = "" Then Return False
	Local $bWidth = StringRegExp($sText, '"width"\s*:\s*"?' & $g_iGAME_WIDTH & '"?', $STR_REGEXPMATCH)
	Local $bHeight = StringRegExp($sText, '"height"\s*:\s*"?' & $g_iGAME_HEIGHT & '"?', $STR_REGEXPMATCH)
	Local $bDpi = StringRegExp($sText, '"dpi"\s*:\s*"?160"?', $STR_REGEXPMATCH)
	Local $bMatch = $bWidth And $bHeight And $bDpi
	If Not $bMatch And $bSetLog Then SetLog("MuMu Player will be configured for the required resolution and DPI", $COLOR_INFO)
	Return $bMatch
EndFunc   ;==>CheckScreenMumu

Func SetScreenMumu()
	Local $sManager = $__Mumu_Manage_Path & "MuMuManager.exe", $process_killed
	Local $iIndex = _MumuInstanceIndex()
	Local $sSettings = "setting --vmindex " & $iIndex & " --key resolution_width.custom --value " & $g_iGAME_WIDTH & _
			" --key resolution_height.custom --value " & $g_iGAME_HEIGHT & " --key resolution_dpi.custom --value 160"
	LaunchConsole($sManager, AddSpace($sSettings), $process_killed)
	LaunchConsole($sManager, AddSpace("rename --vmindex " & $iIndex & " --name MuMu-" & $iIndex), $process_killed)
EndFunc   ;==>SetScreenMumu

Func ConfigMumuWindowManager()
	AndroidAdbSendShellCommand("wm size reset", Default, Default, False)
	AndroidAdbSendShellCommand("wm density 160", Default, Default, False)
	AndroidSetFontSizeNormal()
EndFunc   ;==>ConfigMumuWindowManager

Func RebootMumuSetScreen($bOpenAndroid = True)
	If Not InitAndroid() Then Return False
	ConfigMumuWindowManager()
	CloseAndroid("RebootMumuSetScreen")
	If _Sleep(1000) Then Return False
	SetScreenAndroid()
	If $bOpenAndroid Then OpenAndroid(True)
	Return True
EndFunc   ;==>RebootMumuSetScreen

Func GetMumuRunningInstance($bStrictCheck = True)
	WinGetAndroidHandle()
	Local $aResult[2] = [$g_hAndroidWindow, $g_sAndroidInstance]
	Return $aResult
EndFunc   ;==>GetMumuRunningInstance

Func GetMumuSvcPid()
	Return ProcessExists2("MuMuVMMSVC.exe")
EndFunc   ;==>GetMumuSvcPid

Func CloseMumu()
	Local $sManager = $__Mumu_Manage_Path & "MuMuManager.exe", $process_killed
	If FileExists($sManager) Then LaunchConsole($sManager, AddSpace("control shutdown --vmindex " & _MumuInstanceIndex()), $process_killed)
	If _Sleep(1500) Then Return
	Local $iPid = ProcessExists2($g_sAndroidProgramPath, GetMumuProgramParameter())
	If $iPid Then ShellExecute(@WindowsDir & "\System32\taskkill.exe", " -f -t -pid " & $iPid, "", Default, @SW_HIDE)
EndFunc   ;==>CloseMumu

Func CloseUnsupportedMumu()
	Local $aPos = ControlGetPos($g_sAndroidTitle, "", "")
	If IsArray($aPos) Then
		SetLog("Let My Bot configure and start the selected MuMu instance", $COLOR_INFO)
		RebootMumuSetScreen(False)
		Return True
	EndIf
	Return False
EndFunc   ;==>CloseUnsupportedMumu

Func ZoomOutMumu()
	Return DefaultZoomOut("{DOWN}", 0, ($g_iAndroidZoomoutMode <> 3))
EndFunc   ;==>ZoomOutMumu

Func MumuBotStartEvent()
	Return AndroidCloseSystemBar()
EndFunc   ;==>MumuBotStartEvent

Func MumuBotStopEvent()
	Return AndroidOpenSystemBar()
EndFunc   ;==>MumuBotStopEvent
