; #FUNCTION# ====================================================================================================================
; Name ..........: MBR GUI Control Run Planner
; Description ...: Reads the Run Planner controls and turns them into a run intent the engine can act on.
; Remarks .......: This is the whole engine boundary for the planner: the GUI never touches battle code directly, it builds a
;                  RunIntent and reports what the engine says about it. This file is part of My Bot, distributed under the GNU GPL.
; ===============================================================================================================================
#include-once
#include <Crypt.au3>
#include "MBR GUI Design Run Planner.au3"
#include "..\functions\Run\RunIntent.au3"
#include "..\functions\Run\RunPlanFile.au3"
#include "..\functions\Run\RunEventLog.au3"
#include "..\functions\Run\RunExecutionContract.au3"

Global Const $RUN_PLANNER_URL = "http://127.0.0.1:8765/"
Global Const $RUN_PLANNER_HEALTH_URL = "http://127.0.0.1:8765/api/health"

; What /api/health has to say before this build will talk to the service. tools/check_plan_bridge.py
; compares these two against the values tools/planner_ui.py actually serves, because a bridge version
; bumped on one side and not the other would otherwise leave the GUI reporting "unavailable" forever
; with a healthy service running in front of it.
Global Const $RUN_PLANNER_SERVICE_NAME = "my-bot-control-center"
Global Const $RUN_PLANNER_BRIDGE_VERSION = "autoit-control-file-v1"
Global Const $RUN_PLANNER_HEALTH_PROTOCOL = "my-bot-control-center-health-v2"
Global Const $RUN_PLANNER_OWNERSHIP_SCHEMA = "my-bot-planner-owner-v1"
Global Const $RUN_PLANNER_OWNERSHIP_RECEIPT = $g_sMBRFuncRuntimeLocalAppData & "\My Bot 2.0\planner-owner-v1.json"
Global $g_oRunPlannerIntent = 0
Global $g_sRunPlannerHeroIds = ""
Global $g_iRunPlannerObservedServicePid = 0
Global $g_sRunPlannerObservedOwnerToken = ""
Global $g_iRunPlannerOwnedServicePid = 0
Global $g_sRunPlannerOwnedServiceToken = ""

; Change token of the plan file as of the last time it was read into the controls. Empty means never read, or no file.
Global $g_sRunPlannerPlanFileStamp = ""
Global $g_sRunPlannerPlanFileNote = ""

; The payload is parsed rather than pattern-matched. Substring checks made this depend on the exact
; spacing json.dumps happens to emit: switching the server to compact separators, or adding an indent,
; would silently report a perfectly healthy service as unavailable with nothing to show why.
Func _RunPlannerNormalizeRoot($sRoot)
	Local $sNormalized = StringLower(StringReplace(StringStripWS(String($sRoot), $STR_STRIPLEADING + $STR_STRIPTRAILING), "/", "\"))
	While StringLen($sNormalized) > 3 And StringRight($sNormalized, 1) = "\"
		$sNormalized = StringTrimRight($sNormalized, 1)
	WEnd
	Return $sNormalized
EndFunc   ;==>_RunPlannerNormalizeRoot

Func _RunPlannerScriptBuildHash()
	Local $sScript = @ScriptDir & "\tools\planner_ui.py"
	If Not FileExists($sScript) Then Return ""
	Local $vHash = _Crypt_HashFile($sScript, $CALG_SHA_256)
	If @error Or Not IsBinary($vHash) Then Return ""
	Return StringLower(StringTrimLeft(String($vHash), 2))
EndFunc   ;==>_RunPlannerScriptBuildHash

Func _RunPlannerHashText($sText)
	Local $vHash = _Crypt_HashData(StringToBinary(String($sText), 4), $CALG_SHA_256)
	If @error Or Not IsBinary($vHash) Then Return ""
	Return StringLower(StringTrimLeft(String($vHash), 2))
EndFunc   ;==>_RunPlannerHashText

Func _RunPlannerPathToken($sPath)
	Local $sEncoded = _Base64Encode(StringToBinary(String($sPath), 4), 0)
	If @error Then Return ""
	$sEncoded = StringReplace(StringReplace($sEncoded, @CR, ""), @LF, "")
	$sEncoded = StringReplace(StringReplace($sEncoded, "+", "-"), "/", "_")
	Return StringRegExpReplace($sEncoded, "=+$", "")
EndFunc   ;==>_RunPlannerPathToken

; A PID is not an identity: Windows may reuse it. Pair it with the kernel creation FILETIME and
; compare the pair immediately before any close.
Func _RunPlannerProcessCreationId($iPid)
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
EndFunc   ;==>_RunPlannerProcessCreationId

Func _RunPlannerProcessImagePath($iPid)
	Local $aOpen = DllCall("kernel32.dll", "handle", "OpenProcess", "dword", 0x1000, "bool", False, "dword", $iPid)
	If @error Or Not IsArray($aOpen) Or Not $aOpen[0] Then Return ""
	Local $hProcess = $aOpen[0]
	Local $tPath = DllStructCreate("wchar[32768]")
	Local $aQuery = DllCall("kernel32.dll", "bool", "QueryFullProcessImageNameW", "handle", $hProcess, "dword", 0, _
		"struct*", $tPath, "dword*", 32768)
	DllCall("kernel32.dll", "bool", "CloseHandle", "handle", $hProcess)
	If @error Or Not IsArray($aQuery) Or Not $aQuery[0] Then Return ""
	Return DllStructGetData($tPath, 1)
EndFunc   ;==>_RunPlannerProcessImagePath

Func _RunPlannerParentPid($iPid)
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
EndFunc   ;==>_RunPlannerParentPid

Func _RunPlannerReceiptString($sReceipt, $sName)
	Local $aValue = StringRegExp($sReceipt, '"' & $sName & '"\s*:\s*"([A-Za-z0-9_-]+)"', $STR_REGEXPARRAYMATCH)
	If @error Or Not IsArray($aValue) Or UBound($aValue) <> 1 Then Return ""
	Return $aValue[0]
EndFunc   ;==>_RunPlannerReceiptString

Func _RunPlannerReceiptInt($sReceipt, $sName)
	Local $aValue = StringRegExp($sReceipt, '"' & $sName & '"\s*:\s*([0-9]+)', $STR_REGEXPARRAYMATCH)
	If @error Or Not IsArray($aValue) Or UBound($aValue) <> 1 Then Return 0
	Return Int($aValue[0])
EndFunc   ;==>_RunPlannerReceiptInt

Func _RunPlannerReadOwnershipReceipt()
	If Not FileExists($RUN_PLANNER_OWNERSHIP_RECEIPT) Then Return ""
	If Not _RunPlannerReceiptPathSafe(True) Then Return ""
	Local $sReceipt = FileRead($RUN_PLANNER_OWNERSHIP_RECEIPT)
	If @error Or StringLen($sReceipt) > 4096 Then Return ""
	Return $sReceipt
EndFunc   ;==>_RunPlannerReadOwnershipReceipt

Func _RunPlannerReceiptPathSafe($bRequireReceipt = False)
	Local $sParent = $g_sMBRFuncRuntimeLocalAppData & "\My Bot 2.0"
	Local $aParent = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $sParent)
	If @error Or Not IsArray($aParent) Or $aParent[0] = 0xFFFFFFFF Then Return False
	If BitAND($aParent[0], 0x10) = 0 Or BitAND($aParent[0], 0x400) <> 0 Then Return False
	If Not FileExists($RUN_PLANNER_OWNERSHIP_RECEIPT) Then Return Not $bRequireReceipt
	Local $aReceipt = DllCall("kernel32.dll", "dword", "GetFileAttributesW", "wstr", $RUN_PLANNER_OWNERSHIP_RECEIPT)
	If @error Or Not IsArray($aReceipt) Or $aReceipt[0] = 0xFFFFFFFF Then Return False
	Return BitAND($aReceipt[0], 0x10) = 0 And BitAND($aReceipt[0], 0x400) = 0
EndFunc   ;==>_RunPlannerReceiptPathSafe

Func _RunPlannerReceiptOwnedByCurrentBackend($sReceipt, $iPid, $sOwnerToken)
	If _RunPlannerReceiptString($sReceipt, "schema") <> $RUN_PLANNER_OWNERSHIP_SCHEMA Then Return False
	If _RunPlannerReceiptString($sReceipt, "token") <> $sOwnerToken Then Return False
	If _RunPlannerReceiptString($sReceipt, "health_token") <> _RunPlannerHashText($sOwnerToken) Then Return False
	If _RunPlannerReceiptInt($sReceipt, "service_pid") <> $iPid Then Return False
	If _RunPlannerReceiptInt($sReceipt, "backend_pid") <> @AutoItPID Then Return False
	If _RunPlannerReceiptString($sReceipt, "backend_created") <> _RunPlannerProcessCreationId(@AutoItPID) Then Return False
	Return True
EndFunc   ;==>_RunPlannerReceiptOwnedByCurrentBackend

Func _RunPlannerReceiptMatchesLiveService($sReceipt, $iPid, $sOwnerToken)
	If Not _RunPlannerReceiptOwnedByCurrentBackend($sReceipt, $iPid, $sOwnerToken) Then Return False
	If Not ProcessExists($iPid) Then Return False
	If _RunPlannerReceiptString($sReceipt, "service_created") <> _RunPlannerProcessCreationId($iPid) Then Return False
	If _RunPlannerReceiptInt($sReceipt, "parent_pid") <> @AutoItPID Or _RunPlannerParentPid($iPid) <> @AutoItPID Then Return False
	Local $sImage = _RunPlannerProcessImagePath($iPid)
	If Not StringRegExp(StringLower($sImage), "\\pythonw\.exe$") Then Return False
	If _RunPlannerReceiptString($sReceipt, "python_image_token") <> _RunPlannerPathToken($sImage) Then Return False
	If _RunPlannerReceiptString($sReceipt, "script_path_token") <> _RunPlannerPathToken(@ScriptDir & "\tools\planner_ui.py") Then Return False
	If _RunPlannerReceiptString($sReceipt, "profiles_root_token") <> _RunPlannerPathToken($g_sProfilePath) Then Return False
	If _RunPlannerReceiptString($sReceipt, "build_sha256") <> _RunPlannerScriptBuildHash() Then Return False
	Local $sCommand = ProcessGetCommandLine($iPid)
	If @error Or $sCommand = "" Or $sCommand = "-1" Then Return False
	If _RunPlannerReceiptString($sReceipt, "command_sha256") <> _RunPlannerHashText($sCommand) Then Return False
	If StringInStr($sCommand, '"' & @ScriptDir & '\tools\planner_ui.py"') = 0 Then Return False
	If StringInStr($sCommand, '--owner-token "' & $sOwnerToken & '"') = 0 Then Return False
	If StringInStr($sCommand, '--profiles-root "' & $g_sProfilePath & '"') = 0 Then Return False
	Return True
EndFunc   ;==>_RunPlannerReceiptMatchesLiveService

Func _RunPlannerWriteOwnershipReceipt($iPid, $sOwnerToken, $sExpectedCommand)
	Local $sServiceCreated = _RunPlannerProcessCreationId($iPid)
	Local $sBackendCreated = _RunPlannerProcessCreationId(@AutoItPID)
	Local $iParentPid = _RunPlannerParentPid($iPid)
	Local $sImage = _RunPlannerProcessImagePath($iPid)
	Local $sCommand = ProcessGetCommandLine($iPid)
	If $sServiceCreated = "" Or $sBackendCreated = "" Or $iParentPid <> @AutoItPID Then Return False
	If Not StringRegExp(StringLower($sImage), "\\pythonw\.exe$") Then Return False
	If @error Or $sCommand = "" Or $sCommand = "-1" Then Return False
	If _RunPlannerHashText($sCommand) <> _RunPlannerHashText($sExpectedCommand) Then Return False

	Local $sHealthToken = _RunPlannerHashText($sOwnerToken)
	Local $sReceipt = '{"schema":"' & $RUN_PLANNER_OWNERSHIP_SCHEMA & '","token":"' & $sOwnerToken & _
		'","health_token":"' & $sHealthToken & '","service_pid":' & $iPid & ',"service_created":"' & $sServiceCreated & _
		'","backend_pid":' & @AutoItPID & ',"backend_created":"' & $sBackendCreated & '","parent_pid":' & $iParentPid & _
		',"python_image_token":"' & _RunPlannerPathToken($sImage) & '","script_path_token":"' & _
		_RunPlannerPathToken(@ScriptDir & "\tools\planner_ui.py") & '","profiles_root_token":"' & _RunPlannerPathToken($g_sProfilePath) & _
		'","command_sha256":"' & _RunPlannerHashText($sCommand) & '","build_sha256":"' & _RunPlannerScriptBuildHash() & '"}'
	If StringInStr($sReceipt, ':""') Then Return False
	DirCreate($g_sMBRFuncRuntimeLocalAppData & "\My Bot 2.0")
	If Not _RunPlannerReceiptPathSafe(False) Then Return False
	Local $sTemporary = $RUN_PLANNER_OWNERSHIP_RECEIPT & ".tmp." & StringLeft($sOwnerToken, 16)
	If FileExists($sTemporary) Then Return False
	Local $hReceipt = FileOpen($sTemporary, 10)
	If $hReceipt = -1 Then Return False
	Local $bWritten = FileWrite($hReceipt, $sReceipt) = 1
	FileFlush($hReceipt)
	FileClose($hReceipt)
	If Not $bWritten Or Not FileMove($sTemporary, $RUN_PLANNER_OWNERSHIP_RECEIPT, 1) Then
		FileDelete($sTemporary)
		Return False
	EndIf
	Return _RunPlannerReadOwnershipReceipt() = $sReceipt
EndFunc   ;==>_RunPlannerWriteOwnershipReceipt

Func _RunPlannerDeleteOwnedReceipt($iPid, $sOwnerToken)
	Local $sReceipt = _RunPlannerReadOwnershipReceipt()
	If $sReceipt = "" Then Return True
	If Not _RunPlannerReceiptOwnedByCurrentBackend($sReceipt, $iPid, $sOwnerToken) Then Return False
	If Not _RunPlannerReceiptPathSafe(True) Or _RunPlannerReadOwnershipReceipt() <> $sReceipt Then Return False
	Return FileDelete($RUN_PLANNER_OWNERSHIP_RECEIPT) = 1 Or Not FileExists($RUN_PLANNER_OWNERSHIP_RECEIPT)
EndFunc   ;==>_RunPlannerDeleteOwnedReceipt

Func _RunPlannerReadHealth(ByRef $oPayload)
	$oPayload = 0
	Local $bPayload = InetRead($RUN_PLANNER_HEALTH_URL, 1)
	If @error Then Return False

	Local $sPayload = BinaryToString($bPayload, 4)
	If StringStripWS($sPayload, $STR_STRIPALL) = "" Then Return False

	Local $oDecoded = Json_Decode($sPayload)
	If @error Or Not IsObj($oDecoded) Then Return False
	$oPayload = $oDecoded
	Return True
EndFunc   ;==>_RunPlannerReadHealth

Func _RunPlannerServiceHealthy()
	$g_iRunPlannerObservedServicePid = 0
	$g_sRunPlannerObservedOwnerToken = ""
	Local $oPayload = 0
	If Not _RunPlannerReadHealth($oPayload) Then Return False

	; A service that answers but reports itself unhealthy is not healthy, so ok has to be the boolean
	; true rather than merely present.
	If Json_ObjGet($oPayload, "ok") <> True Then Return False
	If Json_ObjGet($oPayload, "service") <> $RUN_PLANNER_SERVICE_NAME Then Return False
	If Json_ObjGet($oPayload, "bridge") <> $RUN_PLANNER_BRIDGE_VERSION Then Return False
	If Json_ObjGet($oPayload, "protocol") <> $RUN_PLANNER_HEALTH_PROTOCOL Then Return False
	If _RunPlannerNormalizeRoot(Json_ObjGet($oPayload, "repo_root")) <> _RunPlannerNormalizeRoot(@ScriptDir) Then Return False
	If _RunPlannerNormalizeRoot(Json_ObjGet($oPayload, "profiles_root")) <> _RunPlannerNormalizeRoot($g_sProfilePath) Then Return False
	Local $sExpectedBuild = _RunPlannerScriptBuildHash()
	If $sExpectedBuild = "" Or StringLower(String(Json_ObjGet($oPayload, "build_sha256"))) <> $sExpectedBuild Then Return False
	Local $iServicePid = Int(Json_ObjGet($oPayload, "service_pid"))
	If $iServicePid <= 0 Or Not ProcessExists($iServicePid) Then Return False
	$g_iRunPlannerObservedServicePid = $iServicePid
	$g_sRunPlannerObservedOwnerToken = String(Json_ObjGet($oPayload, "owner_token"))
	Return True
EndFunc   ;==>_RunPlannerServiceHealthy

; A matching build/root response is only a compatibility signal. Reuse requires the exact receipt
; created by this backend plus its raw token, process creation identity, parent, image and command.
Func _RunPlannerAdoptOwnedHealthyService()
	If Not _RunPlannerServiceHealthy() Then Return False
	Local $iPid = $g_iRunPlannerObservedServicePid
	Local $sReceipt = _RunPlannerReadOwnershipReceipt()
	Local $sOwnerToken = _RunPlannerReceiptString($sReceipt, "token")
	If $sReceipt = "" Or $sOwnerToken = "" Then Return False
	If $g_sRunPlannerObservedOwnerToken <> _RunPlannerHashText($sOwnerToken) Then Return False
	If Not _RunPlannerReceiptMatchesLiveService($sReceipt, $iPid, $sOwnerToken) Then Return False
	$g_iRunPlannerOwnedServicePid = $iPid
	$g_sRunPlannerOwnedServiceToken = $sOwnerToken
	Return True
EndFunc   ;==>_RunPlannerAdoptOwnedHealthyService

Func _RunPlannerNewOwnerToken()
	Local $tEntropy = DllStructCreate("byte[32]")
	Local $aRandom = DllCall("bcrypt.dll", "long", "BCryptGenRandom", "ptr", 0, "struct*", $tEntropy, "ulong", 32, "ulong", 0x2)
	If @error Or Not IsArray($aRandom) Or $aRandom[0] <> 0 Then Return ""
	Return StringLower(Hex(DllStructGetData($tEntropy, 1)))
EndFunc   ;==>_RunPlannerNewOwnerToken

Func _RunPlannerPythonExecutable()
	Local $aCandidates = [ _
		$g_sMBRFuncRuntimeLocalAppData & "\Programs\Python\Python313\pythonw.exe", _
		$g_sMBRFuncRuntimeLocalAppData & "\Programs\Python\Python312\pythonw.exe", _
		$g_sMBRFuncRuntimeLocalAppData & "\Programs\Python\Python311\pythonw.exe", _
		$g_sMBRFuncRuntimeLocalAppData & "\Programs\Python\Python310\pythonw.exe"]
	For $i = 0 To UBound($aCandidates) - 1
		If FileExists($aCandidates[$i]) Then Return $aCandidates[$i]
	Next
	Return "pythonw.exe"
EndFunc   ;==>_RunPlannerPythonExecutable

Func _RunPlannerStartService(ByRef $sError)
	$sError = ""
	If _RunPlannerServiceHealthy() Then
		If _RunPlannerAdoptOwnedHealthyService() Then Return True
		$sError = "Planner service ownership could not be verified"
		Return False
	EndIf
	Local $sScript = @ScriptDir & "\tools\planner_ui.py"
	If Not FileExists($sScript) Then
		$sError = "Planner service script is missing"
		Return False
	EndIf
	Local $sPython = _RunPlannerPythonExecutable()
	Local $sOwnerToken = _RunPlannerNewOwnerToken()
	If $sOwnerToken = "" Then
		$sError = "Secure planner ownership token could not be created"
		Return False
	EndIf
	Local $sCommand = '"' & $sPython & '" "' & $sScript & '" --no-browser --owner-token "' & $sOwnerToken & '" --profiles-root "' & $g_sProfilePath & '"'
	; The native runtime has an authoritative Local AppData path even when its parent was launched
	; from a restricted environment without LOCALAPPDATA. The planner independently confines the
	; supplied profiles root below this value, so publish the trusted native value to the child before
	; it starts instead of weakening that validation or relying on the parent process environment.
	If Not EnvSet("LOCALAPPDATA", $g_sMBRFuncRuntimeLocalAppData) Then
		$sError = "Trusted Local AppData could not be published to the planner service"
		Return False
	EndIf
	Local $iPid = Run($sCommand, @ScriptDir, @SW_HIDE)
	If $iPid = 0 Then
		$sError = "Python could not start the planner service"
		Return False
	EndIf
	For $i = 1 To 25
		Sleep(200)
		If _RunPlannerServiceHealthy() Then
			If $g_iRunPlannerObservedServicePid = $iPid And $g_sRunPlannerObservedOwnerToken = _RunPlannerHashText($sOwnerToken) Then
				If Not _RunPlannerWriteOwnershipReceipt($iPid, $sOwnerToken, $sCommand) Then
					If ProcessExists($iPid) Then ProcessClose($iPid)
					$sError = "Planner ownership receipt could not be secured"
					Return False
				EndIf
				$g_iRunPlannerOwnedServicePid = $iPid
				$g_sRunPlannerOwnedServiceToken = $sOwnerToken
				Return True
			EndIf
			; Another service won the port race. Close only the process returned by our Run call, then
			; reuse the listener only if it has this backend's complete ownership receipt.
			If ProcessExists($iPid) Then ProcessClose($iPid)
			If _RunPlannerAdoptOwnedHealthyService() Then Return True
			$sError = "Planner service ownership could not be verified"
			Return False
		EndIf
		If Not ProcessExists($iPid) Then ExitLoop
	Next
	If ProcessExists($iPid) Then ProcessClose($iPid)
	Local $oConflict = 0
	If _RunPlannerReadHealth($oConflict) Then
		$sError = "Planner service belongs to a different checkout or build"
	Else
		$sError = "Planner service did not become healthy"
	EndIf
	Return False
EndFunc   ;==>_RunPlannerStartService

; This file has no application-exit hook. The owner should call this bounded helper from the native
; shutdown path. It refuses to close a reused service or a PID whose launch token/root no longer
; prove that this process created it.
Func RunPlannerStopOwnedService()
	Local $iPid = $g_iRunPlannerOwnedServicePid
	Local $sOwnerToken = $g_sRunPlannerOwnedServiceToken
	If $iPid <= 0 Or $sOwnerToken = "" Then Return True
	If Not ProcessExists($iPid) Then
		Local $bReceiptRemoved = _RunPlannerDeleteOwnedReceipt($iPid, $sOwnerToken)
		$g_iRunPlannerOwnedServicePid = 0
		$g_sRunPlannerOwnedServiceToken = ""
		Return $bReceiptRemoved
	EndIf

	Local $sReceipt = _RunPlannerReadOwnershipReceipt()
	If $sReceipt = "" Or Not _RunPlannerReceiptMatchesLiveService($sReceipt, $iPid, $sOwnerToken) Then Return False
	Local $oPayload = 0
	If Not _RunPlannerReadHealth($oPayload) Then Return False
	If Json_ObjGet($oPayload, "service") <> $RUN_PLANNER_SERVICE_NAME Then Return False
	If _RunPlannerNormalizeRoot(Json_ObjGet($oPayload, "repo_root")) <> _RunPlannerNormalizeRoot(@ScriptDir) Then Return False
	If _RunPlannerNormalizeRoot(Json_ObjGet($oPayload, "profiles_root")) <> _RunPlannerNormalizeRoot($g_sProfilePath) Then Return False
	If Int(Json_ObjGet($oPayload, "service_pid")) <> $iPid Then Return False
	If String(Json_ObjGet($oPayload, "owner_token_kind")) <> "sha256" Then Return False
	If String(Json_ObjGet($oPayload, "owner_token")) <> _RunPlannerHashText($sOwnerToken) Then Return False
	; Recheck the PID/creation pair directly before closing so a stale receipt cannot target a reused PID.
	If Not _RunPlannerReceiptMatchesLiveService($sReceipt, $iPid, $sOwnerToken) Then Return False

	If Not ProcessClose($iPid) Then Return False
	For $i = 1 To 20
		If Not ProcessExists($iPid) Then ExitLoop
		Sleep(50)
	Next
	If ProcessExists($iPid) Then Return False
	If Not _RunPlannerDeleteOwnedReceipt($iPid, $sOwnerToken) Then Return False
	$g_iRunPlannerOwnedServicePid = 0
	$g_sRunPlannerOwnedServiceToken = ""
	Return True
EndFunc   ;==>RunPlannerStopOwnedService

Func _RunPlannerSetLabel($hControl, $sText, $iColor)
	If $hControl = 0 Then Return
	GUICtrlSetData($hControl, $sText)
	GUICtrlSetColor($hControl, $iColor)
EndFunc   ;==>_RunPlannerSetLabel

Func RunPlannerSettingIndex($sSettingId)
	For $i = 0 To UBound($g_aRunPlannerSettings, 1) - 1
		If $g_aRunPlannerSettings[$i][$eRunPlannerSettingId] = $sSettingId Then Return $i
	Next
	Return -1
EndFunc   ;==>RunPlannerSettingIndex

Func RunPlannerOptionIndex($sSettingId, $sValue)
	For $i = 0 To UBound($g_aRunPlannerOptions, 1) - 1
		If $g_aRunPlannerOptions[$i][$eRunPlannerOptionSettingId] <> $sSettingId Then ContinueLoop
		If $g_aRunPlannerOptions[$i][$eRunPlannerOptionValue] = $sValue Then Return $i
	Next
	Return -1
EndFunc   ;==>RunPlannerOptionIndex

; Combos display a decorated label, so read the control and map the text back to the option value.
Func RunPlannerSelectedValue($sSettingId)
	Local $iSetting = RunPlannerSettingIndex($sSettingId)
	If $iSetting < 0 Then Return ""
	Local $hControl = $g_ahRunPlannerControls[$iSetting]
	If $hControl = 0 Then Return ""
	Local $sText = GUICtrlRead($hControl)
	For $i = 0 To UBound($g_aRunPlannerOptions, 1) - 1
		If $g_aRunPlannerOptions[$i][$eRunPlannerOptionSettingId] <> $sSettingId Then ContinueLoop
		If _RunPlannerDecoratedLabel($i) = $sText Then Return $g_aRunPlannerOptions[$i][$eRunPlannerOptionValue]
	Next
	Return ""
EndFunc   ;==>RunPlannerSelectedValue

Func RunPlannerReadInteger($sSettingId)
	Local $iSetting = RunPlannerSettingIndex($sSettingId)
	If $iSetting < 0 Then Return 0
	If $g_ahRunPlannerControls[$iSetting] = 0 Then Return 0
	Return Int(GUICtrlRead($g_ahRunPlannerControls[$iSetting]))
EndFunc   ;==>RunPlannerReadInteger

Func RunPlannerReadBoolean($sSettingId)
	Local $iSetting = RunPlannerSettingIndex($sSettingId)
	If $iSetting < 0 Then Return False
	If $g_ahRunPlannerControls[$iSetting] = 0 Then Return False
	Return GUICtrlRead($g_ahRunPlannerControls[$iSetting]) = $GUI_CHECKED
EndFunc   ;==>RunPlannerReadBoolean

Func RunPlannerReadText($sSettingId)
	Local $iSetting = RunPlannerSettingIndex($sSettingId)
	If $iSetting < 0 Then Return ""
	If $g_ahRunPlannerControls[$iSetting] = 0 Then Return ""
	Return StringStripWS(GUICtrlRead($g_ahRunPlannerControls[$iSetting]), $STR_STRIPLEADING + $STR_STRIPTRAILING)
EndFunc   ;==>RunPlannerReadText

; ===============================================================================================================================
; The web planner writes config\run-plan.local.json; this reads it back into the tab.
;
; The file is the single source of truth and the traffic is one way: the tab mirrors the file, and nothing here writes to it.
; That is what makes the two views safe to have open at once - the browser cannot be quietly overwritten by a stale tab.
; ===============================================================================================================================

; A hand-edited file can hold anything. Booleans arrive as real booleans from the parser, but the words are accepted too so a
; file someone typed themselves behaves the way it reads.
Func _RunPlannerBooleanFromValue($vValue, ByRef $bValid)
	$bValid = True
	If IsBool($vValue) Then Return $vValue
	If IsNumber($vValue) Then Return ($vValue <> 0)
	Switch StringLower(StringStripWS(String($vValue), $STR_STRIPALL))
		Case "true", "1", "yes", "on"
			Return True
		Case "false", "0", "no", "off", ""
			Return False
	EndSwitch
	$bValid = False
	Return False
EndFunc   ;==>_RunPlannerBooleanFromValue

; Puts one value from the plan file into the control that owns it.
;
; True means the control now holds a usable value; False means it was left alone because the file's value could not be
; represented, which costs that one setting rather than the whole plan. $sError is set either way when there is something to
; say, so True with a message means the value was accepted after being adjusted.
Func _RunPlannerApplySetting($iSetting, $vValue, ByRef $sError)
	$sError = ""
	Local $sId = $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingId]
	Local $hControl = $g_ahRunPlannerControls[$iSetting]
	If $hControl = 0 Then
		$sError = $sId & " has no control"
		Return SetError(1, 0, False)
	EndIf
	If $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingNativeFixed] Then
		Local $vFixed = $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingNativeFixedValue]
		If String($vValue) <> String($vFixed) Then $sError = $sId & ": fixed by the native contract; used " & String($vFixed)
		$vValue = $vFixed
	EndIf

	Switch StringLower($g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingType])
		Case "select"
			Local $sValue = String($vValue)
			If RunPlannerOptionIndex($sId, $sValue) < 0 Then
				$sError = $sId & ": " & $sValue & " is not one of the offered options"
				Return SetError(2, 0, False)
			EndIf
			; Same clear-and-repopulate the Reset button uses: it is the one way to move a combo's selection that also keeps
			; the decorated availability labels correct.
			GUICtrlSetData($hControl, "")
			GUICtrlSetData($hControl, _RunPlannerOptionLabelList($sId), _RunPlannerDefaultLabel($sId, $sValue))
			_RunPlannerTintForAvailability($hControl, $sId, $sValue)

		Case "multi-select"
			; Heroes are held in a loadout rather than the control, so the list goes through the engine and an impossible
			; selection is refused here rather than surfacing at Apply.
			Local $sIds = StringStripWS(String($vValue), $STR_STRIPLEADING + $STR_STRIPTRAILING)
			Local $oLoadout = HeroLoadoutCreate(RunPlannerReadInteger("run.town_hall"))
			If Not IsObj($oLoadout) Then
				$sError = $sId & ": unable to create a Hero loadout"
				Return SetError(3, 0, False)
			EndIf
			If $sIds <> "" Then
				Local $aIds = StringSplit($sIds, $RUN_PLAN_FILE_LIST_SEPARATOR, $STR_NOCOUNT)
				For $i = 0 To UBound($aIds) - 1
					Local $sHero = StringStripWS($aIds[$i], $STR_STRIPALL)
					If $sHero = "" Then ContinueLoop
					If Not HeroLoadoutAdd($oLoadout, $sHero, $sError) Then
						$sError = $sId & ": " & $sError
						Return SetError(4, 0, False)
					EndIf
				Next
			EndIf
			$g_sRunPlannerHeroIds = $oLoadout.Item("hero_ids")
			RunPlannerRefreshHeroSelection()

		Case "integer"
			If Not StringRegExp(StringStripWS(String($vValue), $STR_STRIPALL), "^-?[0-9]+$") Then
				$sError = $sId & ": " & String($vValue) & " is not a whole number"
				Return SetError(5, 0, False)
			EndIf
			Local $iValue = Int($vValue)
			Local $iMinimum = Int($g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingMinimum])
			Local $iMaximum = Int($g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingMaximum])
			; Out of range is clamped rather than refused: the control cannot hold the original either way, and a run that
			; keeps going at the nearest legal value beats one that silently ignored the setting.
			If $iValue < $iMinimum Then
				$sError = $sId & ": " & $iValue & " is below " & $iMinimum & ", used " & $iMinimum
				$iValue = $iMinimum
			ElseIf $iValue > $iMaximum Then
				$sError = $sId & ": " & $iValue & " is above " & $iMaximum & ", used " & $iMaximum
				$iValue = $iMaximum
			EndIf
			GUICtrlSetData($hControl, $iValue)

		Case "boolean"
			Local $bValid = False
			Local $bValue = _RunPlannerBooleanFromValue($vValue, $bValid)
			If Not $bValid Then
				$sError = $sId & ": " & String($vValue) & " is not a yes or no"
				Return SetError(6, 0, False)
			EndIf
			GUICtrlSetState($hControl, ($bValue ? $GUI_CHECKED : $GUI_UNCHECKED))

		Case Else
			GUICtrlSetData($hControl, String($vValue))
	EndSwitch
	_RunPlannerApplyNativeFixedState($iSetting)

	Return True
EndFunc   ;==>_RunPlannerApplySetting

; Reads the plan file into the tab. Returns the number of settings applied, and leaves a one-line summary in
; $g_sRunPlannerPlanFileNote for whoever wants to show it.
Func RunPlannerApplyPlanFile($sPath, ByRef $sError)
	$sError = ""
	$g_sRunPlannerPlanFileNote = ""

	Local $oValues = RunPlanFileLoad($sPath, $sError)
	Local $iLoadStatus = @error ; captured before anything else can clear it
	If Not IsObj($oValues) Then
		; No file at all is the ordinary state, not a fault: nobody has opened the web planner on this machine.
		If $iLoadStatus = 2 Then
			$sError = ""
			Return SetError(1, 0, 0)
		EndIf
		Return SetError(2, 0, 0)
	EndIf

	Local $iApplied = 0, $iAdjusted = 0, $iRefused = 0, $iUnknown = 0
	Local $sFirstProblem = ""
	Local $aKeys = $oValues.Keys()
	; Hero availability depends on the plan's Town Hall. Apply that identity first even when
	; the JSON dictionary returns run.heroes before run.town_hall.
	If $oValues.Exists("run.town_hall") Then
		Local $iTownHallSetting = RunPlannerSettingIndex("run.town_hall")
		Local $sTownHallError = ""
		If $iTownHallSetting >= 0 And _RunPlannerApplySetting($iTownHallSetting, $oValues.Item("run.town_hall"), $sTownHallError) Then
			$iApplied += 1
			If $sTownHallError <> "" Then $iAdjusted += 1
		Else
			$iRefused += 1
		EndIf
		If $sTownHallError <> "" Then $sFirstProblem = $sTownHallError
	EndIf

	For $i = 0 To UBound($aKeys) - 1
		Local $sKey = $aKeys[$i]
		If $sKey = "run.town_hall" Then ContinueLoop
		Local $iSetting = RunPlannerSettingIndex($sKey)
		If $iSetting < 0 Then
			; A setting this build does not have. Older or newer plan files are readable either way, which is the point of
			; keying on setting ids rather than positions.
			$iUnknown += 1
			ContinueLoop
		EndIf

		Local $sSettingError = ""
		Local $bApplied = _RunPlannerApplySetting($iSetting, $oValues.Item($sKey), $sSettingError)
		If $bApplied Then
			$iApplied += 1
			If $sSettingError <> "" Then $iAdjusted += 1
		Else
			$iRefused += 1
		EndIf
		If $sSettingError <> "" And $sFirstProblem = "" Then $sFirstProblem = $sSettingError
	Next

	; The controls moved without anyone clicking them, so the derived panes have to be told.
	UpdateRunPlannerBanner()
	UpdateRunPlannerDetail("run.surface")

	$g_sRunPlannerPlanFileNote = "Loaded " & $iApplied & " setting" & (($iApplied = 1) ? "" : "s") & " from the run plan file"
	If $iAdjusted > 0 Then $g_sRunPlannerPlanFileNote &= ", " & $iAdjusted & " brought into range"
	If $iUnknown > 0 Then $g_sRunPlannerPlanFileNote &= ", ignored " & $iUnknown & " this build does not have"
	If $iRefused > 0 Then $g_sRunPlannerPlanFileNote &= ", refused " & $iRefused
	$sError = $sFirstProblem

	Return SetError(0, $iRefused, $iApplied)
EndFunc   ;==>RunPlannerApplyPlanFile

; Called wherever the tab is about to be believed. Cheap when nothing changed: it compares a timestamp and a size before it
; opens anything.
Func RunPlannerSyncPlanFile($bForce = False)
	; The mini GUI does not build the planner tab, so there are no controls to write into.
	If $g_iGuiMode <> 1 Then Return 0

	Local $sPath = RunPlanFileDefaultPath()
	Local $sStamp = RunPlanFileStamp($sPath)
	If Not $bForce And $sStamp = $g_sRunPlannerPlanFileStamp Then Return 0
	$g_sRunPlannerPlanFileStamp = $sStamp

	Local $sError = ""
	Local $iApplied = RunPlannerApplyPlanFile($sPath, $sError)
	Local $iStatus = @error

	If $iStatus = 1 Then Return 0 ; there is no plan file on this machine
	If $iStatus <> 0 Then
		SetLog("Run Planner: run plan file was not read - " & $sError, $COLOR_ERROR)
		If $g_hRunPlannerStatus <> 0 Then GUICtrlSetData($g_hRunPlannerStatus, "Run plan file could not be read")
		Return 0
	EndIf

	SetLog("Run Planner: " & $g_sRunPlannerPlanFileNote, ($sError = "") ? $COLOR_SUCCESS : $COLOR_ACTION)
	RunEventLogPlanFileLoaded($g_sRunPlannerPlanFileNote)
	If $sError <> "" Then SetLog("Run Planner: " & $sError, $COLOR_ACTION)
	If $g_hRunPlannerStatus <> 0 Then GUICtrlSetData($g_hRunPlannerStatus, $g_sRunPlannerPlanFileNote)
	Return $iApplied
EndFunc   ;==>RunPlannerSyncPlanFile

; The engine stores a plan mode; the planner stores an exact surface. This is the only place that maps between them.
Func RunPlannerPlanModeForSurface($sSurfaceId)
	Local $iIndex = CurrentGameFindBattleSurface($sSurfaceId)
	If $iIndex < 0 Then Return ""
	Local $sRoute = StringLower(StringStripWS($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleEngineRoute], $STR_STRIPALL))
	If $sRoute <> "" Then Return $sRoute
	Local $iParent = CurrentGameFindBattleSurface($g_aCurrentGameBattleSurfaces[$iIndex][$eGameBattleParentSurface])
	If $iParent < 0 Then Return ""
	Return StringLower(StringStripWS($g_aCurrentGameBattleSurfaces[$iParent][$eGameBattleEngineRoute], $STR_STRIPALL))
EndFunc   ;==>RunPlannerPlanModeForSurface

Func RunPlannerBuildLoadout(ByRef $sError)
	$sError = ""
	Local $oLoadout = HeroLoadoutCreate(RunPlannerReadInteger("run.town_hall"))
	If Not IsObj($oLoadout) Then
		$sError = "Unable to create a Hero loadout"
		Return SetError(1, 0, 0)
	EndIf
	If StringStripWS($g_sRunPlannerHeroIds, $STR_STRIPALL) = "" Then Return $oLoadout

	Local $aIds = StringSplit($g_sRunPlannerHeroIds, $HERO_LOADOUT_SEPARATOR, $STR_NOCOUNT)
	For $i = 0 To UBound($aIds) - 1
		If Not HeroLoadoutAdd($oLoadout, $aIds[$i], $sError) Then Return SetError(2, 0, 0)
	Next
	Return $oLoadout
EndFunc   ;==>RunPlannerBuildLoadout

Func RunPlannerBuildIntent(ByRef $sError)
	$sError = ""
	Local $sSurface = RunPlannerSelectedValue("run.surface")
	If $sSurface = "" Then
		$sError = "Choose a battle surface first"
		Return SetError(1, 0, 0)
	EndIf

	Local $sMode = RunPlannerPlanModeForSurface($sSurface)
	If $sMode = "" Then
		$sError = "Surface " & $sSurface & " has no reachable engine route"
		Return SetError(2, 0, 0)
	EndIf

	Local $sStrategy = RunPlannerSelectedValue("run.strategy")
	If $sStrategy = "" Then $sStrategy = "legacy.csv"
	Local $sAttackScript = RunPlannerSelectedValue("run.attack_script")
	If $sAttackScript = "" Then $sAttackScript = "profile-current"

	Local $oPlan = RunPlanCreateDefault($sMode, $sStrategy, $sAttackScript)
	If Not IsObj($oPlan) Then
		$sError = "Unable to create a run plan"
		Return SetError(3, 0, 0)
	EndIf
	If Not RunPlanSetPlannedTownHall($oPlan, RunPlannerReadInteger("run.town_hall"), $sError) Then _
		Return SetError(3, 1, 0)

	If Not RunPlanSetStopConditions($oPlan, RunPlannerReadInteger("run.duration_minutes"), RunPlannerReadInteger("run.max_battles"), RunPlannerReadBoolean("run.stop_on_star_bonus"), RunPlannerReadInteger("run.max_failures")) Then
		$sError = "Stop conditions are out of range"
		Return SetError(4, 0, 0)
	EndIf
	If Not RunPlanSetResourceTargets($oPlan, RunPlannerReadInteger("target.gold"), RunPlannerReadInteger("target.elixir"), RunPlannerReadInteger("target.dark_elixir")) Then
		$sError = "Resource targets are out of range"
		Return SetError(5, 0, 0)
	EndIf

	Local $sPolicy = RunPlannerSelectedValue("upgrade.policy")
	If $sPolicy <> "" Then $oPlan.Item("upgrade_policy") = $sPolicy
	$oPlan.Item("account_queue_id") = RunPlannerReadText("account.queue")
	$oPlan.Item("army_manage_training") = RunPlannerReadBoolean("army.manage_training")

	Local $oLoadout = RunPlannerBuildLoadout($sError)
	If Not IsObj($oLoadout) Then Return SetError(6, 0, 0)

	Local $oIntent = RunIntentCreate($oPlan, $sSurface, $oLoadout, $sError)
	If Not IsObj($oIntent) Then Return SetError(7, 0, 0)
	If Not RunIntentSetProfile($oIntent, $g_sProfileCurrentName) Then
		$sError = "Unable to bind the run intent to the active profile"
		Return SetError(7, 1, 0)
	EndIf

	If Not RunIntentSetPacing($oIntent, RunPlannerReadInteger("pacing.action_delay_ms"), RunPlannerReadInteger("pacing.settle_ms"), RunPlannerReadInteger("pacing.retry_attempts"), RunPlannerReadInteger("pacing.break_every_minutes"), RunPlannerReadInteger("pacing.break_minutes"), $sError) Then
		$sError = "Pacing is out of range: " & $sError
		Return SetError(8, 0, 0)
	EndIf

	; Diagnostic mode is the operator's choice, and the note is stored with the run so a later reader knows
	; the result was observed rather than demonstrated.
	If RunPlannerReadBoolean("run.diagnostic_mode") Then
		Local $sNote = RunPlannerReadText("run.diagnostic_note")
		If $sNote = "" Then
			$sError = "Add a diagnostic note naming who is watching this run"
			Return SetError(9, 0, 0)
		EndIf
		If Not RunIntentEnableDiagnostic($oIntent, $sNote, $sError) Then Return SetError(10, 0, 0)
	EndIf

	Return $oIntent
EndFunc   ;==>RunPlannerBuildIntent

Func UpdateRunPlannerBanner()
	If $g_hRunPlannerBanner = 0 Then Return
	Local $sSurface = RunPlannerSelectedValue("run.surface")
	If $sSurface = "" Then
		GUICtrlSetData($g_hRunPlannerBanner, "")
		Return
	EndIf

	Local $sReason = ""
	Local $sState = RunVerificationSurfaceState($sSurface, $sReason)
	If $sState = $RUN_VERIFICATION_VERIFIED Then
		GUICtrlSetData($g_hRunPlannerBanner, "Verified: this surface has been demonstrated on the current client.")
		GUICtrlSetColor($g_hRunPlannerBanner, $COLOR_GREEN)
		Return
	EndIf

	Local $sBanner = RunVerificationBanner($sState, $sReason)
	If Not RunPlannerReadBoolean("run.diagnostic_mode") Then
		$sBanner &= " Turn on the Diagnostics option to run it anyway."
	EndIf
	GUICtrlSetData($g_hRunPlannerBanner, $sBanner)
	GUICtrlSetColor($g_hRunPlannerBanner, $COLOR_MAROON)
EndFunc   ;==>UpdateRunPlannerBanner

Func UpdateRunPlannerDetail($sSettingId)
	If $g_hRunPlannerDetail = 0 Then Return
	Local $iSetting = RunPlannerSettingIndex($sSettingId)
	If $iSetting < 0 Then Return

	Local $sText = $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingDescription]
	If $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingNativeFixedReason] <> "" Then _
		$sText &= @CRLF & @CRLF & "Fixed by native contract: " & $g_aRunPlannerSettings[$iSetting][$eRunPlannerSettingNativeFixedReason]
	Local $sValue = RunPlannerSelectedValue($sSettingId)
	Local $iOption = ($sValue = "") ? -1 : RunPlannerOptionIndex($sSettingId, $sValue)

	If $iOption >= 0 Then
		$sText &= @CRLF & @CRLF & $g_aRunPlannerOptions[$iOption][$eRunPlannerOptionLabel] & ": " & $g_aRunPlannerOptions[$iOption][$eRunPlannerOptionDescription]

		Local $sPrerequisites = $g_aRunPlannerOptions[$iOption][$eRunPlannerOptionPrerequisites]
		If $sPrerequisites <> "" Then
			$sText &= @CRLF & @CRLF & "Needs: " & StringReplace($sPrerequisites, $HERO_LOADOUT_SEPARATOR, ", ")
		EndIf

		Local $sDisabled = $g_aRunPlannerOptions[$iOption][$eRunPlannerOptionDisabledReason]
		If $sDisabled <> "" Then $sText &= @CRLF & @CRLF & "Not verified: " & $sDisabled

		Local $sWarning = $g_aRunPlannerOptions[$iOption][$eRunPlannerOptionWarning]
		If $sWarning <> "" Then $sText &= @CRLF & @CRLF & "Note: " & $sWarning
	EndIf

	GUICtrlSetData($g_hRunPlannerDetail, $sText)
EndFunc   ;==>UpdateRunPlannerDetail

Func RunPlannerRefreshHeroSelection()
	If $g_hRunPlannerHeroSelection = 0 Then Return
	If StringStripWS($g_sRunPlannerHeroIds, $STR_STRIPALL) = "" Then
		GUICtrlSetData($g_hRunPlannerHeroSelection, "No Heroes selected")
		Return
	EndIf

	Local $aIds = StringSplit($g_sRunPlannerHeroIds, $HERO_LOADOUT_SEPARATOR, $STR_NOCOUNT)
	Local $sLabels = ""
	For $i = 0 To UBound($aIds) - 1
		Local $iHero = CurrentGameFindHero($aIds[$i])
		Local $sLabel = ($iHero >= 0) ? $g_aCurrentGameHeroes[$iHero][$eGameHeroLabel] : $aIds[$i]
		$sLabels &= (($sLabels = "") ? "" : ", ") & $sLabel
	Next
	GUICtrlSetData($g_hRunPlannerHeroSelection, $sLabels & "   (" & UBound($aIds) & "/" & $CURRENT_GAME_MAX_ACTIVE_HERO_SLOTS & ")")
EndFunc   ;==>RunPlannerRefreshHeroSelection

Func btnRunPlannerHeroAdd()
	Local $sHero = RunPlannerSelectedValue("run.heroes")
	If $sHero = "" Then Return

	; Round-trip through the engine so the GUI cannot build a selection the engine would reject.
	Local $sError = ""
	Local $oLoadout = RunPlannerBuildLoadout($sError)
	If Not IsObj($oLoadout) Then
		GUICtrlSetData($g_hRunPlannerStatus, $sError)
		Return
	EndIf
	If Not HeroLoadoutAdd($oLoadout, $sHero, $sError) Then
		GUICtrlSetData($g_hRunPlannerStatus, $sError)
		Return
	EndIf

	$g_sRunPlannerHeroIds = $oLoadout.Item("hero_ids")
	GUICtrlSetData($g_hRunPlannerStatus, "")
	RunPlannerRefreshHeroSelection()
EndFunc   ;==>btnRunPlannerHeroAdd

Func btnRunPlannerHeroRemove()
	Local $sHero = RunPlannerSelectedValue("run.heroes")
	If $sHero = "" Then Return

	Local $sError = ""
	Local $oLoadout = RunPlannerBuildLoadout($sError)
	If Not IsObj($oLoadout) Then
		GUICtrlSetData($g_hRunPlannerStatus, $sError)
		Return
	EndIf
	If Not HeroLoadoutRemove($oLoadout, $sHero) Then
		GUICtrlSetData($g_hRunPlannerStatus, "That Hero is not in the active slots")
		Return
	EndIf

	$g_sRunPlannerHeroIds = $oLoadout.Item("hero_ids")
	GUICtrlSetData($g_hRunPlannerStatus, "")
	RunPlannerRefreshHeroSelection()
EndFunc   ;==>btnRunPlannerHeroRemove

Func btnRunPlannerApply()
	; The file has the last word, so a change made in the browser a moment ago is honoured rather than overwritten by
	; whatever the tab happened to be showing.
	RunPlannerSyncPlanFile()

	Local $sError = ""
	Local $oIntent = RunPlannerBuildIntent($sError)
	If Not IsObj($oIntent) Then
		GUICtrlSetData($g_hRunPlannerStatus, $sError)
		SetLog("Run Planner: " & $sError, $COLOR_ERROR)
		Return
	EndIf

	$g_oRunPlannerIntent = $oIntent

	; Apply prepares only. Pacing and every other override become active together at the explicit Start boundary.
	RunPacingDeactivate()

	; Recorded to the JSONL stream as well as the log, because the control centre's Activity panel reads that file and
	; applying a plan is the first thing an operator wants to see confirmed there.
	Local $sSurfaceId = $oIntent.Item("surface_id")

	Local $sReason = ""
	Local $bCanStart = RunIntentCanStart($oIntent, $sReason)
	If $bCanStart Then $bCanStart = RunExecutionContractValidate($oIntent, $sReason)
	If $bCanStart Then
		Local $sState = RunIntentVerificationState($oIntent)
		If $sState = $RUN_VERIFICATION_DIAGNOSTIC Then
			GUICtrlSetData($g_hRunPlannerStatus, "Ready as a diagnostic run")
			SetLog("Run Planner: " & RunIntentDescribe($oIntent), $COLOR_ACTION)
			SetLog("Run Planner: proceeding unverified - " & $sReason, $COLOR_ACTION)
		Else
			GUICtrlSetData($g_hRunPlannerStatus, "Ready")
			SetLog("Run Planner: " & RunIntentDescribe($oIntent), $COLOR_SUCCESS)
		EndIf
		RunEventLogPlanApplied($sSurfaceId, $sState, RunIntentDescribe($oIntent))
	Else
		GUICtrlSetData($g_hRunPlannerStatus, "Blocked")
		SetLog("Run Planner cannot start: " & $sReason, $COLOR_ERROR)
		RunEventLogPlanBlocked($sSurfaceId, $sReason)
	EndIf
	UpdateRunPlannerBanner()
EndFunc   ;==>btnRunPlannerApply

Func btnRunPlannerReset()
	For $i = 0 To UBound($g_aRunPlannerSettings, 1) - 1
		Local $hControl = $g_ahRunPlannerControls[$i]
		If $hControl = 0 Then ContinueLoop
		Local $sId = $g_aRunPlannerSettings[$i][$eRunPlannerSettingId]
		Switch StringLower($g_aRunPlannerSettings[$i][$eRunPlannerSettingType])
			Case "select", "multi-select"
				GUICtrlSetData($hControl, "")
				GUICtrlSetData($hControl, _RunPlannerOptionLabelList($sId), _RunPlannerDefaultLabel($sId, $g_aRunPlannerSettings[$i][$eRunPlannerSettingDefault]))
			Case "boolean"
				GUICtrlSetState($hControl, ($g_aRunPlannerSettings[$i][$eRunPlannerSettingDefault] ? $GUI_CHECKED : $GUI_UNCHECKED))
			Case Else
				GUICtrlSetData($hControl, $g_aRunPlannerSettings[$i][$eRunPlannerSettingDefault])
		EndSwitch
	Next
	_RunPlannerApplyAllNativeFixedStates()
	$g_sRunPlannerHeroIds = ""
	$g_oRunPlannerIntent = 0
	; Reset drops the applied plan, so the pacing that came with it goes too rather than outliving the plan that set it.
	RunPacingDeactivate()
	RunPlannerRefreshHeroSelection()
	GUICtrlSetData($g_hRunPlannerStatus, "")
	UpdateRunPlannerBanner()
	UpdateRunPlannerDetail("run.surface")
EndFunc   ;==>btnRunPlannerReset

Func cmbRunPlannerSurface()
	UpdateRunPlannerBanner()
	UpdateRunPlannerDetail("run.surface")
EndFunc   ;==>cmbRunPlannerSurface

Func cmbRunPlannerHeroes()
	UpdateRunPlannerDetail("run.heroes")
EndFunc   ;==>cmbRunPlannerHeroes

Func inpRunPlannerTownHall()
	UpdateRunPlannerDetail("run.town_hall")
EndFunc   ;==>inpRunPlannerTownHall

Func cmbRunPlannerStrategy()
	UpdateRunPlannerDetail("run.strategy")
EndFunc   ;==>cmbRunPlannerStrategy

Func cmbRunPlannerEmulator()
	UpdateRunPlannerDetail("runtime.emulator")
EndFunc   ;==>cmbRunPlannerEmulator

Func cmbRunPlannerUpgradePolicy()
	UpdateRunPlannerDetail("upgrade.policy")
EndFunc   ;==>cmbRunPlannerUpgradePolicy

Func chkRunPlannerDiagnostic()
	UpdateRunPlannerBanner()
EndFunc   ;==>chkRunPlannerDiagnostic

Func btnRunPlannerRefresh()
	Local $bHealthy = _RunPlannerServiceHealthy()
	Local $sService = ($bHealthy ? "Control center online" : "Control center offline")
	Local $sPlan = "no saved plan"
	Local $bSaved = FileExists(RunPlanFileDefaultPath())
	If $bSaved Then $sPlan = "plan saved " & FileGetTime(RunPlanFileDefaultPath(), 0, 1)
	_RunPlannerSetLabel($g_hRunPlannerStatus, $sService & " · " & $sPlan, ($bHealthy And $bSaved ? $COLOR_GREEN : $COLOR_MAROON))
EndFunc   ;==>btnRunPlannerRefresh

Func btnRunPlannerOpen()
	Local $sError = ""
	If Not _RunPlannerStartService($sError) Then
		GUICtrlSetData($g_hRunPlannerStatus, $sError)
		SetLog("Run Planner: " & $sError, $COLOR_ERROR)
		btnRunPlannerRefresh()
		Return
	EndIf
	ShellExecute($RUN_PLANNER_URL)
	GUICtrlSetData($g_hRunPlannerStatus, "Control center opened")
	btnRunPlannerRefresh()
EndFunc   ;==>btnRunPlannerOpen

Func btnRunPlannerLoad()
	Local $sError = ""
	Local $oIntent = RunPlanFileLoadIntent(RunPlanFileDefaultPath(), $sError)
	If Not IsObj($oIntent) Then
		$g_oRunPlannerIntent = 0
		_RunPlannerSetLabel($g_hRunPlannerStatus, "Rejected · " & $sError, $COLOR_MAROON)
		SetLog("Run Planner: " & $sError, $COLOR_ERROR)
		Return
	EndIf
	If Not RunIntentSetProfile($oIntent, $g_sProfileCurrentName) Then
		$g_oRunPlannerIntent = 0
		_RunPlannerSetLabel($g_hRunPlannerStatus, "Rejected · current profile could not be bound", $COLOR_MAROON)
		Return
	EndIf
	$g_oRunPlannerIntent = $oIntent
	Local $sReason = ""
	Local $bCanStart = RunIntentCanStart($oIntent, $sReason)
	If $bCanStart Then $bCanStart = RunExecutionContractValidate($oIntent, $sReason)
	If $bCanStart Then
		_RunPlannerSetLabel($g_hRunPlannerStatus, "Prepared · engine gates cleared", $COLOR_GREEN)
	Else
		_RunPlannerSetLabel($g_hRunPlannerStatus, "Prepared · blocked: " & $sReason, $COLOR_MAROON)
	EndIf
	SetLog("Run Planner: " & RunIntentDescribe($oIntent), $COLOR_SUCCESS)
EndFunc   ;==>btnRunPlannerLoad

Func tabRunPlanner()
	If $g_iGuiMode <> 1 Then Return
	RunPlannerSyncPlanFile()
	UpdateRunPlannerBanner()
	RunPlannerRefreshHeroSelection()
	btnRunPlannerRefresh()
EndFunc   ;==>tabRunPlanner
