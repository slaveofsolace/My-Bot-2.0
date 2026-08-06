; #FUNCTION# ====================================================================================================================
; Name ..........: LDPlayer 9 adapter
; Description ...: Discovers, configures, starts, stops, and addresses LDPlayer 9 instances.
; Source lineage : Adapted for the v8.2.0 engine from xbebenk/MBR_xbebenkMod with the corrected multi-instance ADB formula.
; ===============================================================================================================================
#include-once

Global $__LDPlayer9_Version = ""
Global $__LDPlayer9_Path = ""

Func _LDPlayer9InstanceIndex()
	Local $sIndex = StringReplace($g_sAndroidInstance, "leidian", "")
	If Not StringIsInt($sIndex) Then $sIndex = "0"
	Return Int($sIndex)
EndFunc   ;==>_LDPlayer9InstanceIndex

Func GetLDPlayer9ProgramParameter($bAlternative = False)
	Local $iIndex = _LDPlayer9InstanceIndex()
	If $bAlternative Then Return AddSpace("index=") & $iIndex
	Return AddSpace("index=" & $iIndex & "|")
EndFunc   ;==>GetLDPlayer9ProgramParameter

Func GetLDPlayer9AdbPath()
	Local $sEmulatorAdb = $__LDPlayer9_Path & "adb.exe"
	If FileExists($sEmulatorAdb) Then Return $sEmulatorAdb
	Local $sBundledAdb = @ScriptDir & "\lib\adb\adb.exe"
	If FileExists($sBundledAdb) Then Return $sBundledAdb
	Return ""
EndFunc   ;==>GetLDPlayer9AdbPath

Func _ResolveLDPlayer9AdbPath()
	Local $sPath = GetLDPlayer9AdbPath()
	If $g_iAndroidAdbReplace = 1 Then
		Local $sBundled = @ScriptDir & "\lib\adb\adb.exe"
		If FileExists($sBundled) Then $sPath = $sBundled
	EndIf
	Return $sPath
EndFunc   ;==>_ResolveLDPlayer9AdbPath

Func InitLDPlayer9X($bCheckOnly = False)
	$__LDPlayer9_Version = RegRead($g_sHKLM & "\SOFTWARE" & $g_sWow6432Node & "\Microsoft\Windows\CurrentVersion\Uninstall\LDPlayer9\", "DisplayVersion")
	$__LDPlayer9_Path = RegRead($g_sHKLM & "\SOFTWARE\XuanZhi\LDPlayer9\", "InstallDir")
	$__LDPlayer9_Path = StringReplace($__LDPlayer9_Path, "\\", "\")
	If $__LDPlayer9_Path <> "" And StringRight($__LDPlayer9_Path, 1) <> "\" Then $__LDPlayer9_Path &= "\"

	Local $sProgram = $__LDPlayer9_Path & "dnplayer.exe"
	Local $sConsole = $__LDPlayer9_Path & "ldconsole.exe"
	If $__LDPlayer9_Path = "" Or Not FileExists($sProgram) Or Not FileExists($sConsole) Then
		If Not $bCheckOnly Then SetLog("LDPlayer 9 installation is incomplete or could not be located", $COLOR_ERROR)
		Return SetError(1, 0, False)
	EndIf

	Local $sAdbPath = _ResolveLDPlayer9AdbPath()
	If $sAdbPath = "" Then
		If Not $bCheckOnly Then SetLog("No compatible ADB executable was found for LDPlayer 9", $COLOR_ERROR)
		Return SetError(2, 0, False)
	EndIf

	If Not $bCheckOnly Then
		$g_sAndroidPath = $__LDPlayer9_Path
		$g_sAndroidProgramPath = $sProgram
		$g_sAndroidAdbPath = $sAdbPath
		$g_sAndroidVersion = $__LDPlayer9_Version
		ConfigureSharedFolderLDPlayer9()
		WinGetAndroidHandle()
	EndIf
	Return True
EndFunc   ;==>InitLDPlayer9X

Func InitLDPlayer9($bCheckOnly = False)
	Local $bInstalled = InitLDPlayer9X($bCheckOnly)
	If Not $bInstalled Then Return False
	If $__LDPlayer9_Version <> "" And GetVersionNormalized($__LDPlayer9_Version) < GetVersionNormalized("9.0") Then
		If Not $bCheckOnly Then SetLog("LDPlayer 9 or newer is required", $COLOR_ERROR)
		Return SetError(3, 0, False)
	EndIf

	Local $iPort = 5554 + (2 * _LDPlayer9InstanceIndex())
	$g_sAndroidAdbDevice = "emulator-" & $iPort
	If Not $bCheckOnly Then
		$g_sAndroidAdbShellOptions = " /system/xbin/su root"
		$g_iAndroidAdbMinitouchMode = 1
		GetLDPlayer9BackgroundMode()
	EndIf
	Return True
EndFunc   ;==>InitLDPlayer9

Func OpenLDPlayer9($bRestart = False)
	SetLog("Starting LDPlayer 9", $COLOR_SUCCESS)
	If Not InitAndroid() Then Return False
	Local $sConsole = $__LDPlayer9_Path & "ldconsole.exe"
	Local $sParameters = "launch --index " & _LDPlayer9InstanceIndex()
	Local $process_killed
	LaunchConsole($g_sAndroidAdbPath, AddSpace($g_sAndroidAdbGlobalOptions) & "start-server", $process_killed)
	If WinGetAndroidHandle() = 0 Then
		LaunchConsole($sConsole, AddSpace($sParameters), $process_killed)
		If _SleepStatus(5000) Then Return False
	Else
		SetLog("LDPlayer 9 is already running")
		Return True
	EndIf

	Local $hTimer = __TimerInit()
	While $g_hAndroidControl = 0
		_StatusUpdateTime($hTimer, $g_sAndroidEmulator & " Starting")
		If __TimerDiff($hTimer) > $g_iAndroidLaunchWaitSec * 1000 Then
			SetLog("LDPlayer 9 did not become ready within the configured launch timeout", $COLOR_ERROR)
			Return SetError(1, 0, False)
		EndIf
		If _Sleep(500) Then Return False
		WinGetAndroidHandle()
	WEnd

	ConnectAndroidAdb(False, 3000)
	If WaitForAndroidBootCompleted($g_iAndroidLaunchWaitSec - __TimerDiff($hTimer) / 1000, $hTimer) Then Return False
	SetLog("LDPlayer 9 loaded in " & Round(__TimerDiff($hTimer) / 1000, 2) & " seconds", $COLOR_SUCCESS)
	Return True
EndFunc   ;==>OpenLDPlayer9

Func ConfigureSharedFolderLDPlayer9($iMode = 0, $bSetLog = Default)
	Local $sConfig = $__LDPlayer9_Path & "vms\config\" & $g_sAndroidInstance & ".config"
	Local $aLines = FileReadToArray($sConfig)
	If @error Then Return SetError(1, 0, False)
	For $i = 0 To UBound($aLines) - 1
		If StringInStr($aLines[$i], '"statusSettings.sharedPictures"') Then
			Local $aPath = StringRegExp($aLines[$i], ':\s*"([^"]+)"', $STR_REGEXPARRAYMATCH)
			If IsArray($aPath) Then
				Local $sPath = StringReplace($aPath[0], "/", "\")
				If StringRight($sPath, 1) <> "\" Then $sPath &= "\"
				$g_sAndroidPicturesHostPath = $sPath
				$g_sAndroidPicturesPath = "/mnt/shared/Pictures/"
				$g_bAndroidSharedFolderAvailable = True
				SetDebugLog("LDPlayer 9 shared folder: " & $sPath)
				Return True
			EndIf
		EndIf
	Next
	Return SetError(2, 0, False)
EndFunc   ;==>ConfigureSharedFolderLDPlayer9

Func GetLDPlayer9BackgroundMode()
	$g_iAndroidBackgroundMode = $g_iAndroidBackgroundModeDirectX
	Return $g_iAndroidBackgroundModeDirectX
EndFunc   ;==>GetLDPlayer9BackgroundMode

Func CheckScreenLDPlayer9($bSetLog = True)
	Local $sConfig = $__LDPlayer9_Path & "vms\config\" & $g_sAndroidInstance & ".config"
	Local $sText = FileRead($sConfig)
	If @error Or $sText = "" Then Return False
	Local $bMatch = StringInStr($sText, '"width": ' & $g_iGAME_WIDTH) And _
			StringInStr($sText, '"height": ' & $g_iGAME_HEIGHT) And _
			StringInStr($sText, '"advancedSettings.resolutionDpi": 160')
	If Not $bMatch And $bSetLog Then SetLog("LDPlayer 9 will be configured for the required resolution and DPI", $COLOR_INFO)
	Return ($bMatch <> 0)
EndFunc   ;==>CheckScreenLDPlayer9

Func SetScreenLDPlayer9()
	Local $sConsole = $__LDPlayer9_Path & "ldconsole.exe", $process_killed
	Local $iIndex = _LDPlayer9InstanceIndex()
	LaunchConsole($sConsole, AddSpace("modify --index " & $iIndex & " --resolution " & $g_iGAME_WIDTH & "," & $g_iGAME_HEIGHT & ",160 --root 1"), $process_killed)
	LaunchConsole($sConsole, AddSpace("rename --index " & $iIndex & " --title LD9-" & $iIndex), $process_killed)
EndFunc   ;==>SetScreenLDPlayer9

Func ConfigLDPlayer9WindowManager()
	AndroidAdbSendShellCommand("wm size reset", Default, Default, False)
	AndroidAdbSendShellCommand("wm density 160", Default, Default, False)
	AndroidSetFontSizeNormal()
EndFunc   ;==>ConfigLDPlayer9WindowManager

Func RebootLDPlayer9SetScreen($bOpenAndroid = True)
	If Not InitAndroid() Then Return False
	ConfigLDPlayer9WindowManager()
	CloseAndroid("RebootLDPlayer9SetScreen")
	If _Sleep(1000) Then Return False
	SetScreenAndroid()
	If $bOpenAndroid Then OpenAndroid(True)
	Return True
EndFunc   ;==>RebootLDPlayer9SetScreen

Func GetLDPlayer9RunningInstance($bStrictCheck = True)
	WinGetAndroidHandle()
	Local $aResult[2] = [$g_hAndroidWindow, $g_sAndroidInstance]
	Return $aResult
EndFunc   ;==>GetLDPlayer9RunningInstance

Func GetLDPlayer9SvcPid()
	Return ProcessExists2("Ld9BoxSvc.exe")
EndFunc   ;==>GetLDPlayer9SvcPid

Func CloseLDPlayer9()
	Local $sConsole = $__LDPlayer9_Path & "ldconsole.exe", $process_killed
	If FileExists($sConsole) Then LaunchConsole($sConsole, AddSpace("quit --index " & _LDPlayer9InstanceIndex()), $process_killed)
	If _Sleep(1500) Then Return
	Local $iPid = ProcessExists2($g_sAndroidProgramPath, GetLDPlayer9ProgramParameter())
	If $iPid Then ShellExecute(@WindowsDir & "\System32\taskkill.exe", " -f -t -pid " & $iPid, "", Default, @SW_HIDE)
EndFunc   ;==>CloseLDPlayer9

Func CloseUnsupportedLDPlayer9()
	Local $aPos = ControlGetPos($g_sAndroidTitle, "", "")
	If IsArray($aPos) Then
		SetLog("Let My Bot configure and start the selected LDPlayer 9 instance", $COLOR_INFO)
		RebootLDPlayer9SetScreen(False)
		Return True
	EndIf
	Return False
EndFunc   ;==>CloseUnsupportedLDPlayer9

Func ZoomOutLDPlayer9()
	Return DefaultZoomOut("{F3}", 0, ($g_iAndroidZoomoutMode <> 3))
EndFunc   ;==>ZoomOutLDPlayer9

Func LDPlayer9BotStartEvent()
	Return AndroidCloseSystemBar()
EndFunc   ;==>LDPlayer9BotStartEvent

Func LDPlayer9BotStopEvent()
	Return AndroidOpenSystemBar()
EndFunc   ;==>LDPlayer9BotStopEvent
