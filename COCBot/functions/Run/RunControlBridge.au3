; #FUNCTION# ====================================================================================================================
; Name ..........: Run control bridge
; Description ...: Consumes loopback control-center commands and publishes native engine state.
; Remarks .......: The bridge is file-based so the web service never needs elevation or a handle into the bot process.
;                  Commands are single-use, status writes are atomic, and no credentials or game data cross this boundary.
; ===============================================================================================================================
#include-once
#include <FileConstants.au3>

Global Const $RUN_CONTROL_COMMAND_FILE_NAME = "config\control-command.local.json"
Global Const $RUN_CONTROL_STATUS_FILE_NAME = "config\control-status.local.json"
Global Const $RUN_CONTROL_MAX_COMMAND_BYTES = 8192

Global $g_bRunControlReady = False
Global $g_sRunControlLastCommandId = ""
Global $g_sRunControlLastCommand = ""
Global $g_sRunControlLastOutcome = ""
Global $g_sRunControlMessage = "Native engine is starting"

Func RunControlCommandPath()
	Return @ScriptDir & "\" & $RUN_CONTROL_COMMAND_FILE_NAME
EndFunc   ;==>RunControlCommandPath

Func RunControlStatusPath()
	Return @ScriptDir & "\" & $RUN_CONTROL_STATUS_FILE_NAME
EndFunc   ;==>RunControlStatusPath

Func RunControlState()
	If $g_iBotAction = $eBotClose Then Return "closing"
	If $g_iBotAction = $eBotStop Then Return "stopping"
	If Not $g_bRunState And $g_iBotAction = $eBotStart Then Return "starting"
	If Not $g_bRunState Then Return "idle"
	If $g_bBotPaused Then Return "paused"
	Return "running"
EndFunc   ;==>RunControlState

Func _RunControlBool($bValue)
	Return $bValue ? "true" : "false"
EndFunc   ;==>_RunControlBool

Func _RunControlStateMessage($sState)
	Switch $sState
		Case "idle"
			Return "Native engine is ready"
		Case "starting"
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
	$sJson &= _RunEventJsonString("profile") & ":" & _RunEventJsonString($g_sProfileCurrentName) & ","
	$sJson &= _RunEventJsonString("emulator") & ":" & _RunEventJsonString($g_sAndroidEmulator) & ","
	$sJson &= _RunEventJsonString("instance") & ":" & _RunEventJsonString($g_sAndroidInstance) & ","
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

Func _RunControlConsumeCommand()
	Local $sPath = RunControlCommandPath()
	If Not FileExists($sPath) Then Return
	If FileGetSize($sPath) <= 0 Or FileGetSize($sPath) > $RUN_CONTROL_MAX_COMMAND_BYTES Then
		FileDelete($sPath)
		_RunControlAcknowledge("", "", "rejected", "Control command was empty or too large")
		Return
	EndIf

	Local $sError = ""
	Local $oCommand = RunPlanFileLoad($sPath, $sError)
	FileDelete($sPath) ; Every command is single-use, including malformed commands.
	If @error Or Not IsObj($oCommand) Then
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

	Switch $sAction
		Case "start"
			If $g_bRunState Or $g_iBotAction <> $eBotNoAction Then
				_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Engine is not idle")
				Return
			EndIf
			$g_iBotAction = $eBotStart
			_RunControlAcknowledge($sRequestId, $sAction, "accepted", "Start requested by control center")
		Case "stop"
			If Not $g_bRunState And $g_iBotAction <> $eBotStart Then
				_RunControlAcknowledge($sRequestId, $sAction, "no-op", "Engine is already idle")
				Return
			EndIf
			$g_bRunState = False
			$g_iBotAction = $eBotStop
			_RunControlAcknowledge($sRequestId, $sAction, "accepted", "Stop requested by control center")
		Case "pause"
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
			_RunControlAcknowledge($sRequestId, $sAction, "accepted", "Run paused by control center")
		Case "resume"
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
			_RunControlAcknowledge($sRequestId, $sAction, "accepted", "Run resumed by control center")
		Case Else
			_RunControlAcknowledge($sRequestId, $sAction, "rejected", "Unsupported control action")
	EndSwitch
EndFunc   ;==>_RunControlConsumeCommand

Func RunControlPoll()
	Static $bPolling = False
	If Not $g_bRunControlReady Or $bPolling Then Return
	$bPolling = True
	_RunControlConsumeCommand()
	RunControlWriteStatus()
	$bPolling = False
EndFunc   ;==>RunControlPoll

Func RunControlInitialize()
	$g_bRunControlReady = True
	$g_sRunControlMessage = "Native engine is ready"
	RunControlWriteStatus(True)
	; Idle startup can spend time outside the main sleep pump (browser launch, emulator checks,
	; notification setup). The lightweight registered poll keeps the browser heartbeat and Start
	; command responsive there; the re-entrancy guard in RunControlPoll serializes it with _Sleep.
	AdlibRegister("RunControlPoll", 500)
EndFunc   ;==>RunControlInitialize
