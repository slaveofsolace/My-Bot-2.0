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
#include <Misc.au3>
#include <MsgBoxConstants.au3>
#include <WinAPIGdi.au3>

Opt("MustDeclareVars", 1)

Global Const $g_sLauncherTitle = "My Bot 2.0"
Global Const $g_sControlCenterUrl = "http://127.0.0.1:8765/"
Global Const $g_sControllerPath = @ScriptDir & "\MyBot.run.MiniGui.exe"
Global Const $g_sControllerSha256 = "ae26c098ceb3c74e3d7f567834d9135257e094172e32140f4a5b615eaf90ceda"
Global Const $g_iControllerBytes = 1634304
Global Const $g_sHostPath = @ScriptDir & "\MyBot.run.exe"
Global Const $g_sHostConfigPath = $g_sHostPath & ".config"
Global Const $g_sEngineMarkerPath = @ScriptDir & "\MyBot.run.txt"
Global Const $g_sEnginePath = @ScriptDir & "\lib\MyBot.run.dll"
Global Const $g_sControllerTitlePattern = "^My Bot Mini v8\.2\.0(?: \(.+\))?$"
Global Const $g_sBlueStacksTitle = "BlueStacks5-Pie64"
Global Const $g_iDockGap = 8
Global Const $g_iDockWaitMs = 600000
Global Const $g_iDockPollMs = 1000
Global Const $g_iErrorAlreadyExists = 183

If Not _ValidateInstallation() Then Exit 1

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
Local $iControllerPid = ShellExecute($g_sControllerPath, "/nowatchdog", @ScriptDir, "", @SW_SHOWNORMAL)
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

Func _ValidateInstallation()
	If Not FileExists($g_sControllerPath) Then Return _InstallError("MyBot.run.MiniGui.exe is missing.", $g_sControllerPath)
	If FileGetSize($g_sControllerPath) <> $g_iControllerBytes Or _FileSha256($g_sControllerPath) <> $g_sControllerSha256 Then
		Return _InstallError("The native controller is not the supported MyBot.run v8.2.0 build.", $g_sControllerPath)
	EndIf
	If Not FileExists($g_sHostPath) Then Return _InstallError("MyBot.run.exe is missing.", $g_sHostPath)
	If Not FileExists($g_sHostConfigPath) Then Return _InstallError("MyBot.run.exe.config is missing.", $g_sHostConfigPath)
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

Func _FindBlueStacksWindow()
	Local $aWindows = WinList($g_sBlueStacksTitle)
	Local $hFound = 0
	For $i = 1 To $aWindows[0][0]
		If $aWindows[$i][0] <> $g_sBlueStacksTitle Then ContinueLoop
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
		Local $hBlueStacks = _FindBlueStacksWindow()
		If @error = 2 Then Return False
		If $hBlueStacks Then Return _DockController($hController, $hBlueStacks)
		Sleep(500)
	Until TimerDiff($hTimer) >= $iTimeoutMs
	Return False
EndFunc   ;==>_DockWhenReady

Func _KeepDocked($hController, $iControllerPid)
	While ProcessExists($iControllerPid)
		; Re-prove the controller's exact PID, path, and title before every possible move. If its
		; window is briefly recreated, reacquire only another exact window from the same process.
		If Not _ControllerWindowMatches($hController, $iControllerPid) Then
			$hController = _FindControllerWindow($iControllerPid)
			If @error = 2 Then Return False
			If Not $hController Then
				Sleep($g_iDockPollMs)
				ContinueLoop
			EndIf
		EndIf

		Local $hBlueStacks = _FindBlueStacksWindow()
		If @error <> 2 And $hBlueStacks And _WindowCanDock($hController) And _WindowCanDock($hBlueStacks) Then
			_DockController($hController, $hBlueStacks, False)
		EndIf
		Sleep($g_iDockPollMs)
	WEnd
	Return True
EndFunc   ;==>_KeepDocked

Func _WindowCanDock($hWindow)
	If Not WinExists($hWindow) Then Return False
	Local $iState = WinGetState($hWindow)
	If @error Then Return False
	Return BitAND($iState, 2) <> 0 And BitAND($iState, 16) = 0
EndFunc   ;==>_WindowCanDock

Func _DockController($hController, $hBlueStacks, $bReveal = True)
	If $bReveal Then WinSetState($hController, "", @SW_SHOW)
	Local $aController = WinGetPos($hController)
	Local $aBlueStacks = WinGetPos($hBlueStacks)
	If @error Or Not IsArray($aController) Or Not IsArray($aBlueStacks) Then Return False
	If $aController[2] <= 0 Or $aController[3] <= 0 Or $aBlueStacks[2] <= 0 Or $aBlueStacks[3] <= 0 Then Return False

	Local $hMonitor = _WinAPI_MonitorFromWindow($hBlueStacks, 2)
	Local $aMonitor = _WinAPI_GetMonitorInfo($hMonitor)
	If @error Or Not IsArray($aMonitor) Then Return False
	Local $iWorkLeft = DllStructGetData($aMonitor[1], "Left")
	Local $iWorkTop = DllStructGetData($aMonitor[1], "Top")
	Local $iWorkRight = DllStructGetData($aMonitor[1], "Right")
	Local $iWorkBottom = DllStructGetData($aMonitor[1], "Bottom")

	Local $iX = $aBlueStacks[0] + $aBlueStacks[2] + $g_iDockGap
	If $iX + $aController[2] > $iWorkRight Then $iX = $aBlueStacks[0] - $g_iDockGap - $aController[2]
	If $iX < $iWorkLeft Then $iX = $iWorkRight - $aController[2]
	Local $iY = $aBlueStacks[1]
	If $iY < $iWorkTop Then $iY = $iWorkTop
	If $iY + $aController[3] > $iWorkBottom Then $iY = $iWorkBottom - $aController[3]

	; Avoid needless WinMove calls once the requested 8 px relationship is already stable.
	If Abs($aController[0] - $iX) <= 2 And Abs($aController[1] - $iY) <= 2 Then Return True
	WinMove($hController, "", $iX, $iY)
	If @error Then Return False
	Local $aMoved = WinGetPos($hController)
	Return IsArray($aMoved) And Abs($aMoved[0] - $iX) <= 2 And Abs($aMoved[1] - $iY) <= 2
EndFunc   ;==>_DockController

Func _OpenControlCenter()
	Local $iBrowserPid = ShellExecute($g_sControlCenterUrl)
	If @error Or $iBrowserPid <= 0 Then
		_ShowError("My Bot 2.0 is running, but its Control Center could not be opened." & @CRLF & @CRLF & $g_sControlCenterUrl)
		Return False
	EndIf
	Return True
EndFunc   ;==>_OpenControlCenter

Func _ShowError($sMessage)
	MsgBox(BitOR($MB_OK, $MB_ICONERROR, $MB_TOPMOST), $g_sLauncherTitle, $sMessage)
EndFunc   ;==>_ShowError
