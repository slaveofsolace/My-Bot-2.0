; #FUNCTION# ====================================================================================================================
; Name ..........: MBRFunc, debugMBRFunctions
; Description ...: MBRFunc will open or close the MyBot.run.dll, debugMBRFunctions will set the debug levels.
; Syntax ........:
; Parameters ....:
; Return values .:
; Author ........: Didipe (2015)
; Modified ......: Hervidero (2015)
; Remarks .......: This file is part of MyBot, previously known as ClashGameBot. Copyright 2015-2025
;                  MyBot is distributed under the terms of the GNU GPL
; Related .......:
; Link ..........: https://github.com/MyBotRun/MyBot/wiki
; Example .......: No
; ===============================================================================================================================

Global $g_bLibMyBotInitialized = False
Global $g_bMBRFuncEngineAvailable = True
Global $g_sMBRFuncEngineProbeState = "not-run"
Global $g_sMBRFuncEngineError = ""
Global Const $g_sMBRFuncEngineMarkerName = "MyBot.run.txt"
Global Const $g_sMBRFuncEngineSupervisorSchema = "engine-init-supervisor-v1"
Global Const $g_sMBRFuncRuntimeLocalAppData = _MBRFuncRuntimeLocalAppDataDir()
Global Const $g_sMBRFuncEngineReceiptPath = $g_sMBRFuncRuntimeLocalAppData & "\My Bot 2.0\engine-init-owner-v1.json"
Global Const $g_sMBRFuncEngineTokenEnv = "MYBOT_ENGINE_INIT_TOKEN"
Global Const $g_sMBRFuncEngineLauncherPidEnv = "MYBOT_ENGINE_INIT_LAUNCHER_PID"
Global Const $g_sMBRFuncEngineLauncherCreatedEnv = "MYBOT_ENGINE_INIT_LAUNCHER_CREATED"

Func _MBRFuncCanonicalDirectory($sPath)
	If $sPath = "" Or Not FileExists($sPath) Or StringInStr(FileGetAttrib($sPath), "D") = 0 Then Return SetError(1, 0, "")
	Local $aAttributes = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $sPath)
	If @error Or Not IsArray($aAttributes) Or $aAttributes[0] = 0xFFFFFFFF Or BitAND($aAttributes[0], 0x400) <> 0 Then Return SetError(2, 0, "")
	Local $tFull = DllStructCreate("wchar[32768]")
	Local $aFull = DllCall("kernel32.dll", "dword", "GetFullPathNameW", "wstr", $sPath, "dword", 32768, "struct*", $tFull, "ptr", 0)
	If @error Or Not IsArray($aFull) Or $aFull[0] = 0 Or $aFull[0] >= 32768 Then Return SetError(3, 0, "")
	Local $sFull = DllStructGetData($tFull, 1)
	While StringLen($sFull) > 3 And StringRight($sFull, 1) = "\"
		$sFull = StringTrimRight($sFull, 1)
	WEnd
	Return SetError(0, 0, $sFull)
EndFunc   ;==>_MBRFuncCanonicalDirectory

Func _MBRFuncRuntimeLocalAppDataDir()
	If EnvGet("MYBOT_RUN_PYTHON_INTEGRATION") <> "1" Then Return @LocalAppDataDir
	Local $sTestRoot = _MBRFuncCanonicalDirectory(EnvGet("MYBOT_INSTALL_TEST_ROOT"))
	Local $iTestError = @error
	Local $sLocalRoot = _MBRFuncCanonicalDirectory(EnvGet("LOCALAPPDATA"))
	If $iTestError Or @error Or $sTestRoot = "" Or $sLocalRoot = "" Then Return @ScriptDir & "\.invalid-test-localappdata"
	Local $sPrefix = StringLower($sTestRoot & "\")
	If StringLeft(StringLower($sLocalRoot), StringLen($sPrefix)) <> $sPrefix Then Return @ScriptDir & "\.invalid-test-localappdata"
	Return $sLocalRoot
EndFunc   ;==>_MBRFuncRuntimeLocalAppDataDir
; Both the pinned Mini and backend capture the inherited launcher context into process-local globals,
; then immediately clear their environment. Mini restores only around its exact backend Run call.
Global $g_bMBRFuncEngineContextHost = StringRegExp(StringLower(@ScriptName), "^mybot\.run(?:\.minigui)?\.(?:exe|au3)$")
Global $g_bMBRFuncBackendHost = StringLower(@ScriptName) = "mybot.run.exe" Or StringLower(@ScriptName) = "mybot.run.au3"
Global $g_sMBRFuncEngineSupervisorToken = $g_bMBRFuncEngineContextHost ? EnvGet($g_sMBRFuncEngineTokenEnv) : ""
Global $g_sMBRFuncEngineLauncherPidText = $g_bMBRFuncEngineContextHost ? EnvGet($g_sMBRFuncEngineLauncherPidEnv) : ""
Global $g_sMBRFuncEngineLauncherCreated = $g_bMBRFuncEngineContextHost ? EnvGet($g_sMBRFuncEngineLauncherCreatedEnv) : ""
If $g_bMBRFuncEngineContextHost Then
	EnvSet($g_sMBRFuncEngineTokenEnv, "")
	EnvSet($g_sMBRFuncEngineLauncherPidEnv, "")
	EnvSet($g_sMBRFuncEngineLauncherCreatedEnv, "")
EndIf
Global $g_bMBRFuncEngineSupervisorValid = $g_bMBRFuncEngineContextHost And StringRegExp($g_sMBRFuncEngineSupervisorToken, "^[0-9a-f]{64}$") And _
	StringRegExp($g_sMBRFuncEngineLauncherPidText, "^[1-9][0-9]{0,9}$") And _
	StringRegExp($g_sMBRFuncEngineLauncherCreated, "^[0-9a-f]{16}$")
Global $g_iMBRFuncEngineReceiptSequence = 0
Global $g_sMBRFuncEngineReceiptHistory = ""
Global $g_sMBRFuncEngineReceiptStartRequestId = ""
Global $g_bMBRFuncEngineInitializing = False

Func MBRFuncManagedLaunchBound()
	Return $g_bMBRFuncBackendHost And $g_bMBRFuncEngineSupervisorValid
EndFunc   ;==>MBRFuncManagedLaunchBound

Func MBRFunc($Start = True, $bInitialize = True)
	Switch $Start
		Case True
			; Loading the mixed-mode image outside the launcher-owned Start boundary would let a
			; legacy configuration callback become the first CLR export with no receipt or timeout.
			If Not $bInitialize Then
				SetDebugLog("Managed engine library open deferred to supervised Start.")
				Return False
			EndIf
			Return MBRFuncInitialize()
		Case False
			If $g_hLibMyBot <> 0 And $g_hLibMyBot <> -1 Then DllClose($g_hLibMyBot)
			$g_hLibMyBot = -1
			$g_bLibMyBotInitialized = False
			$g_bMBRFuncEngineInitializing = False
			SetDebugLog($g_sMBRLib & " closed.")
	EndSwitch
EndFunc   ;==>MBRFunc

Func _MBRFuncOpenEngineLibrary()
	If $g_hLibMyBot <> 0 And $g_hLibMyBot <> -1 Then Return True
	RemoveZoneIdentifiers()
	$g_hLibMyBot = DllOpen($g_sLibMyBotPath)
	If $g_hLibMyBot = -1 Then
		SetLog($g_sMBRLib & " not found.", $COLOR_ERROR)
		Return False
	EndIf
	SetDebugLog($g_sMBRLib & " opened inside supervised Start.")
	Return True
EndFunc   ;==>_MBRFuncOpenEngineLibrary

; The mixed-mode DLL starts the CLR on its first exported call. Keep that unbounded work out of
; GUI startup: on affected Windows machines an antivirus/filter-driver stall would otherwise leave
; both the splash and main window permanently unresponsive. BotStart calls this explicit boundary.
Func MBRFuncInitialize($bDiscoverAndroid = True)
	Local $sMarkerError = ""
	If Not MBRFuncValidateEngineMarker($sMarkerError) Then Return False
	If $g_bLibMyBotInitialized Then Return True
	If Not $g_bMBRFuncEngineSupervisorValid Then
		MBRFuncMarkUnavailable("Managed engine supervisor context is missing or invalid; launch My Bot 2.0 from its installed launcher")
		Return False
	EndIf
	Local $sStartRequestId = _MBRFuncCurrentStartRequestId()
	If $sStartRequestId = "" Then
		MBRFuncMarkUnavailable("Managed engine Start ownership is missing or invalid")
		Return False
	EndIf
	; One immutable request id owns the entire generation. Stop may terminalize the native command
	; while a managed export is returning; re-reading live command state at each phase would then
	; corrupt the terminal receipt with an empty id before the launcher can finalize it.
	$g_sMBRFuncEngineReceiptStartRequestId = $sStartRequestId
	$g_iMBRFuncEngineReceiptSequence = 0
	$g_sMBRFuncEngineReceiptHistory = ""

	$g_sMBRFuncEngineProbeState = "running"
	If Not _MBRFuncPublishEngineReceipt("prepared") Then Return _MBRFuncInitializationFailed("Managed engine supervisor receipt could not be prepared")
	If Not _MBRFuncOpenEngineLibrary() Then Return _MBRFuncInitializationFailed("Managed engine library could not be opened")
	$g_bMBRFuncEngineInitializing = True
	If Not _MBRFuncPublishEngineReceipt("pool-entered") Then Return _MBRFuncInitializationFailed("Managed engine supervisor receipt could not publish pool-entered")
	If Not setProcessingPoolSize($g_iGlobalThreads) Then Return _MBRFuncInitializationFailed("Managed engine processing-pool initialization failed")
	If Not _MBRFuncPublishEngineReceipt("pool-returned") Then Return _MBRFuncInitializationFailed("Managed engine supervisor receipt could not publish pool-returned")
	If Not _MBRFuncPublishEngineReceipt("max-entered") Then Return _MBRFuncInitializationFailed("Managed engine supervisor receipt could not publish max-entered")
	If Not setMaxDegreeOfParallelism($g_iThreads) Then Return _MBRFuncInitializationFailed("Managed engine parallelism initialization failed")
	If Not _MBRFuncPublishEngineReceipt("max-returned") Then Return _MBRFuncInitializationFailed("Managed engine supervisor receipt could not publish max-returned")
	If Not _MBRFuncPublishEngineReceipt("android-entered") Then Return _MBRFuncInitializationFailed("Managed engine supervisor receipt could not publish android-entered")
	; The engine-only diagnostic must exercise the managed Android-binding export without
	; discovering, moving, hiding, initializing, or otherwise touching an emulator. Passing PID 0
	; is the engine's detached binding; normal Start retains the existing live PID discovery path.
	If $bDiscoverAndroid Then
		If Not setAndroidPID() Then Return _MBRFuncInitializationFailed("Managed engine Android binding failed")
	Else
		If Not setAndroidPID(0) Then Return _MBRFuncInitializationFailed("Managed engine detached Android binding failed")
	EndIf
	If Not _MBRFuncPublishEngineReceipt("android-returned") Then Return _MBRFuncInitializationFailed("Managed engine supervisor receipt could not publish android-returned")
	If Not _MBRFuncPublishEngineReceipt("gui-entered") Then Return _MBRFuncInitializationFailed("Managed engine supervisor receipt could not publish gui-entered")
	If Not SetBotGuiPID() Then Return _MBRFuncInitializationFailed("Managed engine GUI binding failed")
	$g_bLibMyBotInitialized = True
	$g_bMBRFuncEngineInitializing = False
	$g_bMBRFuncEngineAvailable = True
	$g_sMBRFuncEngineProbeState = "passed"
	$g_sMBRFuncEngineError = ""
	If Not _MBRFuncPublishEngineReceipt("initialized") Then Return _MBRFuncInitializationFailed("Managed engine supervisor receipt could not publish initialized")
	; PID 0 proves the managed ABI without attaching to an emulator, but it is not an operational
	; binding. Keep the warmed DLL resident and require the next normal Start to run the complete
	; supervised initialization again with a freshly discovered emulator PID.
	If Not $bDiscoverAndroid Then $g_bLibMyBotInitialized = False
	Return True
EndFunc   ;==>MBRFuncInitialize

Func MBRFuncEngineAvailable()
	Return $g_bMBRFuncEngineAvailable
EndFunc   ;==>MBRFuncEngineAvailable

Func MBRFuncEngineProbeState()
	Return $g_sMBRFuncEngineProbeState
EndFunc   ;==>MBRFuncEngineProbeState

Func MBRFuncEngineError()
	Return $g_sMBRFuncEngineError
EndFunc   ;==>MBRFuncEngineError

Func MBRFuncMarkUnavailable($sReason)
	$g_bMBRFuncEngineAvailable = False
	$g_sMBRFuncEngineProbeState = "failed"
	$g_sMBRFuncEngineError = $sReason
	; Mini GUI includes the engine wrapper without the run-event layer. Build the optional callback
	; name at runtime so Au3Check does not require that full-only function in reduced entry points.
	Local $sEventCallback = "RunEventLogEngine" & "Unavailable"
	; IsFunc() accepts a function value, not a string name. Call() is the supported dynamic
	; dispatch primitive and reports a missing callback as @error=0xDEAD/@extended=0xBEEF.
	Call($sEventCallback, $sReason)
EndFunc   ;==>MBRFuncMarkUnavailable

; MyBot.run.dll validates this upstream release marker when its managed image exports start.
; Reject a damaged checkout before invoking any export so the protected engine cannot fail later
; with a misleading image-location/copycat error.
Func MBRFuncValidateEngineMarker(ByRef $sError)
	Local $sMarkerPath = @ScriptDir & "\" & $g_sMBRFuncEngineMarkerName
	$sError = ""
	If Not FileExists($sMarkerPath) Then
		$sError = "Managed image engine unavailable: " & $g_sMBRFuncEngineMarkerName & " is missing; restore the empty release marker and restart My Bot 2.0"
		MBRFuncMarkUnavailable($sError)
		Return False
	EndIf

	Local $sMarkerAttributes = FileGetAttrib($sMarkerPath)
	If @error Or StringInStr($sMarkerAttributes, "D") > 0 Then
		$sError = "Managed image engine unavailable: " & $g_sMBRFuncEngineMarkerName & " must be a zero-byte file; restore the release marker and restart My Bot 2.0"
		MBRFuncMarkUnavailable($sError)
		Return False
	EndIf

	Local $iMarkerSize = FileGetSize($sMarkerPath)
	If @error Or $iMarkerSize <> 0 Then
		$sError = "Managed image engine unavailable: " & $g_sMBRFuncEngineMarkerName & " must be a zero-byte file; restore the release marker and restart My Bot 2.0"
		MBRFuncMarkUnavailable($sError)
		Return False
	EndIf
	Return True
EndFunc   ;==>MBRFuncValidateEngineMarker

Func _MBRFuncProcessCreationId($iPid)
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
EndFunc   ;==>_MBRFuncProcessCreationId

Func _MBRFuncParentPid($iPid)
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
EndFunc   ;==>_MBRFuncParentPid

Func _MBRFuncEngineReceiptPathSafe($bRequireReceipt = False)
	Local $sParent = $g_sMBRFuncRuntimeLocalAppData & "\My Bot 2.0"
	Local $aParent = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $sParent)
	If @error Or Not IsArray($aParent) Or $aParent[0] = 0xFFFFFFFF Then Return False
	If BitAND($aParent[0], 0x10) = 0 Or BitAND($aParent[0], 0x400) <> 0 Then Return False
	If Not FileExists($g_sMBRFuncEngineReceiptPath) Then Return Not $bRequireReceipt
	Local $aReceipt = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $g_sMBRFuncEngineReceiptPath)
	If @error Or Not IsArray($aReceipt) Or $aReceipt[0] = 0xFFFFFFFF Then Return False
	Return BitAND($aReceipt[0], 0x10) = 0 And BitAND($aReceipt[0], 0x400) = 0
EndFunc   ;==>_MBRFuncEngineReceiptPathSafe

Func _MBRFuncCurrentStartRequestId()
	Local $sCallback = "RunControlCurrentCommand" & "Id"
	Local $vRequestId = Call($sCallback)
	Local $iCallError = @error
	Local $iCallExtended = @extended
	If $iCallError = 0xDEAD And $iCallExtended = 0xBEEF Then Return ""
	If $iCallError Then Return ""
	Local $sRequestId = String($vRequestId)
	If Not StringRegExp($sRequestId, "^[A-Za-z0-9._-]{1,80}$") Then Return ""
	Return $sRequestId
EndFunc   ;==>_MBRFuncCurrentStartRequestId

Func _MBRFuncPublishEngineReceipt($sPhase)
	If Not StringRegExp($sPhase, "^(prepared|pool-entered|pool-returned|max-entered|max-returned|android-entered|android-returned|gui-entered|initialized|failed)$") Then Return False
	Local $iLauncherPid = Int($g_sMBRFuncEngineLauncherPidText)
	Local $iParentPid = _MBRFuncParentPid(@AutoItPID)
	Local $sLauncherCreated = _MBRFuncProcessCreationId($iLauncherPid)
	Local $sBackendCreated = _MBRFuncProcessCreationId(@AutoItPID)
	Local $sControllerCreated = _MBRFuncProcessCreationId($iParentPid)
	If $iLauncherPid <= 0 Or Not ProcessExists($iLauncherPid) Or $iParentPid <= 0 Or _
		$sLauncherCreated <> $g_sMBRFuncEngineLauncherCreated Or $sBackendCreated = "" Or $sControllerCreated = "" Then Return False
	$g_iMBRFuncEngineReceiptSequence += 1
	; Retain the complete monotonic phase chain in every receipt. A live evidence
	; observer may miss a short-lived intermediate replacement, but it must never
	; infer skipped phases from only the terminal number.
	Local $sCandidateHistory = $g_sMBRFuncEngineReceiptHistory
	If $sCandidateHistory = "" Then
		$sCandidateHistory = '["' & $sPhase & '"]'
	Else
		$sCandidateHistory = StringTrimRight($sCandidateHistory, 1) & ',"' & $sPhase & '"]'
	EndIf
	Local $sReceipt = '{"schema":"' & $g_sMBRFuncEngineSupervisorSchema & '","token":"' & $g_sMBRFuncEngineSupervisorToken & _
		'","launcher_pid":' & $iLauncherPid & ',"launcher_created":"' & $g_sMBRFuncEngineLauncherCreated & _
		'","controller_pid":' & $iParentPid & ',"controller_created":"' & $sControllerCreated & _
		'","backend_pid":' & @AutoItPID & ',"backend_created":"' & $sBackendCreated & _
		'","parent_pid":' & $iParentPid & ',"phase":"' & $sPhase & '","start_request_id":"' & _
		$g_sMBRFuncEngineReceiptStartRequestId & '","sequence":' & $g_iMBRFuncEngineReceiptSequence & _
		',"phase_history":' & $sCandidateHistory & '}'
	DirCreate($g_sMBRFuncRuntimeLocalAppData & "\My Bot 2.0")
	If Not _MBRFuncEngineReceiptPathSafe(False) Then Return False
	Local $sTemporary = $g_sMBRFuncEngineReceiptPath & ".tmp." & @AutoItPID
	If FileExists($sTemporary) Then FileDelete($sTemporary)
	If FileExists($sTemporary) Then Return False
	Local $hReceipt = FileOpen($sTemporary, 10)
	If $hReceipt = -1 Then Return False
	Local $bWritten = FileWrite($hReceipt, $sReceipt) = 1
	Local $bFlushed = FileFlush($hReceipt)
	FileClose($hReceipt)
	If Not $bWritten Or Not $bFlushed Or Not FileMove($sTemporary, $g_sMBRFuncEngineReceiptPath, 1) Then
		FileDelete($sTemporary)
		Return False
	EndIf
	If Not _MBRFuncEngineReceiptPathSafe(True) Then Return False
	If FileRead($g_sMBRFuncEngineReceiptPath) <> $sReceipt Then Return False
	$g_sMBRFuncEngineReceiptHistory = $sCandidateHistory
	Return True
EndFunc   ;==>_MBRFuncPublishEngineReceipt

Func _MBRFuncInitializationFailed($sReason)
	MBRFuncMarkUnavailable($sReason)
	_MBRFuncPublishEngineReceipt("failed")
	$g_bMBRFuncEngineInitializing = False
	$g_bLibMyBotInitialized = False
	If $g_hLibMyBot <> 0 And $g_hLibMyBot <> -1 Then DllClose($g_hLibMyBot)
	$g_hLibMyBot = -1
	Return False
EndFunc   ;==>_MBRFuncInitializationFailed

; The installed launcher supervises the real backend's first in-host managed call. This static gate
; only validates the release marker and inherited ownership context; it never runs a synthetic
; helper or invokes a stateful export in a second process.
Func MBRFuncProbeEngine(ByRef $sError, $iTimeoutMs = 15000)
	$sError = ""
	If Not MBRFuncValidateEngineMarker($sError) Then Return False
	If Not $g_bMBRFuncEngineAvailable Then
		$sError = $g_sMBRFuncEngineError
		Return False
	EndIf
	If Not $g_bMBRFuncEngineSupervisorValid Then
		$sError = "Managed engine supervisor context is missing or invalid; launch My Bot 2.0 from its installed launcher"
		MBRFuncMarkUnavailable($sError)
		Return False
	EndIf
	Return True
EndFunc   ;==>MBRFuncProbeEngine

Func DllCallMyBotIsActive()
	Return $g_bLibMyBotActive
EndFunc   ;==>DllCallMyBotIsActive

; Public DllCall MyBot.run.dll function call
Func DllCallMyBot($sFunc, $sType1 = Default, $vParam1 = Default, $sType2 = Default, $vParam2 = Default, $sType3 = Default, $vParam3 = Default, $sType4 = Default, $vParam4 = Default, $sType5 = Default, $vParam5 = Default _
		, $sType6 = Default, $vParam6 = Default, $sType7 = Default, $vParam7 = Default, $sType8 = Default, $vParam8 = Default, $sType9 = Default, $vParam9 = Default, $sType10 = Default, $vParam10 = Default)
	If Not $g_bLibMyBotInitialized Then
		Local $aUnavailable[1] = [""]
		Return SetError(1, 0, $aUnavailable)
	EndIf
	; This fork is not licensed to patch around the inherited recognizer's anti-copycat guard. Do not
	; invoke any public recognition export: it can generate and open lib/<message-id>.html. Callers
	; receive the same critical-error shape and must stop or use an independently implemented adapter.
	Local $aBlocked[1] = ["-2|Inherited ImgLoc recognition is disabled in this fork; licensed permission or a clean-room recognizer is required"]
	Return SetError(1, 0, $aBlocked)
EndFunc   ;==>DllCallMyBot

Func debugMBRFunctions($iDebugSearchArea = 0, $iDebugRedArea = 0, $iDebugOcr = 0)
	If Not $g_bLibMyBotInitialized And Not $g_bMBRFuncEngineInitializing Then Return False
	SetDebugLog("debugMBRFunctions: $iDebugSearchArea=" & $iDebugSearchArea & ", $iDebugRedArea=" & $iDebugRedArea & ", $giDebugOcr=" & $iDebugOcr)
	Local $activeHWnD = WinGetHandle("")
	Local $result = DllCall($g_hLibMyBot, "str", "setGlobalVar", "int", $iDebugSearchArea, "int", $iDebugRedArea, "int", $iDebugOcr)
	If @error Then
		_logErrorDLLCall($g_sLibMyBotPath & ", setGlobalVar:", @error)
		Return SetError(@error)
	EndIf
	;dll return 0 on success, -1 on error
	If IsArray($result) Then
		If $g_bDebugSetLog And $result[0] = -1 Then SetLog($g_sMBRLib & " error setting Global vars.", $COLOR_DEBUG)
	Else
		SetDebugLog($g_sMBRLib & " not found.", $COLOR_ERROR)
	EndIf
	WinActivate($activeHWnD) ; restore current active window
EndFunc   ;==>debugMBRFunctions

Func setAndroidPID($pid = GetAndroidPid())
	If Not $g_bLibMyBotInitialized And Not $g_bMBRFuncEngineInitializing Then Return False
	If $g_hLibMyBot = -1 Then Return False ; Bot didn't finish launch yet
	SetDebugLog("setAndroidPID: $pid=" & $pid)
	Local $result = DllCall($g_hLibMyBot, "str", "setAndroidPID", "int", $pid, "str", $g_sBotVersion, "str", $g_sAndroidEmulator, "str", $g_sAndroidVersion, "str", $g_sAndroidInstance)
	If @error Then
		_logErrorDLLCall($g_sLibMyBotPath & ", setAndroidPID:", @error)
		Return SetError(@error, 0, False)
	EndIf
	;dll return 0 on success, -1 on error
	If IsArray($result) Then
		If $result[0] = "" Then
			SetDebugLog($g_sMBRLib & " error setting Android PID.")
			Return False
		Else
			SetDebugLog("Android PID=" & $pid & " initialized: " & $result[0])
			debugMBRFunctions(0, $g_bDebugRedArea ? 1 : 0, $g_bDebugOcr ? 1 : 0) ; set debug levels
		EndIf
	Else
		SetDebugLog($g_sMBRLib & " not found.", $COLOR_ERROR)
		Return False
	EndIf
	Return True
EndFunc   ;==>setAndroidPID

Func SetBotGuiPID($pid = $g_iGuiPID)
	If Not $g_bLibMyBotInitialized And Not $g_bMBRFuncEngineInitializing Then Return False
	If $g_hLibMyBot = -1 Then Return False ; Bot didn't finish launch yet
	SetDebugLog("SetBotGuiPID: $pid=" & $pid)
	Local $result = DllCall($g_hLibMyBot, "str", "SetBotGuiPID", "int", $pid)
	If @error Then
		_logErrorDLLCall($g_sLibMyBotPath & ", SetBotGuiPID:", @error)
		Return SetError(@error, 0, False)
	EndIf
	;dll return 0 on success, -1 on error
	If IsArray($result) Then
		If $result[0] = "" Then
			SetDebugLog($g_sMBRLib & " error setting Android PID.")
			Return False
		Else
			SetDebugLog("Bot GUI PID=" & $pid & " initialized: " & $result[0])
			;debugMBRFunctions($g_iDebugSearchArea, $g_iDebugRedArea, $g_iDebugOcr) ; set debug levels
		EndIf
	Else
		SetDebugLog($g_sMBRLib & " not found.", $COLOR_ERROR)
		Return False
	EndIf
	Return True
EndFunc   ;==>SetBotGuiPID

Func CheckForumAuthentication()
	If Not $g_bLibMyBotInitialized Then Return -1
	If $g_hLibMyBot = -1 Then Return -1 ; Bot didn't finish launch yet
	Local $result = DllCall($g_hLibMyBot, "str", "CheckForumAuthentication")
	Local $iCallError = @error
	If $iCallError Then
		_logErrorDLLCall($g_sLibMyBotPath & ", CheckForumAuthentication:", $iCallError)
		Return SetError($iCallError, 0, -1)
	EndIf

	; 0 is deliberately reserved for an explicit upstream credential rejection.
	; Missing, malformed, or unexpected results are transient/unknown and must fail closed as -1.
	Local $iAuthenticated = _ForumAuthenticationStatusFromDllCall($result, $iCallError, True)
	If $iAuthenticated = 1 Then
		SetLog(GetTranslatedFileIni("MBR Authentication", "BotIsAuthenticated", "Upstream engine authenticated"), $COLOR_SUCCESS)
	Else
		SetLog(GetTranslatedFileIni("MBR Authentication", "BotIsNotAuthenticated", "Unable to authenticate the upstream image engine"), $COLOR_ERROR)
		If $iAuthenticated = -1 Then SetDebugLog("Forum authentication returned no usable status.", $COLOR_ERROR)
	EndIf
	Return $iAuthenticated
EndFunc   ;==>CheckForumAuthentication

Func _ForumAuthenticationStatusFromDllCall(ByRef $vResult, $iDllError, $bLibraryAvailable = True)
	If Not $bLibraryAvailable Or $iDllError <> 0 Or Not IsArray($vResult) Then Return -1
	If UBound($vResult, 0) <> 1 Or UBound($vResult) < 1 Then Return -1
	Return _ForumAuthenticationResponseStatus($vResult[0])
EndFunc   ;==>_ForumAuthenticationStatusFromDllCall

Func _ForumAuthenticationResponseStatus($vResponse)
	If Not IsString($vResponse) Then Return -1
	If StringInStr($vResponse, '"access_token"', 1) > 0 Then Return 1
	If StringInStr($vResponse, '"login_err_', 1) > 0 Then Return 0
	Return -1
EndFunc   ;==>_ForumAuthenticationResponseStatus

Func ForumLogin($sUsername, $sPassword)
	If Not $g_bLibMyBotInitialized Then Return False
	If $g_hLibMyBot = -1 Then Return False ; Bot didn't finish launch yet
	Local $result = DllCall($g_hLibMyBot, "str", "ForumLogin", "str", _Base64Encode(StringToBinary($sUsername, 4), 1024), "str", _Base64Encode(StringToBinary($sPassword, 4), 1024))
	If @error Then
		_logErrorDLLCall($g_sLibMyBotPath & ", ForumLogin:", @error)
		Return SetError(@error)
	EndIf
	;dll return string including access_token
	If IsArray($result) Then
		Local $iLoginStatus = _ForumAuthenticationResponseStatus($result[0])
		If $iLoginStatus = 1 Then
			SetDebugLog("Forum login successful, message length: " & StringLen($result[0]))
		ElseIf $iLoginStatus = 0 Then
			SetDebugLog("Forum login rejected by the upstream engine.")
		Else
			SetDebugLog("Forum login failed with an unexpected response (message length: " & StringLen($result[0]) & ").")
		EndIf
		Return $result[0]
	Else
		SetDebugLog($g_sMBRLib & " not found.", $COLOR_ERROR)
	EndIf
EndFunc   ;==>ForumLogin

Func setVillageOffset($x, $y, $z)
	If Not $g_bLibMyBotInitialized Then Return False
	DllCall($g_hLibMyBot, "str", "setVillageOffset", "int", $x, "int", $y, "float", $z)
	$g_iVILLAGE_OFFSET[0] = $x
	$g_iVILLAGE_OFFSET[1] = $y
	$g_iVILLAGE_OFFSET[2] = $z
EndFunc   ;==>setVillageOffset

Func setMaxDegreeOfParallelism($iMaxDegreeOfParallelism = 0)
	If Not $g_bLibMyBotInitialized And Not $g_bMBRFuncEngineInitializing Then Return False
	Local $i = Int($iMaxDegreeOfParallelism)
	If $i < 1 Then $i = 0
	SetDebugLog("Threading: Using " & $i & " threads for parallelism")
	If $i < 1 Then $i = -1
	Local $aResult = DllCall($g_hLibMyBot, "none", "setMaxDegreeOfParallelism", "int", $i) ;set PARALLELOPTIONS.MaxDegreeOfParallelism for multi-threaded operations
	If @error Or Not IsArray($aResult) Then Return False
	Return True
EndFunc   ;==>setMaxDegreeOfParallelism

Func setProcessingPoolSize($iProcessingPoolSize = 0)
	If Not $g_bLibMyBotInitialized And Not $g_bMBRFuncEngineInitializing Then Return False
	Local $i = Int($iProcessingPoolSize)
	; Zero means Automatic in the profile. The managed library already owns that default. Calling the
	; optional tuning export for Automatic has blocked inside the CLR with both the inherited -1
	; sentinel and an explicit processor count, so leave the default untouched. Explicit positive
	; user overrides still cross the supervised export boundary exactly once.
	If $i < 1 Then
		SetDebugLog("Threading: Using the managed engine default processing pool (automatic)")
		Return True
	EndIf
	SetDebugLog("Threading: Using " & $i & " threads shared across all bot instances (explicit)")
	Local $aResult = DllCall($g_hLibMyBot, "none", "setProcessingPoolSize", "int", $i) ;set ProcessingPoolSize for multi-threaded operations (global number of used threads for ImgLoc for all bot instances)
	If @error Or Not IsArray($aResult) Then Return False
	Return True
EndFunc   ;==>setProcessingPoolSize

Func setGcCollectTotalMemoryPreasure($iGcCollectTotalMemoryPreasure = 0)
	If Not $g_bLibMyBotInitialized Then Return False
	DllCall($g_hLibMyBot, "none", "setGcCollectTotalMemoryPreasure", "int", $iGcCollectTotalMemoryPreasure) ;set Heap preasure, when exceeded, calls GC.Collect() in ImageDispose, 0 to disable, 32 * 1024 * 1024 (32MB) good value to keep heap small
EndFunc   ;==>setGcCollectTotalMemoryPreasure

Func ConvertVillagePos(ByRef $x, ByRef $y, $zoomfactor = 0)
	If Not $g_bLibMyBotInitialized Then Return
	If $g_hLibMyBot = -1 Then Return ; Bot didn't finish launch yet
	Local $result = DllCall($g_hLibMyBot, "str", "ConvertVillagePos", "int", $x, "int", $y, "float", $zoomfactor)
	If IsArray($result) = False Then
		If $g_bDebugSetLog Then SetDebugLog("ConvertVillagePos result error", $COLOR_ERROR)
		Return ;exit if
	EndIf
	Local $a = StringSplit($result[0], "|")
	If UBound($a) < 3 Then Return
	$x = Int($a[1])
	$y = Int($a[2])
EndFunc   ;==>ConvertVillagePos

Func ConvertToVillagePos(ByRef $x, ByRef $y, $zoomfactor = 0)
	If Not $g_bLibMyBotInitialized Then Return
	If $g_hLibMyBot = -1 Then Return ; Bot didn't finish launch yet
	Local $result = DllCall($g_hLibMyBot, "str", "ConvertToVillagePos", "int", $x, "int", $y, "float", $zoomfactor)
	If IsArray($result) = False Then
		If $g_bDebugSetLog Then SetDebugLog("ConvertToVillagePos result error", $COLOR_ERROR)
		Return ;exit if
	EndIf
	Local $a = StringSplit($result[0], "|")
	If UBound($a) < 3 Then Return
	$x = Int($a[1])
	$y = Int($a[2])
EndFunc   ;==>ConvertToVillagePos

Func ConvertFromVillagePos(ByRef $x, ByRef $y)
	If Not $g_bLibMyBotInitialized Then Return
	If $g_hLibMyBot = -1 Then Return ; Bot didn't finish launch yet
	Local $result = DllCall($g_hLibMyBot, "str", "ConvertFromVillagePos", "int", $x, "int", $y)
	If IsArray($result) = False Then
		If $g_bDebugSetLog Then SetDebugLog("ConvertVillagePos result error", $COLOR_ERROR)
		Return ;exit if
	EndIf
	Local $a = StringSplit($result[0], "|")
	If UBound($a) < 3 Then Return
	$x = Int($a[1])
	$y = Int($a[2])
EndFunc   ;==>ConvertFromVillagePos

Func ReduceBotMemory($bDisposeCaptures = True)
	If $bDisposeCaptures = True Then _CaptureDispose()
	If $g_iEmptyWorkingSetBot > 0 Then _WinAPI_EmptyWorkingSet(@AutoItPID) ; Reduce Working Set of Bot
	;DllCall($g_hLibMyBot, "none", "gc") ; run .net garbage collection
EndFunc   ;==>ReduceBotMemory

Func RemoveZoneIdentifiers()
	; remove the Zone.Identifier from any exe or dll
	Local $aPaths = [@ScriptDir, $g_sLibPath, $g_sLibPath & "\adb", $g_sLibPath & "\curl"]
	For $i = 0 To UBound($aPaths) - 1
		Local $sPath = $aPaths[$i]
		Local $aFiles = _FileListToArray($sPath, "*", $FLTA_FILES, True)
		For $j = 1 To $aFiles[0]
			If StringRegExp($aFiles[$j], ".+[.](exe|dll)$") Then
				Local $sStream = $aFiles[$j] & ":Zone.Identifier:$DATA"
				Local $h = _WinAPI_CreateFile($sStream, 2, 2)
				If $h Then
					_WinAPI_CloseHandle($h)
					If _WinAPI_DeleteFile($sStream) Then
						SetDebugLog("Removed Zone.Identifier from file: " & $sStream)
					Else
						SetDebugLog("Failed to remove Zone.Identifier from file: " & $sStream, $COLOR_ERROR)
					EndIf
				EndIf
			EndIf
		Next
	Next
EndFunc   ;==>RemoveZoneIdentifiers
