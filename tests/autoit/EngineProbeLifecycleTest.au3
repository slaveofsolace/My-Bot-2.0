#NoTrayIcon
; Static lifecycle contract for the managed engine probe. This test never launches the helper or DLL.

Global $g_iAssertions = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 10
	EndIf
EndFunc   ;==>AssertTrue

Local $sRoot = @ScriptDir & "\..\.."
Local $sHelper = FileRead($sRoot & "\MyBot.run.EngineProbe.au3")
Local $sParent = FileRead($sRoot & "\COCBot\functions\Other\MBRFunc.au3")
Local $sConfig = FileRead($sRoot & "\MyBot.run.EngineProbe.exe.config")

AssertTrue(StringInStr($sHelper, "DllClose(", 1) = 0, "helper never enters mixed-mode DLL teardown")
Local $iCall = StringInStr($sHelper, "DllCall(", 1)
Local $iValidated = StringInStr($sHelper, "If $iProbeError Or Not IsArray($aProbe) Then Exit 4", 1)
Local $iPublished = StringInStr($sHelper, '_EngineProbePublish($sTokenPath, $ENGINE_PROBE_PROTOCOL & "|call-returned")', 1)
AssertTrue($iCall > 0 And $iValidated > $iCall And $iPublished > $iValidated, "versioned success follows a validated call")

Local $aPhases[3] = ["opened", "call-entered", "call-returned"]
For $sPhase In $aPhases
	AssertTrue(StringInStr($sHelper, '$ENGINE_PROBE_PROTOCOL & "|' & $sPhase & '"', 1) > 0, "helper publishes phase " & $sPhase)
	AssertTrue(StringInStr($sParent, 'Return "' & $sPhase & '"', 1) > 0, "parent recognizes phase " & $sPhase)
Next

Local $iProbeStart = StringInStr($sParent, "Func MBRFuncProbeEngine(", 1)
Local $iProbeEnd = StringInStr($sParent, "EndFunc", 1, 1, $iProbeStart)
Local $sProbe = StringMid($sParent, $iProbeStart, $iProbeEnd - $iProbeStart)
Local $iCancel = StringInStr($sProbe, "$g_iBotAction = $eBotStop Or $g_iBotAction = $eBotClose", 1)
Local $iRead = StringInStr($sProbe, "FileRead($sToken)", 1)
Local $iReap = StringInStr($sProbe, "MBRFuncEngineProbeEnsureHelperGone($iProbePid, 1)", 1)
Local $iGone = StringInStr($sProbe, "If Not ProcessExists($iProbePid) Then", 1)
Local $iPassed = StringInStr($sProbe, '$g_sMBRFuncEngineProbeState = "passed"', 1, 1, $iGone)
Local $iNonce = StringInStr($sProbe, "Random(100000, 999999, 1)", 1)
Local $iPhasePath = StringInStr($sProbe, 'Local $sPhasePath = $sToken & ".phase"', 1)
Local $iPrelaunchCleanup = StringInStr($sProbe, "If Not MBRFuncEngineProbeCleanupArtifacts($sToken, $sPhasePath, 0) Then", 1)
Local $iLaunch = StringInStr($sProbe, "Run('", 1)
AssertTrue($iCancel > 0 And $iCancel < $iRead, "Stop and Close win before success receipt consumption")
AssertTrue(StringInStr($sProbe, '$sError = "Engine start was cancelled"', 1) > 0, "cancellation wording is preserved")
AssertTrue($iReap > $iRead And $iGone > $iReap And $iPassed > $iGone, "parent proves exact helper exit before passing")
AssertTrue(StringInStr($sProbe, "$iTimeoutMs = 15000", 1) > 0, "default deadline remains 15 seconds")
AssertTrue($iNonce > 0 And $iPhasePath > $iNonce And $iPrelaunchCleanup > $iPhasePath And $iLaunch > $iPrelaunchCleanup, "unique receipts are verified clean before helper launch")

Local $iRejectStart = StringInStr($sParent, "Func MBRFuncEngineProbeRejectReceipt(", 1)
Local $iRejectEnd = StringInStr($sParent, "EndFunc", 1, 1, $iRejectStart)
Local $sReject = StringMid($sParent, $iRejectStart, $iRejectEnd - $iRejectStart)
Local $iRejectReap = StringInStr($sReject, "MBRFuncEngineProbeEnsureHelperGone($iProbePid)", 1)
Local $iRejectCleanup = StringInStr($sReject, "MBRFuncEngineProbeCleanupArtifacts($sToken, $sPhasePath, $iProbePid)", 1)
Local $iRejectReapCheck = StringInStr($sReject, "If Not $bHelperGone Then", 1)
Local $iRejectCleanupCheck = StringInStr($sReject, "ElseIf Not $bArtifactsCleared Then", 1)
Local $iRejectReturn = StringInStr($sReject, "Return False", 1)
AssertTrue($iRejectReap > 0 And $iRejectCleanup > $iRejectReap And $iRejectReapCheck > $iRejectCleanup And $iRejectCleanupCheck > $iRejectReapCheck And $iRejectReturn > $iRejectCleanupCheck, "receipt rejection checks exact PID reap and artifact cleanup before return")
AssertTrue(StringInStr($sProbe, 'Return MBRFuncEngineProbeRejectReceipt($sError, "Managed engine probe success receipt could not be consumed"', 1) > 0, "unconsumable receipt uses verified rejection cleanup")
AssertTrue(StringInStr($sProbe, 'Return MBRFuncEngineProbeRejectReceipt($sError, "Managed engine probe returned an invalid receipt"', 1) > 0, "invalid receipt uses verified rejection cleanup")

AssertTrue(StringInStr($sConfig, "useLegacyV2RuntimeActivationPolicy", 1) = 0, "legacy CLR v2 activation policy is absent")
AssertTrue(StringInStr($sConfig, 'supportedRuntime version="v4.0"', 1) > 0, "CLR v4 remains pinned")
AssertTrue(StringInStr($sConfig, '<probing privatePath="lib" />', 1) > 0, "private lib probing remains configured")

ConsoleWrite("Engine probe lifecycle tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
