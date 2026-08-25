; #FUNCTION# ====================================================================================================================
; Name ..........: OpenBlueStacks5
; Description ...:
; Syntax ........: OpenBlueStacks5([$bRestart = False])
; Parameters ....: $bRestart            - [optional] a boolean value. Default is False.
; Return values .: None
; Author ........: xbebenk (2020)
; Modified ......:
; Remarks .......: This file is part of MyBot, previously known as ClashGameBot. Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
; Related .......:
; Link ..........: https://github.com/MyBotRun/MyBot/wiki
; Example .......: No
; ===============================================================================================================================
Func DoubleQuote($sString)
	Return Chr(34) & $sString & Chr(34)
EndFunc   ;==>DoubleQuote

Func GetBlueStacks5ProgramParameter($bAlternative = False)
	Return DoubleQuote("--instance") & " " & DoubleQuote($g_sAndroidInstance)
EndFunc   ;==>GetBlueStacks5ProgramParameter

Global Const $g_sBlueStacks5LaunchOnlyOwnerSchema = "my-bot-launch-only-emulator-owner-v1"
Global Const $g_sBlueStacks5LaunchOnlyOwnerReceipt = $g_sMBRFuncRuntimeLocalAppData & "\My Bot 2.0\launch-only-emulator-owner-v1.json"

Func _BlueStacks5LaunchOnlyReceiptPathSafe($bRequireReceipt = False)
	Local $sParent = $g_sMBRFuncRuntimeLocalAppData & "\My Bot 2.0"
	Local $aParent = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $sParent)
	If @error Or Not IsArray($aParent) Or $aParent[0] = 0xFFFFFFFF Then Return False
	If BitAND($aParent[0], 0x10) = 0 Or BitAND($aParent[0], 0x400) <> 0 Then Return False
	If Not FileExists($g_sBlueStacks5LaunchOnlyOwnerReceipt) Then Return Not $bRequireReceipt
	Local $aReceipt = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $g_sBlueStacks5LaunchOnlyOwnerReceipt)
	If @error Or Not IsArray($aReceipt) Or $aReceipt[0] = 0xFFFFFFFF Then Return False
	Return BitAND($aReceipt[0], 0x10) = 0 And BitAND($aReceipt[0], 0x400) = 0
EndFunc   ;==>_BlueStacks5LaunchOnlyReceiptPathSafe

Func _BlueStacks5WriteLaunchOnlyOwnerReceipt($iPlayerPid)
	If $iPlayerPid <= 0 Or ProcessExists2($iPlayerPid) <> $iPlayerPid Then Return False
	If Not StringRegExp($g_sAndroidInstance, "^[A-Za-z0-9._-]{1,64}$") Then Return False
	If Not $g_bMBRFuncEngineSupervisorValid Then Return False
	Local $iLauncherPid = Int($g_sMBRFuncEngineLauncherPidText)
	Local $iControllerPid = _MBRFuncParentPid(@AutoItPID)
	Local $sLauncherCreated = _MBRFuncProcessCreationId($iLauncherPid)
	Local $sControllerCreated = _MBRFuncProcessCreationId($iControllerPid)
	Local $sBackendCreated = _MBRFuncProcessCreationId(@AutoItPID)
	Local $sPlayerCreated = _MBRFuncProcessCreationId($iPlayerPid)
	If $iLauncherPid <= 0 Or Not ProcessExists($iLauncherPid) Or $iControllerPid <= 0 Or _
			$sLauncherCreated <> $g_sMBRFuncEngineLauncherCreated Or $sControllerCreated = "" Or _
			$sBackendCreated = "" Or $sPlayerCreated = "" Then Return False
	DirCreate($g_sMBRFuncRuntimeLocalAppData & "\My Bot 2.0")
	If Not _BlueStacks5LaunchOnlyReceiptPathSafe(False) Then Return False
	Local $sReceipt = '{"schema":"' & $g_sBlueStacks5LaunchOnlyOwnerSchema & '","launcher_pid":' & $iLauncherPid & _
		',"launcher_created":"' & $sLauncherCreated & '","controller_pid":' & $iControllerPid & _
		',"controller_created":"' & $sControllerCreated & '","backend_pid":' & @AutoItPID & _
		',"backend_created":"' & $sBackendCreated & '","player_pid":' & $iPlayerPid & _
		',"player_created":"' & $sPlayerCreated & '","emulator":"BlueStacks5","instance":"' & $g_sAndroidInstance & '"}'
	Local $sTemporary = $g_sBlueStacks5LaunchOnlyOwnerReceipt & ".tmp." & @AutoItPID
	If FileExists($sTemporary) Then FileDelete($sTemporary)
	If FileExists($sTemporary) Then Return False
	Local $hReceipt = FileOpen($sTemporary, 10)
	If $hReceipt = -1 Then Return False
	Local $bWritten = FileWrite($hReceipt, $sReceipt) = 1
	Local $bFlushed = FileFlush($hReceipt)
	FileClose($hReceipt)
	If Not $bWritten Or Not $bFlushed Or Not FileMove($sTemporary, $g_sBlueStacks5LaunchOnlyOwnerReceipt, 1) Then
		FileDelete($sTemporary)
		Return False
	EndIf
	If Not _BlueStacks5LaunchOnlyReceiptPathSafe(True) Then Return False
	Return FileRead($g_sBlueStacks5LaunchOnlyOwnerReceipt) = $sReceipt
EndFunc   ;==>_BlueStacks5WriteLaunchOnlyOwnerReceipt

; Return the one HD-Player process that owns the configured instance's loopback ADB listener. Newer
; BlueStacks builds can withhold both CommandLine and ExecutablePath from WMI and can publish an empty
; Qt window title. The configured per-instance ADB port remains an OS-owned identity boundary: require
; an exact loopback LISTENING row, the exact HD-Player image name, and one unique owner PID.
Func _BlueStacks5ConfiguredAdbOwnerPid()
	Local $aPort = StringRegExp(String($g_sAndroidAdbDevice), "^127\.0\.0\.1:([0-9]{1,5})$", 1)
	If Not IsArray($aPort) Then Return 0
	Local $iExpectedPort = Int($aPort[0])
	If $iExpectedPort < 1 Or $iExpectedPort > 65535 Then Return 0
	Local $aTcp = _CV_GetExtendedTcpTable()
	If Not IsArray($aTcp) Then Return 0
	Local $iOwnerPid = 0
	For $i = 1 To UBound($aTcp) - 1
		If Int($aTcp[$i][2]) <> $iExpectedPort Or $aTcp[$i][5] <> "LISTENING" Or _
				StringLower(String($aTcp[$i][0])) <> "hd-player.exe" Or _
				String($aTcp[$i][1]) <> "localhost (127.0.0.1)" Then ContinueLoop
		Local $iCandidatePid = Int($aTcp[$i][6])
		If $iCandidatePid <= 0 Or ProcessExists2($iCandidatePid) <> $iCandidatePid Then ContinueLoop
		If $iOwnerPid <> 0 And $iOwnerPid <> $iCandidatePid Then Return 0
		$iOwnerPid = $iCandidatePid
	Next
	Return $iOwnerPid
EndFunc   ;==>_BlueStacks5ConfiguredAdbOwnerPid

Func _BlueStacks5ModernWindowMatchesInstance($hWindow, $iAdbOwnerPid)
	If $iAdbOwnerPid <= 0 Or Not IsHWnd($hWindow) Or WinGetProcess($hWindow) <> $iAdbOwnerPid Or _
			Not StringRegExp(_WinAPI_GetClassName($hWindow), "^Qt[0-9]+QWindowIcon$") Then Return False
	Local $sTitle = WinGetTitle($hWindow)
	Return $sTitle = "" Or StringCompare($sTitle, "BlueStacks5-" & $g_sAndroidInstance, 0) = 0
EndFunc   ;==>_BlueStacks5ModernWindowMatchesInstance

; Distinguish a uniquely bound but frozen modern player from an instance that is absent. The
; template-free one-shot routes intentionally never launch, reboot, or terminate BlueStacks, but a
; precise diagnostic lets the operator use the reviewed Recovery path instead of being told that an
; exact window which still exists is "not already running".
Func BlueStacks5ExactInstanceWindowHung()
	Local $iAdbOwnerPid = _BlueStacks5ConfiguredAdbOwnerPid()
	If $iAdbOwnerPid <= 0 Then Return False
	Local $aWindows = _WinAPI_EnumWindows(False)
	If Not IsArray($aWindows) Then Return False

	Local $hFound = 0
	Local $iFound = 0
	For $i = 1 To $aWindows[0][0]
		Local $hWindow = $aWindows[$i][0]
		If Not _BlueStacks5ModernWindowMatchesInstance($hWindow, $iAdbOwnerPid) Then ContinueLoop
		$hFound = $hWindow
		$iFound += 1
	Next
	If $iFound <> 1 Or Not IsHWnd($hFound) Then Return False

	Local $aHung = DllCall("user32.dll", "bool", "IsHungAppWindow", "hwnd", $hFound)
	If @error Or Not IsArray($aHung) Then Return False
	Return $aHung[0] <> 0
EndFunc   ;==>BlueStacks5ExactInstanceWindowHung

; BlueStacks 5.22 moved its visible shell from the inherited BlueStacksApp class/title to a Qt
; top-level window. Prefer the exact configured title, but when BlueStacks publishes an empty title
; bind the unique Qt shell to the unique OS-owned ADB listener PID for this exact instance.
Func FindBlueStacks5WindowFallback()
	Static $iTrustedPid = 0
	Static $sTrustedInstance = ""
	If $sTrustedInstance <> $g_sAndroidInstance Then
		$iTrustedPid = 0
		$sTrustedInstance = $g_sAndroidInstance
	EndIf
	; Include hidden/off-screen windows: the product launcher intentionally minimizes the native
	; surfaces while leaving the exact emulator instance running for browser control.
	Local $aWindows = _WinAPI_EnumWindows(False)
	Local $hFound = 0
	Local $iFound = 0
	Local $iQtCandidates = 0
	Local $iTitleMatches = 0
	Local $iBlankTitleMatches = 0
	Local $iInvalidGeometry = 0
	Local $iUndersized = 0
	Local $iAdbOwnerPid = _BlueStacks5ConfiguredAdbOwnerPid()
	If $g_sAndroidInstance = "" Or $iAdbOwnerPid = 0 Then
		SetDebugLog("BlueStacks5 modern-window fallback rejected: exact instance ADB listener owner is unavailable", $COLOR_ERROR)
		Return 0
	EndIf
	If Not IsArray($aWindows) Then Return 0
	For $i = 1 To $aWindows[0][0]
		Local $hWindow = $aWindows[$i][0]
		If Not StringRegExp(_WinAPI_GetClassName($hWindow), "^Qt[0-9]+QWindowIcon$") Then ContinueLoop
		$iQtCandidates += 1
		Local $sTitle = WinGetTitle($hWindow)
		If StringCompare($sTitle, "BlueStacks5-" & $g_sAndroidInstance, 0) = 0 Then
			$iTitleMatches += 1
		ElseIf $sTitle = "" Then
			$iBlankTitleMatches += 1
		Else
			ContinueLoop
		EndIf
		If Not _BlueStacks5ModernWindowMatchesInstance($hWindow, $iAdbOwnerPid) Then ContinueLoop
		Local $aPosition = WinGetPos($hWindow)
		If Not IsArray($aPosition) Then
			$iInvalidGeometry += 1
			ContinueLoop
		EndIf
		; A minimized Qt window reports a tiny placeholder rectangle. Exact class/title/instance and
		; uniqueness remain authoritative while ADB supplies both capture and input coordinates.
		If BitAND(WinGetState($hWindow), 16) = 0 And ($aPosition[2] < 400 Or $aPosition[3] < 400) Then
			$iUndersized += 1
			ContinueLoop
		EndIf
		$hFound = $hWindow
		$iFound += 1
	Next
	If $iFound = 1 Then
		Local $iFoundPid = WinGetProcess($hFound)
		If $iFoundPid > 0 Then
			$iTrustedPid = $iFoundPid
			$sTrustedInstance = $g_sAndroidInstance
		EndIf
		Return $hFound
	EndIf
	Local $sTrustedPid = ($iTrustedPid > 0 ? String($iTrustedPid) : "none")
	Local $sTrustedPidAlive = ($iTrustedPid > 0 ? String(ProcessExists2($iTrustedPid) = $iTrustedPid) : "unknown")
	Local $sFallbackDiagnostic = "BlueStacks5 modern-window fallback rejected: expected_title='BlueStacks5-" & $g_sAndroidInstance & _
		"', adb_owner_pid=" & $iAdbOwnerPid & ", qt_candidates=" & $iQtCandidates & ", title_matches=" & $iTitleMatches & _
		", blank_title_matches=" & $iBlankTitleMatches & ", invalid_geometry=" & $iInvalidGeometry & _
		", undersized=" & $iUndersized & ", accepted=" & $iFound & ", trusted_pid=" & $sTrustedPid & ", trusted_pid_alive=" & $sTrustedPidAlive
	If $iFound > 1 Then
		SetDebugLog($sFallbackDiagnostic & ", reason=multiple exact player windows", $COLOR_ERROR)
	Else
		SetDebugLog($sFallbackDiagnostic & ", reason=no exact player window")
	EndIf
	Return 0
EndFunc   ;==>FindBlueStacks5WindowFallback

; BlueStacks 5.22's Qt shell is not the Android rendering surface. Its native toolbar and
; window chrome can be resized independently while the ADB framebuffer remains fixed at the
; configured dimensions. When capture and input both use ADB, report that framebuffer geometry
; so generic window-resize recovery never destroys a healthy modern instance.
Func GetBlueStacks5ModernAdbSurfacePosition()
	If $g_sAndroidEmulator <> "BlueStacks5" Or Not $g_bChkBackgroundMode Or Not $g_bAndroidAdbScreencap Or Not $g_bAndroidAdbClick Then Return 0
	Local $hWindow = GetCurrentAndroidHWnD()
	If $g_sAndroidInstance = "" Or Not _BlueStacks5ModernWindowMatchesInstance($hWindow, _BlueStacks5ConfiguredAdbOwnerPid()) Then Return 0
	Local $aSurface[4] = [0, 0, $g_iAndroidClientWidth, $g_iAndroidClientHeight]
	Return $aSurface
EndFunc   ;==>GetBlueStacks5ModernAdbSurfacePosition

; Map desktop mouse input to the actual game viewport. Current BlueStacks Qt shells can include a
; title bar, toolbar, and advertisement rail, and can scale the configured ADB framebuffer. The one
; exact BlueStacksApp descendant is the render surface; require its process, visibility, containment,
; and aspect ratio to match before returning screen coordinates. Never infer a viewport from the
; top-level shell dimensions because that can silently select the wrong building.
Func GetBlueStacks5ModernManualViewportPosition()
	Local $aSurface = GetBlueStacks5ModernAdbSurfacePosition()
	If Not IsArray($aSurface) Then Return 0
	Local $hWindow = GetCurrentAndroidHWnD()
	Local $aViewport = ManualViewportFindBlueStacks5Surface($hWindow, $g_iAndroidClientWidth, $g_iAndroidClientHeight)
	If Not IsArray($aViewport) Then SetDebugLog("BlueStacks5 manual viewport rejected: no unique proven BlueStacksApp surface", $COLOR_ERROR)
	Return $aViewport
EndFunc   ;==>GetBlueStacks5ModernManualViewportPosition

Func OpenBlueStacks5($bRestart = False)
	SetLog("Starting BlueStacks and Clash Of Clans", $COLOR_SUCCESS)
	If Not InitAndroid() Then Return False
	; open newer BlueStacks versions 5
	Return _OpenBlueStacks5($bRestart)
EndFunc   ;==>OpenBlueStacks5

; A recognized frame is not a truthful launch receipt if the emulator immediately dies afterward.
; Bind the exact proven window/PID and require a short passive settle period. This helper never
; captures another frame or sends input; it only observes process/window liveness and Stop.
Func _LaunchBlueStacks5FinalizePassiveProof(ByRef $sReason, $sProof, $bStartedEmulator)
	Local $hProvenWindow = $g_hAndroidWindow
	Local $iProvenPid = IsHWnd($hProvenWindow) ? WinGetProcess($hProvenWindow) : 0
	If $iProvenPid <= 0 Or Not ProcessExists($iProvenPid) Or Not WinExists($hProvenWindow) Then
		$sReason = "BlueStacks exited before the passive game-ready proof could settle"
		Return False
	EndIf

	Local $hSettleTimer = __TimerInit()
	While __TimerDiff($hSettleTimer) < 5000
		If RunControlStopRequested() Or Not $g_bRunState Then
			$sReason = "BlueStacks and Clash of Clans launch cancelled while settling passive game-ready proof"
			Return False
		EndIf
		If Not ProcessExists($iProvenPid) Or Not IsHWnd($hProvenWindow) Or _
				Not WinExists($hProvenWindow) Or WinGetProcess($hProvenWindow) <> $iProvenPid Then
			$sReason = "BlueStacks exited during the passive game-ready settle period"
			Return False
		EndIf
		If _Sleep(250) Then
			$sReason = "BlueStacks and Clash of Clans launch cancelled while settling passive game-ready proof"
			Return False
		EndIf
	WEnd

	$sReason = "BlueStacks and Clash of Clans launched; " & $sProof & "; emulator_started=" & ($bStartedEmulator ? "true" : "false")
	Return True
EndFunc   ;==>_LaunchBlueStacks5FinalizePassiveProof

; Launch only the exact configured BlueStacks 5 process for a bounded diagnostic.
; Unlike the inherited LaunchAndroid() helper, this process-only contract must not
; configure shared folders, press Home, launch CoC through the legacy path, or stop
; the bot. CoC is started below through an exact ADB activity command after the
; requested instance is owned and connected.
Func LaunchBlueStacks5ProcessOnly($sProgramPath, $sCmdParam, $sPath)
	If $sCmdParam And StringLeft($sCmdParam, 1) <> " " Then
		$sCmdParam = " " & $sCmdParam
	EndIf
	Local $pid = 0
	For $i = 1 To 3
		SetDebugLog("LaunchBlueStacks5ProcessOnly: " & $sProgramPath & $sCmdParam)
		$pid = Run($sProgramPath & $sCmdParam, $sPath)
		If _Sleep(3000) Then Return 0
		If $pid <> 0 Then $pid = ProcessExists($pid)
		If $pid <> 0 Then ExitLoop
	Next
	SetDebugLog("$LaunchBlueStacks5ProcessOnlyPID= " & $pid)
	Return $pid
EndFunc   ;==>LaunchBlueStacks5ProcessOnly

; Launch the exact configured BlueStacks 5 instance and the CoC activity for a bounded diagnostic.
; This route never enters the legacy run loop, changes accounts, pushes shared preferences, presses
; Home, clears obstacles, zooms, trains, donates, searches, attacks, upgrades, or spends. Home proof
; is passive ADB capture only; failures do not close/reboot the emulator or call the legacy Stop path.
Func LaunchBlueStacks5CoCOnly(ByRef $sReason)
	$sReason = ""
	If $g_sAndroidEmulator <> "BlueStacks5" Then
		$sReason = "Launch-only validation currently requires BlueStacks 5"
		Return False
	EndIf
	If Not StringRegExp($g_sAndroidInstance, "^[A-Za-z0-9._-]{1,64}$") Then
		$sReason = "The configured BlueStacks 5 instance is missing or unsafe"
		Return False
	EndIf
	If Not $g_bRunState Or RunControlStopRequested() Then
		$sReason = "BlueStacks and Clash of Clans launch cancelled before initialization"
		Return False
	EndIf
	If Not InitAndroid() Or $g_sAndroidEmulator <> "BlueStacks5" Then
		$sReason = "The exact BlueStacks 5 adapter could not be initialized"
		Return False
	EndIf

	Local $bStartedEmulator = False
	Local $bHadExactWindow = WinGetAndroidHandle() <> 0
	Local $iLaunchPid = 0
	Local $bProcessKilled = False
	Local $hLaunchTimer = __TimerInit()
	LaunchConsole($g_sAndroidAdbPath, AddSpace($g_sAndroidAdbGlobalOptions) & "start-server", $bProcessKilled)
	If RunControlStopRequested() Or Not $g_bRunState Then
		$sReason = "BlueStacks and Clash of Clans launch cancelled before the emulator start"
		Return False
	EndIf
	If WinGetAndroidHandle() = 0 Then
		$iLaunchPid = LaunchBlueStacks5ProcessOnly($g_sAndroidProgramPath, GetAndroidProgramParameter(), $g_sAndroidPath)
		$bStartedEmulator = $iLaunchPid > 0
		If $iLaunchPid = 0 And WinGetAndroidHandle() = 0 Then
			$sReason = "The exact BlueStacks 5 instance did not accept the launch request"
			Return False
		EndIf
	EndIf

	While WinGetAndroidHandle() = 0 Or $g_hAndroidControl = 0
		If RunControlStopRequested() Or Not $g_bRunState Then
			$sReason = "BlueStacks and Clash of Clans launch cancelled while waiting for the exact instance"
			Return False
		EndIf
		If __TimerDiff($hLaunchTimer) > $g_iAndroidLaunchWaitSec * 1000 Then
			$sReason = "The exact BlueStacks 5 instance did not become ready before the bounded deadline"
			Return False
		EndIf
		If _Sleep(500) Then
			$sReason = "BlueStacks and Clash of Clans launch cancelled while waiting for the exact instance"
			Return False
		EndIf
	WEnd
	If Not $bHadExactWindow And WinGetAndroidHandle() <> 0 Then $bStartedEmulator = True

	If Not ConnectAndroidAdb(False, 3000) Then
		$sReason = "ADB did not bind to the exact BlueStacks 5 instance"
		Return False
	EndIf
	If WaitForAndroidBootCompleted($g_iAndroidLaunchWaitSec, $hLaunchTimer) Then
		$sReason = RunControlStopRequested() ? _
				"BlueStacks and Clash of Clans launch cancelled during Android boot" : _
				"The exact BlueStacks 5 instance did not finish booting before the bounded deadline"
		Return False
	EndIf
	If RunControlStopRequested() Or Not $g_bRunState Then
		$sReason = "BlueStacks and Clash of Clans launch cancelled before the game activity"
		Return False
	EndIf
	If $bStartedEmulator Then
		Local $iOwnedPlayerPid = _BlueStacks5ConfiguredAdbOwnerPid()
		If $iOwnedPlayerPid <= 0 Or Not _BlueStacks5WriteLaunchOnlyOwnerReceipt($iOwnedPlayerPid) Then
			$sReason = "BlueStacks launched but exact product ownership could not be recorded for cleanup"
			Return False
		EndIf
	EndIf

	; Deliberately bypass the legacy game restart helper, which can push account shared preferences,
	; close/reboot the emulator, clear queued clicks, and retry. One exact am-start command is the only
	; allowed game-launch input in this diagnostic.
	Local $sLaunchOutput = AndroidAdbSendShellCommand("am start -n " & $g_sAndroidGamePackage & "/" & $g_sAndroidGameClass, 15000)
	If @error Or StringInStr($sLaunchOutput, "Error:") Or StringInStr($sLaunchOutput, "Exception") Then
		$sReason = "Clash of Clans did not accept the one bounded Android activity launch"
		Return False
	EndIf

	Local $hGameTimer = __TimerInit()
	While __TimerDiff($hGameTimer) <= 90000
		If RunControlStopRequested() Or Not $g_bRunState Then
			$sReason = "BlueStacks and Clash of Clans launch cancelled while waiting for passive game-ready proof"
			Return False
		EndIf
		If GetAndroidProcessPID(Default, False) <> 0 Then
			; OpenHomeCollectorsProveHome() refreshes the current ADB frame before checking Home.
			; If a known startup overlay blocks Home, recognize it from that same fresh frame but never
			; click or dismiss it. The caller returns idle and game_ready remains false until Home is visible.
                        If OpenHomeCollectorsProveHome() Then
                                Return _LaunchBlueStacks5FinalizePassiveProof($sReason, "Home Village passively proven", $bStartedEmulator)
                        EndIf
                        If BuilderMaintenanceRoutePrepared() And _CheckPixel($aIsOnBuilderBase, False) Then
                                Return _LaunchBlueStacks5FinalizePassiveProof($sReason, "Builder Base passively proven for the selected Builder maintenance route", $bStartedEmulator)
                        EndIf
                        If OpenHomeDailyRewardOverlayReady() Then
                                Local $aDailyRewardClaim[2]
                                Local $iDailyRewardClaims = OpenHomeDailyRewardFindClaim($aDailyRewardClaim)
				If $iDailyRewardClaims = 1 Then
					Return _LaunchBlueStacks5FinalizePassiveProof($sReason, "verified Daily Reward overlay and one Claim candidate passively recognized at (" & $aDailyRewardClaim[0] & "," & $aDailyRewardClaim[1] & "); Home is blocked until the operator handles the overlay", $bStartedEmulator)
				EndIf
				If $iDailyRewardClaims = 0 Then
					Return _LaunchBlueStacks5FinalizePassiveProof($sReason, "verified Daily Reward overlay passively recognized with no actionable Claim candidate; Home is blocked until the operator handles the overlay", $bStartedEmulator)
				EndIf
				Return _LaunchBlueStacks5FinalizePassiveProof($sReason, "verified Daily Reward overlay passively recognized with ambiguous Claim candidates=" & $iDailyRewardClaims & "; no input is permitted; Home is blocked until the operator handles the overlay", $bStartedEmulator)
			EndIf
			If OpenHomeDailyRewardClaimedOverlayReady() Then
				Return _LaunchBlueStacks5FinalizePassiveProof($sReason, "verified post-claim Daily Reward overlay passively recognized; Home is blocked until the operator closes the overlay", $bStartedEmulator)
			EndIf
			If OpenHomeInactivityReloadDialogReady() Then
				Return _LaunchBlueStacks5FinalizePassiveProof($sReason, "verified inactivity reload dialog passively recognized; Home is blocked until the operator reloads the game", $bStartedEmulator)
			EndIf
			If OpenHomeWelcomeBackOverlayReady() Then
				Return _LaunchBlueStacks5FinalizePassiveProof($sReason, "verified Welcome Back overlay passively recognized; Home is blocked until the operator handles the overlay", $bStartedEmulator)
			EndIf
		EndIf
		If _Sleep(1000) Then
			$sReason = "BlueStacks and Clash of Clans launch cancelled while waiting for passive game-ready proof"
			Return False
		EndIf
	WEnd
	$sReason = "Clash of Clans launched but neither Home Village nor a verified startup overlay was passively proven before the bounded deadline"
	Return False
EndFunc   ;==>LaunchBlueStacks5CoCOnly

Func _OpenBlueStacks5($bRestart = False)

	Local $hTimer, $iCount = 0, $cmdPar
	Local $PID, $ErrorResult, $connected_to, $process_killed

	; always start ADB first to avoid ADB connection problems
	LaunchConsole($g_sAndroidAdbPath, AddSpace($g_sAndroidAdbGlobalOptions) & "start-server", $process_killed)

	$cmdPar = GetAndroidProgramParameter()
	If WinGetAndroidHandle() = 0 Then
		; Current BlueStacks exits a duplicate launcher process when the requested instance is already
		; running. Do not cancel the bot on that zero PID until the exact Qt instance fallback has had
		; one final chance to claim the existing player window.
		$PID = LaunchAndroid($g_sAndroidProgramPath, $cmdPar, $g_sAndroidPath, 0, False)
		If $PID = 0 And WinGetAndroidHandle() = 0 Then
			SetLog("Unable to load " & $g_sAndroidEmulator & ($g_sAndroidInstance = "" ? "" : "(" & $g_sAndroidInstance & ")") & ", please check emulator/installation.", $COLOR_ERROR)
			SetLog("Unable to continue........", $COLOR_WARNING)
			btnStop()
			Return False
		EndIf
		;LaunchAndroid($g_sAndroidProgramPath, GetAndroidProgramParameter(), $g_sAndroidPath)
	Else
		SetLog("BlueStacks5 Already Loaded")
		Return True
	EndIf

	$hTimer = __TimerInit() ; start a timer for tracking BS start up time
	While $g_hAndroidControl = 0
		_StatusUpdateTime($hTimer, $g_sAndroidEmulator & " Starting")
		If __TimerDiff($hTimer) > $g_iAndroidLaunchWaitSec * 1000 Then ; if no BS position returned in 4 minutes, BS/PC has major issue so exit
			SetLog("Serious error has occurred, please restart PC and try again", $COLOR_ERROR)
			SetLog("BlueStacks refuses to load, waited " & Round(__TimerDiff($hTimer) / 1000, 2) & " seconds", $COLOR_ERROR)
			SetLog("Unable to continue........", $COLOR_WARNING)
			btnstop()
			SetError(1, 1, -1)
			Return False
		EndIf
		; Match the LDPlayer and MuMu adapters: yield to the message/control pump and honor Stop.
		; The inherited busy loop could pin a core and ignore a stop request for the full launch timeout.
		If _Sleep(500) Then Return False
		WinGetAndroidHandle()
	WEnd

	If $g_hAndroidControl Then
		$connected_to = ConnectAndroidAdb(False, 3000) ; small time-out as ADB connection must be available now
		If WaitForAndroidBootCompleted($g_iAndroidLaunchWaitSec - __TimerDiff($hTimer) / 1000, $hTimer) Then Return
		If Not $g_bRunState Then Return
		SetLog("BlueStacks Loaded, took " & Round(__TimerDiff($hTimer) / 1000, 2) & " seconds to begin.", $COLOR_SUCCESS)
		Return True
	EndIf
	Return False
EndFunc   ;==>_OpenBlueStacks5

Func GetBlueStacks5AdbPath()
	Local $adbPath = $__BlueStacks_Path & "HD-Adb.exe"
	If FileExists($adbPath) Then Return $adbPath
	Return ""
EndFunc   ;==>GetBlueStacks5AdbPath

Func InitBlueStacks5X($bCheckOnly = False, $bAdjustResolution = False, $bLegacyMode = False)
	;Bluestacks5 doesn't have registry tree for engine, only installation dir info available on registry
	$__BlueStacks5_Version = RegRead($g_sHKLM & "\SOFTWARE\BlueStacks_nxt\", "Version")
	$__BlueStacks_Path = RegRead($g_sHKLM & "\SOFTWARE\BlueStacks_nxt\", "InstallDir")
	$__BlueStacks_Path = StringReplace($__BlueStacks_Path, "\\", "\")

	Local $frontend_exe = ["HD-Frontend.exe", "HD-Player.exe"]
	Local $i, $aFiles = ["HD-Player.exe", "HD-Adb.exe"] ; first element can be $frontend_exe array!

	For $i = 0 To UBound($aFiles) - 1
		Local $File
		Local $bFileFound = False
		Local $aFiles2 = $aFiles[$i]
		If Not IsArray($aFiles2) Then Local $aFiles2 = [$aFiles[$i]]
		For $j = 0 To UBound($aFiles2) - 1
			$File = $__BlueStacks_Path & $aFiles2[$j]
			$bFileFound = FileExists($File)
			If $bFileFound Then
				; check if $frontend_exe is array, then convert
				If $i = 0 And IsArray($frontend_exe) Then $frontend_exe = $aFiles2[$j]
				ExitLoop
			EndIf
		Next
		If Not $bFileFound Then
			If Not $bCheckOnly Then
				SetLog("Serious error has occurred: Cannot find " & $g_sAndroidEmulator & ":", $COLOR_ERROR)
				SetLog($File, $COLOR_ERROR)
				SetError(1, @extended, False)
			EndIf
			Return False
		EndIf
	Next
	Local $sPreferredADB = FindPreferredAdbPath()

	If Not $bCheckOnly Then
		; update global variables
		$g_sAndroidPath = $__BlueStacks_Path
		$g_sAndroidProgramPath = $__BlueStacks_Path & $frontend_exe
		$g_sAndroidAdbPath = $sPreferredADB
		$g_sAndroidVersion = $__BlueStacks5_Version
		ConfigureSharedFolderBlueStacks5() ; something like D:\ProgramData\BlueStacks\Engine\UserData\SharedFolder\
		WinGetAndroidHandle()
	EndIf

	Return True
EndFunc   ;==>InitBlueStacks5X

Func ConfigureSharedFolderBlueStacks5($iMode = 0, $bSetLog = Default)
	If $bSetLog = Default Then $bSetLog = True
	Local $bResult = False
	Local $__BlueStacks5_ProgramData = RegRead($g_sHKLM & "\SOFTWARE\BlueStacks_nxt\", "UserDefinedDir")
	Local $__BlueStacks5_InstanceConf = FileReadToArray($__BlueStacks5_ProgramData & "\Engine\" & $g_sAndroidInstance & "\" & $g_sAndroidInstance & ".bstk")
	Local $iLineCount = @extended

	Switch $iMode
		Case 0 ; check that shared folder is configured in VM
			For $i = 0 To $iLineCount - 1
				If StringInStr($__BlueStacks5_InstanceConf[$i], "BstSharedFolder") Then
					Local $aPath = StringRegExp($__BlueStacks5_InstanceConf[$i], "hostPath=(.+)writable", $STR_REGEXPARRAYMATCH)
					If IsArray($aPath) And Not @error Then
						Local $path = StringStripWS((StringReplace($aPath[0], '"', '')), $STR_STRIPTRAILING)
						If StringRight($path, 1) <> "\" Then $path &= "\"
						$g_sAndroidPicturesHostPath = $path
						$bResult = True
						$g_bAndroidSharedFolderAvailable = True
						$g_sAndroidPicturesPath = "/mnt/windows/BstSharedFolder/"
						SetDebugLog("g_sAndroidPicturesHostPath = " & $g_sAndroidPicturesHostPath)
						SetDebugLog("g_sAndroidPicturesPath = " & $g_sAndroidPicturesPath)
					EndIf
				EndIf
			Next
			If Not $bResult Then ;set default value
				$g_sAndroidPicturesHostPath = "C:\ProgramData\BlueStacks_nxt\Engine\UserData\SharedFolder\"
				$g_sAndroidPicturesPath = "/mnt/windows/BstSharedFolder/"
				SetDebugLog("g_sAndroidPicturesHostPath = " & $g_sAndroidPicturesHostPath)
				SetDebugLog("g_sAndroidPicturesPath = " & $g_sAndroidPicturesPath)
				$bResult = True
			EndIf
		Case 1 ; create missing shared folder
		Case 2 ; Configure VM and add missing shared folder
	EndSwitch

	Return SetError(0, 0, $bResult)
EndFunc   ;==>ConfigureSharedFolderBlueStacks5

Func InitBlueStacks5($bCheckOnly = False)
	Local $bInstalled = InitBlueStacks5X($bCheckOnly, True)
	If $bInstalled And StringInStr($__BlueStacks5_Version, "5.") <> 1 Then
		SetLog("BlueStacks 5 supported version 5.x not found", $COLOR_ERROR)
		SetError(1, @extended, False)
		Return False
	EndIf

	Local $__BlueStacks5_ProgramData = RegRead($g_sHKLM & "\SOFTWARE\BlueStacks_nxt\", "UserDefinedDir")
	Local $__Bluestacks5Conf = FileReadToArray($__BlueStacks5_ProgramData & "\bluestacks.conf")
	Local $iLineCount = @extended

	For $i = 0 To $iLineCount - 1
		If StringInStr($__Bluestacks5Conf[$i], "bst.instance." & $g_sAndroidInstance & ".") Then
			Local $propkey = StringReplace($__Bluestacks5Conf[$i], "bst.instance." & $g_sAndroidInstance & ".", "")
			Local $aProperty = StringSplit($propkey, "=", $STR_NOCOUNT)
			If IsArray($aProperty) And UBound($aProperty) = 2 Then
				If StringRegExp($aProperty[0], "^(adb_port|display_name|dpi|fb_height|fb_width|graphics_renderer)$") Then SetDebugLog($propkey)
				If StringInStr($aProperty[0], "adb_port") Then
					Local $port = StringReplace($aProperty[1], '"', '')
					$g_sAndroidAdbDevice = "127.0.0.1:" & $port
				EndIf
			EndIf
		EndIf
	Next

	If $bInstalled And Not $bCheckOnly Then
		$__VBoxManage_Path = $__BlueStacks_Path & "BstkVMMgr.exe"
		Local $bsNow = GetVersionNormalized($__BlueStacks5_Version)
		If $bsNow > GetVersionNormalized("5.0") Then
			; Modern BlueStacks 5 exposes screencap, input and property commands through the normal ADB
			; shell. The inherited bstk/su wrapper is a BlueStacks 2/4 path; current builds may accept
			; it and then close without output, which falsely looks like a boot failure and reboots CoC.
			$g_sAndroidAdbShellOptions = ""

			; Keep the stdin minitouch transport used by the BlueStacks adapter.
			$g_iAndroidAdbMinitouchMode = 1
		EndIf
	EndIf

	Return $bInstalled
EndFunc   ;==>InitBlueStacks5

Func GetBlueStacks5BackgroundMode()
	#cs
		If 9600 <= @OSBuild Then
			Return $g_iAndroidBackgroundModeDirectX
		Else
	#ce
	; check if BlueStacks 5 is running in OpenGL mode
	Local $__BlueStacks5_ProgramData = RegRead($g_sHKLM & "\SOFTWARE\BlueStacks_nxt\", "UserDefinedDir")
	Local $__Bluestacks5Conf = FileReadToArray($__BlueStacks5_ProgramData & "\bluestacks.conf")
	Local $iLineCount = @extended
	Local $GlRenderMode = "dx"
	For $i = 0 To $iLineCount - 1
		If StringInStr($__Bluestacks5Conf[$i], "bst.instance." & $g_sAndroidInstance & ".graphics_renderer") Then
			$GlRenderMode = StringRegExp($__Bluestacks5Conf[$i], '=\"(.+)\"', $STR_REGEXPARRAYMATCH)
			ExitLoop
		EndIf
	Next

	If IsArray($GlRenderMode) Then
		SetDebugLog("GlRenderMode = " & $GlRenderMode[0])
		Switch $GlRenderMode[0]
			Case "dx"
				; DirectX
				Return $g_iAndroidBackgroundModeDirectX
			Case "gl"
				; OpenGL
				Return $g_iAndroidBackgroundModeOpenGL
			Case "vlcn"
				; Current BlueStacks Vulkan renderer still uses the proven ADB screencap transport.
				SetDebugLog("BlueStacks5 Vulkan render mode uses ADB screencap for Background Mode")
				Return $g_iAndroidBackgroundModeOpenGL
			Case Else
				SetLog($g_sAndroidEmulator & " unsupported render mode " & $GlRenderMode, $COLOR_WARNING)
				Return 0
		EndSwitch
	EndIf
	;EndIf
EndFunc   ;==>GetBlueStacks5BackgroundMode

Func RestartBlueStacks5CoC()
	If Not $g_bRunState Then Return False
	Local $cmdOutput
	If Not InitAndroid() Then Return False
	If WinGetAndroidHandle() = 0 Then Return False
	$cmdOutput = AndroidAdbSendShellCommand("am start -W -n " & $g_sAndroidGamePackage & "/" & $g_sAndroidGameClass, 60000) ; timeout of 1 Minute ; disabled -S due to long wait after 2017 Dec. Update
	SetLog("Please wait for CoC restart......", $COLOR_INFO) ; Let user know we need time...
	Return True
EndFunc   ;==>RestartBlueStacks5CoC

Func CheckScreenBlueStacks5($bSetLog = True)
	Local $__BlueStacks5_ProgramData = RegRead($g_sHKLM & "\SOFTWARE\BlueStacks_nxt\", "UserDefinedDir")
	Local $sConfigPath = $__BlueStacks5_ProgramData & "\bluestacks.conf"
	Local $__Bluestacks5Conf = FileReadToArray($sConfigPath)
	Local $iLineCount = @extended
	If $__BlueStacks5_ProgramData = "" Or Not IsArray($__Bluestacks5Conf) Then
		If $bSetLog Then SetLog("Cannot read BlueStacks configuration: " & $sConfigPath, $COLOR_ERROR)
		Return False
	EndIf

	Local $aiSearch = ["bst.instance." & $g_sAndroidInstance & ".fb_width", _
			"bst.instance." & $g_sAndroidInstance & ".fb_height", _
			'bst.instance.' & $g_sAndroidInstance & '.dpi="160"', _
			"bst.instance." & $g_sAndroidInstance & ".gl_win_height", _
			"bst.instance." & $g_sAndroidInstance & ".display_name"]

	Local $aiMustBe = ['"860"', _
			'"732"', _
			'"160"', _
			'"732"', _
			'"BlueStacks5']

	; BlueStacks 5.22's Qt presentation window can legitimately report a gl_win_height
	; smaller than the ADB framebuffer (730 for the verified 860x732 Pie64 surface).
	; Once the strict modern ADB surface contract is proven, gl_win_height is not an
	; input or capture dimension and must not trigger a destructive emulator reboot.
	Local $bModernAdbSurface = IsArray(GetBlueStacks5ModernAdbSurfacePosition())
	Local $bAdbAccessConfigured = False
	Local $abSettingFound[UBound($aiSearch)]
	If $bModernAdbSurface Then
		$abSettingFound[3] = True
		SetDebugLog("Modern BlueStacks5 ADB framebuffer verified; ignoring Qt gl_win_height")
	EndIf
	For $i = 0 To $iLineCount - 1
		If StringInStr($__Bluestacks5Conf[$i], "bst.enable_adb_access") Then _
				$bAdbAccessConfigured = StringInStr($__Bluestacks5Conf[$i], '="1"') > 0
		For $iSearch = 0 To UBound($aiSearch) - 1
			If $bModernAdbSurface And $iSearch = 3 Then ContinueLoop
			If StringInStr($__Bluestacks5Conf[$i], $aiSearch[$iSearch]) Then
				$abSettingFound[$iSearch] = True
				SetDebugLog($__Bluestacks5Conf[$i])
				If StringInStr($__Bluestacks5Conf[$i], $aiMustBe[$iSearch]) = 0 Then
					If $bSetLog = True Then SetLog("Please wait, Bot will configure your Bluestacks", $COLOR_ERROR)
					Return False
				EndIf
			EndIf
		Next
	Next
	For $iSearch = 0 To UBound($abSettingFound) - 1
		If Not $abSettingFound[$iSearch] Then
			If $bSetLog Then SetLog("BlueStacks setting is missing: " & $aiSearch[$iSearch], $COLOR_ERROR)
			Return False
		EndIf
	Next
	If Not $bAdbAccessConfigured Then
		If $bSetLog = True Then SetLog("Please wait, Bot will enable BlueStacks ADB access", $COLOR_ERROR)
		Return False
	EndIf
	Return True
EndFunc   ;==>CheckScreenBlueStacks5

Func SetScreenBlueStacks5()
	Local $__BlueStacks5_ProgramData = RegRead($g_sHKLM & "\SOFTWARE\BlueStacks_nxt\", "UserDefinedDir")
	Local $sConfigPath = $__BlueStacks5_ProgramData & "\bluestacks.conf"
	Local $__Bluestacks5Conf = FileReadToArray($sConfigPath)
	Local $iLineCount = @extended
	If $__BlueStacks5_ProgramData = "" Or Not IsArray($__Bluestacks5Conf) Then
		SetLog("Cannot read BlueStacks configuration: " & $sConfigPath, $COLOR_ERROR)
		Return False
	EndIf

	Local $aiSearch = ["bst.instance." & $g_sAndroidInstance & ".fb_width", _
			"bst.instance." & $g_sAndroidInstance & ".fb_height", _
			"bst.instance." & $g_sAndroidInstance & ".dpi", _
			"bst.instance." & $g_sAndroidInstance & ".gl_win_height", _
			"bst.instance." & $g_sAndroidInstance & ".show_sidebar", _
			"bst.instance." & $g_sAndroidInstance & ".display_name", _
			"bst.instance." & $g_sAndroidInstance & ".enable_fps_display", _
			"bst.instance." & $g_sAndroidInstance & ".google_login_popup_shown"]

	Local $aiMustBe = ['bst.instance.' & $g_sAndroidInstance & '.fb_width="860"', _
			'bst.instance.' & $g_sAndroidInstance & '.fb_height="732"', _
			'bst.instance.' & $g_sAndroidInstance & '.dpi="160"', _
			'bst.instance.' & $g_sAndroidInstance & '.gl_win_height="732"', _
			'bst.instance.' & $g_sAndroidInstance & '.show_sidebar="0"', _
			'bst.instance.' & $g_sAndroidInstance & '.display_name="BlueStacks5-' & $g_sAndroidInstance & '"', _
			'bst.instance.' & $g_sAndroidInstance & '.enable_fps_display="1"', _
			"bst.instance." & $g_sAndroidInstance & '.google_login_popup_shown="0"']

	Local $bAdbAccessFound = False
	Local $abSettingFound[UBound($aiSearch)]
	For $i = 0 To $iLineCount - 1
		If StringInStr($__Bluestacks5Conf[$i], "bst.enable_adb_access") Then
				$__Bluestacks5Conf[$i] = 'bst.enable_adb_access="1"'
			$bAdbAccessFound = True
		EndIf
		For $iSearch = 0 To UBound($aiSearch) - 1
			If StringInStr($__Bluestacks5Conf[$i], $aiSearch[$iSearch]) Then
				$__Bluestacks5Conf[$i] = $aiMustBe[$iSearch]
				$abSettingFound[$iSearch] = True
			EndIf
		Next
	Next
	For $iSearch = 0 To UBound($abSettingFound) - 1
		If Not $abSettingFound[$iSearch] Then _ArrayAdd($__Bluestacks5Conf, $aiMustBe[$iSearch])
	Next
	If Not $bAdbAccessFound Then _ArrayAdd($__Bluestacks5Conf, 'bst.enable_adb_access="1"')
	If _FileWriteFromArray($sConfigPath, $__Bluestacks5Conf) = 0 Then
		SetLog("Cannot update BlueStacks configuration: " & $sConfigPath, $COLOR_ERROR)
		Return False
	EndIf
	Return True
EndFunc   ;==>SetScreenBlueStacks5

Func ConfigBlueStacks5WindowManager()
	If Not $g_bRunState Then Return
	Local $cmdOutput
	; shell wm density 160
	; shell wm size 860x732
	; shell reboot

	; Reset Window Manager size
	$cmdOutput = AndroidAdbSendShellCommand("wm size reset", Default, Default, False)

	; Set expected dpi
	$cmdOutput = AndroidAdbSendShellCommand("wm density 160", Default, Default, False)

	; Set font size to normal
	AndroidSetFontSizeNormal()
EndFunc   ;==>ConfigBlueStacks5WindowManager

Func RebootBlueStacks5SetScreen($bOpenAndroid = True)

	If Not InitAndroid() Then Return False

	ConfigBlueStacks5WindowManager()

	; Close Android
	CloseAndroid("RebootBlueStacks5SetScreen")
	If _Sleep(1000) Then Return False

	SetScreenAndroid()
	If Not $g_bRunState Then Return False

	If $bOpenAndroid Then
		; Start Android
		OpenAndroid(True)
	EndIf

	Return True

EndFunc   ;==>RebootBlueStacks5SetScreen

Func GetBlueStacks5RunningInstance($bStrictCheck = True)
	WinGetAndroidHandle()
	Local $a[2] = [$g_hAndroidWindow, ""]
	If $g_hAndroidWindow <> 0 Then Return $a
	If $bStrictCheck Then Return False
	Local $WinTitleMatchMode = Opt("WinTitleMatchMode", -3) ; in recent 2.3.x can be also "BlueStacks App Player"
	Local $h = WinGetHandle("Bluestacks App Player", "") ; Need fixing as BS2 Emulator can have that title when configured in registry
	If @error = 0 Then
		$a[0] = $h
	EndIf
	Opt("WinTitleMatchMode", $WinTitleMatchMode)
	Return $a
EndFunc   ;==>GetBlueStacks5RunningInstance

Func BlueStacks5BotStartEvent()
	Return AndroidCloseSystemBar()
EndFunc   ;==>BlueStacks5BotStartEvent

Func BlueStacks5BotStopEvent()
	Return AndroidOpenSystemBar()
EndFunc   ;==>BlueStacks5BotStopEvent

Func GetBlueStacks5SvcPid()
	; find process PID
	Local $PID = ProcessExists2("HD-Service.exe")
	Return $PID
EndFunc   ;==>GetBlueStacks5SvcPid

Func CloseBlueStacks5()

	Local $bOops = False

	If Not InitAndroid() Then Return

	If Not CloseUnsupportedBlueStacksX(False) Then
		; BlueStacks 5 supports multiple instance
		; Current BlueStacks 5 instances run in HD-Player.exe. Match both the exact
		; executable path and quoted --instance argument before terminating it so a
		; frozen modern Qt shell can be restarted without touching another account.
		Local $iPlayerPid = ProcessExists2($__BlueStacks_Path & "HD-Player.exe", GetBlueStacks5ProgramParameter(), 1, 1)
		If $iPlayerPid Then
			ShellExecute(@WindowsDir & "\System32\taskkill.exe", " -f -t -pid " & $iPlayerPid, "", Default, @SW_HIDE)
			If _Sleep(1000) Then Return ; Give OS time to work
		EndIf

		; Keep inherited service/frontend fallbacks for older BlueStacks 5 layouts.
		Local $aFiles = ["HD-Frontend.exe", "HD-Plus-Service.exe", "HD-Service.exe"]

		Local $bError = False
		For $sFile In $aFiles
			Local $PID
			$PID = ProcessExists2($sFile, $g_sAndroidInstance)
			If $PID Then
				ShellExecute(@WindowsDir & "\System32\taskkill.exe", " -f -t -pid " & $PID, "", Default, @SW_HIDE)
				If _Sleep(1000) Then Return ; Give OS time to work
			EndIf
		Next
		If $iPlayerPid And ProcessExists($iPlayerPid) Then SetLog($g_sAndroidEmulator & " failed to kill HD-Player.exe for instance " & $g_sAndroidInstance, $COLOR_ERROR)
		If _Sleep(1000) Then Return ; Give OS time to work
		For $sFile In $aFiles
			Local $PID
			$PID = ProcessExists2($sFile, $g_sAndroidInstance)
			If $PID Then
				SetLog($g_sAndroidEmulator & " failed to kill " & $sFile, $COLOR_ERROR)
			EndIf
		Next

		; also close vm
		CloseVboxAndroidSvc()
	Else
		SetDebugLog("Closing BlueStacks: " & $__BlueStacks_Path & "HD-Quit.exe")
		RunWait($__BlueStacks_Path & "HD-Quit.exe")
		If @error <> 0 Then SetLog($g_sAndroidEmulator & " failed to quit", $COLOR_ERROR)
	EndIf

	If _Sleep(2000) Then Return ; wait a bit

	If $bOops Then
		SetError(1, @extended, -1)
	EndIf

EndFunc   ;==>CloseBlueStacks5

Func BlueStacks5AdjustClickCoordinates(ByRef $x, ByRef $y)
	$x = Round(32767.0 / $g_iAndroidClientWidth * $x)
	$y = Round(32767.0 / $g_iAndroidClientHeight * $y)
EndFunc   ;==>BlueStacks5AdjustClickCoordinates

Func CloseUnsupportedBlueStacksX($bClose = True)
	Local $WinTitleMatchMode = Opt("WinTitleMatchMode", -3) ; in recent 2.3.x can be also "BlueStacks App Player"
	Local $sPartnerExePath = RegRead($g_sHKLM & "\SOFTWARE\BlueStacks\Config\", "PartnerExePath")
	If IsArray(ControlGetPos("Bluestacks App Player", "", "")) Or ($sPartnerExePath And ProcessExists2($sPartnerExePath)) Then ; $g_avAndroidAppConfig[1][4]
		Opt("WinTitleMatchMode", $WinTitleMatchMode)
		; Offical "Bluestacks App Player" v2.0 not supported because it changes the Android Screen!!!
		If $bClose = True Then
			SetLog($g_sProductName & " doesn't work with " & $g_sAndroidEmulator & " App Player", $COLOR_ERROR)
			SetLog("Please let " & $g_sProductName & " start " & $g_sAndroidEmulator & " automatically", $COLOR_INFO)
			RebootBlueStacks5SetScreen(False)
		EndIf
		Return True
	EndIf
	Opt("WinTitleMatchMode", $WinTitleMatchMode)
	Return False
EndFunc   ;==>CloseUnsupportedBlueStacksX
