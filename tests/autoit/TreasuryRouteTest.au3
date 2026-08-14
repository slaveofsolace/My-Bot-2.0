#NoTrayIcon
#include <StringConstants.au3>
#include "..\..\COCBot\functions\Run\TreasuryRoute.au3"

Global $g_iAssertions = 0
Global $g_sTreasuryStopStep = ""
Global $g_sTreasuryPhase = "castle"
Global $g_sTreasuryCollectState = $TREASURY_STATE_COLLECT_READY
Global $g_bTreasuryHome = True
Global $g_iTreasuryInputs = 0
Global $g_iTreasuryCleanupCalls = 0

Func AssertTrue($bCondition, $sMessage)
	$g_iAssertions += 1
	If Not $bCondition Then
		ConsoleWriteError("ASSERTION FAILED: " & $sMessage & @CRLF)
		Exit 10
	EndIf
EndFunc   ;==>AssertTrue

Func FixtureReset($sCollectState = $TREASURY_STATE_COLLECT_READY, $sStopStep = "", $bHome = True)
	$g_sTreasuryStopStep = $sStopStep
	$g_sTreasuryPhase = "castle"
	$g_sTreasuryCollectState = $sCollectState
	$g_bTreasuryHome = $bHome
	$g_iTreasuryInputs = 0
	$g_iTreasuryCleanupCalls = 0
EndFunc   ;==>FixtureReset

Func FixtureStop()
	Return $g_sTreasuryStopStep <> "" And $g_sTreasuryStopStep = $g_sTreasuryPhase
EndFunc   ;==>FixtureStop

Func FixtureDetectCastle()
	$g_sTreasuryPhase = "castle-ready"
	Return TreasuryObservationCreate($TREASURY_STATE_CASTLE_READY, 150, 250)
EndFunc   ;==>FixtureDetectCastle

Func FixtureIssueCastle($iX, $iY)
	$g_iTreasuryInputs += 1
	$g_sTreasuryPhase = "castle-issued"
	Return $iX = 150 And $iY = 250
EndFunc   ;==>FixtureIssueCastle

Func FixtureDetectEntry()
	$g_sTreasuryPhase = "entry-ready"
	Return TreasuryObservationCreate($TREASURY_STATE_ENTRY_READY, 300, 650)
EndFunc   ;==>FixtureDetectEntry

Func FixtureIssueEntry($iX, $iY)
	$g_iTreasuryInputs += 1
	$g_sTreasuryPhase = "entry-issued"
	Return $iX = 300 And $iY = 650
EndFunc   ;==>FixtureIssueEntry

Func FixtureDetectCollect()
	$g_sTreasuryPhase = "collect-ready"
	If $g_sTreasuryCollectState = $TREASURY_STATE_COLLECT_READY Then Return TreasuryObservationCreate($g_sTreasuryCollectState, 430, 650)
	Return TreasuryObservationCreate($g_sTreasuryCollectState)
EndFunc   ;==>FixtureDetectCollect

Func FixtureIssueCollect($iX, $iY)
	$g_iTreasuryInputs += 1
	$g_sTreasuryPhase = "collect-issued"
	Return $iX = 430 And $iY = 650
EndFunc   ;==>FixtureIssueCollect

Func FixtureDetectConfirm()
	$g_sTreasuryPhase = "confirm-ready"
	Return TreasuryObservationCreate($TREASURY_STATE_CONFIRM_READY, 500, 500)
EndFunc   ;==>FixtureDetectConfirm

Func FixtureIssueConfirm($iX, $iY)
	$g_iTreasuryInputs += 1
	$g_sTreasuryPhase = "confirm-issued"
	Return $iX = 500 And $iY = 500
EndFunc   ;==>FixtureIssueConfirm

Func FixtureCleanup()
	$g_iTreasuryCleanupCalls += 1
	$g_sTreasuryPhase = "cleanup"
	Return TreasuryCleanupCreate(1, True, $g_bTreasuryHome)
EndFunc   ;==>FixtureCleanup

Func FixtureRun()
	Return TreasuryRouteRunAdapter("FixtureDetectCastle", "FixtureIssueCastle", "FixtureDetectEntry", "FixtureIssueEntry", _
			"FixtureDetectCollect", "FixtureIssueCollect", "FixtureDetectConfirm", "FixtureIssueConfirm", "FixtureStop", "FixtureCleanup")
EndFunc   ;==>FixtureRun

Local $oInvalid = TreasuryObservationCreate($TREASURY_STATE_CONFIRM_READY, 900, 500)
AssertTrue(Not TreasuryObservationValid($oInvalid), "coordinates outside the viewport are rejected")

FixtureReset()
Local $oIssued = FixtureRun()
AssertTrue($oIssued.Item("state") = $TREASURY_OUTCOME_CONFIRM_ISSUED, "success is truthfully an issued confirmation, not a claimed transfer")
AssertTrue($g_iTreasuryInputs = 4, "success invokes exactly four action callbacks")
Local $aSteps = ["castle", "entry", "collect", "confirm", "close"]
For $sStep In $aSteps
	AssertTrue($oIssued.Item($sStep & "_attempts") = 1, $sStep & " is attempted exactly once")
	AssertTrue($oIssued.Item($sStep & "_issued"), $sStep & " has an accepted input receipt")
Next
AssertTrue($oIssued.Item("home_proven"), "success re-proves Home")

Local $aUnavailable = [$TREASURY_STATE_NOT_FULL, $TREASURY_STATE_HOME_STORAGE_FULL]
For $sUnavailable In $aUnavailable
	FixtureReset($sUnavailable)
	Local $oUnavailable = FixtureRun()
	AssertTrue($oUnavailable.Item("state") = $TREASURY_OUTCOME_UNAVAILABLE, $sUnavailable & " fails closed without transfer")
	AssertTrue(Not $oUnavailable.Item("collect_issued") And Not $oUnavailable.Item("confirm_issued"), $sUnavailable & " issues no transfer input")
	AssertTrue($g_iTreasuryInputs = 2, $sUnavailable & " only selects the exact Castle and Treasury entry")
Next

FixtureReset($TREASURY_STATE_COLLECT_MISSING)
Local $oMissing = FixtureRun()
AssertTrue($oMissing.Item("state") = $TREASURY_OUTCOME_UNCONFIRMED, "missing Collect is unconfirmed")
AssertTrue(Not $oMissing.Item("collect_issued") And Not $oMissing.Item("confirm_issued"), "missing Collect never falls back")

Local $aStopPoints = ["castle", "castle-ready", "castle-issued", "entry-ready", "entry-issued", "collect-ready", "collect-issued", "confirm-ready", "confirm-issued"]
For $sStop In $aStopPoints
	FixtureReset($TREASURY_STATE_COLLECT_READY, $sStop)
	Local $oStopped = FixtureRun()
	AssertTrue($oStopped.Item("state") = (($sStop = "castle" Or $sStop = "castle-ready") ? $TREASURY_OUTCOME_CANCELLED : $TREASURY_OUTCOME_UNCONFIRMED), _
			"Stop at " & $sStop & " preserves irreversible truth")
	AssertTrue($g_iTreasuryCleanupCalls = 0, "Stop at " & $sStop & " invokes no cleanup callback")
Next

FixtureReset($TREASURY_STATE_COLLECT_READY, "", False)
Local $oNoHome = FixtureRun()
AssertTrue($oNoHome.Item("state") = $TREASURY_OUTCOME_UNCONFIRMED, "accepted confirmation without Home proof remains unconfirmed")
AssertTrue($oNoHome.Item("confirm_issued"), "Home failure preserves the confirmation input receipt")

ConsoleWrite("Treasury route tests passed: " & $g_iAssertions & " assertions" & @CRLF)
Exit 0
