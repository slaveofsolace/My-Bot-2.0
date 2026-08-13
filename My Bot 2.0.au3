#NoTrayIcon
#RequireAdmin
#AutoIt3Wrapper_UseX64=n
#pragma compile(Icon, "Images\MyBot.ico")
#pragma compile(ProductName, My Bot 2.0)
#pragma compile(FileDescription, My Bot 2.0)
#pragma compile(ProductVersion, 2.0.0)
#pragma compile(FileVersion, 2.0.0)
#pragma compile(Out, My Bot 2.0.exe)

#include <Crypt.au3>
#include <GUIConstantsEx.au3>
#include <Misc.au3>
#include <MsgBoxConstants.au3>
#include <StringConstants.au3>
#include <WinAPIGdi.au3>
#include <WindowsConstants.au3>

Opt("MustDeclareVars", 1)
Opt("GUIOnEventMode", 1)

Global Const $g_sLauncherTitle = "My Bot 2.0"
Global Const $g_sControlCenterUrl = "http://127.0.0.1:8765/"
Global Const $g_sControllerPath = @ScriptDir & "\MyBot.run.MiniGui.exe"
Global Const $g_sControllerSha256 = "ae26c098ceb3c74e3d7f567834d9135257e094172e32140f4a5b615eaf90ceda"
Global Const $g_iControllerBytes = 1634304
Global Const $g_sHostPath = @ScriptDir & "\MyBot.run.exe"
Global Const $g_sHostConfigPath = $g_sHostPath & ".config"
Global Const $g_sEngineProbeConfigPath = @ScriptDir & "\MyBot.run.EngineProbe.exe.config"
Global Const $g_sEngineMarkerPath = @ScriptDir & "\MyBot.run.txt"
Global Const $g_sEnginePath = @ScriptDir & "\lib\MyBot.run.dll"
Global Const $g_sUserDataRoot = @LocalAppDataDir & "\My Bot 2.0"
Global Const $g_sProfilesRoot = $g_sUserDataRoot & "\Profiles"
Global Const $g_sProfilesIniPath = $g_sProfilesRoot & "\profile.ini"
Global Const $g_sFirstRunProfile = "MyVillage"
Global Const $g_sControllerTitlePattern = "^My Bot Mini v8\.2\.0(?: \(.+\))?$"
Global Const $g_iDockGap = 8
Global Const $g_iDockWaitMs = 600000
Global Const $g_iDockTransitionPollMs = 1000
Global Const $g_iDockStablePollMs = 5000
Global Const $g_iErrorAlreadyExists = 183
Global Const $g_sRecoveryLogPath = @ScriptDir & "\artifacts\launcher-recovery.log"
Global Const $g_sPlannerServiceName = "my-bot-control-center"
Global Const $g_sPlannerScriptPath = @ScriptDir & "\tools\planner_ui.py"
Global Const $g_iLauncherErrorTimeoutSec = 15
Global Const $g_iControlStripHeight = 34
Global Const $g_iControlStripGap = 4
Global $g_hControlStrip = 0
Global $g_idOpenControlCenter = 0
Global $g_idMinimizePair = 0
Global Const $g_iPairVisible = 0
Global Const $g_iPairMinimizing = 1
Global Const $g_iPairMinimized = 2
Global Const $g_iPairRestoring = 3
Global $g_iPairVisibilityState = $g_iPairVisible

_CloseOwnedAutoItErrorDialogs()
If _CommandLineHas("/recover") Or _CommandLineHas("/repair") Then
	If _RecoverBotStack() Then Exit 0
	Exit 6
EndIf
If Not _ValidateInstallation() Then Exit 1
If _CommandLineHas("/background") Then Exit _SetDockPairMinimized() ? 0 : 7
If _CommandLineHas("/foreground") Then Exit _SetDockPairRestored() ? 0 : 8

; One invisible launcher process owns docking for this installation. Re-running the launcher can
; perform one verified snap and open the requested Control Center, but cannot create another keeper.
Local $hDockKeeperMutex = _AcquireDockKeeper()
Local $iDockKeeperError = @error
If $iDockKeeperError <> 0 And $iDockKeeperError <> $g_iErrorAlreadyExists Then
	_ShowError("My Bot 2.0 could not reserve its window dock keeper.")
	Exit 5
EndIf
Local $bOwnDockKeeper = $hDockKeeperMutex <> 0

Local $hController = _FindControllerWindow()
If @error = 2 Then
	_ShowError("More than one My Bot Mini controller is running from this installation." & @CRLF & @CRLF & _
		"Close the extra controller before launching My Bot 2.0 again.")
	Exit 2
EndIf

If $hController Then
	Local $iExistingControllerPid = WinGetProcess($hController)
	_ShowControlStrip($hController)
	_DockWhenReady($hController, $iExistingControllerPid, 15000)
	_OpenControlCenter()
	If Not $bOwnDockKeeper Then Exit 0
	_KeepDocked($hController, $iExistingControllerPid)
	Exit 0
EndIf

; A keeper that won the startup race owns controller launch. This duplicate launcher waits only
; long enough to perform a verified first snap and open the requested Control Center, then exits.
If Not $bOwnDockKeeper Then
	$hController = _WaitForControllerFromInstallation(60000)
	If @error = 2 Then
		_ShowError("More than one My Bot Mini controller is running from this installation." & @CRLF & @CRLF & _
			"Close the extra controller before launching My Bot 2.0 again.")
		Exit 2
	EndIf
	If $hController Then
		_DockWhenReady($hController, WinGetProcess($hController), 15000)
		_OpenControlCenter()
	EndIf
	Exit 0
EndIf

; The inherited image engine supports this exact upstream controller as its genuine remote GUI.
; The controller remains visible and functional; it launches the modern backend with /ng and /guipid.
Local $sLaunchProfile = _PrepareUserProfile()
If @error Or $sLaunchProfile = "" Then
	_ShowError("My Bot 2.0 could not prepare its per-user profile." & @CRLF & @CRLF & _
		"Check this folder and its profile.ini, then try again:" & @CRLF & $g_sProfilesRoot)
	Exit 9
EndIf
Local $iControllerPid = ShellExecute($g_sControllerPath, _BuildControllerArguments($sLaunchProfile), @ScriptDir, "", @SW_SHOWNORMAL)
If @error Or $iControllerPid <= 0 Then
	_ShowError("My Bot 2.0 could not start its native controller." & @CRLF & @CRLF & _
		"Approve the Windows administrator prompt and try again.")
	Exit 3
EndIf

$hController = _WaitForControllerWindow($iControllerPid, 60000)
If Not $hController Then
	_ShowError("The native controller did not become ready." & @CRLF & @CRLF & _
		"My Bot 2.0 left the controller process running so its log can be inspected.")
	Exit 4
EndIf

; The invisible launcher remains a lightweight dock keeper. It follows later BlueStacks shell
; resizes and exits with the exact Mini controller, without reparenting or commanding either app.
_ShowControlStrip($hController)
_DockWhenReady($hController, $iControllerPid, $g_iDockWaitMs)
_KeepDocked($hController, $iControllerPid)
Exit 0

Func _DockKeeperMutexName()
	; Scope ownership to this checkout while keeping reserved path separators out of the object name.
	Return "Local\MyBot2DockKeeper_" & StringRegExpReplace(StringLower(@ScriptDir), "[^a-z0-9]", "_")
EndFunc   ;==>_DockKeeperMutexName

Func _AcquireDockKeeper()
	Local $hMutex = _Singleton(_DockKeeperMutexName(), 1)
	If @error Then Return SetError(@error, @extended, 0)
	Return $hMutex
EndFunc   ;==>_AcquireDockKeeper

Func _CommandLineHas($sSwitch)
	For $i = 1 To $CmdLine[0]
		If StringLower($CmdLine[$i]) = StringLower($sSwitch) Then Return True
	Next
	Return False
EndFunc   ;==>_CommandLineHas

Func _PrepareUserProfile()
	If Not FileExists($g_sProfilesRoot) Then
		If Not DirCreate($g_sProfilesRoot) Then Return SetError(1, 0, "")
	EndIf
	If StringInStr(FileGetAttrib($g_sProfilesRoot), "D") = 0 Then Return SetError(2, 0, "")

	If Not FileExists($g_sProfilesIniPath) Then
		Local $sFirstRunPath = $g_sProfilesRoot & "\" & $g_sFirstRunProfile
		If Not FileExists($sFirstRunPath) And Not DirCreate($sFirstRunPath) Then Return SetError(3, 0, "")
		If Not IniWrite($g_sProfilesIniPath, "general", "defaultprofile", $g_sFirstRunProfile) Then Return SetError(4, 0, "")
	EndIf

	Local $sProfile = StringStripWS(IniRead($g_sProfilesIniPath, "general", "defaultprofile", ""), $STR_STRIPLEADING + $STR_STRIPTRAILING)
	If Not _IsSafeProfileName($sProfile) Then Return SetError(5, 0, "")
	Local $sProfilePath = $g_sProfilesRoot & "\" & $sProfile
	If Not FileExists($sProfilePath) Or StringInStr(FileGetAttrib($sProfilePath), "D") = 0 Then Return SetError(6, 0, "")
	Return $sProfile
EndFunc   ;==>_PrepareUserProfile

Func _IsSafeProfileName($sProfile)
	; The pinned Mini controller forwards positional arguments as a reconstructed command line.
	; Keep the profile name simple so it cannot split, inject another option, or select a parent path.
	Return StringRegExp($sProfile, "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$") = 1
EndFunc   ;==>_IsSafeProfileName

Func _BuildControllerArguments($sProfile)
	; The first parse must leave literal quotes around the path in Mini's $CmdLine value. Mini then
	; rebuilds the backend command without its own quoting, and the second parse consumes these quotes.
	; This keeps a path such as "My Bot 2.0\Profiles" intact through both exact pinned executables.
	Return '"' & $sProfile & '" ' & '"/profiles=\"' & $g_sProfilesRoot & '\"" /nowatchdog'
EndFunc   ;==>_BuildControllerArguments

Func _RecoverBotStack()
	_RecoveryLog("recovery requested")
	_CloseOwnedAutoItErrorDialogs()
	_CloseExactPathProcesses("MyBot.run.MiniGui.exe", $g_sControllerPath)
	_CloseExactPathProcesses("MyBot.run.exe", $g_sHostPath)
	Local $bPlannerClosed = _CloseOwnedPlannerService()
	_CloseExactPathProcesses("My Bot 2.0.exe", @ScriptFullPath, @AutoItPID)

	Local $hController = _FindControllerWindow()
	Local $bControllerClosed = Not $hController
	Local $bBackendClosed = _CountExactPathProcesses("MyBot.run.exe", $g_sHostPath) = 0
	Local $bRecovered = $bControllerClosed And $bBackendClosed And $bPlannerClosed
	_RecoveryLog("recovery completed; controller_closed=" & $bControllerClosed & "; backend_closed=" & $bBackendClosed & "; planner_closed=" & $bPlannerClosed)
	Return $bRecovered
EndFunc   ;==>_RecoverBotStack

; The planner service can outlive a backend that was force-closed. Recovery runs elevated, but it
; still proves the loopback service name, exact checkout root, current script hash, reported PID,
; and pythonw image before closing anything. A foreign listener is logged and left untouched.
Func _CloseOwnedPlannerService()
	Local $vHealth = InetRead($g_sControlCenterUrl & "api/health", 1)
	If @error Or Not IsBinary($vHealth) Or BinaryLen($vHealth) = 0 Then Return True
	Local $sHealth = BinaryToString($vHealth, 4)
	If StringInStr($sHealth, """service"": """ & $g_sPlannerServiceName & """") = 0 Then
		_RecoveryLog("refused planner service: unexpected service identity")
		Return False
	EndIf
	Local $sJsonRoot = StringReplace(@ScriptDir, "\", "\\")
	If StringInStr($sHealth, """repo_root"": """ & $sJsonRoot & """") = 0 Then
		_RecoveryLog("refused planner service: repository root mismatch")
		Return False
	EndIf
	Local $sScriptHash = _FileSha256($g_sPlannerScriptPath)
	If $sScriptHash = "" Or StringInStr(StringLower($sHealth), """build_sha256"": """ & $sScriptHash & """") = 0 Then
		_RecoveryLog("refused planner service: script build mismatch")
		Return False
	EndIf
	Local $aPid = StringRegExp($sHealth, """service_pid""\s*:\s*([0-9]+)", $STR_REGEXPARRAYMATCH)
	If @error Or Not IsArray($aPid) Or UBound($aPid) <> 1 Then
		_RecoveryLog("refused planner service: missing service pid")
		Return False
	EndIf
	Local $iPid = Int($aPid[0])
	If $iPid <= 0 Or Not ProcessExists($iPid) Then Return True
	If Not StringRegExp(StringLower(_ProcessImagePath($iPid)), "\\pythonw\.exe$") Then
		_RecoveryLog("refused planner service: pid " & $iPid & " is not pythonw.exe")
		Return False
	EndIf
	_RecoveryLog("closing verified planner service; pid=" & $iPid)
	If Not ProcessClose($iPid) Then Return False
	For $i = 1 To 40
		If Not ProcessExists($iPid) Then Return True
		Sleep(50)
	Next
	Return Not ProcessExists($iPid)
EndFunc   ;==>_CloseOwnedPlannerService

Func _CloseOwnedAutoItErrorDialogs()
	Local $aDialogs = WinList("AutoIt Error")
	Local $sRootPrefix = StringLower(@ScriptDir & "\")
	For $i = 1 To $aDialogs[0][0]
		Local $hDialog = $aDialogs[$i][1]
		Local $iPid = WinGetProcess($hDialog)
		If $iPid <= 0 Then ContinueLoop
		Local $sPath = StringLower(_ProcessImagePath($iPid))
		If StringLeft($sPath, StringLen($sRootPrefix)) <> $sRootPrefix Then ContinueLoop

		Local $sErrorText = StringStripWS(StringReplace(WinGetText($hDialog), @CRLF, " | "), $STR_STRIPTRAILING)
		_RecoveryLog("closing owned AutoIt error; pid=" & $iPid & "; image=" & $sPath & "; text=" & $sErrorText)
		WinClose($hDialog)
		WinWaitClose($hDialog, "", 2)
	Next
EndFunc   ;==>_CloseOwnedAutoItErrorDialogs

Func _CloseExactPathProcesses($sProcessName, $sExpectedPath, $iExcludePid = 0)
	Local $aProcesses = ProcessList($sProcessName)
	For $i = 1 To $aProcesses[0][0]
		Local $iPid = $aProcesses[$i][1]
		If $iPid = $iExcludePid Then ContinueLoop
		If StringLower(_ProcessImagePath($iPid)) <> StringLower($sExpectedPath) Then
			_RecoveryLog("refused non-matching process; name=" & $sProcessName & "; pid=" & $iPid)
			ContinueLoop
		EndIf

		_CloseWindowsForPid($iPid)
		If ProcessWaitClose($iPid, 5) Then
			_RecoveryLog("closed gracefully; name=" & $sProcessName & "; pid=" & $iPid)
			ContinueLoop
		EndIf
		ProcessClose($iPid)
		ProcessWaitClose($iPid, 5)
		_RecoveryLog("force-closed exact process; name=" & $sProcessName & "; pid=" & $iPid)
	Next
EndFunc   ;==>_CloseExactPathProcesses

Func _CloseWindowsForPid($iPid)
	Local $aWindows = WinList()
	For $i = 1 To $aWindows[0][0]
		If WinGetProcess($aWindows[$i][1]) = $iPid Then WinClose($aWindows[$i][1])
	Next
EndFunc   ;==>_CloseWindowsForPid

Func _CountExactPathProcesses($sProcessName, $sExpectedPath)
	Local $aProcesses = ProcessList($sProcessName)
	Local $iCount = 0
	For $i = 1 To $aProcesses[0][0]
		If StringLower(_ProcessImagePath($aProcesses[$i][1])) = StringLower($sExpectedPath) Then $iCount += 1
	Next
	Return $iCount
EndFunc   ;==>_CountExactPathProcesses

Func _RecoveryLog($sMessage)
	FileWriteLine($g_sRecoveryLogPath, @YEAR & "-" & @MON & "-" & @MDAY & "T" & @HOUR & ":" & @MIN & ":" & @SEC & " " & $sMessage)
EndFunc   ;==>_RecoveryLog

Func _ValidateInstallation()
	If Not FileExists($g_sControllerPath) Then Return _InstallError("MyBot.run.MiniGui.exe is missing.", $g_sControllerPath)
	If FileGetSize($g_sControllerPath) <> $g_iControllerBytes Or _FileSha256($g_sControllerPath) <> $g_sControllerSha256 Then
		Return _InstallError("The native controller is not the supported MyBot.run v8.2.0 build.", $g_sControllerPath)
	EndIf
	If Not FileExists($g_sHostPath) Then Return _InstallError("MyBot.run.exe is missing.", $g_sHostPath)
	If Not FileExists($g_sHostConfigPath) Then Return _InstallError("MyBot.run.exe.config is missing.", $g_sHostConfigPath)
	If Not FileExists($g_sEngineProbeConfigPath) Then Return _InstallError("MyBot.run.EngineProbe.exe.config is missing.", $g_sEngineProbeConfigPath)
	If Not FileExists($g_sEnginePath) Then Return _InstallError("lib\MyBot.run.dll is missing.", $g_sEnginePath)
	If Not FileExists($g_sEngineMarkerPath) Or FileGetSize($g_sEngineMarkerPath) <> 0 Then
		Return _InstallError("The empty MyBot.run.txt engine marker is missing or invalid.", $g_sEngineMarkerPath)
	EndIf
	Return True
EndFunc   ;==>_ValidateInstallation

Func _InstallError($sMessage, $sPath)
	_ShowError($sMessage & @CRLF & @CRLF & "Reinstall or restore it beside this launcher:" & @CRLF & $sPath)
	Return False
EndFunc   ;==>_InstallError

Func _FileSha256($sPath)
	Local $vHash = _Crypt_HashFile($sPath, $CALG_SHA_256)
	If @error Or Not IsBinary($vHash) Then Return ""
	Return StringLower(StringTrimLeft(String($vHash), 2))
EndFunc   ;==>_FileSha256

Func _FindControllerWindow($iExpectedPid = 0)
	Local $aWindows = WinList("[CLASS:AutoIt v3 GUI]")
	Local $hFound = 0
	For $i = 1 To $aWindows[0][0]
		Local $hWindow = $aWindows[$i][1]
		If Not _ControllerWindowMatches($hWindow, $iExpectedPid) Then ContinueLoop
		If $hFound Then Return SetError(2, 0, 0)
		$hFound = $hWindow
	Next
	Return $hFound
EndFunc   ;==>_FindControllerWindow

Func _ControllerWindowMatches($hWindow, $iExpectedPid = 0)
	If Not WinExists($hWindow) Then Return False
	If Not StringRegExp(WinGetTitle($hWindow), $g_sControllerTitlePattern) Then Return False
	Local $iPid = WinGetProcess($hWindow)
	If $iPid <= 0 Or ($iExpectedPid > 0 And $iPid <> $iExpectedPid) Then Return False
	Return StringLower(_ProcessImagePath($iPid)) = StringLower($g_sControllerPath)
EndFunc   ;==>_ControllerWindowMatches

Func _WaitForControllerWindow($iControllerPid, $iTimeoutMs)
	Local $hController = 0
	Local $hTimer = TimerInit()
	Do
		If Not ProcessExists($iControllerPid) Then ExitLoop
		$hController = _FindControllerWindow($iControllerPid)
		If $hController Then Return $hController
		Sleep(200)
	Until TimerDiff($hTimer) >= $iTimeoutMs
	Return 0
EndFunc   ;==>_WaitForControllerWindow

Func _WaitForControllerFromInstallation($iTimeoutMs)
	Local $hController = 0
	Local $hTimer = TimerInit()
	Do
		$hController = _FindControllerWindow()
		If @error = 2 Then Return SetError(2, 0, 0)
		If $hController Then Return $hController
		Sleep(200)
	Until TimerDiff($hTimer) >= $iTimeoutMs
	Return 0
EndFunc   ;==>_WaitForControllerFromInstallation

Func _ProcessImagePath($iPid)
	Local $aOpen = DllCall("kernel32.dll", "handle", "OpenProcess", "dword", 0x1000, "bool", False, "dword", $iPid)
	If @error Or Not IsArray($aOpen) Or Not $aOpen[0] Then Return ""
	Local $hProcess = $aOpen[0]
	Local $tPath = DllStructCreate("wchar[32768]")
	Local $aQuery = DllCall("kernel32.dll", "bool", "QueryFullProcessImageNameW", "handle", $hProcess, "dword", 0, _
		"struct*", $tPath, "dword*", 32768)
	DllCall("kernel32.dll", "bool", "CloseHandle", "handle", $hProcess)
	If @error Or Not IsArray($aQuery) Or Not $aQuery[0] Then Return ""
	Return DllStructGetData($tPath, 1)
EndFunc   ;==>_ProcessImagePath

Func _ControllerBlueStacksTitle($hController)
	If Not WinExists($hController) Then Return ""
	Local $aMatch = StringRegExp(WinGetTitle($hController), _
		"^My Bot Mini v8\.2\.0 \(([A-Za-z0-9_. -]{1,64})\)$", $STR_REGEXPARRAYMATCH)
	If @error Or Not IsArray($aMatch) Or UBound($aMatch) <> 1 Then Return ""
	Return "BlueStacks5-" & $aMatch[0]
EndFunc   ;==>_ControllerBlueStacksTitle

Func _FindBlueStacksWindow($hController)
	; The backend writes its exact bound instance into the genuine Mini controller caption.
	; Dock only the BlueStacks window for that same instance; never guess a default account.
	Local $sBlueStacksTitle = _ControllerBlueStacksTitle($hController)
	If $sBlueStacksTitle = "" Then Return 0
	Local $aWindows = WinList($sBlueStacksTitle)
	Local $hFound = 0
	For $i = 1 To $aWindows[0][0]
		If $aWindows[$i][0] <> $sBlueStacksTitle Then ContinueLoop
		Local $hWindow = $aWindows[$i][1]
		Local $sClass = _WindowClassName($hWindow)
		If Not StringRegExp($sClass, "^Qt[0-9]+QWindowIcon$") Then ContinueLoop
		Local $iPid = WinGetProcess($hWindow)
		If Not StringRegExp(StringLower(_ProcessImagePath($iPid)), "\\hd-player\.exe$") Then ContinueLoop
		If $hFound Then Return SetError(2, 0, 0)
		$hFound = $hWindow
	Next
	Return $hFound
EndFunc   ;==>_FindBlueStacksWindow

Func _WindowClassName($hWindow)
	Local $tClass = DllStructCreate("wchar[256]")
	Local $aClass = DllCall("user32.dll", "int", "GetClassNameW", "hwnd", $hWindow, "struct*", $tClass, "int", 256)
	If @error Or Not IsArray($aClass) Or $aClass[0] <= 0 Then Return ""
	Return DllStructGetData($tClass, 1)
EndFunc   ;==>_WindowClassName

Func _DockWhenReady($hController, $iControllerPid, $iTimeoutMs)
	Local $hTimer = TimerInit()
	Do
		If Not ProcessExists($iControllerPid) Or Not WinExists($hController) Then Return False
		Local $hBlueStacks = _FindBlueStacksWindow($hController)
		If @error = 2 Then Return False
		If $hBlueStacks Then Return _DockController($hController, $hBlueStacks)
		Sleep(500)
	Until TimerDiff($hTimer) >= $iTimeoutMs
	Return False
EndFunc   ;==>_DockWhenReady

Func _KeepDocked($hController, $iControllerPid)
	Local $sPreviousDockState = ""
	While ProcessExists($iControllerPid)
		; Re-prove the controller's exact PID, path, and title before every possible move. If its
		; window is briefly recreated, reacquire only another exact window from the same process.
		If Not _ControllerWindowMatches($hController, $iControllerPid) Then
			$hController = _FindControllerWindow($iControllerPid)
			If @error = 2 Then Return False
			If Not $hController Then
				Sleep(_AdaptiveDockPollDelay("controller-unbound", $sPreviousDockState))
				ContinueLoop
			EndIf
		EndIf
		Local $hBlueStacks = _FindBlueStacksWindow($hController)
		Local $iBlueStacksFindError = @error
		Local $sDockState = "unbound:" & String($hController)
		Local $bNeedsFastPoll = $iBlueStacksFindError = 2
		If $iBlueStacksFindError <> 2 And $hBlueStacks Then
			Local $bVisibilityHandled = _SynchronizeDockPairVisibility($hController, $hBlueStacks)
			$sDockState = "bound:" & String($hController) & ":" & String($hBlueStacks) & ":" & String($g_iPairVisibilityState)
			If Not $bVisibilityHandled Then
				If _WindowCanDock($hController) And _WindowCanDock($hBlueStacks) Then
					Local $bDocked = _DockController($hController, $hBlueStacks, False)
					Local $iDockAction = @extended
					$bNeedsFastPoll = Not $bDocked Or $iDockAction > 0
				Else
					$bNeedsFastPoll = True
				EndIf
			EndIf
		ElseIf _WindowCanDock($hController) Then
			_DockControlStrip($hController)
			$bNeedsFastPoll = $bNeedsFastPoll Or @extended > 0
		EndIf
		Sleep(_AdaptiveDockPollDelay($sDockState, $sPreviousDockState, $bNeedsFastPoll))
	WEnd
	Return True
EndFunc   ;==>_KeepDocked

; A stable bound pair and a stable unbound controller need only a low-frequency identity check.
; Any state transition, ambiguous binding, or corrected geometry gets a fast confirmation poll.
Func _AdaptiveDockPollDelay($sState, ByRef $sPreviousState, $bNeedsFastPoll = False)
	Local $bStateChanged = $sState <> $sPreviousState
	$sPreviousState = $sState
	If $bNeedsFastPoll Or $bStateChanged Then Return $g_iDockTransitionPollMs
	Return $g_iDockStablePollMs
EndFunc   ;==>_AdaptiveDockPollDelay

; Treat the exact controller and the exact instance-bound BlueStacks window as one visible pair.
; A four-state handshake avoids the asynchronous restore race where one window becomes visible a
; poll before the other and would otherwise be minimized again. No HWND parent/style is changed, so
; ADB Background Mode remains the capture/input authority while both top-level windows are off-screen.
Func _SynchronizeDockPairVisibility($hController, $hBlueStacks)
	If Not WinExists($hController) Or Not WinExists($hBlueStacks) Then Return False
	Local $bControllerMinimized = _WindowIsMinimized($hController)
	Local $bBlueStacksMinimized = _WindowIsMinimized($hBlueStacks)

	Switch $g_iPairVisibilityState
		Case $g_iPairVisible
			If $bControllerMinimized Or $bBlueStacksMinimized Then
				If Not $bControllerMinimized Then WinSetState($hController, "", @SW_MINIMIZE)
				If Not $bBlueStacksMinimized Then WinSetState($hBlueStacks, "", @SW_MINIMIZE)
				If $g_hControlStrip <> 0 Then WinSetState($g_hControlStrip, "", @SW_HIDE)
				; This poll owns the paired action. Commit the stable state now so an immediate user
				; restore cannot be mistaken for an unfinished asynchronous minimize on the next poll.
				$g_iPairVisibilityState = $g_iPairMinimized
				Return True
			EndIf
		Case $g_iPairMinimizing
			If Not $bControllerMinimized Then WinSetState($hController, "", @SW_MINIMIZE)
			If Not $bBlueStacksMinimized Then WinSetState($hBlueStacks, "", @SW_MINIMIZE)
			If _WindowIsMinimized($hController) And _WindowIsMinimized($hBlueStacks) Then $g_iPairVisibilityState = $g_iPairMinimized
			Return True
		Case $g_iPairMinimized
			If Not $bControllerMinimized Or Not $bBlueStacksMinimized Then
				WinSetState($hController, "", @SW_RESTORE)
				WinSetState($hBlueStacks, "", @SW_RESTORE)
				$g_iPairVisibilityState = $g_iPairVisible
				If $g_hControlStrip <> 0 Then WinSetState($g_hControlStrip, "", @SW_SHOW)
				_DockController($hController, $hBlueStacks, False)
				Return False
			EndIf
			Return True
		Case $g_iPairRestoring
			If $bControllerMinimized Then WinSetState($hController, "", @SW_RESTORE)
			If $bBlueStacksMinimized Then WinSetState($hBlueStacks, "", @SW_RESTORE)
			If Not $bControllerMinimized And Not $bBlueStacksMinimized Then
				$g_iPairVisibilityState = $g_iPairVisible
				If $g_hControlStrip <> 0 Then WinSetState($g_hControlStrip, "", @SW_SHOW)
				_DockController($hController, $hBlueStacks, False)
				Return False
			EndIf
			Return True
	EndSwitch
	$g_iPairVisibilityState = $g_iPairVisible
	Return False
EndFunc   ;==>_SynchronizeDockPairVisibility

Func _WindowIsMinimized($hWindow)
	If Not WinExists($hWindow) Then Return False
	Local $iState = WinGetState($hWindow)
	If @error Then Return False
	Return BitAND($iState, 16) <> 0
EndFunc   ;==>_WindowIsMinimized

Func _WindowCanDock($hWindow)
	If Not WinExists($hWindow) Then Return False
	Local $iState = WinGetState($hWindow)
	If @error Then Return False
	Return BitAND($iState, 2) <> 0 And BitAND($iState, 16) = 0
EndFunc   ;==>_WindowCanDock

Func _VirtualDesktopHorizontalBounds()
	Local $aX = DllCall("user32.dll", "int", "GetSystemMetrics", "int", $SM_XVIRTUALSCREEN)
	Local $aWidth = DllCall("user32.dll", "int", "GetSystemMetrics", "int", $SM_CXVIRTUALSCREEN)
	Local $aBounds[2] = [0, @DesktopWidth]
	If @error Or Not IsArray($aX) Or Not IsArray($aWidth) Or $aWidth[0] <= 0 Then Return $aBounds
	$aBounds[0] = Int($aX[0])
	$aBounds[1] = Int($aX[0]) + Int($aWidth[0])
	Return $aBounds
EndFunc   ;==>_VirtualDesktopHorizontalBounds

Func _DockController($hController, $hBlueStacks, $bReveal = True)
	If $bReveal Then WinSetState($hController, "", @SW_SHOW)
	Local $aController = WinGetPos($hController)
	Local $aBlueStacks = WinGetPos($hBlueStacks)
	If @error Or Not IsArray($aController) Or Not IsArray($aBlueStacks) Then Return SetExtended(0, False)
	If $aController[2] <= 0 Or $aController[3] <= 0 Or $aBlueStacks[2] <= 0 Or $aBlueStacks[3] <= 0 Then Return SetExtended(0, False)

	Local $hMonitor = _WinAPI_MonitorFromWindow($hBlueStacks, 2)
	Local $aMonitor = _WinAPI_GetMonitorInfo($hMonitor)
	If @error Or Not IsArray($aMonitor) Then Return SetExtended(0, False)
	Local $iWorkTop = DllStructGetData($aMonitor[1], "Top")
	Local $iWorkBottom = DllStructGetData($aMonitor[1], "Bottom")

	; A BlueStacks window may fill most of one monitor while an adjacent monitor still has room.
	; Horizontal docking therefore uses the complete virtual desktop, not only BlueStacks' monitor.
	; If neither side fits, fail instead of overlapping the game surface.
	Local $aVirtual = _VirtualDesktopHorizontalBounds()
	Local $iX = $aBlueStacks[0] + $aBlueStacks[2] + $g_iDockGap
	If $iX + $aController[2] > $aVirtual[1] Then $iX = $aBlueStacks[0] - $g_iDockGap - $aController[2]
	If $iX < $aVirtual[0] Then Return SetExtended(0, False)
	Local $iY = $aBlueStacks[1]
	If $iY < $iWorkTop Then $iY = $iWorkTop
	If $iY + $aController[3] > $iWorkBottom Then $iY = $iWorkBottom - $aController[3]

	; Avoid needless WinMove calls once the requested 8 px relationship is already stable.
	If Abs($aController[0] - $iX) <= 2 And Abs($aController[1] - $iY) <= 2 Then
		_DockControlStrip($hController)
		Local $iStripAction = @extended
		Return SetExtended($iStripAction, True)
	EndIf
	WinMove($hController, "", $iX, $iY)
	If @error Then Return SetExtended(0, False)
	Local $aMoved = WinGetPos($hController)
	Local $bMoved = IsArray($aMoved) And Abs($aMoved[0] - $iX) <= 2 And Abs($aMoved[1] - $iY) <= 2
	If $bMoved Then _DockControlStrip($hController)
	Return SetExtended($bMoved ? 1 : 0, $bMoved)
EndFunc   ;==>_DockController

Func _ShowControlStrip($hController)
	If $g_hControlStrip = 0 Then
		$g_hControlStrip = GUICreate("My Bot 2.0 Control", 472, $g_iControlStripHeight, -1, -1, _
			BitOR($WS_POPUP, $WS_BORDER), 0, $hController)
		GUISetBkColor(0x16191D, $g_hControlStrip)
		$g_idOpenControlCenter = GUICtrlCreateButton("OPEN CONTROL CENTER", 0, 0, 234, $g_iControlStripHeight)
		GUICtrlSetFont($g_idOpenControlCenter, 8, 700, 0, "Segoe UI")
		GUICtrlSetOnEvent($g_idOpenControlCenter, "_OpenControlCenter")
		$g_idMinimizePair = GUICtrlCreateButton("MINIMIZE BOTH - BACKGROUND", 238, 0, 234, $g_iControlStripHeight)
		GUICtrlSetFont($g_idMinimizePair, 8, 700, 0, "Segoe UI")
		GUICtrlSetOnEvent($g_idMinimizePair, "_MinimizeDockPair")
	EndIf
	If _WindowIsMinimized($hController) Then
		GUISetState(@SW_HIDE, $g_hControlStrip)
		Return True
	EndIf
	_DockControlStrip($hController)
	GUISetState(@SW_SHOW, $g_hControlStrip)
EndFunc   ;==>_ShowControlStrip

Func _DockControlStrip($hController)
	If $g_hControlStrip = 0 Or Not WinExists($hController) Then Return SetExtended(0, False)
	; A visible owned popup can restore its minimized owner on Windows. Never move or reveal this
	; strip until the paired controller is visible again; the pair synchronizer owns that transition.
	If _WindowIsMinimized($hController) Then
		WinSetState($g_hControlStrip, "", @SW_HIDE)
		Return SetExtended(0, False)
	EndIf
	Local $aController = WinGetPos($hController)
	If @error Or Not IsArray($aController) Or $aController[2] <= 0 Or $aController[3] <= 0 Then Return SetExtended(0, False)

	Local $hMonitor = _WinAPI_MonitorFromWindow($hController, 2)
	Local $aMonitor = _WinAPI_GetMonitorInfo($hMonitor)
	If @error Or Not IsArray($aMonitor) Then Return SetExtended(0, False)
	Local $iWorkTop = DllStructGetData($aMonitor[1], "Top")
	Local $iWorkBottom = DllStructGetData($aMonitor[1], "Bottom")
	Local $iX = $aController[0]
	Local $iY = $aController[1] + $aController[3] + $g_iControlStripGap
	If $iY + $g_iControlStripHeight > $iWorkBottom Then $iY = $aController[1] - $g_iControlStripGap - $g_iControlStripHeight
	If $iY < $iWorkTop Then Return SetExtended(0, False)

	Local $iHalfWidth = Int(($aController[2] - 4) / 2)
	GUICtrlSetPos($g_idOpenControlCenter, 0, 0, $iHalfWidth, $g_iControlStripHeight)
	GUICtrlSetPos($g_idMinimizePair, $iHalfWidth + 4, 0, $aController[2] - $iHalfWidth - 4, $g_iControlStripHeight)
	Local $aStrip = WinGetPos($g_hControlStrip)
	If IsArray($aStrip) And Abs($aStrip[0] - $iX) <= 2 And Abs($aStrip[1] - $iY) <= 2 And _
			Abs($aStrip[2] - $aController[2]) <= 2 And Abs($aStrip[3] - $g_iControlStripHeight) <= 2 Then Return SetExtended(0, True)
	WinMove($g_hControlStrip, "", $iX, $iY, $aController[2], $g_iControlStripHeight)
	If @error Then Return SetExtended(0, False)
	Local $aMoved = WinGetPos($g_hControlStrip)
	Local $bMoved = IsArray($aMoved) And Abs($aMoved[0] - $iX) <= 2 And Abs($aMoved[1] - $iY) <= 2
	Return SetExtended($bMoved ? 1 : 0, $bMoved)
EndFunc   ;==>_DockControlStrip

Func _OpenControlCenter()
	Local $iBrowserPid = ShellExecute($g_sControlCenterUrl)
	If @error Or $iBrowserPid <= 0 Then
		_ShowError("My Bot 2.0 is running, but its Control Center could not be opened." & @CRLF & @CRLF & $g_sControlCenterUrl)
		Return False
	EndIf
	Return True
EndFunc   ;==>_OpenControlCenter

Func _MinimizeDockPair()
	Return _SetDockPairMinimized()
EndFunc   ;==>_MinimizeDockPair

Func _SetDockPairMinimized()
	Local $hController = _FindControllerWindow()
	If @error Or Not $hController Then Return False
	Local $hBlueStacks = _FindBlueStacksWindow($hController)
	If @error Or Not $hBlueStacks Then
		_ShowError("My Bot 2.0 could not identify the exact BlueStacks instance paired with this controller.")
		Return False
	EndIf

	; Keep top-level ownership/styles unchanged. The ADB framebuffer remains the bot's input and
	; capture surface while the exact controller and exact instance-bound player leave the desktop.
	$g_iPairVisibilityState = $g_iPairMinimized
	WinSetState($hController, "", @SW_MINIMIZE)
	WinSetState($hBlueStacks, "", @SW_MINIMIZE)
	If $g_hControlStrip <> 0 Then WinSetState($g_hControlStrip, "", @SW_HIDE)
	Return True
EndFunc   ;==>_SetDockPairMinimized

Func _SetDockPairRestored()
	Local $hController = _FindControllerWindow()
	If @error Or Not $hController Then Return False
	Local $hBlueStacks = _FindBlueStacksWindow($hController)
	If @error Or Not $hBlueStacks Then Return False

	WinSetState($hController, "", @SW_RESTORE)
	WinSetState($hBlueStacks, "", @SW_RESTORE)
	$g_iPairVisibilityState = $g_iPairVisible
	Return True
EndFunc   ;==>_SetDockPairRestored

Func _ShowError($sMessage)
	Local $sLogText = StringStripWS(StringReplace($sMessage, @CRLF, " | "), $STR_STRIPTRAILING)
	_RecoveryLog("launcher error; pid=" & @AutoItPID & "; image=" & @ScriptFullPath & "; text=" & $sLogText)
	; A launcher failure must not pin itself above unrelated work. Keep the message user-visible,
	; but let Windows manage normal focus/z-order and release the caller automatically.
	MsgBox(BitOR($MB_OK, $MB_ICONERROR), $g_sLauncherTitle, $sMessage, $g_iLauncherErrorTimeoutSec)
EndFunc   ;==>_ShowError
