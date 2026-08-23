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
Local $sMain = FileRead($sRoot & "\MyBot.run.au3")

Local $iProbeStart = StringInStr($sParent, "Func MBRFuncProbeEngine(", 1)
Local $iProbeEnd = StringInStr($sParent, "EndFunc", 1, 1, $iProbeStart)
Local $sProbe = StringMid($sParent, $iProbeStart, $iProbeEnd - $iProbeStart)
AssertTrue(StringInStr($sProbe, "Run(", 1) = 0, "static probe never launches a helper")
AssertTrue(StringInStr($sProbe, "DllCall(", 1) = 0, "static probe never invokes a managed export")
AssertTrue(StringInStr($sProbe, "$g_bMBRFuncEngineSupervisorValid", 1) > 0, "static probe requires launcher supervision")

Local $iInitStart = StringInStr($sParent, "Func MBRFuncInitialize(", 1)
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
AssertTrue(StringInStr($sParent, "Global $g_sMBRFuncEngineReceiptStartRequestId", 1) > 0, "receipt keeps an immutable request id per generation")
AssertTrue(StringInStr($sParent, "$g_sMBRFuncEngineReceiptStartRequestId = $sStartRequestId", 1) > 0, "initialization binds the active request id once")
AssertTrue(StringInStr($sReceipt, "$g_sMBRFuncEngineReceiptStartRequestId", 1) > 0 And StringInStr($sReceipt, "_MBRFuncCurrentStartRequestId()", 1) = 0, "publisher retains the immutable request id after native terminalization")
AssertTrue(StringInStr($sInit, "$g_iMBRFuncEngineReceiptSequence = 0", 1) > 0, "initialization resets receipt sequence for the next generation")
AssertTrue(StringInStr($sInit, '$g_sMBRFuncEngineReceiptHistory = ""', 1) > 0, "initialization resets receipt history for the next generation")
Local $iPoolStart = StringInStr($sParent, "Func setProcessingPoolSize(", 1)
Local $iPoolEnd = StringInStr($sParent, "EndFunc", 1, 1, $iPoolStart)
Local $sPool = StringMid($sParent, $iPoolStart, $iPoolEnd - $iPoolStart)
AssertTrue(StringInStr($sParent, "Func _MBRFuncAutomaticProcessingPoolSize()", 1) > 0, "automatic processing pool has an explicit resolver")
AssertTrue(StringInStr($sParent, "GetActiveProcessorCount", 1) > 0, "automatic processing pool uses the Windows active processor count")
AssertTrue(StringInStr($sPool, "_MBRFuncAutomaticProcessingPoolSize()", 1) > 0, "zero processing-pool setting resolves before the managed export")
AssertTrue(StringInStr($sPool, "$i = -1", 1) = 0, "processing-pool export never receives the blocking minus-one sentinel")
Local $iMaxStart = StringInStr($sParent, "Func setMaxDegreeOfParallelism(", 1)
Local $iMaxEnd = StringInStr($sParent, "EndFunc", 1, 1, $iMaxStart)
Local $sMax = StringMid($sParent, $iMaxStart, $iMaxEnd - $iMaxStart)
AssertTrue(StringInStr($sMax, "If $i < 1 Then $i = -1", 1) > 0, "automatic parallelism uses the proven managed sentinel after pool warmup")
Local $iAndroidPidStart = StringInStr($sParent, "Func setAndroidPID(", 1)
Local $iAndroidPidEnd = StringInStr($sParent, "EndFunc", 1, 1, $iAndroidPidStart)
Local $sAndroidPid = StringMid($sParent, $iAndroidPidStart, $iAndroidPidEnd - $iAndroidPidStart)
AssertTrue(StringInStr($sAndroidPid, '$g_sAndroidEmulator = "BlueStacks5"', 1) > 0 And StringInStr($sAndroidPid, "$g_bAndroidAdbScreencap", 1) > 0 And StringInStr($sAndroidPid, "$g_bAndroidAdbClick", 1) > 0, "BlueStacks5 managed binding requires the verified ADB screenshot and click surface")
AssertTrue(StringInStr($sAndroidPid, "$pid = 0", 1) > 0 And StringInStr($sAndroidPid, "exact ADB surface owns player PID", 1) > 0, "BlueStacks5 managed binding stays detached from the player process")
Local $iManagedBoundStart = StringInStr($sParent, "Func MBRFuncManagedLaunchBound()", 1)
Local $iManagedBoundEnd = StringInStr($sParent, "EndFunc", 1, 1, $iManagedBoundStart)
Local $sManagedBound = StringMid($sParent, $iManagedBoundStart, $iManagedBoundEnd - $iManagedBoundStart)
AssertTrue(StringInStr($sManagedBound, "$g_bMBRFuncBackendHost And $g_bMBRFuncEngineSupervisorValid", 1) > 0, "managed launch binding requires the exact supervised backend")
Local $iNetworkGate = StringInStr($sMain, "If MBRFuncManagedLaunchBound() Then", 1)
Local $iNetworkGateEnd = StringInStr($sMain, "EndIf", 1, 1, $iNetworkGate)
Local $sNetworkGate = StringMid($sMain, $iNetworkGate, $iNetworkGateEnd - $iNetworkGate)
AssertTrue(StringInStr($sNetworkGate, "Managed local runtime skipped", 1) > 0, "managed package startup declares its local-only version policy")
AssertTrue(StringInStr($sNetworkGate, "CheckVersion()", 1) > StringInStr($sNetworkGate, "Else", 1), "legacy version lookup remains reachable only outside the managed path")

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
Local $iLaunch = StringInStr($sStart, "_BotOpenHomeEnsureExactBlueStacks(", 1)
Local $iInitialize = StringInStr($sStart, "MBRFuncInitialize()", 1)
Local $iAuthorization = StringInStr($sStart, "ForumAuthentication()", 1)
Local $iResume = StringInStr($sStart, "ResumeAndroid()", 1)
AssertTrue($iGate > 0 And $iLaunch > $iGate And $iInitialize > $iLaunch And $iAuthorization > $iInitialize And $iResume > $iAuthorization, "BotStart launches the exact game before managed attachment and gates later input on real-host initialization")

ConsoleWrite("Engine supervision lifecycle tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
