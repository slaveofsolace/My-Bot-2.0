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

Func MBRFunc($Start = True, $bInitialize = True)
	Switch $Start
		Case True
			RemoveZoneIdentifiers()
			$g_hLibMyBot = DllOpen($g_sLibMyBotPath)
			If $g_hLibMyBot = -1 Then
				SetLog($g_sMBRLib & " not found.", $COLOR_ERROR)
				Return False
			EndIf
			SetDebugLog($g_sMBRLib & " opened.")
			If $bInitialize Then Return MBRFuncInitialize()
			Return True
		Case False
			DllClose($g_hLibMyBot)
			$g_bLibMyBotInitialized = False
			SetDebugLog($g_sMBRLib & " closed.")
	EndSwitch
EndFunc   ;==>MBRFunc

; The mixed-mode DLL starts the CLR on its first exported call. Keep that unbounded work out of
; GUI startup: on affected Windows machines an antivirus/filter-driver stall would otherwise leave
; both the splash and main window permanently unresponsive. BotStart calls this explicit boundary.
Func MBRFuncInitialize()
	If $g_bLibMyBotInitialized Then Return True
	If $g_hLibMyBot = 0 Or $g_hLibMyBot = -1 Then Return False

	If Not setProcessingPoolSize($g_iGlobalThreads) Then Return False
	If Not setMaxDegreeOfParallelism($g_iThreads) Then Return False
	If Not setAndroidPID() Then Return False
	If Not SetBotGuiPID() Then Return False
	$g_bLibMyBotInitialized = True
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
	If IsFunc("RunEventLogEngineUnavailable") Then Call("RunEventLogEngineUnavailable", $sReason)
EndFunc   ;==>MBRFuncMarkUnavailable

; Starts the mixed-mode DLL in an isolated x86 helper first. A filter-driver or CLR stall can then
; freeze only the helper, which is terminated at the bounded deadline while the GUI keeps pumping.
Func MBRFuncProbeEngine(ByRef $sError, $iTimeoutMs = 15000)
	$sError = ""
	If $g_sMBRFuncEngineProbeState = "passed" Then Return True
	If Not $g_bMBRFuncEngineAvailable Then
		$sError = $g_sMBRFuncEngineError
		Return False
	EndIf

	Local $sHelper = @ScriptDir & "\MyBot.run.EngineProbe.exe"
	If Not FileExists($sHelper) Then
		$sError = "Managed engine probe helper is missing; rebuild or reinstall My Bot 2.0"
		MBRFuncMarkUnavailable($sError)
		Return False
	EndIf

	Local $sToken = @ScriptDir & "\config\engine-probe-" & @AutoItPID & ".ok"
	FileDelete($sToken)
	$g_sMBRFuncEngineProbeState = "running"
	Local $iProbePid = Run('"' & $sHelper & '" "' & $sToken & '"', @ScriptDir, @SW_HIDE)
	If @error Or $iProbePid <= 0 Then
		$sError = "Managed engine probe could not be started"
		MBRFuncMarkUnavailable($sError)
		Return False
	EndIf

	Local $hProbeTimer = __TimerInit()
	Local $bProbeExited = False
	While __TimerDiff($hProbeTimer) < $iTimeoutMs
		If FileExists($sToken) Then
			Local $sResult = StringStripWS(FileRead($sToken), $STR_STRIPALL)
			FileDelete($sToken)
			If $sResult = "ok" Then
				$g_bMBRFuncEngineAvailable = True
				$g_sMBRFuncEngineProbeState = "passed"
				$g_sMBRFuncEngineError = ""
				Return True
			EndIf
		EndIf
		If Not ProcessExists($iProbePid) Then
			$bProbeExited = True
			ExitLoop
		EndIf
		If $g_iBotAction = $eBotStop Or $g_iBotAction = $eBotClose Then
			ProcessClose($iProbePid)
			ProcessWaitClose($iProbePid, 2)
			FileDelete($sToken)
			$sError = "Engine start was cancelled"
			$g_sMBRFuncEngineProbeState = "not-run"
			Return False
		EndIf
		_Sleep(100, True, False)
	WEnd

	If ProcessExists($iProbePid) Then
		ProcessClose($iProbePid)
		ProcessWaitClose($iProbePid, 2)
	EndIf
	FileDelete($sToken)
	If $bProbeExited Then
		$sError = "Managed engine startup failed; check Windows Security and .NET health, then restart My Bot 2.0"
	Else
		$sError = "Managed engine did not answer within " & Int($iTimeoutMs / 1000) & " seconds; check Windows Security and .NET health, then restart My Bot 2.0"
	EndIf
	MBRFuncMarkUnavailable($sError)
	Return False
EndFunc   ;==>MBRFuncProbeEngine

; Private DllCall MyBot.run.dll function call
Func _DllCallMyBot($sFunc, $sType1 = Default, $vParam1 = Default, $sType2 = Default, $vParam2 = Default, $sType3 = Default, $vParam3 = Default, $sType4 = Default, $vParam4 = Default, $sType5 = Default, $vParam5 = Default _
		, $sType6 = Default, $vParam6 = Default, $sType7 = Default, $vParam7 = Default, $sType8 = Default, $vParam8 = Default, $sType9 = Default, $vParam9 = Default, $sType10 = Default, $vParam10 = Default)
	If $sType1 = Default Then Return DllCall($g_hLibMyBot, "str", $sFunc)
	If $sType2 = Default Then Return DllCall($g_hLibMyBot, "str", $sFunc, $sType1, $vParam1)
	If $sType3 = Default Then Return DllCall($g_hLibMyBot, "str", $sFunc, $sType1, $vParam1, $sType2, $vParam2)
	If $sType4 = Default Then Return DllCall($g_hLibMyBot, "str", $sFunc, $sType1, $vParam1, $sType2, $vParam2, $sType3, $vParam3)
	If $sType5 = Default Then Return DllCall($g_hLibMyBot, "str", $sFunc, $sType1, $vParam1, $sType2, $vParam2, $sType3, $vParam3, $sType4, $vParam4)
	If $sType6 = Default Then Return DllCall($g_hLibMyBot, "str", $sFunc, $sType1, $vParam1, $sType2, $vParam2, $sType3, $vParam3, $sType4, $vParam4, $sType5, $vParam5)
	If $sType7 = Default Then Return DllCall($g_hLibMyBot, "str", $sFunc, $sType1, $vParam1, $sType2, $vParam2, $sType3, $vParam3, $sType4, $vParam4, $sType5, $vParam5, $sType6, $vParam6)
	If $sType8 = Default Then Return DllCall($g_hLibMyBot, "str", $sFunc, $sType1, $vParam1, $sType2, $vParam2, $sType3, $vParam3, $sType4, $vParam4, $sType5, $vParam5, $sType6, $vParam6, $sType7, $vParam7)
	If $sType9 = Default Then Return DllCall($g_hLibMyBot, "str", $sFunc, $sType1, $vParam1, $sType2, $vParam2, $sType3, $vParam3, $sType4, $vParam4, $sType5, $vParam5, $sType6, $vParam6, $sType7, $vParam7, $sType8, $vParam8)
	If $sType10 = Default Then Return DllCall($g_hLibMyBot, "str", $sFunc, $sType1, $vParam1, $sType2, $vParam2, $sType3, $vParam3, $sType4, $vParam4, $sType5, $vParam5, $sType6, $vParam6, $sType7, $vParam7, $sType8, $vParam8, $sType9, $vParam9)
	Return DllCall($g_hLibMyBot, "str", $sFunc, $sType1, $vParam1, $sType2, $vParam2, $sType3, $vParam3, $sType4, $vParam4, $sType5, $vParam5, $sType6, $vParam6, $sType7, $vParam7, $sType8, $vParam8, $sType9, $vParam9, $sType10, $vParam10)
EndFunc   ;==>_DllCallMyBot

Func DllCallMyBotIsActive()
	Return $g_bLibMyBotActive
EndFunc   ;==>DllCallMyBotIsActive

; Public DllCall MyBot.run.dll function call
Func DllCallMyBot($sFunc, $sType1 = Default, $vParam1 = Default, $sType2 = Default, $vParam2 = Default, $sType3 = Default, $vParam3 = Default, $sType4 = Default, $vParam4 = Default, $sType5 = Default, $vParam5 = Default _
		, $sType6 = Default, $vParam6 = Default, $sType7 = Default, $vParam7 = Default, $sType8 = Default, $vParam8 = Default, $sType9 = Default, $vParam9 = Default, $sType10 = Default, $vParam10 = Default)
	$g_bLibMyBotActive = True
	Local $aResult
	Local $sFileOrFolder = Default
	Switch $sFunc
		Case "SearchMultipleTilesBetweenLevels", "FindTile", "SearchTile", "SearchMultipleTilesLevel", "SearchMultipleTiles", "RecheckTile", "DoOCR"
			If StringLeft($vParam2, 1) <> "-" Then
				$sFileOrFolder = $vParam2
				$vParam2 = "-" & _Base64Encode(StringToBinary($vParam2, 4), 1024) ; support umlauts using Base64 UTF-8
			EndIf
	EndSwitch
	If $g_bDebugBetaVersion And $sFileOrFolder <> Default And StringInStr($sFileOrFolder, "\") And FileExists($sFileOrFolder) = 0 Then SetLog("Cannot access path: " & $sFileOrFolder, $COLOR_ERROR)
	; suspend Android now
	Local $bWasSuspended = SuspendAndroid()
	$aResult = _DllCallMyBot($sFunc, $sType1, $vParam1, $sType2, $vParam2, $sType3, $vParam3, $sType4, $vParam4, $sType5, $vParam5, $sType6, $vParam6, $sType7, $vParam7, $sType8, $vParam8, $sType9, $vParam9, $sType10, $vParam10)
	Local $error = @error
	Local $i = 1
	While Not $error And $aResult[0] = "<GetAsyncResult>"
		; when receiving "<GetAsyncResult>", dll waited already 100ms, and android should be resumed after 500ms for 100ms
		If Mod($i + 5, 10) = 0 Then
			SetDebugLog("Waiting for DLL async function " & $sFunc & " ...")
			ResumeAndroid()
		EndIf
		$i += 1
		If _Sleep(100) Then
			ResumeAndroid()
			$aResult[0] = ""
			$g_bLibMyBotActive = False
			Return SetError(0, 0, $aResult)
		EndIf
		SuspendAndroid()
		$aResult = _DllCallMyBot("GetAsyncResult")
		$error = @error
	WEnd

	; resume Android again (if it was not already suspended)
	SuspendAndroid($bWasSuspended)
	$g_bLibMyBotActive = False
	Return SetError($error, @extended, $aResult)
EndFunc   ;==>DllCallMyBot

Func debugMBRFunctions($iDebugSearchArea = 0, $iDebugRedArea = 0, $iDebugOcr = 0)
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
	If $g_hLibMyBot = -1 Then Return False ; Bot didn't finish launch yet
	Local $result = DllCall($g_hLibMyBot, "str", "CheckForumAuthentication")
	If @error Then
		_logErrorDLLCall($g_sLibMyBotPath & ", CheckForumAuthentication:", @error)
		Return SetError(@error)
	EndIf
	;dll return string including access_token
	Local $iAuthenticated = 0 ; 0 = not authenticated (username or password incorrect), 1 = authenticated, -1 = not authenticated (unknown error)
	If IsArray($result) Then
		If StringInStr($result[0], '"access_token"') > 0 Then
			SetLog(GetTranslatedFileIni("MBR Authentication", "BotIsAuthenticated", "MyBot.run is authenticated"), $COLOR_SUCCESS)
			$iAuthenticated = 1
		Else
			SetLog(GetTranslatedFileIni("MBR Authentication", "BotIsNotAuthenticated", "Error authenticating Mybot.run"), $COLOR_ERROR)
			If StringInStr($result[0], '"login_err_') > 0 Then
				; username or password incorrect
				$iAuthenticated = 0
			Else
				; unknown error
				$iAuthenticated = -1
			EndIf
		EndIf
	Else
		SetDebugLog($g_sMBRLib & " not found.", $COLOR_ERROR)
	EndIf
	Return $iAuthenticated
EndFunc   ;==>CheckForumAuthentication

Func ForumLogin($sUsername, $sPassword)
	If $g_hLibMyBot = -1 Then Return False ; Bot didn't finish launch yet
	Local $result = DllCall($g_hLibMyBot, "str", "ForumLogin", "str", _Base64Encode(StringToBinary($sUsername, 4), 1024), "str", _Base64Encode(StringToBinary($sPassword, 4), 1024))
	If @error Then
		_logErrorDLLCall($g_sLibMyBotPath & ", ForumLogin:", @error)
		Return SetError(@error)
	EndIf
	;dll return string including access_token
	If IsArray($result) Then
		If StringInStr($result[0], '"access_token"') > 0 Then
			SetDebugLog("Forum login successful, message length: " & StringLen($result[0]))
			Return $result[0]
		Else
			SetDebugLog("Forum login failed, message: " & $result[0])
			Return $result[0]
		EndIf
	Else
		SetDebugLog($g_sMBRLib & " not found.", $COLOR_ERROR)
	EndIf
EndFunc   ;==>ForumLogin

Func setVillageOffset($x, $y, $z)
	DllCall($g_hLibMyBot, "str", "setVillageOffset", "int", $x, "int", $y, "float", $z)
	$g_iVILLAGE_OFFSET[0] = $x
	$g_iVILLAGE_OFFSET[1] = $y
	$g_iVILLAGE_OFFSET[2] = $z
EndFunc   ;==>setVillageOffset

Func setMaxDegreeOfParallelism($iMaxDegreeOfParallelism = 0)
	Local $i = Int($iMaxDegreeOfParallelism)
	If $i < 1 Then $i = 0
	SetDebugLog("Threading: Using " & $i & " threads for parallelism")
	If $i < 1 Then $i = -1
	Local $aResult = DllCall($g_hLibMyBot, "none", "setMaxDegreeOfParallelism", "int", $i) ;set PARALLELOPTIONS.MaxDegreeOfParallelism for multi-threaded operations
	If @error Or Not IsArray($aResult) Then Return False
	Return True
EndFunc   ;==>setMaxDegreeOfParallelism

Func setProcessingPoolSize($iProcessingPoolSize = 0)
	Local $i = Int($iProcessingPoolSize)
	If $i < 1 Then $i = 0
	SetDebugLog("Threading: Using " & $i & " threads shared across all bot instances")
	If $i < 1 Then $i = -1
	Local $aResult = DllCall($g_hLibMyBot, "none", "setProcessingPoolSize", "int", $i) ;set ProcessingPoolSize for multi-threaded operations (global number of used threads for ImgLoc for all bot instances)
	If @error Or Not IsArray($aResult) Then Return False
	Return True
EndFunc   ;==>setProcessingPoolSize

Func setGcCollectTotalMemoryPreasure($iGcCollectTotalMemoryPreasure = 0)
	DllCall($g_hLibMyBot, "none", "setGcCollectTotalMemoryPreasure", "int", $iGcCollectTotalMemoryPreasure) ;set Heap preasure, when exceeded, calls GC.Collect() in ImageDispose, 0 to disable, 32 * 1024 * 1024 (32MB) good value to keep heap small
EndFunc   ;==>setGcCollectTotalMemoryPreasure

Func ConvertVillagePos(ByRef $x, ByRef $y, $zoomfactor = 0)
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
