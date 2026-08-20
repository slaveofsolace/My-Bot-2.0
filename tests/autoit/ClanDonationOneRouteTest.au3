#NoTrayIcon
#include <StringConstants.au3>
#include "..\..\COCBot\functions\Run\ClanDonationOneRoute.au3"

Global $g_iAssertions = 0
Global $g_iIssueCalls = 0
Global $g_iStopCalls = 0
Global $g_iStopAt = 0
Global $g_iHomeCalls = 0
Global $g_bIssueAccepted = True
Global $g_bNoGemReady = True
Global $g_oBefore = 0
Global $g_oAfter = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 10
	EndIf
EndFunc

Func FixtureReset()
	$g_iIssueCalls = 0
	$g_iStopCalls = 0
	$g_iStopAt = 0
	$g_iHomeCalls = 0
	$g_bIssueAccepted = True
	$g_bNoGemReady = True
	$g_oBefore = ClanDonationObservationCreate($CLAN_DONATION_STATE_STRUCTURED_READY, 3, "balloon", 4, 6, 5, "structured-icon")
	$g_oAfter = ClanDonationObservationCreate($CLAN_DONATION_STATE_POST_DONATED, 3, "balloon", 3, 5, 5, "structured-icon")
EndFunc

Func FixtureDetect($sPhase)
	If StringLower($sPhase) = "after" Then Return $g_oAfter
	Return $g_oBefore
EndFunc

Func FixtureIssueOne($iSlot, $sUnit)
	$g_iIssueCalls += 1
	Return $g_bIssueAccepted And $iSlot = 3 And $sUnit = "balloon"
EndFunc

Func FixtureStop()
	$g_iStopCalls += 1
	Return $g_iStopAt > 0 And $g_iStopCalls >= $g_iStopAt
EndFunc

Func FixtureNoGem()
	Return $g_bNoGemReady
EndFunc

Func FixtureHome()
	$g_iHomeCalls += 1
	Return True
EndFunc

Func FixtureRun()
	Return ClanDonationOneRouteRunAdapter("FixtureDetect", "FixtureIssueOne", "FixtureStop", "FixtureNoGem", "FixtureHome")
EndFunc

FixtureReset()
Local $oCommitted = FixtureRun()
AssertTrue($oCommitted.Item("state") = $CLAN_DONATION_OUTCOME_COMMITTED, "one structured unit commits")
AssertTrue($oCommitted.Item("attempts") = 1 And $oCommitted.Item("input_issued"), "one input receipt is truthful")
AssertTrue($oCommitted.Item("confirmed") And $oCommitted.Item("capacity_before") = 4 And $oCommitted.Item("capacity_after") = 3, "one-unit decrement is proved")
AssertTrue($g_iIssueCalls = 1 And $oCommitted.Item("home_proven"), "input runs once and Home is passively proved")

FixtureReset()
$g_oBefore = ClanDonationObservationCreate($CLAN_DONATION_STATE_UNAVAILABLE)
Local $oUnavailable = FixtureRun()
AssertTrue($oUnavailable.Item("state") = $CLAN_DONATION_OUTCOME_UNAVAILABLE, "no request is unavailable")
AssertTrue($g_iIssueCalls = 0, "unavailable route issues no input")

FixtureReset()
$g_oBefore = ClanDonationObservationCreate($CLAN_DONATION_STATE_STRUCTURED_READY, 3, "balloon", 4, 6, 5, "ocr", True)
Local $oFreeText = FixtureRun()
AssertTrue($oFreeText.Item("state") = $CLAN_DONATION_OUTCOME_UNCONFIRMED, "OCR or free text is rejected")
AssertTrue($g_iIssueCalls = 0, "rejected free text issues no input")

FixtureReset()
$g_oBefore = ClanDonationObservationCreate($CLAN_DONATION_STATE_STRUCTURED_READY, 3, "balloon", 4, 5, 5, "structured-icon")
Local $oReserve = FixtureRun()
AssertTrue($oReserve.Item("state") = $CLAN_DONATION_OUTCOME_UNCONFIRMED, "reserve floor is fail-closed")
AssertTrue($g_iIssueCalls = 0, "reserve failure issues no input")

FixtureReset()
$g_bNoGemReady = False
Local $oGem = FixtureRun()
AssertTrue($oGem.Item("state") = $CLAN_DONATION_OUTCOME_UNCONFIRMED, "no-gem guard blocks donation")
AssertTrue($oGem.Item("attempts") = 0 And $g_iIssueCalls = 0, "blocked donation consumes no attempt")

FixtureReset()
$g_bIssueAccepted = False
Local $oRejected = FixtureRun()
AssertTrue($oRejected.Item("state") = $CLAN_DONATION_OUTCOME_UNCONFIRMED, "rejected delivery is unconfirmed")
AssertTrue($oRejected.Item("attempts") = 1 And Not $oRejected.Item("input_issued") And $g_iIssueCalls = 1, "rejected delivery remains one attempt")

FixtureReset()
$g_oAfter = ClanDonationObservationCreate($CLAN_DONATION_STATE_POST_DONATED, 3, "balloon", 2, 4, 5, "structured-icon")
Local $oOverDrop = FixtureRun()
AssertTrue($oOverDrop.Item("state") = $CLAN_DONATION_OUTCOME_UNCONFIRMED, "a multi-unit decrement is never confirmed")
AssertTrue($oOverDrop.Item("input_issued") And $g_iIssueCalls = 1, "unconfirmed issued input is never retried")

For $i = 1 To 3
	FixtureReset()
	$g_iStopAt = $i
	Local $oStopped = FixtureRun()
	AssertTrue($oStopped.Item("state") = $CLAN_DONATION_OUTCOME_CANCELLED, "pre-input Stop cancels at boundary " & $i)
	AssertTrue($g_iIssueCalls = 0, "pre-input Stop issues nothing at boundary " & $i)
Next

FixtureReset()
$g_iStopAt = 4
Local $oPostStop = FixtureRun()
AssertTrue($oPostStop.Item("state") = $CLAN_DONATION_OUTCOME_UNCONFIRMED And $oPostStop.Item("input_issued"), "post-input Stop is irreversible uncertainty")
AssertTrue($g_iHomeCalls = 0 And $g_iIssueCalls = 1, "post-input Stop performs no capture or cleanup")

ConsoleWrite("Clan donation one-route tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
