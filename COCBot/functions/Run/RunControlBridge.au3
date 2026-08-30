; #FUNCTION# ====================================================================================================================
; Name ..........: Run control bridge
; Description ...: Consumes loopback control-center commands and publishes native engine state.
; Remarks .......: The bridge is file-based so the web service never needs elevation or a handle into the bot process.
;                  Commands are single-use, status writes are atomic, and no credentials or game data cross this boundary.
; ===============================================================================================================================
#include-once
#include <Date.au3>
#include <FileConstants.au3>

Global Const $RUN_CONTROL_COMMAND_FILE_NAME = "config\control-command.local.json"
Global Const $RUN_CONTROL_STATUS_FILE_NAME = "config\control-status.local.json"
Global Const $RUN_CONTROL_MAX_COMMAND_BYTES = 8192
Global Const $RUN_CONTROL_COMMAND_TTL_SECONDS = 30
Global Const $RUN_CONTROL_CLOCK_SKEW_SECONDS = 5
Global Const $RUN_CONTROL_TERMINAL_OUTCOME_TTL_SECONDS = 120

Global $g_bRunControlReady = False
Global $g_sRunControlLastCommandId = ""
Global $g_sRunControlLastCommand = ""
Global $g_sRunControlLastOutcome = ""
Global $g_sRunControlMessage = "Native engine is starting"
Global $g_bRunControlStartInProgress = False
Global $g_bRunControlStopRequested = False
Global $g_bRunControlEngineCheckRequested = False
Global $g_bRunControlGameLaunchRequested = False
Global $g_sRunControlPendingStartRequestId = ""
Global $g_sRunControlActiveStartRequestId = ""
Global $g_sRunControlRunRequestId = ""
Global $g_sRunControlPendingStartMode = ""
Global $g_sRunControlActiveStartMode = ""
Global $g_sRunControlPendingStartPlanRevision = ""
Global $g_sRunControlActiveStartPlanRevision = ""
Global $g_sRunControlPendingStartPlanToken = ""
Global $g_sRunControlActiveStartPlanToken = ""
Global $g_hRunControlOwnerMutex = 0

Func RunControlStopRequested()
	Return $g_bRunControlStopRequested
EndFunc   ;==>RunControlStopRequested

Func RunControlEngineCheckRequested()
	Return $g_bRunControlEngineCheckRequested
EndFunc   ;==>RunControlEngineCheckRequested

Func RunControlGameLaunchRequested()
	Return $g_bRunControlGameLaunchRequested
EndFunc   ;==>RunControlGameLaunchRequested

; The engine-initialization ownership receipt binds a blocked Start to the exact command that
; requested it. Expose only the already-validated local request id; no file or loopback parsing is
; performed from the synchronous managed-call boundary.
Func RunControlCurrentCommandId()
	If Not $g_bRunControlStartInProgress Then Return ""
	If ($g_sRunControlLastCommand <> "start" And $g_sRunControlLastCommand <> "check-engine") Or _
			$g_sRunControlLastOutcome <> "accepted" Then Return ""
	If Not StringRegExp($g_sRunControlActiveStartRequestId, "^[A-Za-z0-9._-]{1,80}$") Then Return ""
	Return $g_sRunControlActiveStartRequestId
EndFunc   ;==>RunControlCurrentCommandId

Func RunControlCurrentStartMode()
	If Not $g_bRunControlStartInProgress Then Return ""
	If Not StringRegExp($g_sRunControlActiveStartMode, "^(planned|native-profile)$") Then Return ""
	Return $g_sRunControlActiveStartMode
EndFunc   ;==>RunControlCurrentStartMode

Func RunControlCurrentStartPlanRevision()
	If Not $g_bRunControlStartInProgress Then Return ""
	If Not StringRegExp($g_sRunControlActiveStartPlanRevision, "^(0|[1-9][0-9]{0,18})$") Then Return ""
	Return $g_sRunControlActiveStartPlanRevision
EndFunc   ;==>RunControlCurrentStartPlanRevision

Func RunControlCurrentStartPlanToken()
	If Not $g_bRunControlStartInProgress Then Return ""
	If Not StringRegExp($g_sRunControlActiveStartPlanToken, "^(absent|sha256:[0-9a-f]{64})$") Then Return ""
	Return $g_sRunControlActiveStartPlanToken
EndFunc   ;==>RunControlCurrentStartPlanToken

Func RunControlCurrentStartGeneration()
	Return _RunControlCurrentStartGeneration(True)
EndFunc   ;==>RunControlCurrentStartGeneration

Func RunControlAcceptedStopRequestId($sExpectedStartRequestId)
	If Not $g_bRunControlStopRequested Or _RunControlCurrentStartGeneration(True) <> $sExpectedStartRequestId Then Return ""
	If $g_sRunControlLastCommand <> "stop" Or $g_sRunControlLastOutcome <> "accepted" Then Return ""
	If Not StringRegExp($g_sRunControlLastCommandId, "^[A-Za-z0-9._-]{1,80}$") Then Return ""
	Return $g_sRunControlLastCommandId
EndFunc   ;==>RunControlAcceptedStopRequestId

Func _RunControlNewLocalStartRequestId()
	Local $sRequestId = "local-start-" & @AutoItPID & "-" & @YEAR & @MON & @MDAY & @HOUR & @MIN & @SEC & @MSEC & "-" & Random(100000, 999999, 1)
	If Not StringRegExp($sRequestId, "^[A-Za-z0-9._-]{1,80}$") Then Return ""
	Return $sRequestId
EndFunc   ;==>_RunControlNewLocalStartRequestId

Func _RunControlCurrentStartGeneration($bAllowInitializing = False)
	Local $sRequestId = $g_sRunControlRunRequestId
	If StringRegExp($sRequestId, "^[A-Za-z0-9._-]{1,80}$") Then Return $sRequestId
	If Not $bAllowInitializing Then Return ""
	$sRequestId = $g_sRunControlActiveStartRequestId
	If StringRegExp($sRequestId, "^[A-Za-z0-9._-]{1,80}$") Then Return $sRequestId
	$sRequestId = $g_sRunControlPendingStartRequestId
	If StringRegExp($sRequestId, "^[A-Za-z0-9._-]{1,80}$") Then Return $sRequestId
	Return ""
EndFunc   ;==>_RunControlCurrentStartGeneration

Func RunControlCommandPath()
	Return @ScriptDir & "\" & $RUN_CONTROL_COMMAND_FILE_NAME
EndFunc   ;==>RunControlCommandPath

Func RunControlStatusPath()
	Return @ScriptDir & "\" & $RUN_CONTROL_STATUS_FILE_NAME
EndFunc   ;==>RunControlStatusPath

Func _RunControlOwnerMutexName()
	Local $sCheckout = StringLower(@ScriptDir)
	$sCheckout = StringReplace($sCheckout, "\", "-")
	$sCheckout = StringReplace($sCheckout, ":", "")
	Return "MyBot.2.0/ControlCenter/" & $sCheckout
EndFunc   ;==>_RunControlOwnerMutexName

Func RunControlState()
	If $g_iBotAction = $eBotClose Then Return "closing"
	If $g_iBotAction = $eBotStop Then Return "stopping"
	If $g_bRunControlStartInProgress Then Return "starting"
	If Not $g_bRunState And $g_iBotAction = $eBotStart Then Return "starting"
	If Not $g_bRunState Then Return "idle"
	If $g_bBotPaused Then Return "paused"
	Return "running"
EndFunc   ;==>RunControlState

Func _RunControlBool($bValue)
	Return $bValue ? "true" : "false"
EndFunc   ;==>_RunControlBool

Func _RunControlOutcomeIsTerminal($sOutcome)
	Return StringRegExp(StringLower(String($sOutcome)), "^(completed|failed|passed|rejected|stopped)$") = 1
EndFunc   ;==>_RunControlOutcomeIsTerminal

Func _RunControlRestoreRecentTerminalOutcome()
	Local $sPath = RunControlStatusPath()
	If Not FileExists($sPath) Then Return False
	Local $sTimestampError = ""
	Local $iAgeSeconds = _RunControlCommandAgeSeconds($sPath, $sTimestampError)
	If $sTimestampError <> "" Then Return False
	If $iAgeSeconds < -$RUN_CONTROL_CLOCK_SKEW_SECONDS Then Return False
	If $iAgeSeconds > $RUN_CONTROL_TERMINAL_OUTCOME_TTL_SECONDS Then Return False
	Local $sLoadError = ""
	Local $oStatus = RunPlanFileLoad($sPath, $sLoadError)
	If @error Or Not IsObj($oStatus) Then Return False
	If Not $oStatus.Exists("last_outcome") Or Not $oStatus.Exists("last_command") Then Return False
	Local $sOutcome = StringLower(StringStripWS(String($oStatus.Item("last_outcome")), $STR_STRIPALL))
	If Not _RunControlOutcomeIsTerminal($sOutcome) Then Return False
	Local $sCommand = StringLower(StringStripWS(String($oStatus.Item("last_command")), $STR_STRIPALL))
	If Not StringRegExp($sCommand, "^(start|launch-game|check-engine|stop)$") Then Return False
	Local $sRequestId = ""
	If $oStatus.Exists("last_command_id") Then $sRequestId = StringStripWS(String($oStatus.Item("last_command_id")), $STR_STRIPALL)
	If $sRequestId <> "" And Not StringRegExp($sRequestId, "^[A-Za-z0-9._-]{1,80}$") Then Return False
	Local $sMessage = ""
	If $oStatus.Exists("last_command_message") Then $sMessage = StringLeft(String($oStatus.Item("last_command_message")), 1024)
	$g_sRunControlLastCommandId = $sRequestId
	$g_sRunControlLastCommand = $sCommand
	$g_sRunControlLastOutcome = $sOutcome
	$g_sRunControlMessage = $sMessage
	Return True
EndFunc   ;==>_RunControlRestoreRecentTerminalOutcome

Func _RunControlStateMessage($sState)
	Switch $sState
		Case "idle"
			If Not MBRFuncEngineAvailable() Then Return MBRFuncEngineError()
			Return "Native engine is ready"
		Case "starting"
			If Not MBRFuncEngineAvailable() Then Return MBRFuncEngineError()
			Return "Preparing the run"
		Case "running"
			Return "Run is active"
		Case "paused"
			Return "Run is paused"
		Case "stopping"
			Return "Stopping the run"
		Case "closing"
			Return "Native engine is closing"
	EndSwitch
	Return $g_sRunControlMessage
EndFunc   ;==>_RunControlStateMessage

Func RunControlWriteStatus($bForce = False)
	Static $hStatusTimer = 0
	If Not $g_bRunControlReady Then Return False
	If Not $bForce And $hStatusTimer <> 0 And __TimerDiff($hStatusTimer) < 1000 Then Return True

	Local $sState = RunControlState()
	Local $sStatusPath = RunControlStatusPath()
	Local $sTemporary = $sStatusPath & "." & @AutoItPID & ".tmp"
	Local $sJson = "{"
	$sJson &= _RunEventJsonString("schema_version") & ":1,"
	$sJson &= _RunEventJsonString("product_name") & ":" & _RunEventJsonString($g_sProductName) & ","
	$sJson &= _RunEventJsonString("product_version") & ":" & _RunEventJsonString($g_sProductVersion) & ","
	$sJson &= _RunEventJsonString("engine_version") & ":" & _RunEventJsonString($g_sBotVersion) & ","
	$sJson &= _RunEventJsonString("state") & ":" & _RunEventJsonString($sState) & ","
	$sJson &= _RunEventJsonString("run_state") & ":" & _RunControlBool($g_bRunState) & ","
	$sJson &= _RunEventJsonString("paused") & ":" & _RunControlBool($g_bBotPaused) & ","
	$sJson &= _RunEventJsonString("authorization_ready") & ":" & _RunControlBool(ForumAuthorizationReady()) & ","
	$sJson &= _RunEventJsonString("engine_available") & ":" & _RunControlBool(MBRFuncEngineAvailable()) & ","
        $sJson &= _RunEventJsonString("engine_probe_state") & ":" & _RunEventJsonString(MBRFuncEngineProbeState()) & ","
        $sJson &= _RunEventJsonString("recognition_available") & ":" & _RunControlBool(MBRFuncRecognitionAvailable()) & ","
        $sJson &= _RunEventJsonString("recognition_error") & ":" & _RunEventJsonString(MBRFuncRecognitionError()) & ","
        $sJson &= _RunEventJsonString("recognition_provider") & ":" & _RunEventJsonString(MBRFuncRecognitionProviderState()) & ","
        $sJson &= _RunEventJsonString("recognition_provider_reason") & ":" & _RunEventJsonString(MBRFuncRecognitionProviderReason()) & ","
        $sJson &= _RunEventJsonString("plan_active") & ":" & _RunControlBool(RunExecutionPlanActive()) & ","
	$sJson &= _RunEventJsonString("plan_message") & ":" & _RunEventJsonString(RunExecutionMessage()) & ","
	$sJson &= _RunEventJsonString("session_id") & ":" & _RunEventJsonString(RunExecutionSessionId()) & ","
	$sJson &= _RunEventJsonString("run_request_id") & ":" & _RunEventJsonString($g_sRunControlRunRequestId) & ","
	$sJson &= _RunEventJsonString("profile") & ":" & _RunEventJsonString($g_sProfileCurrentName) & ","
	$sJson &= _RunEventJsonString("emulator") & ":" & _RunEventJsonString($g_sAndroidEmulator) & ","
	$sJson &= _RunEventJsonString("instance") & ":" & _RunEventJsonString($g_sAndroidInstance) & ","
	; A stale/destroyed HWND can remain handle-typed after the emulator exits. Publish attachment
	; only while the exact window still exists and belongs to a live process.
	Local $bWindowAttached = IsHWnd($g_hAndroidWindow) And WinExists($g_hAndroidWindow) = 1 And WinGetProcess($g_hAndroidWindow) > 0
	; An initialized ADB executable/device string proves configuration, not an attached emulator.
	; A server-only `adb devices` result must therefore remain not-ready when the native window is absent.
	Local $bAdbReady = $bWindowAttached And $g_bAndroidInitialized And StringLen($g_sAndroidAdbDevice) > 0
	Local $bGameReady = $bAdbReady And $g_bRunState And $g_bMainWindowOk
	; Preserve emulator_attached for v1 clients while publishing the actual readiness stages.
	$sJson &= _RunEventJsonString("emulator_attached") & ":" & _RunControlBool($bWindowAttached) & ","
	$sJson &= _RunEventJsonString("window_attached") & ":" & _RunControlBool($bWindowAttached) & ","
	$sJson &= _RunEventJsonString("adb_ready") & ":" & _RunControlBool($bAdbReady) & ","
	$sJson &= _RunEventJsonString("game_ready") & ":" & _RunControlBool($bGameReady) & ","
	$sJson &= _RunEventJsonString("bot_pid") & ":" & @AutoItPID & ","
	$sJson &= _RunEventJsonString("last_command_id") & ":" & _RunEventJsonString($g_sRunControlLastCommandId) & ","
	$sJson &= _RunEventJsonString("last_command") & ":" & _RunEventJsonString($g_sRunControlLastCommand) & ","
	$sJson &= _RunEventJsonString("last_outcome") & ":" & _RunEventJsonString($g_sRunControlLastOutcome) & ","
	$sJson &= _RunEventJsonString("last_command_message") & ":" & _RunEventJsonString($g_sRunControlMessage) & ","
	$sJson &= _RunEventJsonString("message") & ":" & _RunEventJsonString(_RunControlStateMessage($sState))
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
	If Not FileMove($sTemporary, $sStatusPath, $FC_OVERWRITE) Then
		FileDelete($sTemporary)
		Return False
	EndIf
	$hStatusTimer = __TimerInit()
	Return True
EndFunc   ;==>RunControlWriteStatus

Func _RunControlAcknowledge($sRequestId, $sAction, $sOutcome, $sMessage)
	$g_sRunControlLastCommandId = $sRequestId
	$g_sRunControlLastCommand = $sAction
	$g_sRunControlLastOutcome = $sOutcome
	$g_sRunControlMessage = $sMessage
	RunControlWriteStatus(True)
EndFunc   ;==>_RunControlAcknowledge

Func _RunControlCommandAgeSeconds($sPath, ByRef $sError)
	$sError = ""
	Local $sTimestamp = FileGetTime($sPath, $FT_MODIFIED, $FT_STRING)
	If @error Or Not StringRegExp($sTimestamp, "^[0-9]{14}$") Then
		$sError = "Control command timestamp is unavailable"
		Return 0
	EndIf

	Local $sModified = StringLeft($sTimestamp, 4) & "/" & StringMid($sTimestamp, 5, 2) & "/" & StringMid($sTimestamp, 7, 2) & _
		" " & StringMid($sTimestamp, 9, 2) & ":" & StringMid($sTimestamp, 11, 2) & ":" & StringRight($sTimestamp, 2)
	Local $iAgeSeconds = _DateDiff("s", $sModified, _NowCalc())
	If @error Then
		$sError = "Control command timestamp could not be validated"
		Return 0
	EndIf
	Return $iAgeSeconds
EndFunc   ;==>_RunControlCommandAgeSeconds

Func RunControlReportStartOutcome($bStarted, $sMessage)
	$g_bRunControlStartInProgress = False
	$g_bRunControlEngineCheckRequested = False
	$g_bRunControlGameLaunchRequested = False
	$g_sRunControlActiveStartRequestId = ""
	$g_sRunControlPendingStartRequestId = ""
	$g_sRunControlActiveStartMode = ""
	$g_sRunControlPendingStartMode = ""
	$g_sRunControlActiveStartPlanRevision = ""
	$g_sRunControlPendingStartPlanRevision = ""
	$g_sRunControlActiveStartPlanToken = ""
	$g_sRunControlPendingStartPlanToken = ""
	If Not $bStarted And Not $g_bRunControlStopRequested Then $g_sRunControlRunRequestId = ""
	If $g_bRunControlStopRequested Then
		$g_bRunState = False
		$g_iBotAction = $eBotStop
	EndIf
	If $g_sRunControlLastCommand = "start" And $g_sRunControlLastOutcome = "accepted" Then
		$g_sRunControlLastOutcome = $bStarted ? "started" : "rejected"
	EndIf
	$g_sRunControlMessage = $sMessage
	RunControlWriteStatus(True)
EndFunc   ;==>RunControlReportStartOutcome

Func RunControlReportEngineCheckOutcome(ByRef $bPassed, ByRef $sMessage)
	Local $bStopAccepted = $g_bRunControlStopRequested
	If $bStopAccepted Then
		$bPassed = False
		$sMessage = "Managed engine check cancelled; no emulator or game action was attempted"
	EndIf
	$g_bRunControlStartInProgress = False
	$g_bRunControlEngineCheckRequested = False
	$g_bRunControlGameLaunchRequested = False
	$g_bRunControlStopRequested = False
	$g_sRunControlActiveStartRequestId = ""
	$g_sRunControlPendingStartRequestId = ""
	$g_sRunControlActiveStartMode = ""
	$g_sRunControlPendingStartMode = ""
	$g_sRunControlActiveStartPlanRevision = ""
	$g_sRunControlPendingStartPlanRevision = ""
	$g_sRunControlActiveStartPlanToken = ""
	$g_sRunControlPendingStartPlanToken = ""
	$g_sRunControlRunRequestId = ""
	$g_bRunState = False
	$g_iBotAction = $eBotNoAction
	If $bStopAccepted Then
		If $g_sRunControlLastCommand = "stop" And $g_sRunControlLastOutcome = "accepted" Then $g_sRunControlLastOutcome = "stopped"
	ElseIf $g_sRunControlLastCommand = "check-engine" And $g_sRunControlLastOutcome = "accepted" Then
			$g_sRunControlLastOutcome = $bPassed ? "passed" : "failed"
	EndIf
	$g_sRunControlMessage = $sMessage
	RunControlWriteStatus(True)
	Return $bStopAccepted ? "cancelled" : ($bPassed ? "passed" : "failed")
EndFunc   ;==>RunControlReportEngineCheckOutcome

Func RunControlReportGameLaunchOutcome(ByRef $bPassed, ByRef $sMessage)
	Local $bStopAccepted = $g_bRunControlStopRequested
	If $bStopAccepted Then
		$bPassed = False
		$sMessage = "BlueStacks and Clash of Clans launch cancelled before completion"
	EndIf
	$g_bRunControlStartInProgress = False
	$g_bRunControlEngineCheckRequested = False
	$g_bRunControlGameLaunchRequested = False
	$g_bRunControlStopRequested = False
	$g_sRunControlActiveStartRequestId = ""
	$g_sRunControlPendingStartRequestId = ""
	$g_sRunControlActiveStartMode = ""
	$g_sRunControlPendingStartMode = ""
	$g_sRunControlActiveStartPlanRevision = ""
	$g_sRunControlPendingStartPlanRevision = ""
	$g_sRunControlActiveStartPlanToken = ""
	$g_sRunControlPendingStartPlanToken = ""
	$g_sRunControlRunRequestId = ""
	$g_bRunState = False
	$g_iBotAction = $eBotNoAction
	If $bStopAccepted Then
		If $g_sRunControlLastCommand = "stop" And $g_sRunControlLastOutcome = "accepted" Then $g_sRunControlLastOutcome = "stopped"
	ElseIf $g_sRunControlLastCommand = "launch-game" And $g_sRunControlLastOutcome = "accepted" Then
		$g_sRunControlLastOutcome = $bPassed ? "passed" : "failed"
	EndIf
	$g_sRunControlMessage = $sMessage
	RunControlWriteStatus(True)
	Return $bStopAccepted ? "cancelled" : ($bPassed ? "passed" : "failed")
EndFunc   ;==>RunControlReportGameLaunchOutcome

Func RunControlReportRunFailure($sMessage)
	$g_bRunControlStartInProgress = False
	$g_bRunControlEngineCheckRequested = False
	$g_bRunControlGameLaunchRequested = False
	$g_sRunControlActiveStartRequestId = ""
	$g_sRunControlPendingStartRequestId = ""
	$g_sRunControlActiveStartMode = ""
	$g_sRunControlPendingStartMode = ""
	$g_sRunControlActiveStartPlanRevision = ""
	$g_sRunControlPendingStartPlanRevision = ""
	$g_sRunControlActiveStartPlanToken = ""
	$g_sRunControlPendingStartPlanToken = ""
	; Preserve an accepted Stop until BotStop publishes its terminal stopped outcome. A bounded
	; recognition/readiness call may unwind after the Stop flag was latched, but that unwind is not
	; a new run failure and must not overwrite the command acknowledgement.
	If $g_bRunControlStopRequested Then
		RunControlWriteStatus(True)
		Return
	EndIf
	$g_sRunControlRunRequestId = ""
	$g_sRunControlLastOutcome = "failed"
	$g_sRunControlMessage = $sMessage
	RunControlWriteStatus(True)
EndFunc   ;==>RunControlReportRunFailure

; Terminalize a bounded Start that deliberately returns idle without entering BotStop. This is used
; by input-minimal one-shot adapters whose cleanup must not call ResumeAndroid or legacy Stop work.
Func RunControlReportOneShotOutcome($sOutcome, $sMessage)
	Local $bStopAccepted = $g_bRunControlStopRequested
	$g_bRunControlStopRequested = False
	$g_bRunControlStartInProgress = False
	$g_bRunControlEngineCheckRequested = False
	$g_bRunControlGameLaunchRequested = False
	$g_sRunControlActiveStartRequestId = ""
	$g_sRunControlPendingStartRequestId = ""
	$g_sRunControlActiveStartMode = ""
	$g_sRunControlPendingStartMode = ""
	$g_sRunControlActiveStartPlanRevision = ""
	$g_sRunControlPendingStartPlanRevision = ""
	$g_sRunControlActiveStartPlanToken = ""
	$g_sRunControlPendingStartPlanToken = ""
	$g_sRunControlRunRequestId = ""
	$g_bBotPaused = False
	$g_bRunState = False
	$g_iBotAction = $eBotNoAction
	If $bStopAccepted And $g_sRunControlLastCommand = "stop" And $g_sRunControlLastOutcome = "accepted" Then
		$g_sRunControlLastOutcome = "stopped"
	ElseIf ($g_sRunControlLastCommand = "start" Or $g_sRunControlLastCommand = "launch-game") And _
			($g_sRunControlLastOutcome = "accepted" Or $g_sRunControlLastOutcome = "started") Then
		$g_sRunControlLastOutcome = $sOutcome
	EndIf
	$g_sRunControlMessage = $sMessage
	RunControlWriteStatus(True)
	Return $bStopAccepted ? "stopped" : $sOutcome
EndFunc   ;==>RunControlReportOneShotOutcome

Func RunControlBeginStart()
	If $g_bRunControlStartInProgress And StringRegExp($g_sRunControlActiveStartRequestId, "^[A-Za-z0-9._-]{1,80}$") Then Return
	If StringRegExp($g_sRunControlPendingStartRequestId, "^[A-Za-z0-9._-]{1,80}$") Then
		$g_sRunControlActiveStartRequestId = $g_sRunControlPendingStartRequestId
		$g_sRunControlActiveStartMode = $g_sRunControlPendingStartMode
		$g_sRunControlActiveStartPlanRevision = $g_sRunControlPendingStartPlanRevision
		$g_sRunControlActiveStartPlanToken = $g_sRunControlPendingStartPlanToken
	Else
		$g_sRunControlActiveStartRequestId = _RunControlNewLocalStartRequestId()
		$g_sRunControlActiveStartMode = ""
		$g_sRunControlActiveStartPlanRevision = ""
		$g_sRunControlActiveStartPlanToken = ""
		$g_sRunControlLastCommandId = $g_sRunControlActiveStartRequestId
		$g_sRunControlLastCommand = "start"
		$g_sRunControlLastOutcome = "accepted"
		$g_sRunControlMessage = "Start requested locally"
	EndIf
	$g_sRunControlRunRequestId = $g_sRunControlActiveStartRequestId
	$g_sRunControlPendingStartRequestId = ""
	$g_sRunControlPendingStartMode = ""
	$g_sRunControlPendingStartPlanRevision = ""
	$g_sRunControlPendingStartPlanToken = ""
	; A completed one-shot must never leave Pause armed for the next Start.
	$g_bBotPaused = False
	$g_bRunControlStartInProgress = True
	RunControlWriteStatus(True)
EndFunc   ;==>RunControlBeginStart

Func RunControlReportStopComplete()
	$g_bRunControlStopRequested = False
	$g_bRunControlStartInProgress = False
	$g_bRunControlEngineCheckRequested = False
	$g_bRunControlGameLaunchRequested = False
	$g_sRunControlActiveStartRequestId = ""
	$g_sRunControlPendingStartRequestId = ""
	$g_sRunControlActiveStartMode = ""
	$g_sRunControlPendingStartMode = ""
	$g_sRunControlActiveStartPlanRevision = ""
	$g_sRunControlPendingStartPlanRevision = ""
	$g_sRunControlActiveStartPlanToken = ""
	$g_sRunControlPendingStartPlanToken = ""
	$g_sRunControlRunRequestId = ""
	$g_bBotPaused = False
	If $g_sRunControlLastCommand = "stop" And $g_sRunControlLastOutcome = "accepted" Then
		$g_sRunControlLastOutcome = "stopped"
		$g_sRunControlMessage = "Run stopped"
	ElseIf $g_sRunControlLastCommand = "start" And $g_sRunControlLastOutcome = "accepted" Then
		$g_sRunControlLastOutcome = "rejected"
		$g_sRunControlMessage = "Start ended before the run became active"
	EndIf
	RunControlWriteStatus(True)
EndFunc   ;==>RunControlReportStopComplete

; A command file belongs to the native process that was alive when the service
; accepted it. Reject any file left across a crash or fast restart before this
; process publishes a heartbeat, so a recent Start can never replay here.
Func _RunControlRejectOrphanedCommand()
	Local $sPath = RunControlCommandPath()
	If Not FileExists($sPath) Then Return True

	Local $sRequestId = ""
	Local $sAction = ""
	Local $iSize = FileGetSize($sPath)
	If Not @error And $iSize > 0 And $iSize <= $RUN_CONTROL_MAX_COMMAND_BYTES Then
		Local $sError = ""
		Local $oCommand = RunPlanFileLoad($sPath, $sError)
		If Not @error And IsObj($oCommand) Then
			If $oCommand.Exists("request_id") Then
				Local $sCandidateId = StringStripWS(String($oCommand.Item("request_id")), $STR_STRIPALL)
				If StringRegExp($sCandidateId, "^[A-Za-z0-9._-]{1,80}$") Then $sRequestId = $sCandidateId
			EndIf
			If $oCommand.Exists("action") Then
				Local $sCandidateAction = StringLower(StringStripWS(String($oCommand.Item("action")), $STR_STRIPALL))
				If StringRegExp($sCandidateAction, "^(start|stop|pause|resume|check-engine|launch-game)$") Then $sAction = $sCandidateAction
			EndIf
		EndIf
	EndIf

	FileDelete($sPath)
	If FileExists($sPath) Then Return False
	$g_sRunControlLastCommandId = $sRequestId
	$g_sRunControlLastCommand = $sAction
	$g_sRunControlLastOutcome = "rejected"
	$g_sRunControlMessage = "Command rejected because the native engine restarted before consuming it"
	Return True
EndFunc   ;==>_RunControlRejectOrphanedCommand

Func _RunControlConsumeCommand()
	Local $sPath = RunControlCommandPath()
	If Not FileExists($sPath) Then Return
	; Atomically claim the command on the same volume before parsing or dispatching it. If the
	; rename loses a race or is denied, execute nothing and let the next poll retry the original.
	Local $sClaimPath = $sPath & ".claim-" & @AutoItPID & "-" & @HOUR & @MIN & @SEC & @MSEC & "-" & Random(100000, 999999, 1)
	If Not FileMove($sPath, $sClaimPath) Then Return
	$sPath = $sClaimPath
	If FileGetSize($sPath) <= 0 Or FileGetSize($sPath) > $RUN_CONTROL_MAX_COMMAND_BYTES Then
		FileDelete($sPath)
		_RunControlAcknowledge("", "", "rejected", "Control command was empty or too large")
		Return
	EndIf
	Local $sTimestampError = ""
	Local $iCommandAgeSeconds = _RunControlCommandAgeSeconds($sPath, $sTimestampError)
	Local $sAgeProblem = $sTimestampError
	If $sAgeProblem = "" And $iCommandAgeSeconds > $RUN_CONTROL_COMMAND_TTL_SECONDS Then _
		$sAgeProblem = "Control command expired before the native engine could consume it"
	If $sAgeProblem = "" And $iCommandAgeSeconds < -$RUN_CONTROL_CLOCK_SKEW_SECONDS Then _
		$sAgeProblem = "Control command timestamp is in the future"

	Local $sError = ""
	Local $oCommand = RunPlanFileLoad($sPath, $sError)
	Local $iLoadError = @error
	; Parsing is read-only. Consume the claimed file before any validation can reach dispatch,
	; and fail closed if Windows still has the claim locked after the delete attempt.
	FileDelete($sPath)
	If FileExists($sPath) Then
		_RunControlAcknowledge("", "", "rejected", "Control command claim could not be cleared; no action was dispatched")
		Return
	EndIf
	If $iLoadError Or Not IsObj($oCommand) Then
		_RunControlAcknowledge("", "", "rejected", "Control command could not be parsed: " & $sError)
		Return
	EndIf
	If Not $oCommand.Exists("request_id") Or Not $oCommand.Exists("action") Then
		_RunControlAcknowledge("", "", "rejected", "Control command is missing request_id or action")
		Return
	EndIf

	Local $sRequestId = StringStripWS(String($oCommand.Item("request_id")), $STR_STRIPALL)
	Local $sAction = StringLower(StringStripWS(String($oCommand.Item("action")), $STR_STRIPALL))
	If Not StringRegExp($sRequestId, "^[A-Za-z0-9._-]{1,80}$") Then
		_RunControlAcknowledge("", $sAction, "rejected", "Control command request_id is invalid")
		Return
	EndIf
	If $sAgeProblem <> "" Then
		_RunControlAcknowledge($sRequestId, $sAction, "rejected", $sAgeProblem)
		Return
	EndIf
	If Not $oCommand.Exists("schema_version") Or Not $oCommand.Exists("requested_at") Then
		_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Control command is missing schema_version or requested_at")
		Return
	EndIf
	Local $sSchemaVersion = StringStripWS(String($oCommand.Item("schema_version")), $STR_STRIPALL)
	If Not StringRegExp($sSchemaVersion, "^1(?:\.0+)?$") Then
		_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Control command schema_version is unsupported")
		Return
	EndIf
	Local $sRequestedAt = StringStripWS(String($oCommand.Item("requested_at")), $STR_STRIPALL)
	If Not StringRegExp($sRequestedAt, "^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[0-1])T([0-1][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]{1,6})?(Z|[+-]([0-1][0-9]|2[0-3]):[0-5][0-9])$") Then
		_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Control command requested_at is invalid")
		Return
	EndIf
	Local $sRunMode = ""
	If $oCommand.Exists("run_mode") Then $sRunMode = StringLower(StringStripWS(String($oCommand.Item("run_mode")), $STR_STRIPALL))
	Local $sPlanRevision = ""
	If $oCommand.Exists("plan_revision") Then $sPlanRevision = StringStripWS(String($oCommand.Item("plan_revision")), $STR_STRIPALL)
	Local $sPlanToken = ""
	If $oCommand.Exists("plan_token") Then $sPlanToken = StringLower(StringStripWS(String($oCommand.Item("plan_token")), $STR_STRIPALL))
	Local $bHasExpectedStartRequestId = $oCommand.Exists("expected_start_request_id")
	Local $sExpectedStartRequestId = ""
	If $bHasExpectedStartRequestId Then $sExpectedStartRequestId = String($oCommand.Item("expected_start_request_id"))
	Local $bGenerationAction = StringRegExp($sAction, "^(stop|pause|resume)$") = 1
	If $sAction = "start" And Not StringRegExp($sRunMode, "^(planned|native-profile)$") Then
		_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Start command is missing a valid run_mode")
		Return
	EndIf
	If $sAction = "start" And Not StringRegExp($sPlanRevision, "^(0|[1-9][0-9]{0,18})$") Then
		_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Start command is missing a valid plan_revision")
		Return
	EndIf
	If $sAction = "start" And (($sRunMode = "planned" And Not StringRegExp($sPlanToken, "^sha256:[0-9a-f]{64}$")) Or _
			($sRunMode = "native-profile" And $sPlanToken <> "absent")) Then
		_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Start command is missing a valid plan_token")
		Return
	EndIf
	If $sAction <> "start" And $sRunMode <> "" Then
		_RunControlAcknowledge($sRequestId, $sAction, "rejected", "run_mode is valid only for Start")
		Return
	EndIf
	If $sAction <> "start" And $sPlanRevision <> "" Then
		_RunControlAcknowledge($sRequestId, $sAction, "rejected", "plan_revision is valid only for Start")
		Return
	EndIf
	If $sAction <> "start" And $sPlanToken <> "" Then
		_RunControlAcknowledge($sRequestId, $sAction, "rejected", "plan_token is valid only for Start")
		Return
	EndIf
	If Not $bGenerationAction And $bHasExpectedStartRequestId Then
		_RunControlAcknowledge($sRequestId, $sAction, "rejected", "expected_start_request_id is valid only for Stop, Pause, or Resume")
		Return
	EndIf
	If $bGenerationAction And $bHasExpectedStartRequestId And Not StringRegExp($sExpectedStartRequestId, "^[A-Za-z0-9._-]{1,80}$") Then
		_RunControlAcknowledge($sRequestId, $sAction, "rejected", StringUpper(StringLeft($sAction, 1)) & StringTrimLeft($sAction, 1) & " command expected_start_request_id is invalid")
		Return
	EndIf
	If $bGenerationAction And Not $bHasExpectedStartRequestId Then
		_RunControlAcknowledge($sRequestId, $sAction, "rejected", StringUpper(StringLeft($sAction, 1)) & StringTrimLeft($sAction, 1) & " command is missing expected_start_request_id")
		Return
	EndIf

	Switch $sAction
		Case "start"
			If Not MBRFuncEngineAvailable() Then
				_RunControlAcknowledge($sRequestId, $sAction, "rejected", MBRFuncEngineError())
				Return
			EndIf
			If $g_bRunState Or $g_iBotAction <> $eBotNoAction Then
				_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Engine is not idle")
				Return
			EndIf
			$g_bRunControlStopRequested = False
			$g_bRunControlEngineCheckRequested = False
			$g_bRunControlGameLaunchRequested = False
			$g_sRunControlPendingStartRequestId = $sRequestId
			$g_sRunControlPendingStartMode = $sRunMode
			$g_sRunControlPendingStartPlanRevision = $sPlanRevision
			$g_sRunControlPendingStartPlanToken = $sPlanToken
			$g_iBotAction = $eBotStart
			_RunControlAcknowledge($sRequestId, $sAction, "accepted", "Start requested by control center")
		Case "check-engine"
			If Not MBRFuncEngineAvailable() Then
				_RunControlAcknowledge($sRequestId, $sAction, "rejected", MBRFuncEngineError())
				Return
			EndIf
			If $g_bRunState Or $g_iBotAction <> $eBotNoAction Then
				_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Engine is not idle")
				Return
			EndIf
			$g_bRunControlStopRequested = False
			$g_bRunControlEngineCheckRequested = True
			$g_bRunControlGameLaunchRequested = False
			$g_sRunControlPendingStartRequestId = $sRequestId
			$g_sRunControlPendingStartMode = ""
			$g_sRunControlPendingStartPlanRevision = ""
			$g_sRunControlPendingStartPlanToken = ""
			$g_iBotAction = $eBotStart
			_RunControlAcknowledge($sRequestId, $sAction, "accepted", "Managed engine check requested by control center")
		Case "launch-game"
			If $g_bRunState Or $g_iBotAction <> $eBotNoAction Then
				_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Engine is not idle")
				Return
			EndIf
			$g_bRunControlStopRequested = False
			$g_bRunControlEngineCheckRequested = False
			$g_bRunControlGameLaunchRequested = True
			$g_sRunControlPendingStartRequestId = $sRequestId
			$g_sRunControlPendingStartMode = ""
			$g_sRunControlPendingStartPlanRevision = ""
			$g_sRunControlPendingStartPlanToken = ""
			$g_iBotAction = $eBotStart
			_RunControlAcknowledge($sRequestId, $sAction, "accepted", "BlueStacks and Clash of Clans launch requested by control center")
		Case "stop"
			Local $sCurrentStartRequestId = _RunControlCurrentStartGeneration(True)
			If $sCurrentStartRequestId = "" Or $sCurrentStartRequestId <> $sExpectedStartRequestId Then
				_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Stop command targets a Start generation that is no longer active")
				Return
			EndIf
			$g_sRunControlPendingStartRequestId = ""
			$g_sRunControlPendingStartMode = ""
			$g_sRunControlPendingStartPlanRevision = ""
			$g_sRunControlPendingStartPlanToken = ""
			If Not $g_bRunState And $g_iBotAction <> $eBotStart Then
				_RunControlAcknowledge($sRequestId, $sAction, "no-op", "Engine is already idle")
				Return
			EndIf
			$g_bRunControlStopRequested = True
			$g_bRunState = False
			$g_iBotAction = $eBotStop
			_RunControlAcknowledge($sRequestId, $sAction, "accepted", "Stop requested by control center")
		Case "pause"
			If _RunControlCurrentStartGeneration(False) <> $sExpectedStartRequestId Then
				_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Pause command targets a Start generation that is no longer active")
				Return
			EndIf
			If Not $g_bRunState Then
				_RunControlAcknowledge($sRequestId, $sAction, "rejected", "A run must be active before it can pause")
				Return
			EndIf
			If $g_bBotPaused Then
				_RunControlAcknowledge($sRequestId, $sAction, "no-op", "Run is already paused")
				Return
			EndIf
			$g_bBotPaused = True
			TogglePauseUpdateState("Control center")
			_RunControlAcknowledge($sRequestId, $sAction, "paused", "Run paused by control center")
		Case "resume"
			If _RunControlCurrentStartGeneration(False) <> $sExpectedStartRequestId Then
				_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Resume command targets a Start generation that is no longer active")
				Return
			EndIf
			If Not $g_bRunState Then
				_RunControlAcknowledge($sRequestId, $sAction, "rejected", "There is no paused run to resume")
				Return
			EndIf
			If Not $g_bBotPaused Then
				_RunControlAcknowledge($sRequestId, $sAction, "no-op", "Run is already active")
				Return
			EndIf
			$g_bBotPaused = False
			TogglePauseUpdateState("Control center")
			_RunControlAcknowledge($sRequestId, $sAction, "resumed", "Run resumed by control center")
		Case Else
			_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Unsupported control action")
	EndSwitch
EndFunc   ;==>_RunControlConsumeCommand

Func RunControlPoll()
	Static $bPolling = False
	If Not $g_bRunControlReady Or $bPolling Then Return
	$bPolling = True
	; Consume the current command before applying a prior Stop flag. A fresh Start command
	; deliberately clears stale stop state; applying the old flag first kills the new run.
	_RunControlConsumeCommand()
	If $g_bRunControlStopRequested Then $g_bRunState = False
	RunControlWriteStatus()
	$bPolling = False
EndFunc   ;==>RunControlPoll

Func RunControlInitialize()
	$g_bRunControlReady = False
	If $g_hRunControlOwnerMutex = 0 Then $g_hRunControlOwnerMutex = CreateMutex(_RunControlOwnerMutexName())
	If $g_hRunControlOwnerMutex = 0 Then
		$g_sRunControlMessage = "Control Center is owned by another bot process in this checkout"
		Return False
	EndIf
	If Not _RunControlRejectOrphanedCommand() Then
		$g_sRunControlMessage = "Native control is unavailable because an orphaned command could not be cleared"
		ReleaseMutex($g_hRunControlOwnerMutex)
		$g_hRunControlOwnerMutex = 0
		Return False
	EndIf
	$g_bRunControlReady = True
	Local $bRestoredTerminalOutcome = False
	If $g_sRunControlLastOutcome = "" Then $bRestoredTerminalOutcome = _RunControlRestoreRecentTerminalOutcome()
	If Not $bRestoredTerminalOutcome And $g_sRunControlLastOutcome <> "rejected" Then $g_sRunControlMessage = "Native engine is ready"
	RunControlWriteStatus(True)
	; Idle startup can spend time outside the main sleep pump (browser launch, emulator checks,
	; notification setup). The lightweight registered poll keeps the browser heartbeat and Start
	; command responsive there; the re-entrancy guard in RunControlPoll serializes it with _Sleep.
	AdlibRegister("RunControlPoll", 500)
	Return True
EndFunc   ;==>RunControlInitialize

Func RunControlShutdown()
	AdlibUnRegister("RunControlPoll")
	$g_bRunControlReady = False
	$g_bRunControlStartInProgress = False
	$g_bRunControlEngineCheckRequested = False
	$g_bRunControlGameLaunchRequested = False
	$g_sRunControlActiveStartRequestId = ""
	$g_sRunControlPendingStartRequestId = ""
	$g_sRunControlRunRequestId = ""
	$g_sRunControlActiveStartMode = ""
	$g_sRunControlPendingStartMode = ""
	$g_sRunControlActiveStartPlanToken = ""
	$g_sRunControlPendingStartPlanToken = ""
	If $g_hRunControlOwnerMutex = 0 Then Return
	If Not _RunControlOutcomeIsTerminal($g_sRunControlLastOutcome) Then FileDelete(RunControlStatusPath())
	ReleaseMutex($g_hRunControlOwnerMutex)
	$g_hRunControlOwnerMutex = 0
EndFunc   ;==>RunControlShutdown
