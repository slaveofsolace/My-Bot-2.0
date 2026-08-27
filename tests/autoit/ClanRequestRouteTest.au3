#NoTrayIcon
#include <StringConstants.au3>
#include "..\..\COCBot\functions\Run\NoPremiumPermitPolicy.au3"

; Pure contract harness stubs: this test validates request-only route contracts
; and fixture dispatch. The production entrypoints compile the real page
; recognition and clean-room detector graph.
Func IsAttackPage($bWriteLog = True)
        Return False
EndFunc   ;==>IsAttackPage

Func IsEndBattlePage($bWriteLog = True)
        Return False
EndFunc   ;==>IsEndBattlePage

Func IsReturnHomeBattlePage($useReturnValue = False, $makeDebugImageScreenshot = True)
        Return False
EndFunc   ;==>IsReturnHomeBattlePage

Func CleanRoomRedlineDetectorRuntimeReady()
        Return True
EndFunc   ;==>CleanRoomRedlineDetectorRuntimeReady

#include "..\..\COCBot\functions\Run\RunExecutionContract.au3"

Global $g_iAssertions = 0
Global $g_sFixtureBefore = $CLAN_REQUEST_STATE_AVAILABLE
Global $g_sFixtureAfter = $CLAN_REQUEST_STATE_ALREADY_MADE
Global $g_iFixtureStopCalls = 0
Global $g_iFixtureStopAt = 0
Global $g_iFixtureOpenCalls = 0
Global $g_iFixtureDialogCalls = 0
Global $g_iFixtureSendCalls = 0
Global $g_bFixtureSendAccepted = True
Global $g_iFixtureCloseCalls = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 10
	EndIf
EndFunc   ;==>AssertTrue

Func FixtureReset($sBefore = $CLAN_REQUEST_STATE_AVAILABLE, $sAfter = $CLAN_REQUEST_STATE_ALREADY_MADE, $iStopAt = 0, $bSendAccepted = True)
	$g_sFixtureBefore = $sBefore
	$g_sFixtureAfter = $sAfter
	$g_iFixtureStopCalls = 0
	$g_iFixtureStopAt = $iStopAt
	$g_iFixtureOpenCalls = 0
	$g_iFixtureDialogCalls = 0
	$g_iFixtureSendCalls = 0
	$g_bFixtureSendAccepted = $bSendAccepted
	$g_iFixtureCloseCalls = 0
EndFunc   ;==>FixtureReset

Func FixtureStopRequested()
	$g_iFixtureStopCalls += 1
	Return $g_iFixtureStopAt > 0 And $g_iFixtureStopCalls >= $g_iFixtureStopAt
EndFunc   ;==>FixtureStopRequested

Func FixtureOpenOverview()
	$g_iFixtureOpenCalls += 1
	Return True
EndFunc   ;==>FixtureOpenOverview

Func FixtureDetectState($sPhase)
	If StringLower($sPhase) = "after" Then Return ClanRequestObservationCreate($g_sFixtureAfter, 740, 470)
	Return ClanRequestObservationCreate($g_sFixtureBefore, 740, 470)
EndFunc   ;==>FixtureDetectState

Func FixtureOpenDialog($iX, $iY)
	$g_iFixtureDialogCalls += 1
	If $iX < 0 Or $iY < 0 Then Return 0
	Return ClanRequestObservationCreate($CLAN_REQUEST_STATE_SEND_READY, 500, 600)
EndFunc   ;==>FixtureOpenDialog

Func FixtureIssueSend($iX, $iY)
	$g_iFixtureSendCalls += 1
	Return $g_bFixtureSendAccepted And $iX = 500 And $iY = 600
EndFunc   ;==>FixtureIssueSend

Func FixtureCloseAndProveHome()
	$g_iFixtureCloseCalls += 1
	Return True
EndFunc   ;==>FixtureCloseAndProveHome

Func FixtureRun()
	Return ClanRequestRouteRunAdapter("FixtureOpenOverview", "FixtureDetectState", "FixtureOpenDialog", _
			"FixtureIssueSend", "FixtureStopRequested", "FixtureCloseAndProveHome")
EndFunc   ;==>FixtureRun

Func CreateClanRequestIntent($bDiagnostic = True)
	Local $oPlan = RunPlanCreateDefault("regular", $CLAN_REQUEST_ROUTE_STRATEGY, "profile-current")
	$oPlan.Item("planned_town_hall") = 18
	$oPlan.Item("max_battles") = 0
	$oPlan.Item("max_failures") = 0
	$oPlan.Item("army_wait_for_full") = False
	$oPlan.Item("donate_request_when_short") = True
	$oPlan.Item("emulator") = "bluestacks5"
	$oPlan.Item("emulator_instance") = "Pie64"

	Local $oLoadout = HeroLoadoutCreate(18)
	Local $sError = ""
	Local $oIntent = RunIntentCreate($oPlan, "regular", $oLoadout, $sError)
	If Not IsObj($oIntent) Then Return SetError(1, 0, 0)
	If Not RunIntentSetProfile($oIntent, "MyVillage") Then Return SetError(2, 0, 0)
	If $bDiagnostic And Not RunIntentEnableDiagnostic($oIntent, "supervised request-only fixture", $sError) Then _
		Return SetError(3, 0, 0)
	Return $oIntent
EndFunc   ;==>CreateClanRequestIntent

Local $sError = ""
Local $oIntent = CreateClanRequestIntent()
AssertTrue(IsObj($oIntent), "request-only intent is created")
AssertTrue(ClanRequestRouteSelected($oIntent), "request-only route is explicitly selected")
AssertTrue(ClanRequestRouteAccountMatches($oIntent, "MyVillage"), "route is bound to the exact current profile")
AssertTrue(Not ClanRequestRouteAccountMatches($oIntent, "OtherVillage"), "route rejects a different active profile")
AssertTrue(ClanRequestRouteValidate($oIntent, $sError), "request-only contract validates: " & $sError)
AssertTrue(RunExecutionContractValidate($oIntent, $sError), "execution contract dispatches to request-only route: " & $sError)

Local $oNoDiagnostic = CreateClanRequestIntent(False)
AssertTrue(Not RunExecutionContractValidate($oNoDiagnostic, $sError), "request-only route rejects missing diagnostic acknowledgement")
Local $oNoProfile = CreateClanRequestIntent()
$oNoProfile.Item("profile_id") = ""
AssertTrue(Not RunExecutionContractValidate($oNoProfile, $sError), "request-only route rejects an empty account binding")
Local $oDonationPlan = $oIntent.Item("plan")
$oDonationPlan.Item("donate_mode") = "matching"
AssertTrue(Not RunExecutionContractValidate($oIntent, $sError), "request-only route rejects donation mode")
$oDonationPlan.Item("donate_mode") = "off"
$oDonationPlan.Item("donate_request_when_short") = False
AssertTrue(Not RunExecutionContractValidate($oIntent, $sError), "request-only route requires Request when available")
$oDonationPlan.Item("donate_request_when_short") = True
$oDonationPlan.Item("events_collect_resources") = True
AssertTrue(Not RunExecutionContractValidate($oIntent, $sError), "request-only route rejects collectors")
$oDonationPlan.Item("events_collect_resources") = False
AssertTrue(RunExecutionContractValidate($oIntent, $sError), "restoring request-only settings clears side-effect gates: " & $sError)

FixtureReset()
Local $oCommitted = FixtureRun()
AssertTrue(IsObj($oCommitted), "committed fixture returns an outcome")
AssertTrue($oCommitted.Item("state") = $CLAN_REQUEST_OUTCOME_COMMITTED, "Available -> AlreadyMade is committed")
AssertTrue($oCommitted.Item("before_state") = $CLAN_REQUEST_STATE_AVAILABLE And _
		$oCommitted.Item("after_state") = $CLAN_REQUEST_STATE_ALREADY_MADE, "both fresh states are recorded")
AssertTrue($oCommitted.Item("send_issued") And $oCommitted.Item("send_attempts") = 1, "one Send is latched")
AssertTrue($g_iFixtureSendCalls = 1, "committed route calls the irreversible adapter exactly once")
AssertTrue($g_iFixtureStopCalls = 6, "route polls Stop before every state/input boundary")
AssertTrue($g_iFixtureCloseCalls = 1 And $oCommitted.Item("home_proven"), "route closes once and proves Home")

FixtureReset($CLAN_REQUEST_STATE_ALREADY_MADE)
Local $oUnavailable = FixtureRun()
AssertTrue($oUnavailable.Item("state") = $CLAN_REQUEST_OUTCOME_UNAVAILABLE, "AlreadyMade is an unavailable outcome")
AssertTrue($g_iFixtureDialogCalls = 0 And $g_iFixtureSendCalls = 0, "unavailable route issues no dialog or Send")

FixtureReset($CLAN_REQUEST_STATE_AVAILABLE, $CLAN_REQUEST_STATE_AVAILABLE)
Local $oUnconfirmed = FixtureRun()
AssertTrue($oUnconfirmed.Item("state") = $CLAN_REQUEST_OUTCOME_UNCONFIRMED, "unchanged post-state is unconfirmed")
AssertTrue($oUnconfirmed.Item("send_issued") And $g_iFixtureSendCalls = 1, "unconfirmed Send remains latched exactly once")
AssertTrue($oUnconfirmed.Item("send_attempts") = 1, "unconfirmed route never grants a retry")

FixtureReset($CLAN_REQUEST_STATE_AVAILABLE, $CLAN_REQUEST_STATE_ALREADY_MADE, 0, False)
Local $oRejectedSend = FixtureRun()
AssertTrue($oRejectedSend.Item("state") = $CLAN_REQUEST_OUTCOME_UNCONFIRMED, "rejected input command is unconfirmed")
AssertTrue(Not $oRejectedSend.Item("send_issued"), "rejected input command is not reported as issued")
AssertTrue($oRejectedSend.Item("send_attempts") = 1 And $g_iFixtureSendCalls = 1, "rejected input still consumes the one attempt")

For $iStopPoint = 1 To 4
	FixtureReset($CLAN_REQUEST_STATE_AVAILABLE, $CLAN_REQUEST_STATE_ALREADY_MADE, $iStopPoint)
	Local $oCancelled = FixtureRun()
	AssertTrue($oCancelled.Item("state") = $CLAN_REQUEST_OUTCOME_CANCELLED, "pre-Send Stop point " & $iStopPoint & " cancels")
	AssertTrue($g_iFixtureSendCalls = 0, "pre-Send Stop point " & $iStopPoint & " issues no Send")
	AssertTrue($g_iFixtureCloseCalls = 0, "pre-Send Stop point " & $iStopPoint & " invokes no close/Home callback")
Next

FixtureReset($CLAN_REQUEST_STATE_AVAILABLE, $CLAN_REQUEST_STATE_ALREADY_MADE, 5)
Local $oStoppedAfterSend = FixtureRun()
AssertTrue($oStoppedAfterSend.Item("state") = $CLAN_REQUEST_OUTCOME_UNCONFIRMED, "post-Send Stop is unconfirmed, not cancelled")
AssertTrue($oStoppedAfterSend.Item("send_issued") And $g_iFixtureSendCalls = 1, "post-Send Stop preserves irreversible Send truth")
AssertTrue($g_iFixtureCloseCalls = 0 And Not $oStoppedAfterSend.Item("home_proven"), "post-Send Stop issues no capture/close input")

Local $oStartedEvent = RunEventCreate("maintenance.clan-request.started", 1, 1000, "request-fixture", "info", _
		"Request-only pass started", "MyVillage", "regular", 0, 0, 0, 0, 0, $RUN_VERIFICATION_DIAGNOSTIC)
AssertTrue(IsObj($oStartedEvent), "request started event is accepted")
Local $oCommittedEvent = RunEventCreate("maintenance.clan-request.committed", 2, 1100, "request-fixture", "info", _
		"Available -> AlreadyMade", "MyVillage", "regular", 0, 0, 0, 0, 0, $RUN_VERIFICATION_DIAGNOSTIC)
AssertTrue(IsObj($oCommittedEvent), "request committed event is accepted")
Local $oUnconfirmedEvent = RunEventCreate("maintenance.clan-request.unconfirmed", 3, 1200, "request-fixture", "error", _
		"send_issued=true", "MyVillage", "regular", 0, 0, 0, 0, 0, $RUN_VERIFICATION_DIAGNOSTIC)
AssertTrue(IsObj($oUnconfirmedEvent), "request unconfirmed event is accepted")

ConsoleWrite("Clan request route tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
