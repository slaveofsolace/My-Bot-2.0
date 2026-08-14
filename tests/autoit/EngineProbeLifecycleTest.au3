#NoTrayIcon
; Static lifecycle contract for supervised managed-engine initialization. This test never launches the DLL.

Global $g_iAssertions = 0

Func _EngineProbeFixtureRequestId()
	Return "fixture-start-request"
EndFunc   ;==>_EngineProbeFixtureRequestId

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 10
	EndIf
EndFunc   ;==>AssertTrue

Local $sRoot = @ScriptDir & "\..\.."
Local $sParent = FileRead($sRoot & "\COCBot\functions\Other\MBRFunc.au3")
Local $sAction = FileRead($sRoot & "\COCBot\MBR GUI Action.au3")

Local $iProbeStart = StringInStr($sParent, "Func MBRFuncProbeEngine(", 1)
Local $iProbeEnd = StringInStr($sParent, "EndFunc", 1, 1, $iProbeStart)
Local $sProbe = StringMid($sParent, $iProbeStart, $iProbeEnd - $iProbeStart)
AssertTrue(StringInStr($sProbe, "Run(", 1) = 0, "static probe never launches a helper")
AssertTrue(StringInStr($sProbe, "DllCall(", 1) = 0, "static probe never invokes a managed export")
AssertTrue(StringInStr($sProbe, "$g_bMBRFuncEngineSupervisorValid", 1) > 0, "static probe requires launcher supervision")

Local $iInitStart = StringInStr($sParent, "Func MBRFuncInitialize()", 1)
Local $iInitEnd = StringInStr($sParent, "EndFunc", 1, 1, $iInitStart)
Local $sInit = StringMid($sParent, $iInitStart, $iInitEnd - $iInitStart)
Local $aOrdered[13] = [ _
	'_MBRFuncPublishEngineReceipt("prepared")', _
	'_MBRFuncPublishEngineReceipt("pool-entered")', _
	"setProcessingPoolSize(", _
	'_MBRFuncPublishEngineReceipt("pool-returned")', _
	'_MBRFuncPublishEngineReceipt("max-entered")', _
	"setMaxDegreeOfParallelism(", _
	'_MBRFuncPublishEngineReceipt("max-returned")', _
	'_MBRFuncPublishEngineReceipt("android-entered")', _
	"setAndroidPID(", _
	'_MBRFuncPublishEngineReceipt("android-returned")', _
	'_MBRFuncPublishEngineReceipt("gui-entered")', _
	"SetBotGuiPID(", _
	'_MBRFuncPublishEngineReceipt("initialized")']
Local $iPrevious = 0
For $sNeedle In $aOrdered
	Local $iOffset = StringInStr($sInit, $sNeedle, 1)
	AssertTrue($iOffset > $iPrevious, "real-host phase/call ordering retains " & $sNeedle)
	$iPrevious = $iOffset
Next

Local $iReceiptStart = StringInStr($sParent, "Func _MBRFuncPublishEngineReceipt(", 1)
Local $iReceiptEnd = StringInStr($sParent, "EndFunc", 1, 1, $iReceiptStart)
Local $sReceipt = StringMid($sParent, $iReceiptStart, $iReceiptEnd - $iReceiptStart)
Local $aReceiptFields[12] = ["schema", "token", "launcher_pid", "launcher_created", "controller_pid", "controller_created", "backend_pid", "backend_created", "parent_pid", "phase", "start_request_id", "sequence"]
For $sField In $aReceiptFields
	AssertTrue(StringInStr($sReceipt, $sField, 1) > 0, "receipt binds " & $sField)
Next
Local $aAtomic[6] = ["FileOpen(", "FileWrite(", "FileFlush(", "FileClose(", "FileMove(", "FileRead("]
$iPrevious = 0
For $sNeedle In $aAtomic
	Local $iOffset = StringInStr($sReceipt, $sNeedle, 1)
	AssertTrue($iOffset > $iPrevious, "receipt atomic order retains " & $sNeedle)
	$iPrevious = $iOffset
Next
AssertTrue(StringInStr($sParent, 'EnvSet($g_sMBRFuncEngineTokenEnv, "")', 1) > 0, "backend clears inherited token")
AssertTrue(StringInStr($sParent, '"^[0-9a-f]{64}$"', 1) > 0, "token grammar is exact")
AssertTrue(StringInStr($sParent, '"^[0-9a-f]{16}$"', 1) > 0, "creation-id grammar matches launcher FILETIME")
AssertTrue(StringInStr($sParent, '^mybot\.run(?:\.minigui)?\.(?:exe|au3)$', 1) > 0, "Mini and backend capture inherited context")
AssertTrue(StringInStr($sParent, "If $g_bMBRFuncEngineContextHost Then", 1) > 0, "context hosts immediately clear inherited environment")
AssertTrue(StringInStr($sReceipt, "$sLauncherCreated <> $g_sMBRFuncEngineLauncherCreated", 1) > 0, "receipt requires the live launcher creation identity")

; AutoIt string dispatch is Call(), not IsFunc(). This executable regression catches the exact
; field failure that previously made every supervised Start reject before publishing prepared.
Local $sFixtureCallback = "_EngineProbeFixtureRequest" & "Id"
AssertTrue(IsFunc($sFixtureCallback) = 0, "IsFunc rejects a string function name")
Local $vFixtureRequestId = Call($sFixtureCallback)
Local $iFixtureCallError = @error
Local $iFixtureCallExtended = @extended
AssertTrue($iFixtureCallError = 0 And $iFixtureCallExtended = 0, "Call dispatches a present string callback")
AssertTrue($vFixtureRequestId = "fixture-start-request", "Call returns the exact supervised Start id")
Local $sMissingFixtureCallback = "_EngineProbeMissingRequest" & "Id"
Call($sMissingFixtureCallback)
AssertTrue(@error = 0xDEAD And @extended = 0xBEEF, "Call fails closed for a missing string callback")

Local $iRequestIdStart = StringInStr($sParent, "Func _MBRFuncCurrentStartRequestId()", 1)
Local $iRequestIdEnd = StringInStr($sParent, "EndFunc", 1, 1, $iRequestIdStart)
Local $sRequestIdBody = StringMid($sParent, $iRequestIdStart, $iRequestIdEnd - $iRequestIdStart)
AssertTrue(StringInStr($sRequestIdBody, "IsFunc($sCallback)", 1) = 0, "Start-id lookup never passes a string to IsFunc")
AssertTrue(StringInStr($sRequestIdBody, "Call($sCallback)", 1) > 0 And StringInStr($sRequestIdBody, "@error", 1) > 0, "Start-id lookup dispatches dynamically and checks Call failure")

Local $iStart = StringInStr($sAction, "Func BotStart(", 1)
Local $iStartEnd = StringInStr($sAction, "EndFunc", 1, 1, $iStart)
Local $sStart = StringMid($sAction, $iStart, $iStartEnd - $iStart)
Local $iGate = StringInStr($sStart, "MBRFuncProbeEngine(", 1)
Local $iInitialize = StringInStr($sStart, "MBRFuncInitialize()", 1)
Local $iAuthorization = StringInStr($sStart, "ForumAuthentication()", 1)
Local $iResume = StringInStr($sStart, "ResumeAndroid()", 1)
AssertTrue($iGate > 0 And $iInitialize > $iGate And $iAuthorization > $iInitialize And $iResume > $iAuthorization, "BotStart gates input on real-host initialization")

ConsoleWrite("Engine supervision lifecycle tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
