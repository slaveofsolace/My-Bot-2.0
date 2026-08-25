#NoTrayIcon
#AutoIt3Wrapper_UseX64=n
#pragma compile(Icon, "Images\MyBot.ico")
#pragma compile(ProductName, My Bot 2.0)
#pragma compile(FileDescription, My Bot 2.0)
#pragma compile(ProductVersion, 2.0.0)
#pragma compile(FileVersion, 2.0.0)
#pragma compile(Out, My Bot 2.0.exe)

#include <Crypt.au3>
#include <FileConstants.au3>
#include <GUIConstantsEx.au3>
#include <Misc.au3>
#include <MsgBoxConstants.au3>
#include <StringConstants.au3>
#include <WinAPIGdi.au3>
#include <WindowsConstants.au3>
#include "COCBot\functions\Other\Base64.au3"

Opt("MustDeclareVars", 1)
Opt("GUIOnEventMode", 1)

Global Const $g_sLauncherTitle = "My Bot 2.0"
Global Const $g_sControlCenterUrl = "http://127.0.0.1:8765/"
Global Const $g_sControllerPath = @ScriptDir & "\MyBot.run.MiniGui.exe"
Global Const $g_sBinaryProvenancePath = @ScriptDir & "\config\binary-provenance.json"
Global Const $g_sHostPath = @ScriptDir & "\MyBot.run.exe"
Global Const $g_sHostConfigPath = $g_sHostPath & ".config"
Global Const $g_sEngineProbeConfigPath = @ScriptDir & "\MyBot.run.EngineProbe.exe.config"
Global Const $g_sEngineMarkerPath = @ScriptDir & "\MyBot.run.txt"
Global Const $g_sEnginePath = @ScriptDir & "\lib\MyBot.run.dll"
Global Const $g_sUserDataRoot = _LauncherRuntimeLocalAppDataDir() & "\My Bot 2.0"
Global Const $g_sProfilesRoot = $g_sUserDataRoot & "\Profiles"
Global Const $g_sProfilesIniPath = $g_sProfilesRoot & "\profile.ini"
Global Const $g_sFirstRunProfile = "MyVillage"
; Match only the reviewed Mini build's own product title.  The inherited engine version remains
; v8.2.0, but the rebuilt controller intentionally presents the My Bot 2.0 product/version title.
Global Const $g_sControllerTitlePattern = "^My Bot 2\.0 Mini v2\.0\.0(?: \([A-Za-z0-9_. -]{1,64}\))?$"
Global Const $g_iDockGap = 8
Global Const $g_iDockWaitMs = 600000
Global Const $g_iDockTransitionPollMs = 1000
Global Const $g_iDockStablePollMs = 5000
Global Const $g_iErrorAlreadyExists = 183
Global Const $g_sRecoveryLogPath = $g_sUserDataRoot & "\launcher-recovery.log"
Global Const $g_sPlannerServiceName = "my-bot-control-center"
Global Const $g_sPlannerScriptPath = @ScriptDir & "\tools\planner_ui.py"
Global Const $g_sPlannerOwnershipSchema = "my-bot-planner-owner-v1"
Global Const $g_sPlannerOwnershipReceipt = $g_sUserDataRoot & "\planner-owner-v1.json"
Global Const $g_sEngineInitOwnershipSchema = "engine-init-supervisor-v1"
Global Const $g_sEngineInitCancelSchema = "engine-init-cancel-v1"
Global Const $g_sEngineInitOwnershipReceipt = $g_sUserDataRoot & "\engine-init-owner-v1.json"
Global Const $g_sEngineInitCancelPath = @ScriptDir & "\config\engine-init-cancel.local.json"
Global Const $g_sControlStatusPath = @ScriptDir & "\config\control-status.local.json"
Global Const $g_sEngineSupervisorTokenEnv = "MYBOT_ENGINE_INIT_TOKEN"
Global Const $g_sEngineSupervisorLauncherPidEnv = "MYBOT_ENGINE_INIT_LAUNCHER_PID"
Global Const $g_sEngineSupervisorLauncherCreatedEnv = "MYBOT_ENGINE_INIT_LAUNCHER_CREATED"
Global Const $g_sLaunchOnlyEmulatorOwnershipSchema = "my-bot-launch-only-emulator-owner-v1"
Global Const $g_sLaunchOnlyEmulatorOwnershipReceipt = $g_sUserDataRoot & "\launch-only-emulator-owner-v1.json"
Global Const $g_iEngineInitEnterTimeoutMs = 10000
Global Const $g_iEngineInitPoolStallTimeoutMs = 90000
Global Const $g_iEngineInitPostReturnTimeoutMs = 15000
Global Const $g_iEngineInitAbsoluteTimeoutMs = 120000
Global Const $g_iEngineInitActivePollMs = 250
Global Const $g_iPlannerHealthResolveTimeoutMs = 200
Global Const $g_iPlannerHealthConnectTimeoutMs = 300
Global Const $g_iPlannerHealthSendTimeoutMs = 300
Global Const $g_iPlannerHealthReceiveTimeoutMs = 500
Global Const $g_iLauncherErrorTimeoutSec = 15
Global Const $g_iLauncherOwnedAdbChildLimit = 64
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
Global $g_bPlannerHealthComError = False
Global $g_bEngineSupervisorArmed = False
Global $g_sEngineSupervisorToken = ""
Global $g_sEngineSupervisorLauncherCreated = ""
Global $g_iEngineSupervisorControllerPid = 0
Global $g_sEngineSupervisorControllerCreated = ""
Global $g_sEngineSupervisorLastPhase = ""
Global $g_iEngineSupervisorLastPhaseRank = -1
Global $g_iEngineSupervisorLastSequence = -1
Global $g_hEngineSupervisorPhaseTimer = 0
Global $g_hEngineSupervisorAbsoluteTimer = 0
Global $g_hEngineSupervisorPostReturnTimer = 0
Global $g_bEngineSupervisorPrepared = False
Global $g_sEngineSupervisorLastNotice = ""
Global $g_iEngineSupervisorBackendPid = 0
Global $g_sEngineSupervisorBackendCreated = ""
Global $g_bEngineSupervisorAbortAttempted = False
Global $g_bEngineSupervisorFailureLatched = False
Global $g_sEngineSupervisorFailure = ""
Global $g_iLauncherOwnedBackendPid = 0
Global $g_sLauncherOwnedBackendCreated = ""
Global $g_bLauncherOwnedBackendAmbiguous = False
Global $g_bLauncherOwnedAdbTrackingIncomplete = False
Global $g_aLauncherOwnedAdbChildren[1][4]

Func _LauncherRuntimeLocalAppDataDir()
	If EnvGet("MYBOT_RUN_PYTHON_INTEGRATION") <> "1" Then Return @LocalAppDataDir
	Local $sTestRoot = _LauncherCanonicalDirectory(EnvGet("MYBOT_INSTALL_TEST_ROOT"))
	Local $sLocalRoot = _LauncherCanonicalDirectory(EnvGet("LOCALAPPDATA"))
	If @error Or $sTestRoot = "" Or $sLocalRoot = "" Then Return @ScriptDir & "\.invalid-test-localappdata"
	Local $sPrefix = StringLower($sTestRoot & "\")
	If StringLeft(StringLower($sLocalRoot), StringLen($sPrefix)) <> $sPrefix Then Return @ScriptDir & "\.invalid-test-localappdata"
	Return $sLocalRoot
EndFunc   ;==>_LauncherRuntimeLocalAppDataDir

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
	_RecoveryLog("engine init supervision not armed: existing controller was not launched by this launcher; pid=" & $iExistingControllerPid)
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
		_RecoveryLog("engine init supervision not armed: controller was launched by another dock keeper; pid=" & WinGetProcess($hController))
		_DockWhenReady($hController, WinGetProcess($hController), 15000)
		_OpenControlCenter()
	EndIf
	Exit 0
EndIf

; The inherited image engine supports this exact upstream controller as its genuine remote GUI.
; The controller remains visible and functional; it launches the full backend with /guipid.
Local $sLaunchProfile = _PrepareUserProfile()
If @error Or $sLaunchProfile = "" Then
	_ShowError("My Bot 2.0 could not prepare its per-user profile." & @CRLF & @CRLF & _
		"Check this folder and its profile.ini, then try again:" & @CRLF & $g_sProfilesRoot)
	Exit 9
EndIf
Local $sEngineSupervisorError = ""
If Not _EngineSupervisorPrepareLaunch($sEngineSupervisorError) Then
	_ShowError("My Bot 2.0 could not prepare safe engine startup supervision." & @CRLF & @CRLF & $sEngineSupervisorError)
	Exit 10
EndIf
Local $iControllerPid = Run('"' & $g_sControllerPath & '" ' & _BuildControllerArguments($sLaunchProfile), @ScriptDir, @SW_SHOWNORMAL)
Local $iControllerLaunchError = @error
_EngineSupervisorClearLaunchEnvironment()
If $iControllerLaunchError Or $iControllerPid <= 0 Then
	_EngineSupervisorDisarm("controller launch failed before ownership could be bound")
	_ShowError("My Bot 2.0 could not start its native controller." & @CRLF & @CRLF & _
		"Approve the Windows administrator prompt and try again.")
	Exit 3
EndIf
If Not _EngineSupervisorBindController($iControllerPid) Then
	_EngineSupervisorDisarm("launched controller identity could not be bound")
	_ShowError("My Bot 2.0 started its native controller, but could not bind safe engine startup supervision." & @CRLF & @CRLF & _
		"The controller was left running for inspection; do not press Start again until recovery is complete.")
	Exit 11
EndIf
; Keep controller creation identity outside supervisor state: Poll may disarm itself in the narrow
; window where the controller exits, but automatic descendant cleanup still needs this immutable proof.
Local $sLauncherOwnedControllerCreated = $g_sEngineSupervisorControllerCreated

$hController = _WaitForControllerWindow($iControllerPid, 60000)
If Not $hController Then
	; Mini normally launches the backend and planner before its window is ready. Never close only the
	; parent here and orphan that descendant chain. The explicit Recovery route re-proves and closes
	; planner, backend, and controller in ownership order.
	_EngineSupervisorDisarm("controller window readiness timed out; controller stack left intact for recovery")
	_ShowError("The native controller did not become ready, so its process stack was left intact for exact-ownership recovery." & @CRLF & @CRLF & _
		"Do not press Start. Run My Bot 2.0 Recovery before launching again, then inspect:" & @CRLF & $g_sRecoveryLogPath)
	Exit 4
EndIf

; The invisible launcher remains a lightweight dock keeper. It follows later BlueStacks shell
; resizes and exits with the exact Mini controller, without reparenting or commanding either app.
_ShowControlStrip($hController)
_DockWhenReady($hController, $iControllerPid, $g_iDockWaitMs)
_KeepDocked($hController, $iControllerPid)
; Mini owns the backend and planner, but a forced or abnormal controller close can orphan either
; child after its window disappears. Close only the backend identity captured while it was still an
; exact child of this launcher's controller; never reuse the broader operator-invoked Recovery here.
Local $bControllerStackRecovered = _RecoverExitedOwnedControllerStack($iControllerPid, _
		$sLauncherOwnedControllerCreated, $g_iLauncherOwnedBackendPid, $g_sLauncherOwnedBackendCreated)
_EngineSupervisorDisarm("owned controller exited")
If Not $bControllerStackRecovered Then
	_RecoveryLog("controller-exit recovery remained incomplete")
	Exit 12
EndIf
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
	; The exact pinned Mini recognizes this profile as its only positional value and forwards it to
	; the backend. Its package-local Profiles view is the installer-verified junction to user data.
	; Managed installations recover both native surfaces to the primary display; direct native
	; launches retain the upstream saved multi-monitor placement contract.
	Return $sProfile & " /nowatchdog /primarywindow"
EndFunc   ;==>_BuildControllerArguments

Func _ProfilesRootToken($sPath)
	Local $sCanonical = _LauncherCanonicalDirectory($sPath)
	If @error Or $sCanonical = "" Then Return ""
	Local $sEncoded = _Base64Encode(StringToBinary($sCanonical, 4), 0)
	$sEncoded = StringReplace(StringReplace($sEncoded, @CR, ""), @LF, "")
	$sEncoded = StringReplace(StringReplace($sEncoded, "+", "-"), "/", "_")
	Return StringRegExpReplace($sEncoded, "=+$", "")
EndFunc   ;==>_ProfilesRootToken

Func _RecoverBotStack()
	_RecoveryLog("recovery requested")
	_CloseOwnedAutoItErrorDialogs()
	; Prove and close the planner while its recorded backend parent is still alive. Closing the
	; backend first would discard the strongest part of the ownership chain and make a stale PID look
	; more trustworthy than it is.
	Local $bPlannerClosed = _CloseOwnedPlannerService()
	; ADB shell/exec clients are direct backend children. Snapshot their exact process identity before
	; closing Mini or the backend, because Windows retains them as orphans if the backend exits before
	; its normal pipe teardown. The emulator-owned ADB server is not a backend child and is never selected.
	Local $aOwnedAdbChildren = _SnapshotOwnedAdbChildren()
	_CloseExactPathProcesses("MyBot.run.MiniGui.exe", $g_sControllerPath)
	_CloseExactPathProcesses("MyBot.run.exe", $g_sHostPath)
	Local $bAdbChildrenClosed = _CloseVerifiedAdbChildren($aOwnedAdbChildren)
	Local $bLaunchOnlyEmulatorClosed = _CloseOwnedLaunchOnlyEmulator(False)
	_CloseExactPathProcesses("My Bot 2.0.exe", @ScriptFullPath, @AutoItPID)

	Local $hController = _FindControllerWindow()
	Local $bControllerClosed = Not $hController
	Local $bBackendClosed = _CountExactPathProcesses("MyBot.run.exe", $g_sHostPath) = 0
	Local $bRecovered = $bControllerClosed And $bBackendClosed And $bPlannerClosed And $bAdbChildrenClosed And $bLaunchOnlyEmulatorClosed
	_RecoveryLog("recovery completed; controller_closed=" & $bControllerClosed & "; backend_closed=" & $bBackendClosed & "; planner_closed=" & $bPlannerClosed & "; adb_children_closed=" & $bAdbChildrenClosed & "; launch_only_emulator_closed=" & $bLaunchOnlyEmulatorClosed)
	Return $bRecovered
EndFunc   ;==>_RecoverBotStack

Func _SnapshotOwnedAdbChildren($iExpectedBackendPid = 0, $sExpectedBackendCreated = "")
	Local $aChildren[1][4]
	Local $iCount = 0
	Local $aBackendProcesses = ProcessList("MyBot.run.exe")
	Local $aAdbNames[2] = ["HD-Adb.exe", "adb.exe"]
	For $iBackend = 1 To $aBackendProcesses[0][0]
		Local $iBackendPid = $aBackendProcesses[$iBackend][1]
		If $iExpectedBackendPid > 0 And $iBackendPid <> $iExpectedBackendPid Then ContinueLoop
		If StringLower(_ProcessImagePath($iBackendPid)) <> StringLower($g_sHostPath) Then ContinueLoop
		If $iExpectedBackendPid > 0 And _ProcessCreationId($iBackendPid) <> $sExpectedBackendCreated Then ContinueLoop
		For $iName = 0 To UBound($aAdbNames) - 1
			Local $aProcesses = ProcessList($aAdbNames[$iName])
			For $i = 1 To $aProcesses[0][0]
				Local $iPid = $aProcesses[$i][1]
				If _ProcessParentPid($iPid) <> $iBackendPid Then ContinueLoop
				Local $sCreated = _ProcessCreationId($iPid)
				If Not StringRegExp($sCreated, "^[0-9a-f]{16}$") Then
					_RecoveryLog("refused unprovable backend ADB child; pid=" & $iPid & "; parent=" & $iBackendPid)
					ContinueLoop
				EndIf
				$iCount += 1
				ReDim $aChildren[$iCount + 1][4]
				$aChildren[$iCount][0] = $iPid
				$aChildren[$iCount][1] = $sCreated
				$aChildren[$iCount][2] = $aAdbNames[$iName]
				$aChildren[$iCount][3] = $iBackendPid
			Next
		Next
	Next
	$aChildren[0][0] = $iCount
	Return $aChildren
EndFunc   ;==>_SnapshotOwnedAdbChildren

; Automatic recovery may close only children captured while the exact backend generation was alive.
; A matching numeric PPID observed after backend exit is only an ambiguity signal: Windows can reuse
; that PID for an unrelated parent, so the launcher must never adopt or close the new process.
Func _HasUncapturedAdbChildForRecordedBackend($iBackendPid)
	Local $aAdbNames[2] = ["HD-Adb.exe", "adb.exe"]
	For $iName = 0 To UBound($aAdbNames) - 1
		Local $aProcesses = ProcessList($aAdbNames[$iName])
		For $i = 1 To $aProcesses[0][0]
			Local $iPid = $aProcesses[$i][1]
			If _ProcessParentPid($iPid) <> $iBackendPid Then ContinueLoop
			Local $sCreated = _ProcessCreationId($iPid)
			Local $bCaptured = False
			For $iKnown = 1 To $g_aLauncherOwnedAdbChildren[0][0]
				If $g_aLauncherOwnedAdbChildren[$iKnown][0] = $iPid And _
						$g_aLauncherOwnedAdbChildren[$iKnown][1] = $sCreated Then
					$bCaptured = True
					ExitLoop
				EndIf
			Next
			If $bCaptured Then ContinueLoop
			_RecoveryLog("refused uncaptured ADB child after backend exit; pid=" & $iPid & "; recorded_parent=" & $iBackendPid)
			Return True
		Next
	Next
	Return False
EndFunc   ;==>_HasUncapturedAdbChildForRecordedBackend

Func _PruneLauncherOwnedAdbChildren()
	Local $aPruned[1][4]
	Local $iCount = 0
	For $i = 1 To $g_aLauncherOwnedAdbChildren[0][0]
		Local $iPid = $g_aLauncherOwnedAdbChildren[$i][0]
		Local $sCreated = $g_aLauncherOwnedAdbChildren[$i][1]
		Local $sName = $g_aLauncherOwnedAdbChildren[$i][2]
		Local $iBackendPid = $g_aLauncherOwnedAdbChildren[$i][3]
		If Not ProcessExists($iPid) Then ContinueLoop
		If _ProcessCreationId($iPid) <> $sCreated Or _ProcessParentPid($iPid) <> $iBackendPid Or _
				Not _ProcessNameMatches($iPid, $sName) Then ContinueLoop
		$iCount += 1
		ReDim $aPruned[$iCount + 1][4]
		For $iField = 0 To 3
			$aPruned[$iCount][$iField] = $g_aLauncherOwnedAdbChildren[$i][$iField]
		Next
	Next
	$aPruned[0][0] = $iCount
	$g_aLauncherOwnedAdbChildren = $aPruned
EndFunc   ;==>_PruneLauncherOwnedAdbChildren

Func _RememberLauncherOwnedAdbChildren(ByRef $aObserved)
	_PruneLauncherOwnedAdbChildren()
	If $g_bLauncherOwnedAdbTrackingIncomplete Then Return False
	For $i = 1 To $aObserved[0][0]
		Local $bKnown = False
		For $iKnown = 1 To $g_aLauncherOwnedAdbChildren[0][0]
			If $g_aLauncherOwnedAdbChildren[$iKnown][0] = $aObserved[$i][0] And _
					$g_aLauncherOwnedAdbChildren[$iKnown][1] = $aObserved[$i][1] Then
				$bKnown = True
				ExitLoop
			EndIf
		Next
		If $bKnown Then ContinueLoop
		Local $iNext = $g_aLauncherOwnedAdbChildren[0][0] + 1
		If $iNext > $g_iLauncherOwnedAdbChildLimit Then
			$g_bLauncherOwnedAdbTrackingIncomplete = True
			_RecoveryLog("launcher-owned ADB identity limit reached; automatic recovery disabled")
			Return False
		EndIf
		ReDim $g_aLauncherOwnedAdbChildren[$iNext + 1][4]
		For $iField = 0 To 3
			$g_aLauncherOwnedAdbChildren[$iNext][$iField] = $aObserved[$i][$iField]
		Next
		$g_aLauncherOwnedAdbChildren[0][0] = $iNext
	Next
	Return True
EndFunc   ;==>_RememberLauncherOwnedAdbChildren

Func _RefreshLauncherOwnedAdbChildren($iBackendPid, $sBackendCreated)
	Local $aObserved = _SnapshotOwnedAdbChildren($iBackendPid, $sBackendCreated)
	Return _RememberLauncherOwnedAdbChildren($aObserved)
EndFunc   ;==>_RefreshLauncherOwnedAdbChildren

; Capture one exact backend while the owned controller is alive. The identity is latched as PID plus
; creation FILETIME and refreshed only after the previous generation exits. Automatic cleanup uses
; this record; path-only enumeration remains limited to the explicit operator Recovery command.
Func _RefreshLauncherOwnedBackend($iControllerPid)
	If $iControllerPid <= 0 Or Not ProcessExists($iControllerPid) Then Return False
	If $g_bLauncherOwnedBackendAmbiguous Then Return False
	Local $aBackends = ProcessList("MyBot.run.exe")
	Local $iMatchPid = 0
	Local $sMatchCreated = ""
	Local $iMatchCount = 0
	For $i = 1 To $aBackends[0][0]
		Local $iPid = $aBackends[$i][1]
		If StringLower(_ProcessImagePath($iPid)) <> StringLower($g_sHostPath) Or _ProcessParentPid($iPid) <> $iControllerPid Then ContinueLoop
		Local $sCreated = _ProcessCreationId($iPid)
		If Not StringRegExp($sCreated, "^[0-9a-f]{16}$") Then ContinueLoop
		$iMatchCount += 1
		If $iMatchCount > 1 Then
			$g_bLauncherOwnedBackendAmbiguous = True
			_RecoveryLog("refused ambiguous owned backend capture; controller_pid=" & $iControllerPid)
			Return False
		EndIf
		$iMatchPid = $iPid
		$sMatchCreated = $sCreated
	Next
	If $iMatchCount = 0 Then
		If $g_iLauncherOwnedBackendPid > 0 And ProcessExists($g_iLauncherOwnedBackendPid) Then
			$g_bLauncherOwnedBackendAmbiguous = True
			_RecoveryLog("latched changed launcher-owned backend identity; controller_pid=" & $iControllerPid)
			Return False
		EndIf
		; Retain the last exact generation and every captured ADB child. They remain the only safe
		; authority if the backend exits before its controller and leaves pipe clients orphaned.
		Return True
	EndIf
	If $g_iLauncherOwnedBackendPid = $iMatchPid And $g_sLauncherOwnedBackendCreated = $sMatchCreated Then
		Return _RefreshLauncherOwnedAdbChildren($iMatchPid, $sMatchCreated)
	EndIf
	If $g_iLauncherOwnedBackendPid > 0 And ProcessExists($g_iLauncherOwnedBackendPid) Then
		$g_bLauncherOwnedBackendAmbiguous = True
		_RecoveryLog("refused overlapping launcher-owned backend generations; controller_pid=" & $iControllerPid)
		Return False
	EndIf
	If $iMatchPid > 0 Then
		$g_iLauncherOwnedBackendPid = $iMatchPid
		$g_sLauncherOwnedBackendCreated = $sMatchCreated
		If Not _RefreshLauncherOwnedAdbChildren($iMatchPid, $sMatchCreated) Then Return False
		_RecoveryLog("captured launcher-owned backend; controller_pid=" & $iControllerPid & "; backend_pid=" & $iMatchPid)
	EndIf
	Return True
EndFunc   ;==>_RefreshLauncherOwnedBackend

Func _CloseVerifiedLauncherBackend($iControllerPid, $iBackendPid, $sBackendCreated)
	If Not ProcessExists($iBackendPid) Then Return True
	If _ProcessCreationId($iBackendPid) <> $sBackendCreated Or _
			StringLower(_ProcessImagePath($iBackendPid)) <> StringLower($g_sHostPath) Or _
			_ProcessParentPid($iBackendPid) <> $iControllerPid Then
		_RecoveryLog("refused changed launcher-owned backend; pid=" & $iBackendPid)
		Return False
	EndIf
	_RecoveryLog("closing verified launcher-owned backend; pid=" & $iBackendPid)
	If Not ProcessClose($iBackendPid) And ProcessExists($iBackendPid) Then Return False
	Return ProcessWaitClose($iBackendPid, 2) Or Not ProcessExists($iBackendPid)
EndFunc   ;==>_CloseVerifiedLauncherBackend

Func _RecoverExitedOwnedControllerStack($iControllerPid, $sControllerCreated, $iBackendPid, $sBackendCreated)
	_RecoveryLog("owned controller-exit recovery requested; controller_pid=" & $iControllerPid & "; backend_pid=" & $iBackendPid)
	If $iControllerPid <= 0 Or ProcessExists($iControllerPid) Or Not StringRegExp($sControllerCreated, "^[0-9a-f]{16}$") Then Return False
	If $g_bLauncherOwnedBackendAmbiguous Then Return False
	If $g_bLauncherOwnedAdbTrackingIncomplete Then Return False
	If $iBackendPid <= 0 Then
		; No backend was captured. A remaining receipt is ambiguous and is left for explicit Recovery.
		Return Not FileExists($g_sPlannerOwnershipReceipt) And $g_aLauncherOwnedAdbChildren[0][0] = 0
	EndIf
	If Not StringRegExp($sBackendCreated, "^[0-9a-f]{16}$") Then Return False
	If ProcessExists($iBackendPid) And (_ProcessCreationId($iBackendPid) <> $sBackendCreated Or _
			StringLower(_ProcessImagePath($iBackendPid)) <> StringLower($g_sHostPath) Or _
			_ProcessParentPid($iBackendPid) <> $iControllerPid) Then Return False
	If ProcessExists($iBackendPid) And Not _RefreshLauncherOwnedAdbChildren($iBackendPid, $sBackendCreated) Then Return False
	_PruneLauncherOwnedAdbChildren()
	Local $bUncapturedAdbChild = False
	If Not ProcessExists($iBackendPid) Then $bUncapturedAdbChild = _HasUncapturedAdbChildForRecordedBackend($iBackendPid)
	Local $aOwnedAdbChildren = $g_aLauncherOwnedAdbChildren
	Local $bPlannerClosed = _CloseOwnedPlannerService($iBackendPid, $sBackendCreated)
	Local $bBackendClosed = _CloseVerifiedLauncherBackend($iControllerPid, $iBackendPid, $sBackendCreated)
	; The live backend may create a final pipe child after the last exact snapshot but before it
	; exits. Once the backend is confirmed gone, detect that child as an unresolved ambiguity;
	; never adopt it from the now-reusable numeric parent PID.
	If $bBackendClosed And Not ProcessExists($iBackendPid) Then
		If _HasUncapturedAdbChildForRecordedBackend($iBackendPid) Then $bUncapturedAdbChild = True
	EndIf
	Local $bAdbChildrenClosed = _CloseVerifiedAdbChildren($aOwnedAdbChildren)
	Local $bLaunchOnlyEmulatorClosed = _CloseOwnedLaunchOnlyEmulator(True)
	Local $bRecovered = $bPlannerClosed And $bBackendClosed And $bAdbChildrenClosed And $bLaunchOnlyEmulatorClosed And Not $bUncapturedAdbChild
	_RecoveryLog("owned controller-exit recovery completed; backend_closed=" & $bBackendClosed & "; planner_closed=" & $bPlannerClosed & "; adb_children_closed=" & $bAdbChildrenClosed & "; launch_only_emulator_closed=" & $bLaunchOnlyEmulatorClosed & "; uncaptured_adb_child=" & $bUncapturedAdbChild)
	Return $bRecovered
EndFunc   ;==>_RecoverExitedOwnedControllerStack

Func _ProcessNameMatches($iPid, $sExpectedName)
	Local $aProcesses = ProcessList($sExpectedName)
	For $i = 1 To $aProcesses[0][0]
		If $aProcesses[$i][1] = $iPid Then Return True
	Next
	Return False
EndFunc   ;==>_ProcessNameMatches

Func _CloseVerifiedAdbChildren(ByRef $aChildren)
	Local $bAllClosed = True
	For $i = 1 To $aChildren[0][0]
		Local $iPid = $aChildren[$i][0]
		If Not ProcessExists($iPid) Then ContinueLoop
		Local $sCreated = $aChildren[$i][1]
		Local $sName = $aChildren[$i][2]
		Local $iBackendPid = $aChildren[$i][3]
		If _ProcessCreationId($iPid) <> $sCreated Or _ProcessParentPid($iPid) <> $iBackendPid Or Not _ProcessNameMatches($iPid, $sName) Then
			_RecoveryLog("refused changed backend ADB child; pid=" & $iPid & "; recorded_parent=" & $iBackendPid)
			$bAllClosed = False
			ContinueLoop
		EndIf
		_RecoveryLog("closing verified backend ADB child; name=" & $sName & "; pid=" & $iPid & "; parent=" & $iBackendPid)
		Local $bCloseIssued = ProcessClose($iPid)
		If (Not $bCloseIssued And ProcessExists($iPid)) Or Not ProcessWaitClose($iPid, 2) Then
			_RecoveryLog("verified backend ADB child remained alive; name=" & $sName & "; pid=" & $iPid)
			$bAllClosed = False
		EndIf
	Next
	Return $bAllClosed
EndFunc   ;==>_CloseVerifiedAdbChildren

Func _ReadLaunchOnlyEmulatorOwnershipReceipt()
	If Not FileExists($g_sLaunchOnlyEmulatorOwnershipReceipt) Then Return ""
	If Not _LaunchOnlyEmulatorReceiptPathSafe(True) Then Return ""
	Local $sReceipt = FileRead($g_sLaunchOnlyEmulatorOwnershipReceipt)
	If @error Or StringLen($sReceipt) > 4096 Then Return ""
	Return $sReceipt
EndFunc   ;==>_ReadLaunchOnlyEmulatorOwnershipReceipt

Func _LaunchOnlyEmulatorReceiptPathSafe($bRequireReceipt = False)
	Local $aParent = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $g_sUserDataRoot)
	If @error Or Not IsArray($aParent) Or $aParent[0] = 0xFFFFFFFF Then Return False
	If BitAND($aParent[0], 0x10) = 0 Or BitAND($aParent[0], 0x400) <> 0 Then Return False
	If Not FileExists($g_sLaunchOnlyEmulatorOwnershipReceipt) Then Return Not $bRequireReceipt
	Local $aReceipt = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $g_sLaunchOnlyEmulatorOwnershipReceipt)
	If @error Or Not IsArray($aReceipt) Or $aReceipt[0] = 0xFFFFFFFF Then Return False
	Return BitAND($aReceipt[0], 0x10) = 0 And BitAND($aReceipt[0], 0x400) = 0
EndFunc   ;==>_LaunchOnlyEmulatorReceiptPathSafe

Func _FindLaunchOnlyBlueStacksWindow($iPlayerPid, $sInstance)
	If $iPlayerPid <= 0 Or Not StringRegExp($sInstance, "^[A-Za-z0-9._-]{1,64}$") Then Return 0
	Local $sTitle = "BlueStacks5-" & $sInstance
	Local $aWindows = WinList($sTitle)
	Local $hFound = 0
	For $i = 1 To $aWindows[0][0]
		If $aWindows[$i][0] <> $sTitle Then ContinueLoop
		Local $hWindow = $aWindows[$i][1]
		If WinGetProcess($hWindow) <> $iPlayerPid Then ContinueLoop
		If Not StringRegExp(_WindowClassName($hWindow), "^Qt[0-9]+QWindowIcon$") Then ContinueLoop
		If Not StringRegExp(StringLower(_ProcessImagePath($iPlayerPid)), "\\hd-player\.exe$") Then ContinueLoop
		If $hFound Then Return SetError(2, 0, 0)
		$hFound = $hWindow
	Next
	Return $hFound
EndFunc   ;==>_FindLaunchOnlyBlueStacksWindow

Func _LaunchOnlyEmulatorReceiptConsumedSafely($sCurrentReceipt, $iPlayerPid)
	Return $sCurrentReceipt = "" And $iPlayerPid > 0 And Not ProcessExists($iPlayerPid)
EndFunc   ;==>_LaunchOnlyEmulatorReceiptConsumedSafely

Func _CloseOwnedLaunchOnlyEmulator($bRequireCurrentLauncher)
	Local $sReceipt = _ReadLaunchOnlyEmulatorOwnershipReceipt()
	If $sReceipt = "" Then Return True
	If _PlannerReceiptString($sReceipt, "schema") <> $g_sLaunchOnlyEmulatorOwnershipSchema Then
		_RecoveryLog("refused launch-only emulator: invalid ownership receipt schema")
		Return False
	EndIf
	Local $iPlayerPid = _PlannerReceiptInt($sReceipt, "player_pid")
	Local $sPlayerCreated = _PlannerReceiptString($sReceipt, "player_created")
	Local $sInstance = _LauncherReceiptIdentifier($sReceipt, "instance")
	If $iPlayerPid <= 0 Or Not StringRegExp($sPlayerCreated, "^[0-9a-f]{16}$") Or _
			Not StringRegExp($sInstance, "^[A-Za-z0-9._-]{1,64}$") Then
		_RecoveryLog("refused launch-only emulator: malformed ownership receipt")
		Return False
	EndIf
	If $bRequireCurrentLauncher Then
		Local $iLauncherPid = _PlannerReceiptInt($sReceipt, "launcher_pid")
		Local $sLauncherCreated = _PlannerReceiptString($sReceipt, "launcher_created")
		If $iLauncherPid <> @AutoItPID Or $sLauncherCreated <> _ProcessCreationId(@AutoItPID) Then
			_RecoveryLog("refused launch-only emulator: receipt belongs to another launcher generation")
			Return False
		EndIf
	EndIf
	If Not ProcessExists($iPlayerPid) Then
		_RecoveryLog("removing stale launch-only emulator receipt; pid=" & $iPlayerPid)
		Return FileDelete($g_sLaunchOnlyEmulatorOwnershipReceipt) = 1 Or Not FileExists($g_sLaunchOnlyEmulatorOwnershipReceipt)
	EndIf
	If _ProcessCreationId($iPlayerPid) <> $sPlayerCreated Or _
			Not StringRegExp(StringLower(_ProcessImagePath($iPlayerPid)), "\\hd-player\.exe$") Then
		_RecoveryLog("refused launch-only emulator: player identity changed; pid=" & $iPlayerPid)
		Return False
	EndIf
	Local $sCommand = _ProcessCommandLine($iPlayerPid)
	Local $bCommandMatches = $sCommand <> "" And StringInStr($sCommand, "--instance") > 0 And StringInStr($sCommand, $sInstance) > 0
	Local $hWindow = _FindLaunchOnlyBlueStacksWindow($iPlayerPid, $sInstance)
	If @error = 2 Or (Not $hWindow And Not $bCommandMatches) Then
		_RecoveryLog("refused launch-only emulator: no exact instance window or command line proof; pid=" & $iPlayerPid & "; instance=" & $sInstance)
		Return False
	EndIf
	Local $sCurrentReceipt = _ReadLaunchOnlyEmulatorOwnershipReceipt()
	If $sCurrentReceipt <> $sReceipt Then
		If _LaunchOnlyEmulatorReceiptConsumedSafely($sCurrentReceipt, $iPlayerPid) Then
			_RecoveryLog("launch-only owned BlueStacks player already closed by concurrent recovery; pid=" & $iPlayerPid & "; instance=" & $sInstance)
			Return True
		EndIf
		Return False
	EndIf
	If Not ProcessExists($iPlayerPid) Then
		_RecoveryLog("removing stale launch-only emulator receipt after concurrent close; pid=" & $iPlayerPid)
		Return FileDelete($g_sLaunchOnlyEmulatorOwnershipReceipt) = 1 Or Not FileExists($g_sLaunchOnlyEmulatorOwnershipReceipt)
	EndIf
	If _ProcessCreationId($iPlayerPid) <> $sPlayerCreated Then Return False
	_RecoveryLog("closing launch-only owned BlueStacks player; pid=" & $iPlayerPid & "; instance=" & $sInstance)
	ShellExecute(@WindowsDir & "\System32\taskkill.exe", " -f -t -pid " & $iPlayerPid, "", Default, @SW_HIDE)
	For $i = 1 To 40
		If Not ProcessExists($iPlayerPid) Then ExitLoop
		Sleep(250)
	Next
	If ProcessExists($iPlayerPid) Then
		_RecoveryLog("launch-only owned BlueStacks player remained alive; pid=" & $iPlayerPid)
		Return False
	EndIf
	Local $sFinalReceipt = _ReadLaunchOnlyEmulatorOwnershipReceipt()
	If $sFinalReceipt <> $sReceipt Then
		If _LaunchOnlyEmulatorReceiptConsumedSafely($sFinalReceipt, $iPlayerPid) Then Return True
		Return False
	EndIf
	If Not _LaunchOnlyEmulatorReceiptPathSafe(True) Then Return False
	Return FileDelete($g_sLaunchOnlyEmulatorOwnershipReceipt) = 1 Or Not FileExists($g_sLaunchOnlyEmulatorOwnershipReceipt)
EndFunc   ;==>_CloseOwnedLaunchOnlyEmulator

Func _PlannerReceiptString($sReceipt, $sName)
	Local $aValue = StringRegExp($sReceipt, '"' & $sName & '"\s*:\s*"([A-Za-z0-9_-]+)"', $STR_REGEXPARRAYMATCH)
	If @error Or Not IsArray($aValue) Or UBound($aValue) <> 1 Then Return ""
	Return $aValue[0]
EndFunc   ;==>_PlannerReceiptString

Func _PlannerReceiptInt($sReceipt, $sName)
	Local $aValue = StringRegExp($sReceipt, '"' & $sName & '"\s*:\s*([0-9]+)', $STR_REGEXPARRAYMATCH)
	If @error Or Not IsArray($aValue) Or UBound($aValue) <> 1 Then Return 0
	Return Int($aValue[0])
EndFunc   ;==>_PlannerReceiptInt

Func _LauncherReceiptIdentifier($sReceipt, $sName)
	Local $aValue = StringRegExp($sReceipt, '"' & $sName & '"\s*:\s*"([A-Za-z0-9._-]{1,128})"', $STR_REGEXPARRAYMATCH)
	If @error Or Not IsArray($aValue) Or UBound($aValue) <> 1 Then Return ""
	Return $aValue[0]
EndFunc   ;==>_LauncherReceiptIdentifier

Func _EngineSupervisorRequestId($sJson, $sName)
	Local $aValue = StringRegExp($sJson, '"' & $sName & '"\s*:\s*"([A-Za-z0-9._-]{1,80})"', $STR_REGEXPARRAYMATCH)
	If @error Or Not IsArray($aValue) Or UBound($aValue) <> 1 Then Return ""
	Return $aValue[0]
EndFunc   ;==>_EngineSupervisorRequestId

Func _EngineSupervisorSequence($sJson)
	Local $aValue = StringRegExp($sJson, '"sequence"\s*:\s*([0-9]+)', $STR_REGEXPARRAYMATCH)
	If @error Or Not IsArray($aValue) Or UBound($aValue) <> 1 Then Return -1
	Return Int($aValue[0])
EndFunc   ;==>_EngineSupervisorSequence

Func _EngineSupervisorJsonString($sValue)
	Local $sText = String($sValue)
	$sText = StringReplace($sText, "\", "\\")
	$sText = StringReplace($sText, '"', '\"')
	$sText = StringReplace($sText, @CRLF, "\n")
	$sText = StringReplace($sText, @CR, "\n")
	$sText = StringReplace($sText, @LF, "\n")
	$sText = StringReplace($sText, @TAB, "\t")
	Return '"' & $sText & '"'
EndFunc   ;==>_EngineSupervisorJsonString

Func _EngineSupervisorWriteAbortStatus($sStartRequestId, $sReason, $sPhase, $iBackendPid)
	If Not _EngineSupervisorPathSafe($g_sControlStatusPath, False) Then Return False
	Local $sMessage = "Managed engine initialization failed"
	If $sPhase <> "" Then $sMessage &= " at " & $sPhase
	If $sReason <> "" Then $sMessage &= ": " & $sReason
	Local $sTemporary = $g_sControlStatusPath & "." & @AutoItPID & ".tmp"
	Local $sJson = "{"
	$sJson &= _EngineSupervisorJsonString("schema_version") & ":1,"
	$sJson &= _EngineSupervisorJsonString("product_name") & ":" & _EngineSupervisorJsonString("My Bot 2.0") & ","
	$sJson &= _EngineSupervisorJsonString("product_version") & ":" & _EngineSupervisorJsonString("2.0.0") & ","
	$sJson &= _EngineSupervisorJsonString("engine_version") & ":" & _EngineSupervisorJsonString("8.2.0") & ","
	$sJson &= _EngineSupervisorJsonString("state") & ":" & _EngineSupervisorJsonString("failed") & ","
	$sJson &= _EngineSupervisorJsonString("run_state") & ":false,"
	$sJson &= _EngineSupervisorJsonString("paused") & ":false,"
	$sJson &= _EngineSupervisorJsonString("authorization_ready") & ":true,"
	$sJson &= _EngineSupervisorJsonString("engine_available") & ":false,"
	$sJson &= _EngineSupervisorJsonString("engine_probe_state") & ":" & _EngineSupervisorJsonString("failed") & ","
	$sJson &= _EngineSupervisorJsonString("recognition_available") & ":false,"
	$sJson &= _EngineSupervisorJsonString("recognition_error") & ":" & _EngineSupervisorJsonString($sMessage) & ","
	$sJson &= _EngineSupervisorJsonString("plan_active") & ":false,"
	$sJson &= _EngineSupervisorJsonString("plan_message") & ":" & _EngineSupervisorJsonString($sMessage) & ","
	$sJson &= _EngineSupervisorJsonString("session_id") & ":" & _EngineSupervisorJsonString("") & ","
	$sJson &= _EngineSupervisorJsonString("profile") & ":" & _EngineSupervisorJsonString("") & ","
	$sJson &= _EngineSupervisorJsonString("emulator") & ":" & _EngineSupervisorJsonString("") & ","
	$sJson &= _EngineSupervisorJsonString("instance") & ":" & _EngineSupervisorJsonString("") & ","
	$sJson &= _EngineSupervisorJsonString("emulator_attached") & ":false,"
	$sJson &= _EngineSupervisorJsonString("window_attached") & ":false,"
	$sJson &= _EngineSupervisorJsonString("adb_ready") & ":false,"
	$sJson &= _EngineSupervisorJsonString("game_ready") & ":false,"
	$sJson &= _EngineSupervisorJsonString("bot_pid") & ":" & Int($iBackendPid) & ","
	$sJson &= _EngineSupervisorJsonString("last_command_id") & ":" & _EngineSupervisorJsonString($sStartRequestId) & ","
	$sJson &= _EngineSupervisorJsonString("last_command") & ":" & _EngineSupervisorJsonString($sStartRequestId = "" ? "check-engine" : "start") & ","
	$sJson &= _EngineSupervisorJsonString("last_outcome") & ":" & _EngineSupervisorJsonString("failed") & ","
	$sJson &= _EngineSupervisorJsonString("last_command_message") & ":" & _EngineSupervisorJsonString($sMessage) & ","
	$sJson &= _EngineSupervisorJsonString("message") & ":" & _EngineSupervisorJsonString($sMessage)
	$sJson &= "}"
	Local $hFile = FileOpen($sTemporary, BitOR($FO_OVERWRITE, $FO_CREATEPATH, $FO_UTF8_NOBOM))
	If $hFile = -1 Then Return False
	Local $bWritten = FileWrite($hFile, $sJson & @LF)
	FileFlush($hFile)
	FileClose($hFile)
	If Not $bWritten Then
		FileDelete($sTemporary)
		Return False
	EndIf
	If Not FileMove($sTemporary, $g_sControlStatusPath, $FC_OVERWRITE) Then
		FileDelete($sTemporary)
		Return False
	EndIf
	Return True
EndFunc   ;==>_EngineSupervisorWriteAbortStatus

Func _ReadPlannerOwnershipReceipt()
	If Not FileExists($g_sPlannerOwnershipReceipt) Then Return ""
	If Not _PlannerReceiptPathSafe(True) Then Return ""
	Local $sReceipt = FileRead($g_sPlannerOwnershipReceipt)
	If @error Or StringLen($sReceipt) > 4096 Then Return ""
	Return $sReceipt
EndFunc   ;==>_ReadPlannerOwnershipReceipt

Func _PlannerReceiptPathSafe($bRequireReceipt = False)
	Local $aParent = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $g_sUserDataRoot)
	If @error Or Not IsArray($aParent) Or $aParent[0] = 0xFFFFFFFF Then Return False
	If BitAND($aParent[0], 0x10) = 0 Or BitAND($aParent[0], 0x400) <> 0 Then Return False
	If Not FileExists($g_sPlannerOwnershipReceipt) Then Return Not $bRequireReceipt
	Local $aReceipt = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $g_sPlannerOwnershipReceipt)
	If @error Or Not IsArray($aReceipt) Or $aReceipt[0] = 0xFFFFFFFF Then Return False
	Return BitAND($aReceipt[0], 0x10) = 0 And BitAND($aReceipt[0], 0x400) = 0
EndFunc   ;==>_PlannerReceiptPathSafe

Func _StringSha256($sText)
	Local $vHash = _Crypt_HashData(StringToBinary(String($sText), 4), $CALG_SHA_256)
	If @error Or Not IsBinary($vHash) Then Return ""
	Return StringLower(StringTrimLeft(String($vHash), 2))
EndFunc   ;==>_StringSha256

Func _LauncherPathToken($sPath)
	Local $sEncoded = _Base64Encode(StringToBinary(String($sPath), 4), 0)
	If @error Then Return ""
	$sEncoded = StringReplace(StringReplace($sEncoded, @CR, ""), @LF, "")
	$sEncoded = StringReplace(StringReplace($sEncoded, "+", "-"), "/", "_")
	Return StringRegExpReplace($sEncoded, "=+$", "")
EndFunc   ;==>_LauncherPathToken

Func _ProcessCreationId($iPid)
	Local $aOpen = DllCall("kernel32.dll", "handle", "OpenProcess", "dword", 0x1000, "bool", False, "dword", $iPid)
	If @error Or Not IsArray($aOpen) Or Not $aOpen[0] Then Return ""
	Local $hProcess = $aOpen[0]
	Local $tCreated = DllStructCreate("dword Low;dword High")
	Local $tExit = DllStructCreate("dword Low;dword High")
	Local $tKernel = DllStructCreate("dword Low;dword High")
	Local $tUser = DllStructCreate("dword Low;dword High")
	Local $aTimes = DllCall("kernel32.dll", "bool", "GetProcessTimes", "handle", $hProcess, "struct*", $tCreated, _
		"struct*", $tExit, "struct*", $tKernel, "struct*", $tUser)
	DllCall("kernel32.dll", "bool", "CloseHandle", "handle", $hProcess)
	If @error Or Not IsArray($aTimes) Or Not $aTimes[0] Then Return ""
	Return StringLower(Hex(DllStructGetData($tCreated, "High"), 8) & Hex(DllStructGetData($tCreated, "Low"), 8))
EndFunc   ;==>_ProcessCreationId

Func _ProcessParentPid($iPid)
	Local $aSnapshot = DllCall("kernel32.dll", "handle", "CreateToolhelp32Snapshot", "dword", 0x2, "dword", 0)
	If @error Or Not IsArray($aSnapshot) Or $aSnapshot[0] = -1 Then Return 0
	Local $hSnapshot = $aSnapshot[0]
	Local $tEntry = DllStructCreate("dword Size;dword Usage;dword ProcessId;ptr DefaultHeap;dword ModuleId;dword Threads;" & _
		"dword ParentProcessId;long PriClassBase;dword Flags;wchar ExeFile[260]")
	DllStructSetData($tEntry, "Size", DllStructGetSize($tEntry))
	Local $aNext = DllCall("kernel32.dll", "bool", "Process32FirstW", "handle", $hSnapshot, "struct*", $tEntry)
	While Not @error And IsArray($aNext) And $aNext[0]
		If DllStructGetData($tEntry, "ProcessId") = $iPid Then
			Local $iParent = DllStructGetData($tEntry, "ParentProcessId")
			DllCall("kernel32.dll", "bool", "CloseHandle", "handle", $hSnapshot)
			Return $iParent
		EndIf
		$aNext = DllCall("kernel32.dll", "bool", "Process32NextW", "handle", $hSnapshot, "struct*", $tEntry)
	WEnd
	DllCall("kernel32.dll", "bool", "CloseHandle", "handle", $hSnapshot)
	Return 0
EndFunc   ;==>_ProcessParentPid

Func _ProcessCommandLine($iPid)
	Local $oWmi = ObjGet("winmgmts:{impersonationLevel=impersonate}!\\.\root\cimv2")
	If @error Or Not IsObj($oWmi) Then Return ""
	Local $oProcesses = $oWmi.ExecQuery("SELECT CommandLine FROM Win32_Process WHERE ProcessId = " & Int($iPid))
	If @error Or Not IsObj($oProcesses) Then Return ""
	For $oProcess In $oProcesses
		Return String($oProcess.CommandLine)
	Next
	Return ""
EndFunc   ;==>_ProcessCommandLine

Func _EngineSupervisorNewToken()
	Local $tEntropy = DllStructCreate("byte[32]")
	Local $aRandom = DllCall("bcrypt.dll", "long", "BCryptGenRandom", "ptr", 0, "struct*", $tEntropy, "ulong", 32, "ulong", 0x2)
	If @error Or Not IsArray($aRandom) Or $aRandom[0] <> 0 Then Return ""
	Return StringLower(Hex(DllStructGetData($tEntropy, 1)))
EndFunc   ;==>_EngineSupervisorNewToken

Func _EngineSupervisorPathSafe($sPath, $bRequireFile = False)
	Local $sParent = StringLeft($sPath, StringInStr($sPath, "\", 0, -1) - 1)
	If $sParent = "" Then Return False
	Local $aParent = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $sParent)
	If @error Or Not IsArray($aParent) Or $aParent[0] = 0xFFFFFFFF Then Return False
	If BitAND($aParent[0], 0x10) = 0 Or BitAND($aParent[0], 0x400) <> 0 Then Return False
	If Not FileExists($sPath) Then Return Not $bRequireFile
	Local $aFile = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $sPath)
	If @error Or Not IsArray($aFile) Or $aFile[0] = 0xFFFFFFFF Then Return False
	Return BitAND($aFile[0], 0x10) = 0 And BitAND($aFile[0], 0x400) = 0
EndFunc   ;==>_EngineSupervisorPathSafe

Func _EngineSupervisorDeleteSafeFile($sPath)
	If Not FileExists($sPath) Then Return True
	If Not _EngineSupervisorPathSafe($sPath, True) Then Return False
	Return FileDelete($sPath) = 1 Or Not FileExists($sPath)
EndFunc   ;==>_EngineSupervisorDeleteSafeFile

Func _EngineSupervisorPrepareLaunch(ByRef $sError)
	$sError = ""
	If Not FileExists($g_sUserDataRoot) And Not DirCreate($g_sUserDataRoot) Then
		$sError = "The per-user data directory could not be created."
		Return False
	EndIf
	If Not _EngineSupervisorPathSafe($g_sEngineInitOwnershipReceipt, False) Or _
			Not _EngineSupervisorPathSafe($g_sEngineInitCancelPath, False) Then
		$sError = "An engine supervision path is redirected or unsafe."
		Return False
	EndIf
	If Not _EngineSupervisorDeleteSafeFile($g_sEngineInitOwnershipReceipt) Or _
			Not _EngineSupervisorDeleteSafeFile($g_sEngineInitCancelPath) Then
		$sError = "A stale engine supervision file could not be removed safely."
		Return False
	EndIf
	Local $sToken = _EngineSupervisorNewToken()
	Local $sCreated = _ProcessCreationId(@AutoItPID)
	If Not StringRegExp($sToken, "^[0-9a-f]{64}$") Or Not StringRegExp($sCreated, "^[0-9a-f]{16}$") Then
		$sError = "A secure launch token or launcher creation identity could not be generated."
		Return False
	EndIf
	If Not EnvSet($g_sEngineSupervisorTokenEnv, $sToken) Or _
			Not EnvSet($g_sEngineSupervisorLauncherPidEnv, String(@AutoItPID)) Or _
			Not EnvSet($g_sEngineSupervisorLauncherCreatedEnv, $sCreated) Then
		_EngineSupervisorClearLaunchEnvironment()
		$sError = "The one-time engine supervision environment could not be set."
		Return False
	EndIf
	$g_bEngineSupervisorArmed = True
	$g_sEngineSupervisorToken = $sToken
	$g_sEngineSupervisorLauncherCreated = $sCreated
	$g_iEngineSupervisorControllerPid = 0
	$g_sEngineSupervisorControllerCreated = ""
	$g_sEngineSupervisorLastPhase = ""
	$g_iEngineSupervisorLastPhaseRank = -1
	$g_iEngineSupervisorLastSequence = -1
	$g_hEngineSupervisorPhaseTimer = TimerInit()
	$g_hEngineSupervisorAbsoluteTimer = 0
	$g_hEngineSupervisorPostReturnTimer = 0
	$g_bEngineSupervisorPrepared = False
	$g_sEngineSupervisorLastNotice = ""
	$g_iEngineSupervisorBackendPid = 0
	$g_sEngineSupervisorBackendCreated = ""
	$g_bEngineSupervisorAbortAttempted = False
	$g_bEngineSupervisorFailureLatched = False
	$g_sEngineSupervisorFailure = ""
	_RecoveryLog("engine init supervision armed; launcher_pid=" & @AutoItPID)
	Return True
EndFunc   ;==>_EngineSupervisorPrepareLaunch

Func _EngineSupervisorClearLaunchEnvironment()
	EnvSet($g_sEngineSupervisorTokenEnv, "")
	EnvSet($g_sEngineSupervisorLauncherPidEnv, "")
	EnvSet($g_sEngineSupervisorLauncherCreatedEnv, "")
EndFunc   ;==>_EngineSupervisorClearLaunchEnvironment

Func _EngineSupervisorBindController($iControllerPid)
	If Not $g_bEngineSupervisorArmed Or $iControllerPid <= 0 Then Return False
	Local $hTimer = TimerInit()
	Do
		If Not ProcessExists($iControllerPid) Then Return False
		Local $sImage = _ProcessImagePath($iControllerPid)
		Local $iParentPid = _ProcessParentPid($iControllerPid)
		Local $sCreated = _ProcessCreationId($iControllerPid)
		If StringLower($sImage) = StringLower($g_sControllerPath) And $iParentPid = @AutoItPID And _
				StringRegExp($sCreated, "^[0-9a-f]{16}$") Then
			$g_iEngineSupervisorControllerPid = $iControllerPid
			$g_sEngineSupervisorControllerCreated = $sCreated
			Return True
		EndIf
		Sleep(50)
	Until TimerDiff($hTimer) >= 2000
	Return False
EndFunc   ;==>_EngineSupervisorBindController

Func _EngineSupervisorDisarm($sReason)
	_EngineSupervisorClearLaunchEnvironment()
	If $sReason <> "" Then _RecoveryLog("engine init supervision disarmed: " & $sReason)
	$g_bEngineSupervisorArmed = False
	$g_sEngineSupervisorToken = ""
	$g_sEngineSupervisorLauncherCreated = ""
	$g_iEngineSupervisorControllerPid = 0
	$g_sEngineSupervisorControllerCreated = ""
	$g_sEngineSupervisorLastPhase = ""
	$g_iEngineSupervisorLastPhaseRank = -1
	$g_iEngineSupervisorLastSequence = -1
	$g_hEngineSupervisorPhaseTimer = 0
	$g_hEngineSupervisorAbsoluteTimer = 0
	$g_hEngineSupervisorPostReturnTimer = 0
	$g_bEngineSupervisorPrepared = False
	$g_sEngineSupervisorLastNotice = ""
	$g_iEngineSupervisorBackendPid = 0
	$g_sEngineSupervisorBackendCreated = ""
	$g_bEngineSupervisorAbortAttempted = False
	$g_bEngineSupervisorFailureLatched = False
	$g_sEngineSupervisorFailure = ""
EndFunc   ;==>_EngineSupervisorDisarm

; A single launcher token and controller binding live for the exact controller lifetime. Each
; backend process is a separate initialization generation, so its phase/sequence clocks may begin
; again at zero without weakening the launcher/controller ownership proof.
Func _EngineSupervisorResetGeneration($iBackendPid, $sBackendCreated, $sReason = "")
	$g_iEngineSupervisorBackendPid = $iBackendPid
	$g_sEngineSupervisorBackendCreated = $sBackendCreated
	$g_sEngineSupervisorLastPhase = ""
	$g_iEngineSupervisorLastPhaseRank = -1
	$g_iEngineSupervisorLastSequence = -1
	$g_hEngineSupervisorPhaseTimer = TimerInit()
	$g_hEngineSupervisorAbsoluteTimer = 0
	$g_hEngineSupervisorPostReturnTimer = 0
	$g_bEngineSupervisorPrepared = False
	$g_sEngineSupervisorLastNotice = ""
	$g_bEngineSupervisorAbortAttempted = False
	$g_bEngineSupervisorFailureLatched = False
	$g_sEngineSupervisorFailure = ""
	If $sReason <> "" Then _RecoveryLog("engine init generation reset; reason=" & $sReason & "; backend_pid=" & $iBackendPid)
EndFunc   ;==>_EngineSupervisorResetGeneration

Func _EngineSupervisorBeginGeneration($sReceipt, $iBackendPid)
	Local $sBackendCreated = _PlannerReceiptString($sReceipt, "backend_created")
	If $iBackendPid = $g_iEngineSupervisorBackendPid And $sBackendCreated = $g_sEngineSupervisorBackendCreated Then Return False
	_EngineSupervisorResetGeneration($iBackendPid, $sBackendCreated)
	_RecoveryLog("engine init generation bound; backend_pid=" & $iBackendPid & "; backend_created=" & $sBackendCreated)
	Return True
EndFunc   ;==>_EngineSupervisorBeginGeneration

Func _EngineSupervisorRecordFailure($sReason)
	$g_bEngineSupervisorFailureLatched = True
	$g_sEngineSupervisorFailure = $sReason
	If $g_sEngineSupervisorLastNotice <> "durable-failure" Then _RecoveryLog("engine init supervisor durable failure; " & $sReason)
	$g_sEngineSupervisorLastNotice = "durable-failure"
	Return False
EndFunc   ;==>_EngineSupervisorRecordFailure

Func _EngineSupervisorReceiptPhaseRank($sPhase)
	Switch $sPhase
		Case "prepared"
			Return 0
		Case "pool-entered"
			Return 1
		Case "pool-returned"
			Return 2
		Case "max-entered"
			Return 3
		Case "max-returned"
			Return 4
		Case "android-entered"
			Return 5
		Case "android-returned"
			Return 6
		Case "gui-entered"
			Return 7
		Case "initialized"
			Return 8
		Case "failed"
			Return 9
	EndSwitch
	Return -1
EndFunc   ;==>_EngineSupervisorReceiptPhaseRank

Func _EngineSupervisorReceiptMatches($sReceipt, ByRef $iBackendPid, ByRef $sPhase, ByRef $sStartRequestId, ByRef $iSequence)
	$iBackendPid = 0
	$sPhase = ""
	$sStartRequestId = ""
	$iSequence = -1
	If _PlannerReceiptString($sReceipt, "schema") <> $g_sEngineInitOwnershipSchema Then Return False
	If Not StringRegExp($g_sEngineSupervisorToken, "^[0-9a-f]{64}$") Then Return False
	If _PlannerReceiptString($sReceipt, "token") <> $g_sEngineSupervisorToken Then Return False
	If _PlannerReceiptInt($sReceipt, "launcher_pid") <> @AutoItPID Then Return False
	If _PlannerReceiptString($sReceipt, "launcher_created") <> $g_sEngineSupervisorLauncherCreated Or _
			_ProcessCreationId(@AutoItPID) <> $g_sEngineSupervisorLauncherCreated Then Return False
	If _PlannerReceiptInt($sReceipt, "controller_pid") <> $g_iEngineSupervisorControllerPid Then Return False
	If _PlannerReceiptString($sReceipt, "controller_created") <> $g_sEngineSupervisorControllerCreated Or _
			_ProcessCreationId($g_iEngineSupervisorControllerPid) <> $g_sEngineSupervisorControllerCreated Then Return False
	If StringLower(_ProcessImagePath($g_iEngineSupervisorControllerPid)) <> StringLower($g_sControllerPath) Then Return False
	If _ProcessParentPid($g_iEngineSupervisorControllerPid) <> @AutoItPID Then Return False
	$iBackendPid = _PlannerReceiptInt($sReceipt, "backend_pid")
	If $iBackendPid <= 0 Or Not ProcessExists($iBackendPid) Then Return False
	Local $sBackendCreated = _ProcessCreationId($iBackendPid)
	If Not StringRegExp($sBackendCreated, "^[0-9a-f]{16}$") Or _
			_PlannerReceiptString($sReceipt, "backend_created") <> $sBackendCreated Then Return False
	If StringLower(_ProcessImagePath($iBackendPid)) <> StringLower($g_sHostPath) Then Return False
	If _PlannerReceiptInt($sReceipt, "parent_pid") <> $g_iEngineSupervisorControllerPid Or _
			_ProcessParentPid($iBackendPid) <> $g_iEngineSupervisorControllerPid Then Return False
	$sPhase = _PlannerReceiptString($sReceipt, "phase")
	Local $iPhaseRank = _EngineSupervisorReceiptPhaseRank($sPhase)
	If $iPhaseRank < 0 Then Return False
	$sStartRequestId = _EngineSupervisorRequestId($sReceipt, "start_request_id")
	If $sStartRequestId = "" Then Return False
	$iSequence = _EngineSupervisorSequence($sReceipt)
	If $sPhase = "failed" Then
		If $iSequence < 2 Or $iSequence > 10 Then Return False
	ElseIf $iSequence <> $iPhaseRank + 1 Then
		Return False
	EndIf
	Return True
EndFunc   ;==>_EngineSupervisorReceiptMatches

Func _EngineSupervisorReadReceipt(ByRef $sReceipt, ByRef $iBackendPid, ByRef $sPhase, ByRef $sStartRequestId, ByRef $iSequence)
	$sReceipt = ""
	$iBackendPid = 0
	$sPhase = ""
	$sStartRequestId = ""
	$iSequence = -1
	If Not FileExists($g_sEngineInitOwnershipReceipt) Then Return False
	If Not _EngineSupervisorPathSafe($g_sEngineInitOwnershipReceipt, True) Then Return False
	$sReceipt = FileRead($g_sEngineInitOwnershipReceipt)
	If @error Or StringLen($sReceipt) > 4096 Then Return False
	Return _EngineSupervisorReceiptMatches($sReceipt, $iBackendPid, $sPhase, $sStartRequestId, $iSequence)
EndFunc   ;==>_EngineSupervisorReadReceipt

Func _EngineSupervisorCancelMatches($sReceiptStartRequestId)
	If Not $g_bEngineSupervisorPrepared Or $sReceiptStartRequestId = "" Then Return False
	If Not FileExists($g_sEngineInitCancelPath) Or Not _EngineSupervisorPathSafe($g_sEngineInitCancelPath, True) Then Return False
	Local $sCancel = FileRead($g_sEngineInitCancelPath)
	If @error Or StringLen($sCancel) > 2048 Then Return False
	If _PlannerReceiptString($sCancel, "schema") <> $g_sEngineInitCancelSchema Then Return False
	If _PlannerReceiptString($sCancel, "token") <> $g_sEngineSupervisorToken Then Return False
	Local $sExpected = _EngineSupervisorRequestId($sCancel, "expected_start_request_id")
	Return $sExpected <> "" And $sExpected = $sReceiptStartRequestId
EndFunc   ;==>_EngineSupervisorCancelMatches

Func _EngineSupervisorFinalize($sReceipt, $sOutcome)
	If Not _EngineSupervisorPathSafe($g_sEngineInitOwnershipReceipt, True) Or FileRead($g_sEngineInitOwnershipReceipt) <> $sReceipt Then _
		Return _EngineSupervisorRecordFailure("initialized receipt changed before cleanup")
	Local $bReceiptRemoved = _EngineSupervisorDeleteSafeFile($g_sEngineInitOwnershipReceipt)
	Local $bCancelRemoved = _EngineSupervisorDeleteSafeFile($g_sEngineInitCancelPath)
	_RecoveryLog("engine init supervision finalized; outcome=" & $sOutcome & "; receipt_removed=" & $bReceiptRemoved & "; cancel_removed=" & $bCancelRemoved)
	If Not $bReceiptRemoved Or Not $bCancelRemoved Then Return _EngineSupervisorRecordFailure("initialized generation files could not be removed safely")
	_EngineSupervisorResetGeneration(0, "", $sOutcome)
	Return True
EndFunc   ;==>_EngineSupervisorFinalize

Func _EngineSupervisorAbort($sReceipt, $iBackendPid, $sReason)
	; Latch before any revalidation or close attempt. A failed ownership check or ProcessClose is a
	; durable, visible failure for this backend generation and can never trigger a second close.
	If $g_bEngineSupervisorAbortAttempted Then Return False
	$g_bEngineSupervisorAbortAttempted = True
	_RecoveryLog("engine init supervisor abort latched; backend_pid=" & $iBackendPid & "; reason=" & $sReason)
	; Re-read the exact receipt and re-prove every process identity immediately before ProcessClose.
	Local $sCurrent = "", $iCurrentBackend = 0, $sCurrentPhase = "", $sCurrentStartRequest = "", $iCurrentSequence = -1
	If Not _EngineSupervisorReadReceipt($sCurrent, $iCurrentBackend, $sCurrentPhase, $sCurrentStartRequest, $iCurrentSequence) Or _
			$sCurrent <> $sReceipt Or $iCurrentBackend <> $iBackendPid Then
		Return _EngineSupervisorRecordFailure("abort refused because exact backend ownership changed; reason=" & $sReason)
	EndIf
	_EngineSupervisorWriteAbortStatus($sCurrentStartRequest, $sReason, $sCurrentPhase, $iBackendPid)
	_RecoveryLog("engine init supervisor closing verified backend; pid=" & $iBackendPid & "; phase=" & $sCurrentPhase & "; reason=" & $sReason)
	Local $bCloseIssued = ProcessClose($iBackendPid)
	If Not $bCloseIssued And ProcessExists($iBackendPid) Then Return _EngineSupervisorRecordFailure("the single verified backend close attempt failed; pid=" & $iBackendPid)
	For $i = 1 To 100
		If Not ProcessExists($iBackendPid) Then ExitLoop
		Sleep(50)
	Next
	If ProcessExists($iBackendPid) Then Return _EngineSupervisorRecordFailure("backend remained alive after the single verified close attempt; pid=" & $iBackendPid)
	Local $bPlannerClosed = _CloseOwnedPlannerService()
	If Not _EngineSupervisorPathSafe($g_sEngineInitOwnershipReceipt, True) Or FileRead($g_sEngineInitOwnershipReceipt) <> $sCurrent Then _
		Return _EngineSupervisorRecordFailure("backend stopped but its ownership receipt changed before cleanup")
	Local $bReceiptRemoved = _EngineSupervisorDeleteSafeFile($g_sEngineInitOwnershipReceipt)
	Local $bCancelRemoved = _EngineSupervisorDeleteSafeFile($g_sEngineInitCancelPath)
	_RecoveryLog("engine init supervisor stopped retry; backend_gone=true; planner_closed=" & $bPlannerClosed & _
		"; receipt_removed=" & $bReceiptRemoved & "; cancel_removed=" & $bCancelRemoved)
	If Not $bPlannerClosed Or Not $bReceiptRemoved Or Not $bCancelRemoved Then _
		Return _EngineSupervisorRecordFailure("backend stopped but supervised cleanup was incomplete")
	; Keep the abort latch and generation identity until a different exact backend generation appears.
	; This prevents a stale receipt or PID reuse race from issuing another close, while the launcher
	; remains armed to supervise the same controller's next backend without replaying Start.
	Return True
EndFunc   ;==>_EngineSupervisorAbort

Func _EngineSupervisorPoll()
	If Not $g_bEngineSupervisorArmed Or $g_iEngineSupervisorControllerPid <= 0 Then Return False
	If Not ProcessExists($g_iEngineSupervisorControllerPid) Then
		_EngineSupervisorDisarm("owned controller exited")
		Return False
	EndIf
	Local $sReceipt = "", $iBackendPid = 0, $sPhase = "", $sStartRequestId = "", $iSequence = -1
	If Not _EngineSupervisorReadReceipt($sReceipt, $iBackendPid, $sPhase, $sStartRequestId, $iSequence) Then
		If FileExists($g_sEngineInitOwnershipReceipt) And $g_sEngineSupervisorLastNotice <> "invalid-receipt" Then
			_RecoveryLog("engine init supervisor ignored an invalid or foreign receipt")
			$g_sEngineSupervisorLastNotice = "invalid-receipt"
		EndIf
		Return False
	EndIf
	$g_sEngineSupervisorLastNotice = ""
	_EngineSupervisorBeginGeneration($sReceipt, $iBackendPid)
	; Cancellation or a prior abort remains authoritative over any late success from this generation.
	If $g_bEngineSupervisorAbortAttempted Or $g_bEngineSupervisorFailureLatched Then Return False
	Local $iPhaseRank = _EngineSupervisorReceiptPhaseRank($sPhase)
	If $g_iEngineSupervisorLastSequence >= 0 And $iSequence < $g_iEngineSupervisorLastSequence Then
		_RecoveryLog("engine init supervisor ignored sequence rollback; observed=" & $iSequence & "; accepted=" & $g_iEngineSupervisorLastSequence)
		Return False
	EndIf
	If $g_iEngineSupervisorLastPhaseRank >= 0 And $iPhaseRank < $g_iEngineSupervisorLastPhaseRank Then
		_RecoveryLog("engine init supervisor ignored phase rollback; observed=" & $sPhase & "; accepted=" & $g_sEngineSupervisorLastPhase)
		Return False
	EndIf
	If Not $g_bEngineSupervisorPrepared Then
		; Every accepted phase is written after prepared. Start the absolute clock at the first receipt
		; we observe, even if a fast transition meant the 1/5 second poll did not see prepared itself.
		$g_bEngineSupervisorPrepared = True
		$g_hEngineSupervisorAbsoluteTimer = TimerInit()
	EndIf
	If $iSequence > $g_iEngineSupervisorLastSequence Then $g_iEngineSupervisorLastSequence = $iSequence
	If $iPhaseRank > $g_iEngineSupervisorLastPhaseRank Then
		$g_iEngineSupervisorLastPhaseRank = $iPhaseRank
		$g_sEngineSupervisorLastPhase = $sPhase
		$g_hEngineSupervisorPhaseTimer = TimerInit()
		If $iPhaseRank >= 2 And $g_hEngineSupervisorPostReturnTimer = 0 Then $g_hEngineSupervisorPostReturnTimer = TimerInit()
		_RecoveryLog("engine init phase; backend_pid=" & $iBackendPid & "; phase=" & $sPhase)
	EndIf
	; A nonce and Start-request-bound cancellation wins over late initialized, failure, and deadline
	; handling once prepared. The launcher never replays Start for a replacement backend.
	If _EngineSupervisorCancelMatches($sStartRequestId) Then Return _EngineSupervisorAbort($sReceipt, $iBackendPid, "matching Start cancellation")
	If $sPhase = "initialized" Then Return _EngineSupervisorFinalize($sReceipt, "initialized")
	If $sPhase = "failed" Then Return _EngineSupervisorAbort($sReceipt, $iBackendPid, "backend reported failed")
	If $sPhase = "prepared" And TimerDiff($g_hEngineSupervisorPhaseTimer) > $g_iEngineInitEnterTimeoutMs Then _
		Return _EngineSupervisorAbort($sReceipt, $iBackendPid, "pool entry did not begin within 10 seconds")
	If $sPhase = "pool-entered" And TimerDiff($g_hEngineSupervisorPhaseTimer) > $g_iEngineInitPoolStallTimeoutMs Then _
		Return _EngineSupervisorAbort($sReceipt, $iBackendPid, "pool initialization remained entered for more than 90 seconds")
	If $iPhaseRank >= 2 And $iPhaseRank < 8 And $g_hEngineSupervisorPostReturnTimer <> 0 And _
			TimerDiff($g_hEngineSupervisorPostReturnTimer) > $g_iEngineInitPostReturnTimeoutMs Then _
		Return _EngineSupervisorAbort($sReceipt, $iBackendPid, "initialization did not finish within 15 seconds after pool return")
	If $g_hEngineSupervisorAbsoluteTimer <> 0 And TimerDiff($g_hEngineSupervisorAbsoluteTimer) > $g_iEngineInitAbsoluteTimeoutMs Then _
		Return _EngineSupervisorAbort($sReceipt, $iBackendPid, "initialization exceeded the 120 second absolute cap")
	Return False
EndFunc   ;==>_EngineSupervisorPoll

; The service proof is sufficient even after its backend parent has crashed: PID plus creation
; FILETIME, image, parent id, exact command digest/arguments, script build, and profile root all have
; to agree with the backend's unguessable receipt.
Func _PlannerReceiptMatchesService($sReceipt, $iServicePid, $sOwnerToken)
	If _PlannerReceiptString($sReceipt, "schema") <> $g_sPlannerOwnershipSchema Then Return False
	If Not StringRegExp($sOwnerToken, "^[0-9a-f]{64}$") Then Return False
	If _PlannerReceiptString($sReceipt, "health_token") <> _StringSha256($sOwnerToken) Then Return False
	If _PlannerReceiptInt($sReceipt, "service_pid") <> $iServicePid Then Return False
	Local $iBackendPid = _PlannerReceiptInt($sReceipt, "backend_pid")
	If $iBackendPid <= 0 Or _PlannerReceiptInt($sReceipt, "parent_pid") <> $iBackendPid Then Return False
	If Not ProcessExists($iServicePid) Then Return False
	If _PlannerReceiptString($sReceipt, "service_created") <> _ProcessCreationId($iServicePid) Then Return False
	If _ProcessParentPid($iServicePid) <> $iBackendPid Then Return False
	Local $sImage = _ProcessImagePath($iServicePid)
	If Not StringRegExp(StringLower($sImage), "\\pythonw\.exe$") Then Return False
	If _PlannerReceiptString($sReceipt, "python_image_token") <> _LauncherPathToken($sImage) Then Return False
	If _PlannerReceiptString($sReceipt, "script_path_token") <> _LauncherPathToken($g_sPlannerScriptPath) Then Return False
	If _PlannerReceiptString($sReceipt, "profiles_root_token") <> _ProfilesRootToken($g_sProfilesRoot) Then Return False
	If _PlannerReceiptString($sReceipt, "build_sha256") <> _FileSha256($g_sPlannerScriptPath) Then Return False
	Local $sCommand = _ProcessCommandLine($iServicePid)
	If $sCommand = "" Or _PlannerReceiptString($sReceipt, "command_sha256") <> _StringSha256($sCommand) Then Return False
	If StringInStr($sCommand, '"' & $g_sPlannerScriptPath & '"') = 0 Then Return False
	If StringInStr($sCommand, '--owner-token "' & $sOwnerToken & '"') = 0 Then Return False
	If StringInStr($sCommand, '--profiles-root "' & $g_sProfilesRoot & '"') = 0 Then Return False
	Return True
EndFunc   ;==>_PlannerReceiptMatchesService

Func _PlannerReceiptMatchesLiveBackend($sReceipt)
	Local $iBackendPid = _PlannerReceiptInt($sReceipt, "backend_pid")
	If $iBackendPid <= 0 Or Not ProcessExists($iBackendPid) Then Return False
	If StringLower(_ProcessImagePath($iBackendPid)) <> StringLower($g_sHostPath) Then Return False
	If _PlannerReceiptString($sReceipt, "backend_created") <> _ProcessCreationId($iBackendPid) Then Return False
	Return True
EndFunc   ;==>_PlannerReceiptMatchesLiveBackend

Func _PlannerHealthComError($oError)
	$g_bPlannerHealthComError = True
	Return
EndFunc   ;==>_PlannerHealthComError

; Recovery must remain bounded even if a foreign listener accepts the fixed loopback port and never
; sends a response. WinHTTP supplies explicit per-stage millisecond timeouts; direct mode prevents a
; user/system proxy from becoming part of the local ownership decision.
Func _ReadPlannerHealthBounded(ByRef $sHealth, $sUrl = "")
	$sHealth = ""
	If $sUrl = "" Then $sUrl = $g_sControlCenterUrl & "api/health"
	$g_bPlannerHealthComError = False
	Local $oErrorSink = ObjEvent("AutoIt.Error", "_PlannerHealthComError")
	Local $oRequest = ObjCreate("WinHttp.WinHttpRequest.5.1")
	If @error Or Not IsObj($oRequest) Then Return False
	$oRequest.SetProxy(1)
	$oRequest.SetTimeouts($g_iPlannerHealthResolveTimeoutMs, $g_iPlannerHealthConnectTimeoutMs, _
		$g_iPlannerHealthSendTimeoutMs, $g_iPlannerHealthReceiveTimeoutMs)
	$oRequest.Open("GET", $sUrl, True)
	$oRequest.SetRequestHeader("Host", "127.0.0.1:8765")
	$oRequest.Send()
	If $g_bPlannerHealthComError Then Return False
	Local $bCompleted = $oRequest.WaitForResponse(1)
	If $g_bPlannerHealthComError Or Not $bCompleted Then
		$oRequest.Abort()
		Return False
	EndIf
	If Int($oRequest.Status) <> 200 Then Return False
	$sHealth = String($oRequest.ResponseText)
	Return $sHealth <> ""
EndFunc   ;==>_ReadPlannerHealthBounded

; Loopback health is not authority. Recovery requires the exact, atomically persisted ownership
; receipt plus a live process/lineage match, then uses health only as a second-channel liveness proof.
Func _CloseOwnedPlannerService($iExpectedBackendPid = 0, $sExpectedBackendCreated = "")
	Local $sReceipt = _ReadPlannerOwnershipReceipt()
	If $sReceipt = "" Then
		Local $sUnownedHealth = ""
		If _ReadPlannerHealthBounded($sUnownedHealth) Then
			_RecoveryLog("refused planner service: loopback health has no safe ownership receipt")
			Return False
		EndIf
		Return True
	EndIf
	If $iExpectedBackendPid > 0 And (_PlannerReceiptInt($sReceipt, "backend_pid") <> $iExpectedBackendPid Or _
			_PlannerReceiptString($sReceipt, "backend_created") <> $sExpectedBackendCreated) Then
		_RecoveryLog("refused planner service: receipt does not match captured launcher-owned backend")
		Return False
	EndIf
	Local $sHealth = ""
	Local $bHealthAvailable = _ReadPlannerHealthBounded($sHealth)
	Local $sOwnerToken = _PlannerReceiptString($sReceipt, "token")
	Local $sHealthToken = _PlannerReceiptString($sReceipt, "health_token")
	If $sOwnerToken = "" Or $sHealthToken = "" Or _StringSha256($sOwnerToken) <> $sHealthToken Then
		_RecoveryLog("refused planner service: invalid ownership token receipt")
		Return False
	EndIf
	Local $iPid = _PlannerReceiptInt($sReceipt, "service_pid")
	If $iPid <= 0 Or Not _PlannerReceiptMatchesService($sReceipt, $iPid, $sOwnerToken) Then
		_RecoveryLog("refused planner service: receipt or service identity mismatch")
		Return False
	EndIf
	Local $bLiveBackend = _PlannerReceiptMatchesLiveBackend($sReceipt)
	Local $bObservedForeignHealth = False
	If $bHealthAvailable Then
		Local $sJsonRoot = StringReplace(@ScriptDir, "\", "\\")
		Local $sProfilesRootToken = _ProfilesRootToken($g_sProfilesRoot)
		Local $sScriptHash = _FileSha256($g_sPlannerScriptPath)
		Local $aHealthPid = StringRegExp($sHealth, """service_pid""\s*:\s*([0-9]+)", $STR_REGEXPARRAYMATCH)
		Local $iHealthPidError = @error
		Local $bHealthPidMatches = False
		If $iHealthPidError = 0 Then
			If IsArray($aHealthPid) Then
				If UBound($aHealthPid) = 1 Then $bHealthPidMatches = Int($aHealthPid[0]) = $iPid
			EndIf
		EndIf
		Local $bHealthMatches = StringInStr($sHealth, """service"": """ & $g_sPlannerServiceName & """") > 0 And _
			StringInStr($sHealth, """repo_root"": """ & $sJsonRoot & """") > 0 And _
			$sProfilesRootToken <> "" And StringInStr($sHealth, """profiles_root_token"": """ & $sProfilesRootToken & """") > 0 And _
			$sScriptHash <> "" And StringInStr(StringLower($sHealth), """build_sha256"": """ & $sScriptHash & """") > 0 And _
			StringInStr($sHealth, """owner_token_kind"": ""sha256""") > 0 And _
			StringInStr(StringLower($sHealth), """owner_token"": """ & $sHealthToken & """") > 0 And $bHealthPidMatches
		; A live backend needs matching health. An orphan is recoverable from its stronger persisted
		; service identity even if a foreign listener races onto the fixed loopback port.
		If $bLiveBackend And Not $bHealthMatches Then
			_RecoveryLog("refused planner service: live owner health does not match receipt")
			Return False
		EndIf
		If Not $bLiveBackend And Not $bHealthMatches Then
			$bObservedForeignHealth = True
			_RecoveryLog("orphan recovery observed a foreign loopback listener; exact planner will close but recovery remains unresolved")
		EndIf
	ElseIf $bLiveBackend Then
		_RecoveryLog("recovering unresponsive planner with exact live-owner receipt")
	Else
		_RecoveryLog("recovering orphaned planner with exact service receipt")
	EndIf
	; Re-read the exact receipt and service identity immediately before close. A changed receipt,
	; reparented process, or reused PID fails closed.
	If _ReadPlannerOwnershipReceipt() <> $sReceipt Or Not _PlannerReceiptMatchesService($sReceipt, $iPid, $sOwnerToken) Then Return False
	_RecoveryLog("closing verified planner service; pid=" & $iPid)
	If Not ProcessClose($iPid) Then Return False
	For $i = 1 To 40
		If Not ProcessExists($iPid) Then ExitLoop
		Sleep(50)
	Next
	If ProcessExists($iPid) Then Return False
	If _ReadPlannerOwnershipReceipt() <> $sReceipt Or Not _PlannerReceiptPathSafe(True) Then Return False
	Local $bReceiptDeleted = FileDelete($g_sPlannerOwnershipReceipt) = 1 Or Not FileExists($g_sPlannerOwnershipReceipt)
	If Not $bReceiptDeleted Then Return False
	; One bounded post-close read prevents a truthful close from being reported as complete while a
	; different service still owns the fixed port. It is observed and logged, never terminated.
	Local $sRemainingHealth = ""
	If _ReadPlannerHealthBounded($sRemainingHealth) Then
		_RecoveryLog("recovery unresolved: foreign planner listener still answers on 127.0.0.1:8765")
		Return False
	EndIf
	Return True
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
	If Not FileExists($g_sUserDataRoot) Then DirCreate($g_sUserDataRoot)
	FileWriteLine($g_sRecoveryLogPath, @YEAR & "-" & @MON & "-" & @MDAY & "T" & @HOUR & ":" & @MIN & ":" & @SEC & " " & $sMessage)
EndFunc   ;==>_RecoveryLog

Func _ValidateInstallation()
	If Not FileExists($g_sControllerPath) Then Return _InstallError("MyBot.run.MiniGui.exe is missing.", $g_sControllerPath)
	If Not _ControllerProvenanceMatches() Then
		Return _InstallError("The native controller does not match its reviewed local-build provenance.", $g_sBinaryProvenancePath)
	EndIf
	If Not FileExists($g_sHostPath) Then Return _InstallError("MyBot.run.exe is missing.", $g_sHostPath)
	If Not FileExists($g_sHostConfigPath) Then Return _InstallError("MyBot.run.exe.config is missing.", $g_sHostConfigPath)
	If Not FileExists($g_sEngineProbeConfigPath) Then Return _InstallError("MyBot.run.EngineProbe.exe.config is missing.", $g_sEngineProbeConfigPath)
	If Not FileExists($g_sEnginePath) Then Return _InstallError("lib\MyBot.run.dll is missing.", $g_sEnginePath)
	If Not FileExists($g_sEngineMarkerPath) Or FileGetSize($g_sEngineMarkerPath) <> 0 Then
		Return _InstallError("The empty MyBot.run.txt engine marker is missing or invalid.", $g_sEngineMarkerPath)
	EndIf
	Local $sForeignBackend = ""
	If _FindForeignBackendConflict($sForeignBackend) Then
		Return _LaunchConflictError("A different MyBot.run.exe is already running outside this installation." & @CRLF & @CRLF & _
			$sForeignBackend & @CRLF & @CRLF & _
			"Close that old MyBot backend from Task Manager, run My Bot 2.0 Recovery from its own install, or reboot before launching again.")
	EndIf
	If Not _InstalledProfilesJunctionMatches() Then
		Return _InstallError("The installed Profiles junction is missing or targets another directory.", @ScriptDir & "\Profiles")
	EndIf
	Return True
EndFunc   ;==>_ValidateInstallation

Func _FindForeignBackendConflict(ByRef $sConflict)
	$sConflict = ""
	Local $aBackends = ProcessList("MyBot.run.exe")
	For $i = 1 To $aBackends[0][0]
		Local $iPid = $aBackends[$i][1]
		Local $sPath = _ProcessImagePath($iPid)
		If $sPath = "" Then
			$sConflict = "PID " & $iPid & " could not be inspected, so My Bot 2.0 cannot prove it is safe to start another backend."
			_RecoveryLog("foreign backend conflict; pid=" & $iPid & "; path=<unreadable>")
			Return True
		EndIf
		If StringLower($sPath) <> StringLower($g_sHostPath) Then
			$sConflict = "PID " & $iPid & " is running from:" & @CRLF & $sPath
			_RecoveryLog("foreign backend conflict; pid=" & $iPid & "; path=" & $sPath)
			Return True
		EndIf
	Next
	Return False
EndFunc   ;==>_FindForeignBackendConflict

Func _ControllerProvenanceMatches()
	If Not FileExists($g_sBinaryProvenancePath) Then Return False
	Local $sProvenance = FileRead($g_sBinaryProvenancePath)
	If @error Or $sProvenance = "" Then Return False

	; The release gate writes this deterministic object shape. Requiring one exact match rejects
	; missing, duplicate, inherited, malformed, or differently sourced controller records.
	Local $sPattern = '(?s)\{\s*"path"\s*:\s*"MyBot\.run\.MiniGui\.exe"\s*,\s*"sha256"\s*:\s*"([0-9a-f]{64})"\s*,\s*"bytes"\s*:\s*([1-9][0-9]*)\s*,\s*"provenance"\s*:\s*\{\s*"kind"\s*:\s*"local-build"\s*,\s*"source"\s*:\s*"MyBot\.run\.MiniGui\.au3"'
	Local $aIdentity = StringRegExp($sProvenance, $sPattern, 3)
	If @error Or UBound($aIdentity) <> 2 Then Return False

	Local $sExpectedSha256 = StringLower($aIdentity[0])
	Local $iExpectedBytes = Number($aIdentity[1])
	If $iExpectedBytes < 1 Then Return False
	Return FileGetSize($g_sControllerPath) = $iExpectedBytes And _FileSha256($g_sControllerPath) = $sExpectedSha256
EndFunc   ;==>_ControllerProvenanceMatches

Func _InstalledProfilesJunctionMatches()
	Local $sLink = @ScriptDir & "\Profiles"
	Local $aAttributes = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $sLink)
	If @error Or Not IsArray($aAttributes) Or $aAttributes[0] = 0xFFFFFFFF Then Return False
	If BitAND($aAttributes[0], 0x400) = 0 Then Return False
	Local $sActual = _LauncherCanonicalDirectory($sLink)
	If @error Or $sActual = "" Then Return False
	Local $sExpected = _LauncherCanonicalDirectory($g_sProfilesRoot)
	If @error Or $sExpected = "" Then Return False
	Return StringLower($sActual) = StringLower($sExpected)
EndFunc   ;==>_InstalledProfilesJunctionMatches

Func _LauncherCanonicalDirectory($sPath)
	Local $aHandle = DllCall("kernel32.dll", "handle", "CreateFileW", "wstr", $sPath, "dword", 0, "dword", 0x7, "ptr", 0, "dword", 3, "dword", 0x02000000, "ptr", 0)
	If @error Or Not IsArray($aHandle) Or $aHandle[0] = -1 Then Return SetError(1, 0, "")
	Local $hDirectory = $aHandle[0]
	Local $tFinal = DllStructCreate("wchar[32768]")
	Local $aFinal = DllCall("kernel32.dll", "dword", "GetFinalPathNameByHandleW", "handle", $hDirectory, "struct*", $tFinal, "dword", 32768, "dword", 0)
	Local $iFinalError = @error
	DllCall("kernel32.dll", "bool", "CloseHandle", "handle", $hDirectory)
	If $iFinalError Or Not IsArray($aFinal) Or $aFinal[0] = 0 Or $aFinal[0] >= 32768 Then Return SetError(2, 0, "")
	Local $sFinal = DllStructGetData($tFinal, 1)
	If StringLeft($sFinal, 4) = "\\?\" Then $sFinal = StringTrimLeft($sFinal, 4)
	While StringLen($sFinal) > 3 And StringRight($sFinal, 1) = "\"
		$sFinal = StringTrimRight($sFinal, 1)
	WEnd
	Return SetError(0, 0, $sFinal)
EndFunc   ;==>_LauncherCanonicalDirectory

Func _InstallError($sMessage, $sPath)
	_ShowError($sMessage & @CRLF & @CRLF & "Reinstall or restore it beside this launcher:" & @CRLF & $sPath)
	Return False
EndFunc   ;==>_InstallError

Func _LaunchConflictError($sMessage)
	_ShowError($sMessage)
	Return False
EndFunc   ;==>_LaunchConflictError

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
		_EngineSupervisorPoll()
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
		"^My Bot 2\.0 Mini v2\.0\.0 \(([A-Za-z0-9_. -]{1,64})\)$", $STR_REGEXPARRAYMATCH)
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
		_RefreshLauncherOwnedBackend($iControllerPid)
		_EngineSupervisorPoll()
		If Not ProcessExists($iControllerPid) Or Not WinExists($hController) Then Return False
		Local $hBlueStacks = _FindBlueStacksWindow($hController)
		If @error = 2 Then Return False
		If $hBlueStacks Then Return _DockController($hController, $hBlueStacks)
		Sleep(_EngineSupervisorPollDelay(500))
	Until TimerDiff($hTimer) >= $iTimeoutMs
	Return False
EndFunc   ;==>_DockWhenReady

Func _KeepDocked($hController, $iControllerPid)
	Local $sPreviousDockState = ""
	While ProcessExists($iControllerPid)
		_RefreshLauncherOwnedBackend($iControllerPid)
		_EngineSupervisorPoll()
		; Re-prove the controller's exact PID, path, and title before every possible move. If its
		; window is briefly recreated, reacquire only another exact window from the same process.
		If Not _ControllerWindowMatches($hController, $iControllerPid) Then
			$hController = _FindControllerWindow($iControllerPid)
			If @error = 2 Then
				Sleep(_EngineSupervisorPollDelay($g_iDockTransitionPollMs))
				ContinueLoop
			EndIf
			If Not $hController Then
				Sleep(_EngineSupervisorPollDelay(_AdaptiveDockPollDelay("controller-unbound", $sPreviousDockState)))
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
		Sleep(_EngineSupervisorPollDelay(_AdaptiveDockPollDelay($sDockState, $sPreviousDockState, $bNeedsFastPoll)))
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

; Docking remains at its low-resource 1/5 second cadence while idle. Once a receipt or matching
; cancellation is present, cap only the supervisor-bearing waits at 250 ms so Stop can win before a
; late initialized receipt without turning the launcher into a busy loop.
Func _EngineSupervisorNeedsFastPoll()
	If Not $g_bEngineSupervisorArmed Or $g_iEngineSupervisorControllerPid <= 0 Then Return False
	If $g_bEngineSupervisorAbortAttempted Or $g_bEngineSupervisorFailureLatched Then Return False
	If $g_bEngineSupervisorPrepared Or $g_iEngineSupervisorBackendPid > 0 Then Return True
	If FileExists($g_sEngineInitCancelPath) And _EngineSupervisorPathSafe($g_sEngineInitCancelPath, True) Then Return True
	Return FileExists($g_sEngineInitOwnershipReceipt) And $g_sEngineSupervisorLastNotice <> "invalid-receipt"
EndFunc   ;==>_EngineSupervisorNeedsFastPoll

Func _EngineSupervisorPollDelay($iDefaultDelayMs)
	If _EngineSupervisorNeedsFastPoll() And $iDefaultDelayMs > $g_iEngineInitActivePollMs Then Return $g_iEngineInitActivePollMs
	Return $iDefaultDelayMs
EndFunc   ;==>_EngineSupervisorPollDelay

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
	If EnvGet("MYBOT_CONTROL_CENTER_NO_BROWSER") = "1" Then
		_RecoveryLog("control center browser open suppressed by environment; url=" & $g_sControlCenterUrl)
		Return True
	EndIf
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
